#!/usr/bin/env python3
"""Reads Tom's Paths ahead boards from the Gus relay so Claude can bring them into the vault (the `paths` skill).
The store holds one copy of everything (items, cards, edits, edges); `lanes` are the same boards as JSON Canvas.
  python3 tools/osse/paths_sync.py show [BOARD]        what Tom changed that the vault does not say yet, and each session's running order
  python3 tools/osse/paths_sync.py adopt CARD "Plan name"   swap one of Tom's cards for the plan written from it, on every board
  python3 tools/osse/paths_sync.py tidy                drop Tom's links the vault now says itself, and plans no longer live (run after build.py)
  python3 tools/osse/paths_sync.py settle              clear Tom's edits and drops once the vault holds them (run after build.py)
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


def store():
    doc = call("GET")
    if "items" not in doc:
        if not doc.get("lanes"):
            print("No boards saved yet."); sys.exit()
        sys.exit("These boards were saved before everything had one copy. Open the Paths ahead page once (it converts and saves them), then run this again.")
    return doc


class Board:
    """The stored boards, with the same rules as the page (tools/osse/paths.py)."""
    def __init__(self, doc, data, cur):
        self.doc, self.data, self.cur = doc, data, cur
        self.items, self.cards, self.edits, self.edges = doc["items"], doc.get("cards", {}), doc.get("edits", {}), doc.get("edges", [])
        g, nodes = graph()
        self.pcs = {n["id"]: [n["id"].lower()] + [str(a).lower() for a in (n.get("aliases") or [])] for n in g["nodes"] if n["type"] == "pc"}

    def live(self, i):
        return i in self.items and (i[2:] in self.data if i.startswith("p:") else i[2:] in self.cards)

    def obj(self, i):
        if i.startswith("c:"):
            return self.cards.get(i[2:], {})
        d, e = self.data.get(i[2:], {}), self.edits.get(i[2:], {})
        return {**d, **{k: e[k] for k in ("kind", "present", "where", "clock", "summary") if k in e}}

    def is_scene(self, i):
        return self.obj(i).get("kind") == "scene"

    def scene(self, i):
        sc = self.items.get(i, {}).get("scene")
        return sc if sc and self.live(sc) and self.is_scene(sc) and not self.is_scene(i) else None

    def session(self, i):
        return self.items[self.scene(i) or i]["s"]

    def cast(self, i):
        out = []
        for n in self.obj(i).get("present") or []:
            low = n.strip().lower()
            if low in ("the party", "the whole party"):
                out += [*self.pcs, "The Party"]
            out += [k for k, names in self.pcs.items() if low in names]
        return list(dict.fromkeys(out))

    def lanes(self, i):
        sc = self.scene(i)
        if sc:
            return self.lanes(sc)
        o = self.items[i]
        ks = list(dict.fromkeys(o.get("homes", []) + (self.cast(i) if self.is_scene(i) else [])))
        return ks or [o.get("born", "")]

    def label(self, i):
        if i.startswith("start"):
            return f"the start of {i[6:]}" if i.startswith("start:") else "Now"
        if i.startswith("p:"):
            return f"plan [[{i[2:]}]]"
        return f'card {i} "{self.cards.get(i[2:], {}).get("title") or "untitled"}"'

    def covered(self, e):
        """True when the vault already says what this link says."""
        if not (e["from"].startswith("p:") and e["to"].startswith("p:")):
            return False
        a, b, data = e["from"][2:], e["to"][2:], self.data
        if b in data and any(r["k"] in ("plan", "played") and r["a"] == a for r in data[b]["req"]):
            return True
        return a in data and any(o["to"] == b for o in data[a]["options"])


def show(only=None):
    doc = store()
    data, cur = plan_facts(None)
    b = Board(doc, data, cur)
    print(f"Boards saved {doc.get('saved_at', '?')} (ms), vault after S{cur}. Each plan, card and link is listed once.")
    out = {}

    def say(i, text):
        out.setdefault(b.lanes(i)[0], []).append((i, text))

    for i in [x for x in b.items if b.live(x) and b.is_scene(x)] + [x for x in b.items if b.live(x) and not b.is_scene(x)]:
        ks, sess, sc, o = b.lanes(i), b.session(i), b.scene(i), b.obj(i)
        if i.startswith("p:"):
            pid, d = i[2:], data[i[2:]]
            want = "" if sess == "Later" else sess
            if want != d["target"].upper():
                say(i, f"- [[{pid}]]: placed in {sess}; vault target is {d['target'] or 'empty'} → set target: {want or '(empty)'}")
            if sc and sc.startswith("p:") and d["scene"] != sc[2:]:
                say(i, f"- [[{pid}]]: placed in the scene [[{sc[2:]}]] → set scene: [[{sc[2:]}]]")
            elif sc and sc.startswith("c:"):
                say(i, f"- [[{pid}]]: placed in Tom's new scene {b.label(sc)} → set scene: once that card is a plan")
            elif not sc and d["scene"]:
                say(i, f"- [[{pid}]]: the vault sets it in the scene [[{d['scene']}]], but Tom placed it outside → ask before clearing scene")
            if not sc:
                for k in b.items[i].get("homes", []):
                    if k not in d["lanes"] and k != "world" and not (b.is_scene(i) and k in b.cast(i)):
                        say(i, f"- [[{pid}]]: placed on {k}'s board but not tied to it → add for: [[{k}]]")
        else:
            lines = [f'- NEW CARD {i} ({o.get("kind")}, {sess}): "{o.get("title") or "untitled"}"' + (f': {o["text"]}' if o.get("text") else "")]
            if b.is_scene(i) and len(ks) > 1:
                lines.append(f'    on the boards of: {", ".join(ks)}')
            elif not sc and len(ks) > 1:
                lines.append(f'    on {", ".join(ks)}')
            if o.get("where"):
                lines.append(f'    where: {o["where"]}')
            if o.get("present"):
                lines.append(f'    present: {", ".join(o["present"])}')
            if o.get("clock"):
                lines.append(f'    clock: {o["clock"]}')
            if sc:
                lines.append(f"    in the scene {b.label(sc)}")
            for e in b.edges:
                if e["to"] == i:
                    lines.append(f'    from {b.label(e["from"])}' + (f' · "{e["label"]}"' if e.get("label") else ""))
                if e["from"] == i:
                    lines.append(f'    to {b.label(e["to"])}' + (f' · "{e["label"]}"' if e.get("label") else ""))
            say(i, "\n".join(lines))
    for pid, d in data.items():
        ed, i = b.edits.get(pid, {}), "p:" + pid
        home = b.lanes(i)[0] if b.live(i) else (d["lanes"] or ["world"])[0]
        put = out.setdefault(home, [])
        if ed.get("drop"):
            put.append((i, f"- DROP [[{pid}]]: Tom dropped it → status: dropped, log line"))
            continue
        changes = [f'{k}: "{ed[k]}"' for k in ("kind", "summary", "where", "clock") if k in ed]
        if "present" in ed:
            changes.append("present: " + ", ".join(ed["present"]) if ed["present"] else "present: (nobody)")
        if "idea" in ed:
            changes.append("idea (rewrite ## Idea, linking names as [[ ]]):\n      " + ed["idea"].replace("\n", "\n      "))
        if ed.get("note"):
            changes.append(f'note to Claude: "{ed["note"]}"')
        if changes:
            put.append((i, f"- EDITED [[{pid}]]: " + "; ".join(changes)))
        if i not in b.items and re.fullmatch(r"S\d+", d["target"] or "") and int(d["target"][1:]) > cur:
            put.append((i, f"- [[{pid}]]: vault targets {d['target']}, but Tom left it in the tray → ask before clearing the target"))
    for e in b.edges:
        if not (b.live(e["to"]) and (e["from"].startswith("start") or b.live(e["from"]))):
            continue
        if e["from"].startswith("c:") or e["to"].startswith("c:") or b.covered(e):
            continue
        say(e["to"], f'- NEW LINK {b.label(e["from"])} → {b.label(e["to"])}' + (f' · "{e["label"]}"' if e.get("label") else ""))
    for k, rows in out.items():
        if rows and (not only or only == k or any(b.live(i) and only in b.lanes(i) for i, _ in rows)):
            print(f"\n## {k}")
            print("\n".join(t for i, t in rows if not only or only == k or (b.live(i) and only in b.lanes(i))))
    if not any(out.values()):
        print("nothing new")
    order = doc.get("order") or {}
    if order and not only:
        print("\n## Running order (Session plan; for the session screen, nothing to write in the vault)")
        for sess in sorted(order, key=lambda t: int(t[1:]) if t[1:].isdigit() else 1e9):
            print(f"{sess}:")
            for n, i in enumerate([x for x in order[sess] if b.live(x)], 1):
                print(f"  {n}. {b.label(i)} ({', '.join(b.lanes(i))})")


def adopt(card, plan):
    doc = store()
    card = card if card.startswith("c:") else "c:" + card
    path, nid = f"Plans/{plan}.md", "p:" + plan
    if not os.path.exists(os.path.join(build.VAULT, path)):
        sys.exit(f"No plan note {path} in the vault: write it and run build.py first")
    if card not in doc["items"]:
        sys.exit(f"No card {card} on the boards")
    if nid in doc["items"]:
        sys.exit(f"[[{plan}]] is already on the boards")
    swap = lambda x: nid if x == card else x
    doc["items"] = {swap(i): o for i, o in doc["items"].items()}
    for o in doc["items"].values():
        if o.get("scene") == card:
            o["scene"] = nid
    doc["cards"].pop(card[2:], None)
    for e in doc["edges"]:
        e["from"], e["to"] = swap(e["from"]), swap(e["to"])
    doc["order"] = {s: [swap(i) for i in ids] for s, ids in (doc.get("order") or {}).items()}
    for cv in doc["lanes"].values():   # the JSON Canvas copies, until the page next saves
        for n in cv.get("nodes", []):
            o = n.get("osse") or {}
            if n["id"] == card:
                keep = {k: o[k] for k in ("session", "lx", "ly", "w", "h", "scene") if k in o}
                geo = {k: n[k] for k in ("x", "y", "width", "height")}
                n.clear(); n.update({"id": nid, "type": "file", "file": path, **geo, "osse": {"plan": plan, **keep}})
            if (n.get("osse") or {}).get("scene") == card:
                n["osse"]["scene"] = nid
        for e in cv.get("edges", []):
            e["fromNode"], e["toNode"] = swap(e["fromNode"]), swap(e["toNode"])
            if (e.get("osse") or {}).get("from"):
                e["osse"]["from"] = swap(e["osse"]["from"])
    call("PUT", doc)
    print(f"{card} is now [[{plan}]] on every board")


def settle():
    """Clear Tom's edits and drops once the vault holds them (run after build.py)."""
    doc = store()
    n, doc["edits"] = len(doc.get("edits", {})), {}
    for cv in doc["lanes"].values():
        for node in cv.get("nodes", []):
            (node.get("osse") or {}).pop("edit", None)
    call("PUT", doc)
    print(f"Cleared {n} edit(s) and drop(s); the boards now show the vault's text.")


