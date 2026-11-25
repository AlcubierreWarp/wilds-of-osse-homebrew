#!/usr/bin/env python3
"""Arc planner (vault/arcs.html): the campaign as a row per arc. Built by pages.py on every build; never edit the page by hand.

Each arc has a name, what it starts on, what it ends on, and what it is about. Its row holds session cards in running order:
a card is a played session, a session planned in the Session planner, or a general idea for one. Tom drags cards within a row
and between rows, edits everything, and adds or deletes arcs and cards.

The arcs are the `arcs` part of the Session planner's store on the Gus relay (paths.json), behind the hub's game master
passcode, and both pages read and change the same records. A card whose `link` is a session (S15) IS that session's name and
description in the Session planner. Numbers follow the order of the cards: move a planned session here and its tab, scenes,
cards and links in the Session planner take the new number with it (LINK, below, shared by both pages). A session in the
Session planner that no card is linked to keeps its number, and the cards count around it.
`python3 tools/osse/paths_sync.py arcs` prints them. Nothing here is canon or a vault plan: the arcs only frame the sessions.

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


# How sessions and session cards hold together, the same on both pages. `st` is the store: {sessions, items, edges, order, arcs}.
LINK = r"""const Link = (() => {
  const num = l => { const m = /^S(\d+)$/i.exec(l || ""); return m ? +m[1] : 0; };
  const has = st => !!(st.arcs && st.arcs.order && st.arcs.order.length);
  function tidy(A) {   // every card in exactly one arc, no arc without its record, no session on two cards
    if (!A || !A.order) return;
    A.list ||= {}; A.cards ||= {};
    A.order = [...new Set(A.order.filter(a => A.list[a]))];
    Object.keys(A.list).forEach(a => { if (!A.order.includes(a)) A.order.push(a); });
    const seen = new Set(), links = new Set();
    A.order.forEach(a => { A.list[a].cards = (A.list[a].cards || []).filter(c => A.cards[c] && !seen.has(c) && seen.add(c)); });
    Object.keys(A.cards).forEach(c => { if (!seen.has(c)) delete A.cards[c]; });
    A.order.forEach(a => A.list[a].cards.forEach(c => { const l = A.cards[c].link; if (l) { if (links.has(l)) A.cards[c].link = ""; else links.add(l); } }));
  }
  const seq = A => A.order.flatMap(a => A.list[a].cards).filter(c => A.cards[c]);
  const cardOf = (st, s) => has(st) ? seq(st.arcs).find(c => A_(st, c).link === s) || null : null;
  const A_ = (st, c) => st.arcs.cards[c];
  const arcOf = (st, c) => st.arcs.order.find(a => st.arcs.list[a].cards.includes(c));
  const unplaced = (st, cur) => (st.sessions || []).filter(s => num(s) > cur && !cardOf(st, s));   // in the Session planner, on no card
  function numbers(st, cur) {   // each card's session number: a played one its own; the rest count on, around the sessions no card has
    const keep = new Set(unplaced(st, cur).map(num)), out = {}; let n = cur;
    seq(st.arcs).forEach(c => { const l = num(A_(st, c).link); if (l && l <= cur) { out[c] = l; return; } do n++; while (keep.has(n)); out[c] = n; });
    return out;
  }
  const sort = list => { const o = [...new Set(list)].filter(x => x !== "Later").sort((x, y) => (num(x) || 1e9) - (num(y) || 1e9)); return o.concat("Later"); };
  function settle(st, cur) {   // give every planned session the number its card's place gives it; what is in it goes along. Returns {old: new}
    if (!has(st)) return {};
    tidy(st.arcs);
    const at = numbers(st, cur), map = {};
    seq(st.arcs).forEach(c => { const k = A_(st, c), l = num(k.link); if (l > cur && l !== at[c]) { map[k.link] = "S" + at[c]; k.link = "S" + at[c]; } });
    if (!Object.keys(map).length) return map;
    const to = x => map[x] || x;
    st.sessions = sort(st.sessions.map(to));
    Object.values(st.items || {}).forEach(o => { o.s = to(o.s); });
    (st.edges || []).forEach(e => { if (String(e.from).startsWith("start:")) e.from = "start:" + to(e.from.slice(6)); });
    const ord = {}; for (const k in st.order || {}) ord[to(k)] = st.order[k]; st.order = ord;
    return map;
  }
  function join(st, c, s, cur) {   // card c is session s; "new": the one its place gives, with a new tab. Returns the session's name in the end
    A_(st, c).link = s === "new" ? "S" + numbers(st, cur)[c] : s;
    if (num(A_(st, c).link) > cur) st.sessions = sort(st.sessions.concat(A_(st, c).link));
    settle(st, cur);
    return A_(st, c).link;
  }
  function part(st, c) {   // card c is an idea again; an empty tab goes with it, one with something in it stays as a session on no card
    const s = A_(st, c).link; A_(st, c).link = "";
    if (s && !Object.values(st.items || {}).some(o => o.s === s)) { st.sessions = st.sessions.filter(x => x !== s); if (st.order) delete st.order[s]; }
    return s;
  }
  function add(st, aid, link, cur) {   // a new card: after the last played or planned one in its arc (a played session: after the last earlier one)
    const A = st.arcs, c = "k" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), arr = A.list[aid].cards, n = num(link);
    A.cards[c] = {title: "", text: "", link: ""};
    let at = 0; arr.forEach((x, i) => { const l = num((A.cards[x] || {}).link); if (l && (!n || l < n)) at = i + 1; });
    arr.splice(at, 0, c);
    return c;
  }
  return {num, has, tidy, seq, cardOf, arcOf, unplaced, numbers, sort, settle, join, part, add};
})();
"""


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
    return (head + f"<style>{PANEL}{CSS}</style>" + pages.topbar(site, here="arcs") +
            '<main class="sheet arcs">'
            '<div class="atop"><div><h1>Arc planner</h1><p class="lede">The campaign, an arc to a row. Drag session cards to reorder them or move them '
            'between arcs. Tap anything to edit it. Planned sessions are the ones in the Session planner: what you change here changes there.</p></div>'
            '<div class="tools"><span id="save" class="save"></span><button class="mini" data-act="addarc">+ Arc</button></div></div>'
            '<div class="strip" id="strip" aria-label="The campaign at a glance"></div>'
            '<div class="loose" id="loose" hidden></div>'
            '<div id="rows"></div>'
            '<aside id="drawer" class="drawer" hidden></aside>'
            f'<footer>After S{site.cur}. Nothing here is canon or a vault plan: the arcs frame the sessions, and the Session planner holds what happens in each. '
            'Saved with the Session planner on the relay, behind the hub passcode.</footer>'
            f'<script>const ARCS={js_data};</script><script>' + JS.replace('/*LINK*/', LINK) + '</script></main></div></body></html>')


# The side panel, the same on the Session planner and the Arc planner: a header, boxed sections, rows of label and value, one footer.
PANEL = r"""
.drawer{position:fixed;right:14px;top:14px;bottom:14px;width:min(440px,calc(100vw - 28px));z-index:40;display:flex;flex-direction:column;overflow:hidden;
  background:#e9dcb8;color:var(--vink);border:1px solid rgba(42,29,18,.45);border-radius:8px;box-shadow:0 20px 50px rgba(0,0,0,.45);font:16px/1.4 var(--f-body)}
.ph{flex:none;background:#fbf5e6;border-top:5px solid var(--kc,var(--vmuted));border-bottom:1px solid rgba(42,29,18,.3);padding:6px 8px 9px 12px}
.ph1{display:flex;align-items:center;gap:6px;min-height:32px;font:500 11px var(--f-mono);color:var(--vmuted)}
.ph1 .ch{margin:0;padding:1px 6px}.ph1 .ki{color:var(--kc);margin:0}.ph1 b{font:600 11px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--kc,var(--vmuted));white-space:nowrap}.ph1 .sp{flex:1}
.ph h3{font-size:20px;line-height:1.2;margin:1px 0 0}.drawer .x{border:0;background:none;font:400 26px/1 var(--f-body);width:34px;height:32px;cursor:pointer;color:var(--vmuted);padding:0}
.pb{flex:1;min-height:0;overflow:auto;padding:8px;overscroll-behavior:contain}
.ps{background:#fbf5e6;border:1px solid rgba(42,29,18,.22);border-radius:6px;margin:0 0 8px;overflow:hidden}.ps:last-child{margin-bottom:0}
.ps h4{display:flex;justify-content:space-between;margin:0;padding:5px 10px;background:rgba(42,29,18,.09);font:600 11px/1.3 var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--vink)}.ps h4 span{font-weight:500;color:var(--vmuted)}
.pc{padding:7px 10px}.pc+.pc{border-top:1px solid var(--vline)}.pc p{margin:0}.pc p+p,.pc p+ul,.pc ul+p{margin-top:5px}.pc ul{margin:0;padding-left:18px}.pc a{color:var(--vred)}
.fr{display:grid;grid-template-columns:72px minmax(0,1fr);gap:4px 8px;align-items:center;padding:4px 10px;min-height:32px}.fr+.fr{border-top:1px solid var(--vline)}
.fl{font:500 11px/1.3 var(--f-mono);letter-spacing:.04em;color:var(--vmuted)}.fv{min-width:0}.toread .fr{align-items:baseline;min-height:0}.toread .fr .chips{margin:0}
.drawer input[type=text],.drawer textarea,.drawer select{width:100%;font:16px/1.35 var(--f-body);padding:4px 8px;min-height:32px;border:1px solid rgba(42,29,18,.28);border-radius:4px;background:#fff;color:var(--vink)}
.drawer input:focus,.drawer textarea:focus,.drawer select:focus{outline:2px solid var(--vred);outline-offset:-1px}
.drawer textarea{display:block;min-height:62px;resize:vertical}.drawer textarea.one{min-height:32px;resize:none;overflow:hidden}.ps>textarea,.ps>input[type=text]{border-width:0;border-radius:0;padding:7px 10px}.ps>textarea.one{border-bottom:1px solid var(--vline);font-weight:600;min-height:36px}
.drawer .ttl{font:600 19px/1.2 var(--f-display);min-height:36px;margin-top:2px}
.drawer .chk{display:flex;gap:7px;align-items:center;font:15px/1.3 var(--f-body);min-height:26px;cursor:pointer}.drawer .chk input{width:16px;height:16px;margin:0}.fv>select+.chk{margin-top:4px}
.whof{display:flex;flex-wrap:wrap;gap:4px;align-items:center}.whobox{display:contents}.drawer .whof .whoin,.drawer .whof select{flex:1;width:auto;min-width:130px}
.clk{display:flex;align-items:center;gap:8px}.clkf{display:flex;align-items:center;gap:6px}.drawer .clkf select{width:auto}
.drawer .mini{padding:4px 8px;min-height:30px;font-size:13px}.lnk{border:0;background:none;padding:0;font:inherit;color:var(--vred);text-decoration:underline;text-decoration-color:var(--vrule);text-underline-offset:2px;cursor:pointer;text-align:left}
.el{color:var(--vred)}.el.none{opacity:.75}.or+.or{margin-top:3px}.or .el::after{content:" →"}.ps small,.ol small{color:var(--vmuted);font-size:13px}.badl{margin:0;padding:4px 10px;color:var(--vred);font-size:14px}
.optx{padding:6px 10px}.optx+.optx,.optx+.pc{border-top:1px solid var(--vline)}.ol{display:flex;gap:6px;align-items:center}.ol+.ol{margin-top:4px}.ol>span:first-child{flex:none;width:14px;color:var(--vred)}.ol .on{flex:1;min-width:0}.drawer .ol input[type=text]{flex:1;width:auto;min-width:0}.drawer .ol select{flex:none;width:112px;font-size:14px;padding:4px}
.cl{display:flex;gap:7px;align-items:baseline;width:100%;border:0;border-left:3px solid var(--kc,var(--vmuted));background:none;font:inherit;line-height:1.3;color:var(--vink);text-align:left;padding:3px 6px 3px 7px;margin-top:3px;cursor:pointer;border-radius:0 4px 4px 0;width:auto}.cl:hover{background:rgba(124,22,34,.08)}.cl .ki{color:var(--kc);align-self:center;margin:0}.cl span{min-width:0}.cl small{display:block}
.sub{font:500 10.5px var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--vmuted)}
.drawer .req{list-style:none;padding:0}.req li{display:flex;gap:7px;align-items:baseline;font-size:15px}.req .ok{flex:none;width:13px;font:600 12px var(--f-mono)}.req .ok.y{color:#2f6b3a}.req .ok.n{color:var(--vred)}.req .ok.m{color:#b8860b}.req .kk{flex:none;min-width:52px;font:500 11px var(--f-mono);color:var(--vmuted)}.chg li{font-size:15px}
.pf{flex:none;display:flex;gap:8px;align-items:center;padding:8px;background:#fbf5e6;border-top:1px solid rgba(42,29,18,.3)}.pf button,.pf a{font:500 11px/1 var(--f-mono);letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--vink);border-radius:4px;padding:9px 11px;color:var(--vink);background:none;cursor:pointer;text-decoration:none;min-height:0}.pf button:disabled{opacity:.35;cursor:default}.pf .del{margin-left:auto;border-color:var(--vred);color:var(--vred)}.pf .del:hover{background:var(--vred);color:var(--vellum)}
.rwt{display:inline-flex;border:1px solid var(--vink);border-radius:5px;overflow:hidden;flex:none}.rwt button{border:0;background:none;font:600 10.5px/1 var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--vink);padding:7px 9px;cursor:pointer}.rwt button[aria-pressed=true]{background:var(--vink);color:var(--vellum)}.rwt.big{border-width:2px}.rwt.big button{font-size:12px;padding:10px 14px}
#tip{position:fixed;z-index:70;max-width:340px;background:var(--vink);color:var(--vellum);border-radius:6px;padding:8px 11px;font:14.5px/1.35 var(--f-body);box-shadow:0 8px 24px rgba(0,0,0,.4);pointer-events:none}#tip b{display:block;font:500 10px var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--gold-hi);margin-bottom:2px}
"""

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
.dph{flex:none;width:8px;border-radius:4px;background:var(--vred);opacity:.7;margin:0 -4px}
.fold{flex:none;width:150px;display:flex;flex-direction:column;justify-content:center;gap:4px;padding:10px 12px;border-radius:6px;cursor:pointer;
  border:1px solid color-mix(in srgb,var(--c) 45%,transparent);background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--c) 12%,#f3ead3) 0 8px,color-mix(in srgb,var(--c) 6%,#f3ead3) 8px 16px);font-size:13.5px;color:var(--vink);text-align:left;font-family:inherit}
.fold b{font:600 15px var(--f-display);color:var(--c)}.fold .muted{font:500 10.5px var(--f-mono);color:var(--vmuted)}.fold:hover{box-shadow:0 0 0 2px color-mix(in srgb,var(--c) 35%,transparent)}
.fold.open{width:auto;flex-direction:row;align-items:center;padding:8px;writing-mode:vertical-rl;font:500 10.5px var(--f-mono);letter-spacing:.12em;text-transform:uppercase}
.add{flex:none;width:120px;border:1px dashed var(--vrule);border-radius:6px;background:none;color:var(--vred);font:500 11px var(--f-mono);letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
.add:hover{background:rgba(255,255,255,.5)}
.empty{align-self:center;font-style:italic;color:var(--vmuted);font-size:14px;padding:0 6px}

/* editor: the same panel as the Session planner's */
.card.on{box-shadow:0 0 0 3px rgba(124,22,34,.45)}.ahead.on{background:rgba(255,255,255,.45)}
.info a.go,.info button{display:inline-block;margin-top:7px;font:500 11px var(--f-mono);letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--vink);border-radius:4px;padding:7px 9px;color:var(--vink);background:none;cursor:pointer;text-decoration:none}.info ol{margin:4px 0 0;padding-left:20px}#info:empty{display:none}
footer{margin-top:22px;font-size:13.5px;color:var(--vmuted)}
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:60;max-width:min(560px,calc(100vw - 32px));background:var(--vink);color:var(--vellum);border-radius:8px;padding:12px 16px;font-size:15px;box-shadow:0 10px 30px rgba(0,0,0,.4)}
@media (max-width:760px){
  .seg .nm span,.seg .rg{display:none}.seg{min-width:0}
  .arc{grid-template-columns:1fr}.ahead{border-right:0;border-bottom:1px solid var(--vline)}.ahead .ab{-webkit-line-clamp:3}
  .lane{padding:12px;scroll-padding:12px}.gate{width:150px;position:static;box-shadow:none!important}.card{width:190px}
  .drawer{top:auto;max-height:80vh}
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
/*LINK*/
const copyOf = x => JSON.parse(JSON.stringify(x));
let st = {sessions: [], items: {}, cards: {}, edits: {}, edges: [], order: {}, seeded: [], arcs: copyOf(D.seed)}, A = st.arcs, open = null;   // the whole store; the arcs are its part here
const folded = (() => { try { return JSON.parse(store.get("osse-arcs-open") || "{}"); } catch (e) { return {}; } })();
const num = Link.num;
const uid = p => p + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

/* ---------- what each card is ---------- */
function walk() {   // each card's session number, and whether it comes before a session to its left
  const at = Link.numbers(st, CUR), out = {}, all = Link.seq(A), last = all.reduce((b, c, i) => at[c] <= CUR ? i : b, -1); let prev = 0;
  all.forEach((c, i) => { const n = at[c]; out[c] = {n, linked: !!num(A.cards[c].link), back: n <= CUR ? n <= prev : i < last}; if (n <= CUR) prev = Math.max(prev, n); });
  return out;
}
const state = c => { const n = num(c.link); return n && n <= CUR && PLAYED.has(n) ? "played" : n ? "planned" : "idea"; };
const titleOf = c => c.title || (PLAYED.get(num(c.link)) || {}).title || (c.link ? "Session " + c.link.slice(1) : "Untitled session");
const textOf = c => c.text || (state(c) === "played" ? (PLAYED.get(num(c.link)) || {}).summary || "" : "");
function scenes(link) {   // the running order the Session planner holds for a session
  return (st.order[link] || []).filter(id => id.startsWith("p:") || st.cards[id.slice(2)]).map(id => id.startsWith("p:") ? id.slice(2) : (st.cards[id.slice(2)].title || "Untitled scene"));
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
  strip(w); loose(); wire(); mark();
  if (open) editor(open, true);
}
function cardHtml(cid, w) {
  const c = A.cards[cid], st = state(c);
  const label = st === "played" ? `<b>S${w.n}</b> · played` : st === "planned" ? `<b>S${w.n}</b> · planned` : `about S${w.n} · idea`;
  const sc = st === "planned" ? scenes(c.link) : [];
  return `<div class="card ${st}" data-card="${cid}" tabindex="0" role="button" aria-label="${esc(titleOf(c))}"><div class="k"><span>${label}</span></div>` +
    `<div class="t">${esc(titleOf(c))}</div><div class="s">${esc(textOf(c))}</div>` +
    `<div class="chips">${sc.length ? `<span class="ch">${sc.length} scene${sc.length === 1 ? "" : "s"} planned</span>` : ""}` +
    `${w.back ? `<span class="ch bad" title="It sits among the sessions already played, or before one of them">out of order</span>` : ""}` +
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
function loose() {   // sessions no card is linked to: played ones, and ones in the Session planner
  const used = new Set(Object.values(A.cards).map(c => c.link)), miss = D.played.filter(s => !used.has("S" + s.n)), un = Link.unplaced(st, CUR);
  const el = $("#loose"); el.hidden = !(miss.length || un.length) || !A.order.length;
  el.innerHTML = (miss.length ? `<span><b>Played, not in an arc:</b></span>` + miss.map(s => `<button class="mini" data-place="${s.n}">+ S${s.n} ${esc(s.title)}</button>`).join("") : "") +
    (un.length ? `<span><b>In the Session planner, not in an arc:</b></span>` + un.map(s => { const k = scenes(s).length; return `<button class="mini" data-place="${num(s)}" title="${esc(scenes(s).join(" · "))}">+ ${s}${k ? ` · ${k} scene${k === 1 ? "" : "s"}` : ""}</button>`; }).join("") +
      `<span class="muted">Click to give it a card, or open an idea's card and choose the session there.</span>` : "");
}
function mark() { $$(".card.on,.ahead.on").forEach(x => x.classList.remove("on")); const el = open && (open.card ? $(`[data-card="${open.card}"]`) : $(`[data-edit-arc="${open.arc}"]`)); if (el) el.classList.add("on"); }
const plannerHref = s => "paths.html?" + new URLSearchParams({...Object.fromEntries(new URLSearchParams(location.search)), s}) + "#%40session";

/* ---------- editing ---------- */
function touch(o) { if (o.by === "claude") o.by = "tom"; }
function editor(which, keep) {
  open = which; const d = $("#drawer"); d.hidden = false; mark();
  if (which.arc) {
    const a = A.list[which.arc]; if (!a) return closeEd();
    const i = A.order.indexOf(which.arc);
    if (keep && d.dataset.for === "arc:" + which.arc) return;
    d.dataset.for = "arc:" + which.arc;
    d.className = "drawer toedit"; d.innerHTML = head(`Arc ${i + 1}`, a.by === "claude" ? "Claude’s draft" : "", a.title, "Name this arc") + `<div class="pb">` +
      box("Starts on", `<textarea data-f="starts" aria-label="Starts on" placeholder="Where it begins">${esc(a.starts)}</textarea>`) + box("Ends on", `<textarea data-f="ends" aria-label="Ends on" placeholder="Where it ends">${esc(a.ends)}</textarea>`) +
      box("What happens", `<textarea data-f="about" aria-label="What happens" style="min-height:150px" placeholder="What the arc is about">${esc(a.about)}</textarea>`) +
      `</div><div class="pf"><button data-arcmove="-1" ${i ? "" : "disabled"}>↑ Up</button><button data-arcmove="1" ${i < A.order.length - 1 ? "" : "disabled"}>↓ Down</button><button class="del" data-delarc>Delete</button></div>`;
    grown(d);
    if (which.focus) setTimeout(() => { const f = d.querySelector(`[data-f="${which.focus}"]`); if (f) { f.focus(); f.setSelectionRange(f.value.length, f.value.length); } }, 30);
    return;
  }
  const cid = which.card, c = A.cards[cid]; if (!c) return closeEd();
  const aid = A.order.find(x => A.list[x].cards.includes(cid)), arr = A.list[aid].cards, pos = arr.indexOf(cid), w = walk()[cid] || {};
  if (keep && d.dataset.for === "card:" + cid) { info(c); return; }
  d.dataset.for = "card:" + cid;
  const used = new Set(Object.values(A.cards).map(x => x.link)), un = Link.unplaced(st, CUR), free = D.played.filter(x => !used.has("S" + x.n) || c.link === "S" + x.n), opt = (v, t) => `<option value="${v}" ${c.link === v ? "selected" : ""}>${esc(t)}</option>`;
  const many = x => { const k = scenes(x).length; return k ? `, ${k} scene${k === 1 ? "" : "s"}` : ""; };
  d.className = "drawer toedit"; d.innerHTML = head(w.linked ? `S${w.n} session` : "Session idea", (state(c) === "played" ? "played" : "") + (c.by === "claude" && state(c) !== "played" ? "Claude’s draft" : ""), c.title, titleOf({link: c.link}) || "Name") + `<div class="pb"><div class="ps"><div class="fr"><span class="fl">Session</span><div class="fv"><select data-link aria-label="Session">${opt("", `An idea, about S${w.linked ? w.n : w.n || CUR + 1}`)}` +
    (c.link && state(c) === "planned" ? opt(c.link, `${c.link}, in the Session planner`) : `<option value="new">Bring it into the Session planner</option>`) +
    (un.length ? `<optgroup label="It is a session already in the Session planner">${un.map(x => opt(x, x + many(x))).join("")}</optgroup>` : "") +
    (free.length ? `<optgroup label="It was played as">${free.slice().reverse().map(x => opt("S" + x.n, `S${x.n} · ${x.title}`)).join("")}</optgroup>` : "") + `</select></div></div>` +
    `<div class="fr"><span class="fl">Arc</span><div class="fv"><select data-movearc aria-label="Arc">${A.order.map((x, i) => `<option value="${x}" ${x === aid ? "selected" : ""}>Arc ${i + 1}: ${esc(A.list[x].title || "Untitled arc")}</option>`).join("")}</select></div></div></div>` +
    box("What happens", `<textarea data-f="text" aria-label="What happens" placeholder="${esc(state(c) === "played" ? textOf({link: c.link}) : "Where it goes, what it is for")}">${esc(c.text)}</textarea>`) +
    `<div class="ps" id="info"></div>` +
    `</div><div class="pf"><button data-cardmove="-1" ${pos ? "" : "disabled"}>← Earlier</button><button data-cardmove="1" ${pos < arr.length - 1 ? "" : "disabled"}>Later →</button><button class="del" data-delcard>Delete</button></div>`;
  grown(d);
  info(c);
  if (which.focus) setTimeout(() => { const f = d.querySelector(`[data-f="${which.focus}"]`); if (f) f.focus(); }, 30);
}
const head = (name, tag, title, ph) => `<div class="ph" style="--kc:#4d6b4a"><div class="ph1"><b>${esc(name)}</b>${tag ? `<span class="ch">${esc(tag)}</span>` : ""}<span class="sp"></span><button class="x" data-close aria-label="Close">×</button></div><input type="text" class="ttl" data-f="title" aria-label="Name" value="${esc(title)}" placeholder="${esc(ph)}"></div>`;
const box = (lab, h) => `<div class="ps"><h4>${lab}</h4>${h}</div>`;
const grown = d => d.querySelectorAll("textarea").forEach(t => { const g = () => { t.style.height = "auto"; t.style.height = Math.min(420, t.scrollHeight + 2) + "px"; }; t.addEventListener("input", g); g(); });
function info(c) {
  const el = $("#info"); if (!el) return;
  const part = (lab, n) => `<h4>${lab}${n ? `<span>${n}</span>` : ""}</h4><div class="info pc">`;
  const n = num(c.link), s = PLAYED.get(n), what = state(c);
  if (what === "played") el.innerHTML = part("Played") + `<b>S${n} · ${esc(s.title)}</b><br>${esc(s.summary)}${s.href ? `<br><a class="go" href="${esc(s.href)}">Open the session page</a>` : ""}</div>`;
  else if (what === "planned") { const sc = scenes(c.link); el.innerHTML = part("Scenes", sc.length || "") + `${sc.length ? `<ol>${sc.map(x => `<li>${esc(x)}</li>`).join("")}</ol>` : ""}<a class="go" href="${esc(plannerHref(c.link))}">Open ${c.link} in the Session planner</a></div>`; }
  else el.innerHTML = `<div class="info pc"><button data-bring>Bring it into the Session planner</button></div>`;
}
function closeEd() { open = null; const d = $("#drawer"); d.hidden = true; d.dataset.for = ""; mark(); }
const arcOf = cid => A.order.find(x => A.list[x].cards.includes(cid));
function moveCard(cid, toArc, before) {   // before: a card id, or null for the end
  const from = arcOf(cid); if (!from) return;
  A.list[from].cards = A.list[from].cards.filter(x => x !== cid);
  const arr = A.list[toArc].cards, at = before ? arr.indexOf(before) : -1;
  if (at < 0) arr.push(cid); else arr.splice(at, 0, cid);
}
function settled() {   // the cards moved: planned sessions take their new numbers, here and in the Session planner
  const map = Link.settle(st, CUR), ks = Object.keys(map).sort((x, y) => num(x) - num(y));
  if (ks.length) toast(`Renumbered in the Session planner too: ${ks.map(k => `${k} is now ${map[k]}`).join(", ")}.`);
}
function toast(t) { const d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.append(d); setTimeout(() => d.remove(), 6500); }
function addCard(aid, link) {
  const cid = link ? Link.add(st, aid, link, CUR) : uid("k");
  if (link) Link.join(st, cid, link, CUR); else { A.cards[cid] = {title: "", text: "", link: ""}; A.list[aid].cards.push(cid); settled(); }
  return cid;
}
function relink(cid, v) {   // what the Session menu on a card does
  const c = A.cards[cid], was = c.link;
  if (v === was) return;
  if (was) { const s = Link.part(st, cid); if (num(s) > CUR && st.sessions.includes(s)) toast(`${s} stays in the Session planner with what is in it, on no card here.`); }
  if (v) Link.join(st, cid, v, CUR); else settled();
  touch(c); $("#drawer").dataset.for = ""; changed(); draw();
}
document.addEventListener("input", e => {
  const f = e.target.dataset.f; if (!f || !open) return;
  const o = open.arc ? A.list[open.arc] : A.cards[open.card]; if (!o) return;
  o[f] = e.target.value; touch(o);
  changed(); redraw();
});
let rtimer = null; const redraw = () => { clearTimeout(rtimer); rtimer = setTimeout(() => { const y = scrollY, xs = $$(".lane").map(l => l.scrollLeft); draw(); $$(".lane").forEach((l, i) => l.scrollLeft = xs[i] || 0); scrollTo(0, y); }, 150); };
document.addEventListener("change", e => {
  if (e.target.matches("[data-link]") && open && open.card) relink(open.card, e.target.value);
  if (e.target.matches("[data-movearc]") && open && open.card) { moveCard(open.card, e.target.value, null); settled(); touch(A.cards[open.card]); $("#drawer").dataset.for = ""; changed(); draw(); }
});
document.addEventListener("click", e => {
  const t = e.target.closest("button,[data-edit-arc],[data-card]"); if (!t) return;
  if (t.matches("[data-close]")) return closeEd();
  if (t.matches("[data-bring]") && open && open.card) return relink(open.card, "new");
  if (t.dataset.act === "addarc") { const aid = uid("a"); A.order.push(aid); A.list[aid] = {title: "", starts: "", ends: "", about: "", cards: []}; changed(); draw(); editor({arc: aid, focus: "title"}); document.getElementById("arc-" + aid).scrollIntoView({behavior: "smooth", block: "center"}); return; }
  if (t.dataset.go) { document.getElementById("arc-" + t.dataset.go).scrollIntoView({behavior: "smooth", block: "start"}); return; }
  if (t.dataset.fold) { folded[t.dataset.fold] = !folded[t.dataset.fold]; store.set("osse-arcs-open", JSON.stringify(folded)); draw(); return; }
  if (t.dataset.add) { const cid = addCard(t.dataset.add); changed(); draw(); editor({card: cid, focus: "title"}); const el = $(`[data-card="${cid}"]`); if (el) el.scrollIntoView({behavior: "smooth", inline: "nearest", block: "nearest"}); return; }
  if (t.dataset.place) { const n = +t.dataset.place, prevArc = A.order.slice().reverse().find(x => A.list[x].cards.some(c => A.cards[c] && num(A.cards[c].link) && num(A.cards[c].link) < n)) || A.order[0], cid = addCard(prevArc, "S" + n); changed(); draw(); editor({card: cid, focus: n > CUR ? "title" : ""}); return; }
  if (t.dataset.gate) return editor({arc: t.dataset.arc, focus: t.dataset.gate});
  if (t.dataset.editArc) return editor({arc: t.dataset.editArc});
  if (t.dataset.card) { if (dragged) return; return editor({card: t.dataset.card}); }
  if (t.dataset.arcmove && open && open.arc) { const i = A.order.indexOf(open.arc), j = i + +t.dataset.arcmove; [A.order[i], A.order[j]] = [A.order[j], A.order[i]]; settled(); $("#drawer").dataset.for = ""; changed(); draw(); return; }
  if (t.dataset.cardmove && open && open.card) { const aid = arcOf(open.card), arr = A.list[aid].cards, i = arr.indexOf(open.card), j = i + +t.dataset.cardmove; [arr[i], arr[j]] = [arr[j], arr[i]]; settled(); touch(A.cards[open.card]); $("#drawer").dataset.for = ""; changed(); draw(); return; }
  if (t.matches("[data-delcard]") && open && open.card) { const cid = open.card, aid = arcOf(cid); const l = A.cards[cid].link, full = num(l) > CUR && Object.values(st.items).some(o => o.s === l); if (!confirm(`Delete “${titleOf(A.cards[cid])}”?${full ? ` ${l} stays in the Session planner with what is in it, without a name.` : num(l) > CUR ? ` Its empty tab goes from the Session planner.` : ""}`)) return; Link.part(st, cid); A.list[aid].cards = A.list[aid].cards.filter(x => x !== cid); delete A.cards[cid]; settled(); closeEd(); changed(); draw(); return; }
  if (t.matches("[data-delarc]") && open && open.arc) {
    const aid = open.arc, a = A.list[aid], n = a.cards.length;
    if (!confirm(n ? `Delete “${a.title || "this arc"}” and its ${n} session card${n === 1 ? "" : "s"}? Sessions with something in them stay in the Session planner.` : `Delete “${a.title || "this arc"}”?`)) return;
    a.cards.forEach(c => { if (A.cards[c]) { if (A.cards[c].link) Link.part(st, c); delete A.cards[c]; } }); delete A.list[aid]; A.order = A.order.filter(x => x !== aid); settled(); closeEd(); changed(); draw(); return;
  }
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("#drawer").hidden) closeEd();
  if ((e.key === "Enter" || e.key === " ") && e.target.matches(".card")) { e.preventDefault(); editor({card: e.target.dataset.card}); }
});

/* a click on the main area closes the open panel; a drag, or a click that opens something else, does not (as in the Session planner) */
let press = null;
addEventListener("pointerdown", e => { press = !$("#drawer").hidden && e.button < 1 && {x: e.clientX, y: e.clientY, at: e.target, was: $("#drawer").dataset.for}; }, true);
addEventListener("pointercancel", () => { press = null; }, true);
addEventListener("pointerup", e => {
  const p = press; press = null;
  if (!p || Math.hypot(e.clientX - p.x, e.clientY - p.y) >= 5 || !p.at.closest || !p.at.closest(".arcs") || p.at.closest(".drawer")) return;
  if (p.at.closest("button,a,input,select,textarea,label,.card,[data-edit-arc]")) return;   // these do something of their own
  setTimeout(() => { if (!$("#drawer").hidden && $("#drawer").dataset.for === p.was) closeEd(); }, 0);
}, true);

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
  drag.ph = document.createElement("div"); drag.ph.className = "dph"; el.after(drag.ph);
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
  if (ok && d.lane && d.before !== d.cid) { moveCard(d.cid, d.lane, d.before); settled(); touch(A.cards[d.cid]); $("#drawer").dataset.for = ""; changed(); }
  const xs = $$(".lane").map(l => l.scrollLeft); draw(); $$(".lane").forEach((l, i) => l.scrollLeft = xs[i] || 0);
}
addEventListener("pointerup", ev => { if (drag && ev.pointerId === drag.id) end(true); });
addEventListener("pointercancel", ev => { if (drag && ev.pointerId === drag.id) end(false); });
addEventListener("contextmenu", ev => { if (drag) ev.preventDefault(); });

/* ---------- saving: the Session planner's store, the same way it does. Every save reads first and merges, record by record,
   what changed there with what changed here (here wins on the same thing), then sends the whole store back. ---------- */
const isMap = x => !!x && typeof x === "object" && !Array.isArray(x);
const canon = x => JSON.stringify(x, (k, v) => isMap(v) ? Object.fromEntries(Object.keys(v).sort().map(q => [q, v[q]])) : v) ?? "";
const same = (a, b) => canon(a) === canon(b);
function merge3(b, m, t) {
  if (same(m, b)) return t;
  if (same(t, b) || same(m, t)) return m;
  if (isMap(m) && isMap(t)) { const o = {}; for (const k of new Set([...Object.keys(m), ...Object.keys(t)])) { const v = merge3(isMap(b) ? b[k] : undefined, m[k], t[k]); if (v !== undefined) o[k] = v; } return o; }
  return Array.isArray(m) && Array.isArray(t) ? m.concat(t.filter(x => !m.some(y => same(x, y)) && !(Array.isArray(b) && b.some(y => same(x, y))))) : m;
}
const PARTS = ["sessions", "items", "cards", "edits", "edges", "order", "seeded", "arcs"], LISTS = ["sessions", "edges", "seeded"];
const partsOf = d => { const o = {}; PARTS.forEach(f => { o[f] = copyOf(d[f] ?? (LISTS.includes(f) ? [] : {})); }); o.edges = Object.fromEntries(o.edges.map(e => [e.id, e])); return o; };
function hold(p) { PARTS.forEach(f => { st[f] = f === "edges" ? Object.values(p.edges) : p[f]; }); st.sessions = Link.sort(st.sessions); A = st.arcs; Link.tidy(A); }
function absorb(got) {   // take in what was saved elsewhere; true when it changes what this page holds
  const theirs = partsOf(got), mine = partsOf(st);
  if (!theirs.arcs.order) theirs.arcs = base ? copyOf(base.arcs) : theirs.arcs;   // a store without arcs does not take them away
  const out = merge3(base || theirs, mine, theirs);
  base = copyOf(theirs);
  if (same(out, mine)) return false;
  hold(out); return true;
}
let timer = null, dirty = false, unread = false, base = null, busy = null, ticks = 0;
function status(t, bad) { const el = $("#save"); el.textContent = t; el.classList.toggle("bad", !!bad); }
const get = async () => { const r = await fetch(RELAY + "/paths", {headers: {"x-gus-key": KEY}, cache: "no-store"}); if (!r.ok) throw new Error(r.status === 401 ? "the hub passcode was refused" : "the relay said " + r.status); return r.json(); };
function changed() {
  dirty = true; ticks++; store.set("osse-arcs-local", JSON.stringify(A));
  if (unread) { status("Not saving: the relay could not be read when this page opened. Reload before you change more.", true); return; }
  status(KEY ? "Saving…" : "Saved on this device only");
  clearTimeout(timer); if (KEY) timer = setTimeout(save, 800);
}
async function save() {
  if (busy) { clearTimeout(timer); timer = setTimeout(save, 300); return; }
  busy = (async () => {
    try {
      const got = await get();
      if (!base) base = partsOf(got);
      if (absorb(got)) { Link.settle(st, CUR); draw(); }
      const at = ticks, sent = partsOf(st), body = JSON.stringify({...got, ...copyOf(sent), edges: Object.values(sent.edges)});
      const r = await fetch(RELAY + "/paths", {method: "PUT", headers: {"x-gus-key": KEY, "content-type": "application/json"}, body});
      if (!r.ok) throw new Error(r.status === 401 ? "the hub passcode was refused" : "the relay said " + r.status);
      base = sent; if (ticks === at) { dirty = false; status("Saved"); }
    } catch (e) { status("Not saved: " + e.message + ". This device keeps a copy.", true); }
  })();
  await busy; busy = null;
}
async function look() {   // anything new from another device or a session with Claude?
  if (!KEY || unread || dirty || busy || drag || document.visibilityState === "hidden" || (document.activeElement && document.activeElement.matches("#drawer input, #drawer textarea, #drawer select"))) return;
  try { const got = await get(); if (dirty || drag) return; if (absorb(got)) { $("#drawer").dataset.for = ""; draw(); } } catch (e) {}
}
setInterval(look, 20000); addEventListener("focus", look);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") look(); else if (dirty && KEY && !unread) save(); });
async function load() {
  const local = (() => { try { const x = JSON.parse(store.get("osse-arcs-local") || "null"); return x && x.order ? x : null; } catch (e) { return null; } })();
  let got = null;
  if (KEY) {
    try { got = await get(); status("Saved"); }
    catch (e) { unread = true; status(String(e.message).includes("passcode") ? "Hub passcode refused: unlock the hub again to save." : "Relay unreachable: showing this device's copy. Reload before you change anything.", true); }
  } else status("Unlock the game master section on the hub to save to the relay. Until then this device keeps your changes.");
  if (got) { base = partsOf(got); hold(copyOf(base)); }
  if (!A.order) { st.arcs = A = local || copyOf(D.seed); if (got) dirty = true; }   // the relay lost them (or never had them): this device's copy goes back up
  else if (!got && local) st.arcs = A = local;
  Link.tidy(A); if (got && Object.keys(Link.settle(st, CUR)).length) dirty = true;
  draw();
  const want = new URLSearchParams(location.search).get("card"); if (want && A.cards[want]) { editor({card: want}); const el = $(`[data-card="${want}"]`); if (el) el.scrollIntoView({inline: "center", block: "center"}); }
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
