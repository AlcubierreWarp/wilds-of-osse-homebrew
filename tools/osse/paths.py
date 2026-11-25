#!/usr/bin/env python3
"""Session planner (once called Paths ahead): the DM's planning board (vault/paths.html). Built by pages.py on every build; never edit the page by hand.

Two views of the whole session, Running order and Canvas, show everything planned for it; under them sits one board per player
character and one for the World (what moves without the party). Each board has a tab and a canvas per session (the next sessions,
then Later). In the store the session canvas is the lane "The Party" and the World is "world". The first tab starts from the end of the last played session; each later tab starts
from the end of the one before, as planned. Each board's live plans wait in a tray beside it; Tom drags the ones he
wants onto a session's canvas, draws links between cards, adds, edits and deletes cards, and adds or deletes sessions.
Plans that already have a `target` start in that session's tab. Edits to a plan's text and plans he drops are kept as
overrides until Claude writes them into the vault. The layout is saved as JSON Canvas (jsoncanvas.org) on the Gus relay,
behind the hub's game master passcode; `tools/osse/paths_sync.py` reads it so Claude can turn Tom's changes into
vault plans (see the `paths` skill). The vault stays the truth: the board only places and connects.

Which plans sit in a board's tray: plans whose `for:` names that character; else plans that name the character in
their Links or Requires; else plans that touch someone tied to the character at weight 5; else the session canvas when
they name The Party; else the World. The tray can also show every live plan.
The rules for kinds, options and branching are in docs/osse/branching.md."""
import json, re

import build

STANDING = {"pc", "npc", "faction", "item", "party"}   # link ends that can die
STAMP = re.compile(r"\s*\*\((?:S\d+[^)]*|prep[^)]*)\)\*")


def _plain(s):
    return build.LINK.sub(lambda m: m.group(1), str(s or ""))


def _names(arg):
    return [build.link_name(p.strip()) for p in arg.split("·") if build.link_name(p.strip())]


def _secs(text):
    import pages
    return dict(pages.sections(text))


def _bullets(lines):
    return [ln.strip()[2:] for ln in lines if ln.strip().startswith("- ")]


def _latest(lines, cur):
    """The lines stamped with the most recent session any line carries, without their stamps."""
    tagged = []
    for ln in lines:
        nums = [int(x) for x in re.findall(r"\bS(\d+)\b", " ".join(re.findall(r"\*\(([^)]*)\)\*", ln)))]
        if nums and max(nums) <= cur:
            tagged.append((max(nums), ln))
    if not tagged:
        return 0, []
    top = max(n for n, _ in tagged)
    return top, [_plain(STAMP.sub("", ln)).strip().lstrip("- ").strip() for n, ln in tagged if n == top]


def _list(v):
    return v if isinstance(v, list) else [v] if v not in (None, "") else []


def collect(site):
    g, nodes, cur = site.g, site.nodes, site.cur
    pcs = sorted((n for n in g["nodes"] if n["type"] == "pc"), key=lambda n: (-int(n.get("importance") or 0), n["id"]))
    pc_ids = [n["id"] for n in pcs]
    plans = {n["id"]: n for n in g["nodes"] if n["type"] == "plan"}
    live = {k: n for k, n in plans.items() if n.get("status") in build.LIVE}

    ties = {p: set() for p in pc_ids}
    for e in g["edges"]:
        if e.get("origin") not in ("written", "property") or e.get("layer") == "draft" or int(e.get("weight") or 0) < 5:
            continue
        if e.get("end") is not None and e["end"] <= cur:
            continue
        for a, b in ((e["from"], e["to"]), (e["to"], e["from"])):
            if a in ties and b not in pc_ids and b != "The Party" and nodes.get(b, {}).get("type") not in ("place", "plan", "session"):
                ties[a].add(b)

    data = {}
    for pid, n in live.items():
        text = site.text(pid)
        reqs, links, _ = build.parse_plan({"text": text})
        req = []
        for k, arg in reqs:
            names = _names(arg)
            req.append({"k": k, "a": names[0] if names else "", "t": _plain(arg),
                        "w": [w.strip().lower() for w in (arg.split("·")[1] if "·" in arg else "").split(",") if w.strip()]})
        explicit = {r["a"] for r in req if r["k"] in ("dead", "state")}
        ents = []
        for l in links:
            for end in (l["from"], l["to"]):
                if end not in ents:
                    ents.append(end)
                if end in nodes and end not in explicit and nodes[end]["type"] in STANDING and \
                        not any(r["k"] == "alive" and r["a"] == end for r in req):
                    req.append({"k": "alive", "a": end, "w": [], "t": end, "imp": 1})
        kind = str(n.get("kind") or "beat").lower()
        for key, k, rk in (("who", "entrance", "alive"), ("reveals", "reveal", "hidden")):   # the same as build.py's implicit requirements
            for a in (_plain(x).strip() for x in _list(n.get(key))) if kind == k else ():
                if a in nodes and a not in explicit and not any(r["k"] == rk and r["a"] == a for r in req):
                    req.append({"k": rk, "a": a, "w": [], "t": a, "imp": 1})
        named = set(ents) | {r["a"] for r in req if r["a"]}
        fm_for = [x for x in (_plain(v).strip() for v in _list(n.get("for"))) if x]
        lanes, via = [x for x in fm_for if x in pc_ids or x == "The Party"], {}
        if not lanes:
            lanes = [p for p in pc_ids if p in named]
        if not lanes:
            for p in pc_ids:
                hit = sorted(ties[p] & named)
                if hit:
                    lanes.append(p); via[p] = hit[0]
        if str(n.get("kind") or "").lower() == "scene":   # a scene is on the board of every player character present
            for x in (_plain(v).strip() for v in _list(n.get("present"))):
                if (x in pc_ids or x == "The Party") and x not in lanes:
                    lanes.append(x)
        if not lanes:
            lanes = ["The Party"] if "The Party" in named else ["world"]
        sec = _secs(text)
        data[pid] = {"id": pid, "path": n["path"], "href": site.slugs.get(pid, "") + ".html", "status": n.get("status"),
                     "kind": kind,
                     "where": _plain(n.get("where") or ""), "present": [_plain(x) for x in _list(n.get("present"))],
                     "when": _plain(n.get("when") or ""), "purpose": _plain(n.get("purpose") or ""), "cue": _plain(n.get("cue") or ""),
                     "who": [_plain(x) for x in _list(n.get("who"))], "reveals": ", ".join(_plain(x) for x in _list(n.get("reveals"))),
                     "critical": build.yes(n.get("critical")), "leads": [_plain(x).strip() for x in _list(n.get("leads_to"))],
                     "scene": _plain(n.get("scene") or ""), "clock": str(n.get("clock") or ""), "target": str(n.get("target") or ""),
                     "summary": _plain(n.get("summary")), "req": req, "lanes": lanes, "via": via,
                     "idea": site.blocks(sec.get("Idea", [])),
                     "ideaText": "\n".join(_plain(x) for x in sec.get("Idea", [])).strip(),
                     "options": [{"to": t, "label": c} if t else {"to": "", "label": c, "text": x} for t, c, x in build.parse_options(text)],
                     "anytime": build.yes(n.get("anytime")),
                     "pcs": [x for x in pc_ids if x in named or x in (_plain(v) for v in [*_list(n.get("present")), *_list(n.get("who"))])],
                     "names": sorted({x for x in [*named, *(_plain(v) for v in _list(n.get("present"))), _plain(n.get("where") or "")] if nodes.get(x, {}).get("type") not in (None, "pc", "party", "plan", "session")}),
                     "links": [f'{l["from"]} · {l["type"]} · {l["to"]}' + (f' ({l["note"]})' if l.get("note") else "") for l in links]}

    facts = {}
    for d in data.values():   # and on the board of every player character on one of its cards
        sc = data.get(d["scene"])
        if sc and sc["kind"] == "scene":
            on = d["who"] or d["lanes"]
            for x in pc_ids if "The Party" in on else [p for p in pc_ids if p in on]:
                if x not in sc["lanes"]:
                    sc["lanes"] = [*(k for k in sc["lanes"] if k != "world"), x]
    for d in data.values():
        for r in d["req"]:
            a = r["a"]
            if a and a in nodes and a not in facts:
                m = nodes[a]
                f = {"type": m["type"], "state": str(m.get("state") or "").lower(), "href": site.slugs.get(a, "") + ".html",
                     "out": bool(build.snum(m.get("revealed") or "") is not None and build.snum(m.get("revealed")) <= cur)}
                if m["type"] == "secret":
                    f["clues"] = len(_bullets(_secs(site.text(a)).get("How it could come out", [])))
                facts[a] = f
    return pcs, plans, live, data, facts


def sheet(n):
    """Hit points, slots and conditions as recorded at the end of the last session (post-session sync, from D&D Beyond)."""
    return {k: str(n.get(k)) for k in ("hp", "hp_max", "hp_temp", "slots", "conditions", "sheet_at", "ddb") if n.get(k) not in (None, "")}


# Each player character's colour, as the session screens (screen/sNN.html) use it.
PC_COLOUR = {"Belaskro Tich": "#6fbf9a", "Gabriele d'Avidicci": "#ee8a8a", "GUS": "#e2be6a", "Princess Timbit": "#c3a2f2"}


def lanes_data(site, pcs, data):
    cur, nodes = site.cur, site.nodes
    sess = sorted((n for n in nodes.values() if n["type"] == "session" and str(n.get("number", "")).isdigit()
                   and int(n["number"]) <= cur), key=lambda n: int(n["number"]))
    last = sess[-1] if sess else None
    last_secs = _secs(site.text(last["id"])) if last else {}
    out = []
    for p in pcs:
        nid = p["id"]
        top, recent = _latest(_secs(site.text(nid)).get("Now", []), cur)
        short = nid if " " not in nid else next((str(a) for a in p.get("aliases", []) if " " not in str(a)), nid.split()[0])
        out.append({"key": nid, "short": short, "kind": "pc", "colour": PC_COLOUR.get(nid, "#b9ab95"),
                    "aliases": [str(a) for a in p.get("aliases", []) if a],
                    "now": {"title": nid, "href": site.slugs.get(nid, "") + ".html", "player": p.get("player", ""),
                            "class": _plain(p.get("class", "")), "location": _plain(p.get("location", "")),
                            "state": p.get("state", ""), "sheet": sheet(p), "recent": recent[:5], "recent_at": top}})
    party = nodes.get("The Party")
    if party:
        top, recent = _latest(_secs(site.text("The Party")).get("Now", []), cur)
        out.append({"key": "The Party", "short": "The Party", "kind": "party",
                    "now": {"title": "The whole party", "href": site.slugs.get("The Party", "") + ".html",
                            "location": _plain(party.get("location", "")), "state": party.get("state", ""),
                            "members": [{"name": p["id"], "sheet": sheet(p)} for p in pcs],
                            "summary": _plain(last.get("summary")) if last else "", "recent": recent[:3], "recent_at": top}})
    opens = next((v for k, v in last_secs.items() if k.startswith("Open going into")), [])
    out.append({"key": "world", "short": "World", "kind": "world",
                "now": {"title": "The world", "about": "What moves without the party knowing, and could still reach them.", "href": site.slugs.get(last["id"], "") + ".html" if last else "",
                        "summary": _plain(last.get("summary")) if last else "",
                        "recent": [_plain(x) for x in _bullets(opens)][:6], "recent_at": cur, "open": True}})
    for ln in out:
        ln["count"] = sum(1 for d in data.values() if ln["key"] in d["lanes"])
    return out


def page(site):
    import pages
    cur = site.cur
    pcs, plans, live, data, facts = collect(site)
    lanes = lanes_data(site, pcs, data)
    g = site.g["nodes"]
    places = sorted(n["id"] for n in g if n["type"] == "place")
    people = sorted(({"n": n["id"], "t": n["type"]} for n in g if n["type"] in ("pc", "npc", "party", "faction")
                     and str(n.get("state") or "").lower() not in build.GONE), key=lambda x: ({"pc": 0, "party": 1, "npc": 2}.get(x["t"], 3), x["n"]))
    secrets = sorted(({"n": n["id"], "out": bool(build.snum(n.get("revealed") or "") is not None and build.snum(n.get("revealed")) <= cur)} for n in g if n["type"] == "secret"), key=lambda x: x["n"])
    import arcs
    payload = {"secrets": secrets, "cur": cur, "plans": data, "facts": facts, "lanes": lanes, "gone": sorted(build.GONE), "places": places, "people": people}
    js_data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    head = pages.head("Session planner", False).replace('<div class="wrap">', '<div class="wrap wide">')
    return (head + f"<style>{arcs.PANEL}{CSS}</style>" + pages.topbar(site, here="paths") +
            '<main class="sheet paths">'
            '<div class="ptop"><h1>Session planner</h1><div class="views"><span>Whole session</span><nav id="views" role="tablist" aria-label="Whole session"></nav></div>'
            '<nav class="lanes" id="lanes" role="tablist" aria-label="Boards"></nav>'
            '<div class="tools"><span id="save" class="save"></span><span class="rwt big" id="rw" role="group" aria-label="Side panels open to read or to edit"></span></div></div>'
            '<div class="pal" id="pal" role="toolbar" aria-label="Cards: click one to add it, or drag it into place"></div>'
            '<div class="runw" id="runw" hidden><div class="stage"><nav class="sess" id="rsess" role="tablist" aria-label="Sessions"></nav>'
            '<div class="run" id="run" aria-label="Running order"></div></div>'
            '<aside class="tray" id="loose"><div class="tsec" id="loosez"></div><div class="tsec grow" data-tray></div></aside></div>'
            '<div class="work" id="work"><div class="stage"><nav class="sess" id="sess" role="tablist" aria-label="Sessions"></nav>'
            '<div class="board" id="board" aria-label="Planning board">'
            '<div class="world" id="world"><svg id="wires" class="wires"></svg><div id="nodes"></div></div>'
            '<button class="sname" id="sname" hidden title="This session’s name, what happens and its arc"></button>'
            '<div class="float"><button class="fb" data-act="line" id="lineup" title="Tidy this canvas: scenes in running order, the cards in them by their arrows, the rest underneath">Line up</button><button class="fb" data-act="zout" title="Zoom out" aria-label="Zoom out">−</button><button class="fb" data-act="zin" title="Zoom in" aria-label="Zoom in">+</button><button class="fb" data-act="fit" title="Fit to the window" aria-label="Fit to the window">'
            '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 8V3h5M12 3h5v5M17 12v5h-5M8 17H3v-5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></button>'
            '<button class="fb" data-act="legend" title="Key" aria-label="Key">Key</button></div>'
            '<div class="keyp" id="keyp" hidden></div>'
            '</div></div>'
            '<aside class="tray" id="tray"><div class="tsec grow" data-tray></div></aside></div>'
            '<aside id="drawer" class="drawer" hidden></aside>'
            f'<script>const PATHS={js_data};</script><script>' + JS.replace('/*LINK*/', arcs.LINK) + '</script></main></div></body></html>')


