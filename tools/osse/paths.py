#!/usr/bin/env python3
"""Paths ahead: a DM screen (vault/paths.html) that draws every live plan as a branching tree under the player
character it concerns. Built by pages.py on every build; never edit the page by hand.

How a plan finds its lane:
  1. it names a player character in its Links or Requires (it can sit in two lanes);
  2. else it touches someone or something tied to a player character at weight 5 ("through Corvane Aerrowyn");
  3. else it names The Party: the whole party's lane;
  4. else it goes in "Around the party".
How it branches: a plan that needs another live plan in the same lane (`plan:` or `played:`) grows from it. Otherwise
it hangs from the first secret it needs hidden or revealed, then from a played plan it follows, then from the lane's root.
The page's what-ifs (a secret comes out, someone dies, a plan is set aside) re-check every plan in the browser with the
same rules build.py uses, cascading through `plan:`. Nothing is written back to the vault."""
import html, json, re

import build

STANDING = {"pc", "npc", "faction", "item", "party"}   # link ends a what-if can kill; the build also checks the rest, but they cannot fall


def _plain(s):
    return build.LINK.sub(lambda m: m.group(1), str(s or ""))


def _names(arg):
    return [build.link_name(p.strip()) for p in arg.split("·") if build.link_name(p.strip())]


def collect(site):
    g, nodes, cur = site.g, site.nodes, site.cur
    pcs = sorted((n for n in g["nodes"] if n["type"] == "pc"), key=lambda n: (-int(n.get("importance") or 0), n["id"]))
    pc_ids = [n["id"] for n in pcs]
    plans = {n["id"]: n for n in g["nodes"] if n["type"] == "plan"}
    live = {k: n for k, n in plans.items() if n.get("status") in build.LIVE}

    # strong current ties of each player character (canon or prep, weight 5), for plans that touch a PC only through someone
    ties = {p: {} for p in pc_ids}
    for e in g["edges"]:
        if e.get("origin") not in ("written", "property") or e.get("layer") == "draft":
            continue
        if e.get("end") is not None and e["end"] <= cur:
            continue
        if int(e.get("weight") or 0) < 5:
            continue
        for a, b in ((e["from"], e["to"]), (e["to"], e["from"])):
            if a in ties and b not in pc_ids and b != "The Party" and nodes.get(b, {}).get("type") not in ("place", "plan", "session"):
                ties[a][b] = 5

    data, lanes_of = {}, {}
    for pid, n in live.items():
        reqs, links, _ = build.parse_plan({"text": site.text(pid)})
        req = []
        for k, arg in reqs:
            names = _names(arg)
            req.append({"k": k, "a": names[0] if names else "", "w": [w.strip().lower() for w in (arg.split("·")[1] if "·" in arg else "").split(",") if w.strip()],
                        "t": _plain(arg)})
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
        direct = [p for p in pc_ids if p in named]
        lanes, via = list(direct), {}
        if not lanes:
            best = [(p, t) for p in pc_ids for t in named if t in ties[p]]
            for p, t in best:
                if p not in lanes:
                    lanes.append(p); via[p] = t
        if not lanes:
            lanes = ["The Party"] if "The Party" in named else ["world"]
        lanes_of[pid] = lanes
        sec = dict(build_sections(site.text(pid)))
        data[pid] = {"id": pid, "href": site.slugs.get(pid, "") + ".html", "status": n.get("status"), "target": n.get("target") or "",
                     "summary": _plain(n.get("summary")), "req": req, "via": via,
                     "idea": site.blocks(sec.get("Idea", [])),
                     "links": [f'{l["from"]} · {l["type"]} · {l["to"]}' + (f' ({l["note"]})' if l.get("note") else "") for l in links]}

    facts = {}
    for d in data.values():
        for r in d["req"]:
            a = r["a"]
            if a and a in nodes and a not in facts:
                m = nodes[a]
                facts[a] = {"type": m["type"], "state": str(m.get("state") or "").lower(),
                            "out": bool(build.snum(m.get("revealed") or "") is not None and build.snum(m.get("revealed")) <= cur),
                            "status": str(m.get("status") or "").lower(), "href": site.slugs.get(a, "") + ".html",
                            "summary": _plain(m.get("summary"))}
    return pcs, plans, live, data, lanes_of, facts


def build_sections(text):
    import pages
    return pages.sections(text)


def esc(s):
    return html.escape(str(s or ""))


