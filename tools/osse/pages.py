#!/usr/bin/env python3
"""Build the Ossë vault's web pages from the vault and its graph. No text is written by hand or by Claude.
  python3 tools/osse/pages.py          rebuild everything (build.py also does this after each real build)

vault/   the DM screen: a page for every note, with secrets, prep, plans and DM notes. Link it only from the
         hub's game master section.
codex/   the players' screen: only what has come out in play. A note is in it once it has reached the table
         (first_seen, or revealed for a secret). On each page only lines stamped with a played session survive;
         untagged lines are prep by the vault's rules, so they are left out, as are DM callouts, prep links,
         link notes, summaries, roles and plans. A line that links an unrevealed secret or a plan is dropped.
Both index pages search the vault and the System Reference Document (live, through Open5e) at once, with a filter per type (rules.js).
vault/paths.html (Session planner, from paths.py) draws the live plans as branching trees per player character.
vault/status.json tells the hub where the campaign stands. Only files whose content changed are rewritten."""
import html, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "vault")
OUT_PLAYER = os.path.join(REPO, "codex")
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
PLAYER_SKIP = SKIP_SECTIONS | {"Idea", "Requires", "Links", "Log", "Plans", "Who knows"}
PROPS = [("player", "Player"), ("class", "Class"), ("race", "Race"), ("pronouns", "Pronouns"), ("voice", "Voice"),
         ("wants", "Wants"), ("fear", "Fear"), ("leader", "Leader"), ("known_by", "Known by"), ("opened", "Opened"),
         ("closed", "Closed"), ("played_on", "Played on"), ("in_world", "In the world"), ("thread", "Thread"),
         ("played", "Played"), ("pruned", "Pruned"), ("pruned_by", "Pruned because"), ("map", "Map")]
PLAYER_PROPS = [("player", "Player"), ("class", "Class"), ("pronouns", "Pronouns")]
LINK = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
TAG = re.compile(r"\*\(((?:S\d+|prep)[^)]*)\)\*")


def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "note"


def snum(v):
    m = re.match(r"\s*S(\d+)\b", str(v or ""))
    return int(m.group(1)) if m else None


def player_set(g):
    cur = g.get("current_session", 0)
    keep = set()
    for n in g["nodes"]:
        t = n["type"]
        if t in ("plan", "session"):
            continue
        if t == "secret":
            r = snum(n.get("revealed"))
            if r is not None and r <= cur:
                keep.add(n["id"])
        elif t == "party" or (n.get("stage") == "canon" and (snum(n.get("first_seen")) or 99999) <= cur):
            keep.add(n["id"])
    return keep


