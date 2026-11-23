/* Search tabs for the Ossë pages: "In the world" filters this page; "Rules and items" asks Open5e (SRD only). */
(() => {
const $ = s => document.querySelector(s), API = "https://api.open5e.com/v2/";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const q = $("#q"), tabs = document.querySelectorAll("[data-tab]");
let tab = "world", timer = 0, seq = 0, conds = null;
const store = { get(k){ try { return localStorage.getItem(k); } catch(e) { return null; } }, set(k,v){ try { localStorage.setItem(k,v); } catch(e) {} } };
function show(t){
  tab = t;
  tabs.forEach(b => b.setAttribute("aria-selected", b.dataset.tab === t));
  $("#world").hidden = t !== "world"; $("#rules").hidden = t !== "rules";
  q.placeholder = t === "world" ? "Find a name, alias or summary" : "Find a rule, spell, item, creature or condition";
  if (location.hash !== "#" + t && (t === "rules" || location.hash === "#rules")) history.replaceState(null, "", t === "rules" ? "#rules" : location.pathname);
  run();
}
function world(){
  const v = q.value.trim().toLowerCase();
  document.querySelectorAll(".entries li").forEach(li => { li.hidden = v && !li.dataset.k.includes(v); });
  let any = false;
  document.querySelectorAll("#world section").forEach(s => { const on = !v || s.querySelector("li:not([hidden])"); s.hidden = !on; any = any || on; });
  $("#none").hidden = any;
}
function md(s){
  const lines = String(s || "").split("\n"), out = []; let list = null, table = null;
  const inl = t => esc(t).replace(/\*\*\*(.+?)\*\*\*/g, "<b><i>$1</i></b>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*]+)\*/g, "$1<i>$2</i>").replace(/_(.+?)_/g, "<i>$1</i>");
  const flush = () => { if (list) { out.push("<ul>" + list.join("") + "</ul>"); list = null; } if (table) { out.push("<table>" + table.join("") + "</table>"); table = null; } };
  for (const ln of lines) {
    const t = ln.trim();
    if (/^\|/.test(t)) { if (/^\|[\s:|-]+\|$/.test(t)) continue; table = table || []; const c = t.replace(/^\||\|$/g, "").split("|");
      table.push("<tr>" + c.map(x => (table.length ? "<td>" : "<th>") + inl(x.trim()) + (table.length ? "</td>" : "</th>")).join("") + "</tr>"); continue; }
    if (/^[-*] /.test(t)) { if (table) flush(); list = list || []; list.push("<li>" + inl(t.slice(2)) + "</li>"); continue; }
    flush();
    if (/^#+ /.test(t)) out.push("<h4>" + inl(t.replace(/^#+ /, "")) + "</h4>"); else if (t) out.push("<p>" + inl(t) + "</p>");
  }
  flush(); return out.join("");
}
const mod = v => (v >= 10 ? "+" : "") + Math.floor((v - 10) / 2);
function detail(o, model){
  const h = [`<h3>${esc(o.name)}</h3>`], meta = [], doc = o.document?.display_name || o.document?.name || "";
  if (model === "Spell") {
    meta.push(`${o.level ? "Level " + o.level : "Cantrip"} ${esc(o.school?.name || o.school || "")}`.trim());
    const comp = [o.verbal && "V", o.somatic && "S", o.material && "M" + (o.material_specified ? ` (${o.material_specified})` : "")].filter(Boolean).join(", ");
    h.push(`<dl class="kv"><dt>Casting time</dt><dd>${esc(o.casting_time)}${o.ritual ? " or ritual" : ""}</dd><dt>Range</dt><dd>${esc(o.range_text || o.range)}</dd>
      <dt>Components</dt><dd>${esc(comp)}</dd><dt>Duration</dt><dd>${esc(o.duration)}${o.concentration ? ", concentration" : ""}</dd>
      ${o.classes?.length ? `<dt>Classes</dt><dd>${esc(o.classes.map(c => c.name || c).join(", "))}</dd>` : ""}</dl>`);
    h.push(md(o.desc)); if (o.higher_level) h.push(`<p><b>At higher levels.</b> ${esc(o.higher_level)}</p>`);
  } else if (model === "Creature") {
    meta.push(`${esc(o.size?.name || "")} ${esc(o.type?.name || "")}${o.alignment ? ", " + esc(o.alignment) : ""}`);
    const sp = o.speed_all || o.speed || {}, speed = Object.entries(sp).filter(([k, v]) => v && k !== "unit" && k !== "hover").map(([k, v]) => (k === "walk" ? "" : k + " ") + v + " ft.").join(", ");
    const ab = o.ability_scores || {}, keys = ["strength","dexterity","constitution","intelligence","wisdom","charisma"];
    h.push(`<dl class="kv"><dt>Armour class</dt><dd>${esc(o.armor_class)}${o.armor_detail ? " (" + esc(o.armor_detail) + ")" : ""}</dd>
      <dt>Hit points</dt><dd>${esc(o.hit_points)}${o.hit_dice ? " (" + esc(o.hit_dice) + ")" : ""}</dd><dt>Speed</dt><dd>${esc(speed)}</dd>
      <dt>Challenge</dt><dd>${esc(o.challenge_rating_text || o.challenge_rating)}${o.proficiency_bonus ? " · PB +" + o.proficiency_bonus : ""}</dd>
      ${o.passive_perception ? `<dt>Passive Perception</dt><dd>${o.passive_perception}</dd>` : ""}${o.languages?.as_string ? `<dt>Languages</dt><dd>${esc(o.languages.as_string)}</dd>` : ""}</dl>
      <table class="abil"><tr>${keys.map(k => `<th>${k.slice(0,3).toUpperCase()}</th>`).join("")}</tr><tr>${keys.map(k => `<td>${ab[k] ?? ""} (${ab[k] != null ? mod(ab[k]) : ""})</td>`).join("")}</tr></table>`);
    const part = (title, xs) => xs?.length ? `<h4>${title}</h4>` + xs.map(x => `<p><b>${esc(x.name)}.</b> ${md(x.desc).replace(/^<p>|<\/p>$/g, "")}</p>`).join("") : "";
    const acts = o.actions || [], by = t => acts.filter(a => (a.action_type || "ACTION") === t);
    h.push(part("Traits", o.traits) + part("Actions", by("ACTION")) + part("Bonus actions", by("BONUS_ACTION")) + part("Reactions", by("REACTION")) + part("Legendary actions", by("LEGENDARY_ACTION")));
  } else if (model === "MagicItem" || model === "Item") {
    meta.push([o.category?.name, o.rarity?.name, o.requires_attunement ? "requires attunement" + (o.attunement_detail ? " " + o.attunement_detail : "") : ""].filter(Boolean).map(esc).join(", "));
    if (model === "Item") h.push(`<dl class="kv">${o.cost ? `<dt>Cost</dt><dd>${esc(o.cost)} gp</dd>` : ""}${o.weight ? `<dt>Weight</dt><dd>${esc(o.weight)} ${esc(o.weight_unit || "lb")}</dd>` : ""}
      ${o.weapon ? `<dt>Damage</dt><dd>${esc(o.weapon.damage_dice || "")} ${esc(o.weapon.damage_type?.name || "")}</dd>${o.weapon.properties?.length ? `<dt>Properties</dt><dd>${esc(o.weapon.properties.map(p => p.property?.name || p.name || p).join(", "))}</dd>` : ""}` : ""}
      ${o.armor ? `<dt>Armour class</dt><dd>${esc(o.armor.ac_display || o.armor.ac_base)}</dd>` : ""}</dl>`);
    h.push(md(o.desc));
  } else if (model === "Condition" && o.descriptions?.length) {
    const ed = document.querySelector("[name=ed]:checked").value, d = o.descriptions.find(x => x.document === ed) || o.descriptions.find(x => x.document?.startsWith("srd")) || o.descriptions[0];
    h.push(md(d.desc)); o.document = {display_name: d.document === "srd-2024" ? "SRD 5.2 (2024 rules)" : d.document === "srd-2014" ? "SRD 5.1 (2014 rules)" : d.document};
  } else { h.push(md(o.desc)); }
  if (meta.filter(Boolean).length) h.splice(1, 0, `<p class="meta">${meta.join(" · ")}</p>`);
  h.push(`<p class="src">${esc(doc)}</p>`);
  return h.join("");
}
async function open(route, key, model){
  const box = $("#rshow"); box.innerHTML = "<p class='muted'>Opening</p>";
  try { const r = await fetch(API + route.replace(/^v2\//, "") + encodeURIComponent(key) + "/"); box.innerHTML = r.ok ? detail(await r.json(), model) : "<p>Could not open that entry.</p>"; }
  catch(e) { box.innerHTML = "<p>Open5e can't be reached. Check the connection.</p>"; }
}
async function rules(){
  const v = q.value.trim(), ed = document.querySelector("[name=ed]:checked").value, me = ++seq, list = $("#rlist");
  $("#ddb").href = "https://www.dndbeyond.com/search?q=" + encodeURIComponent(v);
  if (v.length < 2) { list.innerHTML = "<li class='muted'>Type at least two letters.</li>"; return; }
  list.innerHTML = "<li class='muted'>Searching</li>";
  try {
    if (!conds) { conds = []; try { const c = await (await fetch(API + "conditions/?limit=60&fields=key,name")).json(); conds = c.results.filter(x => !x.key.includes("_")).map(x => ({route: "v2/conditions/", object_pk: x.key, object_name: x.name, object_model: "Condition"})); } catch(e) {} }
    const j = await (await fetch(API + "search/?limit=30&document_pk=" + ed + "&query=" + encodeURIComponent(v))).json();
    if (me !== seq) return;
    const lv = v.toLowerCase(), rank = r => { const n = r.object_name.toLowerCase(); return n === lv ? 0 : n.startsWith(lv) ? 1 : n.includes(lv) ? 2 : 3; };
    const hits = conds.filter(c => c.object_name.toLowerCase().includes(lv)).concat(j.results || []).sort((a, b) => rank(a) - rank(b));
    list.innerHTML = hits.length ? hits.map((r, i) => `<li><button data-r="${esc(r.route)}" data-k="${esc(r.object_pk)}" data-m="${esc(r.object_model)}"><b>${esc(r.object_name)}</b><span>${esc(r.object_model.replace(/([a-z])([A-Z])/g, "$1 $2"))}</span></button></li>`).join("")
      : "<li class='muted'>Nothing in the SRD. Try D&amp;D Beyond below.</li>";
    const first = list.querySelector("button"); if (first && rank(hits[0]) <= 1) first.click(); else if (!first) $("#rshow").innerHTML = "";
  } catch(e) { if (me === seq) list.innerHTML = "<li class='muted'>Open5e can't be reached. Check the connection.</li>"; }
}
function run(){ if (tab === "world") world(); else { clearTimeout(timer); timer = setTimeout(rules, 250); } }
q.addEventListener("input", run);
tabs.forEach(b => b.addEventListener("click", () => show(b.dataset.tab)));
document.addEventListener("click", e => {
  const b = e.target.closest("#rlist button"); if (b) { document.querySelectorAll("#rlist button").forEach(x => x.classList.toggle("on", x === b)); open(b.dataset.r, b.dataset.k, b.dataset.m); }
  const g = e.target.closest("[data-go]"); if (g) { e.preventDefault(); show(g.dataset.go); }
});
document.querySelectorAll("[name=ed]").forEach(r => r.addEventListener("change", () => { store.set("osse-rules-ed", r.value); run(); }));
const ed = store.get("osse-rules-ed"); if (ed) { const r = document.querySelector(`[name=ed][value="${ed}"]`); if (r) r.checked = true; }
const p = new URLSearchParams(location.search); if (p.get("q")) q.value = p.get("q");
show(location.hash === "#rules" ? "rules" : "world");
})();