def plan_node(site, d, lane, cur):
    tgt = d["target"]
    stale = build.snum(tgt) is not None and build.snum(tgt) <= cur
    checks = sum(1 for r in d["req"] if r["k"] == "check")
    badges = [f'<span class="b {esc(d["status"])}">{esc(d["status"])}</span>']
    if tgt:
        badges.append(f'<span class="b tg{" stale" if stale else ""}">{esc(tgt)}{" · stale" if stale else ""}</span>')
    if checks:
        badges.append(f'<span class="b ck" title="judgment calls to make">{checks} check{"s" if checks > 1 else ""}</span>')
    via = d["via"].get(lane)
    return (f'<button class="node plan" data-plan="{esc(d["id"])}" aria-label="{esc(d["id"])}">'
            f'<span class="nt">{esc(d["id"])}</span><span class="badges">{"".join(badges)}</span>'
            f'<span class="ns">{esc(d["summary"])}</span>'
            + (f'<span class="via">through {esc(via)}</span>' if via else "")
            + '<span class="why"></span></button>')


def tree(children):
    if not children:
        return ""
    return '<div class="kids">' + "".join(f'<div class="br">{c}</div>' for c in children) + "</div>"


def lane_html(site, key, title, sub, root_body, pids, data, lanes_of, plans, cur):
    in_lane = set(pids)

    def parent(pid):
        for r in data[pid]["req"]:
            if r["k"] in ("plan", "played") and r["a"] in in_lane and r["a"] != pid:
                return r["a"]
        return None

    kids = {}
    for pid in pids:
        kids.setdefault(parent(pid), []).append(pid)

    order = lambda p: (data[p]["status"] != "ready", not data[p]["target"], str(data[p]["target"]), p)

    def sub_tree(pid, seen=()):
        if pid in seen:
            return plan_node(site, data[pid], key, cur)
        ch = [sub_tree(c, seen + (pid,)) for c in sorted(kids.get(pid, []), key=order)]
        return f'<div class="row">{plan_node(site, data[pid], key, cur)}{tree(ch)}</div>'

    groups, loose = {}, []
    for pid in sorted(kids.get(None, []), key=order):
        h = None
        for r in data[pid]["req"]:
            if r["k"] in ("hidden", "revealed") and r["a"]:
                h = ("secret", r["k"], r["a"]); break
        if not h:
            for r in data[pid]["req"]:
                if r["k"] in ("plan", "played") and r["a"] in plans:
                    h = ("after", r["k"], r["a"]); break
        (groups.setdefault(h, []) if h else loose).append(pid)

    branches = []
    for h in sorted(groups, key=lambda h: (h[0] != "secret", h[2])):
        kind, k, a = h
        fact = site.nodes.get(a, {})
        if kind == "secret":
            lab = "while hidden" if k == "hidden" else "once it is out"
            head = (f'<button class="node hinge" data-secret="{esc(a)}" data-need="{k}" title="What if this comes out?">'
                    f'<span class="hk">Secret · <i>{lab}</i></span><span class="nt">{esc(a)}</span>'
                    f'<span class="ns">{esc(_plain(fact.get("summary")))}</span><span class="flip">What if it comes out?</span></button>')
        else:
            st = plans.get(a, {}).get("status", "")
            played = plans.get(a, {}).get("played") or ""
            where = "" if st != "played" else f" in {played}" if played else ""
            head = (f'<div class="node after"><span class="hk">Follows a plan · {esc(st)}{esc(where)}</span>'
                    f'<a class="nt" href="{esc(site.slugs.get(a, ""))}.html">{esc(a)}</a></div>')
        branches.append(f'<div class="row">{head}{tree([sub_tree(p) for p in groups[h]])}</div>')
    branches += [sub_tree(p) for p in loose]

    count = len(pids)
    empty = "" if pids else '<p class="empty">No live plans yet. Room to write some.</p>'
    return (f'<section class="lane" id="{esc(key if key in ("world",) else site.slugs.get(key, key))}" data-lane="{esc(key)}">'
            f'<h2>{esc(title)} <span>{count} live plan{"" if count == 1 else "s"}</span></h2>'
            f'<div class="scroll"><div class="row top"><div class="node root">{root_body}</div>{tree(branches)}</div></div>{empty}</section>')


