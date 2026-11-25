"""Draft scenes, decisions, beats and links onto Tom's Paths ahead boards from a session (the `paths` skill).
Run through paths_sync.py: `board`, `draft` and `undraft`. Nothing here writes to the vault's notes.

A draft is a JSON file. Every part is optional:
{"session": "S14",                       the session new cards go to, unless a card names its own
 "cards": [
   {"key": "gala", "kind": "scene", "title": "The gala", "text": "the situation", "where": "Aerrowyn Manor", "when": "that night",
    "present": ["GUS", "The Party"], "purpose": "force a choice",
    "cards": [{"key": "ask", "kind": "decision", "title": "...", "text": "...", "cue": "what triggers it", "critical": true}, "p:An existing plan",
              {"kind": "reveal", "title": "...", "cue": "...", "reveals": "A secret"}, {"kind": "entrance", "title": "...", "cue": "...", "who": ["Vigil"]},
              {"key": "out", "kind": "exit", "title": "...", "cue": "..."},                     an exit's links out are where it leads
              {"kind": "beat", "title": "...", "cue": "...", "anytime": true}]},                in the scene's Any time section: it follows no other card
   {"kind": "scene", "title": "...", "float": true, "after": ["gala"], "before": []},         no fixed place in the running order, within those limits
   {"kind": "decision", "title": "...", "options": [{"label": "the choice", "text": "the outcome"}]},   options with no card; a link out is an option with one
   {"key": "rumour", "kind": "pressure", "title": "...", "board": "Belaskro Tich"},        outside any scene: say which board
   {"key": "b2", "kind": "beat", "title": "...", "in": "c:9qyi0ije"}],                     into a scene already on the boards
 "place": [{"plan": "A plan", "in": "gala"}, {"plan": "Another", "session": "S15", "board": "GUS"}],
 "links": [["ask", "tells", "tells the truth"], ["c:9qyi0ije", "p:A plan"]],               from a decision: the label is the choice
 "edit":  [{"id": "c:abc", "title": "...", "text": "..."}, {"id": "p:A plan", "summary": "..."}],
 "relabel": [["e999yrti", "a clearer choice"]], "unlink": ["eqe5643p"], "remove": ["c:abc"],
 "order": ["gala", "c:9qyi0ije"],                                                          running order of that session's scenes
 "layout": ["c:9qyi0ije"]}                                                                 lay these scenes' cards out again on the canvas
Cards are named by key, c:id (Tom's card) or p:Plan name (a vault plan). Ids come from `board`."""
import copy, json, os, random, re, string, tempfile, time

KINDS = ("scene", "beat", "reveal", "complication", "decision", "entrance", "exit", "clock", "pressure", "bottleneck", "note")
IN_SCENE = ("beat", "reveal", "complication", "decision", "entrance", "exit")
FOR = {"where": ("scene",), "when": ("scene",), "present": ("scene",), "purpose": ("scene",), "cue": IN_SCENE, "who": ("entrance", "exit"),
       "reveals": ("reveal",), "critical": ("decision",), "clock": ("clock",)}   # the kinds each extra field belongs on
EXTRA = tuple(FOR)
PLACE = ("anytime", "float", "after", "before")   # where it stands: in its scene's Any time section; a scene with no fixed place, and the scenes it must come after or before
CARD_FIELDS = ("kind", "title", "text", "options", *EXTRA)
PLAN_FIELDS = ("kind", "summary", "idea", "options", *EXTRA, "note")
has = lambda o, f: (o.get("kind") or "beat") in FOR[f] and o.get(f) not in (None, "", [], False)
PARTS = ("items", "cards", "edits", "edges", "order", "sessions")
PART_KEYS = {"session", "cards", "place", "links", "edit", "relabel", "unlink", "remove", "order", "layout", "base"}
SCW, SCH = 572, 396


def is_map(x):
    return isinstance(x, dict)


def merge3(base, mine, theirs):
    """Three-way merge, record by record; where both changed the same thing, mine wins. None means absent."""
    if mine == base:
        return theirs
    if theirs == base or mine == theirs:
        return mine
    if is_map(mine) and is_map(theirs):
        b, out = base if is_map(base) else {}, {}
        for k in [*mine, *[k for k in theirs if k not in mine]]:
            v = merge3(b.get(k), mine.get(k), theirs.get(k))
            if v is not None:
                out[k] = v
        return out
    return mine


