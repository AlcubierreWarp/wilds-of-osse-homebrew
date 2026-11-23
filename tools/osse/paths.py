#!/usr/bin/env python3
"""Paths ahead: the DM's planning board (vault/paths.html). Built by pages.py on every build; never edit the page by hand.

One board per player character, plus The Party and Around the party. Each board has a tab and a canvas per session
(the next sessions, then Later). The first tab starts from the end of the last played session; each later tab starts
from the end of the one before, as planned. Each board's live plans wait in a tray beside it; Tom drags the ones he
wants onto a session's canvas, draws links between cards, adds, edits and deletes cards, and adds or deletes sessions.
Plans that already have a `target` start in that session's tab. Edits to a plan's text and plans he drops are kept as
overrides until Claude writes them into the vault. The layout is saved as JSON Canvas (jsoncanvas.org) on the Gus relay,
behind the hub's game master passcode; `tools/osse/paths_sync.py` reads it so Claude can turn Tom's changes into
vault plans (see the `paths` skill). The vault stays the truth: the board only places and connects.

Which plans sit in a board's tray: plans whose `for:` names that character; else plans that name the character in
their Links or Requires; else plans that touch someone tied to the character at weight 5; else The Party's board when
they name The Party; else Around the party. The tray can also show every live plan.
The rules for kinds, options and branching are in docs/osse/branching.md."""
import json, re

import build