CSS = r"""
.wrap.wide{max-width:none}
.paths{padding:12px clamp(12px,1.4vw,20px) 14px}
html{overscroll-behavior:none}body{padding:12px 14px;user-select:none;-webkit-user-select:none}input,textarea,.drawer,.keyp{user-select:text;-webkit-user-select:text}
header{padding-bottom:8px;margin-bottom:10px}
@media (min-width:901px) and (min-height:560px){   /* the page is the window: nothing under the canvas, nothing to scroll */
  html,body{height:100%;min-height:0;overflow:hidden;overflow:clip}body{height:100dvh}
  .wrap.wide{height:100%;display:flex;flex-direction:column}header{flex:none}
  .paths{flex:1;min-height:0;display:flex;flex-direction:column}.paths>*{flex:none}
  .paths .work,.paths .runw{flex:1;height:auto;min-height:0}
}
.ptop{display:flex;flex-wrap:wrap;align-items:center;gap:8px 18px;margin-bottom:10px}.ptop h1{font-size:27px}
@media (max-width:1700px){.ptop{gap:8px 10px}.ptop h1{font-size:22px}.lanes .lb,.ptop .views>span{display:none}.lanes .sep{margin:0 2px}.ptop .views button{padding:10px 12px}.lanes button{padding:7px 10px}}
.trayh b{font:600 11.5px var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:var(--vred)}
.ptop .tools{margin-left:auto}
.views{display:flex;align-items:stretch;border:2px solid #3f5a3c;border-radius:7px;overflow:hidden;background:#e7efe3}
.views>span{display:flex;align-items:center;padding:0 12px;font:500 10.5px/1 var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:#3f5a3c;border-right:2px solid #3f5a3c}
.views nav{display:flex}.views button{display:inline-flex;align-items:center;gap:8px;font:600 14px/1 var(--f-display);letter-spacing:.05em;color:#3f5a3c;background:none;border:0;padding:11px 16px;cursor:pointer}
.views button+button{border-left:1px solid #9bb397}.views button:hover{background:#d8e5d2}.views svg{flex:none}
.views button[aria-selected=true]{background:#3f5a3c;color:var(--vellum)}
.lanes{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
.lanes .lb{font:500 10.5px/1 var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted);margin-right:3px}
.lanes .sep{width:1px;height:24px;background:var(--vrule);margin:0 7px}
.lanes button{display:inline-flex;align-items:center;font:600 13px/1 var(--f-display);letter-spacing:.06em;color:var(--vmuted);background:rgba(255,255,255,.35);border:1px solid var(--vline);border-radius:999px;padding:8px 13px;cursor:pointer}
.lanes button i{width:11px;height:11px;border-radius:50%;background:var(--c);border:1px solid rgba(42,29,18,.45);margin-right:8px}
.lanes button small{color:inherit;font:500 11px var(--f-mono);margin-left:6px;opacity:.75}
.lanes button:hover{border-color:var(--vink)}.lanes button[aria-selected=true]{background:var(--vink);color:var(--vellum);border-color:var(--vink)}
.lanes button.wb{border-radius:6px;border-color:rgba(61,90,128,.5);color:#3d5a80}.lanes button.wb[aria-selected=true]{background:#3d5a80;border-color:#3d5a80;color:var(--vellum)}.lanes .wb svg{margin-right:7px}
.paths.whole .sess button[aria-selected=true]{color:#3f5a3c}.paths.whole .board,.paths.whole .run{border-color:#7f977b}
.wires path.run{stroke:#7f977b;stroke-width:5;stroke-linecap:round;opacity:.7}
.ord{display:inline-grid;place-items:center;min-width:26px;height:26px;margin-right:8px;border-radius:50%;background:#3f5a3c;color:var(--vellum);font:600 14px/1 var(--f-display)}
.tools{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.mini{font:500 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--vrule);background:rgba(255,255,255,.45);color:var(--vred);border-radius:4px;padding:8px 10px;cursor:pointer}
.mini:hover{background:#fff}
.save{font:500 11.5px var(--f-mono);color:var(--vmuted);margin-left:4px;max-width:420px}.save.bad{color:var(--vred)}
.pal{display:flex;flex-wrap:wrap;gap:5px;align-items:stretch;margin:0 0 8px}
.pal button{display:inline-flex;align-items:center;gap:7px;font:500 13.5px/1 var(--f-body);color:var(--vink);background:#fbf5e6;border:1px solid var(--vline);border-left:4px solid var(--kc,var(--vmuted));border-radius:5px;padding:8px 10px 8px 8px;min-height:36px;cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none}
.pal button svg{color:var(--kc,var(--vmuted));flex:none}.pal button:hover{background:#fff;border-color:var(--kc,var(--vink))}.pal button:active{cursor:grabbing}.pal button.drag{opacity:.45}
@media (max-width:700px){.pal button span{display:none}.pal button{padding:8px}.pal button svg{width:20px;height:20px}}
.pal .sep{width:1px;background:var(--vrule);margin:3px 5px}
.k-scene{--kc:#4d6b4a}.k-beat{--kc:#6b5b45}.k-reveal{--kc:#6a4a8a}.k-complication{--kc:#b5561c}.k-decision{--kc:var(--vred)}.k-entrance{--kc:#2f7d76}.k-exit{--kc:var(--vink)}.k-clock{--kc:#3d5a80}.k-pressure{--kc:#b8860b}.k-bottleneck{--kc:var(--vink)}.k-note{--kc:#c9a400}
.sname{display:inline-flex;align-items:center;gap:8px;font:500 14px/1 var(--f-body);color:var(--vink);background:rgba(251,245,230,.95);border:1px solid var(--vrule);border-radius:6px;padding:8px 10px;cursor:pointer;max-width:min(460px,calc(100% - 20px))}
.sname[hidden]{display:none}.sname:hover{background:#fff}.sname b{font:600 13px/1 var(--f-display)!important;letter-spacing:.06em!important;text-transform:none!important;color:var(--vred)!important}.sname small,.sname .pen{color:var(--vmuted);font:500 11px var(--f-mono)}.sname i{color:var(--vmuted)}
#sname{position:absolute;left:10px;top:10px;z-index:8;min-height:34px;box-shadow:0 2px 6px rgba(42,29,18,.15)}
.pick{display:flex;gap:12px;align-items:baseline;width:100%;text-align:left;font:16px/1.3 var(--f-body);color:var(--vink);background:rgba(255,255,255,.45);border:1px solid var(--vline);border-left:4px solid #4d6b4a;border-radius:5px;padding:9px 11px;margin:5px 0 0;cursor:pointer}
.pick:hover{background:#fff;border-color:#4d6b4a}.pick b{flex:none;min-width:34px;font:600 14px var(--f-display);color:#3f5a3c}.pick small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:13.5px;color:var(--vmuted);margin-top:2px}.pick.new{border-left-style:dashed;background:none}
.ki{vertical-align:-2px;margin-right:5px;flex:none}.keyp dt .ki{color:var(--kc)}.ghost .ki{color:var(--kc)}
.work{display:grid;grid-template-columns:1fr 300px;gap:12px;height:calc(100vh - 300px);min-height:480px}
.stage{display:flex;flex-direction:column;min-height:0;min-width:0}
.sess{display:flex;gap:2px;align-items:flex-end;overflow-x:auto;padding-left:6px}
.sess button{font:600 13px/1 var(--f-display);letter-spacing:.08em;color:var(--vmuted);background:rgba(255,255,255,.3);border:1px solid var(--vrule);border-bottom:0;border-radius:6px 6px 0 0;padding:10px 14px 9px;cursor:pointer;white-space:nowrap}
.sess button small{font:500 10.5px var(--f-mono);letter-spacing:.02em;margin-left:6px;opacity:.8}
.sess button[aria-selected=true]{background:#f6eed8;color:var(--vred);position:relative;top:1px}
.sess button.drop{background:rgba(124,22,34,.15)}
.sess .dx{display:inline-block;margin-left:8px;padding:0 4px;border-radius:3px;font:600 13px var(--f-mono);color:var(--vmuted)}.sess .dx:hover{background:var(--vred);color:var(--vellum)}
.sess .add{font:500 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--vred);border-style:dashed}
.board{position:relative;flex:1;min-height:0;overflow:hidden;overflow:clip;border:1px solid var(--vrule);border-radius:0 8px 8px 8px;
  background-color:#f6eed8;background-image:radial-gradient(circle,rgba(42,29,18,.2) 1.1px,transparent 1.4px);touch-action:none;cursor:grab}
.board.panning{cursor:grabbing}
.world{position:absolute;left:0;top:0;transform-origin:0 0}
.wires{position:absolute;left:0;top:0;width:1px;height:1px;overflow:visible;pointer-events:none}
.wires path{fill:none;stroke:rgba(124,22,34,.45);stroke-width:1.8}
.wires path.own{stroke:var(--vred);stroke-dasharray:6 4;stroke-width:2}
.wires path.opt{stroke:var(--vink);stroke-width:2}
.wires path.carry{stroke:rgba(42,29,18,.35);stroke-dasharray:2 4}
.wires polygon{fill:rgba(124,22,34,.6)}.wires polygon.own{fill:var(--vred)}.wires polygon.opt{fill:var(--vink)}.wires polygon.carry{fill:rgba(42,29,18,.5)}
.wires path.hit{stroke:transparent;stroke-width:16;pointer-events:stroke;cursor:pointer}
.wires path.temp{stroke:var(--vred);stroke-dasharray:3 4}
.wl{position:absolute;transform:translate(-50%,-50%);font:italic 13px/1.2 var(--f-body);background:#f6eed8;color:var(--vink);border:1px solid var(--vline);border-radius:4px;padding:1px 6px;white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis;z-index:2}
.wl.own{border-color:var(--vrule);color:var(--vred);cursor:pointer}
.float{position:absolute;right:10px;top:10px;display:flex;gap:6px;z-index:8}
.fb{height:34px;min-width:34px;font-size:13px;display:inline-flex;align-items:center;justify-content:center;font:600 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;
  color:var(--vink);background:rgba(251,245,230,.95);border:1px solid var(--vrule);border-radius:6px;padding:0 9px;cursor:pointer;box-shadow:0 2px 6px rgba(42,29,18,.15)}
.fb:hover,.fb.on{background:var(--vink);color:var(--vellum)}
.keyp{position:absolute;right:10px;top:52px;width:min(360px,calc(100% - 20px));max-height:calc(100% - 64px);overflow:auto;z-index:9;
  background:#fbf5e6;border:1px solid var(--vrule);border-radius:8px;padding:14px 16px;box-shadow:0 10px 30px rgba(42,29,18,.25);font-size:14.5px;cursor:default}
.keyp h3{font-size:18px;margin:0 24px 6px 0}.keyp .x{position:absolute;right:8px;top:4px;border:0;background:none;font-size:24px;cursor:pointer;color:var(--vmuted)}
.keyp dt{font-weight:600;margin-top:7px}.keyp dd{margin:0;color:var(--vmuted)}
.bn{position:absolute;width:250px;display:flex;flex-direction:column;gap:4px;font:14.5px/1.3 var(--f-body);color:var(--vink);
  background:#fbf5e6;border:1px solid var(--vline);border-left:5px solid var(--vmuted);border-radius:6px;padding:8px 11px 9px;box-shadow:0 2px 6px rgba(42,29,18,.12);cursor:pointer;user-select:none;-webkit-user-select:none;touch-action:none}
.bn:hover,.bn.on{box-shadow:0 0 0 2px rgba(124,22,34,.35),0 4px 12px rgba(42,29,18,.18)}
.bn.drag{opacity:.85;box-shadow:0 10px 24px rgba(42,29,18,.3);z-index:5}
.bn .k{font:500 10px var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted);display:flex;justify-content:space-between;gap:6px}
.bn .t{font-weight:600;font-size:15.5px;line-height:1.25}
.bn .s{font-size:13px;color:var(--vmuted)}
.bn .chips,.ti .chips,.kv .chips{display:flex;flex-wrap:wrap;gap:4px;margin:2px 0 0}
.ch{font:500 10.5px/1.5 var(--f-mono);padding:0 6px;border-radius:3px;border:1px solid var(--vline);background:rgba(255,255,255,.6);white-space:nowrap;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.ch.ready{background:var(--vink);color:var(--vellum);border-color:var(--vink)}.ch.sec{border:1px dashed var(--vred);color:var(--vred)}
.ch.sec.out{background:var(--vred);color:var(--vellum);border-style:solid}.ch.move{background:#b8860b;color:#fff;border-color:#b8860b}.ch.ck{border-color:#b8860b;color:#7a5a08}
.ch.ed{display:inline-block;margin:0;font-size:10.5px;border:1px dashed var(--vred);color:var(--vred)}
.bn .opts{margin:2px 0 0;padding:0;list-style:none;font-size:13px}.bn .opts li{margin:2px 0}.bn .opts li::before{content:"◇ ";color:var(--vred)}.bn .opts li.ld::before{content:none}.opts .to{color:var(--vmuted)}.opts .off{opacity:.6}
.bn .xx{position:absolute;right:-10px;top:-10px;width:22px;height:22px;border-radius:50%;border:1px solid var(--vrule);background:#fbf5e6;color:var(--vred);font:600 14px/18px var(--f-mono);padding:0;cursor:pointer;display:none;z-index:3}
.bn:hover .xx,.bn.on .xx{display:block}.bn .xx:hover{background:var(--vred);color:var(--vellum)}
.bn .hd{position:absolute;right:-10px;top:50%;width:20px;height:20px;margin-top:-10px;border-radius:50%;background:#f6eed8;border:2px solid var(--vred);cursor:crosshair;touch-action:none}
.bn .hd::after{content:"+";position:absolute;inset:0;font:600 13px/16px var(--f-mono);text-align:center;color:var(--vred)}
.k-decision{border-left-color:var(--vred)}.bn.k-decision .k{color:var(--vred)}
.k-pressure{border-left-color:#b8860b}.bn.k-pressure{background:#fbf0d6}.bn.k-pressure .k{color:#7a5a08}
.bn.k-bottleneck{border:2px solid var(--vink);border-left:6px double var(--vink)}.k-bottleneck{border-left-color:var(--vink)}
.bn.k-note{background:#fff6b8;border-left-color:#c9a400}
.bn.scene{background:rgba(77,107,74,.05);border:2px dashed rgba(42,29,18,.38);border-radius:10px;box-shadow:none;padding:0;pointer-events:none;cursor:default;gap:0}
.bn.scene:hover,.bn.scene.on{box-shadow:none;border-color:var(--vred)}.bn.scene.hot{border-color:var(--vred);background:rgba(124,22,34,.07)}
.bn.scene .sh{pointer-events:auto;cursor:grab;display:flex;flex-direction:column;gap:4px;background:#efe4c4;border-bottom:1px solid var(--vline);border-left:5px solid #4d6b4a;border-radius:8px 8px 0 0;padding:9px 14px 10px}
.bn.scene .k,.bn.scene .k span:first-child{color:#3f5a3c}.bn.scene .t{font:600 18px var(--f-display);letter-spacing:.01em}
.bn.scene.mine{outline:0}.bn.scene.mine .sh{outline:1px dashed var(--vred);outline-offset:-4px}
.bn.scene .rz{pointer-events:auto;position:absolute;right:0;bottom:0;width:24px;height:24px;cursor:nwse-resize;background:linear-gradient(135deg,transparent 55%,rgba(42,29,18,.45) 55%);border-radius:0 0 8px 0;touch-action:none}
.bn.scene .hd,.bn.scene .xx{pointer-events:auto}.bn.scene .hd{top:30px;margin-top:0}
.k-reveal{border-left-color:#6a4a8a}.bn.k-reveal .k{color:#6a4a8a}
.k-complication{border-left-color:#b5561c}.bn.k-complication .k{color:#b5561c}
.k-entrance{border-left-color:#2f7d76}.bn.k-entrance .k{color:#2f7d76}
.bn.k-exit{border-left-color:var(--vink);border-right:5px solid var(--vink)}.k-exit{border-left-color:var(--vink)}.bn.k-exit .k{color:var(--vink)}
.bn.crit{background:#fbe6e0;border-color:var(--vred);border-left-width:9px}
.cue{font-size:13.5px;font-style:italic}.cue b,.pur b{font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vred);margin-right:6px}.pur{font-size:13.5px}
.adds{display:flex;flex-wrap:wrap;gap:5px;align-items:center}.rm .adds{margin-top:10px}.adds button{font:500 11px var(--f-mono);letter-spacing:.04em;border:1px solid var(--vline);border-left-width:4px;border-left-style:solid;background:rgba(255,255,255,.5);color:var(--vink);border-radius:4px;padding:6px 8px;cursor:pointer}.adds button:hover{background:#fff}
.tr .tt .cue{display:block;font-size:13px;color:var(--vmuted)}
.mk.k-decision.crit{background:var(--vred);color:var(--vellum);border-left-color:var(--vred);padding-right:4px}
.rc .rp{font-size:13.5px;margin-top:2px}
.k-scene{border-left-color:#4d6b4a}.k-clock{border-left-color:#3d5a80}.bn.k-clock .k{color:#3d5a80}
.at{font-size:13.5px}.at b{font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vmuted);margin-right:5px}
.ch.who,.pcx.who{display:inline-flex;align-items:center;gap:3px}
.ch.who button,.pcx.who button{border:0;background:none;cursor:pointer;color:var(--vred);font:600 12px var(--f-mono);padding:0 0 0 3px}
.clk{display:flex;align-items:center;gap:8px;font:500 12px var(--f-mono);color:#3d5a80}
.rng{border:0;background:none;padding:0;cursor:pointer;line-height:0;display:inline-block}
.rng path{fill:rgba(255,255,255,.8);stroke:#3d5a80;stroke-width:1.4}.rng path.on{fill:#3d5a80}
.bn.mine{outline:1px dashed var(--vred);outline-offset:3px}
.bn.mine .k span:last-child,.bn.edited .k span:last-child{color:var(--vred)}
.bn.now{width:300px;background:var(--vink);color:var(--vellum);border:1px solid var(--vink);border-left:5px solid var(--gold)}
.bn.now .k{color:var(--gold-hi)}.bn.now .t{font:600 19px var(--f-display);letter-spacing:.02em}.bn.now a{color:var(--gold-hi)}
.bn.now .s{color:rgba(239,227,198,.8)}
.bn.now dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 10px;margin:4px 0;font-size:13.5px}
.bn.now dt{font:500 10px/1.9 var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--gold-hi);opacity:.8}.bn.now dd{margin:0}
.bn.now ul{margin:2px 0 0;padding-left:16px;font-size:13.5px;color:rgba(239,227,198,.88)}.bn.now li{margin:2px 0}
.bn.now .miss{opacity:.6;font-style:italic}
.bn.start{background:#3a2c20}
.tray{display:flex;flex-direction:column;min-height:0;border:1px solid var(--vrule);border-radius:8px;background:rgba(255,255,255,.3);padding:10px}
.tray.over{background:rgba(124,22,34,.1);border-style:dashed}
.trayh{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.all{font:500 11px var(--f-mono);color:var(--vmuted)}
.tsec{display:flex;flex-direction:column;min-height:0;border-radius:6px}.tsec.grow{flex:1}.tsec.over{background:rgba(124,22,34,.1);outline:1px dashed var(--vred)}
#loosez{flex:none;max-height:44%;overflow:auto;border-bottom:1px solid var(--vrule);margin-bottom:10px;padding-bottom:6px}#loosez[hidden]{display:none}#loosez .tlist{overflow:visible}
.trayh small{font:500 11px var(--f-mono);color:var(--vmuted);margin-right:auto}.all[hidden]{display:none}
.tqr{display:flex;gap:6px;margin:8px 0}.tqr .tq{flex:1;min-width:0;font:15px var(--f-body);padding:8px 10px;border:1px solid var(--vline);border-radius:4px;background:rgba(255,255,255,.6);color:var(--vink)}
.tfb{display:inline-flex;align-items:center;gap:6px;font:500 11px var(--f-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--vink);background:rgba(255,255,255,.45);border:1px solid var(--vline);border-radius:4px;padding:0 9px;cursor:pointer}
.tfb:hover{background:#fff}.tfb.on,.tfb[aria-expanded=true]{border-color:var(--vred);color:var(--vred)}.tfb b{font:700 11px var(--f-mono)!important;letter-spacing:0!important;background:var(--vred);color:var(--vellum)!important;border-radius:9px;padding:1px 6px}.tfb b:empty{display:none}
.tfp{border:1px solid var(--vrule);border-radius:6px;background:#fbf5e6;padding:8px 10px;margin:0 0 8px;max-height:56%;overflow:auto;flex:none}.tfp[hidden]{display:none}
.tfg{margin:0 0 8px}.tfg>span{display:block;font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vmuted);margin:0 0 3px}.tfg>div,.tfa{display:flex;flex-wrap:wrap;gap:4px}.tfa:not(:empty){margin:0 0 6px}
.tfc{display:inline-flex;align-items:center;font:500 12px/1.2 var(--f-body);color:var(--vink);background:rgba(255,255,255,.6);border:1px solid var(--vline);border-radius:999px;padding:4px 9px;cursor:pointer}.tfc .ki{color:var(--kc);margin-right:4px}.tfc.pc{border:2px solid var(--c)}
.tfc:hover{border-color:var(--vink)}.tfc.on{background:var(--vink);color:var(--vellum);border-color:var(--vink)}.tfc.on .ki{color:inherit}.tfc.pc.on{background:var(--c);color:#1b1410;border-color:#1b1410}
.tfg>span{display:flex!important;justify-content:space-between;align-items:center}
.tfc.not{border-style:dashed;border-color:var(--vred)!important;color:var(--vred);background:none;text-decoration:line-through}.tfc.not .ki{color:inherit}.jo{font:500 10.5px var(--f-mono);font-style:normal;text-transform:uppercase;color:var(--vred);align-self:center}
.oa{display:inline-flex;border:1px solid var(--vline);border-radius:4px;overflow:hidden}.oa button{border:0;background:none;font:600 10px/1 var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--vmuted);padding:5px 8px;cursor:pointer}.oa button[aria-pressed=true]{background:var(--vink);color:var(--vellum)}
.tfe{display:flex;gap:6px;justify-content:flex-end;align-items:center;border-top:1px solid var(--vline);padding-top:8px}.btw{display:inline-flex;align-items:center;gap:6px;margin-right:auto;font:500 10px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--vmuted)}
.ti .k{font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--kc,var(--vmuted))}.tlist h4 .ki{color:var(--kc)}
.any{border-top:1px dashed rgba(42,29,18,.35);padding-top:5px;pointer-events:auto;cursor:default}.anyh{border:0;background:none;padding:2px 0;cursor:pointer;font:500 10.5px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:#3f5a3c}.anyh small{opacity:.8}.anyl[hidden]{display:none}
.any .tr{background:#fbf5e6;border:1px solid var(--vline);border-left:4px solid var(--kc,var(--vmuted));margin-top:4px;padding:4px 8px 4px 4px;cursor:grab;font-size:14px}.any .tr:hover{background:#fff}.any .tr .mk,.anyz .tr .mk{border-left:0;padding-left:0}
.any .outs,.anyz .outs{margin:0 0 2px 24px;font-size:13px}
.bn.scene.anyhot .sh::after{content:"Drop here: any time in this scene";display:block;border:1.5px dashed var(--vred);border-radius:4px;color:var(--vred);font:500 11px var(--f-mono);padding:6px;text-align:center;background:#fbf5e6}
.anyz{border:1px dashed #7f977b;border-radius:6px;padding:4px 6px 6px;margin:0 0 8px;background:rgba(77,107,74,.06)}.anyz.none{display:none}.rc.near .anyz.none{display:block}.anyt{font:500 10.5px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:#3f5a3c;padding:1px 2px}
.anyz .tr{border-left:4px solid var(--kc,var(--vmuted));margin-top:3px}
.bn.scene.floaty{border-style:dotted;border-color:#3d5a80}.bn.scene.floaty .sh{border-left-color:#3d5a80;border-left-style:double}.rc.floaty{border-left:5px double #3d5a80;border-style:dashed;border-left-style:double;margin-left:26px;max-width:734px}.rc.floaty .rn{color:#3d5a80;padding-top:2px}.ord.fl{background:#3d5a80}
.lim{font-size:13.5px}.lim b{font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:#3d5a80;margin-right:6px}.badl{color:var(--vred);font-style:normal}
.addo{border:1px dashed var(--vline);background:none;border-radius:4px;font:500 11px var(--f-mono);color:var(--vred);padding:2px 7px;cursor:pointer}.addo:hover{background:#fff}
.toast button{margin-left:14px;border:1px solid var(--vellum);background:none;color:inherit;border-radius:4px;font:600 12px var(--f-mono);padding:5px 10px;cursor:pointer}
.tlist{overflow:auto;min-height:0;flex:1}
.tlist h4{margin:10px 0 4px;font:600 11px var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted)}
.ti{display:flex;gap:8px;align-items:flex-start;padding:8px;margin:0 0 6px;border:1px solid var(--vline);border-left:4px solid var(--vmuted);border-radius:5px;background:#fbf5e6;cursor:grab;touch-action:pan-y;user-select:none;-webkit-user-select:none}
.ti>div{min-width:0}
.ti .g{flex:none;width:18px;color:var(--vmuted);font-size:16px;line-height:1.1;touch-action:none;cursor:grab}
.ti .t{font-weight:600;font-size:14.5px;line-height:1.25}.ti .s{font-size:12.5px;color:var(--vmuted);line-height:1.3}
.tlist .gone{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:13.5px;color:var(--vmuted);padding:4px 2px;border-bottom:1px dashed var(--vline)}
.tlist .gone s{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.empty{color:var(--vmuted);font-style:italic;font-size:14px}
.ghost{position:fixed;z-index:50;pointer-events:none;width:220px;opacity:.92;transform:rotate(-2deg)}
.acts{display:flex;gap:8px;flex-wrap:wrap}.acts button{font:500 11px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;border:1px solid var(--vink);border-radius:4px;padding:9px 11px;color:var(--vink);background:none;cursor:pointer}
.work[hidden],.runw[hidden]{display:none}
.runw{display:grid;grid-template-columns:1fr 300px;gap:12px;height:calc(100vh - 300px);min-height:480px}
.run{flex:1;min-height:0;overflow:auto;border:1px solid var(--vrule);border-radius:0 8px 8px 8px;background:#f6eed8;padding:14px clamp(10px,2vw,22px) 40px}
.runh{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:6px 14px;margin:0 0 10px;font-size:14.5px;color:var(--vmuted)}
.runh b{font:600 12px var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:#3f5a3c}
.rc{display:grid;grid-template-columns:20px 30px 1fr auto;gap:2px 10px;align-items:start;max-width:760px;margin:0 0 8px;padding:8px 10px 8px 6px;
  background:#fbf5e6;border:1px solid var(--vline);border-left:5px solid #4d6b4a;border-radius:6px;box-shadow:0 1px 4px rgba(42,29,18,.1);user-select:none;-webkit-user-select:none}
.rc.drag{position:relative;z-index:5;box-shadow:0 10px 24px rgba(42,29,18,.3);opacity:.95}
.rc .rg{color:var(--vmuted);font-size:17px;line-height:1.3;cursor:grab;touch-action:none;text-align:center}
.rc .rn{font:600 19px/1.1 var(--f-display);color:#3f5a3c;text-align:center}
.rc .rb{min-width:0;cursor:grab}
.rc .rt{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px}.rc .rt b{font-weight:600;font-size:15.5px;line-height:1.25}
.rc .rw{font-size:13px;color:var(--vmuted);margin-top:1px}
.pcs{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin-top:5px}.pcs .none{margin:0 4px 0 0}
.pcx{font:700 10.5px/1.55 var(--f-mono);letter-spacing:.06em;text-transform:uppercase;padding:0 7px;border-radius:4px;border:2px solid var(--c);color:#1b1410;background:color-mix(in srgb,var(--c) 18%,#fbf5e6);white-space:nowrap}
.pcx.in{background:var(--c)}.pcx.off{border-style:dashed;background:none;opacity:.85}.pcx.plus{--c:#9a8c74;border-style:dashed;background:none;color:var(--vmuted)}.pcx.plus.on{border-style:solid;background:var(--vink);color:var(--vellum)}.pcs .none{font-size:13px;font-style:italic;color:var(--vmuted)}
.addsc{display:block;width:100%;max-width:760px;margin:4px 0 0;padding:12px;border:1.5px dashed #7f977b;border-radius:6px;background:none;color:#3f5a3c;font:600 13px var(--f-display);letter-spacing:.06em;cursor:pointer}.addsc:hover{background:#e7efe3}
.ot{padding:3px 6px;font-size:13.5px;color:var(--vmuted)}.ot .el{color:var(--vred)}.ot .el::after{content:" →"}.ot small{font-size:12px}button.pcx{cursor:pointer}button.pcx:hover{outline:2px solid var(--vink);outline-offset:1px}
.pcx.all{border:2px solid #1b1410;background:var(--all) padding-box;letter-spacing:.12em;padding:0 10px}.pcx.all.off{border:2px dashed #7c6033;background:none}.pcx.who button{color:#1b1410}
.chips .none{font-size:13px;font-style:italic;color:var(--vmuted)}
.rc .rx{font:600 11px var(--f-mono);letter-spacing:.06em;border:1px solid var(--vline);background:rgba(255,255,255,.5);color:var(--vink);border-radius:4px;padding:6px 8px;cursor:pointer;white-space:nowrap}
.rc .rx[aria-expanded=true]{background:var(--vink);color:var(--vellum)}
.rc .rm{grid-column:3/5;border-top:1px dashed var(--vline);margin-top:6px;padding-top:6px;font-size:14px}
.rc .rm p{margin:0 0 6px}
#meas{position:absolute;left:-9999px;top:0;width:900px;visibility:hidden}
.tree{list-style:none;margin:0;padding:0}.rm>.tree{margin-bottom:6px}
.tree .tree{margin-left:13px;padding-left:15px;border-left:1.5px solid rgba(42,29,18,.28)}
.tree li{position:relative}.tree .tree>li::before{content:"";position:absolute;left:-15px;top:15px;width:11px;border-top:1.5px solid rgba(42,29,18,.28)}
.tree .tree>li:last-child::after{content:"";position:absolute;left:-17px;top:17px;bottom:0;width:4px;background:#fbf5e6}
.tr{display:flex;align-items:baseline;gap:8px;padding:5px 6px 5px 2px;border-radius:4px;cursor:pointer;position:relative}
.tr:hover{background:rgba(124,22,34,.07)}.tr.on,.li.on{box-shadow:0 0 0 2px rgba(124,22,34,.35)}
.tr .rg,.li .rg{flex:none;width:16px;color:var(--vmuted);font-size:15px;line-height:1.1;cursor:grab;touch-action:none;text-align:center}
.tr .tt{min-width:0;flex:1}.tr .el{color:var(--vred);font-size:13px}.tr .el::after{content:" →"}.tr .rng{align-self:center}
.tr small{color:var(--vmuted);font-size:12px}
.tr.in-on{background:rgba(124,22,34,.16);box-shadow:inset 0 0 0 2px var(--vred)}
.tr.in-before::before,.tr.in-after::before,.rc.in-before::before{content:"";position:absolute;left:0;right:0;height:3px;border-radius:2px;background:var(--vred);top:-2px}
.tr.in-after::before{top:auto;bottom:-2px}.rc.in-before{position:relative}.rc.in-before::before{top:-7px}
.rc.hot{border-color:var(--vred);box-shadow:0 0 0 2px rgba(124,22,34,.35)}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:60;max-width:min(560px,calc(100vw - 32px));background:var(--vink);color:var(--vellum);border-radius:8px;padding:12px 16px;font-size:15px;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.bn.flash,.bn.scene.flash{outline:3px solid var(--vred);outline-offset:4px}
.mk{flex:none;min-width:74px;font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vmuted);border-left:4px solid var(--vmuted);padding-left:6px}
.mk.k-decision{border-left-color:var(--vred);color:var(--vred)}.mk.k-pressure{border-left-color:#b8860b;color:#7a5a08}.mk.k-clock{border-left-color:#3d5a80;color:#3d5a80}
.mk.k-reveal{border-left-color:#6a4a8a;color:#6a4a8a}.mk.k-complication{border-left-color:#b5561c;color:#b5561c}.mk.k-entrance{border-left-color:#2f7d76;color:#2f7d76}.mk.k-exit{border-left-color:var(--vink);color:var(--vink);font-weight:700}
.mk.k-bottleneck{border-left:4px double var(--vink);color:var(--vink)}.mk.k-note{border-left-color:#c9a400}
.rc .rm .acts{margin-top:6px}
#loosez h4{margin:8px 0 4px}
@media (max-width:900px){.runw{grid-template-columns:minmax(0,1fr);grid-template-rows:1fr 30vh;height:calc(100vh - 170px)}}
@media (max-width:900px){.work{grid-template-columns:minmax(0,1fr);grid-template-rows:1fr 34vh;height:calc(100vh - 170px)}}
@media print{.pal,.bar,.tray,.drawer,.float,.rg,.rx{display:none}.runw{display:block;height:auto}.run{overflow:visible}.work{display:block;height:auto}}
"""

