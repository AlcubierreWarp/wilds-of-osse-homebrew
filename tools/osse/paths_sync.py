#!/usr/bin/env python3
"""Reads Tom's Paths ahead boards from the Gus relay so Claude can bring them into the vault, and drafts onto them (the `paths` skill).
The store holds one copy of everything (items, cards, edits, edges); `lanes` are the same boards as JSON Canvas.
  python3 tools/osse/paths_sync.py show [BOARD]        what Tom changed that the vault does not say yet, and each session's running order
  python3 tools/osse/paths_sync.py board [SESSION ...] everything on the boards with its ids: scenes in order, their cards as a tree
  python3 tools/osse/paths_sync.py draft FILE [--write]     check a draft and print its outline; --write puts it on the boards (tools/osse/paths_draft.py has the format)
  python3 tools/osse/paths_sync.py undraft [WHEN] [--write] take a draft back off, keeping what Tom changed since; with no WHEN, the last one
  python3 tools/osse/paths_sync.py notes SCENE [DIR]    the plan notes a scene on the boards and its cards would become; with DIR, written there
  python3 tools/osse/paths_sync.py adopt CARD "Plan name"   swap one of Tom's cards for the plan written from it, on every board
  python3 tools/osse/paths_sync.py tidy                drop Tom's links the vault now says itself, and plans no longer live (run after build.py)
  python3 tools/osse/paths_sync.py settle              clear Tom's edits and drops once the vault holds them (run after build.py)
  python3 tools/osse/paths_sync.py export DIR          write each board as a .canvas file (JSON Canvas 1.0)
  python3 tools/osse/paths_sync.py arcs                the Arc planner: each arc, what it starts and ends on, and its session cards in order
Add --mock to use the local relay stand-in (relay/gus/mock.py, key test-gm).
The game master key is read from the macOS Keychain inside this process and never printed. Writes only to the relay."""
import copy, datetime, json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402
import paths_draft  # noqa: E402

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