def page(site):
    import pages
    cur = site.cur
    pcs, plans, live, data, lanes_of, facts = collect(site)
    lanes = [(p["id"], p) for p in pcs] + [("The Party", site.nodes.get("The Party")), ("world", None)]
    out = [pages.head("Paths ahead", False).replace('<div class="wrap">', '<div class="wrap wide">'), f"<style>{CSS}</style>",
           pages.topbar(site, "Paths ahead"), '<main class="sheet paths">', "<h1>Paths ahead</h1>",
           f'<p class="summary">Every live plan after S{cur}, grown from the player character it concerns. '
           "None of it is canon. Tap a plan for its idea and what it needs; tap a secret, or a need inside a plan, "
           "to try a what-if and see which paths close.</p>",
           '<div class="whatif" id="whatif"><b>What-ifs</b><span id="wi-list" class="muted">none: this is the world as it stands.</span>'
           '<span id="wi-count"></span><button id="wi-reset" hidden>Clear</button></div>',
           '<nav class="jump">']
    for key, n in lanes:
        k = [p for p, ls in lanes_of.items() if key in ls]
        if key == "world" and not k:
            continue
        anchor = "world" if key == "world" else site.slugs.get(key, key)
        label = "Around the party" if key == "world" else key
        out.append(f'<a href="#{esc(anchor)}">{esc(label)} <small>{len(k)}</small></a>')
    out.append("</nav>")
    for key, n in lanes:
        pids = [p for p, ls in lanes_of.items() if key in ls]
        if key == "world":
            if not pids:
                continue
            root = '<span class="hk">The world</span><span class="nt">Around the party</span><span class="ns">Plans that touch no player character directly.</span>'
            out.append(lane_html(site, key, "Around the party", "", root, pids, data, lanes_of, plans, cur)); continue
        if key == "The Party":
            if not pids:
                continue
            root = f'<span class="hk">Together</span><a class="nt" href="{esc(site.slugs.get(key, ""))}.html">The whole party</a><span class="ns">Plans aimed at the party as one.</span>'
            out.append(lane_html(site, key, "The whole party", "", root, pids, data, lanes_of, plans, cur)); continue
        bits = [x for x in (n.get("player") and f"played by {n['player']}", n.get("location") and f"at {_plain(n['location'])}",
                            n.get("state") not in (None, "", "alive") and n["state"]) if x]
        root = (f'<span class="hk">Player character</span><a class="nt" href="{esc(site.slugs.get(key, ""))}.html">{esc(key)}</a>'
                f'<span class="ns">{esc(_plain(n.get("summary")))}</span><span class="meta">{esc(" · ".join(bits))}</span>')
        out.append(lane_html(site, key, key, "", root, pids, data, lanes_of, plans, cur))
    out.append('<aside id="drawer" class="drawer" hidden aria-live="polite"></aside>')
    out.append(f'<footer>Built from the plans in the Ossë vault after S{cur}: {len(live)} live, '
               f'{sum(1 for p in plans.values() if p.get("status") == "pruned")} pruned, '
               f'{sum(1 for p in plans.values() if p.get("status") == "played")} played. '
               "What-ifs here change nothing in the vault; to test one for real, run "
               '<code>build.py --dry --assume</code>. Lanes and branches are worked out by <code>tools/osse/paths.py</code>.</footer>')
    payload = json.dumps({"plans": data, "facts": facts, "gone": sorted(build.GONE)}, ensure_ascii=False).replace("</", "<\\/")
    out.append(f'<script>const PATHS={payload};</script><script>{JS}</script></main></div></body></html>')
    return "".join(out)