def tidy():
    doc = store()
    data, cur = plan_facts(None)
    b = Board(doc, data, cur)
    gone = [i for i in doc["items"] if i.startswith("p:") and i[2:] not in data]
    for i, o in doc["items"].items():   # what a gone scene held goes back to its own boards
        so = doc["items"].get(o.get("scene"))
        if o.get("scene") in gone and i not in gone:
            o["at"] = {k: {"x": a["x"] + o.get("rx", 0), "y": a["y"] + o.get("ry", 0)} for k, a in (so.get("at") or {}).items() if k in o.get("homes", [])}
            o["s"] = so["s"]
            for k in ("scene", "rx", "ry"):
                o.pop(k, None)
    for i in gone:
        doc["items"].pop(i)
    keep = [e for e in doc["edges"] if not b.covered(e) and e["from"] not in gone and e["to"] not in gone]
    n = len(doc["edges"]) - len(keep)
    doc["edges"] = keep
    ids = {e["id"] for e in keep}
    for cv in doc["lanes"].values():
        cv["nodes"] = [x for x in cv.get("nodes", []) if x["id"] not in gone]
        cv["edges"] = [e for e in cv.get("edges", []) if e["id"] in ids]
    call("PUT", doc)
    print(f"Dropped {n} link(s) the vault now holds, and {len(gone)} plan(s) no longer live.")


def export(folder):
    doc = store()
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
    elif a[0] == "adopt" and len(a) == 3:
        adopt(a[1], a[2])
    elif a[0] == "settle":
        settle()
    elif a[0] == "tidy":
        tidy()
    elif a[0] == "export" and len(a) == 2:
        export(a[1])
    else:
        print(__doc__); sys.exit(1)