def put(doc):
    """Save the boards, unless Tom saved them after they were read."""
    if doc.get("saved_at") and call("GET").get("saved_at") != doc["saved_at"]:
        sys.exit("Tom changed the boards in the meantime: nothing was written. Run this again.")
    call("PUT", doc)


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
        sys.exit("These boards were saved before everything had one copy. Open the Session planner page once (it converts and saves them), then run this again.")
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
        return {**d, **{k: e[k] for k in ("kind", "summary", "options", *paths_draft.EXTRA) if k in e}}

    def is_scene(self, i):
        return self.obj(i).get("kind") == "scene"

    def scene(self, i):
        sc = self.items.get(i, {}).get("scene")
        return sc if sc and self.live(sc) and self.is_scene(sc) and not self.is_scene(i) else None

    def anytime(self, i):
        """In the scene's Any time section: it can come at any point, on its cue."""
        return bool(self.scene(i) and self.items[i].get("any"))

    def floating(self, i):
        """What a floating scene says of its place ('' when its place in the running order is fixed)."""
        o = self.items[i]
        if not o.get("float"):
            return ""
        t = lambda x: x[2:] if x.startswith("p:") else self.cards[x[2:]].get("title") or "untitled"
        lim = [f"{k} " + " and ".join(t(x) for x in o.get(k) or [] if self.live(x)) for k in ("after", "before") if any(self.live(x) and self.session(x) == o["s"] for x in o.get(k) or [])]
        return "floating: " + (", ".join(lim) or "any time in the session")

    def session(self, i):
        return self.items[self.scene(i) or i]["s"]

    def cast(self, i):
        """The boards of the player characters in a scene: there when it opens, or on one of its cards (who it names, else the boards a plan is tied to)."""
        out = []
        on = [n for m in self.items if self.live(m) and self.scene(m) == i for n in self.named(m)]
        for n in (self.obj(i).get("present") or []) + on:
            low = n.strip().lower()
            if low in ("the party", "the whole party"):
                out += [*self.pcs, "The Party"]
            out += [k for k, names in self.pcs.items() if low in names]
        return list(dict.fromkeys(out))

    def named(self, m):
        o = self.obj(m)
        who = o.get("who") if (o.get("kind") or "beat") in paths_draft.IN_SCENE else None
        return who or (self.data[m[2:]]["lanes"] if m.startswith("p:") and m[2:] in self.data else [])

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
        if a in data and self.obj(e["from"]).get("kind") == "decision":   # each link out of a decision is its own option
            return any(o["to"] == b and o["label"].strip().lower() == (e.get("label") or "").strip().lower() for o in data[a]["options"])
        if a in data and self.obj(e["from"]).get("kind") == "exit":
            return b in data[a]["leads"]
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
            if sc and b.anytime(i) != d["anytime"]:
                say(i, f"- [[{pid}]]: " + ("in its scene's Any time section → set anytime: true" if b.anytime(i) else "no longer in the Any time section → remove anytime"))
            if not sc:
                for k in b.items[i].get("homes", []):
                    if k not in d["lanes"] and k != "world" and not (b.is_scene(i) and k in b.cast(i)):
                        say(i, f"- [[{pid}]]: placed on {k}'s board but not tied to it → add for: [[{k}]]")
        else:
            lines = [f'- NEW CARD {i} ({o.get("kind")}, {sess}): "{o.get("title") or "untitled"}"' + {"new": " (drafted by Claude, not changed by Tom since)", "edit": " (Tom's card, last tidied by Claude)"}.get(o.get("draft"), "") + (f': {o["text"]}' if o.get("text") else "")]
            if b.is_scene(i) and len(ks) > 1:
                lines.append(f'    on the boards of: {", ".join(ks)}')
            elif not sc and len(ks) > 1:
                lines.append(f'    on {", ".join(ks)}')
            for f in paths_draft.EXTRA:
                if paths_draft.has(o, f):
                    lines.append(f'    {f}: {", ".join(o[f]) if isinstance(o[f], list) else o[f]}')
            for x in o.get("options") or []:
                lines.append(f'    option · "{x.get("label") or "(not named)"}"' + (f': {x["text"]}' if x.get("text") else "") + " (only listed, no card)")
            if sc:
                lines.append(f"    in the scene {b.label(sc)}" + (", any time" if b.anytime(i) else ""))
            for e in b.edges:
                choice = " option" if not e["from"].startswith("start") and b.obj(e["from"]).get("kind") == "decision" else ""
                if e["to"] == i:
                    lines.append(f'    from {b.label(e["from"])}{choice}' + (f' · "{e["label"]}"' if e.get("label") else " · (not named)" if choice else ""))
                if e["from"] == i:
                    lines.append(f'   {" leads to" if o.get("kind") == "exit" else choice + " to"} {b.label(e["to"])}' + (f' · "{e["label"]}"' if e.get("label") else " · (not named)" if choice else ""))
            say(i, "\n".join(lines))
    for pid, d in data.items():
        ed, i = b.edits.get(pid, {}), "p:" + pid
        home = b.lanes(i)[0] if b.live(i) else (d["lanes"] or ["world"])[0]
        put = out.setdefault(home, [])
        if ed.get("drop"):
            put.append((i, f"- DROP [[{pid}]]: Tom dropped it → status: dropped, log line"))
            continue
        changes = [f'{k}: "{ed[k]}"' for k in ("kind", "summary", *(f for f in paths_draft.EXTRA if f not in ("present", "who"))) if k in ed]
        changes += [f"{k}: " + (", ".join(ed[k]) or "(nobody)") for k in ("present", "who") if k in ed]
        if "options" in ed:
            changes.append("options (rewrite ## Options with the whole list):" + "".join(f'\n      - ' + (f'[[{x["to"]}]] · {x.get("label") or "(not named)"}' if x.get("to") else f'{x.get("label") or "(not named)"} · {x.get("text") or "(outcome not written)"}') for x in ed["options"]))
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
            print("\n## " + {"The Party": "Session canvas only (the whole party)", "world": "World"}.get(k, k))
            print("\n".join(t for i, t in rows if not only or only == k or (b.live(i) and only in b.lanes(i))))
    if not any(out.values()):
        print("nothing new")
    order = doc.get("order") or {}
    if order and not only:
        print("\n## Running order (for the session screen, nothing to write in the vault)")
        for sess in sorted(order, key=lambda t: int(t[1:]) if t[1:].isdigit() else 1e9):
            print(f"{sess}:")
            n = 0
            for i in (x for x in order[sess] if b.live(x)):
                n += not b.floating(i)
                print(f"  {'~' if b.floating(i) else f'{n}.'} {b.label(i)} ({', '.join(b.lanes(i))})" + (f" [{b.floating(i)}]" if b.floating(i) else ""))