def parts(doc):
    d = {k: copy.deepcopy(doc.get(k) or ([] if k in ("edges", "sessions") else {})) for k in PARTS}
    d["edges"] = {e["id"]: e for e in d["edges"]}
    return d


def put_parts(doc, d):
    for k in PARTS:
        doc[k] = list(d[k].values()) if k == "edges" else d[k]


def prune(doc, was):
    """After an undo: nothing left half there."""
    for cid in list(doc["cards"]):
        if "c:" + cid not in doc["items"]:
            if "c:" + cid in was["items"]:   # Tom changed this card since: it stays, where it stood
                doc["items"]["c:" + cid] = was["items"]["c:" + cid]
    for i in [i for i in doc["items"] if i.startswith("c:") and i[2:] not in doc["cards"]]:
        doc["items"].pop(i)
    for i, o in doc["items"].items():
        if o.get("scene") and o["scene"] not in doc["items"]:
            o["homes"] = o.get("homes") or [o.get("born") or "The Party"]
            for k in ("scene", "rx", "ry", "lay", "any"):
                o.pop(k, None)
            o["at"] = {}
        if not o.get("scene"):
            for k in ("rx", "ry", "lay"):
                o.pop(k, None)
    doc["edges"] = [e for e in doc["edges"] if e["to"] in doc["items"] and (e["from"].startswith("start") or e["from"] in doc["items"])]
    doc["order"] = {s: [i for i in ids if i in doc["items"]] for s, ids in doc["order"].items()}


def folder(mock):
    import build
    d = os.path.join(tempfile.gettempdir(), "osse-paths-drafts-mock") if mock else os.path.join(build.VAULT, ".osse", "paths-drafts")
    os.makedirs(d, exist_ok=True)
    return d


def nid():
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))


