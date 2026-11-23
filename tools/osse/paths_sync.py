#!/usr/bin/env python3
"""Reads Tom's Paths ahead boards from the Gus relay so Claude can bring them into the vault (the `paths` skill).
  python3 tools/osse/paths_sync.py show [BOARD]        what Tom changed that the vault does not say yet
  python3 tools/osse/paths_sync.py adopt BOARD CARD "Plan name"   swap one of Tom's cards for the plan written from it
  python3 tools/osse/paths_sync.py tidy                drop Tom's links the vault now says itself (run after build.py)
  python3 tools/osse/paths_sync.py settle [BOARD]      clear Tom's edits and drops once the vault holds them (run after build.py)
  python3 tools/osse/paths_sync.py export DIR          write each board as a .canvas file (JSON Canvas 1.0)
Add --mock to use the local relay stand-in (relay/gus/mock.py, key test-gm).
The game master key is read from the macOS Keychain inside this process and never printed. Writes only to the relay."""
import json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402

RELAY = "https://2srnsytz3rqi3jke23bz643jhq0irvei.lambda-url.ca-central-1.on.aws"
MOCK = "--mock" in sys.argv


def key():
    if MOCK:
        return "test-gm"
    return subprocess.check_output(["security", "find-generic-password", "-a", "osse", "-s", "osse-gus-gm", "-w"]).decode().strip()


def call(method, body=None):
    url = ("http://localhost:8714" if MOCK else RELAY) + "/paths"
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"x-gus-key": key(), "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def graph():
    g = json.load(open(os.path.join(build.VAULT, ".osse", "graph.json"), encoding="utf-8"))
    return g, {n["id"]: n for n in g["nodes"]}


def plan_facts(nodes):
    """For each live plan: the plans it needs (plan:/played:), its options, and its boards."""
    import pages, paths
    site = pages.Site(json.load(open(os.path.join(build.VAULT, ".osse", "graph.json"), encoding="utf-8")))
    _, _, _, data, _ = paths.collect(site)
    return data, site.cur


def label(nid, board, data):
    if nid == "now" or nid.startswith("start"):
        return f"the start of {nid[6:]}" if nid.startswith("start:") else "Now"
    if nid.startswith("p:"):
        return f"plan [[{nid[2:]}]]"
    c = board["cards"].get(nid)
    return f'card {nid} "{c["title"] or "untitled"}"' if c else nid


def boards(doc):
    out = {}
    for name, cv in (doc.get("lanes") or {}).items():
        b = {"placed": {}, "cards": {}, "edges": [], "edits": {}}
        for n in cv.get("nodes", []):
            o = n.get("osse") or {}
            if o.get("plan"):
                if o.get("edit"):
                    b["edits"][o["plan"]] = o["edit"]
                if not o.get("tray"):
                    b["placed"][o["plan"]] = o.get("session") or o.get("column", "")
            elif o.get("card"):
                b["cards"][n["id"]] = {"kind": o.get("kind", "note"), "title": o.get("title", ""), "body": o.get("body", ""),
                                       "column": o.get("session") or o.get("column", "")}
        b["edges"] = [{"id": e["id"], "from": (e.get("osse") or {}).get("from") or e["fromNode"], "to": e["toNode"], "label": e.get("label", "")}
                      for e in cv.get("edges", []) if (e.get("osse") or {}).get("own")]
        out[name] = b
    return out


def covered(e, data):
    """True when the vault already says what this link says."""
    if not (e["from"].startswith("p:") and e["to"].startswith("p:")):
        return False
    a, b = e["from"][2:], e["to"][2:]
    if b in data and any(r["k"] in ("plan", "played") and r["a"] == a for r in data[b]["req"]):
        return True
    return a in data and any(o["to"] == b for o in data[a]["options"])


