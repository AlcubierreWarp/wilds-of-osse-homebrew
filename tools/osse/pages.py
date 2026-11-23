#!/usr/bin/env python3
"""Build a DM page for every vault note, plus an index, into this repo's vault/ folder.
  python3 tools/osse/pages.py          rebuild every page (build.py also does this after each real build)
Each page is generated from the note and the vault graph: no text is written by hand or by Claude.
vault/ is a DM screen. It holds game secrets, prep and plans, so link it only from the hub's game master section.
Only files whose content changed are rewritten, so a build leaves a small diff."""
import html, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "vault")
VAULT = os.environ.get("OSSE_VAULT") or os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Ossë")
SITE = "https://osse.thomashuet.ca/vault/"
sys.path.insert(0, HERE)
import build  # frontmatter reader

ORDER = [("session", "Sessions"), ("pc", "Player characters"), ("party", "The party"), ("npc", "People"),
         ("faction", "Factions"), ("place", "Places"), ("item", "Things"), ("lore", "Lore"),
         ("secret", "Secrets"), ("thread", "Threads"), ("plan", "Plans")]
LABEL = {t: l for t, l in ORDER}
SINGULAR = {"session": "Session", "pc": "Player character", "party": "Party", "npc": "Person", "faction": "Faction",
            "place": "Place", "item": "Thing", "lore": "Lore", "secret": "Secret", "thread": "Thread", "plan": "Plan"}
FAMILIES = ["kin", "social", "role", "place", "thing", "deed", "knowledge", "faith", "lore", "story", "related"]
SKIP_SECTIONS = {"Connections", "Past"}          # shown from the graph instead
PROPS = [("player", "Player"), ("class", "Class"), ("race", "Race"), ("pronouns", "Pronouns"), ("voice", "Voice"),
         ("wants", "Wants"), ("fear", "Fear"), ("leader", "Leader"), ("known_by", "Known by"), ("opened", "Opened"),
         ("closed", "Closed"), ("played_on", "Played on"), ("in_world", "In the world"), ("thread", "Thread"),
         ("played", "Played"), ("pruned", "Pruned"), ("pruned_by", "Pruned because"), ("map", "Map")]
LINK = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "note"