def apply(spec, doc, b, known):
    """Work the draft into doc. Returns (problems, warnings, ids by key)."""
    bad, warn, ids, boards, later = [], [], {}, known["boards"], []
    doc.setdefault("cards", {}), doc.setdefault("edits", {}), doc.setdefault("edges", []), doc.setdefault("order", {})
    b.cards, b.edits, b.edges = doc["cards"], doc["edits"], doc["edges"]
    for k in spec:
        if k not in PART_KEYS:
            bad.append(f"unknown part '{k}'")

    def walk(x, where="draft"):
        if isinstance(x, str) and chr(8212) in x:
            bad.append(f"em dash in {where}: {x[:60]}")
        for k, v in x.items() if is_map(x) else enumerate(x) if isinstance(x, list) else []:
            walk(v, f"{where}.{k}")
    walk(spec)

    def sess(s):
        s = str(s or spec.get("session") or f"S{b.cur + 1}")
        s = "Later" if s.lower() == "later" else s.upper()
        if s != "Later" and (not re.fullmatch(r"S\d+", s) or int(s[1:]) <= b.cur):
            bad.append(f"session {s} is not a coming session")
        elif s not in doc["sessions"]:
            doc["sessions"] = sorted(set(doc["sessions"]) | {s}, key=lambda t: int(t[1:]) if t[1:].isdigit() else 1e9)
        return s

    def board(x, what):
        x = known["alias"].get(str(x or "").lower())
        if not x:
            bad.append(f"{what}: say which board (one of {', '.join(boards)})")
        return x or boards[0]

    def ref(x, what, want_live=True):
        i = ids.get(x) or (x if str(x).startswith(("c:", "p:")) else "p:" + str(x) if x in b.data else None)
        if not i or (want_live and not b.live(i)):
            bad.append(f"{what}: '{x}' is not a key in this draft or a card on the boards" + (" (that plan is not placed: add it under place)" if i and i[2:] in b.data else ""))
            return None
        return i

    def check(c, what):
        if c.get("kind", "beat") not in KINDS:
            bad.append(f"{what}: kind '{c.get('kind')}' is not one of {', '.join(KINDS)}")
        if c.get("clock") and not re.fullmatch(r"\d+/\d+", str(c["clock"])):
            bad.append(f"{what}: clock must read filled/segments, like 0/6")
        for f in ("present", "who"):
            if f in c and not isinstance(c[f], list):
                bad.append(f"{what}: {f} must be a list")
            else:
                warn.extend(f"{what}: {n} is not in the vault (kept as plain text)" for n in c.get(f) or [] if n.lower() not in known["people"])
        for f in EXTRA:
            if c.get(f) and (c.get("kind") or "beat") not in FOR[f]:
                bad.append(f"{what}: {f} belongs on {' or '.join(FOR[f])}, not {c.get('kind') or 'beat'}")
        if c.get("reveals") and c["reveals"].lower() not in known["secrets"]:
            warn.append(f"{what}: {c['reveals']} is not a secret in the vault (kept as plain text)")
        if c.get("options") and ((c.get("kind") or "beat") != "decision" or not all(is_map(x) and x.get("label") for x in c["options"])):
            bad.append(f"{what}: options belong on a decision, each with a label (the choice) and a text (the outcome)")
        for f in ("anytime", "float"):
            if f in c and not isinstance(c[f], bool):
                bad.append(f"{what}: {f} must be true or false")
        if (c.get("kind") == "scene" and "anytime" in c) or (c.get("kind") != "scene" and any(f in c for f in ("float", "after", "before"))):
            bad.append(f"{what}: anytime belongs on a card in a scene; float, after and before on a scene")
        if "critical" in c and not isinstance(c["critical"], bool):
            bad.append(f"{what}: critical must be true or false")
        if c.get("where") and c["where"].lower() not in known["places"]:
            warn.append(f"{what}: {c['where']} is not a place in the vault (kept as plain text)")

    def into(i, sc):
        o, so = doc["items"][i], doc["items"][sc]
        inside = [m for m in doc["items"] if m != i and b.scene(m) == sc]
        ry = max([132 - 176, *[doc["items"][m].get("ry", 132) for m in inside]]) + 176
        o.update(scene=sc, rx=22, ry=ry, s=so["s"], at={}, lay=1)
        so["h"] = max(so.get("h", SCH), ry + 176)

    def stand(i, c, what):
        """Any time in its scene; floating, and within which limits (worked out once every key is known)."""
        o = doc["items"].get(i)
        if not o:
            return
        if "anytime" in c:
            o.pop("any", None)
            if c["anytime"]:
                if not b.scene(i):
                    bad.append(f"{what}: anytime needs a scene")
                else:
                    o["any"] = max([0, *[doc["items"][m].get("any") or 0 for m in doc["items"] if b.scene(m) == b.scene(i)]]) + 1
        if "float" in c:
            o.pop("float", None)
            if c["float"]:
                o["float"] = 1
            else:
                o.pop("after", None), o.pop("before", None)
        for f in ("after", "before"):
            if f in c:
                later.append((i, f, c[f] if isinstance(c[f], list) else [c[f]], what))

    def loose(i, s, k):
        doc["items"][i] = {"s": s, "homes": [k], "born": k, "at": {}}

    def place(pid, sc=None, s=None, k=None):
        i = "p:" + pid
        if pid not in b.data:
            bad.append(f"place: no live plan called '{pid}'")
            return
        if i not in doc["items"]:
            loose(i, s or sess(None), k or (b.data[pid]["lanes"] or boards)[0])
            doc["items"][i]["homes"] = [k] if k else list(b.data[pid]["lanes"]) or [boards[0]]
            if b.is_scene(i):
                doc["items"][i].update(w=SCW, h=SCH)
        elif s:
            doc["items"][i].update(s=s, at={})
        if k and k not in doc["items"][i]["homes"]:
            doc["items"][i]["homes"].append(k)
        if sc and b.is_scene(i):
            bad.append(f"place: {pid} is a scene, and scenes do not nest")
        elif sc:
            into(i, sc)

    def add(c, parent=None):
        if isinstance(c, str):
            return place(c[2:] if c.startswith("p:") else c, sc=parent)
        what = f"card '{c.get('title') or c.get('key') or '?'}'"
        for k in c:
            if k not in ("key", "cards", "in", "session", "board", *CARD_FIELDS, *PLACE):
                bad.append(f"{what}: unknown field '{k}'")
        if not c.get("title"):
            bad.append(f"{what}: needs a title")
        if c.get("title") in b.data:
            bad.append(f"{what}: a live plan already has this name; place it ('p:{c['title']}') instead")
        check(c, what)
        kind, cid = c.get("kind", "beat"), nid()
        i = "c:" + cid
        if c.get("key"):
            if c["key"] in ids:
                bad.append(f"{what}: key '{c['key']}' is used twice")
            ids[c["key"]] = i
        doc["cards"][cid] = {"kind": kind, "title": c.get("title", ""), "text": c.get("text", ""), "draft": "new"}
        for f in EXTRA:
            if c.get(f):
                doc["cards"][cid][f] = c[f]
        if c.get("options"):
            doc["cards"][cid]["options"] = [{"label": x["label"], "text": x.get("text", "")} for x in c["options"]]
        sc = parent or (ref(c["in"], what) if c.get("in") else None)
        if kind == "scene":
            if sc:
                bad.append(f"{what}: scenes do not nest")
            if "board" in c:
                bad.append(f"{what}: a scene goes on the boards of who is present; use present")
            s = sess(c.get("session"))
            cs = c.get("cards", [])
            doc["cards"][cid].update(where=c.get("where", ""), present=c.get("present", []))
            doc["items"][i] = {"s": s, "homes": [], "born": "The Party", "at": {}, "w": SCW, "h": SCH}
            doc["order"].setdefault(s, []).append(i)
            for x in cs:
                add(x, i)
            if not b.cast(i):
                warn.append(f"{what}: no players yet, so it waits on the session canvas")
        else:
            if c.get("cards"):
                bad.append(f"{what}: only a scene holds cards")
            if sc:
                if not b.is_scene(sc):
                    bad.append(f"{what}: '{c.get('in')}' is not a scene")
                home = b.lanes(sc)[0]
                loose(i, doc["items"][sc]["s"], home)
                into(i, sc)
            else:
                loose(i, sess(c.get("session")), board(c.get("board"), what))
        stand(i, c, what)

    for c in spec.get("cards", []):
        add(c)
    for p in spec.get("place", []):
        sc = ref(p["in"], f"place {p.get('plan')}") if p.get("in") else None
        place(p.get("plan"), sc, sess(p["session"]) if p.get("session") else None, board(p["board"], "place") if p.get("board") else None)

    for e in spec.get("edit", []):
        i = ref(e.get("id"), "edit", False)
        if not i:
            continue
        ch = {k: v for k, v in e.items() if k != "id" and k not in PLACE}
        check({"kind": b.obj(i).get("kind") or "beat", **{k: e[k] for k in PLACE if k in e}}, f"edit {e['id']}")
        stand(i, e, f"edit {e['id']}")
        check({"kind": b.obj(i).get("kind") or "beat", **ch}, f"edit {e['id']}")
        if i.startswith("c:"):
            if i[2:] not in doc["cards"]:
                bad.append(f"edit: no card {i}")
                continue
            for k in ch:
                if k not in CARD_FIELDS:
                    bad.append(f"edit {i}: unknown field '{k}'")
            c = doc["cards"][i[2:]]
            if (c.get("kind") == "scene") != (ch.get("kind", c.get("kind")) == "scene"):
                bad.append(f"edit {i}: turn a card into a scene, or back, on the page")
            c.update(ch)
            for f in EXTRA:
                if f in ch and not ch[f] and f not in ("where", "present"):
                    c.pop(f, None)
            if c.get("draft") != "new":
                c["draft"] = "edit"
        else:
            for k in ch:
                if k not in PLAN_FIELDS:
                    bad.append(f"edit {i}: unknown field '{k}'")
            if i[2:] not in b.data:
                bad.append(f"edit: no live plan {i}")
            doc["edits"].setdefault(i[2:], {}).update(ch)
    for i, f, names, what in later:
        doc["items"][i].pop(f, None)
        got = [x for x in (ref(n, f"{what} {f}") for n in names) if x]
        if any(not b.is_scene(x) or doc["items"][x]["s"] != doc["items"][i]["s"] for x in got):
            bad.append(f"{what}: {f} names scenes in the same session")
        if got:
            doc["items"][i].update({f: got, "float": 1})
    byid = {e["id"]: e for e in doc["edges"]}
    for row in spec.get("relabel", []):
        if row[0] in byid:
            byid[row[0]]["label"] = row[1]
        else:
            bad.append(f"relabel: no link {row[0]}")
    for eid in spec.get("unlink", []):
        if eid not in byid:
            bad.append(f"unlink: no link {eid} of Tom's (a link the vault holds changes in the plan)")
    doc["edges"] = b.edges = [e for e in doc["edges"] if e["id"] not in spec.get("unlink", [])]
    for x in spec.get("remove", []):
        i = ref(x, "remove", False)
        if i and not (i.startswith("c:") and i[2:] in doc["cards"]):
            bad.append(f"remove {x}: only cards that are not plans yet; drop a plan on the page")
        elif i:
            if any(b.scene(m) == i for m in doc["items"]):
                bad.append(f"remove {x}: the scene still holds cards; move or remove them first")
            doc["cards"].pop(i[2:])
            doc["items"].pop(i, None)
            doc["edges"] = b.edges = [e for e in doc["edges"] if i not in (e["from"], e["to"])]
            doc["order"] = {s: [z for z in zs if z != i] for s, zs in doc["order"].items()}
    for row in spec.get("links", []):
        if not 2 <= len(row) <= 3:
            bad.append(f"link {row}: write [from, to, label]")
            continue
        f, t, lab = ref(row[0], f"link {row}"), ref(row[1], f"link {row}"), (row[2] if len(row) > 2 else "") or ""
        if not f or not t:
            continue
        if f == t:
            bad.append(f"link {row}: a card cannot lead to itself")
        if b.obj(f).get("kind") == "decision" and not lab.strip():
            bad.append(f"link {row}: a link from a decision needs the choice as its label")
        if any(e["from"] == f and e["to"] == t and (e.get("label") or "").lower() == lab.lower() for e in doc["edges"]):
            warn.append(f"link {row}: already there")
            continue
        doc["edges"].append({"id": "e" + nid()[:7], "from": f, "to": t, "label": lab})
    for x in spec.get("layout", []):
        sc = ref(x, "layout")
        if sc and not b.is_scene(sc):
            bad.append(f"layout {x}: not a scene")
        for m in doc["items"] if sc else []:
            if b.scene(m) == sc:
                doc["items"][m]["lay"] = 1
    if spec.get("order"):
        s = sess(None)
        first = [i for i in (ref(x, "order") for x in spec["order"]) if i]
        have = [i for i in doc["order"].get(s, []) if i not in first]
        doc["order"][s] = first + have + [i for i in doc["items"] if b.live(i) and b.is_scene(i) and doc["items"][i]["s"] == s and i not in first + have]
    for i in doc["items"]:
        if b.live(i) and b.obj(i).get("kind") == "decision" and i.startswith("c:") and doc["cards"][i[2:]].get("draft") == "new":
            n = sum(e["from"] == i for e in doc["edges"]) + len(doc["cards"][i[2:]].get("options") or [])
            if n < 2:
                warn.append(f"decision '{doc['cards'][i[2:]]['title']}': {n} option{'' if n == 1 else 's'}; link it to what each choice leads to")
    return bad, warn, ids