JS = r"""(() => {
const D = PATHS, P = D.plans, F = D.facts, GONE = new Set(D.gone), CUR = D.cur;
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
const RELAY = (location.hostname === "localhost" && new URLSearchParams(location.search).get("relay"))
  || "https://2srnsytz3rqi3jke23bz643jhq0irvei.lambda-url.ca-central-1.on.aws";
const KEY = store.get("osse-hub-dm");
/*LINK*/
const GRID = 22, CARDW = 250, SX = 44, SY = 44, FIRSTX = 418, TABW = 4000, SCW = 572, SCH = 396;
const snap = v => Math.round(v / GRID) * GRID;
const KINDS = {scene: "Scene", beat: "Beat", reveal: "Reveal", complication: "Complication", decision: "Decision", entrance: "Entrance", exit: "Exit", clock: "Clock", pressure: "Pressure", bottleneck: "Bottleneck", note: "Note"};
const PLANKINDS = Object.keys(KINDS).filter(k => k !== "note");
const INSCENE = ["beat", "reveal", "complication", "decision", "entrance", "exit"];   // the cards a scene is made of; each has a cue
const FIELDS = {where: ["scene"], when: ["scene"], present: ["scene"], purpose: ["scene"], cue: INSCENE, who: INSCENE, reveals: ["reveal"], critical: ["decision"], clock: ["clock"]};   // what each kind adds
const KDESC = {scene: "The situation (where, when, who is there, what is going on) and its purpose. A box on the board; the cards inside it happen during the scene.",
  beat: "A turn that could happen in a scene: one moment, set off by its cue.",
  reveal: "A beat where something comes out. Name the secret when the vault holds it.",
  complication: "A beat that turns the scene against what someone wants.",
  entrance: "Someone comes in, and the scene changes.",
  exit: "A way the scene can end, and where that leads: link it to the next scene. Or someone leaving: say who.",
  clock: "Time pressure: something happens when its segments fill. Tap the clock on the card to fill a segment.",
  decision: "A choice the character faces. Its panel lists the options: each is a choice and its outcome, which is a card or only words. A link you draw out of it is an option too. Two choices can lead to the same card.",
  pressure: "What the world does if no one acts: a portent that fires when they stall.",
  bottleneck: "A beat most paths reach, where branches meet again.",
  note: "A loose idea. Claude turns it into a plan when you ask."};
const ICON = {float: '<path d="M2 10h16M5.2 6.4 1.8 10l3.4 3.6M14.8 6.4l3.4 3.6-3.4 3.6" stroke-linejoin="round"/>', filter: '<path d="M2 4h16l-6.2 7v5.5l-3.6-2V11z" stroke-linejoin="round"/>', list: '<path d="M7 4h10M7 10h10M7 16h10" /><path d="M3 4h.01M3 10h.01M3 16h.01" stroke-width="3" stroke-linecap="round"/>', map: '<rect x="2" y="3" width="6" height="5"/><rect x="12" y="3" width="6" height="5"/><rect x="12" y="12" width="6" height="5"/><path d="M8 5.5h4M15 8v4"/>',
  globe: '<circle cx="10" cy="10" r="7.5"/><path d="M2.5 10h15M10 2.5c5 5 5 10 0 15M10 2.5c-5 5-5 10 0 15"/>',
  scene: '<rect x="2.5" y="4" width="15" height="12.5" rx="1"/><path d="M2.5 8.2h15M6 4l-1.6 4.2M10.6 4 9 8.2M15.2 4l-1.6 4.2"/>',
  beat: '<path d="M1.5 10.5H6l2.2-6 3.6 11 2.2-5h4.5" stroke-linejoin="round"/>',
  reveal: '<path d="M1.5 10S4.8 4.5 10 4.5 18.5 10 18.5 10 15.2 15.5 10 15.5 1.5 10 1.5 10z"/><circle cx="10" cy="10" r="2.4"/>',
  complication: '<path d="M11.5 1.8 4 11.4h5L8 18.2l8-10h-5.2z" stroke-linejoin="round"/>',
  decision: '<path d="M10 18.5V12M10 12 4 6.5V3M10 12l6-5.5V3M1.8 5 4 2.6 6.2 5M13.8 5 16 2.6 18.2 5" stroke-linejoin="round"/>',
  entrance: '<path d="M10 3h7v14h-7M1.5 10H12M8 6l4 4-4 4" stroke-linejoin="round"/>',
  exit: '<path d="M10 3H3v14h7M8 10h10.5M14.5 6l4 4-4 4" stroke-linejoin="round"/>',
  pressure: '<path d="M3 15.5a8 8 0 1 1 14 0M10 11.5l3.6-4.4"/><circle cx="10" cy="12" r="1.3"/>',
  clock: '<circle cx="10" cy="10" r="7.5"/><path d="M10 5.2V10l3.2 2.2"/>',
  bottleneck: '<path d="M3 3h14l-5.4 7L17 17H3l5.4-7z" stroke-linejoin="round"/>',
  note: '<path d="M3 3h14v9l-5 5H3zM12 17v-5h5" stroke-linejoin="round"/>'};
const icon = (n, sz = 15) => `<svg viewBox="0 0 20 20" width="${sz}" height="${sz}" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">${ICON[n]}</svg>`;
const kic = k => ICON[k] ? icon(k, 13).replace("<svg", '<svg class="ki"') : "";   // a card type's symbol
let doc = {sessions: [], items: {}, cards: {}, edits: {}, edges: [], order: {}, seeded: []};
let lane = null, view = {x: 0, y: 0, k: 1}, views = {}, hs = {}, hsh = {};
const tabOf = {};   // board -> open session tab

/* ---------- state: one copy of everything, shown on as many boards as it belongs to ----------
   items[id]: s (session), homes (boards it was put on), at {board: {x,y}}, w and h (a scene's size),
   scene with rx, ry (a card inside a scene: its place in the box, the same on every board) */
const sessNum = s => +(String(s).match(/^S(\d+)$/i) || [])[1] || 0;
function defaults() { return [1, 2, 3].map(i => "S" + (CUR + i)).concat("Later"); }
const WHOLE = "The Party";   // the session canvas: everything in the session, whoever it is for. As a home it means the whole party
const L = () => doc;
const it = id => doc.items[id];
const live = id => !!it(id) && (id.startsWith("p:") ? !!P[id.slice(2)] : !!doc.cards[id.slice(2)]);   // a played or dropped plan stays stored, unseen
const T = () => { if (runMode) return runTab; if (!doc.sessions.includes(tabOf[lane])) tabOf[lane] = doc.sessions[0]; return tabOf[lane]; };
const view_of = id => { const p = P[id], e = doc.edits[id] || {}; return {...p, summary: e.summary ?? p.summary, kind: e.kind ?? p.kind, ideaText: e.idea ?? p.ideaText,
  ...Object.fromEntries(Object.keys(FIELDS).map(f => [f, e[f] ?? p[f]])), options: e.options ?? p.options, edited: Object.keys(e).some(k => k !== "drop")}; };
const objOf = id => id.startsWith("p:") ? (P[id.slice(2)] ? view_of(id.slice(2)) : null) : doc.cards[id.slice(2)] || null;
const kindOf = id => (objOf(id) || {}).kind || "";
const isScene = id => kindOf(id) === "scene";
const sceneOf = id => { const sc = (it(id) || {}).scene; return sc && live(sc) && isScene(sc) && !isScene(id) ? sc : null; };
const sessOf = id => it(id) ? it(sceneOf(id) || id).s : null;
const membersOf = sid => Object.keys(doc.items).filter(i => live(i) && sceneOf(i) === sid);
const isAny = id => !!(it(id) || {}).any && !!sceneOf(id);   // in the scene's Any time section: it follows no other card there
const anyOf = sid => membersOf(sid).filter(isAny).sort((a, b) => it(a).any - it(b).any);
const flowOf = sid => membersOf(sid).filter(m => !isAny(m));   // the cards on the scene's own canvas
const ah = {}, rowAt = {};   // the height of a scene's Any time section (its cards sit under it), and a row's place in its scene
const headOf = sid => (hsh[sid] || 96) - (ah[sid] || 0);
const isFloat = id => !!(it(id) || {}).float;   // a scene with no fixed place in the running order
const fieldOf = (o, f) => FIELDS[f].includes(o.kind || "beat") ? o[f] : undefined;   // a value left over from another kind does not count
function lanesNamed(list) {
  const out = new Set();
  list.forEach(n => { const p = pcOf(n);
    if (p === "party") D.lanes.forEach(l => { if (l.kind !== "world") out.add(l.key); }); else if (p) out.add(p); });
  return [...out];
}
const presentLanes = id => lanesNamed((objOf(id) || {}).present || []);   // there when the scene opens
const comers = id => membersOf(id).filter(m => kindOf(m) === "entrance").flatMap(m => objOf(m).who || []);
const castLanes = id => lanesNamed([...((objOf(id) || {}).present || []), ...comers(id)]);   // the boards of the player characters in a scene, from the start or by an entrance
const charsOn = m => { const w = fieldOf(objOf(m), "who") || []; return lanesNamed(w.length ? w : m.startsWith("p:") ? P[m.slice(2)].lanes : []); };   // the characters on a card: who it names, or the boards a plan is tied to
const cardLanes = id => [...new Set(membersOf(id).flatMap(charsOn))];
function lanesOf(id) {   // the boards an item shows on
  const sc = sceneOf(id); if (sc) return lanesOf(sc);
  const o = it(id), ks = isScene(id) ? [...new Set([...o.homes, ...castLanes(id), ...cardLanes(id)])] : o.homes;
  return ks.length ? ks : [o.born || D.lanes[0].key];
}
const onBoard = (id, k = lane) => k === WHOLE || lanesOf(id).includes(k);
const boardsOf = id => [...new Set([...lanesOf(id), WHOLE])];
const mineHome = () => runMode || lane === WHOLE ? undefined : lane;   // the board a card taken out of a scene stays on
const inTab = (t, k = lane) => Object.keys(doc.items).filter(i => live(i) && sessOf(i) === t && onBoard(i, k));
function measure(ids) {   // card heights, off screen: needed for boards not drawn yet
  const m = $("#meas"); m.innerHTML = ids.map(cardHtml).join("");
  m.querySelectorAll(".bn").forEach(noteSize);
  m.innerHTML = "";
}
function noteSize(el) {
  const id = el.dataset.id, h = el.querySelector(".sh"); hs[id] = el.offsetHeight; if (!h) return;
  const a = h.querySelector(".any"); hsh[id] = h.offsetHeight; ah[id] = a ? a.offsetHeight + 4 : 0;
  if (a) a.querySelectorAll("[data-card]").forEach(r => { rowAt[r.dataset.card] = {y: r.offsetTop, h: r.offsetHeight}; });
}
function box(id, k = lane) {
  if (id === "start") return {x: SX, y: SY, w: 300, h: hs.start || 200};
  if (!live(id)) return null;
  const o = it(id), sc = sceneOf(id);
  if (sc) {
    const b = box(sc, k); if (!b) return null;
    if (o.any) { const r = rowAt[id], up = r && r.h && !it(sc).anyx; return {x: b.x + 14, y: b.y + (up ? r.y : b.hh - 30), w: b.w - 28, h: up ? r.h : 24}; }
    return {x: b.x + (o.rx ?? 22), y: b.y + (o.ry ?? 132) + (ah[sc] || 0), w: CARDW, h: hs[id] || 110};
  }
  const a = (o.at ||= {})[k]; if (!a) return null;
  return isScene(id) ? {x: a.x, y: a.y, w: o.w || SCW, h: (o.h || SCH) + (ah[id] || 0), hh: hsh[id] || 96, sc: 1} : {x: a.x, y: a.y, w: CARDW, h: hs[id] || 110};
}
function freeSpot(t, k = lane) {
  const bs = inTab(t, k).map(i => box(i, k)).filter(b => b && b.x < FIRSTX + CARDW && b.x + b.w > FIRSTX);
  return {x: FIRSTX, y: bs.length ? snap(Math.max(...bs.map(b => b.y + b.h)) + 44) : SY};
}
function ensureAt(t, k = lane) {   // everything that belongs on board k has a place there
  const ids = inTab(t, k), miss = ids.filter(i => hs[i] === undefined);
  if (miss.length) withLane(k, () => measure(miss));
  if (k === WHOLE) { lineUp(t, ids.filter(i => !sceneOf(i) && !(it(i).at ||= {})[k]), k); return; }
  ids.filter(i => !sceneOf(i) && !(it(i).at ||= {})[k]).sort((a, b) => isScene(b) - isScene(a)).forEach(i => { it(i).at[k] = freeSpot(t, k); });
}
function lineUp(t, ids, k) {   // scenes left to right in running order, the floating ones underneath where they would come, then what is in no scene, a column per board
  if (!ids.length) return;
  const put = new Set(ids), all = inTab(t, k).filter(i => !sceneOf(i)), at = i => it(i).at[k], bx = i => box(i, k);
  const order = scenesIn(t).filter(i => all.includes(i)), right = b => snap(b.x + b.w) + 88;
  let x = FIRSTX; all.filter(i => !put.has(i) && isScene(i) && !isFloat(i)).forEach(i => { x = Math.max(x, right(bx(i))); });
  order.filter(i => put.has(i) && !isFloat(i)).forEach(i => { it(i).at[k] = {x, y: SY}; x = right(bx(i)); });
  const low = list => list.length ? snap(Math.max(...list.map(b => b.y + b.h))) + 88 : SY;
  const y1 = low(order.filter(i => !isFloat(i) && at(i)).map(bx)); let fx = FIRSTX;
  order.filter(i => put.has(i) && isFloat(i)).forEach(i => {
    const next = order.slice(order.indexOf(i)).find(o => !isFloat(o) && at(o)), busy = order.filter(o => o !== i && isFloat(o) && at(o)).map(bx);
    fx = Math.max(fx, next ? bx(next).x : x);
    for (let b; (b = busy.find(q => q.x < fx + (it(i).w || SCW) + 44 && q.x + q.w + 44 > fx && q.y + q.h > y1)); ) fx = right(b);
    it(i).at[k] = {x: fx, y: y1}; fx = right(bx(i));
  });
  const y0 = low(all.filter(i => isScene(i) && at(i)).map(bx)), col = i => k === WHOLE ? lanesOf(i)[0] : k;
  const cols = D.lanes.map(l => l.key).filter(c => all.some(i => !isScene(i) && col(i) === c));
  ids.filter(i => !isScene(i)).forEach(i => {
    const cx = FIRSTX + Math.max(0, cols.indexOf(col(i))) * (CARDW + 44), under = all.filter(o => o !== i && !isScene(o) && at(o)).map(bx).filter(b => b.y >= y0 - 1 && b.x < cx + CARDW && b.x + b.w > cx);
    it(i).at[k] = {x: cx, y: under.length ? snap(Math.max(...under.map(b => b.y + b.h))) + 22 : y0};
  });
}
function layScene(sid, list, tr) {   // a scene's cards as a tree: down the page in order, each one to the right of the card that leads to it
  const COL = CARDW + 148, o = it(sid), ow = o.w || SCW, oh = o.h || SCH; let w = 0;   // room between columns for the choices
  const put = (m, d, y) => {
    const x = it(m); x.rx = 22 + d * COL; x.ry = snap(y + 10); w = Math.max(w, x.rx + CARDW);
    return Math.max(x.ry + (hs[m] || 110) + 22, (tr.kids[m] || []).reduce((yy, k) => put(k, d + 1, yy), x.ry));
  };
  const bottom = (tr.kids[""] || []).reduce((yy, m) => put(m, 0, yy), headOf(sid) + 22);
  o.w = Math.max(SCW, snap(w + 32)); o.h = Math.max(264, snap(bottom + 10)); if (!list.length) o.h = Math.max(snap(headOf(sid) + 88), 198);
  makeRoom(sid, ow, oh);
}
function tidy(t, k) {   // Line up: each scene's cards by their arrows, the scenes in running order, linked cards by their arrows; the rest as before
  const ids = inTab(t, k), top = ids.filter(i => !sceneOf(i)), scs = top.filter(isScene), was = copyOf(doc.items);
  withLane(k, () => measure(ids));
  scs.forEach(s => { const tr = treeOf(s); layScene(s, tr.ms, tr); });
  const es = genEdges().filter(e => ids.includes(e.to) && (e.from.startsWith("start") || live(e.from)) || ids.includes(e.from));
  const loose = top.filter(i => !isScene(i)), tied = loose.filter(i => es.some(e => e.from === i || e.to === i)), pos = i => (it(i).at || {})[k] || {x: 0, y: 0};
  tied.sort((a, b) => pos(a).y - pos(b).y || pos(a).x - pos(b).x);
  const par = {}, kids = {};
  tied.forEach(m => { const e = es.find(e => { if (e.to !== m || !tied.includes(e.from) || e.from === m) return false; for (let x = e.from; x; x = par[x]) if (x === m) return false; return true; }); if (e) { par[m] = e.from; (kids[e.from] ||= []).push(m); } });
  const under = m => [m, ...(kids[m] || []).flatMap(under)];
  top.forEach(i => { delete (it(i).at ||= {})[k]; });
  lineUp(t, scs, k);
  const bx = i => box(i, k), y0 = scs.length ? snap(Math.max(...scs.map(i => bx(i).y + bx(i).h))) + 88 : SY, set = [], COL = CARDW + 148;
  tied.filter(m => !par[m]).forEach(root => {
    const all = under(root), e = es.find(e => (all.includes(e.to) && !tied.includes(e.from) && live(e.from)) || (all.includes(e.from) && !tied.includes(e.to))), end = e && (all.includes(e.to) ? e.from : e.to), sc = end && (isScene(end) ? end : sceneOf(end));
    const x0 = sc && scs.includes(sc) ? bx(sc).x : FIRSTX, deep = (m, d) => Math.max(d, ...(kids[m] || []).map(c => deep(c, d + 1))), x1 = x0 + deep(root, 0) * COL + CARDW;
    const y = Math.max(y0, ...set.filter(b => b.x < x1 + 44 && b.x1 + 44 > x0).map(b => b.y1 + 44));
    const put = (m, d, yy) => { it(m).at[k] = {x: x0 + d * COL, y: snap(yy + 10)}; return Math.max(snap(yy + 10) + (hs[m] || 110) + 22, (kids[m] || []).reduce((z, c) => put(c, d + 1, z), yy)); };
    set.push({x: x0, x1, y1: put(root, 0, y)});
  });
  lineUp(t, loose.filter(i => !tied.includes(i)), k);
  changed(); draw(); fit();
  const after = copyOf(doc.items), keys = ["at", "rx", "ry", "w", "h"];
  toast("Lined up.", "Undo", () => {
    for (const i in was) if (it(i) && after[i] && sceneOf(i) === (after[i].scene || null)) keys.forEach(f => { if (f in was[i]) it(i)[f] = was[i][f]; else delete it(i)[f]; });
    changed(); draw(); fit();
  });
}
function setPos(id, x, y) {
  const o = it(id), sc = sceneOf(id);
  if (sc) { const b = box(sc); o.rx = x - b.x; o.ry = y - b.y - (ah[sc] || 0); } else (o.at ||= {})[lane] = {x, y};
}
function sceneAt(id) {   // the smallest scene box on this board holding the card's top middle
  const b = box(id); if (!b || isScene(id)) return null;
  const px = b.x + b.w / 2, py = b.y + Math.min(b.h / 2, 40);
  return inTab(sessOf(id)).filter(isScene).map(x => [x, box(x)]).filter(([, r]) => r && px > r.x && px < r.x + r.w && py > r.y + 20 && py < r.y + r.h)
    .sort((a, c) => a[1].w * a[1].h - c[1].w * c[1].h).map(x => x[0])[0] || null;
}
function join(id, sid, rx, ry) { const o = it(id); o.scene = sid; o.rx = rx; o.ry = ry; o.at = {}; o.s = it(sid).s; delete o.any; }
function release(id, k) {   // out of its scene: it stays on its own boards, and on board k where it was taken out, where it stood
  const o = it(id), so = it(o.scene), hs0 = o.homes.length ? o.homes : [o.born || D.lanes[0].key];
  o.homes = [...new Set([...hs0, ...(k ? [k] : [])])]; o.at = {};
  if (so) { o.s = so.s; [...new Set([...o.homes, WHOLE])].forEach(ln => { const a = (so.at || {})[ln]; if (a) o.at[ln] = {x: a.x + (o.rx || 0), y: a.y + (o.ry || 0) + (ah[o.scene] || 0)}; }); }
  delete o.scene; delete o.rx; delete o.ry; delete o.any;
}
function capture(sid) {   // after a scene is moved or resized on this board: what it encloses is in it, what it leaves out is not
  const sb = box(sid);
  inTab(sessOf(sid)).filter(i => !isScene(i) && !isAny(i)).forEach(i => {
    const at = sceneAt(i);
    if (sceneOf(i) === sid && at !== sid) { const b = box(i), inside = b.x + b.w / 2 > sb.x && b.x + b.w / 2 < sb.x + sb.w && b.y + 20 > sb.y && b.y + 20 < sb.y + sb.h; if (!inside) release(i, mineHome()); }
    else if (!sceneOf(i) && at === sid) { const b = box(i); join(i, sid, b.x - sb.x, Math.max(headOf(sid) + 8, b.y - sb.y - (ah[sid] || 0))); }
  });
}
function growScene(sid, w, h, except) {   // a scene got bigger: make room around it on every board it is on
  const o = it(sid), ow = o.w || SCW, oh = o.h || SCH; o.w = Math.max(ow, snap(w + 10)); o.h = Math.max(oh, snap(h + 10));
  makeRoom(sid, ow, oh, except);
}
function makeRoom(sid, ow, oh, except) {
  const o = it(sid), dw = o.w - ow, dh = o.h - oh, more = ah[sid] || 0; if (dw <= 0 && dh <= 0) return;
  boardsOf(sid).filter(k => k !== except && (o.at || {})[k]).forEach(k => {
    const a = o.at[k];
    inTab(o.s, k).filter(i => i !== sid && !sceneOf(i) && (it(i).at || {})[k]).forEach(i => {
      const b = box(i, k), p = it(i).at[k];
      if (dh > 0 && b.y >= a.y + oh + more - 1 && b.x < a.x + o.w && b.x + b.w > a.x) p.y += dh;
      else if (dw > 0 && b.x >= a.x + ow - 1 && b.y < a.y + o.h + more && b.y + b.h > a.y) p.x += dw;
    });
  });
}
/* a scene's Any time section: cards that can come at any point in it, on their cue */
function roomFor(sid, fn) {   // the section changes size: what stands under the scene makes way
  const h0 = ah[sid] || 0, o = it(sid); fn(); measure([sid]);
  if ((ah[sid] || 0) <= h0) return;
  boardsOf(sid).forEach(k => {
    const a = (o.at || {})[k]; if (!a) return;
    const was = a.y + (o.h || SCH) + h0, now = a.y + (o.h || SCH) + ah[sid];
    const below = inTab(o.s, k).filter(i => i !== sid && !sceneOf(i) && (it(i).at || {})[k] && (b => b.y >= was - 1 && b.x < a.x + (o.w || SCW) && b.x + b.w > a.x)(box(i, k)));
    const need = below.length ? now + 22 - Math.min(...below.map(i => it(i).at[k].y)) : 0;
    if (need > 0) below.forEach(i => { it(i).at[k].y += Math.ceil(need / GRID) * GRID; });
  });
}
function toAny(id, sid, before) {   // into the section, in front of another row or last
  if (isScene(id) || before === id) return;
  if (!it(id)) putPlan(id, sessOf(sid));
  const from = sceneOf(id), gone = [], was = copyOf(it(id)), dec = e => kindOf(e.from) === "decision";
  roomFor(sid, () => {
    if (from && from !== sid) release(id);
    const list = anyOf(sid).filter(x => x !== id), i = before ? list.indexOf(before) : -1; list.splice(i < 0 ? list.length : i, 0, id);
    join(id, sid, it(id).rx ?? 22, it(id).ry ?? headOf(sid) + 22); list.forEach((x, n) => { it(x).any = n + 1; }); delete it(sid).anyx;
    doc.edges = doc.edges.filter(e => { const cut = e.to === id && sceneOf(e.from) === sid && !dec(e); if (cut) gone.push(e); return !cut; });
  });
  changed(); draw(); if (shown === id) open(id);
  if (gone.length) toast(`“${titleOf(id)}” can come at any time now, so its arrow${gone.length > 1 ? "s" : ""} from “${[...new Set(gone.map(e => titleOf(e.from)))].join("” and “")}” came off.`, "Undo", () => {
    if (!it(id)) return; into(it(id), was); doc.edges.push(...gone.filter(e => live(e.from))); changed(); draw(); if (shown === id) open(id); });
}
function outOfAny(id) { const sid = sceneOf(id); delete it(id).any; const f = insideSpot(sid); join(id, sid, f.rx, f.ry); changed(); draw(); }
function seed(key) {   // a board's first look: the vault's plans aimed at a coming session
  const want = Object.values(P).filter(p => p.lanes.includes(key) && sessNum(p.target) > CUR), next = {};
  const tabFor = p => { const t = "S" + sessNum(p.target); if (!doc.sessions.includes(t)) { doc.sessions.push(t); sortSessions(); } return t; };
  const put = (p, extra) => { const id = "p:" + p.id, o = it(id);
    if (o) { if (!o.homes.includes(key)) o.homes.push(key); return o; }
    return doc.items[id] = {s: tabFor(p), homes: [key], born: key, at: {}, ...extra}; };
  want.filter(p => p.kind === "scene").forEach(p => {
    const inner = Object.values(P).filter(q => q.scene === p.id && q.target === p.target), was = it("p:" + p.id);
    put(p, {w: SCW, h: Math.max(SCH, 132 + inner.length * 176)});
    if (!was) inner.forEach((q, i) => { if (!it("p:" + q.id)) doc.items["p:" + q.id] = {s: tabFor(q), homes: [key], born: key, at: {}, scene: "p:" + p.id, rx: 22, ry: 132 + i * 176}; });
  });
  want.filter(p => p.kind !== "scene").forEach(p => { const o = it("p:" + p.id); if (!(o && o.scene)) put(p); });
  doc.seeded.push(key);
}
function sortSessions() { doc.sessions = [...new Set(doc.sessions)].sort((a, b) => (sessNum(a) || 1e9) - (sessNum(b) || 1e9)); if (!doc.sessions.includes("Later")) doc.sessions.push("Later"); }
const parseClock = c => { const m = String(c || "").match(/^\s*(\d+)\s*\/\s*(\d+)\s*$/); return m ? [Math.min(+m[1], +m[2]), +m[2]] : [0, 4]; };
function ring(f, n, sz) {
  const r = sz / 2 - 2, c = sz / 2, pt = a => `${(c + r * Math.cos(a)).toFixed(2)},${(c + r * Math.sin(a)).toFixed(2)}`;
  let h = `<svg viewBox="0 0 ${sz} ${sz}" width="${sz}" height="${sz}" aria-hidden="true">`;
  for (let i = 0; i < n; i++) {
    const a0 = i / n * 2 * Math.PI - Math.PI / 2, a1 = (i + 1) / n * 2 * Math.PI - Math.PI / 2;
    h += `<path d="M${c},${c} L${pt(a0)} A${r},${r} 0 0 1 ${pt(a1)} Z" class="${i < f ? "on" : ""}"/>`;
  }
  return h + "</svg>";
}
function extras(o, id) {   // what a scene or clock adds to its card
  let h = "";
  if (o.kind === "scene") h += `<div class="at">${o.where ? `<b>At</b>${esc(o.where)}` : "<i>Where? Set it in its panel.</i>"}${o.when ? ` · ${esc(o.when)}` : ""}</div>` +
    `<div class="chips">${whoTags(o.present, id && it(id) ? lanesOf(id) : [])}</div>` + (o.purpose ? `<div class="pur"><b>Purpose</b>${esc(o.purpose)}</div>` : "") + (id && isFloat(id) ? `<div class="lim"><b>Floating</b>${limText(id)}</div>` : "");
  if (fieldOf(o, "cue")) h += `<div class="cue"><b>Cue</b>${esc(o.cue)}</div>`;
  if ((fieldOf(o, "who") || []).length) h += `<div class="chips">${peopleTags(o.who)}</div>`;
  if (fieldOf(o, "reveals")) h += `<div class="chips"><span class="ch sec${secretOut(o.reveals) ? " out" : ""}" style="cursor:inherit">${secretOut(o.reveals) ? "already out" : "reveals"}: ${esc(o.reveals)}</span></div>`;
  if (o.kind === "clock") { const [f, n] = parseClock(o.clock);
    h += `<div class="clk"><button class="rng" data-tick title="Fill a segment (Shift-click empties one)" aria-label="Clock: ${f} of ${n}">${ring(f, n, 44)}</button><span>${f} of ${n} filled</span></div>`; }
  return h;
}

/* ---------- running order: every scene of a session, in running order ---------- */
const RUN = "@session", PCS = D.lanes.filter(l => l.kind === "pc");
let runMode = false, runTab = null;
const opened = new Set(), HOMELESS = (D.lanes.find(l => l.kind === "party") || D.lanes[0]).key;   // where a scene with no players waits
let casting = null;
const lc = x => String(x || "").trim().toLowerCase();
function pcOf(name) {   // a player character's key, "party", or null
  const n = lc(name);
  if (n === "the party" || n === "the whole party") return "party";
  const p = PCS.find(q => lc(q.key) === n || (q.aliases || []).some(a => lc(a) === n));
  return p ? p.key : null;
}
/* Who is in a scene, the same tag everywhere: each player character in their own colour, The Party (all four) in all four colours, anyone else plain. */
document.documentElement.style.setProperty("--all", `linear-gradient(90deg,${PCS.map((p, i) => `${p.colour} ${i * 100 / PCS.length}% ${(i + 1) * 100 / PCS.length}%`).join(",")})`);
const everyPc = ks => PCS.length > 1 && PCS.every(p => ks.includes(p.key)), PARTY = `${PCS.slice(0, -1).map(p => p.short).join(", ")} and ${(PCS[PCS.length - 1] || {}).short}`;
const allTag = `<span class="pcx all" title="${esc(PARTY)}">The Party</span>`;
const laneTag = l => l.kind === "party" ? allTag : `<span class="pcx in" style="--c:${esc(l.colour || "#9db4cf")}">${esc(l.short)}</span>`;
function laneTags(ks) {   // the boards something is on
  const all = everyPc(ks) || (ks.includes(WHOLE) && !ks.some(k => k !== WHOLE));
  return (all ? allTag : "") + D.lanes.filter(l => ks.includes(l.key) && l.kind !== "party" && !(all && l.kind === "pc")).map(laneTag).join("");
}
function whoTags(list, ks) {   // a scene's cast: players first, then everyone else
  const who = (list || []).map(pcOf), pcs = who.includes("party") ? PCS.map(p => p.key) : who.filter(Boolean), rest = (list || []).filter(x => !pcOf(x));
  return (pcs.length ? laneTags(pcs) : (ks || []).includes("world") ? laneTags(["world"]) : `<span class="none">No players yet</span>`) + rest.map(x => `<span class="ch who">${esc(x)}</span>`).join("");
}
const peopleTags = list => (list || []).map(x => `<span ${pickTag(x)}>${esc(x)}</span>`).join("");
const secretOut = s => !!D.secrets.find(x => x.n === s && x.out);
const isCrit = o => !!o && o.kind === "decision" && !!o.critical;
const kl = id => isCrit(objOf(id)) ? "Critical decision" : KINDS[kindOf(id)] || "Beat";   // what a card calls itself
function withLane(k, fn) { const keep = lane; lane = k; try { return fn(); } finally { lane = keep; } }
const shortOf = k => (D.lanes.find(l => l.key === k) || {}).short || k;
const boardName = k => k === WHOLE ? "the session canvas" : k === "world" ? "the World board" : shortOf(k) + "’s board";
const runSessions = () => doc.sessions.filter(t => t !== "Later");
const scenesIn = t => {
  const all = Object.keys(doc.items).filter(i => live(i) && isScene(i) && sessOf(i) === t), ord = (doc.order || {})[t] || [];
  return ord.filter(i => all.includes(i)).concat(all.filter(i => !ord.includes(i)));
};
const fixedIn = t => scenesIn(t).filter(i => !isFloat(i)), numIn = id => fixedIn(sessOf(id)).indexOf(id) + 1;   // floating scenes keep a spot in the list, with no number
const limits = id => Object.fromEntries(["after", "before"].map(k => [k, ((it(id) || {})[k] || []).filter(x => x !== id && live(x) && isScene(x) && sessOf(x) === sessOf(id))]));
const called = x => `${numIn(x) ? numIn(x) + ". " : ""}${titleOf(x)}`;
function fits(id, rest) {   // the places in the list it may take: [first, last], or null when its limits leave none
  const l = limits(id), lo = Math.max(0, ...l.after.map(a => rest.indexOf(a) + 1)), hi = l.before.length ? Math.min(...l.before.map(b => rest.indexOf(b))) : rest.length;
  return lo <= hi ? [lo, hi] : null;
}
const limText = id => { const l = limits(id), bits = ["after", "before"].filter(k => l[k].length).map(k => `${k} ${l[k].map(x => esc(called(x))).join(" and ")}`);
  return (bits.length ? bits.join(", ") : "any time in the session") + (fits(id, scenesIn(sessOf(id)).filter(x => x !== id)) ? "" : ` <i class="badl">These limits leave it no place: the first comes later than the second.</i>`); };
function heed(t) {   // floating scenes keep to their limits: one out of bounds moves to the nearest place that fits
  let ord = scenesIn(t); const moved = [];
  ord.filter(isFloat).forEach(id => { const rest = ord.filter(x => x !== id), i = ord.indexOf(id), f = fits(id, rest); if (!f) return;
    const j = Math.min(f[1], Math.max(f[0], i)); if (j !== i) { rest.splice(j, 0, id); ord = rest; moved.push(id); } });
  if (t !== "Later") doc.order[t] = ord;
  return moved;
}
function setFloat(id, on) { const o = it(id); if (on) o.float = 1; else { delete o.float; delete o.after; delete o.before; } heed(sessOf(id)); changed(); draw(); }
const looseIn = t => Object.keys(doc.items).filter(i => live(i) && !isScene(i) && !sceneOf(i) && sessOf(i) === t);
function runOrder() { const o = {}; runSessions().forEach(t => { const s = scenesIn(t); if (s.length) o[t] = s; }); return o; }
function pills(id) {   // the boards a scene is on: filled, listed as present; outlined, on their board only
  const cast = castLanes(id), ks = lanesOf(id), ed = casting === id, all = everyPc(cast), here = presentLanes(id), has = l => l.kind === "party" ? everyPc(here) : here.includes(l.key);
  if (ed) return D.lanes.filter(l => l.kind !== "world").map(l => `<button class="pcx${l.kind === "party" ? " all" : ""}${has(l) ? " in" : " off"}" aria-pressed="${has(l)}" style="--c:${esc(l.colour || "#b9ab95")}" data-cast="${esc(l.key)}" data-id="${esc(id)}">${has(l) ? "✓ " : "+ "}${esc(l.short)}</button>`).join("") +
    `<button class="pcx plus on" data-casting="${esc(id)}">Done</button>`;
  return (ks.some(k => k !== WHOLE) ? (all ? `<button class="pcx all" data-go="${WHOLE}" data-id="${esc(id)}" title="${esc(PARTY)}. Open this scene on the session canvas">The Party</button>` : "") + D.lanes.filter(l => l.kind !== "party" && !(all && l.kind === "pc") && ks.includes(l.key)).map(l => `<button class="pcx${cast.includes(l.key) ? " in" : ""}" style="--c:${esc(l.colour || "#b9ab95")}" data-go="${esc(l.key)}" data-id="${esc(id)}" ` +
    `title="${esc(cast.includes(l.key) || l.kind !== "pc" ? "" : "Not listed as present. " + (cardLanes(id).includes(l.key) ? "On a card in this scene. " : ""))}Open this scene on ${esc(boardName(l.key))}">${esc(l.short)}</button>`).join("") : `<span class="none">No players yet</span>`) +
    `<button class="pcx plus" data-casting="${esc(id)}" title="Add or remove players">+ Players</button>`;
}
function treeOf(sid) {   // a scene's cards under the cards that lead to them, by the arrows
  const pos = m => [it(m).ry || 0, it(m).rx || 0];
  const ms = flowOf(sid).sort((a, b) => pos(a)[0] - pos(b)[0] || pos(a)[1] - pos(b)[1]), inn = new Set(ms);
  const es = genEdges().filter(e => inn.has(e.to) && e.from !== e.to), par = {}, lab = {}, also = {}, kids = {};
  ms.forEach(m => {
    const cands = es.filter(e => e.to === m && inn.has(e.from)), own = cands.filter(e => e.own).reverse();   // Tom's latest arrow wins
    const pick = [...own, ...cands.filter(e => !e.own)].find(e => { for (let x = e.from; x; x = par[x]) if (x === m) return false; return true; });
    if (pick) { par[m] = pick.from; lab[m] = cands.filter(e => e.from === pick.from && e.label && e.label !== "then").map(e => e.label); }
    else { const top = es.find(e => e.to === m && e.from === sid); if (top && top.label) lab[m] = [top.label]; }
    also[m] = [...new Set(cands.filter(e => !pick || e.from !== pick.from).map(e => e.from))];
    (kids[par[m] || ""] ||= []).push(m);
  });
  if (kids[""]) kids[""].sort((a, b) => (kindOf(a) === "exit") - (kindOf(b) === "exit"));   // the ways out come last
  return {ms, par, lab, also, kids, under: m => { const out = [m]; for (let i = 0; i < out.length; i++) out.push(...(kids[out[i]] || [])); return out; }};
}
function rowHtml(m, tr) {   // a card as one line: in the Running order, and in a scene's Any time section
  const k = kindOf(m) || "beat", o = objOf(m), [f, n] = parseClock(o.clock), lab = tr && tr.lab[m], also = tr && tr.also[m] || [];
  return `<div class="tr k-${esc(k)}" data-card="${esc(m)}"><span class="rg" title="Drag to move it">⠿</span><span class="mk k-${esc(k)}${isCrit(o) ? " crit" : ""}">${isCrit(o) ? "Critical" : esc(KINDS[k] || "Beat")}</span>` +
    `<span class="tt">${lab && lab.length ? `<i class="el">${lab.map(esc).join(" <b>or</b> ")}</i> ` : tr && tr.par[m] && kindOf(tr.par[m]) === "decision" ? `<i class="el none">choice not named</i> ` : ""}${esc(titleOf(m))}${(fieldOf(o, "who") || []).length ? ` <small>${esc(o.who.join(", "))}</small>` : ""}${fieldOf(o, "cue") ? `<span class="cue"><b>Cue</b>${esc(o.cue)}</span>` : ""}</span>${k === "clock" ? `<span class="rng">${ring(f, n, 18)}</span>` : ""}` +
    (also.length ? `<small>also after ${esc(also.map(titleOf).join(", "))}</small>` : "") + `</div>`;
}
const NOTREE = {ms: [], par: {}, lab: {}, also: {}, kids: {}}, outsOf = (m, tr) => ["decision", "exit"].includes(kindOf(m)) ? elsewhere(m, tr || NOTREE) : "";
function treeHtml(sid, tr, root) {
  const list = tr.kids[root] || []; if (!list.length) return "";
  return `<ul class="tree">` + list.map(m => `<li>${rowHtml(m, tr)}${treeHtml(sid, tr, m)}${outsOf(m, tr)}</li>`).join("") + `</ul>`;
}
function anyHtml(sid) {   // a scene's Any time section on the canvas: nothing at all when it is empty
  const ms = anyOf(sid), shut = !!(it(sid) || {}).anyx; if (!ms.length) return "";
  return `<div class="any"><button class="anyh" data-anyx aria-expanded="${!shut}">${shut ? "▸" : "▾"} Any time in this scene <small>${ms.length}</small></button><div class="anyl"${shut ? " hidden" : ""}>${ms.map(m => rowHtml(m) + outsOf(m)).join("")}</div></div>`;
}
function flipAny(sid) { const o = it(sid); roomFor(sid, () => { if (o.anyx) delete o.anyx; else o.anyx = 1; }); changed(); draw(); }
function elsewhere(m, tr) {   // a decision's options that lead out of this scene, or to a card shown under another
  const os = optionsOf(m).filter(o => tr.par[o.to] !== m);
  const at = o => !o.to ? "" : o.off ? "not placed" : isAny(o.to) && sceneOf(o.to) === sceneOf(m) ? "any time" : tr.ms.includes(o.to) ? "below" : sceneOf(o.to) ? `in “${titleOf(sceneOf(o.to))}”${sessOf(o.to) !== sessOf(m) ? ", " + sessOf(o.to) : ""}` : isScene(o.to) ? `a scene${sessOf(o.to) !== sessOf(m) ? " in " + sessOf(o.to) : ""}` : `not in a scene${sessOf(o.to) !== sessOf(m) ? ", " + sessOf(o.to) : ""}`;
  if (!os.length && kindOf(m) === "exit" && !(objOf(m).who || []).length && !(tr.kids[m] || []).length) return `<ul class="tree outs"><li><div class="ot">↗ <i>where it leads is not set</i></div></li></ul>`;
  return os.length ? `<ul class="tree outs">${os.map(o => `<li><div class="ot">${o.to ? "↗" : "◇"} ${o.label ? `<i class="el">${esc(o.label)}</i> ` : kindOf(m) === "decision" ? `<i class="el none">choice not named</i> ` : ""}${esc(outOf(o))} <small>${esc(at(o))}</small></div></li>`).join("")}</ul>` : "";
}
function togglePlayer(id, k) {   // in or out of a scene; "The Party" stands for everyone
  const o = it(id), list = [...(objOf(id).present || [])], everyone = everyPc(presentLanes(id)), lead = list.some(n => pcOf(n) === k);
  let next;
  if (k === "The Party") next = [...(everyone ? [] : ["The Party"]), ...list.filter(n => !pcOf(n))];
  else if (everyone) next = [...PCS.map(p => p.key).filter(x => x !== k), ...list.filter(n => !pcOf(n))];
  else if (lead) next = list.filter(n => pcOf(n) !== k);
  else { next = [...list, k]; if (everyPc(next.map(pcOf))) next = ["The Party", ...list.filter(n => !pcOf(n))]; }
  const before = lanesOf(id);
  setPresent(id, next);
  const cast = castLanes(id);
  if ((k === "The Party" && everyone) || (k !== "The Party" && (lead || everyone))) o.homes = o.homes.filter(h => h !== k);   // out of the scene: off that board too
  if (!o.homes.length && !cast.length && !cardLanes(id).length) o.born = HOMELESS;
  const now = lanesOf(id); before.forEach(b => { if (!now.includes(b) && b !== WHOLE && o.at) delete o.at[b]; });
  changed(); drawRun(); if (shown === id) open(id);
}
function newScene(before) {   // a scene for this session, on no board until it has players
  const cid = Math.random().toString(36).slice(2, 10), id = "c:" + cid;
  doc.cards[cid] = {kind: "scene", title: "", text: "", where: "", present: []};
  doc.items[id] = {s: runTab, homes: [], born: HOMELESS, at: {}, w: SCW, h: SCH};
  const ord = scenesIn(runTab).filter(x => x !== id), i = before ? ord.indexOf(before) : -1;
  ord.splice(i < 0 ? ord.length : i, 0, id); doc.order[runTab] = ord; heed(runTab);
  opened.add(id); casting = id; changed(); drawRun();
  const el = $$("#run .rc").find(x => x.dataset.uid === id); if (el) el.scrollIntoView({block: "nearest"});
  openHere(id, "edit");
}
function newInScene(sid, kind = "beat", spot) {   // a card of Tom's, at the end of a scene or where it was dropped
  const cid = Math.random().toString(36).slice(2, 10), id = "c:" + cid, ks = lanesOf(sid);
  doc.cards[cid] = {kind, title: "", text: ""};
  doc.items[id] = {s: sessOf(sid), homes: [ks[0]], born: ks[0], at: {}};
  if (spot && spot.any) { toAny(id, sid, spot.before); if (runMode) openHere(id, "edit"); else open(id, "edit"); return; }
  if (runMode) {
    dropInto(id, spot || {sid}, [id]);
    openHere(id, "edit");
    const e = spot && spot.parent && kindOf(spot.parent) === "decision" && doc.edges.find(x => x.from === spot.parent && x.to === id && !x.label);
    if (e) edgeEditor(e.id, true);   // a new option: ask for the choice
    return;
  }
  const f = insideSpot(sid); join(id, sid, f.rx, f.ry); changed(); draw(); open(id, "edit");
}
const addBtns = sid => `<div class="adds">${INSCENE.map(k => `<button class="k-${k}" data-addto="${esc(sid)}" data-k="${k}" title="${esc(KDESC[k])}">${kic(k)}${KINDS[k]}</button>`).join("")}</div>`;
function runCard(id, i) {
  const o = objOf(id), mine = id.startsWith("c:"), op = opened.has(id), tr = treeOf(id), others = (o.present || []).filter(n => !pcOf(n)), text = (mine ? o.text : o.summary) || "";
  const fl = isFloat(id), any = anyOf(id);
  return `<div class="rc${fl ? " floaty" : ""}" data-uid="${esc(id)}">` +
    `<span class="rg" title="Drag to move it in the running order">⠿</span><span class="rn"${fl ? ` title="Floating: no fixed place in the order">${icon("float", 20)}` : `>${numIn(id)}`}</span>` +
    `<div class="rb"><div class="rt"><b>${esc(titleOf(id))}</b>${!mine && o.status === "ready" ? '<span class="ch ready">ready</span>' : ""}` +
    `${mine ? `<span class="ch ed">${whose(o)}</span>` : o.edited ? '<span class="ch ed">edited</span>' : ""}</div>` +
    `<div class="rw">${o.where ? "At " + esc(o.where) : "<i>Where not set</i>"}${o.when ? " · " + esc(o.when) : ""}${others.length ? " · with " + others.map(esc).join(", ") : ""}</div>` +
    (o.purpose ? `<div class="rp pur"><b>Purpose</b>${esc(o.purpose)}</div>` : "") + (fl ? `<div class="lim"><b>Floating</b>${limText(id)}</div>` : "") + `<div class="pcs">${pills(id)}</div></div>` +
    `<button class="rx" aria-expanded="${op}" title="Show or hide what happens in this scene">${op ? "▾" : "▸"} ${tr.ms.length + any.length}</button>` +
    `<div class="rm"${op ? "" : " hidden"}>${text ? `<p>${esc(text)}</p>` : ""}` + `<div class="anyz${any.length ? "" : " none"}"><div class="anyt">Any time in this scene</div>${any.map(m => rowHtml(m) + outsOf(m)).join("")}</div>` + (treeHtml(id, tr, "") || (any.length ? "" : `<p class="muted">Nothing in this scene yet. Drag a card here.</p>`)) +
    addBtns(id) + `<div class="acts"><button data-edit="${esc(id)}">Edit scene</button><button data-fl="${esc(id)}" title="${fl ? "Give it a fixed place and a number again" : "No number and no link to the scenes around it: move it back and forth as you need"}">${fl ? "Fix it in the order" : "Let it float"}</button></div></div></div>`;
}
function drawRun() {
  const ts = runSessions(); if (!ts.includes(runTab)) runTab = ts[0];
  const t = runTab, scenes = scenesIn(t), all = scenes.length && scenes.every(x => opened.has(x)), top = $("#run").scrollTop;
  $("#rsess").innerHTML = ts.map(x => `<button role="tab" data-rtab="${esc(x)}" aria-selected="${x === t}" title="${esc(sName(x))}">${esc(x)}${sessNum(x) === CUR + 1 ? " · next" : ""}<small>${scenesIn(x).length}</small></button>`).join("") + addTab;
  $("#rsess [data-addsess]").onclick = addSession;
  $$("#rsess [data-rtab]").forEach(b => b.onclick = () => { runTab = b.dataset.rtab; closeDrawer(); drawRun(); $("#run").scrollTop = 0; });
  $("#run").innerHTML = `<div class="runh"><span><b>Running order</b> &nbsp;<button class="sname" data-sname title="This session’s name, what happens and its arc">${snHtml(t)}</button> &nbsp;${scenes.length} scene${scenes.length === 1 ? "" : "s"}</span>` +
    (scenes.length ? `<button class="mini" data-allx>${all ? "Collapse all" : "Expand all"}</button>` : "") + `</div>` +
    (scenes.length ? scenes.map(runCard).join("") : `<p class="empty">No scenes in ${esc(t)} yet. Add the scenes first and fit beats, entrances and exits into them, or drag cards in later.</p>`) +
    `<button class="addsc" data-newscene>+ Add a scene to ${esc(t)}</button>`;
  $("#run").scrollTop = top;
  $("#run [data-sname]").onclick = () => sessPanel(t);
  drawLoose(t);
  $$("#run [data-go]").forEach(b => b.onclick = ev => { ev.stopPropagation(); goto(b.dataset.go, t, b.dataset.id); });
  $$("#run [data-edit]").forEach(b => b.onclick = ev => { ev.stopPropagation(); openHere(b.dataset.edit); });
  $$("#run .rx").forEach(b => b.onclick = ev => { ev.stopPropagation(); toggleRun(b.closest(".rc").dataset.uid); });
  $$("#run [data-casting]").forEach(b => b.onclick = ev => { ev.stopPropagation(); casting = casting === b.dataset.casting ? null : b.dataset.casting; drawRun(); });
  $$("#run [data-cast]").forEach(b => b.onclick = ev => { ev.stopPropagation(); togglePlayer(b.dataset.id, b.dataset.cast); });
  $$("#run [data-addto]").forEach(b => b.onclick = ev => { ev.stopPropagation(); newInScene(b.dataset.addto, b.dataset.k); });
  $$("#run [data-fl]").forEach(b => b.onclick = ev => { ev.stopPropagation(); setFloat(b.dataset.fl, !isFloat(b.dataset.fl)); if (shown === b.dataset.fl) open(shown); });
  $("#run [data-newscene]").onclick = () => newScene();
  const ax = $("#run [data-allx]"); if (ax) ax.onclick = () => { scenes.forEach(x => all ? opened.delete(x) : opened.add(x)); drawRun(); };
  $$("#run .rc").forEach(el => runDrag(el, t));
  $$("#run .tr").forEach(el => cardDrag(el, el.dataset.card));
  tips($("#run"));
  if (shown) $$(`[data-card]`).forEach(x => x.classList.toggle("on", x.dataset.card === shown));
}
function drawLoose(t) {   // beside the Running order: what is in this session but in no scene, then the same tray as the canvases
  const loose = looseIn(t), by = {}; loose.forEach(i => (by[lanesOf(i)[0]] ||= []).push(i));
  const row = id => { const o = objOf(id), s = (id.startsWith("c:") ? o.text : o.summary) || ""; return `<div class="ti k-${esc(kindOf(id) || "beat")}" data-card="${esc(id)}"><span class="g rg" title="Drag it into a scene">⠿</span><div><div class="k">${kic(kindOf(id))}${esc(kl(id))}</div><div class="t">${esc(titleOf(id))}</div>${s ? `<div class="s">${esc(s.length > 120 ? s.slice(0, 120) + "…" : s)}</div>` : ""}</div></div>`; };
  const z = $("#loosez"), y = z.scrollTop; z.hidden = !loose.length;
  z.innerHTML = `<div class="trayh"><b>In no scene</b><small>${loose.length}</small></div><div class="tlist">` + D.lanes.filter(l => by[l.key]).map(l => `<h4>${laneTag(l)}</h4>` + by[l.key].map(row).join("")).join("") + `</div>`; z.scrollTop = y;
  $$("#loosez [data-card]").forEach(el => cardDrag(el, el.dataset.card));
  tray();
}
function toggleRun(u) {
  const on = !opened.has(u); if (on) opened.add(u); else opened.delete(u);
  const el = $$("#run .rc").find(x => x.dataset.uid === u); if (el) expand(el, on);
}
function expand(el, on) {
  el.querySelector(".rm").hidden = !on; const x = el.querySelector(".rx"); x.setAttribute("aria-expanded", on); x.textContent = (on ? "▾ " : "▸ ") + x.textContent.slice(2);
}
function openHere(id, m) {   // its panel, without leaving the running order
  const ks = it(id) ? lanesOf(id) : P[id.slice(2)].lanes; if (!ks.includes(lane)) lane = ks[0] || D.lanes[0].key;
  open(id, m);
}
const rtabUnder = e => $$("#rsess [data-rtab]").find(b => inRect(e, b));
function edgeScroll(e) { const l = $("#run"), r = l.getBoundingClientRect(); if (e.clientY < r.top + 40) l.scrollTop -= 14; else if (e.clientY > r.bottom - 40) l.scrollTop += 14; }
function watch(mv, up) {   // follow the pointer until it lifts; cancel undoes
  const end = e => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", end); window.removeEventListener("pointercancel", end); up(e, e.type === "pointercancel"); };
  window.addEventListener("pointermove", mv); window.addEventListener("pointerup", end); window.addEventListener("pointercancel", end);
}
let dragEnd = 0;
function runDrag(el, t) {   // a scene card: in the running order, or onto another session's tab
  el.addEventListener("click", ev => { if (Date.now() - dragEnd > 300 && !ev.target.closest("button,a,.rm,.rg")) toggleRun(el.dataset.uid); });
  el.addEventListener("pointerdown", ev => {
    if (ev.button > 0 || ev.target.closest("button,a,.rm")) return;
    if (!ev.target.closest(".rg") && ev.pointerType !== "mouse") return;   // touch: the grip drags
    ev.preventDefault();
    const st = {x: ev.clientX, y: ev.clientY}; let moved = false;
    watch(e => {
      if (!moved && Math.hypot(e.clientX - st.x, e.clientY - st.y) < 5) return;
      moved = true; el.classList.add("drag");
      const tb = rtabUnder(e); $$("#rsess button").forEach(x => x.classList.toggle("drop", x === tb && tb.dataset.rtab !== t)); if (tb) return;
      const mid = x => { const r = x.getBoundingClientRect(); return r.top + r.height / 2; };   // the others move round it, so a touch drag keeps its target
      for (let p; (p = el.previousElementSibling) && p.matches(".rc") && e.clientY < mid(p);) el.after(p);
      for (let n; (n = el.nextElementSibling) && n.matches(".rc") && e.clientY > mid(n);) el.before(n);
      $$("#run .rc:not(.floaty) .rn").forEach((n, i) => { n.textContent = i + 1; });
      trayHot(e, el.dataset.uid);
      edgeScroll(e);
    }, (e, off) => {
      el.classList.remove("drag"); $$("#rsess button").forEach(x => x.classList.remove("drop"));
      if (!moved) return;
      dragEnd = Date.now(); const tb = rtabUnder(e);
      if (off) { drawRun(); return; }
      if (tb && tb.dataset.rtab !== t) { moveTo(el.dataset.uid, tb.dataset.rtab); return; }
      if (trayHot(e, el.dataset.uid, true)) { drawRun(); takeOff(el.dataset.uid); return; }
      doc.order[t] = $$("#run .rc").map(x => x.dataset.uid);
      const back = heed(t); if (back.length) toast(`${back.map(x => `“${titleOf(x)}” stays ${limText(x).replace(/<[^>]*>/g, "").replace(/&#39;/g, "’").replace(/&amp;/g, "&")}`).join("; ")}.`);
      changed(); drawRun();
    });
  });
}
const trayHot = (e, id, off) => { const z = $("#loose [data-tray]"), on = id.startsWith("p:") && !!it(id) && inRect(e, z); z.classList.toggle("over", on && !off); return on; };   // a plan dragged back to the tray
const clearRun = () => { $$(".in-on,.in-before,.in-after,.rc.hot,.rc.near,#loose .over").forEach(x => x.classList.remove("in-on", "in-before", "in-after", "hot", "near", "over")); $$("#rsess button").forEach(x => x.classList.remove("drop")); };
function runSpot(e, mine, scene, inScene) {   // where in the running order a card would land, and what that means
  let spot = null, say = "";
  const tb = rtabUnder(e), hit = document.elementFromPoint(e.clientX, e.clientY), row = hit && hit.closest("#run .tr"), rc = hit && hit.closest("#run .rc");
  if (tb) { if (tb.dataset.rtab !== runTab) { tb.classList.add("drop"); spot = {tab: tb.dataset.rtab}; say = `move to ${tb.dataset.rtab}`; } }
  else if (hit && hit.closest("#loose")) {
    if (mine.length && trayHot(e, mine[0])) { spot = {tray: 1}; say = "back to Not placed yet"; }
    else if (inScene) { $$("#loose .tsec").forEach(x => x.classList.add("over")); spot = {out: 1}; say = "take it out of its scene"; }
  }
  else if (scene) { if (hit && hit.closest("#run")) { spot = {scene: 1, before: rc ? rc.dataset.uid : null}; if (rc) rc.classList.add("in-before"); say = `a scene in ${runTab}`; } }
  else if (hit && hit.closest("#run .anyz")) { const to = row && !mine.includes(row.dataset.card) ? row.dataset.card : null; spot = {sid: rc.dataset.uid, any: 1, before: to}; if (to) row.classList.add("in-before"); rc.classList.add("hot", "near"); say = `any time in “${titleOf(rc.dataset.uid)}”`; }
  else if (row && !mine.includes(row.dataset.card)) {
    const to = row.dataset.card, r = row.getBoundingClientRect(), f = (e.clientY - r.top) / r.height, sid = rc.dataset.uid, tr = treeOf(sid), up = tr.par[to];
    if (f < .28) { spot = {sid, parent: up, before: to}; row.classList.add("in-before"); }
    else if (f > .72) { spot = {sid, parent: up, after: to}; row.classList.add("in-after"); }
    else { spot = {sid, parent: to}; row.classList.add("in-on"); }
    say = spot.parent ? `follows “${titleOf(spot.parent)}”` : "starts in this scene";
  } else if (rc && !row) { spot = {sid: rc.dataset.uid}; rc.classList.add("hot"); say = `in “${titleOf(rc.dataset.uid)}”`; }
  if (rc && !scene) rc.classList.add("near");
  return {spot, say, rc};
}
function cardDrag(el, id) {   // a card: into a scene, under or beside another card, back out, or onto another session's tab
  el.addEventListener("click", () => { if (Date.now() - dragEnd > 300) openHere(id); });
  el.addEventListener("pointerdown", ev => {
    if (ev.button > 0 || (!ev.target.closest(".rg") && ev.pointerType !== "mouse")) return;
    ev.preventDefault(); ev.stopPropagation();
    const st = {x: ev.clientX, y: ev.clientY}, from = it(id) ? sceneOf(id) : null, mine = from ? treeOf(from).under(id) : [id], scene = isScene(id);
    let ghost = null, spot = null, timer = null, over = null;
    const clear = clearRun;
    watch(e => {
      if (!ghost) {
        if (Math.hypot(e.clientX - st.x, e.clientY - st.y) < 5) return;
        ghost = document.createElement("div"); ghost.className = `bn ghost k-${kindOf(id) || "beat"}`;
        ghost.innerHTML = `<div class="t">${esc(titleOf(id))}${mine.length > 1 ? ` <small>+ ${mine.length - 1} under it</small>` : ""}</div><div class="s"></div>`; document.body.append(ghost);
      }
      ghost.style.left = e.clientX + 12 + "px"; ghost.style.top = e.clientY + 10 + "px";
      clear(); const at = runSpot(e, mine, scene, it(id) && from), rc = at.rc; spot = at.spot; const say = at.say;
      ghost.querySelector(".s").textContent = say;
      if (rc !== over) { clearTimeout(timer); over = rc; if (rc && !opened.has(rc.dataset.uid)) timer = setTimeout(() => { opened.add(rc.dataset.uid); expand(rc, true); }, 550); }
      edgeScroll(e);
    }, (e, off) => {
      clearTimeout(timer); clear(); if (!ghost) return;
      ghost.remove(); dragEnd = Date.now();
      if (off || !spot) return;
      if (spot.tab) { if (it(id)) moveTo(id, spot.tab); else { putPlan(id, spot.tab); changed(); drawRun(); } }
      else if (spot.tray) takeOff(id);
      else if (spot.out) { mine.forEach(m => { release(m); it(m).at = {}; }); changed(); drawRun(); }
      else if (spot.any) toAny(id, spot.sid, spot.before);
      else if (spot.scene) {
        putPlan(id, runTab); const ord = scenesIn(runTab).filter(x => x !== id), i = spot.before ? ord.indexOf(spot.before) : -1;
        ord.splice(i < 0 ? ord.length : i, 0, id); doc.order[runTab] = ord; heed(runTab); changed(); drawRun();
      } else {
        dropInto(id, spot, mine);
        const e = spot.parent && kindOf(spot.parent) === "decision" && doc.edges.find(x => x.from === spot.parent && x.to === id && !x.label);
        if (e) edgeEditor(e.id, true);   // a new option: ask for the choice
      }
    });
  });
}
function putPlan(id, t) {   // an unplaced plan joins session t, on the boards it is tied to
  const p = P[id.slice(2)], homes = p.lanes.length ? [...p.lanes] : [D.lanes[0].key];
  doc.items[id] = {s: t, homes, born: homes[0], at: {}, ...(isScene(id) ? {w: SCW, h: SCH} : {})};
}
function dropInto(id, spot, block, quiet) {   // put a card (and what follows it) into a scene, joined and placed the way it was dropped
  const sid = spot.sid, from = it(id) ? sceneOf(id) : null, old = from ? treeOf(from) : null;
  if (!it(id)) putPlan(id, sessOf(sid));
  withLane(lanesOf(sid)[0], () => { ensureAt(sessOf(sid)); measure([sid, ...membersOf(sid), ...block]); });
  const H = m => hs[m] || 110, inBlock = new Set(block), tr = treeOf(sid), o = it(sid);
  const rel = block.map(m => from ? [m, (it(m).rx || 0) - (it(id).rx || 0), (it(m).ry || 0) - (it(id).ry || 0)] : [m, 0, 0]);
  /* arrows: the one it hung from goes, the one it was dropped on comes. Dropped on the scene as a whole, it keeps the arrows it has */
  const oldPar = old && old.par[id], members = new Set(membersOf(sid)), whole = !spot.before && !spot.after && !spot.parent;
  if (whole && from !== sid) { const e = genEdges().filter(x => x.to === id && members.has(x.from)).pop(); if (e) spot.parent = e.from; }
  else doc.edges = doc.edges.filter(e => e.to !== id || e.from === spot.parent || !(e.from === oldPar || (!spot.parent && (members.has(e.from) || (old && old.ms.includes(e.from))))));
  if (spot.parent) {
    const mine = e => e.from === spot.parent && e.to === id;
    if (doc.edges.some(mine)) doc.edges = [...doc.edges.filter(e => !mine(e)), ...doc.edges.filter(mine)];   // the latest arrow is the one the list follows
    else addEdge(spot.parent, id);
  }
  /* place */
  const others = tr.ms.filter(m => !inBlock.has(m)), bottom = ms => Math.max(...ms.map(m => it(m).ry + H(m)));
  const branch = m => tr.under(m).filter(x => !inBlock.has(x)), kids = p => (tr.kids[p] || []).filter(x => !inBlock.has(x));
  let x, y;
  if (spot.before) { x = it(spot.before).rx; y = it(spot.before).ry; }
  else if (spot.after) { x = it(spot.after).rx; y = bottom(branch(spot.after)) + 22; }
  else if (spot.parent) { const ks = kids(spot.parent); x = ks.length ? it(ks[0]).rx : it(spot.parent).rx + CARDW + 80; y = ks.length ? bottom(ks.flatMap(branch)) + 22 : it(spot.parent).ry; }
  else { const top = kids(""); x = top.length ? Math.min(...top.map(m => it(m).rx)) : 22; y = others.length ? bottom(others) + 22 : headOf(sid) + 22; }
  const minY = Math.min(...rel.map(r => r[2])), minX = Math.min(...rel.map(r => r[1]));
  x = snap(Math.max(22, x)) - Math.min(0, minX + 0); y = snap(y + 5) - minY;
  const wasScene = from === sid;
  block.forEach(m => { if (!wasScene) { if (it(m).scene) release(m); } });
  rel.forEach(([m, dx, dy]) => join(m, sid, snap(x + dx), snap(y + dy)));
  /* nothing overlaps: whatever is in the way moves down */
  const hit = (a, b) => it(a).rx < it(b).rx + CARDW + 10 && it(a).rx + CARDW + 10 > it(b).rx && it(a).ry < it(b).ry + H(b) + 10 && it(a).ry + H(a) + 10 > it(b).ry;
  const fixed = [...block];
  others.sort((a, b) => it(a).ry - it(b).ry).forEach(m => {
    for (let n = 0, c; n < 60 && (c = fixed.find(f => hit(m, f))); n++) it(m).ry = snap(it(c).ry + H(c) + 22 + 10);
    fixed.push(m);
  });
  const ms = flowOf(sid), needW = Math.max(...ms.map(m => it(m).rx + CARDW)) + 22, needH = bottom(ms) + 22;
  if (needW > (o.w || SCW) || needH > (o.h || SCH)) growScene(sid, needW, needH);
  if (quiet) return;
  opened.add(sid);
  const want = spot.parent || "", got = treeOf(sid).par[id] || "";
  changed(); drawRun();
  if (want !== got && got) toast(`The vault already says “${titleOf(id)}” follows “${titleOf(got)}”, so it stays under it. Ask Claude to change that in the plan.`);
}
function layNew() {   // cards a session drafted into scenes get their places here, where their real sizes are known
  const fresh = Object.keys(doc.items).filter(i => it(i).lay); if (!fresh.length) return false;
  const by = {};
  fresh.forEach(i => { delete it(i).lay; const sc = live(i) && sceneOf(i); if (sc) (by[sc] ||= []).push(i); });
  for (const [sid, ms] of Object.entries(by)) {
    const tr = treeOf(sid), list = (tr.kids[""] || []).flatMap(tr.under).filter(m => ms.includes(m));
    if (list.length < tr.ms.length) { list.forEach(m => { delete it(m).scene; }); list.forEach(m => dropInto(m, {sid}, [m], true)); continue; }   // beside Tom's own cards
    withLane(lanesOf(sid)[0], () => measure([sid, ...list]));
    layScene(sid, list, tr);
  }
  return true;
}
function toast(t, act, fn) {
  const d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.append(d); setTimeout(() => d.remove(), act ? 12000 : 6500);
  if (act) { const b = document.createElement("button"); b.textContent = act; b.onclick = () => { d.remove(); fn(); }; d.append(b); }
}
function goto(k, t, id) {   // a scene on one character's board
  pick(k); if (T() !== t) openTab(t);
  if (id) reveal(id);
}
function reveal(id) {
  const b = box(id); if (!b) return;
  const r = board.getBoundingClientRect(), k = Math.min(1, Math.max(.3, Math.min((r.width - 60) / b.w, (r.height - 90) / b.h)));
  view = {k, x: (r.width - b.w * k) / 2 - b.x * k, y: Math.max(50, (r.height - b.h * k) / 2) - b.y * k}; applyView();
  const el = $$("#nodes .bn").find(x => x.dataset.id === id); if (el) { el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1800); }
}

/* ---------- what a plan needs (the same rules as build.py) ---------- */
const isOut = a => !!(F[a] && F[a].out), isDead = a => !!(F[a] && GONE.has(F[a].state));
function test(r) {
  switch (r.k) {
    case "alive": return !isDead(r.a);
    case "dead": return isDead(r.a);
    case "hidden": return !isOut(r.a);
    case "revealed": return isOut(r.a);
    case "plan": case "played": return !(doc.edits[r.a] || {}).drop;
    default: return true;   // checks and fixed facts hold now, or the build would have pruned the plan
  }
}

/* ---------- drawing ---------- */
const secReq = p => p.req.filter(r => (r.k === "hidden" || r.k === "revealed") && F[r.a]);
function planCard(id) {
  const p = view_of(id), o = it("p:" + id), at = o && sessOf("p:" + id);
  const mv = p.target && o && at.toUpperCase() !== p.target.toUpperCase() ? `vault says ${p.target}` : "";
  const checks = p.req.filter(r => r.k === "check").length;
  return `<div class="k"><span>${kic(p.kind)}${esc(isCrit(p) ? "Critical decision" : KINDS[p.kind] || "Beat")}</span><span>${p.edited ? "edited · not in vault" : esc(p.status)}</span></div><div class="t">${esc(p.id)}</div>` +
    extras(p, "p:" + id) + `<div class="s">${esc(p.summary)}</div>` +
    (p.kind === "decision" || p.kind === "exit" ? optsHtml("p:" + p.id) : "") +
    `<div class="chips">${p.status === "ready" ? '<span class="ch ready">ready</span>' : ""}${mv ? `<span class="ch move">${esc(mv)}</span>` : ""}` +
    secReq(p).map(r => `<span class="ch sec ${isOut(r.a) ? "out" : ""}" title="It needs this secret ${r.k}">${isOut(r.a) ? "out" : "secret"}: ${esc(r.a)}</span>`).join("") +
    (checks ? `<span class="ch ck">${checks} check${checks > 1 ? "s" : ""}</span>` : "") +
    (p.via[lane] ? `<span class="ch">through ${esc(p.via[lane])}</span>` : "") + `</div>`;
}
function hpText(sh) {
  if (!sh.hp) return "";
  return `${sh.hp}${sh.hp_max ? " / " + sh.hp_max : ""}${sh.hp_temp && sh.hp_temp !== "0" ? ` (+${sh.hp_temp} temp)` : ""}`;
}
function nowCard(n, kind) {
  const sh = n.sheet || {}, rows = [], miss = '<span class="miss">filled at the next sync</span>';
  if (n.location) rows.push(["Where", esc(n.location)]);
  if (kind !== "world") rows.push(["Status", esc([n.state, sh.conditions].filter(Boolean).join(" · ") || "unknown")]);
  if (kind === "pc") { rows.push(["HP", hpText(sh) ? esc(hpText(sh)) : miss]); rows.push(["Slots", sh.slots ? esc(sh.slots) : miss]); }
  if (n.members) n.members.forEach(m => rows.push([esc(m.name.split(" ")[0]),
    esc([hpText(m.sheet) ? hpText(m.sheet) + " HP" : "", m.sheet.slots || "", m.sheet.conditions || ""].filter(Boolean).join(" · ")) || miss]));
  const asof = sh.sheet_at ? ` · sheet at end of ${sh.sheet_at}` : "";
  const head = n.open ? `Open going into S${CUR + 1}` : `Lately${n.recent_at ? " · S" + n.recent_at : ""}`;
  return `<div class="k"><span>End of S${CUR} · as played${esc(asof)}</span>${n.player ? `<span>${esc(n.player)}</span>` : ""}</div>` +
    `<div class="t">${n.href ? `<a href="${esc(n.href)}">${esc(n.title)}</a>` : esc(n.title)}</div>` +
    (n.about ? `<div class="s"><i>${esc(n.about)}</i></div>` : "") + (n.class ? `<div class="s">${esc(n.class)}</div>` : "") + (n.summary ? `<div class="s">${esc(n.summary)}</div>` : "") +
    (rows.length ? `<dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl>` : "") +
    (n.recent && n.recent.length ? `<div class="k"><span>${head}</span></div><ul>${n.recent.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : "");
}
const whose = c => c.draft === "new" ? "Claude’s draft" : c.draft === "edit" ? "tidied by Claude" : "yours · not in vault";
function titleOf(id) { if (id.startsWith("p:")) return id.slice(2); const c = doc.cards[id.slice(2)]; return c ? (c.title || "untitled card") : id; }
function between(a, b) {   // sessions only in the Arc planner, before this one
  if (!Link.has(doc)) return "";
  const at = Link.numbers(doc, CUR), list = Link.seq(doc.arcs).filter(c => !doc.arcs.cards[c].link && at[c] > sessNum(a) && at[c] < sessNum(b));
  return list.length ? `<div class="k"><span>In between, in the Arc planner</span></div><ul>${list.map(c => `<li>S${at[c]} ${esc(doc.arcs.cards[c].title || "Untitled session")}</li>`).join("")}</ul>` : "";
}
function startCard(tab, idx) {
  const ln = D.lanes.find(x => x.key === lane);
  if (idx === 0) return nowCard(ln.now, ln.kind);
  const prev = doc.sessions[idx - 1], items = inTab(prev);
  const later = tab === "Later";
  return `<div class="k"><span>${later ? "Later · no session yet" : `End of ${esc(prev)} · as planned`}</span></div>` +
    `<div class="t">${later ? "Whenever it fits" : `After ${esc(prev)}${sName(prev) ? " · " + esc(sName(prev)) : ""}`}</div>` + (later ? "" : between(prev, tab)) +
    (later ? `<div class="s">Ideas without a session. Place a card here, then move it to a session when it is time.</div>` :
      items.length ? `<div class="k"><span>Planned for ${esc(prev)}</span></div><ul>${items.map(i => `<li>${isScene(i) ? "Scene: " : ""}${esc(titleOf(i))}</li>`).join("")}</ul>`
        : `<div class="s">Nothing planned for ${esc(prev)} yet.</div>`);
}
function draw() {
  if (runMode) { drawRun(); return; }
  const tab = T(), idx = doc.sessions.indexOf(tab);
  ensureAt(tab);
  const ids = inTab(tab).filter(i => !isAny(i)).sort((a, b) => isScene(b) - isScene(a));   // scenes underneath
  const paint = () => {
    $("#nodes").innerHTML = `<div class="bn now ${idx ? "start" : ""}" data-id="start" style="left:${SX}px;top:${SY}px">${startCard(tab, idx)}</div>` + ids.map(cardHtml).join("");
    const was = {...ah}; $$("#nodes .bn").forEach(noteSize);
    return ids.some(i => isScene(i) && (was[i] || 0) !== ah[i]);
  };
  if (paint()) paint();   // an Any time section changed size: what is under it moves
  sessTabs(); wires(); bindNodes(); tray(); applyView();
}
function cardHtml(id) {
  const b = box(id) || {x: 0, y: 0, w: (it(id) || {}).w || SCW, h: (it(id) || {}).h || SCH}, sc = isScene(id), mine = id.startsWith("c:");
  let inner, cls;
  if (mine) {
    const c = doc.cards[id.slice(2)];
    inner = `<div class="k"><span>${kic(c.kind)}${esc(kl(id))}</span><span>${whose(c)}</span></div><div class="t">${esc(c.title || "Untitled")}</div>` + extras(c, id) +
      (c.text ? `<div class="s">${esc(c.text.length > 220 ? c.text.slice(0, 220) + "…" : c.text)}</div>` : "") + (c.kind === "decision" || c.kind === "exit" ? optsHtml(id) : "");
    cls = `mine k-${c.kind}`;
  } else {
    const pid = id.slice(2), p = view_of(pid);
    inner = planCard(pid); cls = `k-${p.kind}${p.edited ? " edited" : ""}`;
  }
  if (isCrit(objOf(id))) cls += " crit"; if (sc && isFloat(id)) cls += " floaty";
  const several = it(id) && lane !== WHOLE && !sceneOf(id) && lanesOf(id).length > 1;
  if (lane === WHOLE && it(id)) {
    if (sc) { const n = numIn(id); if (sessOf(id) !== "Later") inner = inner.replace('<div class="t">', isFloat(id) ? `<div class="t"><span class="ord fl" title="Floating: no fixed place in the running order">${icon("float", 14)}</span>` : `<div class="t"><span class="ord" title="Its place in the running order">${n}</span>`); }
    else if (!sceneOf(id)) inner += `<div class="chips">${laneTags(lanesOf(id))}</div>`;
  }
  const xt = several ? "Take it off this board" : mine ? "Delete this card" : "Back to the tray";
  return `<div class="bn ${esc(cls)}${sc ? " scene" : ""}" data-id="${esc(id)}" style="left:${b.x}px;top:${b.y}px${sc ? `;width:${b.w}px;height:${b.h}px` : ""}">` +
    (sc ? `<div class="sh">${inner}${anyHtml(id)}</div><span class="rz" title="Drag to resize the scene"></span>` : inner) +
    `<button class="xx" title="${xt}" aria-label="${xt}">×</button><span class="hd" title="Drag to another card to link them"></span></div>`;
}
/* sessions and the Arc planner: the card linked to a session is its name and what happens in it, the same record on both pages */
const sCard = t => { const c = Link.cardOf(doc, t); return c ? {id: c, ...doc.arcs.cards[c]} : null; };
const sName = t => (sCard(t) || {}).title || "";
const arcNo = a => doc.arcs.order.indexOf(a) + 1, arcName = a => `Arc ${arcNo(a)}: ${doc.arcs.list[a].title || "Untitled arc"}`;
const arcHref = c => "arcs.html?" + new URLSearchParams({...Object.fromEntries(new URLSearchParams(location.search)), ...(c ? {card: c} : {})});
function took(map) {   // sessions took new numbers: what this page has open follows
  const to = x => map[x] || x;
  if (!Object.keys(map).length) return;
  runTab = to(runTab); for (const k in tabOf) tabOf[k] = to(tabOf[k]);
  views = {}; toast(`Renumbered: ${Object.keys(map).sort((a, b) => sessNum(a) - sessNum(b)).map(k => `${k} is now ${map[k]}`).join(", ")}. Their scenes and cards went along.`);
}
function whole(fn) {   // change the sessions and take the new numbers everywhere
  const before = {}; if (Link.has(doc)) Link.seq(doc.arcs).forEach(c => { before[c] = doc.arcs.cards[c].link; });
  const out = fn(); Link.settle(doc, CUR);
  const map = {}; Object.entries(before).forEach(([c, l]) => { const k = doc.arcs.cards[c], n = k && k.link; if (l && n && n !== l) map[l] = n; });
  took(map); return out;
}
function showTab(t) { if (runMode) { runTab = t; changed(); closeDrawer(); drawRun(); $("#run").scrollTop = 0; } else { changed(); openTab(t); } }
function addSession() {   // + Session: pick one built in the Arc planner, or a blank one
  shown = null; enter("+s", "edit", addSession);
  const A = Link.has(doc) ? doc.arcs : null, at = A ? Link.numbers(doc, CUR) : {}, next = "S" + (Math.max(CUR, ...doc.sessions.map(sessNum)) + 1);
  const arcs = A ? A.order.map(a => { const list = A.list[a].cards.filter(c => A.cards[c] && !A.cards[c].link);
    return sec(esc(arcName(a)), `<div class="pc">` + list.map(c => `<button class="pick" data-bring="${esc(c)}"><b>S${at[c]}</b><span>${esc(A.cards[c].title || "Untitled session")}${A.cards[c].text ? `<small>${esc(A.cards[c].text)}</small>` : ""}</span></button>`).join("") +
      `<button class="pick new" data-inarc="${esc(a)}"><b>+</b><span>A new session in this arc</span></button></div>`); }).join("") : "";
  const d = frame({kind: "scene", name: "Session", plain: true, title: `<h3>Add a session</h3>`, body: arcs + sec("Outside the arcs", `<div class="pc"><button class="pick new" data-blank><b>+</b><span>A blank ${esc(next)}</span></button></div>`)});
  const go = c => { const t = whole(() => Link.join(doc, c, "new", CUR)); showTab(doc.arcs.cards[c].link || t); return doc.arcs.cards[c].link; };
  d.querySelectorAll("[data-bring]").forEach(b => b.onclick = () => { go(b.dataset.bring); });
  d.querySelectorAll("[data-inarc]").forEach(b => b.onclick = () => sessPanel(go(Link.add(doc, b.dataset.inarc, "", CUR)), true));
  d.querySelector("[data-blank]").onclick = () => { doc.sessions.push(next); sortSessions(); whole(() => {}); showTab(next); };
}
function sessPanel(t, focus) {   // a session's name, what happens in it and its arc: the Arc planner's card
  if (!t || t === "Later") return;
  shown = null; const ed = enter("s:" + t, focus ? "edit" : undefined, () => sessPanel(t));
  const c = sCard(t), k = c && doc.arcs.cards[c.id], A = Link.has(doc) ? doc.arcs : null, aid = c && Link.arcOf(doc, c.id), ss = scenesIn(t);
  const arcPick = !ed ? (c ? esc(arcName(aid)) : "Not in the Arc planner")
    : c ? `<select data-arc aria-label="Arc">${A.order.map(a => `<option value="${esc(a)}" ${a === aid ? "selected" : ""}>${esc(arcName(a))}</option>`).join("")}</select>`
      : A ? `<select data-putarc aria-label="Arc"><option value="">Not in the Arc planner</option><optgroup label="A new card in">${A.order.map(a => `<option value="a:${esc(a)}">${esc(arcName(a))}</option>`).join("")}</optgroup>` +
        `<optgroup label="It is this idea, already there">${A.order.flatMap(a => A.list[a].cards.filter(x => A.cards[x] && !A.cards[x].link).map(x => `<option value="c:${esc(x)}">${esc(`${A.cards[x].title || "Untitled session"} (arc ${arcNo(a)})`)}</option>`)).join("")}</optgroup></select>` : "No arcs yet";
  const d = frame({kind: "scene", name: t + " session", title: ed && c ? `<input type="text" class="ttl" data-title aria-label="Name" value="${esc(k.title)}" placeholder="Session ${sessNum(t)}">` : `<h3>${esc(c && c.title ? c.title : t)}</h3>`,
    body: rows(row("Arc", arcPick)) + (c ? sec("What happens", ed ? `<textarea data-text aria-label="What happens" placeholder="Where it goes, what it is for">${esc(k.text)}</textarea>` : k.text ? para(k.text) : "") : "") +
      sec("Scenes", ss.length ? `<div class="pc">${ss.map(x => cardLine(x, 0, numIn(x) ? [String(numIn(x))] : ["~"])).join("")}</div>` : "", ss.length || ""),
    foot: `${c ? `<a href="${esc(arcHref(c.id))}">Arc planner</a>` : ""}${ed && doc.sessions.length > 2 ? `<button class="del" data-del>Delete</button>` : ""}`});
  if (!ed) return;
  const mine = () => { if (k.by === "claude") k.by = "tom"; };
  const del = d.querySelector("[data-del]"); if (del) del.onclick = () => delSession(t);
  if (c) {
    const nm = d.querySelector("[data-title]"), tx = d.querySelector("[data-text]"), live = fn => { fn(); mine(); changed(); draw(); };
    nm.oninput = () => live(() => { k.title = nm.value; }); tx.addEventListener("input", () => live(() => { k.text = tx.value; }));
    d.querySelector("[data-arc]").onchange = e => { const to = e.target.value;
      whole(() => { doc.arcs.list[aid].cards = doc.arcs.list[aid].cards.filter(x => x !== c.id); const arr = doc.arcs.list[to].cards; let i = 0; if (arcNo(to) < arcNo(aid)) i = arr.length; else arr.forEach((x, j) => { const l = sessNum((doc.arcs.cards[x] || {}).link); if (l && l <= CUR) i = j + 1; }); arr.splice(i, 0, c.id); mine(); });
      changed(); draw(); sessPanel(k.link, true); };
    if (focus) setTimeout(() => nm.focus(), 50);
  } else if (A) d.querySelector("[data-putarc]").onchange = e => { const v = e.target.value; if (!v) return;
    const cid = whole(() => { const id = v.startsWith("c:") ? v.slice(2) : Link.add(doc, v.slice(2), t, CUR); doc.arcs.cards[id].link = t; return id; });
    const now = doc.arcs.cards[cid].link; if (now !== t) took({[t]: now}); changed(); draw(); sessPanel(now, true); };
}
const addTab = `<button class="add" data-addsess title="Add a session: one built in the Arc planner, or a blank one">+ Session</button>`;
function sessTabs() {
  const tab = T();
  $("#sess").innerHTML = doc.sessions.map((t, i) => `<button role="tab" data-tab="${esc(t)}" aria-selected="${t === tab}" title="${esc(sName(t))}">${esc(t)}${i === 0 && t !== "Later" ? " · next" : ""}<small>${inTab(t).length}</small>` +
    (t === tab && t !== "Later" && doc.sessions.length > 2 ? `<span class="dx" data-delsess title="Delete this session" aria-label="Delete ${esc(t)}">×</span>` : "") + `</button>`).join("") +
    addTab;
  $$("#sess [data-tab]").forEach(b => b.onclick = ev => { if (ev.target.closest("[data-delsess]")) delSession(b.dataset.tab); else openTab(b.dataset.tab); });
  $("#sess [data-addsess]").onclick = addSession;
  const sn = $("#sname"); sn.hidden = tab === "Later"; sn.innerHTML = snHtml(tab); sn.onclick = () => sessPanel(tab);
}
const snHtml = t => { const c = sCard(t); return `<b>${esc(t)}</b>${c ? esc(c.title || "No name yet") : "<i>Not in the Arc planner</i>"}${c ? `<small>Arc ${arcNo(Link.arcOf(doc, c.id))}</small>` : ""}<span class="pen">✎</span>`; };
function delSession(t) {   // on every board
  const n = sessNum(t), ids = Object.keys(doc.items).filter(i => sessOf(i) === t);
  const plans = ids.filter(i => i.startsWith("p:") && live(i)), cards = ids.filter(i => i.startsWith("c:"));
  const what = [plans.length ? `its ${plans.length} plan${plans.length > 1 ? "s go" : " goes"} back to the tray` : "", cards.length ? `your ${cards.length} card${cards.length > 1 ? "s move" : " moves"} to Later` : ""].filter(Boolean).join(" and ");
  const c = sCard(t), later = c ? [] : doc.sessions.filter(x => sessNum(x) > n && !sCard(x));   // sessions on no card count down themselves; the rest follow their cards
  if (!confirm(`Delete ${t} on every board?` + (what ? ` ${what[0].toUpperCase() + what.slice(1)}.` : "") + (c ? ` “${c.title || "Its card"}” stays in the Arc planner as an idea.` : "") + (!c && doc.sessions.some(x => sessNum(x) > n) ? " The sessions after it move up one." : ""))) return;
  plans.forEach(erase);
  Object.values(doc.items).forEach(o => { if (o.s === t) { o.s = "Later"; o.at = {}; } });
  Object.values(doc.items).forEach(o => { const so = o.scene && it(o.scene); if (so) o.s = so.s; });
  doc.edges = doc.edges.filter(e => e.from !== "start:" + t);
  const all = doc.sessions, at = all.indexOf(t);
  doc.sessions = doc.sessions.filter(x => x !== t); delete doc.order[t];
  if (c) doc.arcs.cards[c.id].link = "";
  else if (later.length || Link.has(doc)) {
    const solo = new Set(later), linked = {}; doc.sessions.forEach(x => { const k = sCard(x); if (k && sessNum(x) > n) linked[x] = k.id; });
    const down = x => solo.has(x) || linked[x] ? "S" + (sessNum(x) - 1) : x;
    Object.values(linked).forEach(id => { doc.arcs.cards[id].link = down(doc.arcs.cards[id].link); });
    doc.sessions = doc.sessions.map(down);
    Object.values(doc.items).forEach(o => { o.s = down(o.s); });
    doc.edges.forEach(e => { if (e.from.startsWith("start:")) e.from = "start:" + down(e.from.slice(6)); });
    const ord = {}; for (const k in doc.order) ord[down(k)] = doc.order[k]; doc.order = ord;
  }
  whole(() => {});
  views = {}; const there = doc.sessions[Math.min(at, Math.max(0, doc.sessions.length - 2))]; tabOf[lane] = there; runTab = there === "Later" ? runTab : there;
  changed(); closeDrawer(); draw(); if (!runMode) fit();
}
function erase(id) {   // off every board; what it held stays, on its home boards
  if (isScene(id)) membersOf(id).forEach(m => release(m));
  delete doc.items[id]; doc.edges = doc.edges.filter(e => e.from !== id && e.to !== id);
  if (id.startsWith("c:")) delete doc.cards[id.slice(2)];
}
function unplace(pid) { erase("p:" + pid); changed(); closeDrawer(); draw(); }
const names = ks => (ks.some(k => k !== WHOLE) ? ks.filter(k => k !== WHOLE) : ks).map(boardName).join(", ").replace(/, ([^,]*)$/, " and $1");
function deleteCard(id) {
  const c = doc.cards[id.slice(2)], ks = lanesOf(id);
  if (!c || ((c.title || c.text || ks.length > 1) && !confirm(`Delete “${c.title || "this card"}”${ks.length > 1 ? ` from ${names(ks)}` : ""}? This cannot be undone.`))) return;
  erase(id); changed(); closeDrawer(); draw();
}
function setPresent(id, list) {
  if (id.startsWith("c:")) { doc.cards[id.slice(2)].present = list; return; }
  const pid = id.slice(2), e = {...(doc.edits[pid] || {}), present: list}; doc.edits[pid] = e;
}
function takeOff(id, k = lane) {   // the × on a card, or a drag to the tray
  const o = it(id), ks = sceneOf(id) ? [] : lanesOf(id);
  if (k === WHOLE || runMode) {   // the whole session: off it means off every board
    const on = ks.filter(x => x !== WHOLE);
    if (id.startsWith("c:")) deleteCard(id);
    else if (!on.length || confirm(`Take “${titleOf(id)}” out of ${sessOf(id)}? It goes back to the tray, off ${names(on)}.`)) unplace(id.slice(2));
    return;
  }
  if (ks.length > 1) {
    const rest = ks.filter(x => x !== k);
    if (isScene(id)) {
      const on = membersOf(id).filter(m => charsOn(m).includes(k));
      if (on.length) { toast(`${shortOf(k)} is on ${on.length > 1 ? "cards" : "a card"} in “${titleOf(id)}”: ${on.map(titleOf).join(", ")}. Take them off there first.`); return; }
      const cast = castLanes(id).includes(k), whole = D.lanes.find(l => l.key === k).kind === "party";
      if (!confirm(`Take “${titleOf(id)}” off ${boardName(k)}?${cast && !whole ? ` ${shortOf(k)} comes off who is present.` : ""} It stays on ${names(rest)}.`)) return;
      if (cast) {
        const list = [...new Set((objOf(id).present || []).flatMap(n => pcOf(n) === "party" ? PCS.map(p => p.key) : [n]))];
        setPresent(id, list.filter(n => pcOf(n) !== k));
      }
    }
    o.homes = o.homes.filter(x => x !== k); delete o.at[k]; if (!o.born || o.born === k) o.born = rest[0];
    changed(); closeDrawer(); draw(); return;
  }
  if (id.startsWith("p:")) unplace(id.slice(2)); else deleteCard(id);
}
const removeCard = id => { if (it(id)) takeOff(id); };
function dropPlan(pid) { doc.edits[pid] = {...(doc.edits[pid] || {}), drop: true}; if (it("p:" + pid)) unplace(pid); else { changed(); closeDrawer(); draw(); } }
const sceneSig = () => $$("#nodes .bn.scene").map(e => e.dataset.id).sort().join();
const keepView = () => { views[lane + "|" + T()] = {...view, sig: sceneSig()}; };
function backTo() {   // where this board was left, or all of it when a scene joined or left since
  const v = views[lane + "|" + T()]; if (v && v.sig === sceneSig()) { view = {x: v.x, y: v.y, k: v.k}; applyView(); } else fit();
}
function openTab(t) {
  keepView(); tabOf[lane] = t; closeDrawer(); draw(); backTo();
}
function genEdges() {   // every link between placed items: the vault's, then Tom's own
  const out = [];
  for (const id of Object.keys(doc.items)) {
    if (!id.startsWith("p:") || !live(id)) continue;
    const p = view_of(id.slice(2));
    p.req.forEach(r => { if ((r.k === "plan" || r.k === "played") && live("p:" + r.a)) out.push({from: "p:" + r.a, to: id, label: "then"}); });
    if (p.kind === "exit") p.leads.forEach(t => { if (live("p:" + t)) out.push({from: id, to: "p:" + t, label: "", opt: 1}); });
    if (p.kind === "decision") p.options.forEach(o => { if (o.to && live("p:" + o.to)) out.push({from: id, to: "p:" + o.to, label: o.label, opt: 1}); });
  }
  const pair = e => e.from + ">" + e.to, same = (a, b) => lc(a.label) === lc(b.label);
  const opts = out.filter(e => e.opt), needs = out.filter(e => !e.opt), choosing = e => kindOf(e.from) === "decision";
  const own = doc.edges.filter(e => live(e.to) && (choosing(e) ? !opts.some(o => pair(o) === pair(e) && same(o, e)) : !out.some(o => pair(o) === pair(e)))).map(e => ({...e, own: 1}));
  /* from a decision, each link is an option, so the bare "needs" between two cards goes when an option joins them */
  return [...opts, ...needs.filter(e => !opts.some(o => pair(o) === pair(e)) && !(choosing(e) && own.some(o => pair(o) === pair(e)))), ...own];
}
/* A decision's options. Each one is a choice and its outcome: a card (a link out of the decision), or only words, listed on the decision itself.
   Tom's links are edges. The rest is on the card (options: label, text) or in the plan's own list (to, label, text), which edits can replace. */
const optsSaved = id => (id.startsWith("c:") ? (doc.cards[id.slice(2)] || {}).options : (view_of(id.slice(2)) || {}).options) || [];
function optRows(id) {
  const es = live(id) ? genEdges().filter(e => e.from === id && live(e.to)) : [], plan = id.startsWith("p:");
  return [...optsSaved(id).map((o, i) => ({i, to: o.to ? "p:" + o.to : "", label: o.label || "", text: o.text || "", off: !!o.to && !(live(id) && live("p:" + o.to))})),
    ...es.filter(e => e.own).map(e => ({e: e.id, to: e.to, label: e.label, text: "", own: 1})),
    ...es.filter(e => !e.own && !e.opt).map(e => ({need: 1, to: e.to, label: "", text: ""}))].sort((a, b) => !a.to - !b.to);   // the ones that are only listed come last
}
function optionsOf(id) {   // a decision's options, or where an exit leads; off: the vault lists it, but that plan is not on the boards
  if (kindOf(id) === "decision") return optRows(id).map(o => ({...o, id: o.e}));
  const on = live(id) ? genEdges().filter(e => e.from === id && live(e.to)).map(e => ({to: e.to, label: e.label === "then" ? "" : e.label, own: e.own, id: e.id})) : [];
  const q = id.startsWith("p:") && P[id.slice(2)], off = q && kindOf(id) === "exit" ? q.leads.filter(t => !live(id) || !live("p:" + t)).map(t => ({to: "p:" + t, label: "", off: 1})) : [];
  return on.concat(off);
}
const outOf = o => o.to ? titleOf(o.to) : o.text || "";
const optsHtml = id => { const os = optionsOf(id);
  if (kindOf(id) === "exit") return os.length ? `<ul class="opts">${os.map(o => `<li class="ld${o.off ? " off" : ""}">→ ${esc(titleOf(o.to))}${sessOf(o.to) && sessOf(o.to) !== sessOf(id) ? ` <span class="to">${esc(sessOf(o.to))}</span>` : ""}${o.off ? ' <span class="to">(not placed)</span>' : ""}</li>`).join("")}</ul>`
    : (objOf(id).who || []).length ? "" : `<div class="s"><i>Where it leads: link it to the next scene.</i></div>`;
  return (os.length ? `<ul class="opts">${os.map(o => `<li${o.off ? ' class="off"' : ""}>${o.label ? esc(o.label) : "<i>choice not named</i>"}${outOf(o) ? ` <span class="to">${o.to ? "→" : ":"} ${esc(outOf(o))}${o.off ? " (not placed)" : ""}</span>` : ""}</li>`).join("")}</ul>` : "") +
    `<div><button class="addo" title="Add an option: a choice and its outcome">+ option</button></div>`; };
const HEAD = 12, OUT = {r: [1, 0], l: [-1, 0], b: [0, 1], t: [0, -1]}, within = (v, lo, hi) => Math.min(Math.max(v, lo), Math.max(lo, hi));
function sides(a, b) {   // the sides two cards face each other on: where a link leaves, and where it comes in
  if (b.x - (a.x + a.w) >= 30) return ["r", "l"];
  if (b.y - (a.y + a.h) >= 18) return ["b", "t"];
  if (a.y - (b.y + b.h) >= 18) return ["t", "b"];
  if (a.x - (b.x + b.w) >= 30) return ["l", "r"];
  return ["r", "l"];
}
function port(b, side, to, shift) {   // the spot on that side nearest to where the link comes from
  if (side === "l" || side === "r") return {x: side === "l" ? b.x : b.x + b.w, y: within(to.y + shift, b.y + 14, b.y + Math.min((b.sc ? b.hh : b.h) - 14, 120))};
  return {x: within(to.x + shift, b.x + 24, b.x + b.w - 24), y: side === "t" ? b.y : b.y + b.h};
}
function curve(a, b, inside, off = 0, head = HEAD) {   // off: how far to fan out, when several links join the same two cards
  const unit = (x, y) => { const n = Math.hypot(x, y) || 1; return [x / n, y / n]; }, r = v => Math.round(v * 10) / 10;
  let p0, tip, u, c1, c2, base;
  if (inside) {   // a scene to a card inside it: down from the header, along the scene's edge
    p0 = {x: a.x + 8, y: a.y + a.hh}; tip = {x: b.x, y: b.y + Math.min(b.h / 2, 40)}; u = [1, 0];
    base = {x: tip.x - head, y: tip.y}; c1 = {x: p0.x, y: tip.y}; c2 = c1;
  } else {
    const [so, si] = sides(a, b), out = OUT[so], inn = OUT[si].map(v => -v);
    p0 = port(a, so, {x: a.x + a.w / 2, y: a.y + Math.min(a.h / 2, 56)}, off / 5); tip = port(b, si, p0, off / 4);
    const s = unit(tip.x - p0.x, tip.y - p0.y), per = [-s[1], s[0]], far = Math.hypot(tip.x - p0.x, tip.y - p0.y);
    const reach = s[0] * out[0] + s[1] * out[1] < .1 ? 90 : within(far * .42, 24, 170);
    c1 = {x: p0.x + out[0] * reach + per[0] * off, y: p0.y + out[1] * reach + per[1] * off};
    const v = unit(inn[0] * reach - per[0] * off, inn[1] * reach - per[1] * off), m = unit(v[0] + s[0] * .6, v[1] + s[1] * .6);
    u = m[0] * inn[0] + m[1] * inn[1] > .35 ? m : inn;   // the way the line arrives: the arrowhead lies along it
    base = {x: tip.x - u[0] * head, y: tip.y - u[1] * head};
    const back = Math.max(reach - head, 12); c2 = {x: base.x - u[0] * back, y: base.y - u[1] * back};
  }
  const mid = k => (p0[k] + 3 * c1[k] + 3 * c2[k] + base[k]) / 8, w = head * .46;
  return {d: `M${r(base.x)},${r(base.y)} C${r(c2.x)},${r(c2.y)} ${r(c1.x)},${r(c1.y)} ${r(p0.x)},${r(p0.y)}`,   // from the arrowhead back, so a dash always touches it
    head: `${r(tip.x)},${r(tip.y)} ${r(base.x - u[1] * w)},${r(base.y + u[0] * w)} ${r(base.x + u[1] * w)},${r(base.y - u[0] * w)}`,
    mx: inside ? (p0.x + tip.x) / 2 : mid("x"), my: inside ? tip.y - 14 : mid("y")};
}
function wires(temp) {
  const tab = T(), ti = doc.sessions.indexOf(tab), order = x => doc.sessions.indexOf(x), here = id => live(id) && onBoard(id);
  let svg = "", labels = "";
  const carried = new Set(), es = genEdges(), count = {}, seen = {};
  es.forEach(e => { const k = e.from + ">" + e.to; count[k] = (count[k] || 0) + 1; });
  es.forEach(e => {
    const key = e.from + ">" + e.to, nth = seen[key] = (seen[key] ?? -1) + 1;
    if (e.from.startsWith("start")) { if (e.lane && e.lane !== lane && lane !== WHOLE) return; e = {...e, from: "start"}; }
    if (!here(e.to) || (e.from !== "start" && !here(e.from))) return;
    const fs = e.from === "start" ? tab : sessOf(e.from), ts = sessOf(e.to);
    if (ts !== tab) return;
    let from = e.from, lab = e.label, cls = e.own ? "own" : e.opt ? "opt" : "";
    if (fs !== tab) {   // from an earlier session: it comes in through this tab's start card
      if (order(fs) > ti || carried.has(e.to)) return;
      carried.add(e.to); from = "start"; lab = `after ${titleOf(e.from)} (${fs})`; cls = "carry";
    }
    const a = box(from), b = box(e.to); if (!a || !b) return;
    const c = curve(a, b, a.sc && sceneOf(e.to) === from, (nth - (count[key] - 1) / 2) * 60);
    svg += `<path class="${cls}" d="${c.d}"/><polygon class="${cls}" points="${c.head}"/>`;
    if (e.own && from === e.from) svg += `<path class="hit" data-edge="${esc(e.id)}" d="${c.d}"/>`;
    if (lab || e.own) labels += `<div class="wl ${e.own && from === e.from ? "own" : ""}" ${e.own && from === e.from ? `data-edge="${esc(e.id)}"` : ""} style="left:${c.mx}px;top:${c.my}px">${esc(lab || "add a label")}</div>`;
  });
  if (lane === WHOLE && tab !== "Later") fixedIn(tab).forEach((s, i, all) => {   // the running order, scene to scene, under everything else; floating scenes are not in it
    const a = i && box(all[i - 1]), b = i && box(s); if (a && b) svg = `<path class="run" d="${curve(a, b, false, 0, 0).d}"/>` + svg;
  });
  if (temp) svg += `<path class="temp" d="${temp}"/>`;
  $("#wires").innerHTML = svg;
  $$("#nodes .wl").forEach(x => x.remove());
  $("#nodes").insertAdjacentHTML("beforeend", labels);
  $$("[data-edge]").forEach(x => { x.onpointerdown = ev => ev.stopPropagation(); x.onclick = ev => { ev.stopPropagation(); edgeEditor(x.dataset.edge); }; });
}

/* ---------- tray: the plans that are not placed, the same beside every canvas and the Running order ----------
   The filter, the way most list filters work: in each group pick what to match, joined by OR or AND (AND where a plan can have several);
   click a choice again to leave those plans out; the groups themselves join by AND or OR. A choice left out is kept as "!value". */
const FGROUPS = ["who", "sess", "kind", "sec", "st"], FMANY = ["who", "sess"];   // FMANY: a plan can have more than one of these
let tq = "", tOpen = false, tAll = false, tf = {}; try { tf = JSON.parse(store.get("osse-paths-filter") || "{}"); } catch (e) {}
[...FGROUPS, "and"].forEach(g => { if (!Array.isArray(tf[g])) tf[g] = []; });   // and: the groups joined by AND
function namesHere(t) {   // everyone and everywhere this session's scenes and cards already name, player characters aside
  const out = new Set();
  Object.keys(doc.items).filter(i => live(i) && sessOf(i) === t).forEach(i => { const o = objOf(i);
    [...(o.present || []), ...(o.who || []), o.where, o.reveals, ...(i.startsWith("p:") ? P[i.slice(2)].names : [])].forEach(n => { if (n && !pcOf(n)) out.add(lc(n)); }); });
  return out;
}
const secretsOf = p => [...new Set([...secReq(p).map(r => r.a), ...(p.kind === "reveal" && p.reveals ? [p.reveals] : [])])];
const fIn = g => tf[g].filter(v => v[0] !== "!"), fOut = g => tf[g].filter(v => v[0] === "!").map(v => v.slice(1));
function passes(p, near) {
  const v = view_of(p.id), t = p.target.toUpperCase(), is = {
    who: k => p.lanes.includes(k) || p.pcs.includes(k), kind: k => (v.kind || "beat") === k,
    sess: s => s === "@this" ? t === T().toUpperCase() : s === "@near" ? p.names.some(n => near.has(lc(n))) : s === "@none" ? !t : t === s,
    sec: s => (s === "yes") === !!secretsOf(v).length, st: s => (s === "ready") === (p.status === "ready")};
  if (tq && !lc(p.id + " " + v.summary).includes(lc(tq))) return false;
  const used = FGROUPS.filter(g => tf[g].length), ok = g => { const a = fIn(g); return (!a.length || (tf.and.includes(g) ? a.every(is[g]) : a.some(is[g]))) && !fOut(g).some(is[g]); };
  return !used.length || (tf.any ? used.some(ok) : used.every(ok));
}
function trayUi(host) {   // once for each place it stands
  host.innerHTML = `<div class="trayh"><b>Not placed yet</b><small class="tn"></small><label class="all"><input type="checkbox" class="tall"> every live plan</label></div>` +
    `<div class="tqr"><input type="search" class="tq" placeholder="Find a plan" autocomplete="off"><button class="tfb" aria-expanded="false" title="Filter">${icon("filter", 14)}<span>Filter</span><b></b></button></div><div class="tfp" hidden></div><div class="tfa"></div><div class="tlist"></div>`;
  const q = host.querySelector(".tq"); q.oninput = () => { tq = q.value.trim(); tray(); };
  host.querySelector(".tall").onchange = e => { tAll = e.target.checked; tray(); };
  host.querySelector(".tfb").onclick = () => { tOpen = !tOpen; tray(); };
}
const keepF = () => { store.set("osse-paths-filter", JSON.stringify(tf)); tray(); };
function flipF(g, v) {   // off, matched, left out, off
  tf[g] = tf[g].includes(v) ? tf[g].map(x => x === v ? "!" + v : x) : tf[g].includes("!" + v) ? tf[g].filter(x => x !== "!" + v) : [...tf[g], v]; keepF();
}
function clearF() { [...FGROUPS, "and"].forEach(g => { tf[g] = []; }); delete tf.any; keepF(); }
const orAnd = (on, attr) => `<span class="oa" role="group">${["or", "and"].map(w => `<button data-oa="${w}" ${attr} aria-pressed="${(w === "and") === on}">${w}</button>`).join("")}</span>`;
function tray() {
  const host = $(runMode ? "#loose [data-tray]" : "#tray [data-tray]"), one = !runMode && lane !== WHOLE, t = T(), el = c => host.querySelector(c);
  const base = Object.values(P).filter(p => { const id = "p:" + p.id, o = it(id); if ((doc.edits[p.id] || {}).drop) return false;
    return one ? !(o && lanesOf(id).includes(lane)) && (tAll || (!(o && sceneOf(id)) && p.lanes.includes(lane))) : !o; });
  const near = tf.sess.some(s => s.includes("@near")) ? namesHere(t) : null, list = base.filter(p => passes(p, near)), n = FGROUPS.reduce((x, g) => x + tf[g].length, 0), has = (g, v) => tf[g].includes(v) || tf[g].includes("!" + v);
  const targets = [...new Set(Object.values(P).map(p => p.target.toUpperCase()).filter(Boolean))].sort((a, b) => sessNum(a) - sessNum(b));
  const wl = k => k === WHOLE ? "The Party" : (D.lanes.find(l => l.key === k) || {}).short || k;
  const groups = {
    who: ["Who", D.lanes.map(l => [l.key, l.short, l.kind === "pc" ? `--c:${l.colour}` : ""])],
    sess: ["Session", [["@this", `Aimed at ${t}`], ["@near", `Names someone or somewhere in ${t}`], ...targets.filter(x => x !== t || has("sess", x)).map(x => [x, x]), ["@none", "No session"]]],
    kind: ["Type", PLANKINDS.filter(k => base.some(p => (view_of(p.id).kind || "beat") === k) || has("kind", k)).map(k => [k, KINDS[k], "", kic(k)])],
    sec: ["Secret", [["yes", "Tied to a secret"], ["no", "No secret"]]],
    st: ["Status", [["ready", "Ready"], ["draft", "Not ready"]]]};
  const label = (g, v) => g === "who" ? wl(v) : (groups[g][1].find(x => x[0] === v) || [0, v])[1];
  el(".tn").textContent = n || tq ? `${list.length} of ${base.length}` : base.length;
  el(".all").hidden = !one; el(".tall").checked = tAll; if (el(".tq").value.trim() !== tq) el(".tq").value = tq;
  const fb = el(".tfb"); fb.setAttribute("aria-expanded", tOpen); fb.classList.toggle("on", !!n); fb.querySelector("b").textContent = n || "";
  const fp = el(".tfp"), fy = fp.scrollTop; fp.hidden = !tOpen;
  if (tOpen) fp.innerHTML = Object.entries(groups).map(([g, [lab, vs]]) => `<div class="tfg"><span>${lab}${FMANY.includes(g) ? orAnd(tf.and.includes(g), `data-og="${g}"`) : ""}</span><div>${vs.map(([v, txt, st, ic]) => `<button class="tfc${tf[g].includes(v) ? " on" : tf[g].includes("!" + v) ? " not" : ""}${st ? " pc" : ""}${g === "kind" ? " k-" + v : ""}" aria-pressed="${tf[g].includes(v)}" data-g="${g}" data-v="${esc(v)}" title="Click: match. Again: leave out. Again: off"${st ? ` style="${esc(st)}"` : ""}>${ic || ""}${esc(txt)}</button>`).join("")}</div></div>`).join("") +
    `<div class="tfe"><span class="btw">Between groups ${orAnd(!tf.any, `data-og="*"`)}</span>${n ? `<button class="mini" data-clearf>Clear</button>` : ""}<button class="mini" data-closef>Close</button></div>`;
  fp.scrollTop = fy;
  const word = w => `<i class="jo">${w}</i>`;   // the filter in one line, as it reads
  el(".tfa").innerHTML = n && !tOpen ? FGROUPS.filter(g => tf[g].length).map(g => { const chip = (v, no) => `<button class="tfc ${no ? "not" : "on"}" data-off="${esc((no ? "!" : "") + v)}" data-fg="${g}" title="Remove this filter">${no ? "not " : ""}${esc(label(g, v))} ×</button>`;
    return [fIn(g).map(v => chip(v)).join(word(tf.and.includes(g) ? "and" : "or")), ...fOut(g).map(v => chip(v, 1))].filter(Boolean).join(word("and")); }).join(word(tf.any ? "or" : "and")) + (n > 1 ? `<button class="tfc" data-clearf>Clear</button>` : "") : "";
  host.querySelectorAll("[data-g]").forEach(b => b.onclick = () => flipF(b.dataset.g, b.dataset.v));
  host.querySelectorAll("[data-off]").forEach(b => b.onclick = () => { const g = b.dataset.fg; tf[g] = tf[g].filter(x => x !== b.dataset.off); keepF(); });
  host.querySelectorAll("[data-oa]").forEach(b => b.onclick = () => { const g = b.dataset.og, and = b.dataset.oa === "and"; if (g === "*") { if (and) delete tf.any; else tf.any = 1; } else tf.and = [...tf.and.filter(x => x !== g), ...(and ? [g] : [])]; keepF(); });
  host.querySelectorAll("[data-clearf]").forEach(b => b.onclick = clearF);
  const cl = el("[data-closef]"); if (cl) cl.onclick = () => { tOpen = false; tray(); };
  const elsewhere = p => { const id = "p:" + p.id, sc = it(id) && sceneOf(id); return !it(id) ? "" : `<span class="ch move">${esc(sc ? `in “${titleOf(sc)}”` : `on ${names(lanesOf(id))}`)} · ${esc(sessOf(id))}</span>`; };
  let h = "";
  PLANKINDS.forEach(k => {
    const ps = list.filter(p => (view_of(p.id).kind || "beat") === k).sort((a, b) => (a.status !== "ready") - (b.status !== "ready") || a.id.localeCompare(b.id));
    if (!ps.length) return;
    h += `<h4>${kic(k)}${KINDS[k]}s</h4>` + ps.map(p => `<div class="ti k-${esc(k)}" data-plan="${esc(p.id)}"><span class="g rg" title="Drag it into place, or onto a session tab">⠿</span><div>` +
      `<div class="t">${esc(p.id)}</div><div class="s">${esc(view_of(p.id).summary)}</div><div class="chips">${p.status === "ready" ? '<span class="ch ready">ready</span>' : ""}${p.target ? `<span class="ch">${esc(p.target)}</span>` : ""}${one ? "" : laneTags(p.lanes)}${everyPc(p.lanes) || p.lanes.includes(WHOLE) ? "" : PCS.filter(l => p.pcs.includes(l.key) && !p.lanes.includes(l.key)).map(l => `<span class="pcx" style="--c:${esc(l.colour)}" title="Named in it">${esc(l.short)}</span>`).join("")}${elsewhere(p)}` +
      secReq(p).map(r => `<span class="ch">secret: ${esc(r.a)}</span>`).join("") + `</div></div></div>`).join("");
  });
  if (!h) h = `<p class="empty">${base.length ? "No plan matches. Change the search or the filters." : one ? `Every plan for this board is placed.${tAll ? "" : " Tick “every live plan” to pull one from another board, or add a card."}` : "Every live plan is placed."}</p>`;
  const gone = Object.keys(doc.edits).filter(id => doc.edits[id].drop && P[id]);
  if (gone.length) h += `<h4>Dropped here</h4>` + gone.map(id => `<div class="gone"><s>${esc(id)}</s><button class="mini" data-undrop="${esc(id)}">Undo</button></div>`).join("") +
    `<p class="empty" style="font-size:13px">Claude marks these dropped in the vault when you bring the board in.</p>`;
  const tl = el(".tlist"), y = tl.scrollTop; tl.innerHTML = h; tl.scrollTop = y;
  tl.querySelectorAll("[data-undrop]").forEach(b => b.onclick = () => { const e = doc.edits[b.dataset.undrop]; delete e.drop; if (!Object.keys(e).length) delete doc.edits[b.dataset.undrop]; changed(); tray(); });
  tl.querySelectorAll(".ti").forEach(x => runMode ? cardDrag(x, "p:" + x.dataset.plan) : trayDrag(x));
}

/* ---------- view: pan and zoom; the grid moves with it ---------- */
const board = $("#board"), pts = new Map();
const cap = (el, id) => { try { el.setPointerCapture(id); } catch (e) {} };
function applyView() {
  $("#world").style.transform = `translate(${view.x}px,${view.y}px) scale(${view.k})`;
  const g = GRID * view.k;
  board.style.backgroundSize = `${g}px ${g}px`;
  board.style.backgroundPosition = `${view.x - g / 2}px ${view.y - g / 2}px`;
}
function toWorld(cx, cy) { const r = board.getBoundingClientRect(); return {x: (cx - r.left - view.x) / view.k, y: (cy - r.top - view.y) / view.k}; }
function zoomAt(k, cx, cy) {
  const r = board.getBoundingClientRect(); k = Math.min(2, Math.max(.2, k));
  const px = cx - r.left, py = cy - r.top;
  view.x = px - (px - view.x) * k / view.k; view.y = py - (py - view.y) * k / view.k; view.k = k; applyView();
}
function fit() {
  const r = board.getBoundingClientRect(), bs = ["start", ...$$("#nodes .bn").map(e => e.dataset.id)].map(i => box(i)).filter(Boolean);
  const x0 = Math.min(...bs.map(b => b.x)) - 30, y0 = Math.min(...bs.map(b => b.y)) - 30;
  const x1 = Math.max(...bs.map(b => b.x + b.w)) + 40, y1 = Math.max(...bs.map(b => b.y + b.h)) + 40;
  const k = Math.min(1, Math.max(.2, Math.min((r.width - 20) / (x1 - x0), (r.height - 58) / (y1 - y0))));
  view = {k, x: 10 - x0 * k, y: 48 - y0 * k}; applyView();   // clear of the buttons at the top right
}
let pan = null;
board.addEventListener("pointerdown", e => {
  if (e.target.closest(".bn,.wl,.float,.sname,.keyp")) return;
  cap(board, e.pointerId); pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
  if (pts.size === 1) pan = {x: e.clientX, y: e.clientY, vx: view.x, vy: view.y};
  if (pts.size === 2) { const [a, b] = [...pts.values()]; pan = {pinch: Math.hypot(a.x - b.x, a.y - b.y), k: view.k}; }
  board.classList.add("panning");
});
board.addEventListener("pointermove", e => {
  if (!pts.has(e.pointerId) || !pan) return;
  pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
  if (pts.size === 2 && pan.pinch) { const [a, b] = [...pts.values()]; zoomAt(pan.k * Math.hypot(a.x - b.x, a.y - b.y) / pan.pinch, (a.x + b.x) / 2, (a.y + b.y) / 2); }
  else if (!pan.pinch) { view.x = pan.vx + e.clientX - pan.x; view.y = pan.vy + e.clientY - pan.y; applyView(); }
});
const endPan = e => { pts.delete(e.pointerId); if (!pts.size) { pan = null; board.classList.remove("panning"); } };
board.addEventListener("pointerup", endPan); board.addEventListener("pointercancel", endPan);
board.addEventListener("wheel", e => {
  if (e.target.closest(".keyp")) return;
  e.preventDefault();
  if (e.ctrlKey || e.metaKey) zoomAt(view.k * Math.exp(-e.deltaY / 300), e.clientX, e.clientY);
  else { view.x -= e.deltaX; view.y -= e.deltaY; applyView(); }
}, {passive: false});
board.addEventListener("dblclick", e => { if (!e.target.closest(".bn,.wl,.float,.sname,.keyp")) { const w = toWorld(e.clientX, e.clientY); newCard(w.x - CARDW / 2, w.y - 30); } });

/* ---------- cards: drag, link, open ---------- */
const inRect = (e, el) => { const r = el.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom; };
const tabUnder = e => $$("#sess [data-tab]").find(b => inRect(e, b));
function bindNodes() {
  $$("#nodes .bn").forEach(el => {
    const id = el.dataset.id;
    if (id === "start") {
      el.querySelector(".hd")?.remove();
      el.insertAdjacentHTML("beforeend", '<span class="hd" title="Drag to a card: it follows from here"></span>');
      el.querySelector(".hd").addEventListener("pointerdown", ev => link(ev, id));
      el.onpointerdown = ev => { if (!ev.target.closest("a,.hd")) ev.stopPropagation(); };
      return;
    }
    el.querySelector(".hd").addEventListener("pointerdown", ev => link(ev, id));
    const xx = el.querySelector(".xx"); xx.onpointerdown = ev => ev.stopPropagation(); xx.onclick = ev => { ev.stopPropagation(); removeCard(id); };
    const tk = el.querySelector("[data-tick]"); if (tk) { tk.onpointerdown = ev => ev.stopPropagation(); tk.onclick = ev => { ev.stopPropagation(); tick(id, ev.shiftKey ? -1 : 1); }; }
    el.querySelectorAll(".any [data-card]").forEach(r => rowDrag(r, r.dataset.card)); if (isScene(id)) tips(el);
    const ax = el.querySelector("[data-anyx]"); if (ax) { ax.onpointerdown = ev => ev.stopPropagation(); ax.onclick = ev => { ev.stopPropagation(); flipAny(id); }; }
    const ao = el.querySelector(".addo"); if (ao) { ao.onpointerdown = ev => ev.stopPropagation(); ao.onclick = ev => { ev.stopPropagation(); addOption(id); }; }
    const rz = el.querySelector(".rz"); if (rz) rz.addEventListener("pointerdown", ev => resize(ev, el, id));
    el.addEventListener("pointerdown", ev => {
      if (ev.target.closest(".hd,.xx,.rz,.rng,.any,.addo,a")) return;
      ev.stopPropagation();
      const b = box(id), st = {x: ev.clientX, y: ev.clientY}, sc = isScene(id); let moved = false, nx = b.x, ny = b.y;
      const els = $$("#nodes .bn"), mem = sc ? flowOf(id).map(m => [m, els.find(x => x.dataset.id === m)]) : [];
      cap(el, ev.pointerId);
      const mv = e => {
        const dx = (e.clientX - st.x) / view.k, dy = (e.clientY - st.y) / view.k;
        if (!moved && Math.hypot(dx, dy) < 5) return;
        moved = true; el.classList.add("drag");
        nx = Math.round(b.x + dx); ny = Math.round(b.y + dy); setPos(id, nx, ny);
        el.style.left = nx + "px"; el.style.top = ny + "px";
        mem.forEach(([m, me]) => { if (me) { const mb = box(m); me.style.left = mb.x + "px"; me.style.top = mb.y + "px"; } });
        if (!sc) { const hd = headAt(e), hot = hd ? null : sceneAt(id); hotHead(hd); els.forEach(x => x.classList.toggle("hot", x.dataset.id === hot)); }
        wires();
        $("#tray").classList.toggle("over", id.startsWith("p:") && inRect(e, $("#tray")));
        const tb = tabUnder(e); $$("#sess button").forEach(x => x.classList.toggle("drop", x === tb && tb.dataset.tab !== T()));
      };
      const up = e => {
        el.removeEventListener("pointermove", mv); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
        $("#tray").classList.remove("over"); $$("#sess button").forEach(x => x.classList.remove("drop"));
        if (!moved) { open(id); return; }
        if (id.startsWith("p:") && inRect(e, $("#tray"))) { setPos(id, b.x, b.y); draw(); takeOff(id); return; }
        const tb = tabUnder(e);
        if (tb && tb.dataset.tab !== T()) { setPos(id, b.x, b.y); moveTo(id, tb.dataset.tab); return; }
        const hd = !sc && headAt(e); if (hd) { setPos(id, b.x, b.y); toAny(id, hd, rowUnder(e)); return; }
        nx = snap(nx); ny = snap(ny); setPos(id, nx, ny);
        if (sc) capture(id); else settle(id, nx, ny);
        changed(); draw();
      };
      el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    });
  });
}
const headAt = e => { if (!inRect(e, board)) return null; const w = toWorld(e.clientX, e.clientY);   // the scene whose header is under the pointer
  return inTab(T()).filter(isScene).find(i => { const b = box(i); return b && w.x > b.x && w.x < b.x + b.w && w.y > b.y && w.y < b.y + b.hh + 6; }) || null; };
const hotHead = sid => $$("#nodes .bn.scene").forEach(x => x.classList.toggle("anyhot", x.dataset.id === sid));
const rowUnder = e => { const r = document.elementsFromPoint(e.clientX, e.clientY).map(x => x.closest && x.closest(".any [data-card]")).find(Boolean); return r ? r.dataset.card : null; };
function rowDrag(el, id) {   // a row of a scene's Any time section: click opens it; drag moves it
  el.addEventListener("pointerdown", ev => {
    ev.stopPropagation(); if (ev.button > 0) return;
    const st = {x: ev.clientX, y: ev.clientY}; let ghost = null;
    watch(e => {
      if (!ghost) {
        if (Math.hypot(e.clientX - st.x, e.clientY - st.y) < 5) return;
        ghost = document.createElement("div"); ghost.className = `bn ghost k-${kindOf(id) || "beat"}`; ghost.innerHTML = `<div class="t">${esc(titleOf(id))}</div>`; document.body.append(ghost);
      }
      ghost.style.left = e.clientX - 30 + "px"; ghost.style.top = e.clientY - 16 + "px"; hotHead(headAt(e));
      $("#tray").classList.toggle("over", id.startsWith("p:") && inRect(e, $("#tray")));
      const tb = tabUnder(e); $$("#sess button").forEach(x => x.classList.toggle("drop", x === tb && tb.dataset.tab !== T()));
    }, (e, off) => {
      hotHead(null); $("#tray").classList.remove("over"); $$("#sess button").forEach(x => x.classList.remove("drop"));
      if (!ghost) { if (!off) open(id); return; }
      ghost.remove(); if (off) return;
      const tb = tabUnder(e), hd = headAt(e);
      if (tb) { if (tb.dataset.tab !== T()) moveTo(id, tb.dataset.tab); return; }
      if (id.startsWith("p:") && inRect(e, $("#tray"))) { takeOff(id); return; }
      if (hd) { toAny(id, hd, rowUnder(e)); return; }
      if (!inRect(e, board)) return;
      const w = toWorld(e.clientX, e.clientY), x = snap(w.x - 30), y = snap(w.y - 16), sid = sceneOf(id);
      withLane(lane, () => measure([id])); release(id, mineHome()); it(id).at[lane] = {x, y}; settle(id, x, y);
      if (sceneOf(id) !== sid && !sceneOf(id)) it(id).at[lane] = {x, y};
      changed(); draw();
    });
  });
}
function settle(id, x, y) {   // a card let go at x, y on this board: into the scene it is in, or out of the one it left
  const to = sceneAt(id), was = sceneOf(id);
  if (to === was) return;
  if (to) { const sb = box(to); join(id, to, x - sb.x, Math.max(Math.ceil((headOf(to) + 8) / GRID) * GRID, snap(y - sb.y - (ah[to] || 0)))); }
  else { release(id, mineHome()); it(id).at[lane] = {x, y}; }
}
function insideSpot(sid) {   // the next free place inside a scene; the scene grows to fit
  const ms = flowOf(sid), o = it(sid);
  const y = ms.length ? Math.max(...ms.map(m => it(m).ry + (hs[m] || 110))) + 22 : snap(headOf(sid) + 22);
  if (y + 170 > (o.h || SCH)) growScene(sid, o.w || SCW, y + 170);
  return {rx: 22, ry: snap(y)};
}
function moveTo(id, t) {   // to another session, on every board it is on; a scene takes its cards along
  if (sceneOf(id)) release(id, mineHome());
  const o = it(id); o.s = t; o.at = {}; delete o.after; delete o.before; if (isScene(id)) membersOf(id).forEach(m => { it(m).s = t; });
  doc.edges = doc.edges.filter(e => !(e.from.startsWith("start") && e.to === id));
  changed(); draw();
}
function link(ev, from) {
  ev.stopPropagation(); ev.preventDefault();
  const a = box(from), sx = a.x + a.w, sy = a.y + Math.min(a.h / 2, 56), t = ev.target;
  cap(t, ev.pointerId);
  const mv = e => { const w = toWorld(e.clientX, e.clientY); wires(`M${sx},${sy} C${sx + 60},${sy} ${w.x - 60},${w.y} ${w.x},${w.y}`); };
  const up = e => {
    t.removeEventListener("pointermove", mv); t.removeEventListener("pointerup", up);
    const hit = document.elementsFromPoint(e.clientX, e.clientY).map(x => x.closest && x.closest(".any [data-card],.bn")).find(Boolean);
    const to = hit && (hit.dataset.card || hit.dataset.id);
    if (!to || to === from || to === "start") { wires(); return; }
    const id = addEdge(from === "start" ? "start:" + T() : from, to); changed(); draw(); edgeEditor(id, true);
  };
  t.addEventListener("pointermove", mv); t.addEventListener("pointerup", up);
}
function addEdge(from, to, label) {
  const id = "e" + Math.random().toString(36).slice(2, 9), e = {id, from, to, label: label || ""};
  if (from.startsWith("start")) e.lane = lane;
  doc.edges.push(e); return id;
}
function place(pid, t, x, y) {
  const id = "p:" + pid, sc = P[pid].scene && "p:" + P[pid].scene; let o = it(id);
  if (o && sceneOf(id)) release(id, mineHome());
  if (!o && lane === WHOLE) { putPlan(id, t); o = it(id); }   // on the session canvas a plan keeps the boards it is tied to
  if (!o) o = doc.items[id] = {s: t, homes: [], born: lane, at: {}};
  if (lane !== WHOLE && !o.homes.includes(lane)) o.homes.push(lane);
  if (o.s !== t) { o.s = t; o.at = {}; }
  if (isScene(id)) { o.w ||= SCW; o.h ||= SCH; }
  if (x !== undefined) { o.at[lane] = {x: snap(x), y: snap(y)}; if (isScene(id)) capture(id); else settle(id, snap(x), snap(y)); }
  else if (sc && live(sc) && sessOf(sc) === t && !isScene(id)) { if (P[pid].anytime) { toAny(id, sc); return; } const f = insideSpot(sc); join(id, sc, f.rx, f.ry); }   // the vault's scene, when it is here
  else if (!runMode && lane !== WHOLE) o.at[lane] = freeSpot(t);
  changed(); draw();
}
function trayDrag(el) {
  const pid = el.dataset.plan;
  el.addEventListener("pointerdown", ev => {
    const grip = !!ev.target.closest(".g") || ev.pointerType === "mouse", st = {x: ev.clientX, y: ev.clientY};
    let ghost = null, gave = false;
    const mv = e => {
      const dx = e.clientX - st.x, dy = e.clientY - st.y;
      if (!ghost) {
        if (Math.hypot(dx, dy) < 6) return;
        if (!grip && Math.abs(dy) > Math.abs(dx)) { gave = true; done(); return; }   // a vertical swipe scrolls the tray
        ghost = document.createElement("div"); ghost.className = `bn ghost k-${view_of(pid).kind}`;
        ghost.innerHTML = `<div class="t">${esc(pid)}</div>`; document.body.append(ghost);
        cap(el, e.pointerId);
      }
      e.preventDefault(); ghost.style.left = e.clientX - 30 + "px"; ghost.style.top = e.clientY - 16 + "px"; hotHead(isScene("p:" + pid) ? null : headAt(e));
      const tb = tabUnder(e); $$("#sess button").forEach(x => x.classList.toggle("drop", x === tb));
    };
    const up = e => {
      done(); hotHead(null); $$("#sess button").forEach(x => x.classList.remove("drop"));
      if (gave) return;
      if (!ghost) { open("p:" + pid); return; }
      ghost.remove();
      const tb = tabUnder(e);
      if (tb) { place(pid, tb.dataset.tab); return; }
      if (inRect(e, board)) { const w = toWorld(e.clientX, e.clientY), hd = headAt(e), id = "p:" + pid; place(pid, T(), w.x - 30, w.y - 16); if (hd && !isScene(id)) toAny(id, hd, rowUnder(e)); }
    };
    const cancel = () => { done(); if (ghost) ghost.remove(); };
    const done = () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", cancel); };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", cancel);
  });
}
/* the palette: a button per kind of card. Click adds one (in the scene that is open, or in the middle of the canvas); drag places one */
const sceneHere = () => shown && it(shown) && live(shown) ? (isScene(shown) ? shown : sceneOf(shown)) : null;
function palAdd(kind) {
  const sid = kind === "scene" ? null : sceneHere();
  if (sid && sessOf(sid) === T() && (runMode || onBoard(sid))) { newInScene(sid, kind); return; }
  if (runMode) { if (kind === "scene") newScene(); else toast(`Open a scene first, or drag ${KINDS[kind]} into the scene it belongs to.`); return; }
  const r = board.getBoundingClientRect(), p = toWorld(r.left, r.top + 50), q = toWorld(r.right, r.bottom), w = kind === "scene" ? SCW : CARDW, h = kind === "scene" ? SCH : 150;
  const taken = [...inTab(T()), "start"].map(i => box(i)).filter(Boolean), free = (x, y) => !taken.some(b => x < b.x + b.w + GRID && x + w + GRID > b.x && y < b.y + b.h + GRID && y + h + GRID > b.y);
  const mx = (p.x + q.x - w) / 2, my = (p.y + q.y - h) / 2; let best = null;   // the free spot in view nearest its middle
  for (let x = snap(p.x) + GRID; x + w <= q.x; x += GRID) for (let y = snap(p.y) + GRID; y + h <= q.y; y += GRID) { const d = Math.hypot(x - mx, y - my); if ((!best || d < best.d) && free(x, y)) best = {x, y, d}; }
  const bs = taken.filter(b => b.x < Math.max(FIRSTX, mx) + w && b.x + b.w > Math.max(FIRSTX, mx));   // none: under everything there
  const at = best || {x: snap(Math.max(FIRSTX, mx)), y: bs.length ? snap(Math.max(...bs.map(b => b.y + b.h))) + 44 : SY}, {x, y} = at;
  if (!best) { view.y -= (y + h - q.y + 40) * view.k; applyView(); }
  newCard(x, y, kind);
}
function palDrag(el, kind) {
  el.addEventListener("click", () => { if (Date.now() - dragEnd > 300) palAdd(kind); });
  el.addEventListener("pointerdown", ev => {
    if (ev.button > 0) return;
    const st = {x: ev.clientX, y: ev.clientY}; let ghost = null, at = null, over = null, wait = null;
    const hotScene = e => { const w = toWorld(e.clientX, e.clientY); return kind === "scene" ? null : inTab(T()).filter(isScene).map(i => [i, box(i)]).filter(([, b]) => b && w.x > b.x && w.x < b.x + b.w && w.y > b.y + 20 && w.y < b.y + b.h).sort((a, c) => a[1].w * a[1].h - c[1].w * c[1].h).map(x => x[0])[0] || null; };
    watch(e => {
      if (!ghost) {
        if (Math.hypot(e.clientX - st.x, e.clientY - st.y) < 6) return;
        ghost = document.createElement("div"); ghost.className = `bn ghost k-${kind}`; ghost.innerHTML = `<div class="k"><span>${kic(kind)}${KINDS[kind]}</span></div><div class="s"></div>`;
        document.body.append(ghost); el.classList.add("drag");
      }
      e.preventDefault(); ghost.style.left = e.clientX - 30 + "px"; ghost.style.top = e.clientY - 16 + "px";
      let say = "";
      if (runMode) {
        clearRun(); at = runSpot(e, [], kind === "scene", null); say = at.spot && at.spot.tab ? "" : at.say; $$("#rsess button").forEach(x => x.classList.remove("drop"));
        ghost.style.left = e.clientX + 12 + "px"; ghost.style.top = e.clientY + 10 + "px";
        if (at.rc !== over) { clearTimeout(wait); over = at.rc; const rc = at.rc; if (rc && kind !== "scene" && !opened.has(rc.dataset.uid)) wait = setTimeout(() => { opened.add(rc.dataset.uid); expand(rc, true); }, 550); }
        edgeScroll(e);
      } else { const hd = kind === "scene" ? null : headAt(e), hot = !hd && inRect(e, board) ? hotScene(e) : null; hotHead(hd); $$("#nodes .bn").forEach(x => x.classList.toggle("hot", x.dataset.id === hot)); say = hd ? `any time in “${titleOf(hd)}”` : hot ? `in “${titleOf(hot)}”` : ""; }
      ghost.querySelector(".s").textContent = say;
    }, (e, off) => {
      clearTimeout(wait); el.classList.remove("drag"); clearRun(); hotHead(null); $$("#nodes .bn.hot").forEach(x => x.classList.remove("hot"));
      if (!ghost) return;
      ghost.remove(); dragEnd = Date.now(); if (off) return;
      if (runMode) { const s = at && at.spot; if (!s || s.tab || s.out) return; if (s.scene) newScene(s.before); else newInScene(s.sid, kind, s); return; }
      if (inRect(e, board)) { const w = toWorld(e.clientX, e.clientY); newCard(w.x - 30, w.y - 16, kind, kind === "scene" ? null : headAt(e)); }
    });
  });
}
function newCard(x, y, kind, hd) {
  const cid = Math.random().toString(36).slice(2, 10), id = "c:" + cid; x = snap(x); y = snap(y);
  doc.cards[cid] = {kind: kind || "note", title: "", text: ""};
  doc.items[id] = {s: T(), homes: [lane], born: lane, at: {[lane]: {x, y}}};
  if (kind === "scene") { Object.assign(doc.items[id], {w: SCW, h: SCH}); Object.assign(doc.cards[cid], {where: "", present: lane === "world" || lane === WHOLE ? [] : [lane]}); if (lane === WHOLE) doc.items[id].homes = []; }
  else { settle(id, x, y); if (sceneOf(id) && !kind) doc.cards[cid].kind = "beat"; }
  changed(); if (hd) toAny(id, hd); else draw();
  open(id, "edit");
}
function resize(ev, el, id) {
  ev.stopPropagation(); ev.preventDefault();
  const o = it(id), b = box(id), st = {x: ev.clientX, y: ev.clientY}, t = ev.target, more = ah[id] || 0, minH = headOf(id) + 66;
  cap(t, ev.pointerId);
  const mv = e => {
    o.w = Math.max(300, Math.round(b.w + (e.clientX - st.x) / view.k)); o.h = Math.max(minH, Math.round(b.h - more + (e.clientY - st.y) / view.k));
    el.style.width = o.w + "px"; el.style.height = o.h + more + "px"; wires();
  };
  const up = () => { t.removeEventListener("pointermove", mv); t.removeEventListener("pointerup", up); t.removeEventListener("pointercancel", up);
    o.w = snap(o.w); o.h = Math.max(snap(o.h), minH); makeRoom(id, b.w, b.h - more, lane); capture(id); changed(); draw(); };
  t.addEventListener("pointermove", mv); t.addEventListener("pointerup", up); t.addEventListener("pointercancel", up);
}
function setClock(id, v) {
  if (id.startsWith("c:")) L().cards[id.slice(2)].clock = v;
  else {
    const pid = id.slice(2), s = L(), e = {...(s.edits[pid] || {})};
    if (v === (P[pid].clock || "0/4")) delete e.clock; else e.clock = v;
    if (Object.keys(e).length) s.edits[pid] = e; else delete s.edits[pid];
  }
  changed();
}
function tick(id, d) {
  const o = id.startsWith("p:") ? view_of(id.slice(2)) : L().cards[id.slice(2)];
  const [f, n] = parseClock(o.clock);
  setClock(id, `${(f + d + n + 1) % (n + 1)}/${n}`); draw(); if (shown === id) open(id);
}

/* ---------- side panel: one layout for every card, to read or to edit ----------
   Header (type, state, title), then the same sections in the same order for every kind: details, What happens, what only that kind has
   (Options, Leads to, Cards), Place, then what only a vault plan has (Needs, Changes, Note to Claude), and one footer. */
let shown = null, mode = "view", rw = store.get("osse-paths-rw") === "edit" ? "edit" : "view", own = null, pkey = null, repaint = null;   // rw: the setting at the top of the page; own: the open panel's own choice, which wins
function closeDrawer() { $("#drawer").hidden = true; shown = pkey = own = repaint = null; tipOff(); $$(".bn.on").forEach(x => x.classList.remove("on")); }
function enter(key, m, again) { if (key !== pkey) own = null; if (m) own = m; pkey = key; repaint = again; mode = own || rw; return mode === "edit"; }
const rwBtns = cur => ["view", "edit"].map(m => `<button data-rw="${m}" aria-pressed="${cur === m}">${m === "view" ? "Read" : "Edit"}</button>`).join("");
function frame(o) {   // {kind, name, tags, title, body, foot, plain}
  const d = $("#drawer"); tipOff(); d.className = "drawer " + (mode === "edit" ? "toedit" : "toread"); d.setAttribute("aria-label", o.name);
  d.innerHTML = `<div class="ph k-${esc(o.kind || "note")}"><div class="ph1">${kic(o.kind)}<b>${esc(o.name)}</b>${o.tags || ""}<span class="sp"></span>${o.plain ? "" : `<span class="rwt" role="group" aria-label="This panel">${rwBtns(mode)}</span>`}<button class="x" aria-label="Close">×</button></div>${o.title}</div>` +
    `<div class="pb">${o.body}</div>${o.foot ? `<div class="pf">${o.foot}</div>` : ""}`;
  d.style.top = innerWidth > 900 ? Math.max(14, Math.round($(".ptop").getBoundingClientRect().bottom) + 8) + "px" : "";   // clear of the bar, so Read and Edit stay in reach
  d.hidden = false;
  d.querySelector(".x").onclick = () => { closeDrawer(); draw(); };
  d.querySelectorAll(".rwt [data-rw]").forEach(b => b.onclick = () => { own = b.dataset.rw; draw(); repaint(); });
  d.querySelectorAll("textarea").forEach(t => { const grow = () => { t.style.height = "auto"; t.style.height = Math.min(420, t.scrollHeight + 2) + "px"; }; t.addEventListener("input", grow); grow(); });
  d.querySelectorAll("textarea.one").forEach(t => { t.onkeydown = ev => { if (ev.key === "Enter") { ev.preventDefault(); t.blur(); } }; });
  d.querySelectorAll("[data-open]").forEach(b => b.onclick = () => { if (runMode) openHere(b.dataset.open); else open(b.dataset.open); });
  tips(d);
  return d;
}
const again = () => { const y = ($("#drawer .pb") || {}).scrollTop || 0; repaint(); const b = $("#drawer .pb"); if (b) b.scrollTop = y; };
const row = (lab, h) => `<div class="fr"><span class="fl">${lab}</span><div class="fv">${h}</div></div>`;
const sec = (lab, h, side) => h ? `<div class="ps"><h4>${lab}${side ? `<span>${side}</span>` : ""}</h4>${h}</div>` : "";
const rows = h => h ? `<div class="ps">${h}</div>` : "";   // the details: no heading of their own
const para = t => `<div class="pc">${esc(t).replace(/\n/g, "<br>")}</div>`;
const field = (f, v, ph, list) => `<input type="text" data-f="${f}" aria-label="${f}" value="${esc(v || "")}" placeholder="${esc(ph)}"${list ? ` list="${list}"` : ""}>`;
const longField = (f, v, ph) => `<textarea rows="1" class="one" data-f="${f}" aria-label="${f}" placeholder="${esc(ph)}">${esc(v || "")}</textarea>`;   // one line that wraps
const whoIn = ph => `<div class="whof"><span class="whobox"></span><input type="text" class="whoin" aria-label="Who" list="dl-people" placeholder="${esc(ph)}"></div>`;
const WHOPH = {scene: "Who is there when it opens", entrance: "Who comes in", exit: "Who leaves"}, TEXTPH = {scene: "What is going on when it opens", clock: "What happens when it fills", reveal: "What comes out", complication: "What goes wrong, or turns", decision: "What they must choose", entrance: "How they come in, and what it changes", exit: "How it ends", note: "The idea"};
function details(o, id, ed) {   // what the kind adds, the same rows in the same order to read and to edit
  const k = o.kind || "beat", scene = k === "scene", inS = INSCENE.includes(k), chips = h => `<span class="chips">${h}</span>`;
  let h = ed ? row("Type", `<select data-kind aria-label="Type" title="${esc(KDESC[k])}">${kindOpts(id, k, id.startsWith("c:"))}</select>`) : "";
  if (scene) {
    if (ed || o.where) h += row("Where", ed ? field("where", o.where, "A place", "dl-places") : esc(o.where));
    if (ed || o.when) h += row("When", ed ? field("when", o.when, "The next morning…") : esc(o.when));
  }
  if (inS && (ed || o.cue)) h += row("Cue", ed ? longField("cue", o.cue, "What triggers it") : esc(o.cue));
  const who = (scene ? o.present : o.who) || [];
  if ((scene || inS) && (ed || who.length)) h += row("Who", ed ? whoIn(WHOPH[k] || "Who it is about") : chips(scene ? whoTags(who, live(id) ? lanesOf(id) : []) : peopleTags(who)));
  if (scene && (ed || o.purpose)) h += row("Purpose", ed ? longField("purpose", o.purpose, "Reveal a clue, force a choice…") : esc(o.purpose));
  if (k === "reveal" && (ed || o.reveals)) h += row("Secret", ed ? field("reveals", o.reveals, "The secret it reveals", "dl-secrets") : `${esc(o.reveals)}${secretOut(o.reveals) ? ` <span class="ch">already out</span>` : ""}`);
  if (k === "clock") { const [f, n] = parseClock(o.clock); h += row("Clock", ed ? clockFields(o.clock) : `<span class="clk"><span class="rng">${ring(f, n, 30)}</span>${f} of ${n}</span>`); }
  if (k === "decision" && ed) h += row("Critical", `<label class="chk"><input type="checkbox" data-f="critical" ${o.critical ? "checked" : ""}>Can end or remake a character</label>`);
  return rows(h);
}
function fieldBind(d, o, cb) {   // the panel's fields: cb(field, value) as each one changes
  d.querySelectorAll("[data-f]").forEach(x => { const get = () => x.type === "checkbox" ? x.checked : x.value.trim();
    if (x.type === "checkbox") x.onchange = () => { cb(x.dataset.f, get()); draw(); };
    else { x.oninput = () => cb(x.dataset.f, get()); x.onchange = () => { cb(x.dataset.f, get()); draw(); }; } });
  if (d.querySelector(".whobox")) { const f = o.kind === "scene" ? "present" : "who", pk = whoPicker(d, [...(o[f] || [])], () => { cb(f, pk.get()); draw(); }); }
}
const kindOpts = (id, cur, note) => {   // inside a scene: its six kinds (and the one it has, if it came from before)
  const one = k => `<option value="${k}" ${k === cur ? "selected" : ""}>${KINDS[k]}</option>`, grp = (lab, ks) => ks.length ? `<optgroup label="${lab}">${ks.map(one).join("")}</optgroup>` : "";
  if (it(id) && sceneOf(id)) return grp("In a scene", INSCENE) + grp("Now", INSCENE.includes(cur) ? [] : [cur]);
  return grp("The stage", ["scene"]) + grp("In a scene", INSCENE) + grp("Outside scenes", ["clock", "pressure", "bottleneck", ...(note ? ["note"] : [])]); };
const pickTag = x => { const k = pcOf(x), p = PCS.find(q => q.key === k); return k === "party" ? `class="pcx all who" title="${esc(PARTY)}"` : p ? `class="pcx in who" style="--c:${esc(p.colour)}"` : `class="ch who"`; };
function whoPicker(d, list, cb) {
  const box = d.querySelector(".whobox"), inp = d.querySelector(".whoin");
  const known = x => D.people.some(p => p.n === x);
  const paint = () => {
    box.innerHTML = list.map((x, i) => `<span ${pickTag(x)}${known(x) ? "" : ` title="Not in the vault yet"`}>${esc(x)}${known(x) ? "" : " · new"}<button data-rm="${i}" aria-label="Remove ${esc(x)}">×</button></span>`).join("");
    box.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { list.splice(+b.dataset.rm, 1); paint(); cb(); });
  };
  const add = () => { const v = inp.value.trim(); inp.value = ""; if (v && !list.includes(v)) { list.push(v); paint(); cb(); } };
  inp.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); add(); } };
  inp.oninput = () => { if (known(inp.value.trim())) add(); };   // picked from the list
  inp.onblur = add;
  paint(); return {get: () => [...list]};
}
const clockFields = c => { const [f, n] = parseClock(c), opts = [...new Set([2, 3, 4, 6, 8, 10, 12, n])].sort((a, b) => a - b);
  return `<div class="clkf" data-clk><span class="rng">${ring(f, n, 30)}</span><button class="mini" data-cf="-1" aria-label="Empty a segment">−</button><b>${f}</b><button class="mini" data-cf="1" aria-label="Fill a segment">+</button><span>of</span><select aria-label="Segments">${opts.map(x => `<option ${x === n ? "selected" : ""}>${x}</option>`).join("")}</select></div>`; };
function clockBind(d, c, cb) {
  const w = d.querySelector("[data-clk]"); if (!w) return;
  let [f, n] = parseClock(c);
  const paint = () => { w.querySelector(".rng").innerHTML = ring(f, n, 30); w.querySelector("b").textContent = f; cb(`${f}/${n}`); };
  w.querySelectorAll("[data-cf]").forEach(b => b.onclick = () => { f = Math.max(0, Math.min(n, f + +b.dataset.cf)); paint(); });
  w.querySelector("select").onchange = e => { n = +e.target.value; f = Math.min(f, n); paint(); };
}

/* Place: the session, the scene and the spot in it, for every card and plan */
function placeSec(id, ed) {
  const on = live(id), plan = id.startsWith("p:"), t = on ? sessOf(id) : "", sc = on && sceneOf(id), scene = isScene(id);
  let h = "";
  if (ed) {
    h += row("Session", `<select data-sess aria-label="Session">${plan ? `<option value="" ${on ? "" : "selected"}>Not placed</option>` : ""}${doc.sessions.map(x => `<option ${x === t ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>`);
    if (on && !scene) { const ss = scenesIn(t);
      h += row("Scene", `<select data-scene aria-label="Scene"><option value="">In no scene</option>${ss.map(x => `<option value="${esc(x)}" ${x === sc ? "selected" : ""}>${esc(called(x))}</option>`).join("")}</select>` + (sc ? `<label class="chk"><input type="checkbox" data-any ${isAny(id) ? "checked" : ""}>Any time in this scene</label>` : "")); }
    if (on && scene && t !== "Later") { const l = limits(id), line = (k, lab) => { const rest = scenesIn(t).filter(x => x !== id && !l.after.includes(x) && !l.before.includes(x));
        return row(lab, `<div class="whof">${l[k].map(x => `<span class="ch who">${esc(called(x))}<button data-unlim="${k}" data-x="${esc(x)}" aria-label="Remove this limit">×</button></span>`).join("")}` + (rest.length ? `<select data-lim="${k}" aria-label="${lab}"><option value="">${l[k].length ? "And…" : "No limit"}</option>${rest.map(x => `<option value="${esc(x)}">${esc(called(x))}</option>`).join("")}</select>` : "") + `</div>`); };
      h += row("Order", `<label class="chk"><input type="checkbox" data-float ${isFloat(id) ? "checked" : ""}>Floating${isFloat(id) ? "" : ` <small>now ${numIn(id)} of ${fixedIn(t).length}</small>`}</label>`) +
        (isFloat(id) ? line("after", "After") + line("before", "Before") + (fits(id, scenesIn(t).filter(x => x !== id)) ? "" : `<p class="badl">These limits leave it no place.</p>`) : ""); }
  } else {
    h += row("Session", on ? esc(t) + (sName(t) ? ` · ${esc(sName(t))}` : "") : "Not placed");
    if (sc) h += row("Scene", `<button class="lnk" data-open="${esc(sc)}">${esc(called(sc))}</button>${isAny(id) ? ` <span class="ch">any time</span>` : ""}`);
    if (on && scene && t !== "Later") h += row("Order", isFloat(id) ? `Floating, ${limText(id)}` : `${numIn(id)} of ${fixedIn(t).length}`);
  }
  if (on && !sc) h += row("Boards", `<span class="chips">${lanesOf(id).some(k => k !== WHOLE) || everyPc(lanesOf(id)) ? laneTags(lanesOf(id)) : `<span class="none">The session canvas only</span>`}</span>`);
  const q = plan && P[id.slice(2)], says = q ? [q.target && on && t.toUpperCase() !== q.target.toUpperCase() || q.target && !on ? q.target : "", q.scene && sc !== "p:" + q.scene ? `in “${q.scene}”` : ""].filter(Boolean) : [];
  if (says.length) h += row("Vault says", esc(says.join(", ")));
  return sec("Place", h);
}
function setScene(id, sid) {
  const from = sceneOf(id); if (from === sid) return;
  if (sid) dropInto(id, {sid}, from && !isAny(id) ? treeOf(from).under(id) : [id], true);
  else { release(id, mineHome()); it(id).at = {}; }
  changed(); draw(); again();
}
function placeBind(d, id) {
  const on = (s, f) => { const e = d.querySelector(s); if (e) e.onchange = () => f(e); };
  on("[data-sess]", e => { const t = e.value;
    if (!t) { erase(id); changed(); draw(); }
    else if (live(id)) moveTo(id, t);
    else if (runMode) withLane(WHOLE, () => place(id.slice(2), t)); else place(id.slice(2), t);
    again(); });
  on("[data-scene]", e => setScene(id, e.value || null));
  on("[data-any]", e => { if (e.checked) toAny(id, sceneOf(id)); else { outOfAny(id); again(); } });
  on("[data-float]", e => { setFloat(id, e.checked); again(); });
  const set = (k, list) => { if (list.length) it(id)[k] = list; else delete it(id)[k]; heed(sessOf(id)); changed(); draw(); again(); };
  d.querySelectorAll("[data-lim]").forEach(s => s.onchange = () => { if (s.value) set(s.dataset.lim, [...limits(id)[s.dataset.lim], s.value]); });
  d.querySelectorAll("[data-unlim]").forEach(b => b.onclick = () => set(b.dataset.unlim, limits(id)[b.dataset.unlim].filter(x => x !== b.dataset.x)));
}

/* what only one kind has */
const cardLine = (m, dep, lab) => `<button class="cl k-${esc(kindOf(m) || "beat")}" data-open="${esc(m)}" data-tip="${esc(m)}" style="margin-left:${Math.min(dep, 4) * 14}px">${kic(kindOf(m) || "beat")}<span>${lab && lab.length ? `<i class="el">${lab.map(esc).join(" or ")}</i> ` : ""}${esc(titleOf(m))}${fieldOf(objOf(m), "cue") ? `<small>${esc(objOf(m).cue)}</small>` : ""}</span></button>`;
function cardsSec(id, ed) {   // a scene's cards
  if (!live(id)) return "";
  const tr = treeOf(id), anys = anyOf(id), flat = (p, n) => (tr.kids[p] || []).map(m => cardLine(m, n, tr.lab[m]) + flat(m, n + 1)).join(""), flow = flat("", 0);
  return sec("Cards", (anys.length ? `<div class="pc"><div class="sub">Any time</div>${anys.map(m => cardLine(m, 0)).join("")}</div>` : "") + (flow ? `<div class="pc">${anys.length ? `<div class="sub">In order</div>` : ""}${flow}</div>` : "") + (ed ? `<div class="pc">${addBtns(id)}</div>` : ""), anys.length + tr.ms.length || "");
}
function leadsSec(id, ed) {   // where an exit leads
  if (!live(id)) return "";
  const os = optionsOf(id), from = doc.sessions.indexOf(sessOf(id)), has = new Set(os.map(o => o.to));
  const opts = doc.sessions.filter((t, i) => i >= from).map(t => { const ss = scenesIn(t).filter(x => x !== sceneOf(id) && !has.has(x)); return ss.length ? `<optgroup label="${esc(t)}">${ss.map(x => `<option value="${esc(x)}">${esc(called(x))}</option>`).join("")}</optgroup>` : ""; }).join("");
  return sec("Leads to", (os.length ? `<div class="pc">${os.map(o => `<div class="ol"><span>→</span>${live(o.to) ? `<button class="lnk on" data-open="${esc(o.to)}">${esc(titleOf(o.to))}</button>` : `<b class="on">${esc(titleOf(o.to))} <small>not placed</small></b>`}${ed && o.own ? `<button class="mini" data-unlead="${esc(o.id)}" aria-label="Remove">×</button>` : ""}</div>`).join("")}</div>` : "") +
    (ed && opts ? `<div class="pc"><select data-lead aria-label="Add a scene it leads to"><option value="">${os.length ? "And…" : "Pick the next scene"}</option>${opts}</select></div>` : ""));
}
function leadsBind(d, id) {
  const s = d.querySelector("[data-lead]"); if (s) s.onchange = () => { if (s.value) { addEdge(id, s.value); changed(); draw(); again(); } };
  d.querySelectorAll("[data-unlead]").forEach(b => b.onclick = () => { doc.edges = doc.edges.filter(e => e.id !== b.dataset.unlead); changed(); draw(); again(); });
}
function optsSec(id, ed) {   // a decision's options, each one editable
  const list = optRows(id);
  if (!ed) return sec("Options", list.length ? `<div class="pc">${list.map(o => `<div class="or"><i class="el${o.label ? "" : " none"}">${esc(o.label || "choice not named")}</i> ${o.to && live(o.to) ? `<button class="lnk" data-open="${esc(o.to)}" data-tip="${esc(o.to)}">${esc(titleOf(o.to))}</button>` : esc(outOf(o))}${o.off ? " <small>not placed</small>" : ""}</div>`).join("")}</div>` : "");
  const s = sessOf(id), sid = it(id) && sceneOf(id), from = doc.sessions.indexOf(s), on = live(id);
  const cards = on ? (sid ? membersOf(sid) : looseIn(s)).filter(m => m !== id) : [], op = (v, txt, cur) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(txt)}</option>`;
  const scenes = on ? doc.sessions.filter((t, i) => i >= from).map(t => [t, scenesIn(t)]).filter(x => x[1].length) : [];
  const pick = o => { const known = !o.to || cards.includes(o.to) || scenes.some(x => x[1].includes(o.to));
    return `<select data-ow aria-label="What the outcome is" title="What the outcome is"><option value="" ${o.to ? "" : "selected"}>Only listed</option>` + (on ? `<optgroup label="Make it a new card">${[...INSCENE.map(k => [k, KINDS[k]]), ["scene", "Scene"]].map(([k, n]) => op("new:" + k, "New " + n.toLowerCase(), "")).join("")}</optgroup>` : "") +
      (known ? "" : `<optgroup label="Now">${op(o.to, titleOf(o.to), o.to)}</optgroup>`) + (cards.length ? `<optgroup label="${sid ? "A card in this scene" : "A card in " + esc(s)}">${cards.map(m => op(m, `${kl(m)}: ${titleOf(m)}`, o.to)).join("")}</optgroup>` : "") +
      scenes.map(([t, ss]) => `<optgroup label="A scene in ${esc(t)}">${ss.map(m => op(m, titleOf(m), o.to)).join("")}</optgroup>`).join("") + `</select>`; };
  return sec("Options", list.map((o, i) =>
    `<div class="optx" data-opt="${i}"><div class="ol"><span>◇</span><input type="text" data-ol ${o.e ? `data-oe="${esc(o.e)}"` : ""} value="${esc(o.label)}" placeholder="The choice" aria-label="The choice">` +
    (o.need ? "" : `<button class="mini" data-ox title="Remove this option${o.to ? ". The card it leads to stays" : ""}" aria-label="Remove this option">×</button>`) + `</div>` +
    `<div class="ol"><span>→</span>` + (o.to.startsWith("p:") ? `<b class="on">${esc(titleOf(o.to))}</b>` : `<input type="text" data-ot value="${esc(o.to ? (doc.cards[o.to.slice(2)] || {}).title || "" : o.text)}" placeholder="The outcome" aria-label="The outcome">`) +
    (o.need ? "" : pick(o)) + (o.off && on ? `<button class="mini" data-opl title="Put that plan in this session">Place</button>` : o.to && live(o.to) ? `<button class="mini" data-open="${esc(o.to)}" title="Open that card" aria-label="Open that card">↗</button>` : "") + `</div></div>`).join("") +
    `<div class="pc"><button class="addo" data-addopt>+ option</button></div>`, list.length || "");
}
function needsSec(p) {
  return sec("Needs", p.req.length ? `<div class="pc"><ul class="req">${p.req.map(r => {
    const ok = r.k === "check" ? ["m", "?"] : test(r) ? ["y", "✓"] : ["n", "✗"], nm = r.a && F[r.a] ? `<a href="${esc(F[r.a].href)}">${esc(r.a)}</a>${esc(r.t.slice(r.a.length))}` : esc(r.t), c = F[r.a] && F[r.a].clues;
    return `<li><span class="ok ${ok[0]}">${ok[1]}</span><span class="kk">${esc(r.k)}</span><span>${nm}${c !== undefined ? ` <small title="Ways it could come out. Aim for three">${c} clue${c === 1 ? "" : "s"}</small>` : ""}</span></li>`; }).join("")}</ul></div>` : "");
}
function kindSec(o, id, ed) { return o.kind === "decision" ? optsSec(id, ed) : o.kind === "exit" ? leadsSec(id, ed) : o.kind === "scene" ? cardsSec(id, ed) : ""; }
function binds(d, id) { optsBind(d, id); d.querySelectorAll("[data-addto]").forEach(b => b.onclick = () => newInScene(b.dataset.addto, b.dataset.k)); leadsBind(d, id); placeBind(d, id); }
function open(id, m) {
  const ed = enter(id, m, () => open(id));
  shown = id; $$(".bn").forEach(x => x.classList.toggle("on", x.dataset.id === id)); $$("[data-card]").forEach(x => x.classList.toggle("on", x.dataset.card === id));
  if (id.startsWith("c:")) cardPanel(id, ed); else planPanel(id, ed);
}
function cardPanel(id, ed) {   // Tom's own card
  const cid = id.slice(2), c = doc.cards[cid]; if (!c) return closeDrawer();
  const d = frame({kind: c.kind, name: kl(id), tags: `<span class="ch">${esc(whose(c))}</span>`,
    title: ed ? `<input type="text" class="ttl" data-title aria-label="Title" value="${esc(c.title)}" placeholder="Title">` : `<h3>${esc(c.title || "Untitled")}</h3>`,
    body: details(c, id, ed) + sec("What happens", ed ? `<textarea data-text aria-label="What happens" placeholder="${esc(TEXTPH[c.kind] || "A sentence or two")}">${esc(c.text)}</textarea>` : c.text ? para(c.text) : "") + kindSec(c, id, ed) + placeSec(id, ed),
    foot: ed ? `<button class="del" data-del>Delete</button>` : ""});
  binds(d, id); if (!ed) return;
  const t = d.querySelector("[data-title]"), x = d.querySelector("[data-text]"), k = d.querySelector("[data-kind]");
  const sync = () => { delete c.draft; c.title = t.value.trim(); c.text = x.value.trim(); changed(); };
  t.oninput = sync; x.addEventListener("input", sync); t.onchange = x.onchange = () => { sync(); draw(); };
  t.onkeydown = ev => { if (ev.key === "Enter") { sync(); closeDrawer(); draw(); } };
  k.onchange = () => { sync(); c.kind = k.value; toScene(id); changed(); draw(); again(); };
  fieldBind(d, c, (f, v) => { if ((Array.isArray(v) ? v.length : v) || f === "where" || f === "present") c[f] = v; else delete c[f]; delete c.draft; changed(); });
  clockBind(d, c.clock, v => { c.clock = v; changed(); draw(); });
  d.querySelector("[data-del]").onclick = () => deleteCard(id);
  if (!c.title) setTimeout(() => t.focus(), 50);
}
function planPanel(id, ed) {   // a vault plan: what Tom changes here is an edit, until Claude takes it into the vault
  const pid = id.slice(2), p = view_of(pid), e0 = doc.edits[pid] || {};
  const idea = e0.idea !== undefined ? `<p>${esc(p.ideaText).replace(/\n/g, "<br>")}</p>` : p.idea;
  const d = frame({kind: p.kind, name: kl(id), tags: `<span class="ch${p.status === "ready" ? " ready" : ""}">${esc(p.status)}</span>${p.edited ? `<span class="ch ed">edited</span>` : ""}`,
    title: `<h3 title="A vault plan keeps its name. Ask Claude for a new one">${esc(pid)}</h3>`,
    body: details(p, id, ed) +
      sec("What happens", ed ? `<textarea rows="1" class="one" data-sum aria-label="In one line" placeholder="In one line">${esc(p.summary)}</textarea><textarea data-text aria-label="What happens" placeholder="${esc(TEXTPH[p.kind] || "A sentence or two")}">${esc(p.ideaText)}</textarea>`
        : p.summary || idea ? `<div class="pc">${p.summary ? `<p><b>${esc(p.summary)}</b></p>` : ""}${idea || ""}</div>` : "") +
      kindSec(p, id, ed) + placeSec(id, ed) + needsSec(p) + sec("Changes", p.links.length ? `<div class="pc"><ul class="chg">${p.links.map(l => `<li>${esc(l)}</li>`).join("")}</ul></div>` : "") +
      sec("Note to Claude", ed ? `<textarea data-note aria-label="Note to Claude" placeholder="Anything else to change">${esc(e0.note || "")}</textarea>` : e0.note ? para(e0.note) : ""),
    foot: ed ? `${Object.keys(e0).length ? `<button data-undo>Undo my edits</button>` : ""}<button class="del" data-del>Drop plan</button>` : ""});
  binds(d, id); if (!ed) return;
  const k = d.querySelector("[data-kind]"), s = d.querySelector("[data-sum]"), i = d.querySelector("[data-text]"), n = d.querySelector("[data-note]"), more = {}, v = P[pid];
  let clk = p.clock || "0/4";
  const sync = () => {
    const e = {...(doc.edits[pid] || {})}, set = (key, val, base) => { if (JSON.stringify(val) === JSON.stringify(base)) delete e[key]; else e[key] = val; };
    set("kind", k.value, v.kind); set("summary", s.value.trim(), v.summary); set("idea", i.value.trim(), v.ideaText);
    if (n.value.trim()) e.note = n.value.trim(); else delete e.note;
    for (const f in more) set(f, more[f], v[f]);
    if (d.querySelector("[data-clk]")) set("clock", clk, v.clock || "0/4");
    if (Object.keys(e).length) doc.edits[pid] = e; else delete doc.edits[pid];
    changed();
  };
  [s, i, n].forEach(x => { x.addEventListener("input", sync); x.onchange = () => { sync(); draw(); }; });
  k.onchange = () => { sync(); toScene(id); changed(); draw(); again(); };
  fieldBind(d, p, (f, val) => { more[f] = val; sync(); });
  clockBind(d, p.clock, x => { clk = x; sync(); draw(); });
  const u = d.querySelector("[data-undo]"); if (u) u.onclick = () => { delete doc.edits[pid]; changed(); draw(); again(); };
  d.querySelector("[data-del]").onclick = () => { if (confirm(`Drop “${pid}”? It leaves this board and the tray. Claude marks it dropped in the vault when you bring the board in; until then you can undo it from the tray.`)) dropPlan(pid); };
}
function optsSave(id, list) {
  if (id.startsWith("c:")) { const c = doc.cards[id.slice(2)]; delete c.draft; if (list.length) c.options = list; else delete c.options; return; }
  const pid = id.slice(2), e = {...(doc.edits[pid] || {})};
  if (same(list, P[pid].options)) delete e.options; else e.options = list;
  if (Object.keys(e).length) doc.edits[pid] = e; else delete doc.edits[pid];
}
function optSet(id, row, ch) {   // change an option's choice, its words, or what it leads to
  const edge = row.e && doc.edges.find(x => x.id === row.e), words = {label: ch.label ?? row.label, text: ch.text ?? row.text};
  if (edge) {
    if ("label" in ch) edge.label = ch.label;
    if ("to" in ch) { if (ch.to) edge.to = ch.to; else { doc.edges = doc.edges.filter(x => x !== edge); optsSave(id, [...copyOf(optsSaved(id)), {...(id.startsWith("p:") ? {to: ""} : {}), ...words}]); } }
  } else if (row.need) { row.e = addEdge(id, row.to, words.label); delete row.need; }   // naming a bare "needs" makes it an option of Tom's
  else {
    const list = copyOf(optsSaved(id)), o = list[row.i]; if (!o) return;
    if (!("to" in ch)) { if ("label" in ch) o.label = ch.label; if ("text" in ch) o.text = ch.text; }
    else if (!ch.to) list[row.i] = {...(id.startsWith("p:") ? {to: ""} : {}), ...words};
    else if (id.startsWith("p:") && ch.to.startsWith("p:")) list[row.i] = {to: ch.to.slice(2), label: words.label};
    else { list.splice(row.i, 1); addEdge(id, ch.to, words.label); }
    optsSave(id, list);
  }
  Object.assign(row, words); changed();
}
function optNew(id, row, kind) {   // the outcome becomes a new card, beside the decision
  const cid = Math.random().toString(36).slice(2, 10), n = "c:" + cid, sid = sceneOf(id), t = sessOf(id);
  doc.cards[cid] = {kind, title: row.text || "", text: ""};
  if (kind === "scene") {
    const here = sid ? objOf(sid).present || [] : [];
    Object.assign(doc.cards[cid], {where: "", present: [...here]}); doc.items[n] = {s: t, homes: [], born: lanesOf(id)[0], at: {}, w: SCW, h: SCH};
    if (sid && doc.order[t]) { const ord = scenesIn(t).filter(x => x !== n); ord.splice(ord.indexOf(sid) + 1, 0, n); doc.order[t] = ord; }
  } else {
    doc.items[n] = {s: t, homes: [...lanesOf(id)], born: lanesOf(id)[0], at: {}};
    if (sid && isAny(id)) { withLane(lanesOf(sid)[0], () => measure([sid, ...flowOf(sid)])); const f = insideSpot(sid); join(n, sid, f.rx, f.ry); }
    else if (sid) { dropInto(n, {sid, parent: id}, [n], true); doc.edges = doc.edges.filter(e => !(e.from === id && e.to === n)); }
    else { const k = runMode ? null : lane, b = k && box(id); if (b) { const ks = optRows(id).map(o => o.to && live(o.to) && sessOf(o.to) === t && box(o.to)).filter(Boolean), x = snap(b.x + CARDW + 148); it(n).at[k] = {x, y: snap(Math.max(b.y, ...ks.filter(q => q.x < x + CARDW && q.x + q.w > x).map(q => q.y + q.h + 32)))}; } }
  }
  optSet(id, row, {to: n}); return n;
}
function addOption(id) {   // + option, on the card or in its panel: always to edit
  const list = copyOf(optsSaved(id)); list.push({...(id.startsWith("p:") ? {to: ""} : {}), label: "", text: ""}); optsSave(id, list); changed(); draw();
  if (shown === id && mode === "edit") again(); else if (runMode) openHere(id, "edit"); else open(id, "edit");
  const ins = $$("#drawer [data-ol]"), i = ins[ins.length - 1]; if (i) setTimeout(() => { i.scrollIntoView({block: "nearest"}); i.focus(); }, 30);
}
function optsBind(d, id) {
  const ao = d.querySelector("[data-addopt]"); if (!ao) return; ao.onclick = () => addOption(id);
  const list = optRows(id);
  d.querySelectorAll("[data-opt]").forEach(x => {
    const row = list[+x.dataset.opt], q = s => x.querySelector(s), on = (s, f) => { const e = q(s); if (e) e.onclick = f; };
    const l = q("[data-ol]"); l.oninput = () => optSet(id, row, {label: l.value.trim()}); l.onchange = () => draw();
    const t = q("[data-ot]"); if (t) { t.oninput = () => { if (row.to) { const c = doc.cards[row.to.slice(2)]; c.title = t.value.trim(); delete c.draft; changed(); } else optSet(id, row, {text: t.value.trim()}); }; t.onchange = () => draw(); }
    [l, t].forEach(e => { if (e) e.onkeydown = ev => { if (ev.key === "Enter") { e.blur(); addOption(id); } }; });
    const w = q("[data-ow]"); if (w) w.onchange = () => { const v = w.value;
      if (v.startsWith("new:")) optNew(id, row, v.slice(4)); else optSet(id, row, {to: v, ...(v ? {} : {text: row.to.startsWith("c:") ? (doc.cards[row.to.slice(2)] || {}).title || "" : row.to ? row.to.slice(2) : row.text})});
      draw(); again(); };
    on("[data-ox]", () => { if (row.e) doc.edges = doc.edges.filter(e => e.id !== row.e); else { const list = copyOf(optsSaved(id)); list.splice(row.i, 1); optsSave(id, list); } changed(); draw(); again(); });
    on("[data-opl]", () => { if (runMode) withLane(WHOLE, () => place(row.to.slice(2), sessOf(id))); else place(row.to.slice(2), sessOf(id)); again(); });
  });
}
function toScene(id) {   // after its kind changes: a scene needs a box and sits in no other; anything else holds no cards
  const o = it(id); if (!o) return;
  if (isScene(id)) { if (o.scene) release(id, mineHome()); o.w ||= SCW; o.h ||= SCH; if (id.startsWith("c:")) { const c = doc.cards[id.slice(2)]; c.where ||= ""; c.present ||= lanesOf(id).filter(k => k !== "world" && k !== WHOLE); } }
  else Object.keys(doc.items).filter(i => it(i).scene === id).forEach(i => release(i));
}
function edgeEditor(eid, fresh) {   // an arrow of Tom's; fresh: just drawn, so to edit
  const e = doc.edges.find(x => x.id === eid); if (!e) return;
  if (kindOf(e.from) === "decision") {   // an option: edited on its decision
    const m = fresh ? "edit" : undefined; if (runMode) openHere(e.from, m); else open(e.from, m);
    const i = $$("#drawer [data-oe]").find(x => x.dataset.oe === eid); if (i) setTimeout(() => { i.scrollIntoView({block: "center"}); i.focus(); }, 30); return; }
  const ed = enter("e:" + eid, fresh ? "edit" : undefined, () => edgeEditor(eid)); shown = null;
  const end = x => x.startsWith("start") ? `<span>Start of ${esc(T())}</span>` : `<button class="lnk" data-open="${esc(x)}">${esc(titleOf(x))}</button>`;
  const d = frame({kind: "note", name: "Link", tags: `<span class="ch">yours</span>`, title: `<h3>${esc(e.from.startsWith("start") ? "Start of " + T() : titleOf(e.from))} → ${esc(titleOf(e.to))}</h3>`,
    body: rows((ed || e.label ? row("Label", ed ? `<input type="text" data-lab aria-label="Label" value="${esc(e.label)}" placeholder="then, if they stall…">` : esc(e.label)) : "") + row("From", end(e.from)) + row("To", end(e.to))),
    foot: ed ? `<button class="del" data-del>Delete</button>` : ""});
  if (!ed) return;
  const i = d.querySelector("[data-lab]");
  i.oninput = () => { e.label = i.value.trim(); changed(); }; i.onchange = () => draw();
  i.onkeydown = ev => { if (ev.key === "Enter") { closeDrawer(); draw(); } };
  d.querySelector("[data-del]").onclick = () => { doc.edges = doc.edges.filter(x => x.id !== eid); changed(); closeDrawer(); draw(); };
  setTimeout(() => i.focus(), 50);
}

/* ---------- hover: what happens on a card shown as one line ---------- */
let tipT = null;
const tipText = id => { const o = objOf(id); return !o ? "" : id.startsWith("c:") ? o.text || "" : [o.summary, o.ideaText].filter((x, i, a) => x && a.indexOf(x) === i).join("\n"); };
function tipOff() { clearTimeout(tipT); const t = $("#tip"); if (t) t.hidden = true; }
function tips(host) {   // rows in a scene's Any time section, in the Running order and in a scene's panel
  host.querySelectorAll(".tr[data-card],[data-tip]").forEach(el => { const id = el.dataset.tip || el.dataset.card;
    el.addEventListener("pointerenter", e => { if (e.pointerType === "touch" || e.buttons) return; clearTimeout(tipT); tipT = setTimeout(() => {
      const txt = tipText(id), t = $("#tip"); if (!txt || !el.isConnected) return;
      t.innerHTML = `<b>What happens</b>${esc(txt.length > 700 ? txt.slice(0, 700) + "…" : txt).replace(/\n/g, "<br>")}`; t.hidden = false;
      const r = el.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight, below = r.bottom + 6 + h < innerHeight - 8;
      t.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left)) + "px"; t.style.top = Math.max(8, below ? r.bottom + 6 : r.top - h - 6) + "px"; }, 180); });
    ["pointerleave", "pointerdown"].forEach(n => el.addEventListener(n, tipOff)); });
}
function legend() {
  const k = $("#keyp"), btn = $('[data-act="legend"]');
  if (!k.hidden) { k.hidden = true; btn.classList.remove("on"); return; }
  k.innerHTML = `<button class="x" aria-label="Close">×</button><h3>Key</h3><dl>` +
    Object.keys(KINDS).map(x => `<dt class="k-${x}" style="border:0">${kic(x)}${KINDS[x]}</dt><dd>${esc(KDESC[x])}</dd>`).join("") +
    `<dt>Whole session</dt><dd>Running order and Canvas show everything in a session, whoever it is for: one as a list, one as a canvas with the scenes numbered in that order. Line up tidies the open canvas: the cards in each scene by their arrows, the scenes in running order, the cards linked to them underneath, then any card that is linked to nothing. Undo puts it back.</dd>` +
    `<dt>Floating scenes</dt><dd>A scene with no fixed place: it has no number and no line to the scenes around it. Tick Floating in its panel (Place), or choose Let it float in the Running order, and drag it back and forth. If it must come after or before another scene, say so there; it stays within those limits.</dd>` +
    `<dt>Boards</dt><dd>One per player character, and the World for what moves without the party knowing. The same scenes and cards, only the ones that belong there.</dd>` +
    `<dt>Session tabs</dt><dd>One canvas per session. The first starts from the end of S${CUR} as played; each later one starts from the end of the one before, as planned. Later holds ideas with no session yet.</dd>` +
    `<dt>Arc planner</dt><dd>A session’s name, what happens in it and its arc are one card, the same here and in the Arc planner. + Session brings in a session built there. Session numbers follow the order of the cards there; what is in a session goes along when its number changes. A session can also stay outside the arcs, and an idea can stay only there.</dd>` +
    `<dt>Scenes</dt><dd>Drag a scene by its header: the cards inside move with it. Drag its bottom-right corner to resize it. Drop a card inside a scene to set it there. A scene shows on the board of every player character who is in it or on one of its cards, with its cards. There is one copy: change it on one board and it changes on all of them; only its place on each canvas is its own.</dd>` +
    `<dt>Situation and purpose</dt><dd>On the scene itself: where, when, who is there and what is going on when it opens; and what the scene is for.</dd>` +
    `<dt>Cue</dt><dd>On every card in a scene: what triggers it at the table. With a cue, a card needs no arrow into it; draw arrows only where one thing has to follow another.</dd>` +
    `<dt>Any time</dt><dd>A section under a scene’s header for cards that can come at any point in the scene, on their cue. Drag a card onto the scene’s header to put it there, and drag it out to the canvas to give it a place. It folds up, and takes no room when empty.</dd>` +
    `<dt>Options</dt><dd>Open a decision (or press + option on it) to add and edit its options. An outcome is only listed until you make it a new card or pick one that is there.</dd>` +
    `<dt>Critical</dt><dd>A decision that can end or remake a character. Ticked in its panel.</dd>` +
    `<dt>Card types</dt><dd>The row of symbols above the canvas. Click one to add it: in the scene whose panel (or whose card's panel) is open, or on free canvas in view. Or drag it where it belongs: onto the canvas, into a scene, or into place in the Running order.</dd>` +
    `<dt>Moving a card</dt><dd>Drag it onto another session's tab, or pick the session in its panel.</dd>` +
    `<dt>Deleting</dt><dd>The × on a card: a plan goes back to the tray, your own card is deleted; a scene on several boards comes off this one only. Select a card and press Delete to do the same. To drop a plan for good, open it to edit and choose Drop plan. The × on the open session's tab deletes that session.</dd>` +
    `<dt>Not placed yet</dt><dd>The plans that are not placed, the same list beside the Running order and every canvas (on a board, that board's own). Drag one into place or onto a session tab (on a touch screen, by its ⠿ grip). Drag a plan back onto it to take it off. Filter narrows it: click a choice to match it, again to leave it out, again to clear it. Who and Session join their choices by OR or AND; so do the groups. A filter hides plans, it never removes them.</dd>` +
    `<dt>Links</dt><dd>Solid: the vault already joins them, or it is a decision's option. Dashed red: yours, not in the vault yet; drag from a card's + to add one, tap its label to edit it. Dotted grey: it follows something in an earlier session.</dd>` +
    `<dt>Read and Edit</dt><dd>At the top right: how a card's panel opens. A panel has its own Read and Edit, which wins while it is open. A new card always opens to edit.</dd>` +
    `<dt>Secret chips</dt><dd>A secret the card needs hidden, or out.</dd>` +
    `<dt>Edited</dt><dd>You changed a plan's text here. It goes into the vault when you ask Claude to bring the board in.</dd></dl>` +
    `<p class="muted" style="font-size:13.5px">Drag the canvas to pan; pinch, Command-scroll or the + and − buttons to zoom; double-click empty canvas to add a note. Cards snap to the grid.</p>`;
  k.hidden = false; btn.classList.add("on");
  k.querySelector(".x").onclick = () => { k.hidden = true; btn.classList.remove("on"); };
}

/* ---------- saving: JSON Canvas on the Gus relay ---------- */
function toCanvas(k) { return withLane(k, () => canvasOf(k)); }
function canvasOf(k) {   // one board as JSON Canvas (for Obsidian); the store itself is items, cards, edits and edges
  const nodes = [], edges = [], TW = k === WHOLE ? TABW * 3 : TABW, off = t => Math.max(0, doc.sessions.indexOf(t)) * TW, shown = new Set();
  doc.sessions.forEach((t, i) => { ensureAt(t, k); nodes.push({id: "tab-" + t, type: "group", x: i * TW, y: 0, width: TW - 200, height: 2400, label: t}); });
  nodes.push({id: "now", type: "text", x: SX, y: SY, width: 300, height: 220, text: `End of S${CUR}`, osse: {now: true, sessions: doc.sessions}});
  doc.sessions.flatMap(t => inTab(t, k)).sort((a, b) => isScene(b) - isScene(a)).forEach(id => {
    const b = box(id, k), o = it(id), t = sessOf(id), sc = sceneOf(id); if (!b) return;
    shown.add(id);
    const g = {session: t, lx: b.x, ly: b.y, ...(isScene(id) ? {w: b.w, h: b.h} : {}), ...(sc ? {scene: sc} : {}), ...(isAny(id) ? {anytime: o.any} : {}), ...(isFloat(id) ? {floating: true, ...limits(id)} : {})};
    const n = {id, x: off(t) + b.x, y: b.y, width: b.w, height: Math.round(b.h)};
    if (id.startsWith("p:")) {
      const pid = id.slice(2);
      Object.assign(n, {type: "file", file: P[pid].path, osse: {plan: pid, ...g}});
      if (doc.edits[pid]) n.osse.edit = doc.edits[pid];
    } else {
      const c = doc.cards[id.slice(2)], more = [c.where ? `At ${c.where}` : "", c.when || "", c.present && c.present.length ? `Present: ${c.present.join(", ")}` : "", c.purpose ? `Purpose: ${c.purpose}` : "", fieldOf(c, "cue") ? `Cue: ${c.cue}` : "", (fieldOf(c, "who") || []).length ? `Who: ${c.who.join(", ")}` : "", fieldOf(c, "reveals") ? `Reveals: ${c.reveals}` : "", c.clock ? `Clock ${c.clock}` : ""].filter(Boolean);
      Object.assign(n, {type: "text", text: `## ${c.title || "Untitled"}\n\n${more.length ? more.join("\n") + "\n\n" : ""}${c.text || ""}`, osse: {card: true, kind: c.kind, title: c.title, body: c.text, ...g}});
      for (const f of [...Object.keys(FIELDS), "options"]) if (Array.isArray(c[f]) ? c[f].length : c[f]) n.osse[f] = c[f];
      const col = {decision: "1", pressure: "2", complication: "2", note: "3", scene: "4", clock: "5", reveal: "6"}[c.kind]; if (col) n.color = col;
    }
    nodes.push(n);
  });
  doc.edges.forEach(e => {
    const start = e.from.startsWith("start"); if (!shown.has(e.to) || (start ? e.lane !== k : !shown.has(e.from))) return;
    const x = {id: e.id, fromNode: start ? "now" : e.from, fromSide: "right", toNode: e.to, toSide: "left", osse: {own: true, from: e.from}}; if (e.label) x.label = e.label; edges.push(x);
  });
  return {nodes, edges};
}
function migrate(got) {   // boards saved before everything had one copy: merge them
  const lists = [], at = {};
  const keys = [...D.lanes.map(l => l.key).filter(k => got.lanes[k]), ...Object.keys(got.lanes).filter(k => !D.lanes.some(l => l.key === k))];
  const oldCol = (n, col) => ({s: col, x: snap(FIRSTX + Math.max(0, (n.x - 340) % 300)), y: snap(n.y)});   // the first, column layout
  for (const k of keys) {
    const cv = got.lanes[k]; let sess = null, cols = 3;
    (cv.nodes || []).forEach(n => { const o = n.osse || {}; if (o.now) { sess = o.sessions || null; cols = o.cols || 3; } });
    if (!sess) sess = Array.from({length: cols}, (_, i) => "S" + ((got.after || CUR) + 1 + i)).concat("Later");
    lists.push(sess);
    (cv.nodes || []).forEach(n => {
      const o = n.osse || {}, id = o.plan ? "p:" + o.plan : o.card ? n.id : null; if (!id) return;
      if (o.plan && o.edit) doc.edits[o.plan] = {...o.edit, ...(doc.edits[o.plan] || {})};
      if (o.plan && o.tray) return;
      const p = o.session ? {s: o.session, x: o.lx, y: o.ly} : oldCol(n, o.column || "Later");
      (at[k] ||= {})[id] = p;
      if (o.card) { const c = doc.cards[id.slice(2)] = {kind: o.kind || "note", title: o.title || "", text: o.body || ""}; for (const f of ["where", "present", "clock"]) if (o[f]) c[f] = o[f]; }
      const was = it(id);
      if (was) { if (!was.homes.includes(k)) was.homes.push(k); if (!was.scene && was.s === p.s) was.at[k] = {x: p.x, y: p.y}; return; }
      doc.items[id] = {s: p.s, homes: [k], born: k, at: {[k]: {x: p.x, y: p.y}}, ...(o.w ? {w: o.w, h: o.h} : {}), ...(o.scene ? {scene: o.scene} : {})};
    });
    (cv.edges || []).forEach(e => { const o = e.osse || {}; if (!o.own || doc.edges.some(x => x.id === e.id)) return;
      const from = o.from || e.fromNode, start = from === "now" || from.startsWith("start");
      doc.edges.push({id: e.id, from: from === "now" ? "start:S" + ((got.after || CUR) + 1) : from, to: e.toNode, label: e.label || "", ...(start ? {lane: k} : {})}); });
  }
  for (const [id, o] of Object.entries(doc.items)) {
    if (!o.scene) continue;
    const k = o.homes[0], a = (at[k] || {})[id], b = (at[k] || {})[o.scene];
    if (a && b) { o.rx = a.x - b.x; o.ry = a.y - b.y; o.at = {}; } else delete o.scene;
  }
  for (const pid in doc.edits) if (doc.edits[pid].drop) delete doc.items["p:" + pid];
  const used = new Set(Object.values(doc.items).map(o => o.s));
  doc.sessions = [...new Set(lists.flat())].filter(t => used.has(t) || lists.every(l => l.includes(t))).concat([...used]);
  for (const t in got.order || {}) doc.order[t] = got.order[t].map(u => u.includes("|c:") ? u.slice(u.lastIndexOf("|") + 1) : u);
  doc.seeded = keys;
}
function pack() {
  doc.order = runOrder();
  const lanes = {}; D.lanes.forEach(l => { lanes[l.key] = toCanvas(l.key); });
  return {format: "osse-paths-3: one store (sessions, items, cards, edits, edges, order); lanes are the same boards as JSON Canvas 1.0", after: CUR, ...doc, lanes};
}
/* Saving. The relay holds one copy, and another device or a session with Claude may have saved since this page read it:
   every save first looks, and merges record by record what changed there with what changed here (here wins on the same thing). */
const PARTS = ["sessions", "items", "cards", "edits", "edges", "order", "seeded", "arcs"];   // arcs: the Arc planner's part (vault/arcs.html); its linked cards are the sessions' names
let timer = null, dirty = false, unread = false, rev = null, base = null, ticks = 0, busy = null, held = false;
const copyOf = x => JSON.parse(JSON.stringify(x)), same = (a, b) => canon(a) === canon(b), isMap = x => !!x && typeof x === "object" && !Array.isArray(x);
const canon = x => JSON.stringify(x, (k, v) => isMap(v) ? Object.fromEntries(Object.keys(v).sort().map(q => [q, v[q]])) : v) ?? "";
const partsOf = d => { const o = {}; PARTS.forEach(f => { o[f] = copyOf(d[f] ?? (["sessions", "edges", "seeded"].includes(f) ? [] : {})); }); o.edges = Object.fromEntries(o.edges.map(e => [e.id, e])); return o; };
function merge3(b, m, t) {
  if (same(m, b)) return t;
  if (same(t, b) || same(m, t)) return m;
  if (isMap(m) && isMap(t)) { const o = {}; for (const k of new Set([...Object.keys(m), ...Object.keys(t)])) { const v = merge3(isMap(b) ? b[k] : undefined, m[k], t[k]); if (v !== undefined) o[k] = v; } return o; }
  return Array.isArray(m) && Array.isArray(t) ? m.concat(t.filter(x => !m.some(y => same(x, y)) && !(Array.isArray(b) && b.some(y => same(x, y))))) : m;
}
function into(old, now) {   // update in place, so an open panel keeps working on the same card
  for (const k of Object.keys(old)) if (!(k in now)) delete old[k];
  for (const [k, v] of Object.entries(now)) if (isMap(old[k]) && isMap(v)) into(old[k], v); else old[k] = v;
}
function absorb(got) {   // take in what was saved elsewhere; true when it changes what this page holds
  if (!got || !got.items) return false;
  const theirs = partsOf(got), mine = partsOf(doc), out = merge3(base || theirs, mine, theirs);
  base = copyOf(theirs); rev = got.saved_at;
  if (same(out, mine)) return false;
  const had = new Map(doc.edges.map(e => [e.id, e]));
  PARTS.forEach(f => { if (f === "edges") doc.edges = Object.values(out.edges).map(e => { const o = had.get(e.id); if (!o) return e; into(o, e); return o; }); else if (isMap(doc[f])) into(doc[f], out[f]); else doc[f] = out[f]; });
  sortSessions(); Link.tidy(doc.arcs);
  if (layNew()) changed();
  return true;
}
const peek = async () => { const r = await fetch(RELAY + "/paths", {headers: {"x-gus-key": KEY}, cache: "no-store"}); if (!r.ok) throw new Error(r.status === 401 ? "the hub passcode was refused" : "the relay said " + r.status); return r.json(); };
function showNew() { const y = $("#run").scrollTop; draw(); if (runMode) $("#run").scrollTop = y; if (shown && !$("#drawer").hidden && !live(shown) && !P[shown.slice(2)]) closeDrawer(); }
function status(t, bad) { const el = $("#save"); el.textContent = t; el.classList.toggle("bad", !!bad); }
function changed() {
  dirty = true; ticks++; store.set("osse-paths-local", JSON.stringify(pack()));
  if (unread) { status("Not saving: the relay could not be read when this page opened. Reload before you change more.", true); return; }
  status(KEY ? "Saving…" : "Saved on this device only");
  later();
}
function later(ms = 800) { clearTimeout(timer); if (KEY) timer = setTimeout(() => save(), ms); }
async function save(leaving) {
  if (leaving !== true) {
    if (held) { later(); return; }          // not in the middle of a drag
    if (busy) { later(300); return; }
  }
  const work = (async () => {
    try {
      let fresh = null;
      if (leaving !== true) { const got = fresh = await peek(); if (held) { later(); return; } if (got.items && got.saved_at !== rev && absorb(got)) showNew(); }
      const at = ticks, sent = pack();
      if (fresh && fresh.arcs && !sent.arcs) sent.arcs = doc.arcs = fresh.arcs;
      const body = JSON.stringify(sent);   // keepalive only when leaving: browsers allow 64 KB of it in all, then refuse
      const r = await fetch(RELAY + "/paths", {method: "PUT", headers: {"x-gus-key": KEY, "content-type": "application/json"}, body, keepalive: leaving === true && new Blob([body]).size < 60000});
      if (!r.ok) throw new Error(r.status === 401 ? "the hub passcode was refused" : "the relay said " + r.status);
      rev = (await r.json()).saved_at; base = partsOf(JSON.parse(body));
      if (ticks === at) { dirty = false; status("Saved"); clearTimeout(timer); }
    } catch (e) { status("Not saved: " + e.message + ". This device keeps a copy.", true); }
  })();
  busy = work; await work; if (busy === work) busy = null;
}
async function look() {   // anything new from another device or a session with Claude?
  if (!KEY || unread || dirty || busy || held || document.visibilityState === "hidden") return;
  if (document.activeElement && document.activeElement.matches("#drawer input, #drawer textarea, #drawer select")) return;
  const work = (async () => { try { const got = await peek(); if (dirty || held || !got.items || got.saved_at === rev) return; if (absorb(got)) { showNew(); toast("Updated: the boards were changed somewhere else."); } } catch (e) {} })();
  busy = work; await work; if (busy === work) busy = null;
}
setInterval(look, 20000);
addEventListener("focus", look);
addEventListener("pointerdown", () => { held = true; }, true);
["pointerup", "pointercancel", "blur"].forEach(n => addEventListener(n, () => { held = false; }, true));
async function load() {
  let got = null;
  if (KEY) {
    try {
      const r = await fetch(RELAY + "/paths", {headers: {"x-gus-key": KEY}, cache: "no-store"});
      if (r.ok) { got = await r.json(); status("Saved"); }
      else unread = true, status(r.status === 401 ? "Hub passcode refused: unlock the hub again to save." : "The relay said " + r.status + ": showing this device's copy.", true);
    } catch (e) { unread = true; status("Relay unreachable: showing this device's copy. Reload before you change anything.", true); }
  } else status("Unlock the game master section on the hub to save to the relay. Until then this device keeps your changes.");
  const some = g => g && (g.items || (g.lanes && Object.keys(g.lanes).length));
  if (!some(got)) { try { const loc = JSON.parse(store.get("osse-paths-local") || "null"); if (some(loc)) { got = loc; if (KEY && !unread) dirty = true; } } catch (e) {} }
  if (got && got.items) { if (!dirty) { base = partsOf(got); rev = got.saved_at; } for (const f of PARTS) { if (got[f]) doc[f] = got[f]; } }
  else if (some(got)) { migrate(got); dirty = true; }
  doc.sessions = (doc.sessions.length ? doc.sessions : defaults()).filter(t => t === "Later" || sessNum(t) > CUR || Object.values(doc.items).some(o => o.s === t));
  sortSessions();
  if (Object.keys(Link.settle(doc, CUR)).length) dirty = true;
  if (!doc.seeded.includes("@canvas")) { Object.values(doc.items).forEach(o => { if (o.at) delete o.at[WHOLE]; }); doc.seeded.push("@canvas"); }   // once: The Party's board became the session canvas
  D.lanes.forEach(l => { if (!doc.seeded.includes(l.key)) seed(l.key); });
  if (layNew()) dirty = true;
  if (dirty && KEY && !unread) save();
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") { if (dirty && KEY && !unread) save(true); } else look(); });

/* ---------- boards ---------- */
function pick(key) {
  if (lane && !runMode) keepView();
  const from = runMode ? runTab : lane === WHOLE ? tabOf[WHOLE] : null;   // the two whole-session views stay on the same session
  runMode = key === RUN;
  if (from && key === WHOLE) tabOf[WHOLE] = from; if (from && runMode) runTab = from;
  $(".paths").classList.toggle("whole", runMode || key === WHOLE);
  $("#runw").hidden = !runMode; $("#work").hidden = runMode;
  store.set("osse-paths-lane", key); history.replaceState(null, "", "#" + encodeURIComponent(key));
  $$("[data-lane]").forEach(b => b.setAttribute("aria-selected", b.dataset.lane === key));
  closeDrawer();
  if (runMode) { if (!lane) lane = D.lanes[0].key; drawRun(); return; }
  lane = key; draw();
  backTo();
}
$("#views").innerHTML = `<button role="tab" data-lane="${RUN}" title="The session's scenes, in the order you plan to run them">${icon("list")}Running order</button>` +
  `<button role="tab" data-lane="${WHOLE}" title="The same session as a canvas: every scene and card, whoever it is for">${icon("map")}Canvas</button>`;
$("#lanes").innerHTML = `<span class="lb">Boards</span>` + PCS.map(l => `<button role="tab" data-lane="${esc(l.key)}"><i style="--c:${esc(l.colour)}"></i>${esc(l.short)}<small>${l.count}</small></button>`).join("") + `<span class="sep"></span>` +
  D.lanes.filter(l => l.kind === "world").map(l => `<button role="tab" class="wb" data-lane="${esc(l.key)}" title="What moves without the party knowing, and could still reach them">${icon("globe")}${esc(l.short)}<small>${l.count}</small></button>`).join("");
$$("[data-lane]").forEach(b => b.onclick = () => pick(b.dataset.lane));
$("#pal").innerHTML = ["scene", ...INSCENE, "|", "pressure", "clock", "bottleneck", "note"].map(k => k === "|" ? `<span class="sep"></span>` : `<button class="k-${k}" data-pal="${k}" title="${esc(KINDS[k])}: ${esc(KDESC[k])}">${icon(k, 17)}<span>${KINDS[k]}</span></button>${k === "scene" ? `<span class="sep"></span>` : ""}`).join("");
$$("#pal [data-pal]").forEach(b => palDrag(b, b.dataset.pal));
const rwPaint = () => { $("#rw").innerHTML = rwBtns(rw); $("#rw").querySelectorAll("button").forEach(b => { b.title = b.dataset.rw === "view" ? "Cards open to read" : "Cards open to edit"; b.onclick = () => { rw = b.dataset.rw; own = null; store.set("osse-paths-rw", rw); rwPaint(); if (repaint) { draw(); repaint(); } }; }); };
rwPaint();
$$("[data-tray]").forEach(trayUi);
$$("[data-act]").forEach(b => b.onclick = ev => {
  ev.stopPropagation();
  const a = b.dataset.act;
  const r = board.getBoundingClientRect();
  if (a === "zin" || a === "zout") zoomAt(view.k * (a === "zin" ? 1.25 : .8), r.left + r.width / 2, r.top + r.height / 2);
  if (a === "fit") fit();
  if (a === "line") tidy(T(), lane);
  if (a === "legend") legend();
});
$$(".float button").forEach(b => b.onpointerdown = ev => ev.stopPropagation());
document.addEventListener("keydown", e => {
  if ((e.key === "Delete" || e.key === "Backspace") && shown && !e.target.closest("input,textarea,select")) { e.preventDefault(); removeCard(shown); return; }
  if (e.key === "Escape") { if (!$("#drawer").hidden) closeDrawer(); else if (!$("#keyp").hidden) legend(); } });
/* a click on the main area closes the open panel; a drag, or a click that opens another card, does not */
let press = null;
addEventListener("pointerdown", e => { press = !$("#drawer").hidden && e.button < 1 && {x: e.clientX, y: e.clientY, at: e.target, was: $("#drawer").firstChild}; }, true);
addEventListener("pointercancel", () => { press = null; }, true);
addEventListener("pointerup", e => {
  const p = press; press = null;
  if (!p || Math.hypot(e.clientX - p.x, e.clientY - p.y) >= 5 || !p.at.closest || !p.at.closest(".paths") || p.at.closest(".drawer")) return;
  if (p.at.closest("button,a,input,select,textarea,label,summary,.float,.keyp,.wl,.rng,[data-edge],.tr,.li,.ti,.rc .rg,.bn:not(.now):not(.scene),.bn.scene .sh,.bn .rz,.bn .hd")) return;   // these do something of their own
  setTimeout(() => { if (!$("#drawer").hidden && $("#drawer").firstChild === p.was) { closeDrawer(); draw(); } }, 0);
}, true);
document.body.insertAdjacentHTML("beforeend", `<div id="meas" aria-hidden="true"></div><div id="tip" role="tooltip" hidden></div><datalist id="dl-places">${D.places.map(x => `<option value="${esc(x)}">`).join("")}</datalist>` +
  `<datalist id="dl-secrets">${D.secrets.filter(x => !x.out).map(x => `<option value="${esc(x.n)}">`).join("")}</datalist><datalist id="dl-people">${D.people.map(x => `<option value="${esc(x.n)}" label="${esc(x.t)}">`).join("")}</datalist>`);
load().then(() => {
  const s0 = new URLSearchParams(location.search).get("s"); if (s0 && doc.sessions.includes(s0)) { runTab = s0; [...D.lanes.map(l => l.key), WHOLE].forEach(k => { tabOf[k] = s0; }); }   // from the Arc planner
  const want = decodeURIComponent(location.hash.slice(1)) || store.get("osse-paths-lane");
  pick(want === RUN || D.lanes.some(l => l.key === want) ? want : D.lanes[0].key);
});
})();
"""