class Site:
    def __init__(self, g):
        self.g = g
        self.nodes = {n["id"]: n for n in g["nodes"]}
        self.cur = g.get("current_session", 0)
        self.slugs, used = {}, set()
        for n in sorted(g["nodes"], key=lambda n: n["id"]):
            s = slug(n["id"])
            if s in used:
                s = f"{s}-{n['type']}"
            used.add(s); self.slugs[n["id"]] = s
        self.alias = {}
        for n in g["nodes"]:
            for a in [n["id"]] + [str(x) for x in n.get("aliases", [])]:
                self.alias.setdefault(a.lower(), n["id"])

    def href(self, name):
        nid = self.alias.get(name.strip().lower())
        return (self.slugs[nid] + ".html", nid) if nid else (None, None)

    def a(self, name, text=None):
        h, nid = self.href(name)
        t = html.escape(text or name)
        return f'<a href="{h}">{t}</a>' if h else f'<span class="nolink">{t}</span>'

    # ---------- inline markdown ----------
    def inline(self, s):
        out, last = [], 0
        for m in LINK.finditer(s):
            out.append(self._fmt(s[last:m.start()])); out.append(self.a(m.group(1), m.group(2))); last = m.end()
        out.append(self._fmt(s[last:]))
        return "".join(out)

    def _fmt(self, s):
        s = html.escape(s)
        s = re.sub(r"\*\((S\d+(?:\s*→\s*S?\d*)?|prep)\)\*", lambda m: tag(m.group(1)), s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" rel="noopener">\1</a>', s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<i>\1</i>", s)
        return s

    # ---------- block markdown ----------
    def blocks(self, lines):
        out, i = [], 0
        while i < len(lines):
            ln = lines[i]
            if not ln.strip():
                i += 1; continue
            if ln.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                        rows.append(cells)
                    i += 1
                if len(rows) > 1:  # a header with no rows shows nothing
                    head, rest = rows[0], rows[1:]
                    out.append('<table><thead><tr>' + "".join(f"<th>{self.inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                               + "".join("<tr>" + "".join(f"<td>{self.inline(c)}</td>" for c in r) + "</tr>" for r in rest) + "</tbody></table>")
                continue
            if ln.startswith(">"):
                q = []
                while i < len(lines) and lines[i].startswith(">"):
                    q.append(lines[i][1:].strip()); i += 1
                m = re.match(r"\[!(\w+)\]\s*(.*)", q[0]) if q else None
                kind, title = (m.group(1).lower(), m.group(2) or m.group(1)) if m else ("quote", "")
                body = [x for ln_ in (q[1:] if m else q) for x in (ln_, "")]  # each quoted line is its own paragraph
                out.append(f'<div class="callout {html.escape(kind)}">' + (f'<div class="ch">{self.inline(title)}</div>' if title else "")
                           + self.blocks(body) + "</div>")
                continue
            if re.match(r"\s*[-*] ", ln):
                items = []
                while i < len(lines) and re.match(r"\s*[-*] ", lines[i]):
                    depth = (len(lines[i]) - len(lines[i].lstrip())) // 2
                    items.append((depth, lines[i].strip()[2:])); i += 1
                out.append(self.ul(items))
                continue
            if ln.startswith("```"):
                i += 1; code = []
                while i < len(lines) and not lines[i].startswith("```"):
                    code.append(lines[i]); i += 1
                i += 1
                out.append(f"<pre>{html.escape(chr(10).join(code))}</pre>")
                continue
            if ln.startswith("#"):
                out.append(f"<h4>{self.inline(ln.lstrip('#').strip())}</h4>"); i += 1; continue
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"\s*([-*] |\||>|#|```)", lines[i]):
                para.append(lines[i].strip()); i += 1
            out.append(f"<p>{self.inline(' '.join(para))}</p>")
        return "".join(out)

    def ul(self, items):
        out, depth = ["<ul>"], 0
        for d, text in items:
            while d > depth: out.append("<ul>"); depth += 1
            while d < depth: out.append("</ul>"); depth -= 1
            box = re.match(r"\[( |x)\]\s*(.*)", text)
            out.append(f'<li class="task{" done" if box.group(1) == "x" else ""}">{self.inline(box.group(2))}</li>' if box
                       else f"<li>{self.inline(text)}</li>")
        out.append("</ul>" * (depth + 1))
        return "".join(out)


def tag(when):
    w = str(when).strip()
    cls = "prep" if w == "prep" else "draft" if w == "draft" else "canon"
    return f'<span class="tag {cls}">{html.escape(w)}</span>'


def dots(w):
    w = max(0, min(5, int(w or 0)))
    return f'<span class="dots" title="weight {w} of 5">{"●" * w}<i>{"●" * (5 - w)}</i></span>'


def when(e):
    if e.get("layer") == "draft": return "plan"
    if e.get("date") is not None: return f"S{e['date']}"
    s, en = e.get("start"), e.get("end")
    if s is not None or en is not None:
        return f"S{s if s is not None else '?'} → " + (f"S{en}" if en is not None else "")
    return "prep" if e.get("layer") == "prep" else ""


def sections(text):
    body = text.split("\n---", 1)[1].split("\n", 1)[1] if text.startswith("---") and "\n---" in text[3:] else text
    out, cur = [("", [])], None
    for ln in body.splitlines():
        if ln.startswith("## "):
            out.append((ln[3:].strip(), []))
        elif ln.startswith("# ") and not out[-1][1] and len(out) == 1:
            continue  # a title line repeats the page title
        else:
            out[-1][1].append(ln)
    return [(h, ls) for h, ls in out if any(x.strip() for x in ls)]


def links_for(site, nid):
    cur, rows, past, plans, mentions, sessions = site.cur, {}, [], {}, set(), set()
    for e in site.g["edges"]:
        if nid not in (e["from"], e["to"]):
            continue
        fwd = e["from"] == nid
        other = e["to"] if fwd else e["from"]
        typ = e["type"] if fwd else e.get("inverse", e["type"])
        o = e["origin"]
        if o == "log":
            if site.nodes.get(other, {}).get("type") == "session": sessions.add(other)
            continue
        if o == "plain":
            if not fwd and site.nodes.get(other, {}).get("type") not in (None,):
                mentions.add(other)
            continue
        if e.get("layer") == "draft":
            if e.get("status") in ("draft", "ready"):
                plans.setdefault(e.get("plan"), []).append((e, fwd, other, typ))
            continue
        if (e.get("start") is not None and e["start"] > cur) or (e.get("date") is not None and e["date"] > cur):
            continue
        ended = e.get("end") is not None and e["end"] <= cur
        item = (int(e.get("weight") or 0), e.get("family") or "related", typ, other, e)
        if ended:
            past.append(item); continue
        k = (other, typ)
        if k not in rows or rows[k][0] < item[0] or (rows[k][0] == item[0] and o == "written"):
            rows[k] = item
    return list(rows.values()), past, plans, mentions, sessions


def link_rows(site, items):
    by = {}
    for it in items:
        by.setdefault(it[1], []).append(it)
    out = []
    for fam in FAMILIES + sorted(set(by) - set(FAMILIES)):
        if fam not in by: continue
        out.append(f'<div class="fam"><div class="famh">{html.escape(fam)}</div>')
        for w, _, typ, other, e in sorted(by[fam], key=lambda x: (-x[0], x[3])):
            ot = site.nodes.get(other, {}).get("type", "")
            note = e.get("note") or ""
            wn = when(e)
            out.append(f'<div class="lk">{dots(w)}<span class="ty">{html.escape(typ)}</span>'
                       f'<span class="to">{site.a(other)}<small>{html.escape(SINGULAR.get(ot, ot).lower())}</small></span>'
                       f'<span class="wn">{tag(wn) if wn else ""}</span>'
                       + (f'<span class="nt">{site.inline(note)}</span>' if note else "") + "</div>")
        out.append("</div>")
    return "".join(out)


def chips(site, n, fm):
    t = n["type"]; c = []
    kind = fm.get("kind") if isinstance(fm.get("kind"), str) else ""
    c.append(f'<span class="chip type">{html.escape(SINGULAR.get(t, t))}{" · " + html.escape(kind) if kind else ""}</span>')
    if n.get("state"):
        since = n.get("state_since")
        c.append(f'<span class="chip state s-{slug(n["state"])}">{html.escape(n["state"])}{(" " + tag(since)) if since else ""}</span>')
    for key, lab in (("location", "at"), ("in", "in"), ("holder", "held by")):
        v = fm.get(key)
        if isinstance(v, str) and v.strip():
            m = LINK.search(v)
            c.append(f'<span class="chip">{lab} {site.a(m.group(1)) if m else html.escape(v)}</span>')
    if t == "secret":
        r = n.get("revealed")
        c.append(f'<span class="chip state {"s-revealed" if r else "s-hidden"}">{"revealed " + tag(r) if r else "hidden from the party"}</span>')
    if t in ("plan", "thread") and n.get("status"):
        c.append(f'<span class="chip state s-{slug(n["status"])}">{html.escape(n["status"])}'
                 + (f' · target {html.escape(str(n["target"]))}' if n.get("target") else "") + "</span>")
    if n.get("stage") and n["stage"] != "canon":
        c.append(f'<span class="chip">{tag(n["stage"])}</span>')
    if n.get("first_seen"):
        c.append(f'<span class="chip">first seen {tag(n["first_seen"])}</span>')
    if fm.get("story_role"):
        c.append(f'<span class="chip">{html.escape(str(fm["story_role"]))}</span>')
    if n.get("importance"):
        c.append(f'<span class="chip" title="importance">{dots(n["importance"])}</span>')
    return "".join(c)


def head(title, depth=""):
    return (f'<!doctype html><html lang="en-CA"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex"><title>{html.escape(title)} · Ossë vault</title>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Spectral:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">'
            f'<link rel="stylesheet" href="{depth}vault.css"></head><body><div class="wrap">')


def topbar(site, crumb=""):
    return (f'<header><div><div class="eyebrow">Ossë vault · DM screen · after S{site.cur}</div>'
            f'<nav class="crumbs"><a href="index.html">All entries</a>{(" / " + crumb) if crumb else ""}</nav></div>'
            f'<a class="home" href="../">Hub</a></header>')


def page(site, n):
    nid, t = n["id"], n["type"]
    text = open(os.path.join(VAULT, n["path"]), encoding="utf-8").read()
    fm = build.frontmatter(text)
    rows, past, plans, mentions, sessions = links_for(site, nid)
    title = nid
    out = [head(title), topbar(site, f'<a href="index.html#{t}">{html.escape(LABEL.get(t, t))}</a>'), '<main class="sheet">']
    out.append(f'<h1>{html.escape(title)}</h1>')
    al = [str(a) for a in n.get("aliases", []) if str(a) != nid]
    if al:
        out.append(f'<div class="aka">also {html.escape(", ".join(al))}</div>')
    out.append(f'<div class="chips">{chips(site, n, fm)}</div>')
    if n.get("summary"):
        out.append(f'<p class="summary">{site.inline(str(n["summary"]))}</p>')
    props = []
    if fm.get("role"):
        props.append(("Role", fm["role"]))
    for k, lab in PROPS:
        v = fm.get(k)
        if v not in (None, "", []):
            props.append((lab, ", ".join(map(str, v)) if isinstance(v, list) else str(v)))
    if props:
        out.append('<dl class="props">' + "".join(f"<dt>{html.escape(l)}</dt><dd>{site.inline(v)}</dd>" for l, v in props) + "</dl>")
    logs = []
    for h, ls in sections(text):
        if h in SKIP_SECTIONS:
            continue
        body = site.blocks(ls)
        if not body:
            continue
        if h in ("Session Log", "Log"):
            logs.append(f'<section class="log"><h2>{html.escape(h)}</h2>{body}</section>'); continue
        out.append("<section>" + (f"<h2>{html.escape(h)}</h2>" if h else "") + body + "</section>")
    if rows:
        out.append(f'<section><h2>Links now <span>{len(rows)}, strongest first</span></h2>{link_rows(site, rows)}</section>')
    if past:
        out.append(f'<section><h2>Ended links</h2>{link_rows(site, past)}</section>')
    if plans:
        li = []
        for p, es in sorted(plans.items()):
            pn = site.nodes.get(p, {})
            bits = "; ".join(f'{html.escape(typ)} {site.a(other)}' for e, fwd, other, typ in es)
            li.append(f'<li>{site.a(p)} <span class="tag draft">{html.escape(pn.get("status", ""))}'
                      f'{" · " + html.escape(str(pn["target"])) if pn.get("target") else ""}</span><br><small>{bits}</small></li>')
        out.append(f'<section><h2>In live plans</h2><ul class="plain">{"".join(li)}</ul></section>')
    out += logs
    ment = sorted(m for m in mentions if site.nodes.get(m, {}).get("type") != "session")
    if sessions or ment:
        out.append('<section class="also"><h2>Also see</h2>')
        if sessions:
            ss = sorted(sessions, key=lambda s: int(site.nodes[s].get("number") or 0))
            out.append('<p><b>Sessions:</b> ' + ", ".join(site.a(s, "S" + str(site.nodes[s].get("number"))) for s in ss) + "</p>")
        if ment:
            out.append('<p><b>Mentioned in:</b> ' + ", ".join(site.a(m) for m in ment) + "</p>")
        out.append("</section>")
    foot = [f'From <code>{html.escape(n["path"])}</code> in the Ossë vault']
    if n.get("term"):
        foot.append(f'<code>{html.escape(n["term"])}</code>')
    if fm.get("notion"):
        foot.append(f'<a href="{html.escape(str(fm["notion"]))}" rel="noopener">old Notion page</a>')
    out.append(f'<footer>{" · ".join(foot)}</footer></main></div></body></html>')
    return "".join(out)


def index(site):
    groups = {}
    for n in site.g["nodes"]:
        groups.setdefault(n["type"], []).append(n)
    out = [head("All entries"), topbar(site), '<main class="sheet index">', "<h1>The Ossë vault</h1>",
           f'<p class="summary">Every note in the vault as a DM page, after S{site.cur}. Game secrets, prep and plans are here: '
           'this is a DM screen, never one for players.</p>',
           '<input id="q" type="search" placeholder="Find a name, alias or summary" autocomplete="off">',
           '<nav class="jump">' + " ".join(f'<a href="#{t}">{html.escape(l)} <small>{len(groups.get(t, []))}</small></a>'
                                          for t, l in ORDER if groups.get(t)) + "</nav>"]
    for t, l in ORDER:
        ns = groups.get(t, [])
        if not ns: continue
        key = (lambda n: -int(n.get("number") or 0)) if t == "session" else (lambda n: (-int(n.get("importance") or 0), n["id"]))
        if t == "plan":
            key = lambda n: (n.get("status") not in ("ready", "draft"), n.get("status") != "ready", str(n.get("target") or "S999"), n["id"])
        out.append(f'<section id="{t}"><h2>{html.escape(l)} <span>{len(ns)}</span></h2><ul class="entries">')
        for n in sorted(ns, key=key):
            state = n.get("state") or n.get("status") or ("revealed" if n.get("revealed") else "hidden" if t == "secret" else "")
            hay = " ".join([n["id"]] + [str(a) for a in n.get("aliases", [])] + [str(n.get("summary", ""))]).lower()
            out.append(f'<li data-k="{html.escape(hay)}"><a href="{site.slugs[n["id"]]}.html">{html.escape(n["id"])}</a>'
                       + (f' <span class="st s-{slug(state)}">{html.escape(state)}</span>' if state else "")
                       + (f'<small>{site.inline(str(n.get("summary", "")))}</small>' if n.get("summary") else "") + "</li>")
        out.append("</ul></section>")
    out.append("""<script>
const q=document.getElementById('q');q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();
document.querySelectorAll('.entries li').forEach(li=>{li.hidden=v&&!li.dataset.k.includes(v)});
document.querySelectorAll('.index section').forEach(s=>{s.hidden=v&&!s.querySelector('li:not([hidden])')})});
</script>""")
    out.append("</main></div></body></html>")
    return "".join(out)


CSS = """:root{
  --ink:#0a0d14;--line:rgba(201,170,110,.16);--line-2:rgba(201,170,110,.32);
  --gold:#c9a45a;--gold-hi:#e6cc8f;--gold-lo:#7c6033;--text:#ddd3c0;--muted:#8e8a82;--dim:#6c6c70;--arcane:#86b8e6;
  --vellum:#efe3c6;--vellum-2:#e5d4ab;--vink:#2a1d12;--vmuted:#6d5a43;--vred:#7c1622;--vrule:rgba(124,22,34,.3);--vline:rgba(42,29,18,.14);
  --f-display:"Cinzel",Georgia,serif;--f-body:"Spectral",Georgia,serif;--f-mono:"IBM Plex Mono",ui-monospace,monospace}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;min-height:100vh;color:var(--text);font:17px/1.6 var(--f-body);
  background:radial-gradient(ellipse 80% 50% at 50% 0%,rgba(30,44,74,.35),transparent 70%) fixed,var(--ink);padding:clamp(16px,4vw,36px) 16px 56px}
a{color:var(--gold-hi)}:focus-visible{outline:2px solid var(--arcane);outline-offset:2px}
.wrap{max-width:880px;margin:0 auto}
header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding-bottom:14px;margin-bottom:20px;border-bottom:1px solid var(--line)}
.eyebrow{font:500 11px/1.4 var(--f-mono);letter-spacing:.22em;text-transform:uppercase;color:var(--dim)}
.crumbs{font-size:15px;color:var(--muted);margin-top:2px}.crumbs a{color:var(--muted);text-decoration:none}.crumbs a:hover{color:var(--gold-hi)}
.home{font:500 11px/1 var(--f-mono);letter-spacing:.16em;text-transform:uppercase;text-decoration:none;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:10px 12px}
.home:hover{color:var(--gold-hi);border-color:var(--line-2)}
.sheet{background:linear-gradient(180deg,var(--vellum),var(--vellum-2));color:var(--vink);border-radius:6px;padding:clamp(20px,4vw,40px);box-shadow:0 18px 40px rgba(0,0,0,.45)}
.sheet a{color:var(--vred);text-decoration-color:var(--vrule);text-underline-offset:2px}
.nolink{font-weight:600}
h1{margin:0;font:600 clamp(26px,5vw,36px)/1.15 var(--f-display);letter-spacing:.03em;color:var(--vink)}
.aka{color:var(--vmuted);font-style:italic;margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.chip{display:inline-flex;align-items:center;gap:4px;font:500 12px/1.2 var(--f-mono);letter-spacing:.04em;padding:5px 9px;border:1px solid var(--vline);border-radius:999px;background:rgba(255,255,255,.35)}
.chip.type{background:var(--vink);color:var(--vellum);border-color:var(--vink)}
.chip.state{font-weight:600}.s-dead,.s-destroyed,.s-disbanded,.s-pruned,.s-dropped{color:#fff!important;background:#4a3a2c!important}
.s-missing,.s-captured,.s-hidden,.s-unknown,.s-hospitalized{color:var(--vred)!important;border-color:var(--vrule)!important}
.s-ready,.s-revealed,.s-open{border-color:var(--vink)!important}
.summary{font-size:19px;line-height:1.5;margin:14px 0 6px}
.props{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;margin:16px 0 4px;padding:12px 0;border-top:1px solid var(--vline);border-bottom:1px solid var(--vline);font-size:15.5px}
.props dt{font:500 11px/2 var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted)}.props dd{margin:0}
section{margin-top:22px}
h2{font:600 15px/1.3 var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:var(--vred);margin:0 0 8px;padding-bottom:5px;border-bottom:1px solid var(--vrule)}
h2 span{font:400 12px var(--f-mono);letter-spacing:.04em;text-transform:none;color:var(--vmuted);margin-left:6px}
h4{font:600 14px var(--f-display);letter-spacing:.08em;margin:14px 0 4px}
ul{margin:6px 0;padding-left:22px}li{margin:3px 0}ul.plain{list-style:none;padding:0}ul.plain li{margin:8px 0}
li.task{list-style:"☐  "}li.task.done{list-style:"☑  ";color:var(--vmuted)}
p{margin:6px 0}small{color:var(--vmuted)}
code{font:13px var(--f-mono);background:rgba(42,29,18,.07);padding:1px 4px;border-radius:3px}
pre{font:13px/1.45 var(--f-mono);background:rgba(42,29,18,.06);padding:10px;border-radius:4px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:15.5px;margin:6px 0}
th{text-align:left;font:500 11px var(--f-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--vmuted);border-bottom:1px solid var(--vrule);padding:5px 8px}
td{padding:6px 8px;border-bottom:1px solid var(--vline);vertical-align:top}.log td:first-child{font:600 13px var(--f-mono);white-space:nowrap;width:1%}
.callout{margin:12px 0;padding:10px 14px;border-left:3px solid var(--vred);background:rgba(124,22,34,.07);border-radius:0 4px 4px 0}
.callout .ch{font:600 11px var(--f-mono);letter-spacing:.16em;text-transform:uppercase;color:var(--vred);margin-bottom:2px}
.callout.quote{border-left-color:var(--vmuted);background:rgba(42,29,18,.05)}
.tag{display:inline-block;font:600 11px/1.5 var(--f-mono);letter-spacing:.02em;padding:0 5px;border-radius:3px;margin:0 2px;white-space:nowrap;vertical-align:1px}
.tag.canon{background:var(--vink);color:var(--vellum)}.tag.prep{border:1px dashed var(--vmuted);color:var(--vmuted)}.tag.draft{border:1px dotted var(--vred);color:var(--vred)}
.dots{color:var(--vred);font-size:10px;letter-spacing:-1px;white-space:nowrap}.dots i{color:rgba(42,29,18,.18);font-style:normal}
.fam{margin:10px 0 14px}.famh{font:500 11px var(--f-mono);letter-spacing:.16em;text-transform:uppercase;color:var(--vmuted);margin-bottom:2px}
.lk{display:grid;grid-template-columns:60px minmax(90px,150px) 1fr auto;gap:2px 12px;align-items:baseline;padding:5px 0;border-bottom:1px dashed var(--vline);font-size:15.5px}
.lk .ty{color:var(--vmuted);font-style:italic}.lk .to small{margin-left:6px;font:11px var(--f-mono)}.lk .nt{grid-column:2/5;font-size:14px;color:var(--vmuted)}
.also p{font-size:15.5px}
footer{margin-top:28px;padding-top:10px;border-top:1px solid var(--vline);font-size:13px;color:var(--vmuted)}
#q{width:100%;font:16px var(--f-body);padding:10px 12px;margin:14px 0 6px;border:1px solid var(--vline);border-radius:4px;background:rgba(255,255,255,.5);color:var(--vink)}
.jump{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:15px;margin:6px 0 10px}.jump a{text-decoration:none}.jump small{font:11px var(--f-mono)}
.entries{list-style:none;padding:0;columns:2 320px;column-gap:28px}
.entries li{break-inside:avoid;margin:0 0 10px}.entries li>a{font-weight:600}.entries small{display:block;font-size:14px;line-height:1.35}
.st{font:500 11px var(--f-mono);padding:0 5px;border:1px solid var(--vline);border-radius:3px;margin-left:4px}
@media (max-width:640px){.lk{grid-template-columns:52px 1fr auto}.lk .ty{grid-column:2/4}.lk .to{grid-column:1/3}.lk .wn{grid-row:2;grid-column:3}.lk .nt{grid-column:1/4}.props{grid-template-columns:1fr}.props dt{line-height:1.2;margin-top:6px}}
@media print{body{background:#fff;padding:0}header{display:none}.sheet{box-shadow:none;background:#fff}}
"""


def write(path, text):
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old == text:
        return 0
    open(path, "w", encoding="utf-8").write(text)
    return 1


def build_pages(g=None):
    g = g or json.load(open(os.path.join(VAULT, ".osse", "graph.json"), encoding="utf-8"))
    site = Site(g)
    os.makedirs(OUT, exist_ok=True)
    keep, changed = {"index.html", "vault.css"}, 0
    changed += write(os.path.join(OUT, "vault.css"), CSS)
    changed += write(os.path.join(OUT, "index.html"), index(site))
    for n in g["nodes"]:
        f = site.slugs[n["id"]] + ".html"; keep.add(f)
        changed += write(os.path.join(OUT, f), page(site, n))
    for f in os.listdir(OUT):
        if f.endswith(".html") and f not in keep:
            os.remove(os.path.join(OUT, f)); changed += 1
    return len(keep) - 1, changed, site


if __name__ == "__main__":
    total, changed, _ = build_pages()
    print(f"DM pages: {total} in vault/, {changed} changed")