def outline(doc, b, sessions=None, mark=lambda i: "", withids=True):
    """Every session's scenes in running order, their cards as a tree, then what is loose."""
    name = lambda i: i[2:] if i.startswith("p:") else doc["cards"][i[2:]].get("title") or "untitled"
    tag = lambda i: f"  [{i}]" if withids and i.startswith("c:") else "  [plan]" if i.startswith("p:") else ""
    live = [i for i in doc["items"] if b.live(i)]
    edges = [e for e in doc["edges"] if b.live(e["to"]) and (e["from"].startswith("start") or b.live(e["from"]))]
    for i in live:   # what the vault already links
        d = b.data.get(i[2:]) if i.startswith("p:") else None
        for o in (d or {}).get("options", []):
            if b.live("p:" + o["to"]) and not any(e["from"] == i and e["to"] == "p:" + o["to"] and (e.get("label") or "") == o["label"] for e in edges):
                edges.append({"id": "vault", "from": i, "to": "p:" + o["to"], "label": o["label"]})
        for t in (d or {}).get("leads", []):
            if b.live("p:" + t) and not any(e["from"] == i and e["to"] == "p:" + t for e in edges):
                edges.append({"id": "vault", "from": i, "to": "p:" + t, "label": ""})
        for r in (d or {}).get("req", []):
            f = "p:" + str(r["a"])
            if r["k"] in ("plan", "played") and b.live(f) and not any(e["from"] == f and e["to"] == i for e in edges):
                edges.append({"id": "vault", "from": f, "to": i, "label": ""})
    out = []

    def lines(i, depth, seen, inn):
        o, pad = b.obj(i), "  " * depth
        txt = (o.get("text") if i.startswith("c:") else o.get("summary")) or ""
        out.append(f"{pad}- {mark(i)}{'CRITICAL ' if has(o, 'critical') else ''}{(o.get('kind') or 'beat').upper()} {name(i)}{tag(i)}" + (f" ({o['clock']})" if has(o, "clock") else ""))
        if has(o, "cue"):
            out.append(f"{pad}    cue: {o['cue']}")
        if has(o, "who"):
            out.append(f"{pad}    who: {', '.join(o['who'])}")
        if has(o, "reveals"):
            out.append(f"{pad}    reveals: {o['reveals']}")
        for ln in txt.split("\n") if txt else []:
            if ln.strip():
                out.append(f"{pad}    {ln.strip()}")
        for x in o.get("options") or []:
            if not x.get("to"):
                out.append(f"{pad}    option: \"{x.get('label') or '(not named)'}\": {x.get('text') or '(outcome not written)'}  (listed only)")
        for e in edges:
            if e["from"] == i:
                arrow = f"{pad}    {'option' if o.get('kind') == 'decision' else 'leads to'}: " + (f'"{e["label"]}" → ' if e.get("label") else "→ ") + name(e["to"])
                out.append(arrow + (f"  [{e['id']}]" if withids else ""))
        for e in edges:
            if e["from"] == i and e["to"] in inn and e["to"] not in seen:
                seen.add(e["to"])
                lines(e["to"], depth + 1, seen, inn)

    def group(ms, depth):
        ms = sorted(ms, key=lambda m: (b.obj(m).get("kind") == "exit", doc["items"][m].get("ry", 0), doc["items"][m].get("rx", 0)))   # the ways out last
        led = {e["to"] for e in edges if e["from"] in ms}
        seen = set()
        for i in [m for m in ms if m not in led] + [m for m in ms if m in led]:
            if i not in seen:
                seen.add(i)
                lines(i, depth, seen, set(ms))

    for s in sessions or doc["sessions"]:
        scenes = [i for i in live if b.is_scene(i) and doc["items"][i]["s"] == s]
        order = [i for i in (doc.get("order") or {}).get(s, []) if i in scenes]
        scenes = order + [i for i in scenes if i not in order]
        free = [i for i in live if not b.is_scene(i) and not b.scene(i) and doc["items"][i]["s"] == s]
        if not scenes and not free:
            continue
        out.append(f"\n## {s}")
        n = 0
        for i in scenes:
            o, fl = b.obj(i), b.floating(i)
            n += not fl
            out.append(f"{'~' if fl else f'{n}.'} {mark(i)}SCENE {name(i)}{tag(i)}" + (f"  ({fl})" if fl else ""))
            out.append(f"     at {o.get('where') or '(where not set)'}" + (f" · {o['when']}" if o.get("when") else "") + f" · with {', '.join(o.get('present') or []) or 'nobody yet'} · boards: {', '.join(b.lanes(i))}")
            if o.get("purpose"):
                out.append(f"     purpose: {o['purpose']}")
            txt = (o.get("text") if i.startswith("c:") else o.get("summary")) or ""
            out += [f"     {ln.strip()}" for ln in txt.split("\n") if ln.strip()]
            out += [f"     leads to: {name(e['to'])}" + (f' · "{e["label"]}"' if e.get("label") else "") + (f"  [{e['id']}]" if withids else "") for e in edges if e["from"] == i]
            mem = [m for m in live if b.scene(m) == i]
            free_, flow = [m for m in mem if b.anytime(m)], [m for m in mem if not b.anytime(m)]
            if free_:
                out.append("     Any time:")
                for m in sorted(free_, key=lambda m: doc["items"][m]["any"]):
                    lines(m, 3, set(), set())
                if flow:
                    out.append("     In order:")
            group(flow, 2)
        if free:
            out.append("Not in a scene:")
            for k in dict.fromkeys(b.lanes(i)[0] for i in free):
                out.append(f"  {k}:")
                group([i for i in free if b.lanes(i)[0] == k], 2)
    return "\n".join(out).strip()


def record(mock, before, after):
    d = folder(mock)
    path = os.path.join(d, time.strftime("%Y%m%d-%H%M%S") + ".json")
    json.dump({"before": {k: before.get(k) for k in PARTS}, "after": {k: after.get(k) for k in PARTS}}, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    for old in sorted(os.listdir(d))[:-20]:
        os.remove(os.path.join(d, old))
    return os.path.basename(path)[:-5]