STANDING = {"pc", "npc", "faction", "item", "party"}   # link ends a what-if can kill
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
                     "kind": str(n.get("kind") or "beat").lower(),
                     "where": _plain(n.get("where") or ""), "present": [_plain(x) for x in _list(n.get("present"))],
                     "scene": _plain(n.get("scene") or ""), "clock": str(n.get("clock") or ""), "target": str(n.get("target") or ""),
                     "summary": _plain(n.get("summary")), "req": req, "lanes": lanes, "via": via,
                     "idea": site.blocks(sec.get("Idea", [])),
                     "ideaText": "\n".join(_plain(x) for x in sec.get("Idea", [])).strip(),
                     "options": [{"to": t, "label": c} for t, c in build.parse_options(text) if t],
                     "links": [f'{l["from"]} · {l["type"]} · {l["to"]}' + (f' ({l["note"]})' if l.get("note") else "") for l in links]}

    facts = {}
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
        out.append({"key": "The Party", "short": "The party", "kind": "party",
                    "now": {"title": "The whole party", "href": site.slugs.get("The Party", "") + ".html",
                            "location": _plain(party.get("location", "")), "state": party.get("state", ""),
                            "members": [{"name": p["id"], "sheet": sheet(p)} for p in pcs],
                            "summary": _plain(last.get("summary")) if last else "", "recent": recent[:3], "recent_at": top}})
    opens = next((v for k, v in last_secs.items() if k.startswith("Open going into")), [])
    out.append({"key": "world", "short": "Around the party", "kind": "world",
                "now": {"title": "Around the party", "href": site.slugs.get(last["id"], "") + ".html" if last else "",
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
    payload = {"cur": cur, "plans": data, "facts": facts, "lanes": lanes, "gone": sorted(build.GONE), "places": places, "people": people}
    js_data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    head = pages.head("Paths ahead", False).replace('<div class="wrap">', '<div class="wrap wide">')
    return (head + f"<style>{CSS}</style>" + pages.topbar(site, "Paths ahead") +
            '<main class="sheet paths">'
            '<div class="ptop"><h1>Paths ahead</h1><nav class="lanes" id="lanes" role="tablist" aria-label="Boards"></nav></div>'
            '<div class="bar"><div class="whatif"><b>What-ifs</b><span id="wi-list" class="muted"></span>'
            '<button id="wi-reset" class="mini" hidden>Clear</button></div>'
            '<div class="tools"><button class="mini" data-act="scene">+ Scene</button><button class="mini" data-act="card">+ Card</button><span id="save" class="save"></span></div></div>'
            '<div class="runw" id="runw" hidden><div class="stage"><nav class="sess" id="rsess" role="tablist" aria-label="Sessions"></nav>'
            '<div class="run" id="run" aria-label="Running order"></div></div>'
            '<aside class="tray" id="loose"></aside></div>'
            '<div class="work" id="work"><div class="stage"><nav class="sess" id="sess" role="tablist" aria-label="Sessions"></nav>'
            '<div class="board" id="board" aria-label="Planning board">'
            '<div class="world" id="world"><svg id="wires" class="wires"></svg><div id="nodes"></div></div>'
            '<div class="float"><button class="fb" data-act="zout" title="Zoom out" aria-label="Zoom out">−</button><button class="fb" data-act="zin" title="Zoom in" aria-label="Zoom in">+</button><button class="fb" data-act="fit" title="Fit to the window" aria-label="Fit to the window">'
            '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 8V3h5M12 3h5v5M17 12v5h-5M8 17H3v-5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></button>'
            '<button class="fb" data-act="legend" title="Key" aria-label="Key">Key</button></div>'
            '<div class="keyp" id="keyp" hidden></div>'
            '<div class="hint" id="hint"></div></div></div>'
            '<aside class="tray" id="tray"><div class="trayh"><b>Not placed yet</b>'
            '<label class="all"><input type="checkbox" id="tray-all"> every live plan</label></div>'
            '<input id="tray-q" type="search" placeholder="Find a plan" autocomplete="off">'
            '<div id="tray-list" class="tlist"></div></aside></div>'
            '<aside id="drawer" class="drawer" hidden></aside>'
            f'<footer>Built from the Ossë vault after S{cur}: {len(live)} live plans, '
            f'{sum(1 for p in plans.values() if p.get("status") == "pruned")} pruned, '
            f'{sum(1 for p in plans.values() if p.get("status") == "played")} played. Nothing here is canon. '
            "Placing, linking, edits and new cards change only this board until you ask Claude to bring them into the vault. "
            "What-ifs change nothing anywhere. Rules: <code>docs/osse/branching.md</code>.</footer>"
            f'<script>const PATHS={js_data};</script><script>{JS}</script></main></div></body></html>')


CSS = r"""
.wrap.wide{max-width:none}
.paths{padding:clamp(14px,2.4vw,26px)}
.ptop{display:flex;flex-wrap:wrap;align-items:center;gap:10px 22px}
.lanes{display:flex;flex-wrap:wrap;gap:4px}
.lanes button{font:600 13px/1 var(--f-display);letter-spacing:.06em;color:var(--vmuted);background:rgba(255,255,255,.35);border:1px solid var(--vline);border-radius:999px;padding:9px 13px;cursor:pointer}
.lanes button small{color:inherit;font:500 11px var(--f-mono);margin-left:5px;opacity:.75}
.lanes button[aria-selected=true]{background:var(--vink);color:var(--vellum);border-color:var(--vink)}
.bar{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;justify-content:space-between;margin:12px 0 10px}
.whatif{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:14.5px}
.whatif b,.trayh b{font:600 11.5px var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:var(--vred)}
.wi{display:inline-flex;align-items:center;gap:6px;padding:3px 4px 3px 10px;border-radius:999px;background:var(--vink);color:var(--vellum);font-size:13.5px}
.wi button{border:0;background:rgba(255,255,255,.18);color:inherit;border-radius:999px;width:22px;height:22px;cursor:pointer}
.tools{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.mini{font:500 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--vrule);background:rgba(255,255,255,.45);color:var(--vred);border-radius:4px;padding:8px 10px;cursor:pointer}
.mini:hover{background:#fff}
.save{font:500 11.5px var(--f-mono);color:var(--vmuted);margin-left:4px;max-width:420px}.save.bad{color:var(--vred)}
.work{display:grid;grid-template-columns:1fr 300px;gap:12px;height:calc(100vh - 200px);min-height:480px}
.stage{display:flex;flex-direction:column;min-height:0;min-width:0}
.sess{display:flex;gap:2px;align-items:flex-end;overflow-x:auto;padding-left:6px}
.sess button{font:600 13px/1 var(--f-display);letter-spacing:.08em;color:var(--vmuted);background:rgba(255,255,255,.3);border:1px solid var(--vrule);border-bottom:0;border-radius:6px 6px 0 0;padding:10px 14px 9px;cursor:pointer;white-space:nowrap}
.sess button small{font:500 10.5px var(--f-mono);letter-spacing:.02em;margin-left:6px;opacity:.8}
.sess button[aria-selected=true]{background:#f6eed8;color:var(--vred);position:relative;top:1px}
.sess button.drop{background:rgba(124,22,34,.15)}
.sess .dx{display:inline-block;margin-left:8px;padding:0 4px;border-radius:3px;font:600 13px var(--f-mono);color:var(--vmuted)}.sess .dx:hover{background:var(--vred);color:var(--vellum)}
.sess .add{font:500 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--vred);border-style:dashed}
.board{position:relative;flex:1;min-height:0;overflow:hidden;border:1px solid var(--vrule);border-radius:0 8px 8px 8px;
  background-color:#f6eed8;background-image:radial-gradient(circle,rgba(42,29,18,.2) 1.1px,transparent 1.4px);touch-action:none;cursor:grab}
.board.panning{cursor:grabbing}
.world{position:absolute;left:0;top:0;transform-origin:0 0}
.wires{position:absolute;left:0;top:0;width:1px;height:1px;overflow:visible;pointer-events:none}
.wires path{fill:none;stroke:rgba(124,22,34,.45);stroke-width:1.8}
.wires path.own{stroke:var(--vred);stroke-dasharray:6 4;stroke-width:2}
.wires path.opt{stroke:var(--vink);stroke-width:2}
.wires path.carry{stroke:rgba(42,29,18,.35);stroke-dasharray:2 4}
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
.bn .chips,.ti .chips{display:flex;flex-wrap:wrap;gap:4px;margin:2px 0 0}
.ch{font:500 10.5px/1.5 var(--f-mono);padding:0 6px;border-radius:3px;border:1px solid var(--vline);background:rgba(255,255,255,.6);white-space:nowrap;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.ch.ready{background:var(--vink);color:var(--vellum);border-color:var(--vink)}.ch.sec{border:1px dashed var(--vred);color:var(--vred);cursor:pointer}
.ch.sec.out{background:var(--vred);color:var(--vellum);border-style:solid}.ch.move{background:#b8860b;color:#fff;border-color:#b8860b}.ch.ck{border-color:#b8860b;color:#7a5a08}
.ch.ed{border:1px dashed var(--vred);color:var(--vred)}
.bn .opts{margin:2px 0 0;padding:0;list-style:none;font-size:13px}.bn .opts li{margin:2px 0}.bn .opts li::before{content:"◇ ";color:var(--vred)}
.bn .why{display:none;font:500 11px/1.3 var(--f-mono);color:var(--vred)}
.bn.cut{opacity:.45}.bn.cut .t{text-decoration:line-through}.bn.cut .why{display:block}
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
.k-scene{border-left-color:#4d6b4a}.k-clock{border-left-color:#3d5a80}.bn.k-clock .k{color:#3d5a80}
.at{font-size:13.5px}.at b{font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vmuted);margin-right:5px}
.ch.who{background:#e7efe3;border-color:#9bb397;color:#2f4a2c;display:inline-flex;align-items:center;gap:3px}
.ch.who button{border:0;background:none;cursor:pointer;color:var(--vred);font:600 12px var(--f-mono);padding:0 0 0 3px}
.clk{display:flex;align-items:center;gap:8px;font:500 12px var(--f-mono);color:#3d5a80}
.rng{border:0;background:none;padding:0;cursor:pointer;line-height:0;display:inline-block}
.rng path{fill:rgba(255,255,255,.8);stroke:#3d5a80;stroke-width:1.4}.rng path.on{fill:#3d5a80}
.clkf{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.drawer .clkf select{width:auto}
.whobox{display:flex;flex-wrap:wrap;gap:4px;margin:2px 0 6px}
.drawer .inscene{font-size:14.5px;color:var(--vmuted);margin:6px 0}
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
.hint{position:absolute;left:12px;bottom:10px;font:500 11px var(--f-mono);color:var(--vmuted);background:rgba(246,238,216,.9);padding:4px 8px;border-radius:4px;pointer-events:none}
.tray{display:flex;flex-direction:column;min-height:0;border:1px solid var(--vrule);border-radius:8px;background:rgba(255,255,255,.3);padding:10px}
.tray.over{background:rgba(124,22,34,.1);border-style:dashed}
.trayh{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.all{font:500 11px var(--f-mono);color:var(--vmuted)}
#tray-q{width:100%;font:15px var(--f-body);padding:8px 10px;margin:8px 0;border:1px solid var(--vline);border-radius:4px;background:rgba(255,255,255,.6);color:var(--vink)}
.tlist{overflow:auto;min-height:0;flex:1}
.tlist h4{margin:10px 0 4px;font:600 11px var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted)}
.ti{display:flex;gap:8px;align-items:flex-start;padding:8px;margin:0 0 6px;border:1px solid var(--vline);border-left:4px solid var(--vmuted);border-radius:5px;background:#fbf5e6;cursor:grab;touch-action:pan-y;user-select:none;-webkit-user-select:none}
.ti>div{min-width:0}
.ti .g{flex:none;width:18px;color:var(--vmuted);font-size:16px;line-height:1.1;touch-action:none;cursor:grab}
.ti .t{font-weight:600;font-size:14.5px;line-height:1.25}.ti .s{font-size:12.5px;color:var(--vmuted);line-height:1.3}
.tlist .gone{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:13.5px;color:var(--vmuted);padding:4px 2px;border-bottom:1px dashed var(--vline)}
.tlist .gone s{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ti.cut{opacity:.45}.ti.cut .t{text-decoration:line-through}
.empty{color:var(--vmuted);font-style:italic;font-size:14px}
.ghost{position:fixed;z-index:50;pointer-events:none;width:220px;opacity:.92;transform:rotate(-2deg)}
.drawer{position:fixed;right:16px;top:16px;bottom:16px;width:min(440px,calc(100vw - 32px));overflow:auto;z-index:40;
  background:linear-gradient(180deg,var(--vellum),var(--vellum-2));color:var(--vink);border:1px solid var(--vrule);border-radius:8px;padding:18px 20px 24px;box-shadow:0 20px 50px rgba(0,0,0,.45);font-size:16px}
.drawer h3{font-size:22px;margin:0 30px 6px 0}.drawer .x{position:absolute;right:12px;top:8px;border:0;background:none;font-size:28px;cursor:pointer;color:var(--vmuted)}
.drawer h4{margin:16px 0 4px}.drawer .ey{font:500 11px var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted)}
.drawer label{display:block;font:500 11px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--vmuted);margin:12px 0 4px}
.drawer input[type=text],.drawer textarea,.drawer select{width:100%;font:16px var(--f-body);padding:8px 10px;border:1px solid var(--vline);border-radius:4px;background:rgba(255,255,255,.65);color:var(--vink)}
.drawer textarea{min-height:110px;resize:vertical}
.drawer .row{display:flex;gap:10px}.drawer .row>div{flex:1}
.req{list-style:none;padding:0;margin:4px 0}
.req li{display:flex;gap:8px;align-items:baseline;padding:5px 0;border-bottom:1px dashed var(--vline);font-size:15px}
.req .ok{font:600 12px var(--f-mono);width:14px;flex:none}.req .ok.y{color:#2f6b3a}.req .ok.n{color:var(--vred)}.req .ok.m{color:#b8860b}
.req .kk{font:500 11px var(--f-mono);color:var(--vmuted);flex:none;min-width:54px}.req small{display:block}
.req button{margin-left:auto;flex:none}
.acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.acts a,.acts button{font:500 11px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;border:1px solid var(--vink);border-radius:4px;padding:9px 11px;color:var(--vink);background:none;cursor:pointer;text-decoration:none}
.acts .del{border-color:var(--vred);color:var(--vred)}
.drawer .tabs2{display:flex;gap:4px;margin:12px 0 4px}
.drawer .tabs2 button{font:500 11px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;border:1px solid var(--vline);background:none;border-radius:4px;padding:7px 10px;cursor:pointer;color:var(--vmuted)}
.drawer .tabs2 button[aria-selected=true]{border-color:var(--vink);color:var(--vink);background:rgba(255,255,255,.5)}
.work[hidden],.runw[hidden]{display:none}
.lanes button.runb{color:#3f5a3c;border-color:#9bb397;background:#e7efe3}
.lanes button.runb[aria-selected=true]{background:#3f5a3c;color:var(--vellum);border-color:#3f5a3c}
.runw{display:grid;grid-template-columns:1fr 300px;gap:12px;height:calc(100vh - 200px);min-height:480px}
.run{flex:1;min-height:0;overflow:auto;border:1px solid var(--vrule);border-radius:0 8px 8px 8px;background:#f6eed8;padding:14px clamp(10px,2vw,22px) 40px}
.runh{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:6px 14px;margin:0 0 10px;font-size:14.5px;color:var(--vmuted)}
.runh b{font:600 12px var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:#3f5a3c}
.rc{display:grid;grid-template-columns:20px 30px 1fr auto;gap:2px 10px;align-items:start;max-width:760px;margin:0 0 8px;padding:8px 10px 8px 6px;
  background:#fbf5e6;border:1px solid var(--vline);border-left:5px solid #4d6b4a;border-radius:6px;box-shadow:0 1px 4px rgba(42,29,18,.1);user-select:none;-webkit-user-select:none}
.rc.cut{opacity:.45}.rc.cut .rt b{text-decoration:line-through}
.rc.drag{position:relative;z-index:5;box-shadow:0 10px 24px rgba(42,29,18,.3);opacity:.95}
.rc .rg{color:var(--vmuted);font-size:17px;line-height:1.3;cursor:grab;touch-action:none;text-align:center}
.rc .rn{font:600 19px/1.1 var(--f-display);color:#3f5a3c;text-align:center}
.rc .rb{min-width:0;cursor:grab}
.rc .rt{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px}.rc .rt b{font-weight:600;font-size:15.5px;line-height:1.25}
.rc .rw{font-size:13px;color:var(--vmuted);margin-top:1px}
.pcs{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}
.pcx{font:700 10.5px/1.55 var(--f-mono);letter-spacing:.06em;text-transform:uppercase;padding:0 7px;border-radius:4px;border:2px solid var(--c);color:#1b1410;background:color-mix(in srgb,var(--c) 18%,#fbf5e6);white-space:nowrap}
.pcx.in{background:var(--c)}button.pcx{cursor:pointer}button.pcx:hover{outline:2px solid var(--vink);outline-offset:1px}
.ch.who.pc{border:2px solid var(--c);background:color-mix(in srgb,var(--c) 30%,#fbf5e6);color:#1b1410}
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
.tr:hover{background:rgba(124,22,34,.07)}.tr.on,.li.on{box-shadow:0 0 0 2px rgba(124,22,34,.35)}.tr.cut{opacity:.45;text-decoration:line-through}
.tr .rg,.li .rg{flex:none;width:16px;color:var(--vmuted);font-size:15px;line-height:1.1;cursor:grab;touch-action:none;text-align:center}
.tr .tt{min-width:0;flex:1}.tr .el{color:var(--vred);font-size:13px}.tr .el::after{content:" →"}.tr .rng{align-self:center}
.tr small{color:var(--vmuted);font-size:12px}
.tr.in-on{background:rgba(124,22,34,.16);box-shadow:inset 0 0 0 2px var(--vred)}
.tr.in-before::before,.tr.in-after::before,.rc.in-before::before{content:"";position:absolute;left:0;right:0;height:3px;border-radius:2px;background:var(--vred);top:-2px}
.tr.in-after::before{top:auto;bottom:-2px}.rc.in-before{position:relative}.rc.in-before::before{top:-7px}
.rc.hot{border-color:var(--vred);box-shadow:0 0 0 2px rgba(124,22,34,.35)}
#loose.over{background:rgba(124,22,34,.1);border-style:dashed}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:60;max-width:min(560px,calc(100vw - 32px));background:var(--vink);color:var(--vellum);border-radius:8px;padding:12px 16px;font-size:15px;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.bn.flash,.bn.scene.flash{outline:3px solid var(--vred);outline-offset:4px}
.mk{flex:none;min-width:74px;font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vmuted);border-left:4px solid var(--vmuted);padding-left:6px}
.mk.k-decision{border-left-color:var(--vred);color:var(--vred)}.mk.k-pressure{border-left-color:#b8860b;color:#7a5a08}.mk.k-clock{border-left-color:#3d5a80;color:#3d5a80}
.mk.k-bottleneck{border-left:4px double var(--vink);color:var(--vink)}.mk.k-note{border-left-color:#c9a400}
.rc .rm .acts{margin-top:6px}
.loose h4{margin:12px 0 4px;display:flex;align-items:center;gap:6px}
.loose p{font-size:13.5px;margin:6px 0 0}.loose .free{margin-top:16px;border-top:1px dashed var(--vline);padding-top:10px}.loose summary{cursor:pointer}.loose summary b{font:600 11.5px var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:var(--vred)}
#run-q{width:100%;font:15px var(--f-body);padding:8px 10px;margin:8px 0;border:1px solid var(--vline);border-radius:4px;background:rgba(255,255,255,.6);color:var(--vink)}
.loose .li{display:flex;gap:6px;align-items:baseline;user-select:none;-webkit-user-select:none}.loose .li small{display:block;color:var(--vmuted);font-size:12px}
.loose .li{padding:6px 8px 6px 4px;margin:0 0 5px;border:1px solid var(--vline);border-left:4px solid var(--vmuted);border-radius:5px;background:#fbf5e6;cursor:pointer;font-size:14px}
.loose .li:hover{border-color:var(--vred)}
@media (max-width:900px){.runw{grid-template-columns:1fr;grid-template-rows:1fr 30vh;height:calc(100vh - 170px)}}
@media (max-width:900px){.work{grid-template-columns:1fr;grid-template-rows:1fr 34vh;height:calc(100vh - 170px)}}
@media print{.bar,.tray,.drawer,.float,.rg,.rx{display:none}.runw{display:block;height:auto}.run{overflow:visible}.work{display:block;height:auto}}
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
const GRID = 22, CARDW = 250, SX = 44, SY = 44, FIRSTX = 418, TABW = 4000, SCW = 572, SCH = 396;
const snap = v => Math.round(v / GRID) * GRID;
const KINDS = {scene: "Scene", beat: "Beat", decision: "Decision", clock: "Clock", pressure: "Pressure", bottleneck: "Bottleneck", note: "Note"};
const PLANKINDS = ["scene", "beat", "decision", "clock", "pressure", "bottleneck"];
const KDESC = {scene: "Where, and who is there: it sets the stage. A box on the board; the cards inside it happen during the scene.",
  beat: "One key moment in a scene or encounter: a situation to put in front of them, not a script.",
  clock: "Time pressure: something happens when its segments fill. Tap the clock on the card to fill a segment.",
  decision: "A choice the character faces. Each option leads to its own card; label each link with the choice.",
  pressure: "What the world does if no one acts: a portent that fires when they stall.",
  bottleneck: "A beat most paths reach, where branches meet again.",
  note: "A loose idea. Claude turns it into a plan when you ask."};
let doc = {sessions: [], items: {}, cards: {}, edits: {}, edges: [], order: {}, seeded: []};
let lane = null, view = {x: 0, y: 0, k: 1}, views = {}, hs = {}, hsh = {};
const tabOf = {};   // board -> open session tab

/* ---------- state: one copy of everything, shown on as many boards as it belongs to ----------
   items[id]: s (session), homes (boards it was put on), at {board: {x,y}}, w and h (a scene's size),
   scene with rx, ry (a card inside a scene: its place in the box, the same on every board) */
const sessNum = s => +(String(s).match(/^S(\d+)$/i) || [])[1] || 0;
function defaults() { return [1, 2, 3].map(i => "S" + (CUR + i)).concat("Later"); }
const L = () => doc;
const it = id => doc.items[id];
const live = id => !!it(id) && (id.startsWith("p:") ? !!P[id.slice(2)] : !!doc.cards[id.slice(2)]);   // a played or dropped plan stays stored, unseen
const T = () => { if (runMode) return runTab; if (!doc.sessions.includes(tabOf[lane])) tabOf[lane] = doc.sessions[0]; return tabOf[lane]; };
const view_of = id => { const p = P[id], e = doc.edits[id] || {}; return {...p, summary: e.summary ?? p.summary, kind: e.kind ?? p.kind, ideaText: e.idea ?? p.ideaText,
  where: e.where ?? p.where, present: e.present ?? p.present, clock: e.clock ?? p.clock, edited: Object.keys(e).some(k => k !== "drop")}; };
const objOf = id => id.startsWith("p:") ? (P[id.slice(2)] ? view_of(id.slice(2)) : null) : doc.cards[id.slice(2)] || null;
const kindOf = id => (objOf(id) || {}).kind || "";
const isScene = id => kindOf(id) === "scene";
const sceneOf = id => { const sc = (it(id) || {}).scene; return sc && live(sc) && isScene(sc) && !isScene(id) ? sc : null; };
const sessOf = id => it(id) ? it(sceneOf(id) || id).s : null;
const membersOf = sid => Object.keys(doc.items).filter(i => live(i) && sceneOf(i) === sid);
function castLanes(id) {   // the boards of the player characters a scene lists as present
  const out = new Set();
  ((objOf(id) || {}).present || []).forEach(n => { const p = pcOf(n);
    if (p === "party") D.lanes.forEach(l => { if (l.kind !== "world") out.add(l.key); }); else if (p) out.add(p); });
  return [...out];
}
function lanesOf(id) {   // the boards an item shows on
  const sc = sceneOf(id); if (sc) return lanesOf(sc);
  const o = it(id), ks = isScene(id) ? [...new Set([...o.homes, ...castLanes(id)])] : o.homes;
  return ks.length ? ks : [o.born || D.lanes[0].key];
}
const inTab = (t, k = lane) => Object.keys(doc.items).filter(i => live(i) && sessOf(i) === t && lanesOf(i).includes(k));
function measure(ids) {   // card heights, off screen: needed for boards not drawn yet
  const m = $("#meas"); m.innerHTML = ids.map(cardHtml).join("");
  m.querySelectorAll(".bn").forEach(el => { hs[el.dataset.id] = el.offsetHeight; const h = el.querySelector(".sh"); if (h) hsh[el.dataset.id] = h.offsetHeight; });
  m.innerHTML = "";
}
function box(id, k = lane) {
  if (id === "start") return {x: SX, y: SY, w: 300, h: hs.start || 200};
  if (!live(id)) return null;
  const o = it(id), sc = sceneOf(id);
  if (sc) { const b = box(sc, k); return b && {x: b.x + (o.rx ?? 22), y: b.y + (o.ry ?? 132), w: CARDW, h: hs[id] || 110}; }
  const a = (o.at ||= {})[k]; if (!a) return null;
  return isScene(id) ? {x: a.x, y: a.y, w: o.w || SCW, h: o.h || SCH, hh: hsh[id] || 96, sc: 1} : {x: a.x, y: a.y, w: CARDW, h: hs[id] || 110};
}
function freeSpot(t, k = lane) {
  const bs = inTab(t, k).map(i => box(i, k)).filter(b => b && b.x < FIRSTX + CARDW && b.x + b.w > FIRSTX);
  return {x: FIRSTX, y: bs.length ? snap(Math.max(...bs.map(b => b.y + b.h)) + 44) : SY};
}
function ensureAt(t, k = lane) {   // everything that belongs on board k has a place there
  const ids = inTab(t, k), miss = ids.filter(i => hs[i] === undefined);
  if (miss.length) withLane(k, () => measure(miss));
  ids.filter(i => !sceneOf(i) && !(it(i).at ||= {})[k]).sort((a, b) => isScene(b) - isScene(a)).forEach(i => { it(i).at[k] = freeSpot(t, k); });
}
function setPos(id, x, y) {
  const o = it(id), sc = sceneOf(id);
  if (sc) { const b = box(sc); o.rx = x - b.x; o.ry = y - b.y; } else (o.at ||= {})[lane] = {x, y};
}
function sceneAt(id) {   // the smallest scene box on this board holding the card's top middle
  const b = box(id); if (!b || isScene(id)) return null;
  const px = b.x + b.w / 2, py = b.y + Math.min(b.h / 2, 40);
  return inTab(sessOf(id)).filter(isScene).map(x => [x, box(x)]).filter(([, r]) => r && px > r.x && px < r.x + r.w && py > r.y + 20 && py < r.y + r.h)
    .sort((a, c) => a[1].w * a[1].h - c[1].w * c[1].h).map(x => x[0])[0] || null;
}
function join(id, sid, rx, ry) { const o = it(id); o.scene = sid; o.rx = rx; o.ry = ry; o.at = {}; o.s = it(sid).s; }
function release(id, k) {   // out of its scene: it stays on its own boards, and on board k where it was taken out, where it stood
  const o = it(id), so = it(o.scene), hs0 = o.homes.length ? o.homes : [o.born || D.lanes[0].key];
  o.homes = [...new Set([...hs0, ...(k ? [k] : [])])]; o.at = {};
  if (so) { o.s = so.s; o.homes.forEach(ln => { const a = (so.at || {})[ln]; if (a) o.at[ln] = {x: a.x + (o.rx || 0), y: a.y + (o.ry || 0)}; }); }
  delete o.scene; delete o.rx; delete o.ry;
}
function capture(sid) {   // after a scene is moved or resized on this board: what it encloses is in it, what it leaves out is not
  const sb = box(sid);
  inTab(sessOf(sid)).filter(i => !isScene(i)).forEach(i => {
    const at = sceneAt(i);
    if (sceneOf(i) === sid && at !== sid) { const b = box(i), inside = b.x + b.w / 2 > sb.x && b.x + b.w / 2 < sb.x + sb.w && b.y + 20 > sb.y && b.y + 20 < sb.y + sb.h; if (!inside) release(i, lane); }
    else if (!sceneOf(i) && at === sid) { const b = box(i); join(i, sid, b.x - sb.x, b.y - sb.y); }
  });
}
function growScene(sid, w, h, except) {   // a scene got bigger: make room around it on every board it is on
  const o = it(sid), ow = o.w || SCW, oh = o.h || SCH; o.w = Math.max(ow, snap(w + 10)); o.h = Math.max(oh, snap(h + 10));
  makeRoom(sid, ow, oh, except);
}
function makeRoom(sid, ow, oh, except) {
  const o = it(sid), dw = o.w - ow, dh = o.h - oh; if (dw <= 0 && dh <= 0) return;
  lanesOf(sid).filter(k => k !== except && (o.at || {})[k]).forEach(k => {
    const a = o.at[k];
    inTab(o.s, k).filter(i => i !== sid && !sceneOf(i) && (it(i).at || {})[k]).forEach(i => {
      const b = box(i, k), p = it(i).at[k];
      if (dh > 0 && b.y >= a.y + oh - 1 && b.x < a.x + o.w && b.x + b.w > a.x) p.y += dh;
      else if (dw > 0 && b.x >= a.x + ow - 1 && b.y < a.y + o.h && b.y + b.h > a.y) p.x += dw;
    });
  });
}
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
function extras(o) {   // what a scene or clock adds to its card
  let h = "";
  if (o.kind === "scene") h += `<div class="at">${o.where ? `<b>At</b>${esc(o.where)}` : "<i>Where? Set it in its panel.</i>"}</div>` +
    (o.present && o.present.length ? `<div class="chips">${o.present.map(x => { const p = PCS.find(q => q.key === pcOf(x));
      return `<span class="ch who${p ? " pc" : ""}"${p ? ` style="--c:${esc(p.colour)}"` : ""}>${esc(x)}</span>`; }).join("")}</div>` : "");
  if (o.kind === "clock") { const [f, n] = parseClock(o.clock);
    h += `<div class="clk"><button class="rng" data-tick title="Fill a segment (Shift-click empties one)" aria-label="Clock: ${f} of ${n}">${ring(f, n, 44)}</button><span>${f} of ${n} filled</span></div>`; }
  return h;
}

/* ---------- session plan: every scene of a session, in running order ---------- */
const RUN = "@session", PCS = D.lanes.filter(l => l.kind === "pc");
let runMode = false, runTab = null;
const opened = new Set();
const lc = x => String(x || "").trim().toLowerCase();
function pcOf(name) {   // a player character's key, "party", or null
  const n = lc(name);
  if (n === "the party" || n === "the whole party") return "party";
  const p = PCS.find(q => lc(q.key) === n || (q.aliases || []).some(a => lc(a) === n));
  return p ? p.key : null;
}
function withLane(k, fn) { const keep = lane; lane = k; try { return fn(); } finally { lane = keep; } }
const shortOf = k => (D.lanes.find(l => l.key === k) || {}).short || k;
const boardName = k => k === "world" ? "Around the party" : shortOf(k) + "’s board";
const runSessions = () => doc.sessions.filter(t => t !== "Later");
const scenesIn = t => {
  const all = Object.keys(doc.items).filter(i => live(i) && isScene(i) && sessOf(i) === t), ord = (doc.order || {})[t] || [];
  return ord.filter(i => all.includes(i)).concat(all.filter(i => !ord.includes(i)));
};
const looseIn = t => Object.keys(doc.items).filter(i => live(i) && !isScene(i) && !sceneOf(i) && sessOf(i) === t);
function runOrder() { const o = {}; runSessions().forEach(t => { const s = scenesIn(t); if (s.length) o[t] = s; }); return o; }
function pills(id) {   // the boards a scene is on: filled, listed as present; outlined, on their board only
  const ks = lanesOf(id), cast = castLanes(id);
  return D.lanes.filter(l => ks.includes(l.key)).map(l => `<button class="pcx${cast.includes(l.key) ? " in" : ""}" style="--c:${esc(l.colour || "#b9ab95")}" data-go="${esc(l.key)}" data-id="${esc(id)}" ` +
    `title="${esc(cast.includes(l.key) || l.kind !== "pc" ? "" : "Not listed as present. ")}Open this scene on ${esc(boardName(l.key))}">${esc(l.short)}</button>`).join("");
}
function treeOf(sid) {   // a scene's cards under the cards that lead to them, by the arrows
  const pos = m => [it(m).ry || 0, it(m).rx || 0];
  const ms = membersOf(sid).sort((a, b) => pos(a)[0] - pos(b)[0] || pos(a)[1] - pos(b)[1]), inn = new Set(ms);
  const es = genEdges().filter(e => inn.has(e.to) && e.from !== e.to), par = {}, lab = {}, also = {}, kids = {};
  ms.forEach(m => {
    const cands = es.filter(e => e.to === m && inn.has(e.from)), own = cands.filter(e => e.own).reverse();   // Tom's latest arrow wins
    const pick = [...own, ...cands.filter(e => !e.own)].find(e => { for (let x = e.from; x; x = par[x]) if (x === m) return false; return true; });
    if (pick) { par[m] = pick.from; lab[m] = pick.label === "then" ? "" : pick.label; }
    else { const top = es.find(e => e.to === m && e.from === sid); if (top) lab[m] = top.label; }
    also[m] = cands.filter(e => e !== pick).map(e => e.from);
    (kids[par[m] || ""] ||= []).push(m);
  });
  return {ms, par, lab, also, kids, under: m => { const out = [m]; for (let i = 0; i < out.length; i++) out.push(...(kids[out[i]] || [])); return out; }};
}
function treeHtml(sid, tr, root) {
  const list = tr.kids[root] || []; if (!list.length) return "";
  return `<ul class="tree">` + list.map(m => {
    const k = kindOf(m) || "beat", o = objOf(m), [f, n] = parseClock(o.clock);
    return `<li><div class="tr${m.startsWith("p:") && cut[m.slice(2)] ? " cut" : ""}" data-card="${esc(m)}"><span class="rg" title="Drag to move it">⠿</span><span class="mk k-${esc(k)}">${esc(KINDS[k] || "Beat")}</span>` +
      `<span class="tt">${tr.lab[m] ? `<i class="el">${esc(tr.lab[m])}</i> ` : ""}${esc(titleOf(m))}</span>${k === "clock" ? `<span class="rng">${ring(f, n, 18)}</span>` : ""}` +
      (tr.also[m].length ? `<small>also after ${esc(tr.also[m].map(titleOf).join(", "))}</small>` : "") + `</div>${treeHtml(sid, tr, m)}</li>`;
  }).join("") + `</ul>`;
}
function runCard(id, i) {
  const o = objOf(id), mine = id.startsWith("c:"), op = opened.has(id), tr = treeOf(id), others = (o.present || []).filter(n => !pcOf(n)), text = (mine ? o.text : o.summary) || "";
  return `<div class="rc${!mine && cut[id.slice(2)] ? " cut" : ""}" data-uid="${esc(id)}">` +
    `<span class="rg" title="Drag to move it in the running order">⠿</span><span class="rn">${i + 1}</span>` +
    `<div class="rb"><div class="rt"><b>${esc(titleOf(id))}</b>${!mine && o.status === "ready" ? '<span class="ch ready">ready</span>' : ""}` +
    `${mine ? '<span class="ch ed">yours · not in vault</span>' : o.edited ? '<span class="ch ed">edited</span>' : ""}</div>` +
    `<div class="rw">${o.where ? "At " + esc(o.where) : "<i>Where not set</i>"}${others.length ? " · with " + others.map(esc).join(", ") : ""}</div>` +
    `<div class="pcs">${pills(id)}</div></div>` +
    `<button class="rx" aria-expanded="${op}" title="Show or hide what happens in this scene">${op ? "▾" : "▸"} ${tr.ms.length}</button>` +
    `<div class="rm"${op ? "" : " hidden"}>${text ? `<p>${esc(text)}</p>` : ""}` + (treeHtml(id, tr, "") || `<p class="muted">Nothing in this scene yet. Drag a card here.</p>`) +
    `<div class="acts"><button data-edit="${esc(id)}">Edit scene</button></div></div></div>`;
}
let runQ = "", runTray = false;
function drawRun() {
  const ts = runSessions(); if (!ts.includes(runTab)) runTab = ts[0];
  const t = runTab, scenes = scenesIn(t), all = scenes.length && scenes.every(x => opened.has(x)), top = $("#run").scrollTop;
  $("#rsess").innerHTML = ts.map(x => `<button role="tab" data-rtab="${esc(x)}" aria-selected="${x === t}">${esc(x)}${sessNum(x) === CUR + 1 ? " · next" : ""}<small>${scenesIn(x).length}</small></button>`).join("");
  $$("#rsess [data-rtab]").forEach(b => b.onclick = () => { runTab = b.dataset.rtab; closeDrawer(); drawRun(); $("#run").scrollTop = 0; });
  $("#run").innerHTML = `<div class="runh"><span><b>Running order · ${esc(t)}</b> &nbsp;${scenes.length} scene${scenes.length === 1 ? "" : "s"}</span>` +
    (scenes.length ? `<button class="mini" data-allx>${all ? "Collapse all" : "Expand all"}</button>` : "") + `</div>` +
    (scenes.length ? scenes.map(runCard).join("") : `<p class="empty">No scenes in ${esc(t)} yet. Add one on a character's board (+ Scene), or drag a scene in from the plans on the right.</p>`);
  $("#run").scrollTop = top;
  drawLoose(t);
  $$("#run [data-go]").forEach(b => b.onclick = ev => { ev.stopPropagation(); goto(b.dataset.go, t, b.dataset.id); });
  $$("#run [data-edit]").forEach(b => b.onclick = ev => { ev.stopPropagation(); openHere(b.dataset.edit); });
  $$("#run .rx").forEach(b => b.onclick = ev => { ev.stopPropagation(); toggleRun(b.closest(".rc").dataset.uid); });
  const ax = $("#run [data-allx]"); if (ax) ax.onclick = () => { scenes.forEach(x => all ? opened.delete(x) : opened.add(x)); drawRun(); };
  $$("#run .rc").forEach(el => runDrag(el, t));
  $$("#run .tr").forEach(el => cardDrag(el, el.dataset.card));
  if (shown) $$(`[data-card]`).forEach(x => x.classList.toggle("on", x.dataset.card === shown));
}
function drawLoose(t) {
  const loose = looseIn(t), by = {}; loose.forEach(i => (by[lanesOf(i)[0]] ||= []).push(i));
  const row = (id, sub) => `<div class="li k-${esc(kindOf(id) || "beat")}" data-card="${esc(id)}"><span class="rg" title="Drag it into a scene">⠿</span><div><span class="mk k-${esc(kindOf(id) || "beat")}">${esc(KINDS[kindOf(id)] || "Beat")}</span> ${esc(titleOf(id))}${sub ? `<small>${esc(sub)}</small>` : ""}</div></div>`;
  const q = lc(runQ), free = Object.values(P).filter(p => !it("p:" + p.id) && !(doc.edits[p.id] || {}).drop && (!q || lc(p.id + " " + p.summary).includes(q))).sort((a, b) => a.id.localeCompare(b.id));
  $("#loose").innerHTML = `<div class="tlist loose"><div class="trayh"><b>Not in a scene</b></div><p class="muted">Cards in ${esc(t)} outside every scene. Drag one into a scene.</p>` +
    (loose.length ? D.lanes.filter(l => by[l.key]).map(l => `<h4>${l.kind === "pc" ? `<span class="pcx in" style="--c:${esc(l.colour)}">${esc(l.short)}</span>` : esc(l.short)}</h4>` + by[l.key].map(i => row(i)).join("")).join("")
      : `<p class="empty">Every card in ${esc(t)} sits in a scene.</p>`) +
    `<details class="free"${runTray || q ? " open" : ""}><summary><b>Plans not placed</b> <small>${free.length}</small></summary><input type="search" id="run-q" placeholder="Find a plan" autocomplete="off" value="${esc(runQ)}">` +
    (free.map(p => row("p:" + p.id, p.lanes.map(shortOf).join(", "))).join("") || `<p class="empty">No unplaced plans${q ? " match" : ""}.</p>`) + `</details></div>`;
  $("#loose details").ontoggle = e => { runTray = e.target.open; };
  $("#run-q").oninput = e => { runQ = e.target.value; runTray = true; const at = e.target.selectionStart; drawLoose(t); const n = $("#run-q"); n.focus(); n.setSelectionRange(at, at); };
  $$("#loose [data-card]").forEach(el => cardDrag(el, el.dataset.card));
}
function toggleRun(u) {
  const on = !opened.has(u); if (on) opened.add(u); else opened.delete(u);
  const el = $$("#run .rc").find(x => x.dataset.uid === u); if (el) expand(el, on);
}
function expand(el, on) {
  el.querySelector(".rm").hidden = !on; const x = el.querySelector(".rx"); x.setAttribute("aria-expanded", on); x.textContent = (on ? "▾ " : "▸ ") + x.textContent.slice(2);
}
function openHere(id) {   // its panel, without leaving the session plan
  const ks = it(id) ? lanesOf(id) : P[id.slice(2)].lanes; if (!ks.includes(lane)) lane = ks[0] || D.lanes[0].key;
  open(id); $$("[data-card]").forEach(x => x.classList.toggle("on", x.dataset.card === id));
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
      $$("#run .rc .rn").forEach((n, i) => { n.textContent = i + 1; });
      edgeScroll(e);
    }, (e, off) => {
      el.classList.remove("drag"); $$("#rsess button").forEach(x => x.classList.remove("drop"));
      if (!moved) return;
      dragEnd = Date.now(); const tb = rtabUnder(e);
      if (off) { drawRun(); return; }
      if (tb && tb.dataset.rtab !== t) { moveTo(el.dataset.uid, tb.dataset.rtab); return; }
      doc.order[t] = $$("#run .rc").map(x => x.dataset.uid); changed(); drawRun();
    });
  });
}
function cardDrag(el, id) {   // a card: into a scene, under or beside another card, back out, or onto another session's tab
  el.addEventListener("click", () => { if (Date.now() - dragEnd > 300) openHere(id); });
  el.addEventListener("pointerdown", ev => {
    if (ev.button > 0 || (!ev.target.closest(".rg") && ev.pointerType !== "mouse")) return;
    ev.preventDefault(); ev.stopPropagation();
    const st = {x: ev.clientX, y: ev.clientY}, from = it(id) ? sceneOf(id) : null, mine = from ? treeOf(from).under(id) : [id], scene = isScene(id);
    let ghost = null, spot = null, timer = null, over = null;
    const clear = () => { $$(".in-on,.in-before,.in-after,.rc.hot,#loose.over").forEach(x => x.classList.remove("in-on", "in-before", "in-after", "hot", "over")); $$("#rsess button").forEach(x => x.classList.remove("drop")); };
    watch(e => {
      if (!ghost) {
        if (Math.hypot(e.clientX - st.x, e.clientY - st.y) < 5) return;
        ghost = document.createElement("div"); ghost.className = `bn ghost k-${kindOf(id) || "beat"}`;
        ghost.innerHTML = `<div class="t">${esc(titleOf(id))}${mine.length > 1 ? ` <small>+ ${mine.length - 1} under it</small>` : ""}</div><div class="s"></div>`; document.body.append(ghost);
      }
      ghost.style.left = e.clientX + 12 + "px"; ghost.style.top = e.clientY + 10 + "px";
      clear(); spot = null; let say = "";
      const tb = rtabUnder(e), hit = document.elementFromPoint(e.clientX, e.clientY), row = hit && hit.closest("#run .tr"), rc = hit && hit.closest("#run .rc");
      if (tb) { if (tb.dataset.rtab !== runTab) { tb.classList.add("drop"); spot = {tab: tb.dataset.rtab}; say = `move to ${tb.dataset.rtab}`; } }
      else if (hit && hit.closest("#loose")) { if (it(id) && from) { $("#loose").classList.add("over"); spot = {out: 1}; say = "take it out of its scene"; } }
      else if (scene) { if (hit && hit.closest("#run")) { spot = {scene: 1, before: rc ? rc.dataset.uid : null}; if (rc) rc.classList.add("in-before"); say = `a scene in ${runTab}`; } }
      else if (row && !mine.includes(row.dataset.card)) {
        const to = row.dataset.card, r = row.getBoundingClientRect(), f = (e.clientY - r.top) / r.height, sid = rc.dataset.uid, tr = treeOf(sid), up = tr.par[to];
        if (f < .28) { spot = {sid, parent: up, before: to}; row.classList.add("in-before"); }
        else if (f > .72) { spot = {sid, parent: up, after: to}; row.classList.add("in-after"); }
        else { spot = {sid, parent: to}; row.classList.add("in-on"); }
        say = spot.parent ? `follows “${titleOf(spot.parent)}”` : "starts in this scene";
      } else if (rc && !row) { spot = {sid: rc.dataset.uid}; rc.classList.add("hot"); say = `in “${titleOf(rc.dataset.uid)}”`; }
      ghost.querySelector(".s").textContent = say;
      if (rc !== over) { clearTimeout(timer); over = rc; if (rc && !opened.has(rc.dataset.uid)) timer = setTimeout(() => { opened.add(rc.dataset.uid); expand(rc, true); }, 550); }
      edgeScroll(e);
    }, (e, off) => {
      clearTimeout(timer); clear(); if (!ghost) return;
      ghost.remove(); dragEnd = Date.now();
      if (off || !spot) return;
      if (spot.tab) { if (it(id)) moveTo(id, spot.tab); else { putPlan(id, spot.tab); changed(); drawRun(); } }
      else if (spot.out) { mine.forEach(m => release(m)); changed(); drawRun(); }
      else if (spot.scene) {
        putPlan(id, runTab); const ord = scenesIn(runTab).filter(x => x !== id), i = spot.before ? ord.indexOf(spot.before) : -1;
        ord.splice(i < 0 ? ord.length : i, 0, id); doc.order[runTab] = ord; changed(); drawRun();
      } else dropInto(id, spot, mine);
    });
  });
}
function putPlan(id, t) {   // an unplaced plan joins session t, on the boards it is tied to
  const p = P[id.slice(2)], homes = p.lanes.length ? [...p.lanes] : [D.lanes[0].key];
  doc.items[id] = {s: t, homes, born: homes[0], at: {}, ...(isScene(id) ? {w: SCW, h: SCH} : {})};
}
function dropInto(id, spot, block) {   // put a card (and what follows it) into a scene, joined and placed the way it was dropped
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
    const i = doc.edges.findIndex(e => e.from === spot.parent && e.to === id);
    if (i >= 0) doc.edges.push(doc.edges.splice(i, 1)[0]);   // the latest arrow is the one the list follows
    else addEdge(spot.parent, id);
  }
  /* place */
  const others = tr.ms.filter(m => !inBlock.has(m)), bottom = ms => Math.max(...ms.map(m => it(m).ry + H(m)));
  const branch = m => tr.under(m).filter(x => !inBlock.has(x)), kids = p => (tr.kids[p] || []).filter(x => !inBlock.has(x));
  let x, y;
  if (spot.before) { x = it(spot.before).rx; y = it(spot.before).ry; }
  else if (spot.after) { x = it(spot.after).rx; y = bottom(branch(spot.after)) + 22; }
  else if (spot.parent) { const ks = kids(spot.parent); x = ks.length ? it(ks[0]).rx : it(spot.parent).rx + CARDW + 80; y = ks.length ? bottom(ks.flatMap(branch)) + 22 : it(spot.parent).ry; }
  else { const top = kids(""); x = top.length ? Math.min(...top.map(m => it(m).rx)) : 22; y = others.length ? bottom(others) + 22 : (hsh[sid] || 96) + 22; }
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
  const ms = membersOf(sid), needW = Math.max(...ms.map(m => it(m).rx + CARDW)) + 22, needH = bottom(ms) + 22;
  if (needW > (o.w || SCW) || needH > (o.h || SCH)) growScene(sid, needW, needH);
  opened.add(sid);
  const want = spot.parent || "", got = treeOf(sid).par[id] || "";
  changed(); drawRun();
  if (want !== got && got) toast(`The vault already says “${titleOf(id)}” follows “${titleOf(got)}”, so it stays under it. Ask Claude to change that in the plan.`);
}
function toast(t) { const d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.append(d); setTimeout(() => d.remove(), 6500); }
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

/* ---------- what-ifs (the same rules as build.py) ---------- */
const ov = {out: {}, dead: {}, drop: {}};
let cut = {};
const isOut = a => a in ov.out ? ov.out[a] : !!(F[a] && F[a].out);
const isDead = a => a in ov.dead ? ov.dead[a] : !!(F[a] && GONE.has(F[a].state));
function test(r) {
  switch (r.k) {
    case "alive": return !isDead(r.a);
    case "dead": return isDead(r.a);
    case "state": return ov.dead[r.a] ? r.w.some(w => GONE.has(w)) : true;
    case "hidden": return !isOut(r.a);
    case "revealed": return isOut(r.a);
    case "plan": case "played": return !(ov.drop[r.a] || cut[r.a]);
    default: return true;   // checks and fixed facts hold now, or the build would have pruned the plan
  }
}
const why = r => ({alive: `needs ${r.a} alive`, dead: `needs ${r.a} dead`, state: `needs ${r.a} ${r.w.join(" or ")}`,
  hidden: `needs ${r.a} hidden`, revealed: `needs ${r.a} out`, plan: `needs ${r.a}`, played: `needs ${r.a} played`}[r.k] || r.t);
const fall = a => ({faction: ["it falls", "falls"], item: ["it is destroyed", "is destroyed"]})[F[a] && F[a].type] || ["they die", "dies"];
function recut() {
  cut = {};
  for (const id in ov.drop) if (ov.drop[id]) cut[id] = "set aside";
  for (let ch = true; ch;) { ch = false;
    for (const id in P) { if (cut[id]) continue; const bad = P[id].req.find(r => !test(r)); if (bad) { cut[id] = why(bad); ch = true; } } }
  const items = [...Object.keys(ov.out).map(a => [`${a} ${ov.out[a] ? "comes out" : "stays hidden"}`, () => delete ov.out[a]]),
    ...Object.keys(ov.dead).map(a => [`${a} ${ov.dead[a] ? fall(a)[1] : "lives"}`, () => delete ov.dead[a]]),
    ...Object.keys(ov.drop).map(a => [`set aside: ${a}`, () => delete ov.drop[a]])];
  const box = $("#wi-list"); box.innerHTML = "";
  if (!items.length) box.textContent = "none. Tap a secret chip on a card to try one.";
  items.forEach(([t, undo]) => { const s = document.createElement("span"); s.className = "wi";
    s.innerHTML = `${esc(t)} <button aria-label="Undo">×</button>`; s.querySelector("button").onclick = () => { undo(); refresh(); }; box.append(s); });
  $("#wi-reset").hidden = !items.length;
}
function flip(r) {
  const a = r.a;
  if (r.k === "hidden" || r.k === "revealed") { const v = !isOut(a); if (v === !!(F[a] && F[a].out)) delete ov.out[a]; else ov.out[a] = v; }
  else if (r.k === "plan" || r.k === "played") { if (ov.drop[a]) delete ov.drop[a]; else ov.drop[a] = true; }
  else { const v = !isDead(a); if (v === !!(F[a] && GONE.has(F[a].state))) delete ov.dead[a]; else ov.dead[a] = v; }
  refresh();
}

/* ---------- drawing ---------- */
const secReq = p => p.req.filter(r => (r.k === "hidden" || r.k === "revealed") && F[r.a]);
function planCard(id) {
  const p = view_of(id), o = it("p:" + id), at = o && sessOf("p:" + id);
  const mv = p.target && o && at.toUpperCase() !== p.target.toUpperCase() ? `vault says ${p.target}` : "";
  const checks = p.req.filter(r => r.k === "check").length;
  return `<div class="k"><span>${esc(KINDS[p.kind] || "Beat")}</span><span>${p.edited ? "edited · not in vault" : esc(p.status)}</span></div><div class="t">${esc(p.id)}</div>` +
    extras(p) + `<div class="s">${esc(p.summary)}</div>` +
    (p.kind === "decision" ? (p.options.length ? `<ul class="opts">${p.options.map(o => `<li>${esc(o.label || o.to)}</li>`).join("")}</ul>` : `<div class="s"><i>Options not written yet.</i></div>`) : "") +
    `<div class="chips">${p.status === "ready" ? '<span class="ch ready">ready</span>' : ""}${mv ? `<span class="ch move">${esc(mv)}</span>` : ""}` +
    secReq(p).map(r => `<span class="ch sec ${isOut(r.a) ? "out" : ""}" data-sec="${esc(r.a)}" data-need="${r.k}" title="Tap: what if this comes out?">${isOut(r.a) ? "out" : "secret"}: ${esc(r.a)}</span>`).join("") +
    (checks ? `<span class="ch ck">${checks} check${checks > 1 ? "s" : ""}</span>` : "") +
    (p.via[lane] ? `<span class="ch">through ${esc(p.via[lane])}</span>` : "") + `</div><div class="why">${esc(cut[p.id] ? "closes: " + cut[p.id] : "")}</div>`;
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
    (n.class ? `<div class="s">${esc(n.class)}</div>` : "") + (n.summary ? `<div class="s">${esc(n.summary)}</div>` : "") +
    (rows.length ? `<dl>${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("")}</dl>` : "") +
    (n.recent && n.recent.length ? `<div class="k"><span>${head}</span></div><ul>${n.recent.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : "");
}
function titleOf(id) { if (id.startsWith("p:")) return id.slice(2); const c = doc.cards[id.slice(2)]; return c ? (c.title || "untitled card") : id; }
function startCard(tab, idx) {
  const ln = D.lanes.find(x => x.key === lane);
  if (idx === 0) return nowCard(ln.now, ln.kind);
  const prev = doc.sessions[idx - 1], items = inTab(prev);
  const later = tab === "Later";
  return `<div class="k"><span>${later ? "Later · no session yet" : `End of ${esc(prev)} · as planned`}</span></div>` +
    `<div class="t">${later ? "Whenever it fits" : `After ${esc(prev)}`}</div>` +
    (later ? `<div class="s">Ideas without a session. Place a card here, then move it to a session when it is time.</div>` :
      items.length ? `<div class="k"><span>Planned for ${esc(prev)}</span></div><ul>${items.map(i => `<li>${isScene(i) ? "Scene: " : ""}${esc(titleOf(i))}</li>`).join("")}</ul>`
        : `<div class="s">Nothing planned for ${esc(prev)} yet.</div>`);
}
function draw() {
  if (runMode) { drawRun(); return; }
  const tab = T(), idx = doc.sessions.indexOf(tab);
  ensureAt(tab);
  const ids = inTab(tab).sort((a, b) => isScene(b) - isScene(a));   // scenes underneath
  $("#nodes").innerHTML = `<div class="bn now ${idx ? "start" : ""}" data-id="start" style="left:${SX}px;top:${SY}px">${startCard(tab, idx)}</div>` + ids.map(cardHtml).join("");
  $$("#nodes .bn").forEach(el => { hs[el.dataset.id] = el.offsetHeight; const h = el.querySelector(".sh"); if (h) hsh[el.dataset.id] = h.offsetHeight; });
  sessTabs(); wires(); bindNodes(); tray(); applyView();
}
function cardHtml(id) {
  const b = box(id) || {x: 0, y: 0, w: (it(id) || {}).w || SCW, h: (it(id) || {}).h || SCH}, sc = isScene(id), mine = id.startsWith("c:");
  let inner, cls;
  if (mine) {
    const c = doc.cards[id.slice(2)];
    inner = `<div class="k"><span>${esc(KINDS[c.kind] || "Note")}</span><span>yours · not in vault</span></div><div class="t">${esc(c.title || "Untitled")}</div>` + extras(c) +
      (c.text ? `<div class="s">${esc(c.text.length > 220 ? c.text.slice(0, 220) + "…" : c.text)}</div>` : "");
    cls = `mine k-${c.kind}`;
  } else {
    const pid = id.slice(2), p = view_of(pid);
    inner = planCard(pid); cls = `k-${p.kind}${p.edited ? " edited" : ""}${cut[pid] ? " cut" : ""}`;
  }
  const several = it(id) && !sceneOf(id) && lanesOf(id).length > 1;
  const xt = several ? "Take it off this board" : mine ? "Delete this card" : "Back to the tray";
  return `<div class="bn ${esc(cls)}${sc ? " scene" : ""}" data-id="${esc(id)}" style="left:${b.x}px;top:${b.y}px${sc ? `;width:${b.w}px;height:${b.h}px` : ""}">` +
    (sc ? `<div class="sh">${inner}</div><span class="rz" title="Drag to resize the scene"></span>` : inner) +
    `<button class="xx" title="${xt}" aria-label="${xt}">×</button><span class="hd" title="Drag to another card to link them"></span></div>`;
}
function sessTabs() {
  const tab = T();
  $("#sess").innerHTML = doc.sessions.map((t, i) => `<button role="tab" data-tab="${esc(t)}" aria-selected="${t === tab}">${esc(t)}${i === 0 && t !== "Later" ? " · next" : ""}<small>${inTab(t).length}</small>` +
    (t === tab && t !== "Later" && doc.sessions.length > 2 ? `<span class="dx" data-delsess title="Delete this session" aria-label="Delete ${esc(t)}">×</span>` : "") + `</button>`).join("") +
    `<button class="add" data-addsess title="Add the session after the last one, on every board">+ Session</button>`;
  $$("#sess [data-tab]").forEach(b => b.onclick = ev => { if (ev.target.closest("[data-delsess]")) delSession(b.dataset.tab); else openTab(b.dataset.tab); });
  $("#sess [data-addsess]").onclick = () => {
    const n = "S" + (Math.max(CUR, ...doc.sessions.map(sessNum)) + 1);
    doc.sessions.push(n); sortSessions(); changed(); openTab(n);
  };
}
function delSession(t) {   // on every board
  const n = sessNum(t), ids = Object.keys(doc.items).filter(i => sessOf(i) === t);
  const plans = ids.filter(i => i.startsWith("p:") && live(i)), cards = ids.filter(i => i.startsWith("c:"));
  const what = [plans.length ? `its ${plans.length} plan${plans.length > 1 ? "s go" : " goes"} back to the tray` : "", cards.length ? `your ${cards.length} card${cards.length > 1 ? "s move" : " moves"} to Later` : ""].filter(Boolean).join(" and ");
  const later = doc.sessions.filter(x => sessNum(x) > n);
  if (!confirm(`Delete ${t} on every board?` + (what ? ` ${what[0].toUpperCase() + what.slice(1)}.` : "") + (later.length ? ` ${later.join(", ")} move up one.` : ""))) return;
  plans.forEach(erase);
  Object.values(doc.items).forEach(o => { if (o.s === t) { o.s = "Later"; o.at = {}; } });
  Object.values(doc.items).forEach(o => { const so = o.scene && it(o.scene); if (so) o.s = so.s; });
  doc.edges = doc.edges.filter(e => e.from !== "start:" + t);
  const down = x => sessNum(x) > n ? "S" + (sessNum(x) - 1) : x;
  doc.sessions = doc.sessions.filter(x => x !== t).map(down);
  Object.values(doc.items).forEach(o => { o.s = down(o.s); });
  doc.edges.forEach(e => { if (e.from.startsWith("start:")) e.from = "start:" + down(e.from.slice(6)); });
  const ord = {}; for (const k in doc.order) if (k !== t) ord[down(k)] = doc.order[k]; doc.order = ord;
  views = {}; tabOf[lane] = later.length ? t : doc.sessions[Math.max(0, doc.sessions.length - 2)];
  changed(); closeDrawer(); draw(); fit();
}
function erase(id) {   // off every board; what it held stays, on its home boards
  if (isScene(id)) membersOf(id).forEach(m => release(m));
  delete doc.items[id]; doc.edges = doc.edges.filter(e => e.from !== id && e.to !== id);
  if (id.startsWith("c:")) delete doc.cards[id.slice(2)];
}
function unplace(pid) { erase("p:" + pid); changed(); closeDrawer(); draw(); }
const names = ks => ks.map(boardName).join(", ").replace(/, ([^,]*)$/, " and $1");
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
  if (ks.length > 1) {
    const rest = ks.filter(x => x !== k);
    if (isScene(id)) {
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
function openTab(t) {
  views[lane + "|" + T()] = {...view}; tabOf[lane] = t; closeDrawer(); draw();
  const v = views[lane + "|" + t]; if (v) { view = {...v}; applyView(); } else fit();
}
function genEdges() {   // every link between placed items: the vault's, then Tom's own
  const out = [];
  for (const id of Object.keys(doc.items)) {
    if (!id.startsWith("p:") || !live(id)) continue;
    const p = view_of(id.slice(2));
    p.req.forEach(r => { if ((r.k === "plan" || r.k === "played") && live("p:" + r.a)) out.push({from: "p:" + r.a, to: id, label: "then"}); });
    if (p.kind === "decision") p.options.forEach(o => { if (live("p:" + o.to)) out.push({from: id, to: "p:" + o.to, label: o.label, opt: 1}); });
  }
  const best = new Map();   // a decision's option line beats the bare "needs" between the same two
  out.forEach(e => { const k = e.from + ">" + e.to; if (!best.has(k) || e.opt) best.set(k, e); });
  return [...best.values()].concat(doc.edges.filter(e => !best.has(e.from + ">" + e.to)).map(e => ({...e, own: 1})));
}
function curve(a, b, inside) {
  if (inside) {   // a scene to a card inside it: down from the header
    const x1 = a.x + 20, y1 = a.y + a.hh, x2 = b.x, y2 = b.y + Math.min(b.h / 2, 56);
    return {d: `M${x1},${y1} C${x1},${y2} ${x1},${y2} ${x2},${y2}`, mx: (x1 + x2) / 2, my: y2 - 12};
  }
  const x1 = a.x + a.w, y1 = a.y + Math.min(a.h / 2, 56), x2 = b.x, y2 = b.y + Math.min(b.h / 2, 56);
  const dx = x2 < x1 + 20 ? 90 : Math.max(50, (x2 - x1) / 2);
  return {d: `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`, mx: (x1 + x2) / 2, my: (y1 + y2) / 2};
}
function wires(temp) {
  const tab = T(), ti = doc.sessions.indexOf(tab), order = x => doc.sessions.indexOf(x), here = id => live(id) && lanesOf(id).includes(lane);
  let svg = '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="rgba(124,22,34,.75)"/></marker></defs>', labels = "";
  const carried = new Set();
  genEdges().forEach(e => {
    if (e.from.startsWith("start")) { if (e.lane && e.lane !== lane) return; e = {...e, from: "start"}; }
    if (!here(e.to) || (e.from !== "start" && !here(e.from))) return;
    const fs = e.from === "start" ? tab : sessOf(e.from), ts = sessOf(e.to);
    if (ts !== tab) return;
    let from = e.from, lab = e.label, cls = e.own ? "own" : e.opt ? "opt" : "";
    if (fs !== tab) {   // from an earlier session: it comes in through this tab's start card
      if (order(fs) > ti || carried.has(e.to)) return;
      carried.add(e.to); from = "start"; lab = `after ${titleOf(e.from)} (${fs})`; cls = "carry";
    }
    const a = box(from), b = box(e.to); if (!a || !b) return;
    const c = curve(a, b, a.sc && sceneOf(e.to) === from);
    svg += `<path class="${cls}" d="${c.d}" marker-end="url(#ar)"/>`;
    if (e.own && from === e.from) svg += `<path class="hit" data-edge="${esc(e.id)}" d="${c.d}"/>`;
    if (lab || e.own) labels += `<div class="wl ${e.own && from === e.from ? "own" : ""}" ${e.own && from === e.from ? `data-edge="${esc(e.id)}"` : ""} style="left:${c.mx}px;top:${c.my}px">${esc(lab || "add a label")}</div>`;
  });
  if (temp) svg += `<path class="temp" d="${temp}"/>`;
  $("#wires").innerHTML = svg;
  $$("#nodes .wl").forEach(x => x.remove());
  $("#nodes").insertAdjacentHTML("beforeend", labels);
  $$("[data-edge]").forEach(x => { x.onpointerdown = ev => ev.stopPropagation(); x.onclick = ev => { ev.stopPropagation(); edgeEditor(x.dataset.edge); }; });
}

/* ---------- tray ---------- */
function tray() {
  const all = $("#tray-all").checked, q = $("#tray-q").value.trim().toLowerCase();
  const list = Object.values(P).filter(p => { const id = "p:" + p.id, o = it(id);
    return !(o && lanesOf(id).includes(lane)) && !(doc.edits[p.id] || {}).drop && (all || (!(o && sceneOf(id)) && p.lanes.includes(lane))) &&
      (!q || (p.id + " " + p.summary).toLowerCase().includes(q)); });
  const elsewhere = p => { const id = "p:" + p.id, sc = it(id) && sceneOf(id); return !it(id) ? "" : `<span class="ch move">${esc(sc ? `in “${titleOf(sc)}”` : `on ${names(lanesOf(id))}`)} · ${esc(sessOf(id))}</span>`; };
  let h = "";
  PLANKINDS.forEach(k => {
    const ps = list.filter(p => (view_of(p.id).kind || "beat") === k).sort((a, b) => (a.status !== "ready") - (b.status !== "ready") || a.id.localeCompare(b.id));
    if (!ps.length) return;
    h += `<h4>${KINDS[k]}s</h4>` + ps.map(p => `<div class="ti k-${esc(k)} ${cut[p.id] ? "cut" : ""}" data-plan="${esc(p.id)}"><span class="g" title="Drag onto the board or a session tab">⠿</span><div>` +
      `<div class="t">${esc(p.id)}</div><div class="s">${esc(view_of(p.id).summary)}</div><div class="chips">${p.status === "ready" ? '<span class="ch ready">ready</span>' : ""}${p.target ? `<span class="ch">${esc(p.target)}</span>` : ""}${elsewhere(p)}` +
      secReq(p).map(r => `<span class="ch">secret: ${esc(r.a)}</span>`).join("") + `</div></div></div>`).join("");
  });
  if (!h) h = `<p class="empty">${Object.keys(doc.items).some(i => live(i) && lanesOf(i).includes(lane)) ? "Every plan for this board is placed." : "No live plans for this board yet."} ${all ? "" : "Tick “every live plan” to pull one from another board, or add a card."}</p>`;
  const s = doc, gone = Object.keys(s.edits).filter(id => s.edits[id].drop && P[id]);
  if (gone.length) h += `<h4>Dropped here</h4>` + gone.map(id => `<div class="gone"><s>${esc(id)}</s><button class="mini" data-undrop="${esc(id)}">Undo</button></div>`).join("") +
    `<p class="empty" style="font-size:13px">Claude marks these dropped in the vault when you bring the board in.</p>`;
  $("#tray-list").innerHTML = h;
  $$("#tray-list [data-undrop]").forEach(b => b.onclick = () => { const e = s.edits[b.dataset.undrop]; delete e.drop; if (!Object.keys(e).length) delete s.edits[b.dataset.undrop]; changed(); tray(); });
  $$("#tray-list .ti").forEach(trayDrag);
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
  const r = board.getBoundingClientRect(); k = Math.min(2, Math.max(.25, k));
  const px = cx - r.left, py = cy - r.top;
  view.x = px - (px - view.x) * k / view.k; view.y = py - (py - view.y) * k / view.k; view.k = k; applyView();
}
function fit() {
  const r = board.getBoundingClientRect(), bs = ["start", ...$$("#nodes .bn").map(e => e.dataset.id)].map(i => box(i)).filter(Boolean);
  const x0 = Math.min(...bs.map(b => b.x)) - 30, y0 = Math.min(...bs.map(b => b.y)) - 30;
  const x1 = Math.max(...bs.map(b => b.x + b.w)) + 40, y1 = Math.max(...bs.map(b => b.y + b.h)) + 40;
  const k = Math.min(1, Math.max(.3, Math.min((r.width - 20) / (x1 - x0), (r.height - 20) / (y1 - y0))));
  view = {k, x: 10 - x0 * k, y: 10 - y0 * k}; applyView();
}
let pan = null;
board.addEventListener("pointerdown", e => {
  if (e.target.closest(".bn,.wl,.float,.keyp")) return;
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
board.addEventListener("dblclick", e => { if (!e.target.closest(".bn,.wl,.float,.keyp")) { const w = toWorld(e.clientX, e.clientY); newCard(w.x - CARDW / 2, w.y - 30); } });

/* ---------- cards: drag, link, open ---------- */
const inRect = (e, el) => { const r = el.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom; };
const tabUnder = e => $$("#sess [data-tab]").find(b => inRect(e, b));
function bindNodes() {
  $$("#nodes .bn").forEach(el => {
    const id = el.dataset.id;
    el.querySelectorAll(".ch.sec").forEach(c => { c.onpointerdown = ev => ev.stopPropagation(); c.onclick = ev => { ev.stopPropagation(); flip({k: c.dataset.need, a: c.dataset.sec}); }; });
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
    const rz = el.querySelector(".rz"); if (rz) rz.addEventListener("pointerdown", ev => resize(ev, el, id));
    el.addEventListener("pointerdown", ev => {
      if (ev.target.closest(".hd,.xx,.rz,.rng,.ch.sec,a")) return;
      ev.stopPropagation();
      const b = box(id), st = {x: ev.clientX, y: ev.clientY}, sc = isScene(id); let moved = false, nx = b.x, ny = b.y;
      const els = $$("#nodes .bn"), mem = sc ? membersOf(id).map(m => [m, els.find(x => x.dataset.id === m)]) : [];
      cap(el, ev.pointerId);
      const mv = e => {
        const dx = (e.clientX - st.x) / view.k, dy = (e.clientY - st.y) / view.k;
        if (!moved && Math.hypot(dx, dy) < 5) return;
        moved = true; el.classList.add("drag");
        nx = Math.round(b.x + dx); ny = Math.round(b.y + dy); setPos(id, nx, ny);
        el.style.left = nx + "px"; el.style.top = ny + "px";
        mem.forEach(([m, me]) => { if (me) { const mb = box(m); me.style.left = mb.x + "px"; me.style.top = mb.y + "px"; } });
        if (!sc) { const hot = sceneAt(id); els.forEach(x => x.classList.toggle("hot", x.dataset.id === hot)); }
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
        nx = snap(nx); ny = snap(ny); setPos(id, nx, ny);
        if (sc) capture(id); else settle(id, nx, ny);
        changed(); draw();
      };
      el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    });
  });
}
function settle(id, x, y) {   // a card let go at x, y on this board: into the scene it is in, or out of the one it left
  const to = sceneAt(id), was = sceneOf(id);
  if (to === was) return;
  if (to) { const sb = box(to); join(id, to, x - sb.x, y - sb.y); }
  else { release(id, lane); it(id).at[lane] = {x, y}; }
}
function insideSpot(sid) {   // the next free place inside a scene; the scene grows to fit
  const ms = membersOf(sid), o = it(sid);
  const y = ms.length ? Math.max(...ms.map(m => it(m).ry + (hs[m] || 110))) + 22 : snap((hsh[sid] || 96) + 22);
  if (y + 170 > (o.h || SCH)) growScene(sid, o.w || SCW, y + 170);
  return {rx: 22, ry: snap(y)};
}
function moveTo(id, t) {   // to another session, on every board it is on; a scene takes its cards along
  if (sceneOf(id)) release(id, runMode ? undefined : lane);
  const o = it(id); o.s = t; o.at = {}; if (isScene(id)) membersOf(id).forEach(m => { it(m).s = t; });
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
    const hit = document.elementsFromPoint(e.clientX, e.clientY).map(x => x.closest && x.closest(".bn")).find(Boolean);
    const to = hit && hit.dataset.id;
    if (!to || to === from || to === "start") { wires(); return; }
    const id = addEdge(from === "start" ? "start:" + T() : from, to); changed(); wires(); edgeEditor(id);
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
  if (o && sceneOf(id)) release(id, lane);
  if (!o) o = doc.items[id] = {s: t, homes: [], born: lane, at: {}};
  if (!o.homes.includes(lane)) o.homes.push(lane);
  if (o.s !== t) { o.s = t; o.at = {}; }
  if (isScene(id)) { o.w ||= SCW; o.h ||= SCH; }
  if (x !== undefined) { o.at[lane] = {x: snap(x), y: snap(y)}; if (isScene(id)) capture(id); else settle(id, snap(x), snap(y)); }
  else if (sc && live(sc) && sessOf(sc) === t && !isScene(id)) { const f = insideSpot(sc); join(id, sc, f.rx, f.ry); }   // the vault's scene, when it is here
  else if (!runMode) o.at[lane] = freeSpot(t);
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
      e.preventDefault(); ghost.style.left = e.clientX - 30 + "px"; ghost.style.top = e.clientY - 16 + "px";
      const tb = tabUnder(e); $$("#sess button").forEach(x => x.classList.toggle("drop", x === tb));
    };
    const up = e => {
      done(); $$("#sess button").forEach(x => x.classList.remove("drop"));
      if (gave) return;
      if (!ghost) { open("p:" + pid); return; }
      ghost.remove();
      const tb = tabUnder(e);
      if (tb) { place(pid, tb.dataset.tab); return; }
      if (inRect(e, board)) { const w = toWorld(e.clientX, e.clientY); place(pid, T(), w.x - 30, w.y - 16); }
    };
    const cancel = () => { done(); if (ghost) ghost.remove(); };
    const done = () => { el.removeEventListener("pointermove", mv); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", cancel); };
    el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", cancel);
  });
}
function newCard(x, y, kind) {
  const cid = Math.random().toString(36).slice(2, 10), id = "c:" + cid; x = snap(x); y = snap(y);
  doc.cards[cid] = {kind: kind || "note", title: "", text: ""};
  doc.items[id] = {s: T(), homes: [lane], born: lane, at: {[lane]: {x, y}}};
  if (kind === "scene") { Object.assign(doc.items[id], {w: SCW, h: SCH}); Object.assign(doc.cards[cid], {where: "", present: lane === "world" ? [] : [lane]}); }
  else settle(id, x, y);
  changed(); draw(); open(id);
}
function resize(ev, el, id) {
  ev.stopPropagation(); ev.preventDefault();
  const o = it(id), b = box(id), st = {x: ev.clientX, y: ev.clientY}, t = ev.target, minH = b.hh + 66;
  cap(t, ev.pointerId);
  const mv = e => {
    o.w = Math.max(300, Math.round(b.w + (e.clientX - st.x) / view.k)); o.h = Math.max(minH, Math.round(b.h + (e.clientY - st.y) / view.k));
    el.style.width = o.w + "px"; el.style.height = o.h + "px"; wires();
  };
  const up = () => { t.removeEventListener("pointermove", mv); t.removeEventListener("pointerup", up); t.removeEventListener("pointercancel", up);
    o.w = snap(o.w); o.h = Math.max(snap(o.h), minH); makeRoom(id, b.w, b.h, lane); capture(id); changed(); draw(); };
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
  setClock(id, `${(f + d + n + 1) % (n + 1)}/${n}`); draw(); if (shown === id) open(id, mode);
}

/* ---------- drawer ---------- */
let shown = null;
function closeDrawer() { $("#drawer").hidden = true; shown = null; $$(".bn.on").forEach(x => x.classList.remove("on")); }
function frame(h) { const d = $("#drawer"); d.innerHTML = `<button class="x" aria-label="Close">×</button>${h}`; d.hidden = false; d.querySelector(".x").onclick = closeDrawer; return d; }
const sessPick = (cur, idp) => `<label for="${idp}">Session</label><select id="${idp}">${L().sessions.map(t => `<option ${t === cur ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
let mode = "view";
const sceneFields = (w, idp) => `<label for="${idp}-w">Where</label><input type="text" id="${idp}-w" list="dl-places" value="${esc(w || "")}" placeholder="Pick a place from the vault, or type one">` +
  `<label for="${idp}-p">Who is present</label><div class="whobox"></div><input type="text" class="whoin" id="${idp}-p" list="dl-people" placeholder="Pick someone from the vault, or type a name and press Enter">`;
function whoPicker(d, list, cb) {
  const box = d.querySelector(".whobox"), inp = d.querySelector(".whoin");
  const known = x => D.people.some(p => p.n === x);
  const paint = () => {
    box.innerHTML = list.map((x, i) => `<span class="ch who">${esc(x)}${known(x) ? "" : " · new"}<button data-rm="${i}" aria-label="Remove ${esc(x)}">×</button></span>`).join("") || '<span class="muted" style="font-size:14px">Nobody yet.</span>';
    box.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { list.splice(+b.dataset.rm, 1); paint(); cb(); });
  };
  const add = () => { const v = inp.value.trim(); inp.value = ""; if (v && !list.includes(v)) { list.push(v); paint(); cb(); } };
  inp.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); add(); } };
  inp.oninput = () => { if (known(inp.value.trim())) add(); };   // picked from the list
  paint(); return {get: () => [...list]};
}
const clockFields = (c, idp) => { const [f, n] = parseClock(c), opts = [...new Set([2, 3, 4, 6, 8, 10, 12, n])].sort((a, b) => a - b);
  return `<label>Clock</label><div class="clkf" id="${idp}-clk"><span class="rng">${ring(f, n, 56)}</span><button class="mini" data-cf="-1" aria-label="Empty a segment">−</button>` +
    `<b>${f}</b><span>of</span><select aria-label="Segments">${opts.map(x => `<option ${x === n ? "selected" : ""}>${x}</option>`).join("")}</select><button class="mini" data-cf="1" aria-label="Fill a segment">+</button></div>`; };
function clockBind(d, idp, c, cb) {
  const w = d.querySelector(`#${idp}-clk`); if (!w) return;
  let [f, n] = parseClock(c);
  const paint = () => { w.querySelector(".rng").innerHTML = ring(f, n, 56); w.querySelector("b").textContent = f; cb(`${f}/${n}`); };
  w.querySelectorAll("[data-cf]").forEach(b => b.onclick = () => { f = Math.max(0, Math.min(n, f + +b.dataset.cf)); paint(); });
  w.querySelector("select").onchange = e => { n = +e.target.value; f = Math.min(f, n); paint(); };
}
const inSceneLine = id => { const sc = sceneOf(id); return sc ? `<p class="inscene">During the scene <b>${esc(titleOf(sc))}</b>.</p>` : ""; };
function sceneView(o, id) {
  const mem = id && it(id) ? membersOf(id) : [];
  return `<h4>Scene</h4><dl class="kv"><dt>Where</dt><dd>${o.where ? esc(o.where) : "<i>not set</i>"}</dd><dt>Present</dt><dd>${o.present && o.present.length ? o.present.map(esc).join(", ") : "<i>nobody listed</i>"}</dd></dl>` +
    (id && it(id) ? `<p class="inscene">On ${esc(names(lanesOf(id)))}. It shows on the board of every player character present; there is one copy, so a change on one board is a change on all of them.</p>` : "") +
    (mem.length ? `<h4>In this scene</h4><ul>${mem.map(m => `<li>${esc(KINDS[kindOf(m)] || "Beat")}: ${esc(titleOf(m))}</li>`).join("")}</ul>` : `<p class="inscene">Drag beats, decisions, clocks and pressures into the box to set them in this scene.</p>`);
}
function open(id, m) {
  shown = id; mode = m || (id === shown ? mode : "view");
  $$(".bn").forEach(x => x.classList.toggle("on", x.dataset.id === id));
  if (id.startsWith("c:")) return cardEditor(id.slice(2));
  const pid = id.slice(2), p = view_of(pid), here = it(id) ? {s: sessOf(id)} : null;
  const tabs = `<div class="tabs2"><button data-m="view" aria-selected="${mode === "view"}">Plan</button><button data-m="edit" aria-selected="${mode === "edit"}">Edit</button></div>`;
  let body;
  if (mode === "edit") {
    const e = L().edits[pid] || {};
    body = `<p class="muted" style="font-size:14px">Fix or change the text here. It shows on the board at once and goes into the vault when you ask Claude to bring the board in. The plan keeps its name; ask Claude if it needs a new one.</p>` +
      `<label for="pe-k">Kind</label><select id="pe-k">${PLANKINDS.map(k => `<option value="${k}" ${k === p.kind ? "selected" : ""}>${KINDS[k]}</option>`).join("")}</select>` +
      (p.kind === "scene" ? sceneFields(p.where, "pe") : "") + (p.kind === "clock" ? clockFields(p.clock, "pe") : "") +
      `<label for="pe-s">Summary (one line)</label><input type="text" id="pe-s" value="${esc(p.summary)}">` +
      `<label for="pe-i">Idea</label><textarea id="pe-i">${esc(p.ideaText)}</textarea>` +
      `<label for="pe-n">Note to Claude (optional)</label><textarea id="pe-n" style="min-height:70px" placeholder="Anything else to change: what it needs, who is involved, a new name…">${esc(e.note || "")}</textarea>` +
      (here ? sessPick(here.s, "pe-sess") : "") +
      `<div class="acts"><button data-done>Done</button>${Object.keys(e).length ? `<button class="del" data-undo>Undo my edits</button>` : ""}</div>`;
  } else {
    const reqs = p.req.map((r, i) => {
      const ok = r.k === "check" ? ["m", "?"] : test(r) ? ["y", "✓"] : ["n", "✗"];
      const nm = r.a && F[r.a] ? `<a href="${esc(F[r.a].href)}">${esc(r.a)}</a>${esc(r.t.slice(r.a.length))}` : esc(r.t);
      const can = ["alive", "dead", "state", "hidden", "revealed", "plan", "played"].includes(r.k) && r.a;
      const lab = r.k === "hidden" || r.k === "revealed" ? (r.a in ov.out ? "undo" : isOut(r.a) ? "it stays hidden" : "it comes out")
        : r.k === "plan" || r.k === "played" ? (ov.drop[r.a] ? "undo" : "set it aside") : (r.a in ov.dead ? "undo" : fall(r.a)[0]);
      const cl = F[r.a] && F[r.a].clues !== undefined ? `<small>${F[r.a].clues} way${F[r.a].clues === 1 ? "" : "s"} it could come out${F[r.a].clues < 3 ? ": aim for three" : ""}</small>` : "";
      return `<li><span class="ok ${ok[0]}">${ok[1]}</span><span class="kk">${esc(r.imp ? "alive*" : r.k)}</span><span>${nm}${cl}</span>${can ? `<button class="mini" data-i="${i}">${esc(lab)}</button>` : ""}</li>`;
    }).join("");
    const opts = p.kind !== "decision" ? "" : `<h4>Options</h4>` + (p.options.length ? `<ul class="req">${p.options.map((o, i) =>
      `<li><span class="kk">choice</span><span>${esc(o.label || "")} → <b>${esc(o.to)}</b></span><button class="mini" data-pick="${i}">what if they choose this?</button></li>`).join("")}</ul>`
      : `<p class="muted" style="font-size:15px">None written yet. Add a card for each choice and link this decision to each one, with the choice as the label.</p>`);
    const ideaHtml = p.edited && (L().edits[pid] || {}).idea !== undefined ? `<p>${esc(p.ideaText).replace(/\n/g, "<br>")}</p>` : p.idea;
    const [cf, cn] = parseClock(p.clock);
    body = `<p>${esc(p.summary)}</p>${cut[pid] ? `<p style="color:var(--vred);font-weight:600">Closed by the what-ifs: ${esc(cut[pid])}</p>` : ""}` +
      (p.kind === "scene" ? sceneView(p, id) : inSceneLine(id)) +
      (p.kind === "clock" ? `<p class="clk"><span class="rng">${ring(cf, cn, 40)}</span> ${cf} of ${cn} filled. Tap the clock on the card to fill a segment.</p>` : "") +
      (p.scene && sceneOf(id) !== "p:" + p.scene ? `<p class="inscene">The vault sets it in the scene <b>${esc(p.scene)}</b>.</p>` : "") +
      (ideaHtml ? `<h4>Idea</h4>${ideaHtml}` : "") + opts +
      `<h4>Needs</h4><ul class="req">${reqs || "<li>Nothing: it can happen any time.</li>"}</ul>` +
      (p.req.some(r => r.imp) ? `<small>* named in its links, so it needs them standing.</small>` : "") +
      (p.links.length ? `<h4>Would change</h4><ul>${p.links.map(l => `<li>${esc(l)}</li>`).join("")}</ul>` : "") +
      (here ? sessPick(here.s, "pv-sess") : "") +
      `<div class="acts"><a href="${esc(p.href)}">Open the plan</a>` +
      (here ? `<button data-back>Back to the tray</button>` : `<button data-place>Place in ${esc(T())}</button>`) +
      `<button data-drop>${ov.drop[pid] ? "Keep this plan" : "What if I set it aside?"}</button><button class="del" data-dropplan>Drop this plan</button></div>`;
  }
  const d = frame(`<div class="ey">${esc(KINDS[p.kind] || "Beat")} · ${esc(p.status)}${p.target ? " · vault says " + esc(p.target) : ""}${p.edited ? " · edited here" : ""}</div><h3>${esc(pid)}</h3>${tabs}${body}`);
  d.querySelectorAll("[data-m]").forEach(b => b.onclick = () => open(id, b.dataset.m));
  const sp = d.querySelector("#pv-sess,#pe-sess"); if (sp) sp.onchange = () => { moveTo(id, sp.value); open(id, mode); };
  if (mode === "edit") {
    const k = d.querySelector("#pe-k"), s = d.querySelector("#pe-s"), i = d.querySelector("#pe-i"), n = d.querySelector("#pe-n"), w = d.querySelector("#pe-w");
    let pres = null, clk = p.clock || "0/4";
    const sync = () => {
      const e = {...(L().edits[pid] || {})}, v = P[pid];
      const set = (key, val, base) => { if (JSON.stringify(val) === JSON.stringify(base)) delete e[key]; else e[key] = val; };
      set("kind", k.value, v.kind); set("summary", s.value.trim(), v.summary); set("idea", i.value.trim(), v.ideaText);
      if (n.value.trim()) e.note = n.value.trim(); else delete e.note;
      if (w) set("where", w.value.trim(), v.where);
      if (pres) set("present", pres.get(), v.present);
      if (d.querySelector("#pe-clk")) set("clock", clk, v.clock || "0/4");
      if (Object.keys(e).length) L().edits[pid] = e; else delete L().edits[pid];
      changed();
    };
    [s, i, n].forEach(x => x.oninput = sync); k.onchange = () => { sync(); toScene(id); changed(); draw(); open(id, "edit"); };
    if (w) { w.oninput = sync; w.onchange = () => { sync(); draw(); }; }
    if (d.querySelector(".whobox")) pres = whoPicker(d, [...(p.present || [])], () => { sync(); draw(); });
    clockBind(d, "pe", clk, x => { clk = x; sync(); draw(); });
    d.querySelector("[data-done]").onclick = () => { sync(); draw(); open(id, "view"); };
    const u = d.querySelector("[data-undo]"); if (u) u.onclick = () => { delete L().edits[pid]; changed(); draw(); open(id, "edit"); };
    return;
  }
  d.querySelectorAll("[data-i]").forEach(b => b.onclick = () => flip(p.req[+b.dataset.i]));
  d.querySelectorAll("[data-pick]").forEach(b => b.onclick = () => {
    const keep = p.options[+b.dataset.pick].to; p.options.forEach(o => { if (o.to !== keep) ov.drop[o.to] = true; }); delete ov.drop[keep]; refresh(); });
  const back = d.querySelector("[data-back]"); if (back) back.onclick = () => unplace(pid);
  const pl = d.querySelector("[data-place]"); if (pl) pl.onclick = () => { place(pid, T()); open(id); };
  d.querySelector("[data-dropplan]").onclick = () => { if (confirm(`Drop “${pid}”? It leaves this board and the tray. Claude marks it dropped in the vault when you bring the board in; until then you can undo it from the tray.`)) dropPlan(pid); };
  d.querySelector("[data-drop]").onclick = () => { if (ov.drop[pid]) delete ov.drop[pid]; else ov.drop[pid] = true; refresh(); };
}
function toScene(id) {   // after its kind changes: a scene needs a box and sits in no other; anything else holds no cards
  const o = it(id); if (!o) return;
  if (isScene(id)) { if (o.scene) release(id, runMode ? undefined : lane); o.w ||= SCW; o.h ||= SCH; if (id.startsWith("c:")) { const c = doc.cards[id.slice(2)]; c.where ||= ""; c.present ||= lanesOf(id).filter(k => k !== "world"); } }
  else Object.keys(doc.items).filter(i => it(i).scene === id).forEach(i => release(i));
}
function cardEditor(id) {
  const c = doc.cards[id];
  const d = frame(`<div class="ey">Your card · not in the vault yet</div><h3>${esc(c.title || "New card")}</h3>` +
    `<label for="ce-k">Kind</label><select id="ce-k">${Object.keys(KINDS).map(k => `<option value="${k}" ${k === c.kind ? "selected" : ""}>${KINDS[k]}</option>`).join("")}</select>` +
    `<small id="ce-kd">${esc(KDESC[c.kind])}</small>` +
    `<label for="ce-t">Title</label><input type="text" id="ce-t" value="${esc(c.title)}" placeholder="A short name, like a plan's">` +
    (c.kind === "scene" ? sceneFields(c.where, "ce") : "") + (c.kind === "clock" ? clockFields(c.clock, "ce") : "") +
    `<label for="ce-x">${c.kind === "scene" ? "The situation: what is going on when it opens" : c.kind === "clock" ? "What happens when it fills" : "What happens, or the choice"}</label><textarea id="ce-x" placeholder="A sentence or two: who, what, and why it matters.">${esc(c.text)}</textarea>` +
    (c.kind === "scene" ? sceneView(c, "c:" + id).replace(/<h4>Scene<\/h4><dl[\s\S]*?<\/dl>/, "") : inSceneLine("c:" + id)) +
    sessPick(sessOf("c:" + id), "ce-sess") +
    `<p class="muted" style="font-size:14px">Link it with the + on its right edge, and label each link. When the board is ready, ask Claude to bring it into the vault.</p>` +
    `<div class="acts"><button data-done>Done</button><button class="del" data-del>Delete card</button></div>`);
  const t = d.querySelector("#ce-t"), x = d.querySelector("#ce-x"), k = d.querySelector("#ce-k");
  const w = d.querySelector("#ce-w");
  const sync = () => { c.title = t.value.trim(); c.text = x.value.trim(); c.kind = k.value; if (w) c.where = w.value.trim(); d.querySelector("#ce-kd").textContent = KDESC[c.kind]; changed(); };
  t.oninput = sync; x.oninput = sync;
  k.onchange = () => { sync(); toScene("c:" + id); changed(); draw(); open("c:" + id); };
  if (w) { w.oninput = sync; w.onchange = () => { sync(); draw(); }; }
  if (d.querySelector(".whobox")) { const pk = whoPicker(d, [...(c.present || [])], () => { c.present = pk.get(); changed(); draw(); if (runMode) return; const on = d.querySelector(".inscene"); if (on && c.kind === "scene") on.textContent = `On ${names(lanesOf("c:" + id))}. One copy: a change on one board is a change on all of them.`; }); }
  clockBind(d, "ce", c.clock, v => { c.clock = v; changed(); draw(); });
  d.querySelector("#ce-sess").onchange = e => { sync(); moveTo("c:" + id, e.target.value); if (it("c:" + id)) open("c:" + id); };
  d.querySelector("[data-done]").onclick = () => { sync(); closeDrawer(); draw(); };
  d.querySelector("[data-del]").onclick = () => deleteCard("c:" + id);
  if (!c.title) setTimeout(() => t.focus(), 50);
}
function edgeEditor(eid) {
  const e = L().edges.find(x => x.id === eid); if (!e) return;
  const d = frame(`<div class="ey">Your link · not in the vault yet</div><h3>${esc(e.from.startsWith("start") ? "Start of " + T() : titleOf(e.from))} → ${esc(titleOf(e.to))}</h3>` +
    `<label for="ee-l">Label</label><input type="text" id="ee-l" value="${esc(e.label)}" placeholder="the choice, or “then”, or “if they stall”">` +
    `<p class="muted" style="font-size:14px">From a decision, write the choice that leads here. Between beats, “then” means the second needs the first.</p>` +
    `<div class="acts"><button data-done>Done</button><button class="del" data-del>Delete link</button></div>`);
  const i = d.querySelector("#ee-l");
  i.oninput = () => { e.label = i.value.trim(); changed(); };
  i.onkeydown = ev => { if (ev.key === "Enter") { closeDrawer(); wires(); } };
  d.querySelector("[data-done]").onclick = () => { closeDrawer(); wires(); };
  d.querySelector("[data-del]").onclick = () => { const s = L(); s.edges = s.edges.filter(x => x.id !== eid); changed(); closeDrawer(); wires(); };
  setTimeout(() => i.focus(), 50);
}
function legend() {
  const k = $("#keyp"), btn = $('[data-act="legend"]');
  if (!k.hidden) { k.hidden = true; btn.classList.remove("on"); return; }
  k.innerHTML = `<button class="x" aria-label="Close">×</button><h3>Key</h3><dl>` +
    Object.keys(KINDS).map(x => `<dt>${KINDS[x]}</dt><dd>${esc(KDESC[x])}</dd>`).join("") +
    `<dt>Session tabs</dt><dd>One canvas per session. The first starts from the end of S${CUR} as played; each later one starts from the end of the one before, as planned. Later holds ideas with no session yet.</dd>` +
    `<dt>Scenes</dt><dd>Drag a scene by its header: the cards inside move with it. Drag its bottom-right corner to resize it. Drop a card inside a scene to set it there. A scene shows on the board of every player character listed as present, with its cards. There is one copy: change it on one board and it changes on all of them; only its place on each canvas is its own.</dd>` +
    `<dt>Moving a card</dt><dd>Drag it onto another session's tab, or pick the session in its panel.</dd>` +
    `<dt>Deleting</dt><dd>The × on a card: a plan goes back to the tray, your own card is deleted; a scene on several boards comes off this one only. Select a card and press Delete to do the same. To drop a plan for good, open it and choose Drop this plan. The × on the open session's tab deletes that session.</dd>` +
    `<dt>Tray</dt><dd>This board's plans that are not placed. Drag one onto the canvas or onto a session tab (on a touch screen, by its ⠿ grip). Drag a card back onto the tray to take it off.</dd>` +
    `<dt>Links</dt><dd>Solid: the vault already joins them, or it is a decision's option. Dashed red: yours, not in the vault yet; drag from a card's + to add one, tap its label to edit it. Dotted grey: it follows something in an earlier session.</dd>` +
    `<dt>Secret chips</dt><dd>A secret the card needs. Tap one to try a what-if: cards it closes fade and say why.</dd>` +
    `<dt>Edited</dt><dd>You changed a plan's text here. It goes into the vault when you ask Claude to bring the board in.</dd></dl>` +
    `<p class="muted" style="font-size:13.5px">Drag the canvas to pan; pinch, Command-scroll or the + and − buttons to zoom; double-click empty canvas to add a card. Cards snap to the grid.</p>`;
  k.hidden = false; btn.classList.add("on");
  k.querySelector(".x").onclick = () => { k.hidden = true; btn.classList.remove("on"); };
}

/* ---------- saving: JSON Canvas on the Gus relay ---------- */
function toCanvas(k) { return withLane(k, () => canvasOf(k)); }
function canvasOf(k) {   // one board as JSON Canvas (for Obsidian); the store itself is items, cards, edits and edges
  const nodes = [], edges = [], off = t => Math.max(0, doc.sessions.indexOf(t)) * TABW, shown = new Set();
  doc.sessions.forEach((t, i) => { ensureAt(t, k); nodes.push({id: "tab-" + t, type: "group", x: i * TABW, y: 0, width: TABW - 200, height: 2400, label: t}); });
  nodes.push({id: "now", type: "text", x: SX, y: SY, width: 300, height: 220, text: `End of S${CUR}`, osse: {now: true, sessions: doc.sessions}});
  doc.sessions.flatMap(t => inTab(t, k)).sort((a, b) => isScene(b) - isScene(a)).forEach(id => {
    const b = box(id, k), o = it(id), t = sessOf(id), sc = sceneOf(id); if (!b) return;
    shown.add(id);
    const g = {session: t, lx: b.x, ly: b.y, ...(isScene(id) ? {w: b.w, h: b.h} : {}), ...(sc ? {scene: sc} : {})};
    const n = {id, x: off(t) + b.x, y: b.y, width: b.w, height: Math.round(b.h)};
    if (id.startsWith("p:")) {
      const pid = id.slice(2);
      Object.assign(n, {type: "file", file: P[pid].path, osse: {plan: pid, ...g}});
      if (doc.edits[pid]) n.osse.edit = doc.edits[pid];
    } else {
      const c = doc.cards[id.slice(2)], more = [c.where ? `At ${c.where}` : "", c.present && c.present.length ? `Present: ${c.present.join(", ")}` : "", c.clock ? `Clock ${c.clock}` : ""].filter(Boolean);
      Object.assign(n, {type: "text", text: `## ${c.title || "Untitled"}\n\n${more.length ? more.join("\n") + "\n\n" : ""}${c.text || ""}`, osse: {card: true, kind: c.kind, title: c.title, body: c.text, ...g}});
      for (const f of ["where", "present", "clock"]) if (c[f] && c[f].length) n.osse[f] = c[f];
      const col = {decision: "1", pressure: "2", note: "3", scene: "4", clock: "5"}[c.kind]; if (col) n.color = col;
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
let timer = null, dirty = false, unread = false;
function status(t, bad) { const el = $("#save"); el.textContent = t; el.classList.toggle("bad", !!bad); }
function changed() {
  dirty = true; store.set("osse-paths-local", JSON.stringify(pack()));
  if (unread) { status("Not saving: the relay could not be read when this page opened. Reload before you change more.", true); return; }
  status(KEY ? "Saving…" : "Saved on this device only");
  clearTimeout(timer); if (KEY) timer = setTimeout(() => save(), 800);
}
async function save(leaving) {
  try {
    const body = JSON.stringify(pack());   // keepalive only when leaving: browsers allow 64 KB of it in all, then refuse
    const r = await fetch(RELAY + "/paths", {method: "PUT", headers: {"x-gus-key": KEY, "content-type": "application/json"}, body, keepalive: leaving === true && new Blob([body]).size < 60000});
    if (!r.ok) throw new Error(r.status === 401 ? "the hub passcode was refused" : "the relay said " + r.status);
    dirty = false; status("Saved");
  } catch (e) { status("Not saved: " + e.message + ". This device keeps a copy.", true); }
}
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
  if (got && got.items) for (const f of ["sessions", "items", "cards", "edits", "edges", "order", "seeded"]) { if (got[f]) doc[f] = got[f]; }
  else if (some(got)) { migrate(got); dirty = true; }
  doc.sessions = (doc.sessions.length ? doc.sessions : defaults()).filter(t => t === "Later" || sessNum(t) > CUR || Object.values(doc.items).some(o => o.s === t));
  sortSessions();
  recut();
  D.lanes.forEach(l => { if (!doc.seeded.includes(l.key)) seed(l.key); });
  if (dirty && KEY && !unread) save();
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden" && dirty && KEY && !unread) save(true); });

/* ---------- boards ---------- */
function pick(key) {
  if (lane && !runMode) views[lane + "|" + T()] = {...view};
  runMode = key === RUN;
  $("#runw").hidden = !runMode; $("#work").hidden = runMode; $$(".tools .mini").forEach(b => { b.hidden = runMode; });
  store.set("osse-paths-lane", key); history.replaceState(null, "", "#" + encodeURIComponent(key));
  $$("#lanes button").forEach(b => b.setAttribute("aria-selected", b.dataset.lane === key));
  closeDrawer();
  if (runMode) { if (!lane) lane = D.lanes[0].key; drawRun(); return; }
  lane = key; draw();
  const v = views[key + "|" + T()]; if (v) { view = {...v}; applyView(); } else fit();
}
function refresh() { recut(); draw(); if (shown) open(shown, mode); }
$("#lanes").innerHTML = `<button role="tab" class="runb" data-lane="${RUN}" title="Every board's scenes for a session, in running order">Session plan</button>` + D.lanes.map(l => `<button role="tab" data-lane="${esc(l.key)}">${esc(l.short)}<small>${l.count}</small></button>`).join("");
$$("#lanes button").forEach(b => b.onclick = () => pick(b.dataset.lane));
$("#wi-reset").onclick = () => { ov.out = {}; ov.dead = {}; ov.drop = {}; refresh(); };
$("#tray-all").onchange = tray; $("#tray-q").oninput = tray;
$$("[data-act]").forEach(b => b.onclick = ev => {
  ev.stopPropagation();
  const a = b.dataset.act;
  const r = board.getBoundingClientRect();
  if (a === "card" || a === "scene") { const w = toWorld(r.left + r.width / 2, r.top + r.height / 3), cw = a === "scene" ? SCW : CARDW;
    newCard(Math.max(SX + 344, w.x - cw / 2), w.y, a === "scene" ? "scene" : ""); }   // clear of the start card
  if (a === "zin" || a === "zout") zoomAt(view.k * (a === "zin" ? 1.25 : .8), r.left + r.width / 2, r.top + r.height / 2);
  if (a === "fit") fit();
  if (a === "legend") legend();
});
$$(".float button").forEach(b => b.onpointerdown = ev => ev.stopPropagation());
document.addEventListener("keydown", e => {
  if ((e.key === "Delete" || e.key === "Backspace") && shown && !e.target.closest("input,textarea,select")) { e.preventDefault(); removeCard(shown); return; }
  if (e.key === "Escape") { if (!$("#drawer").hidden) closeDrawer(); else if (!$("#keyp").hidden) legend(); } });
document.body.insertAdjacentHTML("beforeend", `<div id="meas" aria-hidden="true"></div><datalist id="dl-places">${D.places.map(x => `<option value="${esc(x)}">`).join("")}</datalist>` +
  `<datalist id="dl-people">${D.people.map(x => `<option value="${esc(x.n)}" label="${esc(x.t)}">`).join("")}</datalist>`);
$("#hint").textContent = "Drag plans in from the tray · drag a card's + to link · double-click to add a card";
load().then(() => {
  const want = decodeURIComponent(location.hash.slice(1)) || store.get("osse-paths-lane");
  pick(want === RUN || D.lanes.some(l => l.key === want) ? want : D.lanes[0].key);
});
})();
"""