def show(only=None):
    doc = call("GET")
    data, cur = plan_facts(None)
    bs = boards(doc)
    if not bs:
        print("No boards saved yet."); return
    print(f"Boards saved {doc.get('saved_at', '?')} (ms), vault after S{cur}.")
    for name, b in bs.items():
        if only and only != name:
            continue
        lines = []
        for pid, col in b["placed"].items():
            d = data.get(pid)
            if not d:
                lines.append(f"- [[{pid}]] is on the board but no longer live: leave it, the page drops it")
                continue
            tgt = d["target"].upper()
            want = "" if col == "Later" else col
            if want != tgt:
                lines.append(f"- [[{pid}]]: placed in {col}; vault target is {d['target'] or 'empty'} → set target: {want or '(empty)'}")
            if name not in d["lanes"] and name != "world":
                lines.append(f"- [[{pid}]]: placed on this board but not tied to it → add for: [[{name}]]")
        for pid, ed in b["edits"].items():
            if pid not in data:
                continue
            if ed.get("drop"):
                lines.append(f"- DROP [[{pid}]]: Tom dropped it → status: dropped, log line")
            changes = [f'{k}: "{ed[k]}"' for k in ("kind", "summary") if k in ed]
            if "idea" in ed:
                changes.append("idea (rewrite ## Idea, linking names as [[ ]]):\n      " + ed["idea"].replace("\n", "\n      "))
            if ed.get("note"):
                changes.append(f'note to Claude: "{ed["note"]}"')
            if changes:
                lines.append(f"- EDITED [[{pid}]]: " + "; ".join(changes))
        for pid, d in data.items():
            if b["edits"].get(pid, {}).get("drop"):
                continue
            if name in d["lanes"] and pid not in b["placed"] and re.fullmatch(r"S\d+", d["target"] or "") and int(d["target"][1:]) > cur:
                lines.append(f"- [[{pid}]]: vault targets {d['target']}, but Tom left it in the tray → ask before clearing the target")
        for cid, c in b["cards"].items():
            ins = [e for e in b["edges"] if e["to"] == cid]
            outs = [e for e in b["edges"] if e["from"] == cid]
            lines.append(f'- NEW CARD {cid} ({c["kind"]}, {c["column"]}): "{c["title"] or "untitled"}"' + (f' — {c["body"]}' if c["body"] else ""))
            for e in ins:
                lines.append(f'    from {label(e["from"], b, data)}' + (f' · "{e["label"]}"' if e["label"] else ""))
            for e in outs:
                lines.append(f'    to {label(e["to"], b, data)}' + (f' · "{e["label"]}"' if e["label"] else ""))
        for e in b["edges"]:
            if e["from"] in b["cards"] or e["to"] in b["cards"] or covered(e, data):
                continue
            lines.append(f'- NEW LINK {label(e["from"], b, data)} → {label(e["to"], b, data)}' + (f' · "{e["label"]}"' if e["label"] else ""))
        print(f"\n## {name}")
        print("\n".join(lines) if lines else "nothing new")


def adopt(board, card, plan):
    doc = call("GET")
    cv = doc["lanes"][board]
    nid = None
    for n in cv["nodes"]:
        if n["id"] == card:
            path = f"Plans/{plan}.md"
            if not os.path.exists(os.path.join(build.VAULT, path)):
                sys.exit(f"No plan note {path} in the vault: write it and run build.py first")
            nid = "p:" + plan
            o = n.get("osse") or {}
            keep = {k: o[k] for k in ("session", "lx", "ly", "column") if k in o}
            n.clear(); n.update({"id": nid, "type": "file", "file": path, "x": n.get("x", 0), "y": n.get("y", 0),
                                 "width": 250, "height": 140, "osse": {"plan": plan, **keep}})
    if not nid:
        sys.exit(f"No card {card} on board {board}")
    for e in cv.get("edges", []):
        e["fromNode"] = nid if e["fromNode"] == card else e["fromNode"]
        e["toNode"] = nid if e["toNode"] == card else e["toNode"]
    call("PUT", doc)
    print(f"{card} on {board} is now [[{plan}]]")


def settle(board=None):
    """Clear Tom's edits and drops once the vault holds them (run after build.py)."""
    doc = call("GET")
    data, _ = plan_facts(None)
    cleared = 0
    for name, cv in doc.get("lanes", {}).items():
        if board and board != name:
            continue
        keep = []
        for n in cv.get("nodes", []):
            o = n.get("osse") or {}
            if o.get("edit"):
                cleared += 1
                o.pop("edit")
                if o.get("tray"):
                    continue
            keep.append(n)
        cv["nodes"] = keep
    call("PUT", doc)
    print(f"Cleared {cleared} edit(s) and drop(s); the board now shows the vault's text.")


def tidy():
    doc = call("GET")
    data, _ = plan_facts(None)
    dropped = 0
    for name, cv in doc.get("lanes", {}).items():
        keep = []
        for e in cv.get("edges", []):
            own = (e.get("osse") or {}).get("own")
            if own and covered({"from": e["fromNode"], "to": e["toNode"]}, data):
                dropped += 1; continue
            keep.append(e)
        cv["edges"] = keep
    call("PUT", doc)
    print(f"Dropped {dropped} link(s) the vault now holds.")


def export(folder):
    doc = call("GET")
    os.makedirs(folder, exist_ok=True)
    for name, cv in doc.get("lanes", {}).items():
        path = os.path.join(folder, f"Paths - {name}.canvas")
        json.dump({"nodes": cv.get("nodes", []), "edges": cv.get("edges", [])}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(path)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--mock"]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); sys.exit()
    if a[0] == "show":
        show(a[1] if len(a) > 1 else None)
    elif a[0] == "adopt" and len(a) == 4:
        adopt(a[1], a[2], a[3])
    elif a[0] == "settle":
        settle(a[1] if len(a) > 1 else None)
    elif a[0] == "tidy":
        tidy()
    elif a[0] == "export" and len(a) == 2:
        export(a[1])
    else:
        print(__doc__); sys.exit(1)
