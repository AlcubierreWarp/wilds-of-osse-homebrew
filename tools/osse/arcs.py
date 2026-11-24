#!/usr/bin/env python3
"""Arc planner (vault/arcs.html): the campaign as a row per arc. Built by pages.py on every build; never edit the page by hand.

Each arc has a name, what it starts on, what it ends on, and what it is about. Its row holds session cards in running order:
a card is either linked to a session (a played one, or one with a tab in the Session planner) or a general idea for a session
not planned yet. Tom drags cards within a row and between rows, edits everything, and adds or deletes arcs and cards.
Unlinked cards are counted on from the last linked one, so each shows about which session it would be.

The arcs are stored as the `arcs` part of the Session planner's store on the Gus relay (paths.json), behind the hub's
game master passcode; the Session planner carries the part without touching it. `python3 tools/osse/paths_sync.py arcs`
prints them. Nothing here is canon or a vault plan: the arcs only frame the sessions.

Run this file on its own to rebuild vault/arcs.html from vault/status.json and the session pages, without the vault."""
import html, json, os, re, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# The first outline, written once into the store when it has no arcs yet. by: "claude" shows "Claude's draft" until Tom changes it.
SEED_ARCS = [
    {"title": "The Champions of Varenthal",
     "starts": "Gabriele wakes in a cell at the Sanctuary in Althon's Gate, sent after Father Barichello.",
     "ends": "The party leaves Althon's Gate: the tournament postponed, alliances uncertain, an emergency growing on the frontier.",
     "about": "Strangers in the capital. The hunt for Barichello opens onto the Pyreborn, the Unbowed and the sabotage of the royal "
              "tournament, and ends in blood at the Aerrowyn gala. Corvane has thrown the Queen out of his house, Grey is running, "
              "and every alliance the party made is in question. The arc closes as word of trouble on the frontier pulls them out of the city.",
     "cards": [{"link": f"S{n}"} for n in range(1, 14)] + [
         {"link": "S14", "title": "The morning after",
          "text": "House Dreveth leaves at mid-morning with Gabriele's invitation. The loyal page and the Queen's order, the hunt for Grey, "
                  "Honey Cruller's demand for a name, and Belaskro telling Corvane about Aldous and Sloane."},
         {"title": "The frontier calls",
          "text": "Word of the emergency on the frontier: mage-turned beasts pushing out of the wilds toward the border towns. "
                  "Who asks the party to go, who goes with them, and what they leave burning in the capital."}]},
    {"title": "The Road to the Front",
     "starts": "Departure from Althon's Gate.",
     "ends": "The party stands at the front, the emergency met, with the way into Seranthis open.",
     "about": "The road out of the capital, through a land the Spellplague still warps. Known roads are thin lines through living "
              "wilderness, and mage-turned beasts are spilling out of the barrens. Dangerous creatures, dangerous magic, and perhaps "
              "the first meeting with the Oss'kai. Belaskro is heading home, toward Shadowvale and the Shadowed Mountains.",
     "cards": [
         {"title": "Leaving the capital",
          "text": "Who travels with the party, and how: Jared Dreveth's road, the promised HMCS Ferdinand, or Marshal orders. The last look back at Althon's Gate."},
         {"title": "The thin roads",
          "text": "The first real taste of the wilds: a Spellplague-twisted creature on the road, and a change circle best gone around."},
         {"title": "The K'Tinga",
          "text": "A K'Tinga scout sees Oss'kai blood in Belaskro before he does. First contact with the Oss'kai, who knew Sloane's blood and her mother."},
         {"title": "Shadowvale",
          "text": "Belaskro's hometown, which Corvane once led. The emergency up close: a border town holding out against mage-turned beasts."},
         {"title": "The front",
          "text": "The emergency at its height. Belaskro's latent Oss'kai magic could wake here. The party finds the trail into Seranthis."}]},
    {"title": "Seranthis and Dreeshen Vale",
     "starts": "The party crosses into Seranthis, with Jared Dreveth's contact at Sundermark's South Gate.",
     "ends": "The party confronts Dreeshen Vale and learns where Father Barichello was taken.",
     "about": "The rival kingdom, where Oss'kai blood is held as a coerced underclass and the noble houses built their walls on the "
              "backs of the poor. The party follows the Unbowed's trail to the man who sold Barichello. Dreeshen is ruthless, principled "
              "and magnetic; the cost of his war is the lever: his mother Lady Vale, the followers he spends as martyrs, and Rosalia, alive.",
     "cards": [
         {"title": "The South Gate",
          "text": "Sundermark. Ask for Shane Dawson. House Dreveth's welcome, in a city that treats Oss'kai blood as property."},
         {"title": "The Vale name",
          "text": "Lady Vale of the King's Council is Dreeshen's mother: the very system he fights. She never sponsored him."},
         {"title": "Dreeshen's people",
          "text": "Interrogate or flip Dreeshen's agents. Show the movement that he spends his own as martyrs."},
         {"title": "Rosalia",
          "text": "Rosalia Whitlock is alive and does not know he still searches for her: a way to defuse Dreeshen without a fight. "
                  "The party may need to learn this before they leave Althon's Gate."},
         {"title": "Confronting Dreeshen",
          "text": "Face to face with Dreeshen Vale. He sold Barichello to a patron he has never met, and what he knows points to the barrens."}]},
    {"title": "The Benefactor and Father Barichello",
     "starts": "The party sets out for the barrens at the edge of the known world, on Barichello's trail.",
     "ends": "At the dark mage's lair: the ritual stopped or the way to Earth opened, and Barichello saved or lost.",
     "about": "The Big Bad. A former Oss'kai Mage Adept, fused with the shadow creatures she was sent to hunt, has been building power "
              "in the barrens. She wants Earth, and Barichello is the living anchor of the ritual that opens the way: he reached for God "
              "and found her. The arc lands hardest on Gabriele, and brings Belaskro to his twin and his mother.",
     "cards": [
         {"title": "Into the barrens",
          "text": "Across the Scoured Lands toward the Benefactor, where magic does not work the way it does at home."},
         {"title": "An offer to rewrite the past",
          "text": "The Benefactor tempts Gabriele with temporal magic: a way home, or a way to undo."},
         {"title": "The truth about Barichello",
          "text": "Gabriele learns Barichello is the anchor of the ritual and opened the door himself. Compromised, his faith still holding, capable of small resistance."},
         {"title": "Sloane",
          "text": "In Oss'kai territory Belaskro finds his twin alive; the sun and moon rings fit together. Later, perhaps, the mother who left him."},
         {"title": "The dark mage's lair",
          "text": "The K'Tinga arrive in force. The last confrontation, with Barichello at the centre of the ritual."}]},
]