class Site:
    def __init__(self, g, player=False):
        self.g, self.player = g, player
        self.nodes = {n["id"]: n for n in g["nodes"]}
        self.cur = g.get("current_session", 0)
        self.keep = player_set(g) if player else set(self.nodes)
        self.alias_all = {}
        for n in g["nodes"]:
            for a in [n["id"]] + [str(x) for x in n.get("aliases", [])]:
                self.alias_all.setdefault(a.lower(), n["id"])
        self.slugs, used = {}, set()
        for n in sorted(g["nodes"], key=lambda n: n["id"]):
            if n["id"] not in self.keep:
                continue
            s = slug(n["id"])
            if s in used:
                s = f"{s}-{n['type']}"
            used.add(s); self.slugs[n["id"]] = s
        self.texts = {}
        self.aliases = {nid: [str(a) for a in self.nodes[nid].get("aliases", []) if str(a) != nid] for nid in self.keep}
        if player:
            corpus = " ".join(" ".join(self.filter_lines(ls)) for nid in self.keep for _, ls in sections(self.text(nid))).lower()
            try:
                corpus += json.dumps(json.load(open(os.path.join(REPO, "chronicle", "chronicle.json"), encoding="utf-8")), ensure_ascii=False).lower()
            except OSError:
                pass
            self.aliases = {nid: [a for a in al if a.lower() in corpus] for nid, al in self.aliases.items()}

    def text(self, nid):
        if nid not in self.texts:
            self.texts[nid] = open(os.path.join(VAULT, self.nodes[nid]["path"]), encoding="utf-8").read()
        return self.texts[nid]

    def href(self, name):
        nid = self.alias_all.get(name.strip().lower())
        return (self.slugs[nid] + ".html", nid) if nid in self.slugs else (None, nid)

    def a(self, name, text=None):
        h, nid = self.href(name)
        t = html.escape(text or name)
        return f'<a href="{h}">{t}</a>' if h else f'<span class="nolink">{t}</span>'

    # ---------- what players may see ----------
    def canon_ok(self, line):
        tags = TAG.findall(line)
        if not tags:
            return False
        for t in tags:
            n = snum(t)
            if n is None or n > self.cur:
                return False
        for m in LINK.finditer(line):
            nid = self.alias_all.get(m.group(1).strip().lower())
            if nid and nid not in self.keep and self.nodes[nid]["type"] in ("secret", "plan"):
                return False
        return True

    def filter_lines(self, lines):
        out, i, skip = [], 0, None
        while i < len(lines):
            ln = lines[i]
            if ln.startswith(">") or ln.startswith("#"):
                i += 1; continue
            if ln.startswith("```"):
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    i += 1
                i += 1; continue
            if ln.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    rows.append(lines[i]); i += 1
                keep = [r for r in rows[2:] if (lambda c: snum(c) is not None and snum(c) <= self.cur and re.fullmatch(r"S\d+", c))(r.strip().strip("|").split("|")[0].strip())]
                if keep and len(rows) >= 2:
                    out += rows[:2] + keep
                continue
            m = re.match(r"(\s*)[-*] ", ln)
            if m:
                depth = len(m.group(1)) // 2
                if skip is not None and depth > skip:
                    i += 1; continue
                skip = None
                if self.canon_ok(ln):
                    out.append(ln)
                else:
                    skip = depth
                i += 1; continue
            if ln.strip() and self.canon_ok(ln):
                out.append(ln)
            i += 1
        return out

    def first_canon(self, nid):
        sec = dict(sections(self.text(nid)))
        for h in ("Now", "What the party knows", "The question", "The truth", "Who they are", "What it is"):
            for ln in self.filter_lines(sec.get(h, [])):
                if ln.lstrip().startswith("- "):
                    s = LINK.sub(lambda m: m.group(2) or m.group(1), ln.strip()[2:])
                    return TAG.sub("", s).replace("**", "").strip()
        return ""

    # ---------- inline markdown ----------
    def inline(self, s):
        out, last = [], 0
        for m in LINK.finditer(s):
            out.append(self._fmt(s[last:m.start()])); out.append(self.a(m.group(1), m.group(2))); last = m.end()
        out.append(self._fmt(s[last:]))
        return "".join(out)

    def _fmt(self, s):
        s = html.escape(s)
        s = TAG.sub(lambda m: tag(m.group(1)), s)
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
        base = min(d for d, _ in items)
        for d, text in items:
            d -= base
            while d > depth: out.append("<ul>"); depth += 1
            while d < depth: out.append("</ul>"); depth -= 1
            box = re.match(r"\[( |x)\]\s*(.*)", text)
            out.append(f'<li class="task{" done" if box.group(1) == "x" else ""}">{self.inline(box.group(2))}</li>' if box
                       else f"<li>{self.inline(text)}</li>")
        out.append("</ul>" * (depth + 1))
        return "".join(out)


def tag(when):
    w = str(when).strip()
    cls = "prep" if w.startswith("prep") else "draft" if w == "draft" else "canon"
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
    out = [("", [])]
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
        if site.player:
            if o != "written" or e.get("layer") != "canon" or other not in site.keep:
                continue
            if e.get("start") is None and e.get("date") is None:
                continue
            e = dict(e, note="")
        if o == "plain":
            if not fwd:
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
    since = n.get("state_since")
    if n.get("state") and (not site.player or (snum(since) or 99999) <= site.cur):
        c.append(f'<span class="chip state s-{slug(n["state"])}">{html.escape(n["state"])}{(" " + tag(since)) if since else ""}</span>')
    if not site.player:
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
                 + (f' · target {html.escape(str(n["target"]))}' if n.get("target") and not site.player else "") + "</span>")
    if n.get("stage") and n["stage"] != "canon" and not site.player:
        c.append(f'<span class="chip">{tag(n["stage"])}</span>')
    if n.get("first_seen"):
        c.append(f'<span class="chip">first seen {tag(n["first_seen"])}</span>')
    if not site.player:
        if fm.get("story_role"):
            c.append(f'<span class="chip">{html.escape(str(fm["story_role"]))}</span>')
        if n.get("importance"):
            c.append(f'<span class="chip" title="importance">{dots(n["importance"])}</span>')
    return "".join(c)


# The game master lock (assets/dm.js): hidden until unlocked, so nothing shows while the page loads. An unlock made in Gus's archive counts too.
DM_HEAD = '<style>html:not(.dm-ok) body>*:not(#dmlock){display:none!important}</style><script>try{var k=localStorage,g=k.getItem("gus-key-gm");if(!k.getItem("osse-hub-dm")&&g)k.setItem("osse-hub-dm",g);if(k.getItem("osse-hub-dm"))document.documentElement.classList.add("dm-ok")}catch(e){}</script><script src="../assets/dm.js" defer></script>'


