"""Scene sheets: the Session planner's PDF. Each scene as printed Letter pages, to run it from at the table.

Not the canvas and not the Running order: a prompt book, as a stage manager keeps one. Every scene has the same pages in the same order,
in one type size, so the eye learns where each thing is:

    Set the scene    the question the scene answers; Opens on, words to say and things to see, hear and smell; where things stand;
                     what to keep hidden; what pushes in from outside; the people, how they sound and what they want
    Play it          the spine: cue on the left, what it sets off on the right, read by what just happened at the table, in any order;
                     a decision's choices side by side; Any time cards held at the side; the ways out at the foot of the last page

A scene takes as many Play pages as it needs, up to four pages in all (MAX). Past that its sentences run on to save room, then each card
keeps its first lines, and the preview says so. The type never shrinks.

Type follows the research on checklists read under pressure: a sans in sentence case, black on white, bold only for what the eye must
find, no italics, one thought to a line, colour never the only sign (every kind has its symbol too). Boxes are for a pencil.

CSS and JS go into the Session planner (paths.py); the JS uses its functions.
"""
import re

LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")

CSS = r"""
#pdf{position:fixed;inset:0;z-index:90;display:flex;flex-direction:column;background:#2c2a28;user-select:text;-webkit-user-select:text}#pdf[hidden]{display:none}
.pbar{flex:none;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;padding:10px 16px;background:var(--vellum);border-bottom:2px solid var(--vink);color:var(--vink)}
.pbar h2{border:0;margin:0;padding:0;font-size:17px;letter-spacing:.04em;text-transform:none;color:var(--vink)}.pbar .sp{flex:1}
.pbar button{font:500 12px/1 var(--f-mono);letter-spacing:.06em;border:1px solid var(--vink);border-radius:4px;background:none;color:var(--vink);padding:10px 12px;cursor:pointer}
.pbar button:hover{background:rgba(255,255,255,.6)}.pbar .go{background:var(--vink);color:var(--vellum)}.pbar .go:hover{background:#000}.pbar .go:disabled{opacity:.4;cursor:default}
.ppick{display:flex;flex-wrap:wrap;gap:5px}.ppick button{padding:8px 10px;max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--f-body);font-size:14px;letter-spacing:0}.ppick button[aria-pressed=false]{opacity:.5;text-decoration:line-through}.ppick button[aria-pressed=true]{background:rgba(63,90,60,.16);border-color:#3f5a3c}
.pnote{flex-basis:100%;font-size:14px;color:var(--vred)}.pnote:empty{display:none}
.pages{flex:1;min-height:0;overflow:auto;padding:22px 12px;display:flex;flex-direction:column;align-items:center;gap:22px}
.pz{flex:none;position:relative;background:#fff;box-shadow:0 8px 30px rgba(0,0,0,.5)}

.pg{--ink:#111;--soft:#444;--hair:#b9b9b9;--f:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif;--fc:"IBM Plex Sans Condensed","Arial Narrow",Arial,sans-serif;
  width:8.5in;height:10.98in;padding:.38in .42in .32in;display:flex;flex-direction:column;background:#fff;color:var(--ink);font:400 10.5pt/1.32 var(--f);overflow:hidden;transform-origin:0 0;
  print-color-adjust:exact;-webkit-print-color-adjust:exact;text-align:left}
.pg *{box-sizing:border-box}:where(.pg) p,:where(.pg) ul,:where(.pg) li,:where(.pg) h3,:where(.pg) h4{margin:0;padding:0}:where(.pg) p,:where(.pg) li{line-height:inherit;font-size:inherit;max-width:none}
.pg .k-scene{--kc:#3f5a3c}.pg .k-beat{--kc:#5a4c38}.pg .k-reveal{--kc:#5e3d82}.pg .k-complication{--kc:#b04d12}.pg .k-decision{--kc:#8f1626}.pg .k-entrance{--kc:#1f6d66}.pg .k-exit{--kc:#111}.pg .k-clock{--kc:#2f4d75}.pg .k-pressure{--kc:#8d6500}.pg .k-bottleneck{--kc:#111}.pg .k-note{--kc:#7a6400}

/* head: which scene, where, when, whose */
.hd{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:0 .16in;align-items:center;border-bottom:2.5pt solid var(--ink);padding-bottom:.09in}
.hd .no{font:700 40pt/.9 var(--f);min-width:.5in;text-align:center;background:var(--ink);color:#fff;padding:.07in .1in .09in;border-radius:3pt;font-variant-numeric:tabular-nums}
.hd h3{font:600 20pt/1.1 "Cinzel",Georgia,serif;letter-spacing:.01em;text-wrap:balance}.hd .wh{font:600 10.5pt/1.3 var(--f);margin-top:2pt}.hd .wh span+span::before{content:"·";margin:0 .4em;color:var(--soft)}
.rt8{text-align:right;font:500 8.5pt/1.3 var(--f)}.rt8 b{display:block;font:700 10pt/1.2 var(--f)}
.dots{display:flex;gap:3pt;justify-content:flex-end;margin-top:4pt}.dots i{color:var(--ink);opacity:1;font:600 8.5pt/1 var(--f);font-style:normal;min-width:15pt;height:15pt;padding:0 3pt;display:grid;place-items:center;border:1pt solid var(--ink);border-radius:8pt}.dots i.on{background:var(--ink);color:#fff}.dots i.fl{border-style:dashed}
.cast{display:flex;flex-wrap:wrap;gap:3pt 4pt;margin-top:4pt}.cast span{font:700 9.5pt/1 var(--f);padding:3pt 7pt;border:1.2pt solid var(--ink);border-radius:8pt;background:color-mix(in srgb,var(--c,#fff) 55%,#fff)}.cast span.in{border-style:dashed}.cast small{font:500 8pt/1 var(--f)}

.hd.sl{padding-bottom:.07in}.hd.sl .no{font-size:20pt;min-width:.36in;padding:.04in .08in .05in}.hd.sl h3{font-size:15pt}.hd.sl .dots{margin-top:2pt}

/* set the scene */
.st8{flex:1;min-height:0;display:flex;flex-direction:column;gap:.16in;padding-top:.13in}
.qq{font:700 15pt/1.22 var(--f);text-wrap:balance}.qq+p{margin-top:3pt!important;color:var(--soft)}
.op8{border:1.4pt solid var(--ink);border-radius:4pt;padding:.1in .14in .12in}.op8 .lb8{color:var(--ink);font-size:9pt}.op8 .al p{font:500 11.5pt/1.48 var(--f)}.op8 .al p+p{margin-top:.07in}
.sn8{display:grid;grid-template-columns:1fr 1fr;gap:.09in .22in;margin-top:.11in;padding-top:.1in;border-top:.8pt solid var(--hair)}.sn8>div{display:grid;grid-template-columns:.74in minmax(0,1fr);gap:0 6pt}.sn8 b{font:700 8.5pt/1.5 var(--f);letter-spacing:.05em;text-transform:uppercase}
.wln{height:19pt;border-bottom:.7pt solid var(--hair)}.op8 .al .wln{height:22pt}
.tw{display:grid;grid-template-columns:minmax(0,1fr) 2.2in;gap:.22in;align-items:start}.tw>div{display:flex;flex-direction:column;gap:.14in}
.ppl{display:grid;grid-template-columns:1fr 1fr;gap:.1in .24in}.bx .ppl>.pp{margin:0;break-inside:avoid}
.pg .none{color:var(--soft);margin:0}
.lb8{font:700 8pt/1.2 var(--f);letter-spacing:.07em;text-transform:uppercase;color:var(--soft);margin-bottom:2pt;display:block}
:where(.pg) ul{padding-left:.95em;list-style:none}.pg li{position:relative}.pg li+li{margin-top:.1em}.pg li::before{content:"";position:absolute;left:-.8em;top:.55em;width:.28em;height:.28em;border-radius:50%;background:var(--ink)}.pg p+ul{margin-top:1pt}
.say{font-weight:700}
.pg.rn8 .lead:has(+ul){display:inline}.pg.rn8 .lead+ul,.pg.rn8 .lead+ul li{display:inline;padding:0}.pg.rn8 .lead+ul li::before{content:"•\00a0";position:static;width:auto;height:auto;background:none;margin-left:.3em}

.bd8{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 2.05in;gap:.18in;padding-top:.11in}.mn,.sd{min-width:0;min-height:0;display:flex;flex-direction:column;overflow:hidden}.mn>*,.sd>.bx,.st8>:not(.nt8){flex:none}
.mn>.lb8{margin-bottom:5pt}.mn>.lb8 b{color:var(--ink);text-transform:none;letter-spacing:0;font-weight:600}

/* the spine: cue, symbol, what it sets off */
.sp8.th1{margin-top:.35em;border-top:1pt dashed var(--hair);padding-top:.6em}.sp8.th1:first-of-type{margin-top:0;border-top:0;padding-top:0}
.pg.gist .bd8 .lead+ul{display:none}.pg.gist .bd8 .lead{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}
.sp8{break-inside:avoid;display:grid;grid-template-columns:1.1in 2em minmax(0,1fr);gap:0 6pt;position:relative;padding-bottom:.55em}
.sp8 .cu{font:600 .95em/1.22 var(--fc);text-align:right;padding-top:2pt;text-wrap:balance}.sp8 .cu.lo{font-weight:400;color:var(--soft)}.sp8 .cu small{display:block;font:400 .82em/1.2 var(--fc);color:var(--soft)}
.sp8 .nd{position:relative;display:flex;justify-content:center}.sp8:not(.end) .nd::after{content:"";position:absolute;top:1.85em;bottom:calc(-.55em - 1pt);width:1.5pt;background:var(--ink)}
.nd i{position:relative;z-index:1;width:1.9em;height:1.9em;display:grid;place-items:center;border:1.6pt solid var(--kc);border-radius:50%;color:var(--kc);background:#fff}.nd i svg{width:1.2em;height:1.2em}
.k-decision>.nd i{border-radius:2pt;background:var(--kc);color:#fff}.crit>.nd i{outline:1.6pt solid var(--kc);outline-offset:1.6pt}
.ct{display:flex;gap:6pt;align-items:baseline}.ct b{flex:1;min-width:0;font:700 1.1em/1.2 var(--f)}.ct .kd{font:700 .68em/1 var(--f);letter-spacing:.06em;text-transform:uppercase;color:var(--kc);white-space:nowrap}
.tgs{flex:none;max-width:55%;display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:2pt 3pt;font:500 .74em/1 var(--f);color:var(--soft)}.tg{font:600 1em/1 var(--f);color:var(--ink);padding:1.5pt 4pt;border:.8pt solid var(--ink);border-radius:6pt;background:color-mix(in srgb,var(--c,#fff) 55%,#fff)}
.tick{flex:none;align-self:flex-start;width:.95em;height:.95em;border:1.1pt solid var(--ink);border-radius:1.5pt;margin-top:2pt}
.ex{font:500 .86em/1.25 var(--f);margin-top:1pt!important}.ex b{font-weight:700}.ex.only{color:#8f1626}
.lead{margin-top:1pt!important}

/* a fork: the choices side by side */
.fk{margin:0 0 .6em;border-top:1.6pt solid #8f1626;position:relative;display:grid;gap:0 .12in;grid-template-columns:var(--cols);padding-top:.12in}
.fk.more::before{display:none}.fk::before{content:"";position:absolute;left:calc(1.1in + 6pt + 1em - .75pt);top:-.6em;height:.6em;width:1.5pt;background:#8f1626}
.op{position:relative;border:1pt solid var(--hair);border-radius:3pt;padding:0 7pt 6pt;min-width:0;display:flex;flex-direction:column;gap:.45em}
.op::before{content:"";position:absolute;left:50%;top:-.12in;height:.12in;width:1.5pt;background:#8f1626}
.oh{margin:0 -7pt;padding:4pt 7pt;background:#f3e4e6;border-bottom:1pt solid #8f1626;font:700 1em/1.2 var(--f);border-radius:2pt 2pt 0 0}.oh::first-letter{text-transform:uppercase}
.fk.gos{grid-template-columns:1fr;gap:4pt;border-top:0;padding:2pt 0 0 calc(1.1in + 2em + 12pt)}.fk.gos::before{left:calc(1.1in + 6pt + 1em - .75pt);top:-.6em;height:calc(.6em + 2pt)}.fk.gos .op{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:0 8pt;align-items:center;padding:0 7pt 0 0;border-color:#8f1626}.fk.gos .op::before{left:calc(-1em - 6.75pt - 1pt);top:50%;width:calc(1em + 7pt);height:1.5pt}.fk.gos .op::after{content:"";position:absolute;left:calc(-1em - 7.75pt);top:-5pt;height:calc(50% + 6pt);width:1.5pt;background:#8f1626}.fk.gos .op:not(:last-child)::after{height:calc(100% + 6pt)}.fk.gos .oh{margin:0;height:100%;border:0;border-right:1pt solid #8f1626;border-radius:2pt 0 0 2pt;padding:3pt 7pt}.fk.gos .to8{padding:3pt 0}
.mi{border-left:2pt solid var(--kc);padding-left:6pt}.mi .cu{font:600 .9em/1.2 var(--fc);color:var(--soft)}.mi .ct svg{flex:none;width:1em;height:1em;color:var(--kc);align-self:center}.mi .ct b{font-size:1em}
.sub8{display:flex;flex-direction:column;gap:.4em;margin:.35em 0 0 6pt}.sub8>div{border-left:1.6pt solid #8f1626;padding-left:6pt;display:flex;flex-direction:column;gap:.3em}.sub8 .oh{margin:0;padding:1pt 0;background:none;border:0}
.to8{font:600 .92em/1.25 var(--f);display:flex;gap:5pt;align-items:baseline}.to8 .ar{font-weight:700}.to8 .wo{flex:none;font:700 .95em/1 var(--f);background:var(--ink);color:#fff;border-radius:2pt;padding:2pt 4pt}.to8 small{font:400 .9em/1.2 var(--f);color:var(--soft)}

/* the side: what to reach for */
.sd{gap:.1in;border-left:1pt solid var(--hair);padding-left:.14in}
.pg h4{color:var(--ink);font:700 8.5pt/1.2 var(--f);letter-spacing:.07em;text-transform:uppercase;border-bottom:1.4pt solid var(--ink);padding-bottom:2pt;margin-bottom:4pt}
.bx>div+div{margin-top:.5em}
.hold{border:1.2pt solid var(--kc);border-radius:3pt;padding:4pt 6pt 5pt}.hold .cu{font:600 .92em/1.2 var(--fc)}.hold .cu::before{content:"When ";font-weight:400;color:var(--soft)}.hold .ct{gap:2pt 5pt;flex-wrap:wrap}.hold .ct .tgs{order:9;flex-basis:100%;max-width:none;justify-content:flex-start}.hold .ct b{font-size:1em}.hold .ct svg{flex:none;width:1.1em;height:1.1em;color:var(--kc);align-self:center}
.pp b{font:700 1em/1.2 var(--f)}.pp small{font:500 .82em/1 var(--f);color:var(--soft)}.pp p{font-size:.9em;line-height:1.26}.pp p span{font-weight:700;margin-right:.35em}
.hush li{font-size:.94em}.hush li::before{border-radius:0;background:#8f1626}
.cl8{display:flex;gap:2.5pt;margin-top:2pt}.cl8 i{width:11pt;height:11pt;border:1.1pt solid var(--ink);border-radius:50%}.cl8 i.f{background:var(--ink)}
.nt8{flex:1;min-height:0;overflow:hidden}

/* ways out: the foot of every page */
.wy{flex:none;border-top:2.5pt solid var(--ink);padding-top:.08in;margin-top:.08in;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:.08in .14in}
.wy .lb8{grid-column:1/-1;margin:0}
.wo8{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 7pt;align-content:start}.wo8 .lt{font:700 13pt/1 var(--f);background:var(--ink);color:#fff;border-radius:3pt;min-width:20pt;height:20pt;display:grid;place-items:center}
.wo8.nx .lt{background:#fff;color:var(--ink);border:1.2pt solid var(--ink)}.wo8 .cu{font:600 .9em/1.2 var(--fc)}.wo8 p{font-size:.92em;line-height:1.26}.wo8 .gt{font:700 1em/1.25 var(--f);margin-top:2pt}.wo8 .gt::before{content:"→ "}.wo8 .gt u{display:inline-block;min-width:1.2in;border-bottom:1pt solid var(--ink);text-decoration:none}
.ft8{flex:none;display:flex;justify-content:space-between;font:400 7.5pt/1 var(--f);color:var(--soft);padding-top:.1in}

@page{size:letter portrait;margin:0}
@media print{
  html,body{height:auto!important;min-height:0!important;overflow:visible!important;background:#fff!important;padding:0!important;margin:0!important}
  body.sheets>*:not(#pdf){display:none!important}body.sheets::before,body.sheets::after{display:none!important}
  body.sheets #pdf{position:static;display:block;background:none}.pbar{display:none}.pages{display:block;padding:0;overflow:visible}
  .pz{width:auto!important;height:auto!important;box-shadow:none;break-after:page;break-inside:avoid}.pz:last-child{break-after:auto}.pg{transform:none!important}
}
"""