def seed():
    order, lst, cards = [], {}, {}
    for i, a in enumerate(SEED_ARCS, 1):
        aid = f"a{i}"; order.append(aid); ids = []
        for j, c in enumerate(a["cards"], 1):
            cid = f"a{i}k{j}"; ids.append(cid)
            cards[cid] = {"title": c.get("title", ""), "text": c.get("text", ""), "link": c.get("link", ""), "by": "claude"}
        lst[aid] = {"title": a["title"], "starts": a["starts"], "ends": a["ends"], "about": a["about"], "cards": ids, "by": "claude"}
    return {"v": 1, "order": order, "list": lst, "cards": cards}


def played_from_site(site):
    out = []
    for n in site.g["nodes"]:
        if n["type"] == "session" and n.get("number") and n.get("status", "played") == "played" and int(n["number"]) <= site.cur:
            out.append({"n": int(n["number"]), "title": re.sub(r"^S\d+\s*-\s*", "", n["id"]), "summary": str(n.get("summary") or ""),
                        "href": site.slugs.get(n["id"], "") + ".html" if n["id"] in site.slugs else ""})
    return sorted(out, key=lambda x: x["n"])


def page(site, played=None):
    import pages
    played = played if played is not None else played_from_site(site)
    payload = {"cur": site.cur, "played": played, "seed": seed()}
    js_data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    head = pages.head("Arc planner", False).replace('<div class="wrap">', '<div class="wrap wide">')
    return (head + f"<style>{CSS}</style>" + pages.topbar(site, here="arcs") +
            '<main class="sheet arcs">'
            '<div class="atop"><div><h1>Arc planner</h1><p class="lede">The campaign, an arc to a row. Drag session cards to reorder them or move them '
            'between arcs. Tap anything to edit it.</p></div>'
            '<div class="tools"><span id="save" class="save"></span><button class="mini" data-act="addarc">+ Arc</button></div></div>'
            '<div class="strip" id="strip" aria-label="The campaign at a glance"></div>'
            '<div class="loose" id="loose" hidden></div>'
            '<div id="rows"></div>'
            '<aside id="drawer" class="drawer" hidden></aside>'
            f'<footer>After S{site.cur}. Nothing here is canon or a vault plan: the arcs frame the sessions, and the Session planner holds what happens in each. '
            'Saved with the Session planner on the relay, behind the hub passcode.</footer>'
            f'<script>const ARCS={js_data};</script><script>{JS}</script></main></div></body></html>')