CSS = r"""
.wrap.wide{max-width:1500px}
.paths .summary{max-width:780px}
.whatif{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin:14px 0 6px;padding:10px 12px;
  background:var(--vellum);border:1px solid var(--vrule);border-radius:6px;font-size:15px;box-shadow:0 6px 14px rgba(42,29,18,.08)}
.whatif b{font:600 12px var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:var(--vred)}
.whatif .wi{display:inline-flex;align-items:center;gap:6px;padding:3px 4px 3px 10px;border-radius:999px;background:var(--vink);color:var(--vellum);font-size:14px}
.whatif .wi button{border:0;background:rgba(255,255,255,.15);color:inherit;border-radius:999px;width:22px;height:22px;cursor:pointer;font:14px/1 var(--f-body)}
#wi-count{margin-left:auto;font:500 12px var(--f-mono);color:var(--vmuted)}
#wi-reset{font:500 11px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;border:1px solid var(--vrule);background:none;color:var(--vred);border-radius:4px;padding:6px 10px;cursor:pointer}
.lane{margin-top:26px}
.lane .scroll{overflow-x:auto;padding:6px 2px 12px}
.row{display:flex;align-items:center}
.kids{display:flex;flex-direction:column;position:relative;margin-left:26px}
.kids::before{content:"";position:absolute;left:-26px;top:50%;width:26px;border-top:1.5px solid var(--vrule)}
.br{position:relative;padding:5px 0 5px 13px}
.br::before{content:"";position:absolute;left:0;top:50%;width:13px;border-top:1.5px solid var(--vrule)}
.br::after{content:"";position:absolute;left:0;top:0;bottom:0;border-left:1.5px solid var(--vrule)}
.br:first-child::after{top:50%}.br:last-child::after{bottom:50%}.br:only-child::after{display:none}
.node{display:flex;flex-direction:column;gap:3px;width:250px;flex:none;text-align:left;font:15px/1.3 var(--f-body);color:var(--vink);
  background:rgba(255,255,255,.55);border:1px solid var(--vline);border-radius:6px;padding:9px 11px;text-decoration:none}
.node .nt{font-weight:600;font-size:16px;color:var(--vink);text-decoration:none}
a.nt:hover{color:var(--vred)}
.node .ns{font-size:13.5px;color:var(--vmuted);line-height:1.3}
.node .hk{font:500 10.5px var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted)}
.node .meta,.node .via{font:500 11px var(--f-mono);color:var(--vmuted)}
.node.root{width:230px;background:var(--vink);border-color:var(--vink)}
.node.root .nt,.node.root .ns,.node.root .hk,.node.root .meta{color:var(--vellum)}.node.root .ns{opacity:.8}.node.root .hk,.node.root .meta{opacity:.65}
button.node{cursor:pointer}
.node.plan:hover,.node.plan.on{border-color:var(--vred);box-shadow:0 0 0 2px rgba(124,22,34,.15)}
.node.plan.ready{border:2px solid var(--vink)}
.node.hinge{width:220px;border:1.5px dashed var(--vred);background:rgba(124,22,34,.05)}
.node.hinge .hk{color:var(--vred)}.node.hinge .flip{font:500 11px var(--f-mono);color:var(--vred);margin-top:2px}
.node.hinge.out{background:var(--vred);border-style:solid}.node.hinge.out *{color:var(--vellum)!important}
.node.after{width:200px;background:rgba(42,29,18,.05);border-style:dotted}
.badges{display:flex;flex-wrap:wrap;gap:4px}
.b{font:600 10.5px/1.6 var(--f-mono);letter-spacing:.04em;padding:0 6px;border-radius:3px;border:1px solid var(--vline)}
.b.ready{background:var(--vink);color:var(--vellum);border-color:var(--vink)}.b.draft{border-style:dotted;border-color:var(--vred);color:var(--vred)}
.b.tg{color:var(--vink)}.b.stale{background:#b8860b;color:#fff;border-color:#b8860b}.b.ck{border-color:#b8860b;color:#7a5a08}
.node .why{display:none;font:500 11.5px/1.3 var(--f-mono);color:var(--vred)}
.node.cut{opacity:.42;background:repeating-linear-gradient(135deg,transparent 0 8px,rgba(42,29,18,.05) 8px 16px)}
.node.cut .nt{text-decoration:line-through}.node.cut .why{display:block;opacity:1}
.empty{color:var(--vmuted);font-style:italic;margin:4px 0 0}
.drawer{position:fixed;right:16px;top:16px;bottom:16px;width:min(420px,calc(100vw - 32px));overflow:auto;z-index:20;
  background:linear-gradient(180deg,var(--vellum),var(--vellum-2));color:var(--vink);border:1px solid var(--vrule);border-radius:8px;
  padding:18px 20px 24px;box-shadow:0 20px 50px rgba(0,0,0,.45);font-size:16px}
.drawer h3{font-size:22px;margin:0 30px 6px 0}.drawer .x{position:absolute;right:12px;top:10px;border:0;background:none;font-size:26px;cursor:pointer;color:var(--vmuted)}
.drawer h4{margin:16px 0 4px}.drawer ul{padding-left:18px}
.req{list-style:none;padding:0!important;margin:4px 0}
.req li{display:flex;gap:8px;align-items:baseline;padding:5px 0;border-bottom:1px dashed var(--vline)}
.req .ok{font:600 12px var(--f-mono);width:16px;flex:none}.req .ok.y{color:#2f6b3a}.req .ok.n{color:var(--vred)}.req .ok.m{color:#b8860b}
.req .k{font:500 11px var(--f-mono);color:var(--vmuted);flex:none;min-width:58px}.req .imp{opacity:.7}
.req button{margin-left:auto;flex:none;font:500 10.5px var(--f-mono);border:1px solid var(--vrule);background:rgba(255,255,255,.5);color:var(--vred);border-radius:4px;padding:4px 7px;cursor:pointer;white-space:nowrap}
.req button.on{background:var(--vred);color:var(--vellum)}
.drawer .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.drawer .acts a,.drawer .acts button{font:500 11px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;border:1px solid var(--vink);border-radius:4px;padding:8px 10px;color:var(--vink);background:none;cursor:pointer;text-decoration:none}
@media (max-width:640px){.row.top{flex-direction:column;align-items:flex-start}.row.top>.kids{margin:10px 0 0 10px}.row.top>.kids::before{display:none}
  .node.root{width:100%!important}.whatif{position:static}.node{width:210px}.node.hinge{width:190px}.drawer{top:auto;height:70vh;right:8px;left:8px;width:auto;bottom:8px}}
@media print{.whatif,.drawer{display:none}.lane .scroll{overflow:visible}}
"""