JS = r"""
/* ---------- scene sheets: printed pages to run each scene from ---------- */
const Sheets = (() => {
  const FONTS = "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@400;600;700&display=swap";
  const N = D.npcs || {}, MAX = 4;
  let off = new Set(), at = "";
  /* words: one thought to a line; what is said aloud in bold */
  const thoughts = t => String(t || "").split(/\n+/).map(x => x.replace(/^\s*[-•]\s*/, "").trim()).filter(Boolean).map(x => /[.!?:;…"”’)]$/.test(x) ? x : x + ".")
    .flatMap(x => x.replace(/“[^”]*”/g, q => q.replace(/ /g, "\u0002")).replace(/([.!?]["”’)]?)\s+(?=["“(]?[A-ZÀ-Ý])/g, "$1\u0001").replace(/\b(Mr|Mrs|Ms|Dr|St|vs)\.\u0001/g, "$1. ").split("\u0001").map(y => y.replace(/\u0002/g, " ")));
  const loud = t => esc(t).replace(/“[^”]+ [^”]+”|&quot;[^&]+ [^&]+&quot;/g, "<span class=\"say\">$&</span>");
  function words(t) {
    const s = thoughts(t); if (!s.length) return "";
    return s.length < 3 ? `<p class="lead">${loud(s.join(" "))}</p>` : `<p class="lead">${loud(s[0])}</p><ul>${s.slice(1).map(x => `<li>${loud(x)}</li>`).join("")}</ul>`;
  }
  const textOf = id => { const o = objOf(id); return id.startsWith("c:") ? o.text || "" : [o.summary, o.ideaText].filter((x, i, a) => x && a.indexOf(x) === i).join("\n"); };
  const where = (id, from) => {   // a card or scene somewhere else, as a place to go
    const s = isScene(id) ? id : sceneOf(id), t = sessOf(id), other = t !== sessOf(from), no = s && numIn(s) ? numIn(s) + " " : "";
    return `${other && t ? esc(t) + " · " : ""}${s ? no + esc(titleOf(s)) : ""}${isScene(id) ? "" : (s ? ": " : "") + esc(titleOf(id))}`;
  };
  const short = n => { const k = pcOf(n); return k === "party" ? "The Party" : k ? shortOf(k) : n; };

  function page(sid, t, list) {
    const o = objOf(sid), tr = treeOf(sid), any = anyOf(sid), all = membersOf(sid), es = genEdges();
    const outs = [...tr.ms, ...any].filter(m => kindOf(m) === "exit"), letter = m => "ABCDEFGHIJKLMNOP"[outs.indexOf(m)] || "";
    const whoOf = m => fieldOf(objOf(m), "who") || [];

    /* what a card says, the same on the spine, in a fork and in the side */
    function facts(m) {
      const c = objOf(m), k = kindOf(m) || "beat", who = whoOf(m), req = m.startsWith("p:") ? c.req : [];
      const only = req.filter(r => r.k === "check").map(r => r.t), bad = req.filter(r => r.k !== "check" && !test(r)).map(r => `${r.k} ${r.a || r.t}`);
      const come = es.filter(e => e.to === m && e.from !== sid && sceneOf(e.from) !== sid && live(e.from));
      return words(textOf(m)) + (k === "exit" && who.length ? `<p class="ex"><b>Leaves</b> ${esc(who.map(short).join(", "))}</p>` : "") +
        (k === "reveal" && c.reveals ? `<p class="ex"><b>Comes out</b> ${esc(c.reveals)}</p>` : "") +
        (come.length ? `<p class="ex"><b>Follows from</b> ${come.map(e => where(e.from, sid) + (e.label && e.label !== "then" ? ` (${esc(e.label)})` : "")).join("; ")}</p>` : "") +
        (only.length ? `<p class="ex only"><b>Only if</b> ${esc(only.join("; "))}</p>` : "") + (bad.length ? `<p class="ex only"><b>No longer holds</b> ${esc(bad.join("; "))}</p>` : "");
    }
    const away = m => es.filter(e => e.from === m && live(e.to) && sceneOf(e.to) !== sid && e.to !== sid);   // where a card leads, outside this scene
    const goTo = e => `<div class="to8"><span class="ar">→</span><span>${e.label && e.label !== "then" ? esc(e.label) + ": " : ""}${where(e.to, sid)}</span></div>`;
    const wayOut = m => `<div class="to8"><span class="ar">→</span><span class="wo">${letter(m)}</span><span>${esc(titleOf(m))}</span></div>`;
    const tag = n => { const l = PCS.find(p => p.key === pcOf(n)); return `<span class="tg"${l ? ` style="--c:${esc(l.colour)}"` : ""}>${esc(short(n))}</span>`; };
    const title = m => { const k = kindOf(m), who = whoOf(m); return `<div class="ct">%<b>${esc(titleOf(m))}${isCrit(objOf(m)) ? ` <span class="kd">Critical</span>` : ""}</b>${who.length ? `<span class="tgs">${k === "entrance" ? "in" : k === "exit" ? "out" : ""}${who.map(tag).join("")}</span>` : ""}<span class="tick"></span></div>`; };

    function choices(m) {   // a decision's options, the ones that come to the same thing together
      const g = new Map();
      optionsOf(m).forEach(x => { const key = x.to || "t:" + (x.text || x.label); if (!g.has(key)) g.set(key, {...x, labels: []}); if (x.label) g.get(key).labels.push(x.label); });
      return [...g.values()];
    }
    function outcome(m, x) {
      if (!x.to) return x.text ? `<p>${loud(x.text)}</p>` : "";
      if (x.off) return `<div class="to8"><span class="ar">→</span><span>${esc(titleOf(x.to))}</span><small>not placed</small></div>`;
      if (sceneOf(x.to) !== sid) return goTo({to: x.to});
      if (kindOf(x.to) === "exit") return wayOut(x.to);
      return tr.par[x.to] === m ? mini(x.to) : `<div class="to8"><span class="ar">→</span><span>${esc(titleOf(x.to))}</span><small${isAny(x.to) ? ">any time" : ` data-to="${esc(x.to)}">in this scene`}</small></div>`;
    }
    const opHead = x => `<div class="oh${x.labels.length ? "" : " nl"}">${x.labels.length ? x.labels.map(esc).join(" <span style=\"font-weight:400\">or</span> ") : "Choice not named"}</div>`;
    function mini(m) {   // a card in a fork, and what follows it there
      const k = kindOf(m) || "beat", cue = fieldOf(objOf(m), "cue");
      let h = `<div class="mi k-${k}" data-m="${esc(m)}">${cue ? `<div class="cu">${esc(cue)}</div>` : ""}${title(m).replace("%", icon(k, 13))}${facts(m)}</div>`;
      if (k === "decision" && below) { below.push(m); return `<div class="to8"><span class="ar">↓</span><span>${esc(titleOf(m))}</span><small data-to="${esc(m)}">below</small></div>`; }
      if (k === "decision") return h + `<div class="sub8">${choices(m).map(x => `<div>${opHead(x)}${outcome(m, x)}</div>`).join("")}</div>`;
      h += away(m).map(goTo).join("");
      return h + (tr.kids[m] || []).map(x => kindOf(x) === "exit" ? wayOut(x) : mini(x)).join("");
    }
    function fork(m) {
      const xs = choices(m); if (!xs.length) return "";
      const n = xs.length === 4 ? 2 : Math.min(3, xs.length), outs8 = xs.map(x => outcome(m, x)), hs = xs.map((x, i) => opHead(x) + outs8[i]), len = h => h.replace(/<[^>]*>/g, "").length + 60;
      if (outs8.every(h => !h || /^<div class="to8">/.test(h))) return `<div class="fk gos">${hs.map(h => `<div class="op">${h}</div>`).join("")}</div>`;
      const w = Array.from({length: n}, (_, i) => Math.sqrt(Math.max(...hs.filter((h, j) => j % n === i).map(len)))), lo = Math.max(...w) * .62;
      return `<div class="fk" style="--cols:${w.map(x => `minmax(0,${Math.max(lo, x).toFixed(1)}fr)`).join(" ")}">${hs.map(h => `<div class="op">${h}</div>`).join("")}</div>`;
    }
    let before = null, below = null;   // below: decisions met inside the fork being drawn
    function spine(m, last) {   // a card on the spine, then what follows it
      const k = kindOf(m) || "beat", c = objOf(m), cue = fieldOf(c, "cue"), lab = tr.lab[m] || [], par = tr.par[m], kids = tr.kids[m] || [];
      if (k === "exit") { const h = kids.map((x, i) => spine(x, last && i === kids.length - 1)).join(""); return par ? `<div class="sp8 end k-exit"><span></span><span></span>${wayOut(m)}</div>` + h : h; }
      const hops = k === "decision" ? "" : away(m).map(goTo).join(""), also = tr.also[m] || [];
      const left = cue ? esc(cue) : lab.length ? lab.map(esc).join(" or ") : par ? "then" : before ? "" : "opens";
      const after = par && before !== par ? `<small>after ${esc(titleOf(par))}</small>` : "";
      const more = also.length ? `<small>or after ${esc(also.map(titleOf).join(", "))}</small>` : "";
      before = m;
      let fk = "", deeper = [];
      if (k === "decision") { const was = below; below = deeper; fk = fork(m); below = was; }
      const sub = k === "decision" ? [] : kids;
      const open = sub.length || fk;
      return `<div class="sp8 k-${k}${isCrit(c) ? " crit" : ""}${open ? "" : " end"}" data-m="${esc(m)}"><div class="cu${cue ? "" : " lo"}">${left}${after}${more}</div><div class="nd"><i>${icon(k, 13)}</i></div><div>${title(m).replace("%", "")}${facts(m)}${hops}</div></div>` + fk + deeper.map(x => spine(x, last)).join("") +
        sub.map((x, i) => spine(x, last && i === sub.length - 1)).join("");
    }
    const roots = (tr.kids[""] || []).filter(m => kindOf(m) !== "exit" || (tr.kids[m] || []).length);
    const flow = roots.map(m => { before = before && m; return `<div class="th">${spine(m, true)}</div>`; }).join("");

    /* people: everyone not a player character, from the start or on a card */
    const here = (o.present || []).filter(n => !pcOf(n)), folk = [...new Set([...here, ...all.flatMap(whoOf).filter(n => !pcOf(n))])];
    const person = n => { const p = N[n] || {}, ln = (lab, v) => v ? `<p><span>${lab}</span>${loud(v)}</p>` : "";
      return `<div class="pp"><b>${esc(n)}</b>${here.includes(n) ? "" : ` <small>comes in</small>`}${ln("Sounds", p.voice)}${ln("Wants", p.wants)}${ln("Fears", p.fear)}</div>`; };
    const pcs = presentLanes(sid).filter(k => PCS.some(p => p.key === k)), later2 = [...new Set([...comers(sid), ...all.flatMap(whoOf)].map(pcOf))].filter(k => k && k !== "party" && !pcs.includes(k));
    const pill = (k, inn) => { const l = PCS.find(p => p.key === k); return l ? `<span${inn ? ` class="in"` : ""} style="--c:${esc(l.colour)}">${esc(l.short)}${inn ? " <small>comes in</small>" : ""}</span>` : ""; };

    /* what must not slip out, what pushes from outside */
    const outHere = new Set(all.map(m => kindOf(m) === "reveal" && objOf(m).reveals).filter(Boolean));
    const hush = [...new Set(all.filter(m => m.startsWith("p:")).flatMap(m => objOf(m).req.filter(r => r.k === "hidden" && r.a && !isOut(r.a) && !outHere.has(r.a)).map(r => r.a)))];
    const mine = lanesOf(sid), push = looseIn(t).filter(x => lanesOf(x).some(k => mine.includes(k) || k === HOMELESS));
    const side = m => { const k = kindOf(m) || "beat", c = objOf(m), cue = fieldOf(c, "cue"), [f, n] = parseClock(c.clock);
      return `<div class="hold k-${k}">${cue ? `<div class="cu">${esc(cue)}</div>` : ""}${title(m).replace("%", icon(k, 13))}${k === "clock" ? `<div class="cl8">${Array.from({length: n}, (_, i) => `<i${i < f ? ` class="f"` : ""}></i>`).join("")}</div>` : ""}${facts(m)}` +
        (k === "decision" ? `<div class="sub8">${choices(m).map(x => `<div>${opHead(x)}${outcome(m, x)}</div>`).join("")}</div>` : k === "exit" ? wayOut(m) : away(m).map(goTo).join("")) + `</div>`; };
    const bx = (lab, h) => h ? `<div class="bx"><h4>${lab}</h4>${h}</div>` : "";

    /* ways out */
    const i = list.indexOf(sid), next = isFloat(sid) ? null : list.slice(i + 1).find(x => !isFloat(x)), dest = m => optionsOf(m).filter(x => x.to);
    const ways = outs.map(m => { const c = objOf(m), cue = fieldOf(c, "cue"), d = dest(m), gone = whoOf(m);
      return `<div class="wo8"><span class="lt">${letter(m)}</span><div>${cue ? `<div class="cu">${esc(cue)}</div>` : ""}<b>${esc(titleOf(m))}</b>${facts(m)}` +
        (d.length ? d.map(x => `<div class="gt">${x.label ? esc(x.label) + ": " : ""}${x.off ? esc(titleOf(x.to)) : where(x.to, sid)}</div>`).join("") : gone.length ? "" : `<div class="gt"><u>&nbsp;</u></div>`) + `</div></div>`; });
    if (next) ways.push(`<div class="wo8 nx"><span class="lt">${numIn(next)}</span><div><div class="cu">Next in order</div><b>${esc(titleOf(next))}</b>${objOf(next).where || objOf(next).when ? `<p>${esc([objOf(next).where, objOf(next).when].filter(Boolean).join(" · "))}</p>` : ""}</div></div>`);
    else if (!isFloat(sid)) ways.push(`<div class="wo8 nx"><span class="lt">■</span><div><div class="cu">Next in order</div><b>Last scene of ${esc(t)}</b></div></div>`);
    else ways.push(`<div class="wo8 nx"><span class="lt">~</span><div><div class="cu">Floating</div><b>Back to where you were</b><p>${limText(sid)}</p></div></div>`);

    const why = thoughts(o.purpose), qs = why.filter(x => x.endsWith("?")), rest = why.filter(x => !x.endsWith("?")), sit = textOf(sid);
    const ask = `<div><span class="lb8">${qs.length || !why.length ? "The question" : "What it is for"}</span>${why.length ? `<div class="qq">${loud((qs.length ? qs : rest).join(" "))}</div>${qs.length && rest.length ? `<p>${loud(rest.join(" "))}</p>` : ""}` : `<div class="wln"></div>`}</div>`;
    const [aloud, sense] = openOf(fieldOf(o, "opens")), blank = n => "<div class=\"wln\"></div>".repeat(n);
    const opens = `<div class="op8"><span class="lb8">Opens on</span><div class="al">${aloud.length ? aloud.map(x => `<p>${esc(x)}</p>`).join("") : blank(3)}</div>` +
      `<div class="sn8">${SENSES.map(k => `<div><b>${k}</b><div>${sense[k] ? esc(sense[k]) : blank(1)}</div></div>`).join("")}</div></div>`;
    const none = `<p class="none">Nothing</p>`, strip = list.map(x => `<i class="${x === sid ? "on" : ""}${isFloat(x) ? " fl" : ""}">${numIn(x) || "~"}</i>`).join("");
    const head = full => `<div class="hd${full ? "" : " sl"}"><span class="no">${numIn(sid) || "~"}</span><div><h3>${esc(titleOf(sid))}</h3>` + (full ? `<div class="wh">${[o.where, o.when].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join("")}</div>` +
      (pcs.length || later2.length ? `<div class="cast">${pcs.map(k => pill(k)).join("")}${later2.map(k => pill(k, 1)).join("")}</div>` : "") : "") + `</div><div class="rt8"><b>${esc(t)}</b>${full ? esc(sName(t)) : ""}<div class="dots">${strip}</div></div></div>`;
    const foot = `<div class="ft8"><span>Wilds of Ossë · ${esc(t)}${sName(t) ? " · " + esc(sName(t)) : ""}</span><span class="pn8"></span></div>`;
    return {head, foot, flow, any: any.map(side), name: numIn(sid) ? `Scene ${numIn(sid)} of ${list.filter(x => !isFloat(x)).length}` : "Floating scene",
      set: [ask, opens, `<div class="tw"><div>${bx("Where things stand", sit ? words(sit) : none)}</div><div>${bx("Keep hidden", hush.length ? `<ul class="hush">${hush.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : none)}${bx("Pushing in", push.map(side).join(""))}</div></div>`],
      people: folk.length ? `<div class="bx"><h4>People</h4><div class="ppl">${folk.map(person).join("")}</div></div>` : bx("People", `<p class="none">Nobody yet</p>`),
      label: `<span class="lb8">When this happens, this follows${roots.length > 1 ? ` <b>· ${roots.length} threads, each starts on its cue</b>` : ""}</span>`,
      ways: `<div class="wy" style="--n:${Math.min(3, ways.length)}"><span class="lb8">Ways out</span>${ways.join("")}</div>`};
  }
  const SENSES = ["See", "Hear", "Smell", "Going on"];
  function openOf(t) {   // Opens on: lines that begin See:, Hear:, Smell: or Going on: are the palette; the rest is said aloud
    const aloud = [], sense = {};
    String(t || "").split(/\n+/).map(x => x.trim()).filter(Boolean).forEach(x => { const m = x.match(/^(see|hear|smell|going on)\s*:\s*(.*)$/i), k = m && SENSES.find(y => y.toLowerCase() === m[1].toLowerCase()); if (k) sense[k] = (sense[k] ? sense[k] + " " : "") + m[2]; else aloud.push(x); });
    return [aloud, sense];
  }

  /* pages: what does not fit goes on to the next one; the type never shrinks */
  function build(host, sid, list) {
    const P8 = page(sid, at, list), made = [];
    const sheet = html => { const z = document.createElement("div"); z.className = "pz"; z.dataset.s = sid; z.innerHTML = `<div class="pg">${html}${P8.foot}</div>`; curl(z); host.append(z); made.push(z); return z.firstChild; };
    const curl = e => { const w = document.createTreeWalker(e, 4); while (w.nextNode()) { const n = w.currentNode; if (n.data.includes("'")) n.data = n.data.replace(/(^|[\s(:])'(?=\S)/g, "$1‘").replace(/'/g, "’"); } return e; };
    const kids = h => { const x = document.createElement("div"); x.innerHTML = h; return [...curl(x).children]; }, spill = e => e.scrollHeight > e.clientHeight + 1;
    const lines = (box, cls = "bx") => { const n = document.createElement("div"); n.className = "nt8"; box.append(n); if (n.clientHeight > 66) n.innerHTML = `<h4>Notes</h4>` + "<div class=\"wln\"></div>".repeat(Math.floor((n.clientHeight - 20) / 25.4)); };
    function lay1(mode) {
      made.forEach(z => z.remove()); made.length = 0;
      const on = h => { const pg = sheet(h); if (mode) pg.classList.add(...(mode > 1 ? ["rn8", "gist"] : ["rn8"])); return pg; };
      let pg = on(`${P8.head(1)}<div class="st8">${P8.set.join("")}</div>`), st = pg.querySelector(".st8");
      const ppl = kids(P8.people)[0]; st.append(ppl);
      if (spill(st)) { ppl.remove(); lines(st); pg = on(`${P8.head(0)}<div class="st8"></div>`); st = pg.querySelector(".st8"); st.append(ppl); }
      lines(st);
      /* the spine, a card and its fork kept together */
      const units = [];
      kids(P8.flow).forEach(th => [...th.children].forEach((e, i) => { if (!i) e.classList.add("th1"); if (e.matches(".fk") && units.length) units[units.length - 1].push(e); else units.push([e]); }));
      const anys = P8.any.flatMap(kids), play = () => { const g = on(`${P8.head(0)}<div class="bd8"><div class="mn">${P8.label}</div><div class="sd"></div></div>`), sd = g.querySelector(".sd");
        if (anys.length) { const b = kids(`<div class="bx"><h4>Any time</h4></div>`)[0]; sd.append(b); while (anys.length) { b.append(anys[0]); if (spill(sd) && b.children.length > 2) { anys[0].remove(); break; } anys.shift(); } }
        return g; };
      pg = play(); let mn = pg.querySelector(".mn");
      const fresh = () => { pg = play(); mn = pg.querySelector(".mn"); };
      const tail = () => {   // the thread the page ends in, if it started here under another and is short
        const e = [...mn.children].filter(x => x.matches(".th1")).pop(); if (!e || e === mn.children[1]) return [];
        const out = []; for (let x = e; x; x = x.nextElementSibling) out.push(x);
        return out[out.length - 1].getBoundingClientRect().bottom - e.getBoundingClientRect().top < mn.clientHeight * .4 * mn.getBoundingClientRect().height / (mn.offsetHeight || 1) ? out : []; };
      for (const u of units) {
        mn.append(...u); if (!spill(mn)) continue;
        u.forEach(e => e.remove());
        if (mn.children.length > 1) { const t8 = u[0].matches(".th1") ? [] : tail(); t8.forEach(e => e.remove()); fresh(); mn.append(...t8, ...u); if (t8.length && spill(mn)) { u.forEach(e => e.remove()); fresh(); mn.append(...u); } }
        else mn.append(...u);
        if (spill(mn) && u.length > 1) {   // a fork taller than a page: its choices one under the other, over as many pages as they take
          const fk = u[1], ops = [...fk.children]; ops.forEach(x => x.remove()); fk.style.setProperty("--cols", "1fr"); let f = fk;
          ops.forEach(x => { f.append(x); if (spill(mn) && f.children.length > 1) { x.remove(); fresh(); f = fk.cloneNode(false); f.classList.add("more"); mn.append(f); f.append(x); } });
        }
      }
      if (!units.length) mn.append(...kids(`<p class="none">No cards in this scene yet</p>`));
      while (anys.length) fresh();
      const w = kids(P8.ways)[0]; pg.insertBefore(w, pg.querySelector(".ft8"));
      if (spill(mn)) {   // the ways out need room: the last cards go with them to a new page
        w.remove(); const move = []; pg.insertBefore(w, pg.querySelector(".ft8"));
        while (spill(mn) && mn.children.length > 2) { let e = mn.lastElementChild; move.unshift(e); e.remove(); if (e.matches(".fk") && mn.lastElementChild.matches(".sp8")) { e = mn.lastElementChild; if (mn.children.length > 2) { move.unshift(e); e.remove(); } } }
        if (move.length && !move[0].matches(".th1")) { const t8 = tail(); t8.forEach(e => e.remove()); move.unshift(...t8); }
        w.remove(); fresh(); mn.append(...move); pg.insertBefore(w, pg.querySelector(".ft8"));
      }
      made.forEach(z => { const sd = z.querySelector(".sd"); if (sd) lines(sd); });
      const pageOf = m => made.findIndex(z => z.querySelector(`[data-m="${CSS.escape(m)}"]`));
      made.forEach((z, i) => z.querySelectorAll("small[data-to]").forEach(e => { const n = pageOf(e.dataset.to); e.textContent = n < 0 ? "in this scene" : n === i ? (e.compareDocumentPosition(z.querySelector(`[data-m="${CSS.escape(e.dataset.to)}"]`)) & 4 ? "below" : "above") : `page ${n + 1}`; }));
      made.forEach((z, i) => { z.querySelector(".pn8").textContent = `${P8.name} · page ${i + 1} of ${made.length}${mode > 1 ? " · shortened to fit" : ""}`; });
      return made.length;
    }
    let n = lay1(0), mode = 0; while (n > MAX && mode < 2) n = lay1(++mode);
    return {n, cut: mode > 1, off: made.some(z => [".mn", ".st8", ".sd"].some(c => { const e = z.querySelector(c); return e && spill(e); }))};
  }
  async function show(t) {
    at = t; const list = scenesIn(t);
    if (!document.querySelector("#pdffont")) document.head.insertAdjacentHTML("beforeend", `<link id="pdffont" rel="stylesheet" href="${FONTS}">`);
    let box = $("#pdf"); if (!box) { box = document.createElement("div"); box.id = "pdf"; document.body.append(box); }
    box.hidden = false; document.body.classList.add("sheets"); closeDrawer();
    box.innerHTML = `<div class="pbar"><h2>${esc(t)}${sName(t) ? " · " + esc(sName(t)) : ""}</h2><div class="ppick" role="group" aria-label="Scenes to include">${list.map(x => `<button data-inc="${esc(x)}" aria-pressed="${!off.has(x)}" title="Include this scene or leave it out">${esc(called(x))}</button>`).join("")}</div><span class="sp"></span>` +
      `<button class="go" data-print>Print or save as PDF</button><button data-x>Close</button><div class="pnote"></div></div><div class="pages"></div>`;
    box.querySelector("[data-x]").onclick = close;
    box.querySelectorAll("[data-inc]").forEach(b => b.onclick = () => { const x = b.dataset.inc; off.has(x) ? off.delete(x) : off.add(x); b.setAttribute("aria-pressed", !off.has(x)); lay(); });
    box.querySelector("[data-print]").onclick = print8;
    await new Promise(r => { const l = document.querySelector("#pdffont"); if (l.sheet) r(); else { l.onload = l.onerror = r; setTimeout(r, 2500); } });
    await Promise.race([Promise.all(["400", "500", "600", "700"].map(w => document.fonts.load(`${w} 14px "IBM Plex Sans"`)).concat(["400", "600"].map(w => document.fonts.load(`${w} 14px "IBM Plex Sans Condensed"`)), document.fonts.load('600 20px "Cinzel"'))), new Promise(r => setTimeout(r, 2500))]).catch(() => {});
    if (at === t) lay();
  }
  function lay() {
    const host = $("#pdf .pages"), list = scenesIn(at), on = list.filter(x => !off.has(x)), y = host.scrollTop;
    host.innerHTML = ""; const cut = [], over = [], many = [];
    on.forEach(x => { const f = build(host, x, list), n = titleOf(x); if (f.off) over.push(n); else if (f.n > MAX) many.push(`${n} (${f.n})`); else if (f.cut) cut.push(n); });
    scale(); host.scrollTop = y;
    const inAny = new Set(on.flatMap(sid => looseIn(at).filter(x => lanesOf(x).some(k => lanesOf(sid).includes(k) || k === HOMELESS)))), lost = looseIn(at).filter(x => !inAny.has(x));
    $("#pdf .pnote").textContent = [list.length ? "" : "No scenes in this session yet.", over.length ? `Something runs off a page in: ${over.join(", ")}.` : "", many.length ? `More than ${MAX} pages: ${many.join(", ")}. Split ${many.length > 1 ? "each" : "it"} into two scenes.` : "",
      cut.length ? `Shortened to fit ${MAX} pages: ${cut.join(", ")}. Each card keeps its first lines.` : "", on.length && lost.length ? `On no page, being in no scene: ${lost.map(titleOf).join(", ")}.` : ""].filter(Boolean).join(" ");
    $("#pdf [data-print]").disabled = !on.length;
  }
  function scale() {   // on screen a page is as wide as the window lets it be; on paper it is Letter
    const host = $("#pdf .pages"); if (!host || $("#pdf").hidden) return;
    const k = Math.min(1.25, (host.clientWidth - 24) / 816);
    host.querySelectorAll(".pz").forEach(z => { z.style.width = 816 * k + "px"; z.style.height = 10.98 * 96 * k + "px"; z.firstChild.style.transform = `scale(${k})`; });
  }
  function print8() { const was = document.title; document.title = `${at}${sName(at) ? " " + sName(at) : ""} scene sheets`; addEventListener("afterprint", () => { document.title = was; }, {once: true}); print(); }
  function close() { at = ""; $("#pdf").hidden = true; $("#pdf").innerHTML = ""; document.body.classList.remove("sheets"); }
  addEventListener("resize", scale);
  addEventListener("keydown", e => { if (e.key === "Escape" && at) { e.stopImmediatePropagation(); close(); } }, true);
  return {show};
})();
"""


def npcs(site, build):
    """How each person sounds and what they want, for the sheets: {name: {voice, wants, fear}} from the notes' properties."""
    out = {}
    def say(v):
        v = LINK.sub(lambda m: m.group(2) or m.group(1), str(v or "")).strip()
        return v + "'" if len(re.findall(r"(?:^|[\s(:])'", v)) > len(re.findall(r"[.,!?]'", v)) else v   # reading the property took a closing quote off its end
    for n in site.g["nodes"]:
        if n["type"] != "npc":
            continue
        fm = build.frontmatter(site.text(n["id"]))
        got = {k: say(fm.get(k)) for k in ("voice", "wants", "fear") if say(fm.get(k))}
        if got:
            out[n["id"]] = got
    return out