CSS = r"""
.wrap.wide{max-width:none}
.arcs{padding:clamp(14px,2.4vw,26px)}
.atop{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 22px}
.atop h1{margin:0}.lede{margin:4px 0 0;color:var(--vmuted);font-size:15px;max-width:640px}
.tools{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.mini{font:500 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--vrule);background:rgba(255,255,255,.45);color:var(--vred);border-radius:4px;padding:9px 11px;cursor:pointer;min-height:36px}
.mini:hover{background:#fff}.mini.solid{background:var(--vink);color:var(--vellum);border-color:var(--vink)}.mini.solid:hover{background:#000}
.mini.warn{color:var(--vred);border-color:var(--vred)}.mini:disabled{opacity:.4;cursor:default}
.save{font:500 11.5px var(--f-mono);color:var(--vmuted);max-width:420px}.save.bad{color:var(--vred)}

/* the campaign at a glance */
.strip{display:flex;gap:3px;margin:18px 0 6px;position:relative;padding-top:22px}
.seg{flex:var(--w) 1 0;min-width:54px;border:0;padding:0;background:none;cursor:pointer;text-align:left;font:inherit;color:inherit;overflow:hidden}
.seg .bar{display:flex;height:16px;border-radius:3px;overflow:hidden;background:color-mix(in srgb,var(--c) 22%,#f6eed8);border:1px solid color-mix(in srgb,var(--c) 55%,transparent)}
.seg .bar i{flex:var(--p) 1 0;background:var(--c)}.seg .bar b{flex:var(--q) 1 0}
.seg .nm{display:block;font:600 12.5px/1.2 var(--f-display);letter-spacing:.04em;color:var(--c);margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.seg .rg{display:block;font:500 10.5px var(--f-mono);color:var(--vmuted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.seg:hover .bar{box-shadow:0 0 0 2px color-mix(in srgb,var(--c) 40%,transparent)}
.now{position:absolute;top:0;transform:translateX(-50%);font:600 10px/1 var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--vred);white-space:nowrap;pointer-events:none}
.now::after{content:"";position:absolute;left:50%;top:13px;width:2px;height:24px;margin-left:-1px;background:var(--vred)}
.loose{margin:12px 0 0;padding:10px 12px;border:1px dashed var(--vred);border-radius:6px;font-size:14.5px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}

/* rows */
#rows{display:flex;flex-direction:column;gap:16px;margin-top:20px}
.arc{display:grid;grid-template-columns:270px minmax(0,1fr);border:1px solid var(--vline);border-left:6px solid var(--c);border-radius:8px;background:rgba(255,255,255,.28);scroll-margin-top:12px}
.ahead{padding:14px 16px;border-right:1px solid var(--vline);cursor:pointer;display:flex;flex-direction:column;gap:6px;min-width:0}
.ahead:hover{background:rgba(255,255,255,.35)}
.ahead .no{font:600 10.5px var(--f-mono);letter-spacing:.18em;text-transform:uppercase;color:var(--c);display:flex;justify-content:space-between;gap:8px}
.ahead h2{margin:0;font:600 19px/1.2 var(--f-display);color:var(--vink)}
.ahead .ab{font-size:14px;line-height:1.45;color:var(--vmuted);display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden}
.ahead .ab:empty::before{content:"No description yet. Tap to add one.";font-style:italic}
.ahead .rg{font:500 11px var(--f-mono);color:var(--vink);margin-top:auto}
.lane{display:flex;align-items:stretch;gap:10px;overflow-x:auto;padding:14px;min-height:170px;scroll-padding:0 190px;overscroll-behavior-x:contain}
.lane.over{background:color-mix(in srgb,var(--c) 8%,transparent)}
.gate{flex:none;width:170px;display:flex;flex-direction:column;justify-content:flex-start;gap:5px;padding:10px 12px;border-radius:6px;border:2px solid var(--c);
  background:color-mix(in srgb,var(--c) 10%,#fbf5e6);cursor:pointer;font:14px/1.4 var(--f-body);text-align:left;color:var(--vink);position:sticky;z-index:2}
.gate.start{left:0;box-shadow:8px 0 10px -6px rgba(42,29,18,.25)}.gate.end{right:0;margin-left:auto;box-shadow:-8px 0 10px -6px rgba(42,29,18,.25)}
.gate .k{font:600 10px var(--f-mono);letter-spacing:.16em;text-transform:uppercase;color:var(--c);display:flex;align-items:center;gap:6px}
.gate.end{border-style:double;border-width:4px;background:color-mix(in srgb,var(--c) 14%,#fbf5e6)}.gate.start{background:color-mix(in srgb,var(--c) 14%,#fbf5e6)}
.gate .t:empty::before{content:"Not set yet. Tap to set it.";font-style:italic;color:var(--vmuted)}
.gate:hover{box-shadow:0 0 0 2px color-mix(in srgb,var(--c) 35%,transparent)}
.card{flex:none;width:210px;display:flex;flex-direction:column;gap:5px;padding:9px 11px 10px;border-radius:6px;background:#fbf5e6;border:1px solid var(--vline);
  border-top:4px solid var(--c);box-shadow:0 2px 6px rgba(42,29,18,.12);cursor:grab;user-select:none;-webkit-user-select:none;touch-action:pan-x pan-y;position:relative}
.card:hover{box-shadow:0 0 0 2px rgba(124,22,34,.3),0 4px 12px rgba(42,29,18,.18)}
.card .k{font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vmuted);display:flex;justify-content:space-between;gap:6px}
.card .t{font-weight:600;font-size:15.5px;line-height:1.25;color:var(--vink)}
.card .s{font-size:13px;line-height:1.4;color:var(--vmuted);display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden}
.card .chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:auto;padding-top:2px}
.ch{font:500 10.5px/1.6 var(--f-mono);padding:0 6px;border-radius:3px;border:1px solid var(--vline);background:rgba(255,255,255,.6);white-space:nowrap}
.ch.dr{border:1px dashed var(--vred);color:var(--vred)}.ch.bad{background:var(--vred);color:var(--vellum);border-color:var(--vred)}
.card.played{width:160px;background:color-mix(in srgb,var(--c) 7%,#f3ead3);border-top-width:0;border-left:4px solid var(--c)}
.card.played .t{font-size:14.5px}.card.played .s{-webkit-line-clamp:4;font-size:12.5px}
.card.played .k b{color:var(--c)}
.card.planned{border-top-style:solid}.card.planned .k b{color:#3d5a80}
.card.idea{border-top-style:dashed;background:#fdf9ef}
.card.drag{opacity:.35}
.ghost{position:fixed;z-index:50;pointer-events:none;transform:rotate(2deg);box-shadow:0 14px 30px rgba(42,29,18,.35)!important;opacity:.95}
.ph{flex:none;width:8px;border-radius:4px;background:var(--vred);opacity:.7;margin:0 -4px}
.fold{flex:none;width:150px;display:flex;flex-direction:column;justify-content:center;gap:4px;padding:10px 12px;border-radius:6px;cursor:pointer;
  border:1px solid color-mix(in srgb,var(--c) 45%,transparent);background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--c) 12%,#f3ead3) 0 8px,color-mix(in srgb,var(--c) 6%,#f3ead3) 8px 16px);font-size:13.5px;color:var(--vink);text-align:left;font-family:inherit}
.fold b{font:600 15px var(--f-display);color:var(--c)}.fold .muted{font:500 10.5px var(--f-mono);color:var(--vmuted)}.fold:hover{box-shadow:0 0 0 2px color-mix(in srgb,var(--c) 35%,transparent)}
.fold.open{width:auto;flex-direction:row;align-items:center;padding:8px;writing-mode:vertical-rl;font:500 10.5px var(--f-mono);letter-spacing:.12em;text-transform:uppercase}
.add{flex:none;width:120px;border:1px dashed var(--vrule);border-radius:6px;background:none;color:var(--vred);font:500 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
.add:hover{background:rgba(255,255,255,.5)}
.empty{align-self:center;font-style:italic;color:var(--vmuted);font-size:14px;padding:0 6px}

/* editor */
.drawer{position:fixed;right:0;top:0;bottom:0;width:min(440px,100%);z-index:40;overflow:auto;background:#fbf5e6;color:var(--vink);border-left:1px solid var(--vrule);
  box-shadow:-12px 0 30px rgba(0,0,0,.35);padding:18px 20px 30px;font-size:15.5px}
.drawer h3{margin:0 30px 4px 0;font:600 19px/1.25 var(--f-display)}
.drawer .x{position:absolute;right:10px;top:6px;border:0;background:none;font-size:28px;cursor:pointer;color:var(--vmuted);width:44px;height:44px}
.drawer label{display:block;font:500 10.5px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--vmuted);margin:14px 0 4px}
.drawer input,.drawer textarea,.drawer select{width:100%;font:16px/1.4 var(--f-body);color:var(--vink);background:#fff;border:1px solid var(--vrule);border-radius:5px;padding:9px 10px}
.drawer textarea{min-height:110px;resize:vertical}
.drawer .row{display:flex;flex-wrap:wrap;gap:6px;margin-top:16px}
.drawer .note{font-size:14px;color:var(--vmuted);margin:8px 0 0}
.drawer .info{margin-top:10px;padding:9px 11px;border-radius:6px;background:rgba(61,90,128,.08);border:1px solid rgba(61,90,128,.25);font-size:14px}
.drawer .info ol{margin:6px 0 0;padding-left:20px}
footer{margin-top:22px;font-size:13.5px;color:var(--vmuted)}
@media (max-width:760px){
  .seg .nm span,.seg .rg{display:none}.seg{min-width:0}
  .arc{grid-template-columns:1fr}.ahead{border-right:0;border-bottom:1px solid var(--vline)}.ahead .ab{-webkit-line-clamp:3}
  .lane{padding:12px;scroll-padding:12px}.gate{width:150px;position:static;box-shadow:none!important}.card{width:190px}
  .drawer{top:auto;max-height:88vh;border-left:0;border-top:1px solid var(--vrule);border-radius:12px 12px 0 0;box-shadow:0 -12px 30px rgba(0,0,0,.35)}
}
@media print{.tools,.drawer,.add{display:none}.lane{flex-wrap:wrap;overflow:visible}}
"""