JS = r"""(() => {
const P = PATHS.plans, F = PATHS.facts, GONE = new Set(PATHS.gone);
const ov = {out: {}, dead: {}, drop: {}};
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const isOut = a => a in ov.out ? ov.out[a] : !!(F[a] && F[a].out);
const isDead = a => a in ov.dead ? ov.dead[a] : !!(F[a] && GONE.has(F[a].state));
let cut = {};
function test(r) {   // the same rules as build.py's evaluate(), for the kinds a what-if can change
  const a = r.a;
  switch (r.k) {
    case "alive": return !isDead(a);
    case "dead": return isDead(a);
    case "state": return ov.dead[a] ? r.w.some(w => GONE.has(w)) : true;
    case "hidden": return !isOut(a);
    case "revealed": return isOut(a);
    case "plan": case "played": return !(ov.drop[a] || cut[a]);
    default: return true;   // checks and fixed facts: they hold now, or the build would have pruned the plan
  }
}
function why(r) {
  const a = r.a;
  return {alive: `needs ${a} alive`, dead: `needs ${a} dead`, state: `needs ${a} ${r.w.join(" or ")}`, hidden: `needs ${a} hidden`,
    revealed: `needs ${a} out`, plan: `needs plan ${a}`, played: `needs plan ${a} played`}[r.k] || r.t;
}
function run() {
  cut = {};
  for (const id in ov.drop) if (ov.drop[id]) cut[id] = "set aside";
  for (let changed = true; changed;) {
    changed = false;
    for (const id in P) {
      if (cut[id]) continue;
      const bad = P[id].req.find(r => !test(r));
      if (bad) { cut[id] = why(bad); changed = true; }
    }
  }
  $$(".node.plan").forEach(el => {
    const c = cut[el.dataset.plan];
    el.classList.toggle("cut", !!c);
    el.querySelector(".why").textContent = c ? "closes: " + c : "";
  });
  $$(".node.hinge").forEach(el => {
    const o = isOut(el.dataset.secret);
    el.classList.toggle("out", o);
    el.querySelector(".flip").textContent = o ? "What if it stays hidden?" : "What if it comes out?";
  });
  const items = [
    ...Object.keys(ov.out).map(a => [`${a} ${ov.out[a] ? "comes out" : "stays hidden"}`, () => delete ov.out[a]]),
    ...Object.keys(ov.dead).map(a => [`${a} ${ov.dead[a] ? fall(a)[1] : fall(a)[2]}`, () => delete ov.dead[a]]),
    ...Object.keys(ov.drop).map(a => [`set aside: ${a}`, () => delete ov.drop[a]])];
  const list = $("#wi-list");
  list.innerHTML = items.length ? "" : "none: this is the world as it stands.";
  list.classList.toggle("muted", !items.length);
  items.forEach(([t, undo]) => {
    const s = document.createElement("span"); s.className = "wi"; s.innerHTML = `${esc(t)} <button aria-label="Undo">×</button>`;
    s.querySelector("button").onclick = () => { undo(); run(); }; list.append(s);
  });
  const total = Object.keys(P).length, open = total - Object.keys(cut).length;
  $("#wi-count").textContent = `${open} of ${total} plans still possible`;
  $("#wi-reset").hidden = !items.length;
  if (shown) draw(shown);
}
function toggle(r) {
  const a = r.a;
  if (r.k === "hidden" || r.k === "revealed") { const now = !isOut(a); if (now === !!(F[a] && F[a].out)) delete ov.out[a]; else ov.out[a] = now; }
  else if (r.k === "plan" || r.k === "played") { ov.drop[a] ? delete ov.drop[a] : ov.drop[a] = true; }
  else { const now = !isDead(a); if (now === !!(F[a] && GONE.has(F[a].state))) delete ov.dead[a]; else ov.dead[a] = now; }
  run();
}
const fall = a => ({faction: ["it falls", "falls", "stands"], item: ["it is destroyed", "is destroyed", "survives"]})[F[a] && F[a].type] || ["they die", "dies", "lives"];
let shown = null;
function label(r) {
  if (r.k === "hidden" || r.k === "revealed") return isOut(r.a) ? "keep it hidden" : "it comes out";
  if (r.k === "plan" || r.k === "played") return ov.drop[r.a] ? "keep it" : "set it aside";
  return isDead(r.a) ? "undo" : fall(r.a)[0];
}
function draw(id) {
  shown = id; const p = P[id], d = $("#drawer");
  $$(".node.plan").forEach(el => el.classList.toggle("on", el.dataset.plan === id));
  const reqs = p.req.map((r, i) => {
    const ok = r.k === "check" ? ["m", "?"] : test(r) ? ["y", "✓"] : ["n", "✗"];
    const name = r.a && F[r.a] ? `<a href="${esc(F[r.a].href)}">${esc(r.a)}</a>` + esc(r.t.slice(r.a.length)) : esc(r.t);
    const can = ["alive", "dead", "state", "hidden", "revealed", "plan", "played"].includes(r.k) && r.a;
    const on = can && ((r.k === "hidden" || r.k === "revealed") ? r.a in ov.out : (r.k === "plan" || r.k === "played") ? !!ov.drop[r.a] : r.a in ov.dead);
    return `<li class="${r.imp ? "imp" : ""}"><span class="ok ${ok[0]}">${ok[1]}</span><span class="k">${esc(r.imp ? "alive*" : r.k)}</span>` +
      `<span>${name}</span>${can ? `<button data-i="${i}" class="${on ? "on" : ""}">${esc(label(r))}</button>` : ""}</li>`;
  }).join("");
  d.innerHTML = `<button class="x" aria-label="Close">×</button><div class="hk" style="font:500 11px var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted)">` +
    `Plan · ${esc(p.status)}${p.target ? " · aimed at " + esc(p.target) : ""}</div><h3>${esc(id)}</h3><p>${esc(p.summary)}</p>` +
    (cut[id] ? `<p style="color:var(--vred);font-weight:600">Closed by the what-ifs: ${esc(cut[id])}</p>` : "") +
    (p.idea ? `<h4>Idea</h4>${p.idea}` : "") +
    `<h4>Needs</h4><ul class="req">${reqs || "<li>Nothing: it can happen any time.</li>"}</ul>` +
    (p.req.some(r => r.imp) ? `<small>* named in its links, so it needs them standing.</small>` : "") +
    (p.links.length ? `<h4>Would change</h4><ul>${p.links.map(l => `<li>${esc(l)}</li>`).join("")}</ul>` : "") +
    `<div class="acts"><a href="${esc(p.href)}">Open the plan</a><button data-drop>${ov.drop[id] ? "Keep this plan" : "What if I set it aside?"}</button></div>`;
  d.hidden = false;
  d.querySelector(".x").onclick = () => { d.hidden = true; shown = null; $$(".node.plan.on").forEach(el => el.classList.remove("on")); };
  d.querySelectorAll(".req button").forEach(b => b.onclick = () => toggle(p.req[+b.dataset.i]));
  d.querySelector("[data-drop]").onclick = () => { ov.drop[id] ? delete ov.drop[id] : ov.drop[id] = true; run(); };
}
$$(".node.plan").forEach(el => el.onclick = () => draw(el.dataset.plan));
$$(".node.hinge").forEach(el => el.onclick = () => toggle({k: el.dataset.need, a: el.dataset.secret}));
$("#wi-reset").onclick = () => { ov.out = {}; ov.dead = {}; ov.drop = {}; run(); };
document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#drawer").hidden) $("#drawer .x").click(); });
run();
})();
"""