def head(title, player):
    return (f'<!doctype html><html lang="en-CA"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex"><title>{html.escape(title)} · {"The Codex" if player else "Ossë vault"}</title>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Spectral:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">'
            '<link rel="stylesheet" href="pages.css"><link rel="stylesheet" href="../assets/nav.css">' + ("" if player else DM_HEAD) + '</head><body><div class="wrap">')


# The site navigation. Player pages never name or link a DM page; DM pages link only DM pages. Both link the table hub.
NAV_PLAYER = [("hub", "Table hub", "../"), ("chronicle", "Chronicle", "../chronicle/"), ("index", "Codex", "index.html")]
NAV_DM = [("hub", "Table hub", "../"), ("index", "Vault", "index.html"), ("paths", "Session planner", "paths.html"), ("screen", "DM screen", "screen.html")]


def topbar(site, crumb="", here="index"):
    who = "The Codex · what the party knows" if site.player else "Ossë vault · DM screen"
    nav = "".join(f'<a href="{h}"{" aria-current=page" if k == here else ""}>{l}</a>' for k, l, h in (NAV_PLAYER if site.player else NAV_DM))
    return (f'<header><div><div class="eyebrow">{who} · after S{site.cur}</div>'
            + (f'<nav class="crumbs"><a href="index.html">All entries</a> / {crumb}</nav>' if crumb else "")
            + f'</div><nav class="sitenav" aria-label="Site">{nav}</nav></header>')


# Closing an entry goes back to the list as it was left: the search, the filter and the place on the page (rules.js saves them).
CLOSE_JS = """(() => { const c = document.getElementById("close"), k = "osse-list:" + location.pathname.replace(/[^/]*$/, "");
try { const s = JSON.parse(sessionStorage.getItem(k) || "null"); if (s && /^index\\.html([?#]|$)/.test(s.url)) c.href = s.url; } catch (e) {}
c.addEventListener("click", e => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; try { sessionStorage.setItem(k + ":back", "1"); } catch (x) {} });
addEventListener("keydown", e => { if (e.key === "Escape") c.click(); }); })();"""

# The DM screen link (the screen it opens has the lock): the next session's screen once it is built, else the last one built (from status.json).
SCREEN_HTML = """<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>DM screen · Ossë vault</title><link rel="stylesheet" href="pages.css"></head><body><div class="wrap"><p id="m">Opening the DM screen</p>
<script>fetch("status.json",{cache:"no-store"}).then(r=>r.json()).then(s=>{const n=s.screens.includes(s.next)?s.next:Math.max(...s.screens);if(n>0)location.replace("../screen/s"+n+".html");else throw 0;})
.catch(()=>{document.getElementById("m").innerHTML='No DM screen could be opened. <a href="index.html">Back to the vault</a>';});</script></div></body></html>
"""