JS = r"""(() => {
const D = ARCS, CUR = D.cur, PLAYED = new Map(D.played.map(s => [s.n, s]));
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} }};
const RELAY = (location.hostname === "localhost" && new URLSearchParams(location.search).get("relay"))
  || "https://2srnsytz3rqi3jke23bz643jhq0irvei.lambda-url.ca-central-1.on.aws";
const KEY = store.get("osse-hub-dm");
const COLOURS = ["#7c1622", "#3f5a3c", "#3d5a80", "#8a5a12", "#5b3f6b", "#2f6b6b"];
const copyOf = x => JSON.parse(JSON.stringify(x));
let A = copyOf(D.seed), planner = {sessions: [], order: {}, cards: {}}, open = null;
const folded = (() => { try { return JSON.parse(store.get("osse-arcs-open") || "{}"); } catch (e) { return {}; } })();
const num = l => { const m = /^S(\d+)$/.exec(l || ""); return m ? +m[1] : 0; };
const uid = p => p + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

/* ---------- what each card is ---------- */
function walk() {   // each card's session number: its link, or one on from the card before it
  let prev = 0; const out = {};
  for (const aid of A.order) for (const cid of A.list[aid].cards) {
    const c = A.cards[cid]; if (!c) continue;
    const n = num(c.link), est = n || prev + 1;
    out[cid] = {n: est, linked: !!n, back: !!n && n <= prev};
    prev = Math.max(prev, est);
  }
  return out;
}
const state = c => { const n = num(c.link); return n && n <= CUR && PLAYED.has(n) ? "played" : n ? "planned" : "idea"; };
const titleOf = c => c.title || (PLAYED.get(num(c.link)) || {}).title || (c.link ? "Session " + c.link.slice(1) : "Untitled session");
const textOf = c => c.text || (state(c) === "played" ? (PLAYED.get(num(c.link)) || {}).summary || "" : "");
function scenes(link) {   // the running order the Session planner holds for a session
  return (planner.order[link] || []).map(id => id.startsWith("p:") ? id.slice(2) : ((planner.cards[id.slice(2)] || {}).title || "Untitled scene"));
}
function range(aid, w) {
  const ns = A.list[aid].cards.map(c => w[c] && w[c].n).filter(Boolean);
  if (!ns.length) return "";
  const lo = Math.min(...ns), hi = Math.max(...ns), est = A.list[aid].cards.some(c => w[c] && !w[c].linked);
  return lo === hi ? `S${lo}` : `S${lo} to ${est ? "about " : ""}S${hi}`;
}

/* ---------- drawing ---------- */
function draw() {
  const w = walk(), rows = $("#rows");
  rows.innerHTML = A.order.map((aid, i) => {
    const a = A.list[aid], col = COLOURS[i % COLOURS.length], cards = a.cards.filter(c => A.cards[c]);
    const played = cards.filter(c => state(A.cards[c]) === "played"), fold = played.length >= 4 && !folded[aid];
    let lane = `<button class="gate start" data-gate="starts" data-arc="${aid}"><span class="k">▶ Starts</span><span class="t">${esc(a.starts)}</span></button>`;
    if (fold) lane += `<button class="fold" data-fold="${aid}" title="Show the played sessions"><b>S${w[played[0]].n} to S${w[played[played.length - 1]].n}</b>${played.length} played sessions<span class="muted">Tap to show them</span></button>`;
    else if (played.length >= 4) lane += `<button class="fold open" data-fold="${aid}" title="Fold the played sessions">Fold played</button>`;
    lane += cards.filter(c => !(fold && played.includes(c))).map(c => cardHtml(c, w[c])).join("");
    if (!cards.length) lane += `<span class="empty">No sessions yet.</span>`;
    lane += `<button class="add" data-add="${aid}">+ Session</button>`;
    lane += `<button class="gate end" data-gate="ends" data-arc="${aid}"><span class="k">■ Ends</span><span class="t">${esc(a.ends)}</span></button>`;
    return `<section class="arc" id="arc-${aid}" style="--c:${col}" data-arc="${aid}">` +
      `<div class="ahead" data-edit-arc="${aid}"><div class="no"><span>Arc ${i + 1}</span>${a.by === "claude" ? `<span class="ch dr">Claude's draft</span>` : ""}</div>` +
      `<h2>${esc(a.title || "Untitled arc")}</h2><div class="ab">${esc(a.about)}</div>` +
      `<div class="rg">${esc(range(aid, w))}${cards.length ? ` · ${cards.length} session${cards.length === 1 ? "" : "s"}` : ""}</div></div>` +
      `<div class="lane" data-lane="${aid}">${lane}</div></section>`;
  }).join("") || `<p class="empty">No arcs yet. Add one with + Arc.</p>`;
  strip(w); loose(); wire();
  if (open) editor(open, true);
}
function cardHtml(cid, w) {
  const c = A.cards[cid], st = state(c);
  const label = st === "played" ? `<b>S${w.n}</b> · played` : st === "planned" ? `<b>S${w.n}</b> · planned` : `about S${w.n} · idea`;
  const sc = st === "planned" ? scenes(c.link) : [];
  return `<div class="card ${st}" data-card="${cid}" tabindex="0" role="button" aria-label="${esc(titleOf(c))}"><div class="k"><span>${label}</span></div>` +
    `<div class="t">${esc(titleOf(c))}</div><div class="s">${esc(textOf(c))}</div>` +
    `<div class="chips">${sc.length ? `<span class="ch">${sc.length} scene${sc.length === 1 ? "" : "s"} planned</span>` : ""}` +
    `${w.back ? `<span class="ch bad" title="This session comes before a card to its left">out of order</span>` : ""}` +
    `${c.by === "claude" && st !== "played" ? `<span class="ch dr">Claude's draft</span>` : ""}</div></div>`;
}
function strip(w) {
  const segs = A.order.map((aid, i) => {
    const cards = A.list[aid].cards.filter(c => A.cards[c]), p = cards.filter(c => state(A.cards[c]) === "played").length;
    return {aid, i, n: Math.max(cards.length, 1), p, rg: range(aid, w), t: A.list[aid].title || "Untitled arc"};
  });
  const total = segs.reduce((s, x) => s + x.n, 0);
  $("#strip").innerHTML = segs.map(s => `<button class="seg" data-go="${s.aid}" style="--w:${s.n};--p:${s.p};--q:${s.n - s.p};--c:${COLOURS[s.i % COLOURS.length]}" title="${esc(s.t)}">` +
    `<span class="bar"><i></i><b></b></span><span class="nm">${s.i + 1}<span>. ${esc(s.t)}</span></span><span class="rg">${esc(s.rg)}</span></button>`).join("") +
    `<span class="now" id="now">Now · after S${CUR}</span>`;
  requestAnimationFrame(() => {   // the marker sits at the end of the last played session's slot
    const now = $("#now"), box = $("#strip").getBoundingClientRect(); now.style.left = "0px";
    for (const s of segs) { const el = s.p && $(`.seg[data-go="${s.aid}"] .bar`); if (el) { const r = el.getBoundingClientRect(); now.style.left = (r.left - box.left + r.width * s.p / s.n) + "px"; } }
  });
}
function loose() {   // played sessions no card is linked to
  const used = new Set(Object.values(A.cards).map(c => c.link)), miss = D.played.filter(s => !used.has("S" + s.n));
  const el = $("#loose"); el.hidden = !miss.length || !A.order.length;
  el.innerHTML = miss.length ? `<b>Played, not in an arc:</b> ` + miss.map(s => `<button class="mini" data-place="${s.n}">+ S${s.n} ${esc(s.title)}</button>`).join("") : "";
}

/* ---------- editing ---------- */
function touch(o) { if (o.by === "claude") o.by = "tom"; }
function editor(which, keep) {
  open = which; const d = $("#drawer"); d.hidden = false;
  if (which.arc) {
    const a = A.list[which.arc]; if (!a) return closeEd();
    const i = A.order.indexOf(which.arc);
    if (keep && d.dataset.for === "arc:" + which.arc) return;
    d.dataset.for = "arc:" + which.arc;
    d.innerHTML = `<button class="x" data-close aria-label="Close">×</button><h3>Arc ${i + 1}</h3>` +
      `<label for="f-title">Name</label><input id="f-title" data-f="title" value="${esc(a.title)}">` +
      `<label for="f-starts">Starts on</label><textarea id="f-starts" data-f="starts" style="min-height:70px" placeholder="e.g. departure from Althon's Gate">${esc(a.starts)}</textarea>` +
      `<label for="f-ends">Ends on</label><textarea id="f-ends" data-f="ends" style="min-height:70px" placeholder="e.g. confronting Dreeshen">${esc(a.ends)}</textarea>` +
      `<label for="f-about">What the arc is about</label><textarea id="f-about" data-f="about" style="min-height:160px">${esc(a.about)}</textarea>` +
      `<div class="row"><button class="mini" data-arcmove="-1" ${i ? "" : "disabled"}>↑ Move up</button><button class="mini" data-arcmove="1" ${i < A.order.length - 1 ? "" : "disabled"}>↓ Move down</button>` +
      `<button class="mini warn" data-delarc>Delete arc</button><button class="mini solid" data-close>Done</button></div>` +
      (a.by === "claude" ? `<p class="note">Claude's draft until you change it.</p>` : "");
    if (which.focus) setTimeout(() => { const f = d.querySelector(`[data-f="${which.focus}"]`); if (f) { f.focus(); f.setSelectionRange(f.value.length, f.value.length); } }, 30);
    return;
  }
  const cid = which.card, c = A.cards[cid]; if (!c) return closeEd();
  const aid = A.order.find(x => A.list[x].cards.includes(cid)), arr = A.list[aid].cards, pos = arr.indexOf(cid), st = state(c), w = walk()[cid] || {};
  if (keep && d.dataset.for === "card:" + cid) { info(c); return; }
  d.dataset.for = "card:" + cid;
  const taken = new Map(Object.entries(A.cards).filter(([k, x]) => k !== cid && x.link).map(([k, x]) => [x.link, k]));
  const future = [...new Set(planner.sessions.filter(t => num(t) > CUR).concat(Array.from({length: 16}, (_, k) => "S" + (CUR + 1 + k))))].sort((x, y) => num(x) - num(y));
  const opt = (v, t) => `<option value="${v}" ${c.link === v ? "selected" : ""} ${taken.has(v) ? "disabled" : ""}>${esc(t)}${taken.has(v) ? " (on another card)" : ""}</option>`;
  d.innerHTML = `<button class="x" data-close aria-label="Close">×</button><h3>${st === "played" ? "Played session" : st === "planned" ? "Planned session" : "Session idea"}</h3>` +
    `<label for="f-link">Session</label><select id="f-link" data-f="link"><option value="" ${c.link ? "" : "selected"}>Not linked yet (about S${w.n || CUR + 1})</option>` +
    `<optgroup label="Coming up">${future.map(t => opt(t, t + (planner.sessions.includes(t) ? " · in the Session planner" : ""))).join("")}</optgroup>` +
    `<optgroup label="Played">${D.played.slice().reverse().map(s => opt("S" + s.n, `S${s.n} · ${s.title}`)).join("")}</optgroup></select>` +
    `<label for="f-title">Name</label><input id="f-title" data-f="title" value="${esc(c.title)}" placeholder="${esc(titleOf({link: c.link}))}">` +
    `<label for="f-text">What happens</label><textarea id="f-text" data-f="text" placeholder="${esc(st === "played" ? textOf({link: c.link}) : "A line or two: where it goes, what it is for")}">${esc(c.text)}</textarea>` +
    `<div id="info"></div>` +
    `<label for="f-arc">Arc</label><select id="f-arc" data-movearc>${A.order.map((x, i) => `<option value="${x}" ${x === aid ? "selected" : ""}>Arc ${i + 1}: ${esc(A.list[x].title || "Untitled arc")}</option>`).join("")}</select>` +
    `<div class="row"><button class="mini" data-cardmove="-1" ${pos ? "" : "disabled"}>← Earlier</button><button class="mini" data-cardmove="1" ${pos < arr.length - 1 ? "" : "disabled"}>Later →</button>` +
    `<button class="mini warn" data-delcard>Delete</button><button class="mini solid" data-close>Done</button></div>` +
    (c.by === "claude" ? `<p class="note">Claude's draft until you change it.</p>` : "");
  info(c);
  if (which.focus) setTimeout(() => { const f = d.querySelector(`[data-f="${which.focus}"]`); if (f) f.focus(); }, 30);
}
function info(c) {
  const el = $("#info"); if (!el) return;
  const n = num(c.link), s = PLAYED.get(n), st = state(c);
  if (st === "played") el.innerHTML = `<div class="info"><b>S${n} · ${esc(s.title)}</b><br>${esc(s.summary)}${s.href ? `<br><a href="${esc(s.href)}">Open the session page</a>` : ""}</div>`;
  else if (st === "planned") { const sc = scenes(c.link); el.innerHTML = `<div class="info">${sc.length ? `<b>In the Session planner for ${c.link}:</b><ol>${sc.map(x => `<li>${esc(x)}</li>`).join("")}</ol>` : `Nothing in the Session planner's running order for ${c.link} yet.`}<br><a href="paths.html#%40session">Open the Session planner</a></div>`; }
  else el.innerHTML = "";
}
function closeEd() { open = null; const d = $("#drawer"); d.hidden = true; d.dataset.for = ""; }
const arcOf = cid => A.order.find(x => A.list[x].cards.includes(cid));
function moveCard(cid, toArc, before) {   // before: a card id, or null for the end
  const from = arcOf(cid); if (!from) return;
  A.list[from].cards = A.list[from].cards.filter(x => x !== cid);
  const arr = A.list[toArc].cards, at = before ? arr.indexOf(before) : -1;
  if (at < 0) arr.push(cid); else arr.splice(at, 0, cid);
}
function addCard(aid, link) {
  const cid = uid("k"); A.cards[cid] = {title: "", text: "", link: link || ""};
  const arr = A.list[aid].cards, n = num(link);
  let at = arr.length;   // a played session goes in after the last card linked to an earlier session
  if (n) { const i = arr.map(x => num((A.cards[x] || {}).link)).reduce((b, m, k) => m && m < n ? k : b, -1); at = i + 1; }
  arr.splice(at, 0, cid);
  return cid;
}
document.addEventListener("input", e => {
  const f = e.target.dataset.f; if (!f || !open) return;
  const o = open.arc ? A.list[open.arc] : A.cards[open.card]; if (!o) return;
  o[f] = e.target.value; touch(o);
  if (f === "link") { $("#drawer").dataset.for = ""; editor(open); }
  changed(); redraw();
});
let rtimer = null; const redraw = () => { clearTimeout(rtimer); rtimer = setTimeout(() => { const y = scrollY, xs = $$(".lane").map(l => l.scrollLeft); draw(); $$(".lane").forEach((l, i) => l.scrollLeft = xs[i] || 0); scrollTo(0, y); }, 150); };
document.addEventListener("change", e => {
  if (e.target.matches("[data-movearc]") && open && open.card) { moveCard(open.card, e.target.value, null); touch(A.cards[open.card]); $("#drawer").dataset.for = ""; changed(); draw(); }
});
document.addEventListener("click", e => {
  const t = e.target.closest("button,[data-edit-arc],[data-card]"); if (!t) return;
  if (t.matches("[data-close]")) return closeEd();
  if (t.dataset.act === "addarc") { const aid = uid("a"); A.order.push(aid); A.list[aid] = {title: "", starts: "", ends: "", about: "", cards: []}; changed(); draw(); editor({arc: aid, focus: "title"}); document.getElementById("arc-" + aid).scrollIntoView({behavior: "smooth", block: "center"}); return; }
  if (t.dataset.go) { document.getElementById("arc-" + t.dataset.go).scrollIntoView({behavior: "smooth", block: "start"}); return; }
  if (t.dataset.fold) { folded[t.dataset.fold] = !folded[t.dataset.fold]; store.set("osse-arcs-open", JSON.stringify(folded)); draw(); return; }
  if (t.dataset.add) { const cid = addCard(t.dataset.add); changed(); draw(); editor({card: cid, focus: "title"}); const el = $(`[data-card="${cid}"]`); if (el) el.scrollIntoView({behavior: "smooth", inline: "nearest", block: "nearest"}); return; }
  if (t.dataset.place) { const n = +t.dataset.place, prevArc = A.order.slice().reverse().find(x => A.list[x].cards.some(c => A.cards[c] && num(A.cards[c].link) && num(A.cards[c].link) < n)) || A.order[0]; addCard(prevArc, "S" + n); changed(); draw(); return; }
  if (t.dataset.gate) return editor({arc: t.dataset.arc, focus: t.dataset.gate});
  if (t.dataset.editArc) return editor({arc: t.dataset.editArc});
  if (t.dataset.card) { if (dragged) return; return editor({card: t.dataset.card}); }
  if (t.dataset.arcmove && open && open.arc) { const i = A.order.indexOf(open.arc), j = i + +t.dataset.arcmove; [A.order[i], A.order[j]] = [A.order[j], A.order[i]]; $("#drawer").dataset.for = ""; changed(); draw(); return; }
  if (t.dataset.cardmove && open && open.card) { const aid = arcOf(open.card), arr = A.list[aid].cards, i = arr.indexOf(open.card), j = i + +t.dataset.cardmove; [arr[i], arr[j]] = [arr[j], arr[i]]; touch(A.cards[open.card]); $("#drawer").dataset.for = ""; changed(); draw(); return; }
  if (t.matches("[data-delcard]") && open && open.card) { const cid = open.card, aid = arcOf(cid); if (!confirm(`Delete “${titleOf(A.cards[cid])}”?`)) return; A.list[aid].cards = A.list[aid].cards.filter(x => x !== cid); delete A.cards[cid]; closeEd(); changed(); draw(); return; }
  if (t.matches("[data-delarc]") && open && open.arc) {
    const aid = open.arc, a = A.list[aid], n = a.cards.length;
    if (!confirm(n ? `Delete “${a.title || "this arc"}” and its ${n} session card${n === 1 ? "" : "s"}?` : `Delete “${a.title || "this arc"}”?`)) return;
    a.cards.forEach(c => delete A.cards[c]); delete A.list[aid]; A.order = A.order.filter(x => x !== aid); closeEd(); changed(); draw(); return;
  }
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("#drawer").hidden) closeEd();
  if ((e.key === "Enter" || e.key === " ") && e.target.matches(".card")) { e.preventDefault(); editor({card: e.target.dataset.card}); }
});

/* ---------- dragging cards: within a row and between rows; works with a finger ---------- */
let drag = null, dragged = false;
function wire() {
  $$(".card").forEach(el => el.onpointerdown = ev => {
    if (ev.button > 0) return;
    drag = {cid: el.dataset.card, el, x: ev.clientX, y: ev.clientY, on: false, id: ev.pointerId, timer: null, touch: ev.pointerType === "touch"};
    dragged = false;
    if (drag.touch) drag.timer = setTimeout(() => { if (drag && !drag.on) begin(ev.clientX, ev.clientY); }, 350);   // a finger holds to pick a card up, so a swipe still scrolls the row
  });
}
function begin(x, y) {
  const el = drag.el, r = el.getBoundingClientRect(), g = el.cloneNode(true);
  g.classList.add("ghost"); g.style.width = r.width + "px"; g.style.left = r.left + "px"; g.style.top = r.top + "px"; document.body.appendChild(g);
  drag.on = true; drag.g = g; drag.dx = x - r.left; drag.dy = y - r.top; el.classList.add("drag");
  drag.ph = document.createElement("div"); drag.ph.className = "ph"; el.after(drag.ph);
  try { el.setPointerCapture(drag.id); } catch (e) {}
  if (navigator.vibrate && drag.touch) navigator.vibrate(10);
}
function place(x, y) {
  const lane = document.elementsFromPoint(x, y).map(n => n.closest && n.closest(".lane")).find(Boolean);
  $$(".lane.over").forEach(l => l.classList.remove("over"));
  if (!lane) return;
  lane.classList.add("over");
  const cards = [...lane.querySelectorAll(".card:not(.drag)")];
  const next = cards.find(c => { const r = c.getBoundingClientRect(); return x < r.left + r.width / 2; });
  if (next) next.before(drag.ph); else lane.querySelector(".add").before(drag.ph);
  drag.lane = lane.dataset.lane; drag.before = next ? next.dataset.card : null;
  const r = lane.getBoundingClientRect();   // near an edge, the row scrolls
  drag.scroll = x < r.left + 40 ? -14 : x > r.right - 40 ? 14 : 0; drag.laneEl = lane;
}
function tick() {
  if (!drag || !drag.on) return;
  if (drag.scroll && drag.laneEl) drag.laneEl.scrollLeft += drag.scroll;
  if (drag.lastY < 50) scrollBy(0, -12); else if (drag.lastY > innerHeight - 50) scrollBy(0, 12);
  requestAnimationFrame(tick);
}
addEventListener("pointermove", ev => {
  if (!drag || ev.pointerId !== drag.id) return;
  const far = Math.hypot(ev.clientX - drag.x, ev.clientY - drag.y) > 6;
  if (!drag.on) { if (!far) return; if (drag.touch) { clearTimeout(drag.timer); drag = null; return; } begin(ev.clientX, ev.clientY); requestAnimationFrame(tick); }
  if (drag.touch && !drag.ticking) { drag.ticking = true; requestAnimationFrame(tick); }
  ev.preventDefault();
  drag.g.style.left = (ev.clientX - drag.dx) + "px"; drag.g.style.top = (ev.clientY - drag.dy) + "px"; drag.lastY = ev.clientY;
  place(ev.clientX, ev.clientY);
}, {passive: false});
addEventListener("touchmove", ev => { if (drag && drag.on) ev.preventDefault(); }, {passive: false});
function end(ok) {
  if (!drag) return;
  clearTimeout(drag.timer);
  const d = drag; drag = null;
  if (!d.on) return;
  dragged = true; setTimeout(() => { dragged = false; }, 50);
  d.g.remove(); d.el.classList.remove("drag"); $$(".lane.over").forEach(l => l.classList.remove("over"));
  if (ok && d.lane && d.before !== d.cid) { moveCard(d.cid, d.lane, d.before); touch(A.cards[d.cid]); changed(); }
  const xs = $$(".lane").map(l => l.scrollLeft); draw(); $$(".lane").forEach((l, i) => l.scrollLeft = xs[i] || 0);
}
addEventListener("pointerup", ev => { if (drag && ev.pointerId === drag.id) end(true); });
addEventListener("pointercancel", ev => { if (drag && ev.pointerId === drag.id) end(false); });
addEventListener("contextmenu", ev => { if (drag) ev.preventDefault(); });

/* ---------- saving: the `arcs` part of the Session planner's store. Every save reads first and merges what changed
   elsewhere with what changed here (here wins on the same thing), then sends the whole store back with only `arcs` changed. ---------- */
const isMap = x => !!x && typeof x === "object" && !Array.isArray(x);
const canon = x => JSON.stringify(x, (k, v) => isMap(v) ? Object.fromEntries(Object.keys(v).sort().map(q => [q, v[q]])) : v) ?? "";
const same = (a, b) => canon(a) === canon(b);
function merge3(b, m, t) {
  if (same(m, b)) return t;
  if (same(t, b) || same(m, t)) return m;
  if (isMap(m) && isMap(t)) { const o = {}; for (const k of new Set([...Object.keys(m), ...Object.keys(t)])) { const v = merge3(isMap(b) ? b[k] : undefined, m[k], t[k]); if (v !== undefined) o[k] = v; } return o; }
  return Array.isArray(m) && Array.isArray(t) ? m.concat(t.filter(x => !m.some(y => same(x, y)) && !(Array.isArray(b) && b.some(y => same(x, y))))) : m;
}
function tidy() {   // after a merge: every card in exactly one arc, no arc without its record
  A.order = [...new Set(A.order.filter(a => A.list[a]))];
  Object.keys(A.list).forEach(a => { if (!A.order.includes(a)) A.order.push(a); });
  const seen = new Set();
  A.order.forEach(a => { A.list[a].cards = A.list[a].cards.filter(c => A.cards[c] && !seen.has(c) && seen.add(c)); });
  Object.keys(A.cards).forEach(c => { if (!seen.has(c)) delete A.cards[c]; });
}
let timer = null, dirty = false, unread = false, base = null, busy = null;
function status(t, bad) { const el = $("#save"); el.textContent = t; el.classList.toggle("bad", !!bad); }
const get = async () => { const r = await fetch(RELAY + "/paths", {headers: {"x-gus-key": KEY}, cache: "no-store"}); if (!r.ok) throw new Error(r.status === 401 ? "the hub passcode was refused" : "the relay said " + r.status); return r.json(); };
const take = got => { planner = {sessions: got.sessions || [], order: got.order || {}, cards: got.cards || {}}; };
function changed() {
  dirty = true; store.set("osse-arcs-local", JSON.stringify(A));
  if (unread) { status("Not saving: the relay could not be read when this page opened. Reload before you change more.", true); return; }
  status(KEY ? "Saving…" : "Saved on this device only");
  clearTimeout(timer); if (KEY) timer = setTimeout(save, 800);
}
async function save() {
  if (busy) { clearTimeout(timer); timer = setTimeout(save, 300); return; }
  busy = (async () => {
    try {
      const got = await get(); take(got);
      if (got.arcs && base && !same(got.arcs, base)) { A = merge3(base, A, got.arcs); tidy(); draw(); }
      const sent = copyOf(A), body = JSON.stringify({...got, arcs: sent});
      const r = await fetch(RELAY + "/paths", {method: "PUT", headers: {"x-gus-key": KEY, "content-type": "application/json"}, body});
      if (!r.ok) throw new Error(r.status === 401 ? "the hub passcode was refused" : "the relay said " + r.status);
      base = sent; if (same(A, sent)) { dirty = false; status("Saved"); }
    } catch (e) { status("Not saved: " + e.message + ". This device keeps a copy.", true); }
  })();
  await busy; busy = null;
}
async function look() {   // anything new from another device or a session with Claude?
  if (!KEY || unread || dirty || busy || document.visibilityState === "hidden" || (document.activeElement && document.activeElement.matches("#drawer input, #drawer textarea, #drawer select"))) return;
  try { const got = await get(); take(got); if (got.arcs && !same(got.arcs, base)) { A = copyOf(got.arcs); base = copyOf(got.arcs); tidy(); draw(); } } catch (e) {}
}
setInterval(look, 20000); addEventListener("focus", look);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") look(); else if (dirty && KEY && !unread) save(); });
async function load() {
  const local = (() => { try { const x = JSON.parse(store.get("osse-arcs-local") || "null"); return x && x.order ? x : null; } catch (e) { return null; } })();
  let got = null;
  if (KEY) {
    try { got = await get(); take(got); status("Saved"); }
    catch (e) { unread = true; status(String(e.message).includes("passcode") ? "Hub passcode refused: unlock the hub again to save." : "Relay unreachable: showing this device's copy. Reload before you change anything.", true); }
  } else status("Unlock the game master section on the hub to save to the relay. Until then this device keeps your changes.");
  if (got && got.arcs && got.arcs.order) { A = copyOf(got.arcs); base = copyOf(got.arcs); }
  else if (local) { A = local; if (got) { dirty = true; } }   // the relay lost them (or never had them): this device's copy goes back up
  else { A = copyOf(D.seed); if (got) dirty = true; }
  tidy(); draw();
  if (dirty && KEY && !unread) save();
}
load();
})();
"""


def _stub():
    """vault/arcs.html without the vault: the played sessions come from vault/status.json and the session pages."""
    st = json.load(open(os.path.join(REPO, "vault", "status.json"), encoding="utf-8"))
    files = {int(m.group(1)): f for f in os.listdir(os.path.join(REPO, "vault")) for m in [re.fullmatch(r"s(\d+)-.*\.html", f)] if m}
    played = []
    for k, t in st["titles"].items():
        n = int(k); f = files.get(n, "")
        s = ""
        if f:
            m = re.search(r'<p class="summary">(.*?)</p>', open(os.path.join(REPO, "vault", f), encoding="utf-8").read())
            s = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))) if m else ""
        played.append({"n": n, "title": t, "summary": s, "href": f})
    played.sort(key=lambda x: x["n"])
    return types.SimpleNamespace(player=False, cur=st["current"]), played


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    site, played = _stub()
    out = os.path.join(REPO, "vault", "arcs.html")
    open(out, "w", encoding="utf-8").write(page(site, played))
    print("Wrote", os.path.relpath(out, REPO))
