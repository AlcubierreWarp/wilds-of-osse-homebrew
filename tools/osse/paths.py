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
        if not lanes:
            lanes = ["The Party"] if "The Party" in named else ["world"]
        sec = _secs(text)
        data[pid] = {"id": pid, "path": n["path"], "href": site.slugs.get(pid, "") + ".html", "status": n.get("status"),
                     "kind": str(n.get("kind") or "scene").lower(), "target": str(n.get("target") or ""),
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
        out.append({"key": nid, "short": short, "kind": "pc",
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
    payload = {"cur": cur, "plans": data, "facts": facts, "lanes": lanes, "gone": sorted(build.GONE)}
    js_data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    head = pages.head("Paths ahead", False).replace('<div class="wrap">', '<div class="wrap wide">')
    return (head + f"<style>{CSS}</style>" + pages.topbar(site, "Paths ahead") +
            '<main class="sheet paths">'
            '<div class="ptop"><h1>Paths ahead</h1><nav class="lanes" id="lanes" role="tablist" aria-label="Boards"></nav></div>'
            '<div class="bar"><div class="whatif"><b>What-ifs</b><span id="wi-list" class="muted"></span>'
            '<button id="wi-reset" class="mini" hidden>Clear</button></div>'
            '<div class="tools"><button class="mini" data-act="card">+ Card</button><span id="save" class="save"></span></div></div>'
            '<div class="work"><div class="stage"><nav class="sess" id="sess" role="tablist" aria-label="Sessions"></nav>'
            '<div class="board" id="board" aria-label="Planning board">'
            '<div class="world" id="world"><svg id="wires" class="wires"></svg><div id="nodes"></div></div>'
            '<div class="float"><button class="fb" data-act="fit" title="Fit to the window" aria-label="Fit to the window">'
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
.lanes button small{font:500 11px var(--f-mono);margin-left:5px;opacity:.75}
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
.fb{height:34px;min-width:34px;display:inline-flex;align-items:center;justify-content:center;font:600 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;
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
@media (max-width:900px){.work{grid-template-columns:1fr;grid-template-rows:1fr 34vh;height:calc(100vh - 170px)}}
@media print{.bar,.tray,.drawer,.float{display:none}.work{display:block;height:auto}}
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
const GRID = 22, CARDW = 250, SX = 44, SY = 44, FIRSTX = 418, TABW = 4000;
const snap = v => Math.round(v / GRID) * GRID;
const KINDS = {scene: "Scene", decision: "Decision", pressure: "Pressure", bottleneck: "Bottleneck", note: "Note"};
const KDESC = {scene: "Something that could happen: a situation to put in front of them, not a script.",
  decision: "A choice the character faces. Each option leads to its own card; label each link with the choice.",
  pressure: "What the world does if no one acts: a portent that fires when they stall.",
  bottleneck: "A beat most paths reach, where branches meet again.",
  note: "A loose idea. Claude turns it into a plan when you ask."};
let doc = {lanes: {}}, lane = null, view = {x: 0, y: 0, k: 1}, views = {}, hs = {};
const tabOf = {};   // board -> open session tab

/* ---------- state ---------- */
const sessNum = s => +(String(s).match(/^S(\d+)$/i) || [])[1] || 0;
function defaults() { return [1, 2, 3].map(i => "S" + (CUR + i)).concat("Later"); }
function seed(key) {
  const s = {sessions: defaults(), placed: {}, cards: {}, edits: {}, edges: []}, per = {};
  Object.values(P).filter(p => p.lanes.includes(key) && sessNum(p.target) > CUR).forEach(p => {
    const t = "S" + sessNum(p.target);
    if (!s.sessions.includes(t)) { s.sessions.splice(s.sessions.length - 1, 0, t); s.sessions.sort((a, b) => (sessNum(a) || 1e9) - (sessNum(b) || 1e9)); }
    per[t] = (per[t] || 0) + 1;
    s.placed[p.id] = {s: t, x: FIRSTX, y: SY + (per[t] - 1) * 176};
  });
  return s;
}
function L() {
  if (!doc.lanes[lane]) doc.lanes[lane] = seed(lane);
  const s = doc.lanes[lane];
  for (const id of Object.keys(s.placed)) if (!P[id]) delete s.placed[id];   // played, pruned or dropped since
  s.edits ||= {};
  return s;
}
const T = () => { const s = L(); if (!s.sessions.includes(tabOf[lane])) tabOf[lane] = s.sessions[0]; return tabOf[lane]; };
const where = id => { const s = L(); return id.startsWith("p:") ? s.placed[id.slice(2)] : id.startsWith("c:") ? s.cards[id.slice(2)] : null; };
const sessOf = id => { const o = where(id); return o ? o.s : null; };
const view_of = id => { const p = P[id], e = L().edits[id] || {}; return {...p, summary: e.summary ?? p.summary, kind: e.kind ?? p.kind, ideaText: e.idea ?? p.ideaText, edited: !!Object.keys(e).length}; };

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
  const p = view_of(id), o = L().placed[id];
  const mv = p.target && o && o.s.toUpperCase() !== p.target.toUpperCase() ? `vault says ${p.target}` : "";
  const checks = p.req.filter(r => r.k === "check").length;
  return `<div class="k"><span>${esc(KINDS[p.kind] || "Scene")}</span><span>${p.edited ? "edited · not in vault" : esc(p.status)}</span></div><div class="t">${esc(p.id)}</div>` +
    `<div class="s">${esc(p.summary)}</div>` +
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
function titleOf(id) { if (id.startsWith("p:")) return id.slice(2); const c = L().cards[id.slice(2)]; return c ? (c.title || "untitled card") : id; }
function startCard(tab, idx) {
  const s = L(), ln = D.lanes.find(x => x.key === lane);
  if (idx === 0) return nowCard(ln.now, ln.kind);
  const prev = s.sessions[idx - 1];
  const items = [...Object.entries(s.placed).filter(([, o]) => o.s === prev).map(([id]) => "p:" + id),
    ...Object.entries(s.cards).filter(([, c]) => c.s === prev).map(([id]) => "c:" + id)];
  const later = tab === "Later";
  return `<div class="k"><span>${later ? "Later · no session yet" : `End of ${esc(prev)} · as planned`}</span></div>` +
    `<div class="t">${later ? "Whenever it fits" : `After ${esc(prev)}`}</div>` +
    (later ? `<div class="s">Ideas without a session. Place a card here, then move it to a session when it is time.</div>` :
      items.length ? `<div class="k"><span>Planned for ${esc(prev)}</span></div><ul>${items.map(i => `<li>${esc(titleOf(i))}</li>`).join("")}</ul>`
        : `<div class="s">Nothing planned for ${esc(prev)} yet.</div>`);
}
function draw() {
  const s = L(), tab = T(), idx = s.sessions.indexOf(tab);
  const out = [`<div class="bn now ${idx ? "start" : ""}" data-id="start" style="left:${SX}px;top:${SY}px">${startCard(tab, idx)}</div>`];
  for (const [id, o] of Object.entries(s.placed)) if (o.s === tab) {
    const p = view_of(id);
    out.push(`<div class="bn k-${esc(p.kind)} ${p.edited ? "edited" : ""} ${cut[id] ? "cut" : ""}" data-id="p:${esc(id)}" style="left:${o.x}px;top:${o.y}px">${planCard(id)}<button class="xx" title="Take it off the board (back to the tray)" aria-label="Take off the board">×</button><span class="hd" title="Drag to another card to link them"></span></div>`);
  }
  for (const [id, c] of Object.entries(s.cards)) if (c.s === tab)
    out.push(`<div class="bn mine k-${esc(c.kind)}" data-id="c:${esc(id)}" style="left:${c.x}px;top:${c.y}px"><div class="k"><span>${esc(KINDS[c.kind] || "Note")}</span><span>yours · not in vault</span></div>` +
      `<div class="t">${esc(c.title || "Untitled")}</div>${c.text ? `<div class="s">${esc(c.text.length > 220 ? c.text.slice(0, 220) + "…" : c.text)}</div>` : ""}<button class="xx" title="Delete this card" aria-label="Delete card">×</button><span class="hd" title="Drag to another card to link them"></span></div>`);
  $("#nodes").innerHTML = out.join("");
  $$("#nodes .bn").forEach(el => { hs[el.dataset.id] = el.offsetHeight; });
  sessTabs(); wires(); bindNodes(); tray(); applyView();
}
function sessTabs() {
  const s = L(), tab = T();
  const count = t => Object.values(s.placed).filter(o => o.s === t).length + Object.values(s.cards).filter(c => c.s === t).length;
  $("#sess").innerHTML = s.sessions.map((t, i) => `<button role="tab" data-tab="${esc(t)}" aria-selected="${t === tab}">${esc(t)}${i === 0 && t !== "Later" ? " · next" : ""}<small>${count(t)}</small>` +
    (t === tab && t !== "Later" && s.sessions.length > 2 ? `<span class="dx" data-delsess title="Delete this session" aria-label="Delete ${esc(t)}">×</span>` : "") + `</button>`).join("") +
    `<button class="add" data-addsess title="Add the session after the last one">+ Session</button>`;
  $$("#sess [data-tab]").forEach(b => b.onclick = ev => { if (ev.target.closest("[data-delsess]")) delSession(b.dataset.tab); else openTab(b.dataset.tab); });
  $("#sess [data-addsess]").onclick = () => {
    const nums = s.sessions.map(sessNum).filter(Boolean), n = "S" + ((nums.length ? Math.max(...nums) : CUR) + 1);
    s.sessions.splice(s.sessions.indexOf("Later") < 0 ? s.sessions.length : s.sessions.indexOf("Later"), 0, n); changed(); openTab(n);
  };
}
function delSession(t) {
  const s = L(), n = sessNum(t);
  const plans = Object.values(s.placed).filter(o => o.s === t).length, cards = Object.values(s.cards).filter(c => c.s === t).length;
  const what = [plans ? `its ${plans} plan${plans > 1 ? "s go" : " goes"} back to the tray` : "", cards ? `your ${cards} card${cards > 1 ? "s move" : " moves"} to Later` : ""].filter(Boolean).join(" and ");
  const later = s.sessions.filter(x => sessNum(x) > n);
  if (!confirm(`Delete ${t}?` + (what ? ` ${what[0].toUpperCase() + what.slice(1)}.` : "") + (later.length ? ` ${later.join(", ")} move up one.` : ""))) return;
  for (const [id, o] of Object.entries(s.placed)) if (o.s === t) { delete s.placed[id]; s.edges = s.edges.filter(e => e.from !== "p:" + id && e.to !== "p:" + id); }
  for (const c of Object.values(s.cards)) if (c.s === t) { c.s = "Later"; const f = freeSpot("Later"); c.x = f.x; c.y = f.y; }
  s.edges = s.edges.filter(e => e.from !== "start:" + t);
  s.sessions = s.sessions.filter(x => x !== t);
  const down = x => sessNum(x) > n ? "S" + (sessNum(x) - 1) : x;
  s.sessions = s.sessions.map(down);
  [...Object.values(s.placed), ...Object.values(s.cards)].forEach(o => { o.s = down(o.s); });
  s.edges.forEach(e => { if (e.from.startsWith("start:")) e.from = "start:" + down(e.from.slice(6)); });
  const i = Math.max(0, s.sessions.indexOf(down(later[0] || "")));
  tabOf[lane] = s.sessions[later.length ? i : Math.max(0, s.sessions.length - 2)];
  changed(); closeDrawer(); draw(); fit();
}
function removeCard(id) {
  if (id.startsWith("p:")) { unplace(id.slice(2)); return; }
  const s = L(), c = s.cards[id.slice(2)];
  if (!c || ((c.title || c.text) && !confirm(`Delete “${c.title || "this card"}”? This cannot be undone.`))) return;
  delete s.cards[id.slice(2)]; s.edges = s.edges.filter(e => e.from !== id && e.to !== id); changed(); closeDrawer(); draw();
}
function dropPlan(pid) {
  const s = L(); s.edits[pid] = {...(s.edits[pid] || {}), drop: true}; unplace(pid);
}
function openTab(t) {
  views[lane + "|" + T()] = {...view}; tabOf[lane] = t; closeDrawer(); draw();
  const v = views[lane + "|" + t]; if (v) { view = {...v}; applyView(); } else fit();
}
function box(id) {
  if (id === "start") return {x: SX, y: SY, w: 300, h: hs.start || 200};
  const o = where(id); return o && {x: o.x, y: o.y, w: CARDW, h: hs[id] || 110};
}
function genEdges() {
  const s = L(), out = [];
  for (const id of Object.keys(s.placed)) {
    const p = P[id];
    p.req.forEach(r => { if ((r.k === "plan" || r.k === "played") && s.placed[r.a]) out.push({from: "p:" + r.a, to: "p:" + id, label: "then"}); });
    if (p.kind === "decision") p.options.forEach(o => { if (s.placed[o.to]) out.push({from: "p:" + id, to: "p:" + o.to, label: o.label, opt: 1}); });
  }
  const seen = new Set(out.map(e => e.from + ">" + e.to));
  return out.concat(s.edges.filter(e => !seen.has(e.from + ">" + e.to)).map(e => ({...e, own: 1})));
}
function curve(a, b) {
  const x1 = a.x + a.w, y1 = a.y + Math.min(a.h / 2, 56), x2 = b.x, y2 = b.y + Math.min(b.h / 2, 56);
  const dx = x2 < x1 + 20 ? 90 : Math.max(50, (x2 - x1) / 2);
  return {d: `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`, mx: (x1 + x2) / 2, my: (y1 + y2) / 2};
}
function wires(temp) {
  const s = L(), tab = T(), ti = s.sessions.indexOf(tab), order = x => s.sessions.indexOf(x);
  let svg = '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="rgba(124,22,34,.75)"/></marker></defs>', labels = "";
  const carried = new Set();
  genEdges().forEach(e => {
    if (e.from.startsWith("start")) e = {...e, from: "start"};
    const fs = e.from === "start" ? tab : sessOf(e.from), ts = sessOf(e.to);
    if (ts !== tab) return;
    let from = e.from, lab = e.label, cls = e.own ? "own" : e.opt ? "opt" : "";
    if (fs !== tab) {   // from an earlier session: it comes in through this tab's start card
      if (order(fs) > ti || carried.has(e.to)) return;
      carried.add(e.to); from = "start"; lab = `after ${titleOf(e.from)} (${fs})`; cls = "carry";
    }
    const a = box(from), b = box(e.to); if (!a || !b) return;
    const c = curve(a, b);
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
  const s = L(), all = $("#tray-all").checked, q = $("#tray-q").value.trim().toLowerCase();
  const list = Object.values(P).filter(p => !s.placed[p.id] && !(s.edits[p.id] || {}).drop && (all || p.lanes.includes(lane)) &&
    (!q || (p.id + " " + p.summary).toLowerCase().includes(q)));
  let h = "";
  ["decision", "scene", "pressure", "bottleneck"].forEach(k => {
    const ps = list.filter(p => (view_of(p.id).kind || "scene") === k).sort((a, b) => (a.status !== "ready") - (b.status !== "ready") || a.id.localeCompare(b.id));
    if (!ps.length) return;
    h += `<h4>${KINDS[k]}s</h4>` + ps.map(p => `<div class="ti k-${esc(k)} ${cut[p.id] ? "cut" : ""}" data-plan="${esc(p.id)}"><span class="g" title="Drag onto the board or a session tab">⠿</span><div>` +
      `<div class="t">${esc(p.id)}</div><div class="s">${esc(view_of(p.id).summary)}</div><div class="chips">${p.status === "ready" ? '<span class="ch ready">ready</span>' : ""}${p.target ? `<span class="ch">${esc(p.target)}</span>` : ""}` +
      secReq(p).map(r => `<span class="ch">secret: ${esc(r.a)}</span>`).join("") + `</div></div></div>`).join("");
  });
  if (!h) h = `<p class="empty">${Object.keys(s.placed).length ? "Every plan for this board is placed." : "No live plans for this board yet."} ${all ? "" : "Tick “every live plan” to pull one from another board, or add a card."}</p>`;
  const gone = Object.keys(s.edits).filter(id => s.edits[id].drop && P[id]);
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
  const r = board.getBoundingClientRect(); k = Math.min(1.6, Math.max(.3, k));
  const px = cx - r.left, py = cy - r.top;
  view.x = px - (px - view.x) * k / view.k; view.y = py - (py - view.y) * k / view.k; view.k = k; applyView();
}
function fit() {
  const r = board.getBoundingClientRect(), bs = ["start", ...$$("#nodes .bn").map(e => e.dataset.id)].map(box).filter(Boolean);
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
    el.addEventListener("pointerdown", ev => {
      if (ev.target.closest(".hd,.xx,.ch.sec,a")) return;
      ev.stopPropagation();
      const b = box(id), st = {x: ev.clientX, y: ev.clientY}, o = where(id); let moved = false;
      cap(el, ev.pointerId);
      const mv = e => {
        const dx = (e.clientX - st.x) / view.k, dy = (e.clientY - st.y) / view.k;
        if (!moved && Math.hypot(dx, dy) < 5) return;
        moved = true; el.classList.add("drag");
        o.x = Math.round(b.x + dx); o.y = Math.round(b.y + dy);
        el.style.left = o.x + "px"; el.style.top = o.y + "px"; wires();
        $("#tray").classList.toggle("over", id.startsWith("p:") && inRect(e, $("#tray")));
        const tb = tabUnder(e); $$("#sess button").forEach(x => x.classList.toggle("drop", x === tb && tb.dataset.tab !== T()));
      };
      const up = e => {
        el.removeEventListener("pointermove", mv); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
        $("#tray").classList.remove("over"); $$("#sess button").forEach(x => x.classList.remove("drop"));
        if (!moved) { open(id); return; }
        if (id.startsWith("p:") && inRect(e, $("#tray"))) { unplace(id.slice(2)); return; }
        const tb = tabUnder(e);
        if (tb && tb.dataset.tab !== T()) { o.x = b.x; o.y = b.y; moveTo(id, tb.dataset.tab); return; }
        o.x = snap(o.x); o.y = snap(o.y); changed(); draw();
      };
      el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    });
  });
}
function freeSpot(t) {
  const s = L(), ys = [...Object.values(s.placed), ...Object.values(s.cards)].filter(o => o.s === t && Math.abs(o.x - FIRSTX) < 200).map(o => o.y);
  return {x: FIRSTX, y: ys.length ? snap(Math.max(...ys) + 176) : SY};
}
function moveTo(id, t) {
  const o = where(id); o.s = t; const f = freeSpot(t); o.x = f.x; o.y = f.y;
  L().edges = L().edges.filter(e => !(e.from.startsWith("start") && e.to === id));
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
    const id = "e" + Math.random().toString(36).slice(2, 9);
    L().edges.push({id, from: from === "start" ? "start:" + T() : from, to, label: ""}); changed(); wires(); edgeEditor(id);
  };
  t.addEventListener("pointermove", mv); t.addEventListener("pointerup", up);
}
function place(pid, t, x, y) {
  const f = x === undefined ? freeSpot(t) : {x: snap(x), y: snap(y)};
  L().placed[pid] = {s: t, x: f.x, y: f.y}; changed(); draw();
}
function unplace(pid) {
  const s = L(); delete s.placed[pid];
  s.edges = s.edges.filter(e => e.from !== "p:" + pid && e.to !== "p:" + pid); changed(); closeDrawer(); draw();
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
function newCard(x, y) {
  const id = Math.random().toString(36).slice(2, 10);
  L().cards[id] = {s: T(), x: snap(x), y: snap(y), kind: "note", title: "", text: ""};
  changed(); draw(); open("c:" + id);
}

/* ---------- drawer ---------- */
let shown = null;
function closeDrawer() { $("#drawer").hidden = true; shown = null; $$(".bn.on").forEach(x => x.classList.remove("on")); }
function frame(h) { const d = $("#drawer"); d.innerHTML = `<button class="x" aria-label="Close">×</button>${h}`; d.hidden = false; d.querySelector(".x").onclick = closeDrawer; return d; }
const sessPick = (cur, idp) => `<label for="${idp}">Session</label><select id="${idp}">${L().sessions.map(t => `<option ${t === cur ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
let mode = "view";
function open(id, m) {
  shown = id; mode = m || (id === shown ? mode : "view");
  $$(".bn").forEach(x => x.classList.toggle("on", x.dataset.id === id));
  if (id.startsWith("c:")) return cardEditor(id.slice(2));
  const pid = id.slice(2), p = view_of(pid), here = L().placed[pid];
  const tabs = `<div class="tabs2"><button data-m="view" aria-selected="${mode === "view"}">Plan</button><button data-m="edit" aria-selected="${mode === "edit"}">Edit</button></div>`;
  let body;
  if (mode === "edit") {
    const e = L().edits[pid] || {};
    body = `<p class="muted" style="font-size:14px">Fix or change the text here. It shows on the board at once and goes into the vault when you ask Claude to bring the board in. The plan keeps its name; ask Claude if it needs a new one.</p>` +
      `<label for="pe-k">Kind</label><select id="pe-k">${["scene", "decision", "pressure", "bottleneck"].map(k => `<option value="${k}" ${k === p.kind ? "selected" : ""}>${KINDS[k]}</option>`).join("")}</select>` +
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
    body = `<p>${esc(p.summary)}</p>${cut[pid] ? `<p style="color:var(--vred);font-weight:600">Closed by the what-ifs: ${esc(cut[pid])}</p>` : ""}` +
      (ideaHtml ? `<h4>Idea</h4>${ideaHtml}` : "") + opts +
      `<h4>Needs</h4><ul class="req">${reqs || "<li>Nothing: it can happen any time.</li>"}</ul>` +
      (p.req.some(r => r.imp) ? `<small>* named in its links, so it needs them standing.</small>` : "") +
      (p.links.length ? `<h4>Would change</h4><ul>${p.links.map(l => `<li>${esc(l)}</li>`).join("")}</ul>` : "") +
      (here ? sessPick(here.s, "pv-sess") : "") +
      `<div class="acts"><a href="${esc(p.href)}">Open the plan</a>` +
      (here ? `<button data-back>Back to the tray</button>` : `<button data-place>Place in ${esc(T())}</button>`) +
      `<button data-drop>${ov.drop[pid] ? "Keep this plan" : "What if I set it aside?"}</button><button class="del" data-dropplan>Drop this plan</button></div>`;
  }
  const d = frame(`<div class="ey">${esc(KINDS[p.kind] || "Scene")} · ${esc(p.status)}${p.target ? " · vault says " + esc(p.target) : ""}${p.edited ? " · edited here" : ""}</div><h3>${esc(pid)}</h3>${tabs}${body}`);
  d.querySelectorAll("[data-m]").forEach(b => b.onclick = () => open(id, b.dataset.m));
  const sp = d.querySelector("#pv-sess,#pe-sess"); if (sp) sp.onchange = () => { moveTo(id, sp.value); open(id, mode); };
  if (mode === "edit") {
    const k = d.querySelector("#pe-k"), s = d.querySelector("#pe-s"), i = d.querySelector("#pe-i"), n = d.querySelector("#pe-n");
    const sync = () => {
      const e = {};
      if (k.value !== P[pid].kind) e.kind = k.value;
      if (s.value.trim() !== P[pid].summary) e.summary = s.value.trim();
      if (i.value.trim() !== P[pid].ideaText) e.idea = i.value.trim();
      if (n.value.trim()) e.note = n.value.trim();
      if ((L().edits[pid] || {}).drop) e.drop = true;
      if (Object.keys(e).length) L().edits[pid] = e; else delete L().edits[pid];
      changed();
    };
    [s, i, n].forEach(x => x.oninput = sync); k.onchange = () => { sync(); draw(); };
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
function cardEditor(id) {
  const c = L().cards[id];
  const d = frame(`<div class="ey">Your card · not in the vault yet</div><h3>${esc(c.title || "New card")}</h3>` +
    `<label for="ce-k">Kind</label><select id="ce-k">${Object.keys(KINDS).map(k => `<option value="${k}" ${k === c.kind ? "selected" : ""}>${KINDS[k]}</option>`).join("")}</select>` +
    `<small id="ce-kd">${esc(KDESC[c.kind])}</small>` +
    `<label for="ce-t">Title</label><input type="text" id="ce-t" value="${esc(c.title)}" placeholder="A short name, like a plan's">` +
    `<label for="ce-x">What happens, or the choice</label><textarea id="ce-x" placeholder="A sentence or two: who, what, and why it matters.">${esc(c.text)}</textarea>` +
    sessPick(c.s, "ce-sess") +
    `<p class="muted" style="font-size:14px">Link it with the + on its right edge, and label each link. When the board is ready, ask Claude to bring it into the vault.</p>` +
    `<div class="acts"><button data-done>Done</button><button class="del" data-del>Delete card</button></div>`);
  const t = d.querySelector("#ce-t"), x = d.querySelector("#ce-x"), k = d.querySelector("#ce-k");
  const sync = () => { c.title = t.value.trim(); c.text = x.value.trim(); c.kind = k.value; d.querySelector("#ce-kd").textContent = KDESC[c.kind]; changed(); };
  t.oninput = sync; x.oninput = sync; k.onchange = () => { sync(); draw(); open("c:" + id); };
  d.querySelector("#ce-sess").onchange = e => { sync(); moveTo("c:" + id, e.target.value); open("c:" + id); };
  d.querySelector("[data-done]").onclick = () => { sync(); closeDrawer(); draw(); };
  d.querySelector("[data-del]").onclick = () => removeCard("c:" + id);
  if (!c.title) setTimeout(() => t.focus(), 50);
}
function edgeEditor(eid) {
  const e = L().edges.find(x => x.id === eid); if (!e) return;
  const d = frame(`<div class="ey">Your link · not in the vault yet</div><h3>${esc(e.from.startsWith("start") ? "Start of " + T() : titleOf(e.from))} → ${esc(titleOf(e.to))}</h3>` +
    `<label for="ee-l">Label</label><input type="text" id="ee-l" value="${esc(e.label)}" placeholder="the choice, or “then”, or “if they stall”">` +
    `<p class="muted" style="font-size:14px">From a decision, write the choice that leads here. Between scenes, “then” means the second needs the first.</p>` +
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
    `<dt>Moving a card</dt><dd>Drag it onto another session's tab, or pick the session in its panel.</dd>` +
    `<dt>Deleting</dt><dd>The × on a card: a plan goes back to the tray, your own card is deleted. Select a card and press Delete to do the same. To drop a plan for good, open it and choose Drop this plan. The × on the open session's tab deletes that session.</dd>` +
    `<dt>Tray</dt><dd>This board's plans that are not placed. Drag one onto the canvas or onto a session tab (on a touch screen, by its ⠿ grip). Drag a card back onto the tray to take it off.</dd>` +
    `<dt>Links</dt><dd>Solid: the vault already joins them, or it is a decision's option. Dashed red: yours, not in the vault yet; drag from a card's + to add one, tap its label to edit it. Dotted grey: it follows something in an earlier session.</dd>` +
    `<dt>Secret chips</dt><dd>A secret the card needs. Tap one to try a what-if: cards it closes fade and say why.</dd>` +
    `<dt>Edited</dt><dd>You changed a plan's text here. It goes into the vault when you ask Claude to bring the board in.</dd></dl>` +
    `<p class="muted" style="font-size:13.5px">Drag the canvas to pan; pinch or Command-scroll to zoom; double-click empty canvas to add a card. Cards snap to the grid.</p>`;
  k.hidden = false; btn.classList.add("on");
  k.querySelector(".x").onclick = () => { k.hidden = true; btn.classList.remove("on"); };
}

/* ---------- saving: JSON Canvas on the Gus relay ---------- */
function toCanvas(key) {
  const s = doc.lanes[key], nodes = [], edges = [], off = t => Math.max(0, s.sessions.indexOf(t)) * TABW;
  s.sessions.forEach((t, i) => nodes.push({id: "tab-" + t, type: "group", x: i * TABW, y: 0, width: TABW - 200, height: 2400, label: t}));
  nodes.push({id: "now", type: "text", x: SX, y: SY, width: 300, height: 220, text: `End of S${CUR}`, osse: {now: true, sessions: s.sessions}});
  for (const [id, o] of Object.entries(s.placed)) {
    const n = {id: "p:" + id, type: "file", file: (P[id] || {}).path || `Plans/${id}.md`, x: off(o.s) + o.x, y: o.y, width: CARDW, height: 140,
      osse: {plan: id, session: o.s, lx: o.x, ly: o.y}};
    if (s.edits[id]) n.osse.edit = s.edits[id];
    nodes.push(n);
  }
  for (const [id, pid] of Object.keys(s.edits).filter(x => !s.placed[x]).map(x => [x, x]))
    nodes.push({id: "e:" + id, type: "file", file: (P[id] || {}).path || `Plans/${id}.md`, x: -400, y: 0, width: CARDW, height: 140, osse: {plan: pid, tray: true, edit: s.edits[id]}});
  for (const [id, c] of Object.entries(s.cards)) {
    const n = {id: "c:" + id, type: "text", x: off(c.s) + c.x, y: c.y, width: CARDW, height: 120, text: `## ${c.title || "Untitled"}\n\n${c.text || ""}`,
      osse: {card: true, kind: c.kind, title: c.title, body: c.text, session: c.s, lx: c.x, ly: c.y}};
    const col = {decision: "1", pressure: "2", note: "3"}[c.kind]; if (col) n.color = col;
    nodes.push(n);
  }
  s.edges.forEach(e => { const x = {id: e.id, fromNode: e.from.startsWith("start") ? "now" : e.from, fromSide: "right", toNode: e.to, toSide: "left", osse: {own: true, from: e.from}}; if (e.label) x.label = e.label; edges.push(x); });
  return {nodes, edges};
}
function fromCanvas(cv, after) {
  const s = {sessions: null, placed: {}, cards: {}, edits: {}, edges: []};
  let cols = 3;
  const oldCol = (n, col) => ({s: col, x: snap(FIRSTX + Math.max(0, (n.x - 340) % 300)), y: snap(n.y)});   // the earlier column layout
  (cv.nodes || []).forEach(n => {
    const o = n.osse || {};
    if (o.now) { if (o.sessions) s.sessions = o.sessions; cols = o.cols || 3; }
    else if (o.plan) {
      if (o.edit) s.edits[o.plan] = o.edit;
      if (o.tray) return;
      s.placed[o.plan] = o.session ? {s: o.session, x: o.lx, y: o.ly} : oldCol(n, o.column || "Later");
    } else if (o.card) {
      const pos = o.session ? {s: o.session, x: o.lx, y: o.ly} : oldCol(n, o.column || "Later");
      s.cards[n.id.replace(/^c:/, "")] = {...pos, kind: o.kind || "note", title: o.title || "", text: o.body || ""};
    }
  });
  if (!s.sessions) { s.sessions = []; for (let i = 1; i <= cols; i++) s.sessions.push("S" + ((after || CUR) + i)); s.sessions.push("Later"); }
  const used = [...Object.values(s.placed), ...Object.values(s.cards)].map(o => o.s);
  used.forEach(t => { if (t && !s.sessions.includes(t)) s.sessions.splice(s.sessions.length - 1, 0, t); });
  (cv.edges || []).forEach(e => { if ((e.osse || {}).own) s.edges.push({id: e.id, from: e.osse.from || e.fromNode, to: e.toNode, label: e.label || ""}); });
  return s;
}
function pack() { const lanes = {}; for (const k in doc.lanes) lanes[k] = toCanvas(k); return {format: "jsoncanvas-1.0 per board, sessions side by side", after: CUR, lanes}; }
let timer = null, dirty = false;
function status(t, bad) { const el = $("#save"); el.textContent = t; el.classList.toggle("bad", !!bad); }
function changed() {
  dirty = true; store.set("osse-paths-local", JSON.stringify(pack()));
  status(KEY ? "Saving…" : "Saved on this device only");
  clearTimeout(timer); if (KEY) timer = setTimeout(save, 800);
}
async function save() {
  try {
    const r = await fetch(RELAY + "/paths", {method: "PUT", headers: {"x-gus-key": KEY, "content-type": "application/json"}, body: JSON.stringify(pack()), keepalive: true});
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
      else status(r.status === 401 ? "Hub passcode refused: unlock the hub again to save." : "The relay said " + r.status + ": showing this device's copy.", true);
    } catch (e) { status("Relay unreachable: showing this device's copy.", true); }
  } else status("Unlock the game master section on the hub to save to the relay. Until then this device keeps your changes.");
  if (!got || !got.lanes || !Object.keys(got.lanes).length) { try { const loc = JSON.parse(store.get("osse-paths-local") || "null"); if (loc && loc.lanes) { got = loc; if (KEY) dirty = true; } } catch (e) {} }
  if (got && got.lanes) for (const k in got.lanes) doc.lanes[k] = fromCanvas(got.lanes[k], got.after);
  if (dirty) save();
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden" && dirty && KEY) save(); });

/* ---------- boards ---------- */
function pick(key) {
  if (lane) views[lane + "|" + T()] = {...view};
  lane = key; store.set("osse-paths-lane", key); history.replaceState(null, "", "#" + encodeURIComponent(key));
  $$("#lanes button").forEach(b => b.setAttribute("aria-selected", b.dataset.lane === key));
  closeDrawer(); draw();
  const v = views[key + "|" + T()]; if (v) { view = {...v}; applyView(); } else fit();
}
function refresh() { recut(); draw(); if (shown) open(shown, mode); }
$("#lanes").innerHTML = D.lanes.map(l => `<button role="tab" data-lane="${esc(l.key)}">${esc(l.short)}<small>${l.count}</small></button>`).join("");
$$("#lanes button").forEach(b => b.onclick = () => pick(b.dataset.lane));
$("#wi-reset").onclick = () => { ov.out = {}; ov.dead = {}; ov.drop = {}; refresh(); };
$("#tray-all").onchange = tray; $("#tray-q").oninput = tray;
$$("[data-act]").forEach(b => b.onclick = ev => {
  ev.stopPropagation();
  const a = b.dataset.act;
  if (a === "card") { const r = board.getBoundingClientRect(), w = toWorld(r.left + r.width / 2, r.top + r.height / 3); newCard(w.x - CARDW / 2, w.y); }
  if (a === "fit") fit();
  if (a === "legend") legend();
});
$$(".float button").forEach(b => b.onpointerdown = ev => ev.stopPropagation());
document.addEventListener("keydown", e => {
  if ((e.key === "Delete" || e.key === "Backspace") && shown && !e.target.closest("input,textarea,select")) { e.preventDefault(); removeCard(shown); return; }
  if (e.key === "Escape") { if (!$("#drawer").hidden) closeDrawer(); else if (!$("#keyp").hidden) legend(); } });
$("#hint").textContent = "Drag plans in from the tray · drag a card's + to link · double-click to add a card";
recut();
load().then(() => {
  const want = decodeURIComponent(location.hash.slice(1)) || store.get("osse-paths-lane");
  pick(D.lanes.some(l => l.key === want) ? want : D.lanes[0].key);
});
})();
"""