def known(b):
    """The names a draft may use: boards, places and people."""
    g, _ = graph()
    boards = [*b.pcs, "The Party", "world"]
    alias = {a: k for k, names in b.pcs.items() for a in names}
    alias.update({k.split()[0].lower(): k for k in b.pcs}, **{"the party": "The Party", "party": "The Party", "world": "world", "around the party": "world", "canvas": "The Party", "session canvas": "The Party"})
    names = lambda ok: {x.lower() for n in g["nodes"] if ok(n["type"]) for x in [n["id"], *(n.get("aliases") or [])]}
    return {"boards": boards, "alias": alias, "places": names(lambda t: t == "place"),
            "secrets": names(lambda t: t == "secret"), "people": names(lambda t: t in ("npc", "pc", "party", "faction")) | {"the party", "the whole party"}}


def board(sessions):
    doc = store()
    data, cur = plan_facts(None)
    print(f"Boards saved {doc.get('saved_at', '?')} (ms), vault after S{cur}. [c:…] is one of Tom's cards, [plan] a vault plan, [e…] a link.")
    print(paths_draft.outline(doc, Board(doc, data, cur), sessions or None))


def draft(path, write):
    spec = json.load(open(path, encoding="utf-8"))
    doc = store()
    before = copy.deepcopy(doc)
    data, cur = plan_facts(None)
    b = Board(doc, data, cur)
    bad, warn, ids = paths_draft.apply(spec, doc, b, known(b))
    for w in dict.fromkeys(warn):
        print("note:", w)
    if bad:
        sys.exit("\n".join(["Nothing written. Fix:", *(f"- {x}" for x in dict.fromkeys(bad))]))
    b = Board(doc, data, cur)
    was = before["items"]
    mark = lambda i: "NEW " if i not in was else "CHANGED " if doc["cards"].get(i[2:]) != before.get("cards", {}).get(i[2:]) or doc["edits"].get(i[2:]) != before.get("edits", {}).get(i[2:]) \
        else "MOVED " if (doc["items"][i].get("scene"), doc["items"][i]["s"]) != (was[i].get("scene"), was[i]["s"]) else ""
    where = [s for s in doc["sessions"] if any(b.session(i) == s for i in doc["items"] if b.live(i) and (mark(i) or b.session(i) != before["items"][i]["s"]))]
    if not write:
        spec["base"] = doc.get("saved_at")
        json.dump(spec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(paths_draft.outline(doc, b, where or None, mark, withids=False))
        print("\nNot written. Show Tom this outline; when he agrees, run it again with --write.")
        return
    if "base" not in spec:
        sys.exit("Preview it first (run without --write) and show Tom the outline.")
    if spec["base"] != doc.get("saved_at"):
        sys.exit("Tom changed the boards after the preview: nothing was written. Preview again, check it still fits, then write.")
    put(doc)
    when = paths_draft.record(MOCK, before, doc)
    new = [i for i in doc["items"] if i not in was]
    print(f"On the boards: {len(new)} new, in {', '.join(where) or 'no session'}. Undo with: undraft {when}")
    for k, i in ids.items():
        print(f"  {k} = {i}")


def undraft(when, write):
    d = paths_draft.folder(MOCK)
    have = sorted(x[:-5] for x in os.listdir(d) if x.endswith(".json"))
    if not have or (when and when not in have):
        sys.exit("Drafts kept: " + (", ".join(have) or "none"))
    when = when or have[-1]
    rec = json.load(open(os.path.join(d, when + ".json"), encoding="utf-8"))
    doc = store()
    was = copy.deepcopy(doc)
    merged = paths_draft.merge3(paths_draft.parts(rec["after"]), paths_draft.parts(doc), paths_draft.parts(rec["before"]))
    paths_draft.put_parts(doc, merged)
    paths_draft.prune(doc, was)
    gone = [x for x in was["cards"] if x not in doc["cards"]]
    kept = [x for x in rec["after"]["cards"] if x not in rec["before"]["cards"] and x in doc["cards"]]
    t = lambda x: was["cards"][x].get("title") or "untitled"
    print(f"Draft {when}: takes off {len(gone)} card(s): {', '.join(map(t, gone)) or 'none'}.")
    if kept:
        print(f"Keeps, because Tom changed them: {', '.join(map(t, kept))}.")
    if not write:
        print("Not written. Run it again with --write to do it.")
        return
    put(doc)
    os.rename(os.path.join(d, when + ".json"), os.path.join(d, when + ".undone"))
    print("Done.")


def notes(which, out=None):
    """A scene on the boards as plan notes: the scene, then each card in it. A first draft for Claude to tighten; it never writes to the vault."""
    doc = store()
    data, cur = plan_facts(None)
    b = Board(doc, data, cur)
    g, nodes = graph()
    title = lambda i: i[2:] if i.startswith("p:") else b.cards[i[2:]].get("title") or "Untitled"
    sid = next((i for i in b.items if b.live(i) and b.is_scene(i) and (which in (i, i[2:]) or title(i).lower() == which.lower())), None)
    if not sid:
        sys.exit(f"No scene '{which}' on the boards.")
    byname = {}
    for n in g["nodes"]:
        for x in [n["id"], *(n.get("aliases") or [])]:
            byname.setdefault(str(x).lower(), n["id"])
    for n in g["nodes"]:
        byname[n["id"].lower()] = n["id"]
    link = lambda x: f"[[{byname[x.strip().lower()]}]]" if x.strip().lower() in byname else x.strip()
    safe = lambda t: re.sub(r"\s+", " ", re.sub(r'[\[\]#^|\\/:*?"<>]', "", t)).strip()
    plan = lambda i: f"[[{safe(title(i))}]]"
    q = lambda v: '"' + str(v).replace('"', "'").replace("\n", " ") + '"'
    members = [m for m in b.items if b.live(m) and b.scene(m) == sid]
    members.sort(key=lambda m: (not b.anytime(m), b.items[m].get("any", 0) if b.anytime(m) else b.items[m].get("ry", 0), b.items[m].get("rx", 0)))
    today, made = datetime.date.today().isoformat(), []
    for i in [sid, *members]:
        if i.startswith("p:"):
            print(f"(already a plan: [[{i[2:]}]]" + (f'; set scene: "{plan(sid)}"' if i != sid and data[i[2:]]["scene"] != title(sid) else "") + ")")
            continue
        o, kind = b.obj(i), b.obj(i).get("kind") or "beat"
        text = (o.get("text") or "").strip()
        kind = "beat" if kind == "note" else kind
        first = re.split(r"(?<=[.!?])\s", text.split("\n")[0])[0] if text else title(i)
        fm = ["type: plan", "stage: draft", "status: draft", f"kind: {kind}", f"summary: {q(first)}"]
        outs = [e for e in b.edges if e["from"] == i and b.live(e["to"])]
        if i != sid:
            fm.append(f'scene: "{plan(sid)}"')
        for f in paths_draft.EXTRA:
            if not paths_draft.has(o, f):
                continue
            v = o[f]
            fm.append(f"{f}: " + ("[" + ", ".join(q(link(x)) for x in v) + "]" if isinstance(v, list) else "true" if v is True else q(link(v)) if f in ("where", "reveals") else v if f == "clock" else q(v)))
        if b.anytime(i):
            fm.append("anytime: true")
        if kind == "exit" and outs:
            fm.append("leads_to: [" + ", ".join(dict.fromkeys(q(plan(e["to"])) for e in outs)) + "]")
        s = b.session(i)
        fm += ([f"target: {s}"] if s != "Later" else []) + [f"updated: {today}"]
        body = ["## Idea", *(f"- {ln.strip()}" for ln in (text or title(i)).split("\n") if ln.strip())]
        if kind == "decision":
            body += ["", "## Options", *(f"- {plan(e['to'])} · {e.get('label') or '(not named)'}" for e in outs), *(f"- {x.get('label') or '(not named)'} · {x.get('text') or '(outcome not written)'}" for x in o.get("options") or [])]
        ins = [e for e in b.edges if e["to"] == i and not e["from"].startswith("start") and b.live(e["from"])]
        need = [e for e in ins if b.obj(e["from"]).get("kind") not in ("decision", "exit")]
        reqs = []
        if len(need) == 1 and len(ins) == 1:   # one way in: it needs that plan. Several ways in: none of them is needed
            reqs.append(f"- plan: {plan(need[0]['from'])}")
        reqs += [f"- check: {e['label']}" for e in need if e.get("label") and e["label"].lower() != "then"] if len(ins) == 1 and not o.get("cue") else []   # a cue already says it
        if reqs:
            body += ["", "## Requires", *reqs]
        body += ["", "## Log", f"- S{cur}: from the Session planner."]
        made.append((safe(title(i)), "---\n" + "\n".join(fm) + "\n---\n\n" + "\n".join(body) + "\n"))
    names = [t for t, _ in made]
    for t in names:
        if t in nodes:
            print(f"NAME TAKEN: the vault already has a note called '{t}': retitle the card first.")
        if names.count(t) > 1:
            print(f"NAME TWICE: two cards are called '{t}': retitle one.")
    known_plans = set(names) | {n["id"] for n in g["nodes"]}
    for t, s in made:
        for x in build.LINK.findall(s):
            if x not in known_plans:
                print(f"OUTSIDE THE SCENE: '{t}' points to [[{x}]], which is not a plan yet: bring its scene in too.")
        if out:
            os.makedirs(out, exist_ok=True)
            open(os.path.join(out, t + ".md"), "w", encoding="utf-8").write(s)
        else:
            print(f"\n===== Plans/{t}.md\n{s}")
    if out:
        print(f"Wrote {len(made)} note(s) to {out}. Not in the vault yet.")


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
    put(doc)
    print(f"{card} is now [[{plan}]] on every board")


def settle():
    """Clear Tom's edits and drops once the vault holds them (run after build.py)."""
    doc = store()
    n, doc["edits"] = len(doc.get("edits", {})), {}
    for cv in doc["lanes"].values():
        for node in cv.get("nodes", []):
            (node.get("osse") or {}).pop("edit", None)
    put(doc)
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
    put(doc)
    print(f"Dropped {n} link(s) the vault now holds, and {len(gone)} plan(s) no longer live.")


def export(folder):
    doc = store()
    os.makedirs(folder, exist_ok=True)
    for name, cv in doc.get("lanes", {}).items():
        path = os.path.join(folder, f"Paths - {name}.canvas")
        json.dump({"nodes": cv.get("nodes", []), "edges": cv.get("edges", [])}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(path)


def arcs():
    """The Arc planner's part of the store (vault/arcs.html), read only. A linked card is that session's name in the Session planner;
    unlinked ones count on, around the sessions no card has (the same rule as LINK in arcs.py)."""
    doc = call("GET"); A = doc.get("arcs")
    if not A or not A.get("order"):
        print("No arcs saved yet. Opening the Arc planner once saves the first outline."); return
    st = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "vault", "status.json"), encoding="utf-8"))
    cur, titles = st["current"], st.get("titles", {})
    num = lambda t: int((re.fullmatch(r"S(\d+)", t or "") or [0, 0])[1])
    linked = {c.get("link") for c in A["cards"].values()}
    alone = {num(t) for t in doc.get("sessions", []) if num(t) > cur and t not in linked}
    prev = cur
    for i, aid in enumerate(A["order"], 1):
        a = A["list"].get(aid, {})
        print(f"Arc {i}: {a.get('title') or 'Untitled arc'}" + ("  (Claude's draft)" if a.get("by") == "claude" else ""))
        print(f"  starts: {a.get('starts', '')}\n  ends:   {a.get('ends', '')}")
        if a.get("about"):
            print(f"  about:  {a['about']}")
        for cid in a.get("cards", []):
            c = A["cards"].get(cid)
            if not c:
                continue
            m = n = num(c.get("link"))
            if not n or n > cur:
                prev += 1
                while prev in alone:
                    prev += 1
                n = n or prev
            tag = ("played" if n <= cur else "planned") if m else "idea"
            print(f"  - S{n} {tag}: {c.get('title') or titles.get(str(n), 'Untitled session')}" + (f": {c['text']}" if c.get("text") else ""))
        print()
    if alone:
        print("In the Session planner, not in an arc: " + ", ".join(f"S{n}" for n in sorted(alone)))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x not in ("--mock", "--write")]
    WRITE = "--write" in sys.argv
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); sys.exit()
    if a[0] == "show":
        show(a[1] if len(a) > 1 else None)
    elif a[0] == "board":
        board([x.upper() if x.lower() != "later" else "Later" for x in a[1:]])
    elif a[0] == "draft" and len(a) == 2:
        draft(a[1], WRITE)
    elif a[0] == "undraft" and len(a) <= 2:
        undraft(a[1] if len(a) > 1 else None, WRITE)
    elif a[0] == "notes" and len(a) in (2, 3):
        notes(a[1], a[2] if len(a) == 3 else None)
    elif a[0] == "adopt" and len(a) == 3:
        adopt(a[1], a[2])
    elif a[0] == "settle":
        settle()
    elif a[0] == "tidy":
        tidy()
    elif a[0] == "export" and len(a) == 2:
        export(a[1])
    elif a[0] == "arcs":
        arcs()
    else:
        print(__doc__); sys.exit(1)