def page(site, n):
    nid, t, P = n["id"], n["type"], site.player
    text = site.text(nid)
    fm = build.frontmatter(text)
    rows, past, plans, mentions, sessions = links_for(site, nid)
    out = [head(nid, P), topbar(site, f'<a href="index.html#{t}">{html.escape(LABEL.get(t, t))}</a>'), '<main class="sheet">',
           '<a class="close" id="close" href="index.html" title="Close and go back to the list (Esc)">✕ Close</a>']
    out.append(f'<h1>{html.escape(nid)}</h1>')
    al = site.aliases.get(nid, [])
    if al:
        out.append(f'<div class="aka">also {html.escape(", ".join(al))}</div>')
    out.append(f'<div class="chips">{chips(site, n, fm)}</div>')
    if n.get("summary") and not P:
        out.append(f'<p class="summary">{site.inline(str(n["summary"]))}</p>')
    props = [] if P or not fm.get("role") else [("Role", fm["role"])]
    for k, lab in (PLAYER_PROPS if P else PROPS):
        v = fm.get(k)
        if v not in (None, "", []) and (not P or k != "class" or t == "pc"):
            props.append((lab, ", ".join(map(str, v)) if isinstance(v, list) else str(v)))
    if props:
        out.append('<dl class="props">' + "".join(f"<dt>{html.escape(l)}</dt><dd>{site.inline(v)}</dd>" for l, v in props) + "</dl>")
    logs = []
    for h, ls in sections(text):
        if h in (PLAYER_SKIP if P else SKIP_SECTIONS) or (P and h.startswith("Open going into")):
            continue
        body = site.blocks(site.filter_lines(ls) if P else ls)
        if not body:
            continue
        if h in ("Session Log", "Log"):
            logs.append(f'<section class="log"><h2>{html.escape(h)}</h2>{body}</section>'); continue
        out.append("<section>" + (f"<h2>{html.escape(h)}</h2>" if h else "") + body + "</section>")
    if rows:
        out.append(f'<section><h2>Links now <span>{len(rows)}, strongest first</span></h2>{link_rows(site, rows)}</section>')
    if past:
        out.append(f'<section><h2>Ended links</h2>{link_rows(site, past)}</section>')
    if plans and not P:
        li = []
        for p, es in sorted(plans.items()):
            pn = site.nodes.get(p, {})
            bits = "; ".join(f'{html.escape(typ)} {site.a(other)}' for e, fwd, other, typ in es)
            li.append(f'<li>{site.a(p)} <span class="tag draft">{html.escape(pn.get("status", ""))}'
                      f'{" · " + html.escape(str(pn["target"])) if pn.get("target") else ""}</span><br><small>{bits}</small></li>')
        out.append(f'<section><h2>In live plans</h2><ul class="plain">{"".join(li)}</ul></section>')
    out += logs
    ss = sorted((s for s in sessions if (snum("S" + str(site.nodes[s].get("number"))) or 0) <= site.cur),
                key=lambda s: int(site.nodes[s].get("number") or 0))
    ment = [] if P else sorted(m for m in mentions if site.nodes.get(m, {}).get("type") != "session")
    if ss or ment:
        out.append('<section class="also"><h2>Also see</h2>')
        if ss:
            if P:
                out.append('<p><b>In the chronicle:</b> ' + ", ".join(
                    f'<a href="../chronicle/#s{site.nodes[s]["number"]}">S{site.nodes[s]["number"]}</a>' for s in ss) + "</p>")
            else:
                out.append('<p><b>Sessions:</b> ' + ", ".join(site.a(s, "S" + str(site.nodes[s].get("number"))) for s in ss) + "</p>")
        if ment:
            out.append('<p><b>Mentioned in:</b> ' + ", ".join(site.a(m) for m in ment) + "</p>")
        out.append("</section>")
    if P:
        foot = [f"What the party has learned in play, up to S{site.cur}."]
    else:
        foot = [f'From <code>{html.escape(n["path"])}</code> in the Ossë vault']
        if n.get("term"):
            foot.append(f'<code>{html.escape(n["term"])}</code>')
        if fm.get("notion"):
            foot.append(f'<a href="{html.escape(str(fm["notion"]))}" rel="noopener">old Notion page</a>')
    out.append(f'<footer>{" · ".join(foot)}</footer><script>{CLOSE_JS}</script></main></div></body></html>')
    return "".join(out)


def index(site):
    P = site.player
    groups = {}
    for n in site.g["nodes"]:
        if n["id"] in site.keep:
            groups.setdefault(n["type"], []).append(n)
    title = "The Codex" if P else "The Ossë vault"
    lede = (f"Everyone and everything the party has met, as far as play has shown, up to S{site.cur}. "
            "The search also covers the rules, spells, items and creatures." if P else
            f"Every note in the vault as a DM page, after S{site.cur}. Game secrets, prep and plans are here: "
            "this is a DM screen, never one for players. The search also covers the rules, spells, items and creatures.")
    out = [head(title, P).replace('<div class="wrap">', '<div class="wrap list">'), topbar(site), '<main class="sheet index">', f"<h1>{title}</h1>", f'<p class="summary">{lede}</p>',
           '<input id="q" type="search" placeholder="Search the world, the rules and items" autocomplete="off" aria-label="Search the world, the rules and items">',
           '<div class="filters" id="filters" role="group" aria-label="Show only">'
           + f'<button type="button" data-f="all" aria-pressed="true">All</button>'
           + "".join(f'<button type="button" data-f="{t}" aria-pressed="false">{html.escape(l)} <small>{len(groups[t])}</small></button>' for t, l in ORDER if groups.get(t))
           + '<button type="button" class="rf" data-f="rules" aria-pressed="false">Rules and items <small></small></button></div>',
           '<div class="results" id="results"><div id="world"><div class="band" id="wband" hidden><b>In the world</b> <span></span></div>']
    for t, l in ORDER:
        ns = groups.get(t, [])
        if not ns: continue
        key = (lambda n: -int(n.get("number") or 0)) if t == "session" else (lambda n: (-int(n.get("importance") or 0), n["id"]))
        if t == "plan":
            key = lambda n: (n.get("status") not in ("ready", "draft"), n.get("status") != "ready", str(n.get("target") or "S999"), n["id"])
        out.append(f'<section id="{t}"><h2>{html.escape(l)} <span>{len(ns)}</span></h2><ul class="entries">')
        for n in sorted(ns, key=key):
            if P:
                desc = site.first_canon(n["id"])
                state = n.get("state") if (snum(n.get("state_since")) or 99999) <= site.cur else ""
                if t == "thread": state = n.get("status", "")
            else:
                desc = str(n.get("summary", ""))
                state = n.get("state") or n.get("status") or ("revealed" if n.get("revealed") else "hidden" if t == "secret" else "")
            hay = " ".join([n["id"]] + site.aliases.get(n["id"], []) + [desc]).lower()
            out.append(f'<li data-k="{html.escape(hay)}"><a href="{site.slugs[n["id"]]}.html">{html.escape(n["id"])}</a>'
                       + (f' <span class="st s-{slug(state)}">{html.escape(state)}</span>' if state else "")
                       + (f'<small>{site.inline(desc)}</small>' if desc else "") + "</li>")
        out.append("</ul></section>")
    out.append('<p id="none" class="none" hidden></p></div>')
    out.append('<div id="rules" hidden><div class="band rb"><b>Rules and items</b> <span></span></div><div class="ed"><label><input type="radio" name="ed" value="srd-2024" checked> 2024 rules</label>'
               '<label><input type="radio" name="ed" value="srd-2014"> 2014 rules</label></div>'
               '<div class="rgrid"><ol id="rlist" class="rlist"></ol><article id="rshow" class="rshow"></article></div>'
               '<p class="credit">Rules, spells, items and creatures from the System Reference Document (5.1 and 5.2, CC BY 4.0 by Wizards of the Coast), '
               'searched live through <a href="https://open5e.com" rel="noopener">Open5e</a>. Not in the SRD? '
               '<a id="ddb" href="https://www.dndbeyond.com/search" rel="noopener">Search D&amp;D Beyond</a> or <a href="https://5e.tools/" rel="noopener">open 5e.tools</a>.</p></div></div>')
    out.append('<script src="rules.js"></script></main></div></body></html>')
    return "".join(out)


RULES_JS = r"""/* Search and filters for the Ossë pages. One box searches this page ("In the world") and Open5e ("Rules and items", SRD only) together;
   a filter shows one type only. The search and filter live in the address, so closing an entry comes back to the same list. */
(() => {
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)], API = "https://api.open5e.com/v2/";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const q = $("#q"), KEY = "osse-list:" + location.pathname.replace(/[^/]*$/, ""), types = $$("#filters [data-f]").map(b => b.dataset.f);
let f = "all", timer = 0, seq = 0, conds = null, hits = null, asked = "";
const store = { get(k){ try { return localStorage.getItem(k); } catch(e) { return null; } }, set(k,v){ try { localStorage.setItem(k,v); } catch(e) {} } };
const here = { get(k){ try { return sessionStorage.getItem(k); } catch(e) { return null; } }, set(k,v){ try { sessionStorage.setItem(k,v); } catch(e) {} }, del(k){ try { sessionStorage.removeItem(k); } catch(e) {} } };
const typed = () => q.value.trim();
function address(){
  const v = typed(), u = (v ? "?q=" + encodeURIComponent(v) : "") + (f === "all" ? "" : "#" + f);
  history.replaceState(null, "", location.pathname + u); here.set(KEY, JSON.stringify({url: "index.html" + u, y: scrollY}));
}
function pickFilter(t){ f = types.includes(t) && t !== f ? t : "all"; run(); }
function run(now){
  const v = typed();
  $$("#filters [data-f]").forEach(b => b.setAttribute("aria-pressed", b.dataset.f === f));
  $("#world").hidden = f === "rules"; $("#rules").hidden = f !== "rules" && !(f === "all" && v.length > 1);
  $("#rules").classList.toggle("mixed", f === "all"); $("#results").classList.toggle("both", f === "all" && v.length > 1);
  world(); address(); clearTimeout(timer);
  if (f === "rules" || v.length > 1) timer = setTimeout(rules, now === true ? 0 : 300); else { seq++; hits = null; asked = ""; $("#rlist").innerHTML = ""; shut(); }
  counts();
}
function world(){
  const v = typed().toLowerCase(); let n = 0, all = 0;
  $$("#world .entries li").forEach(li => { li.hidden = !!v && !li.dataset.k.includes(v); });
  $$("#world section").forEach(s => { const c = s.querySelectorAll("li:not([hidden])").length, on = c && (f === "all" || f === s.id); s.hidden = !on; all += c; if (on) n += c;
    const h = s.querySelector("h2 span"); if (h) h.textContent = c; });
  $("#wband").hidden = !(v && f === "all"); $("#wband span").textContent = all ? all + (all === 1 ? " entry" : " entries") : "";
  const label = f === "all" || f === "rules" ? "" : $(`#filters [data-f="${f}"]`).firstChild.textContent.trim();
  $("#none").hidden = !!n;
  $("#none").innerHTML = label ? `Nothing in ${esc(label)} by that name. <a href="#all" data-go="all">Search everything</a>` : "Nothing in the world by that name.";
}
function counts(){   // while searching, each filter says how many it would show
  const v = typed();
  $$("#filters [data-f]").forEach(b => { const s = b.querySelector("small"); if (!s) return;
    if (b.dataset.f === "rules") { s.textContent = v.length > 1 && asked === v && hits ? hits.length + (hits.length >= 30 ? "+" : "") : ""; return; }
    const c = document.getElementById(b.dataset.f).querySelectorAll("li:not([hidden])").length; s.textContent = c; b.classList.toggle("zero", !c); });
  $("#rules .band span").textContent = v.length > 1 && asked === v && hits ? (hits.length ? `${hits.length >= 30 ? "the first " : ""}${hits.length} from the System Reference Document` : "") : "";
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
  const box = $("#rshow"), x = '<button type="button" class="close" data-rx title="Close (Esc)">✕ Close</button>'; $("#rules").classList.add("reading"); box.innerHTML = x + "<p class='muted'>Opening</p>";
  try { const r = await fetch(API + route.replace(/^v2\//, "") + encodeURIComponent(key) + "/"); box.innerHTML = x + (r.ok ? detail(await r.json(), model) : "<p>Could not open that entry.</p>"); }
  catch(e) { box.innerHTML = x + "<p>Open5e can't be reached. Check the connection.</p>"; }
  if (innerWidth < 700) box.scrollIntoView({block: "start", behavior: "smooth"});
}
async function rules(){
  const v = typed(), ed = document.querySelector("[name=ed]:checked").value, me = ++seq, list = $("#rlist");
  $("#ddb").href = "https://www.dndbeyond.com/search?q=" + encodeURIComponent(v);
  if (v.length < 2) { hits = null; asked = ""; list.innerHTML = "<li class='muted'>Type at least two letters above to find a rule, spell, item, creature or condition.</li>"; counts(); return; }
  list.innerHTML = "<li class='muted'>Searching</li>";
  try {
    if (!conds) { conds = []; try { const c = await (await fetch(API + "conditions/?limit=60&fields=key,name")).json(); conds = c.results.filter(x => !x.key.includes("_")).map(x => ({route: "v2/conditions/", object_pk: x.key, object_name: x.name, object_model: "Condition"})); } catch(e) {} }
    const j = await (await fetch(API + "search/?limit=30&document_pk=" + ed + "&query=" + encodeURIComponent(v))).json();
    if (me !== seq) return;
    const lv = v.toLowerCase(), rank = r => { const n = r.object_name.toLowerCase(); return n === lv ? 0 : n.startsWith(lv) ? 1 : n.includes(lv) ? 2 : 3; };
    hits = conds.filter(c => c.object_name.toLowerCase().includes(lv)).concat(j.results || []).sort((a, b) => rank(a) - rank(b));
    list.innerHTML = hits.length ? hits.map((r, i) => `<li><button data-r="${esc(r.route)}" data-k="${esc(r.object_pk)}" data-m="${esc(r.object_model)}"><b>${esc(r.object_name)}</b><span>${esc(r.object_model.replace(/([a-z])([A-Z])/g, "$1 $2"))}</span></button></li>`).join("")
      : "<li class='muted'>Nothing in the SRD. Try D&amp;D Beyond below.</li>";
    if (asked !== v) shut();
    asked = v; counts();
    const first = list.querySelector("button"); if (f === "rules" && innerWidth >= 700 && first && rank(hits[0]) <= 1) first.click();
  } catch(e) { if (me === seq) list.innerHTML = "<li class='muted'>Open5e can't be reached. Check the connection.</li>"; }
}
q.addEventListener("input", run);
$("#filters").addEventListener("click", e => { const b = e.target.closest("[data-f]"); if (b) pickFilter(b.dataset.f); });
const shut = () => { $("#rshow").innerHTML = ""; $("#rules").classList.remove("reading"); $$("#rlist button").forEach(x => x.classList.remove("on")); };
document.addEventListener("click", e => {
  const b = e.target.closest("#rlist button"); if (b) { $$("#rlist button").forEach(x => x.classList.toggle("on", x === b)); open(b.dataset.r, b.dataset.k, b.dataset.m); }
  const g = e.target.closest("[data-go]"); if (g) { e.preventDefault(); f = g.dataset.go; run(true); }
  if (e.target.closest("[data-rx]")) shut();
  if (e.target.closest(".entries a")) address();
});
addEventListener("keydown", e => { if (e.key === "Escape" && $("#rshow").innerHTML) shut(); });
addEventListener("pagehide", () => { const s = here.get(KEY); if (s) here.set(KEY, JSON.stringify({...JSON.parse(s), y: scrollY})); });
document.querySelectorAll("[name=ed]").forEach(r => r.addEventListener("change", () => { store.set("osse-rules-ed", r.value); run(); }));
const ed = store.get("osse-rules-ed"); if (ed) { const r = document.querySelector(`[name=ed][value="${ed}"]`); if (r) r.checked = true; }
const was = here.get(KEY), back = here.get(KEY + ":back"); here.del(KEY + ":back");
const p = new URLSearchParams(location.search); if (p.get("q")) q.value = p.get("q");
const h = location.hash.slice(1); if (types.includes(h)) f = h;
run(true);
if (back && was) { try { scrollTo(0, JSON.parse(was).y || 0); } catch (e) {} }
addEventListener("hashchange", () => { const t = location.hash.slice(1); f = types.includes(t) ? t : "all"; run(true); });
})();
"""

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
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px 16px;padding-bottom:14px;margin-bottom:20px;border-bottom:1px solid var(--line)}
.eyebrow{font:500 11px/1.4 var(--f-mono);letter-spacing:.22em;text-transform:uppercase;color:var(--dim)}
.crumbs{font-size:15px;color:var(--muted);margin-top:2px}.crumbs a{color:var(--muted);text-decoration:none}.crumbs a:hover{color:var(--gold-hi)}
.sheet{background:linear-gradient(180deg,var(--vellum),var(--vellum-2));color:var(--vink);border-radius:6px;padding:clamp(20px,4vw,40px);box-shadow:0 18px 40px rgba(0,0,0,.45)}
.sheet a{color:var(--vred);text-decoration-color:var(--vrule);text-underline-offset:2px}
.nolink{font-weight:600}.muted{color:var(--vmuted)}
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
h3{font:600 22px/1.2 var(--f-display);margin:0 0 4px}h4{font:600 14px var(--f-display);letter-spacing:.08em;margin:14px 0 4px;color:var(--vred)}
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
#q{width:100%;font:16px var(--f-body);padding:10px 12px;margin:12px 0 6px;border:1px solid var(--vline);border-radius:4px;background:rgba(255,255,255,.55);color:var(--vink)}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px}
.filters button{font:15px/1.2 var(--f-body);color:var(--vink);background:rgba(255,255,255,.35);border:1px solid var(--vline);border-radius:999px;padding:7px 13px;cursor:pointer}
.filters button:hover{border-color:var(--vred)}.filters small{font:11px var(--f-mono);margin-left:3px}.filters .zero{opacity:.45}
.filters button[aria-pressed=true]{background:var(--vred);border-color:var(--vred);color:var(--vellum)}.filters button[aria-pressed=true] small{color:inherit}
.filters .rf{border-color:rgba(38,70,110,.45);color:#26466e}.filters .rf[aria-pressed=true]{background:#26466e;border-color:#26466e;color:var(--vellum)}
.wrap.list{max-width:1120px}[hidden]{display:none!important}
@media (min-width:860px){.results.both{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,390px);gap:30px;align-items:start}.results.both #rules{margin-top:0;position:sticky;top:8px;max-height:calc(100vh - 16px);overflow:auto}}
.band{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin:14px 0 4px;padding:7px 12px;border-radius:4px;background:rgba(124,22,34,.1);border-left:4px solid var(--vred);color:var(--vred);font-size:14px}
.band b{font:600 14px var(--f-display);letter-spacing:.1em;text-transform:uppercase}.band span{color:var(--vmuted)}
.band.rb{background:rgba(38,70,110,.1);border-left-color:#26466e;color:#26466e}#rules{margin-top:22px}#rules.mixed .rgrid{grid-template-columns:1fr}#rules.mixed .rlist{max-height:60vh;border-right:0}#rules.mixed.reading .rlist{display:none}#rules:not(.mixed) .band{display:none}#rules .rshow h3{color:#26466e}
.close{position:sticky;top:12px;float:right;z-index:3;margin:-6px -6px 8px 14px;display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border:1px solid var(--vred);border-radius:999px;cursor:pointer;font:600 13px/1 var(--f-body);color:var(--vellum)!important;background:var(--vred);text-decoration:none;box-shadow:0 2px 8px rgba(42,29,18,.25)}.close:hover{background:var(--vink);border-color:var(--vink)}
#rshow .close{position:static;min-height:34px;margin:0 0 6px 10px;background:#26466e;border-color:#26466e}
.entries{list-style:none;padding:0;columns:2 320px;column-gap:28px}
.entries li{break-inside:avoid;margin:0 0 10px}.entries li>a{font-weight:600}.entries small{display:block;font-size:14px;line-height:1.35}
.st{font:500 11px var(--f-mono);padding:0 5px;border:1px solid var(--vline);border-radius:3px;margin-left:4px}
.none{margin:16px 0}
.ed{display:flex;gap:18px;font-size:15px;margin:2px 0 10px}.ed input{accent-color:var(--vred)}
.rgrid{display:grid;grid-template-columns:minmax(200px,280px) 1fr;gap:18px;align-items:start}
.rlist{list-style:none;padding:0;margin:0;max-height:70vh;overflow:auto;border-right:1px solid var(--vline);padding-right:8px}
.rlist li{margin:0}.rlist button{width:100%;display:flex;justify-content:space-between;gap:8px;align-items:baseline;text-align:left;font:15px/1.3 var(--f-body);color:var(--vink);background:none;border:0;border-radius:4px;padding:8px;cursor:pointer}
.rlist button span{font:11px var(--f-mono);color:var(--vmuted);white-space:nowrap}.rlist button:hover,.rlist button.on{background:rgba(124,22,34,.08)}
.rshow .meta{font-style:italic;color:var(--vmuted);margin:0 0 8px}.rshow .src{font:11px var(--f-mono);color:var(--vmuted);margin-top:14px}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:2px 14px;font-size:15.5px;margin:8px 0}.kv dt{font-weight:600}.kv dd{margin:0}
.abil td,.abil th{text-align:center}
.credit{font-size:13px;color:var(--vmuted);margin-top:18px;border-top:1px solid var(--vline);padding-top:8px}
@media (max-width:640px){.lk{grid-template-columns:52px 1fr auto}.lk .ty{grid-column:2/4}.lk .to{grid-column:1/3}.lk .wn{grid-row:2;grid-column:3}.lk .nt{grid-column:1/4}
  .props{grid-template-columns:1fr}.props dt{line-height:1.2;margin-top:6px}.rgrid{grid-template-columns:1fr}.rlist{max-height:40vh;border-right:0;border-bottom:1px solid var(--vline)}}
@media print{body{background:#fff;padding:0}header,.close{display:none}.sheet{box-shadow:none;background:#fff}}
"""


def write(path, text):
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old == text:
        return 0
    open(path, "w", encoding="utf-8").write(text)
    return 1


def status(g):
    cur = g.get("current_session", 0); nxt = cur + 1
    plans = [n for n in g["nodes"] if n["type"] == "plan" and n.get("status") in ("draft", "ready")]
    aimed = [n for n in plans if str(n.get("target", "")).upper() == f"S{nxt}"]
    screens = sorted(int(m.group(1)) for f in os.listdir(os.path.join(REPO, "screen")) for m in [re.fullmatch(r"s(\d+)\.html", f)] if m)
    titles = {str(n.get("number")): re.sub(r"^S\d+\s*-\s*", "", n["id"]) for n in g["nodes"] if n["type"] == "session" and n.get("number")}
    return {"current": cur, "next": nxt, "screens": screens, "titles": titles,
            "ready": sorted(n["id"] for n in aimed if n.get("status") == "ready"), "aimed": len(aimed), "live_plans": len(plans),
            "open_threads": sum(1 for n in g["nodes"] if n["type"] == "thread" and n.get("status", "open") == "open"),
            "problems": len(g.get("problems", []))}


def build_set(g, out_dir, player):
    site = Site(g, player)
    os.makedirs(out_dir, exist_ok=True)
    keep, changed = {"index.html", "pages.css", "rules.js"}, 0
    changed += write(os.path.join(out_dir, "pages.css"), CSS)
    changed += write(os.path.join(out_dir, "rules.js"), RULES_JS)
    changed += write(os.path.join(out_dir, "index.html"), index(site))
    if not player:   # Session planner: live plans as branching trees, one lane per player character (tools/osse/paths.py)
        import paths
        keep |= {"paths.html", "screen.html"}
        changed += write(os.path.join(out_dir, "screen.html"), SCREEN_HTML)
        changed += write(os.path.join(out_dir, "paths.html"), paths.page(site))
    for nid in site.slugs:
        f = site.slugs[nid] + ".html"; keep.add(f)
        changed += write(os.path.join(out_dir, f), page(site, site.nodes[nid]))
    for f in os.listdir(out_dir):
        if (f.endswith(".html") or f.endswith(".css")) and f not in keep:
            os.remove(os.path.join(out_dir, f)); changed += 1
    return len(site.slugs), changed, site


def build_pages(g=None):
    g = g or json.load(open(os.path.join(VAULT, ".osse", "graph.json"), encoding="utf-8"))
    total, changed, site = build_set(g, OUT, False)
    changed += write(os.path.join(OUT, "status.json"), json.dumps(status(g), ensure_ascii=False, indent=1) + "\n")
    ptotal, pchanged, _ = build_set(g, OUT_PLAYER, True)
    return total, changed + pchanged, site, ptotal


if __name__ == "__main__":
    total, changed, _, ptotal = build_pages()
    print(f"Pages: {total} DM pages in vault/, {ptotal} player pages in codex/, {changed} files changed")
