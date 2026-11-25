#!/usr/bin/env python3
"""Rebuild the Ossë vault's generated files and check every live plan against canon. Run from anywhere:
   python3 tools/osse/build.py            rebuild, prune plans that became impossible, print problems
   python3 tools/osse/build.py --dry      same checks, but write nothing at all
   python3 tools/osse/build.py --dry --assume "Mira Holt: state=dead" --assume "The bridge was sabotaged: revealed=S13"
                                     preview: which plans a proposed change would prune (nothing is written)
Reads the Ossë vault (iCloud; set OSSE_VAULT to point elsewhere) and writes Index.md, Plan board.md, Glossary.md,
Map.canvas and .osse/graph.json there, and the DM pages in this repo's vault/ folder (see tools/osse/pages.py).
The only notes it ever edits are plans: status, pruned, pruned_by and a Log line."""
import os, re, sys, json, math, datetime

VAULT = os.environ.get("OSSE_VAULT") or os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Ossë")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vocab as terms
ORDER = [("Sessions", "session"), ("Characters", "pc"), ("People", "npc"), ("Factions", "faction"),
         ("Places", "place"), ("Things", "item"), ("Lore", "lore"), ("Secrets", "secret"),
         ("Threads", "thread"), ("Plans", "plan")]
SKIP_DIRS = {".obsidian", ".osse", ".trash", "Bases", "Templates"}
HUB = "The Party"
TODAY = datetime.date.today().isoformat()
DRY = "--dry" in sys.argv or "--assume" in sys.argv   # a what-if never writes
LIVE = {"draft", "ready"}
GONE = {"dead", "destroyed", "disbanded"}

# ---------- reading notes ----------
def frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    data, key = {}, None
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val in ("[]", ""):
                data[key] = [] if val == "[]" else ""
            elif val.startswith("[") and val.endswith("]") and not val.startswith("[["):
                data[key] = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
            else:
                data[key] = val.strip('"').strip("'")
        elif key and re.match(r"^\s+-\s+", line):
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(re.sub(r"^\s+-\s+", "", line).strip().strip('"').strip("'"))
    return data

LINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
SES = re.compile(r"^S(\d+)$")
PERIOD = re.compile(r"^(S\d+|\?)?\s*→\s*(S\d+)?$")
ENTRY = re.compile(r"^-\s+\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]\s*·\s*([a-z]+)/([^·]+?)\s*·\s*([1-5])((?:\s*·\s*[^·]+)*)\s*$")
DRAFT = re.compile(r"^-\s+\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]\s*·\s*([a-z]+)/([^·]+?)\s*·\s*([1-5])\s*·\s*\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]((?:\s*·\s*[^·]+)*)\s*$")
LOGROW = re.compile(r"^\|\s*S(\d+)\s*\|(.*)\|\s*$")

def snum(s):
    m = SES.match(str(s or "").strip())
    return int(m.group(1)) if m else None

def link_name(v):
    m = LINK.search(str(v or ""))
    return m.group(1).strip() if m else None

def sections(text):
    """Yield (section, line) for the body below the front matter."""
    body = text.split("\n---", 1)[1] if text.startswith("---") and "\n---" in text[3:] else text
    sec = ""
    for line in body.splitlines():
        if line.startswith("## "):
            sec = line[3:].strip()
            continue
        yield sec, line.strip()

def collect():
    notes = {}
    for folder, kind in ORDER:
        base = os.path.join(VAULT, folder)
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in sorted(files):
                if not f.endswith(".md"):
                    continue
                path = os.path.join(root, f)
                text = open(path, encoding="utf-8").read()
                fm = frontmatter(text)
                name = f[:-3]
                notes[name] = {"name": name, "folder": folder, "path": os.path.relpath(path, VAULT), "fm": fm, "text": text,
                               "type": fm.get("type") or kind,
                               "aliases": fm.get("aliases") if isinstance(fm.get("aliases"), list) else []}
    return notes

def vocabulary():
    types = {}
    for line in open(os.path.join(VAULT, "Relationship types.md"), encoding="utf-8"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] not in ("Family", "---"):
            fam, typ, form, inv, use = cells
            parts = [x.strip() for x in inv.split(" / ")]
            types[typ] = {"family": fam, "type": typ, "form": form, "inverse": parts[-1] if len(parts) == 3 else parts[0],
                          "inverse_by_pronouns": parts if len(parts) == 3 else None, "use": use}
    return types

# ---------- the graph ----------
def build_graph(notes, vocab, current):
    edges, problems = [], []
    names = set(notes)
    session_note = {}
    for n in notes.values():
        if n["type"] == "session":
            k = n["fm"].get("number")
            if str(k).isdigit():
                session_note[int(k)] = n["name"]

    def inverse(a, typ):
        v = vocab.get(typ)
        if not v:
            return typ
        if v.get("inverse_by_pronouns"):
            pr = str(notes.get(a, {}).get("fm", {}).get("pronouns", "")).lower()
            return v["inverse_by_pronouns"][0 if pr.startswith("he") else 1 if pr.startswith("she") else 2]
        return v["inverse"]

    def add(a, b, typ, w, origin, layer="canon", **kw):
        v = vocab.get(typ) or {"family": "related", "form": "verb"}
        e = {"from": a, "to": b, "family": v["family"], "type": typ, "inverse": inverse(a, typ), "form": v["form"],
             "weight": w, "origin": origin, "layer": layer}
        e.update({k: x for k, x in kw.items() if x not in (None, "")})
        edges.append(e)
        return e

    def parse_extras(extras):
        start = end = date = None; prep = False; rest = []
        for x in extras:
            if x == "prep":
                prep = True
            elif SES.match(x):
                date = snum(x)
            elif "→" in x and PERIOD.match(x):
                pm = PERIOD.match(x)
                start = snum(pm.group(1)) if pm.group(1) and pm.group(1) != "?" else None
                end = snum(pm.group(2)) if pm.group(2) else None
                if pm.group(1) and pm.group(1) != "?" and start is None:
                    rest.append(x)
            else:
                rest.append(x)
        return start, end, date, prep, " · ".join(rest) or None

    for n in notes.values():
        name, fm = n["name"], n["fm"]
        if n["type"] == "plan":
            continue
        typed = set()
        for sec, s in sections(n["text"]):
            m = ENTRY.match(s)
            if m and sec in ("Connections", "Past"):
                tgt, fam, typ, w = m.group(1).strip(), m.group(2), m.group(3).strip(), int(m.group(4))
                if tgt not in names:
                    problems.append(f"{name}: link to missing note [[{tgt}]]")
                    continue
                if typ not in vocab:
                    problems.append(f"{name}: unknown type '{fam}/{typ}' on link to {tgt}")
                elif fam != vocab[typ]["family"]:
                    problems.append(f"{name}: '{fam}/{typ}' should be '{vocab[typ]['family']}/{typ}'")
                extras = [x.strip() for x in m.group(5).split("·") if x.strip()]
                start, end, date, prep, note = parse_extras(extras)
                if date is not None and (start is not None or end is not None):
                    problems.append(f"{name}: link to {tgt} has both a session and a period")
                stamped = date is not None or start is not None or end is not None
                if prep and stamped:
                    problems.append(f"{name}: link to {tgt} is marked prep but also has a session; canon or prep, not both")
                for k_ in (date, start, end):
                    if k_ is not None and k_ not in session_note:
                        problems.append(f"{name}: link to {tgt} names S{k_}, which is not a played session with a note; canon comes only from play, so use prep")
                prep = prep or not stamped   # no session means it has not come out in play
                e = add(name, tgt, typ, w, "written", "prep" if prep else "canon", start=start, end=end, date=date, note=note)
                typed.add(tgt)
                ended = end is not None and end <= current
                if ended and sec != "Past":
                    problems.append(f"{name}: ended link to {tgt} belongs under '## Past'")
                if sec == "Past" and not ended and not (date is not None and date <= current):
                    problems.append(f"{name}: link to {tgt} is under '## Past' but has no end session at or before S{current}")
                if not prep and notes[tgt]["fm"].get("stage") == "draft":
                    problems.append(f"{name}: canon link to draft note {tgt}; promote {tgt} or move the link to a plan")
                if not prep and fm.get("stage") == "draft":
                    problems.append(f"{name}: draft note holds a canon link to {tgt}; draft links belong in a plan")
            elif sec in ("Connections", "Past") and s.startswith("- [["):
                problems.append(f"{name}: connection line not understood: '{s}'")
            elif sec == "Session Log":
                r = LOGROW.match(s)
                if r:
                    k = int(r.group(1))
                    if k not in session_note:
                        problems.append(f"{name}: Session Log row S{k} has no session note; only played sessions belong in the log")
                    if k in session_note and session_note[k] != name:
                        add(name, session_note[k], "appears in", 1, "log", date=k)
                        typed.add(session_note[k])
        # links from properties
        for key, typ in (("location", "at"), ("holder", "held by"), ("in", "located in"), ("leader", "led by")):
            t = link_name(fm.get(key))
            if t:
                if t in names:
                    if t not in typed:
                        add(name, t, typ, int(fm.get("importance") or 2) if str(fm.get("importance", "")).isdigit() else 2, "property")
                        typed.add(t)
                else:
                    problems.append(f"{name}: {key} points to missing note [[{t}]]")
        for t in sorted(set(x.strip() for x in LINK.findall(n["text"]))):
            if t in names and t != name and t not in typed:
                edges.append({"from": name, "to": t, "family": "link", "type": "links to", "inverse": "linked from",
                              "form": "verb", "weight": 0, "origin": "plain", "layer": "canon"})
    # a property link repeats a written one between the same pair: keep the written one
    written_pairs = {frozenset((e["from"], e["to"])) for e in edges if e["origin"] == "written"}
    edges[:] = [e for e in edges if not (e["origin"] == "property" and frozenset((e["from"], e["to"])) in written_pairs)]
    for e in edges:
        if e["origin"] == "property":
            e["layer"] = "canon" if notes[e["from"]]["fm"].get("stage") == "canon" else "prep"
    # a link written on both notes must tell the same story: same layer, same sessions
    wr = [e for e in edges if e["origin"] == "written"]
    key = lambda e: (e["layer"], e.get("start"), e.get("end"), e.get("date"))
    by_pair = {}
    for e in wr:
        by_pair.setdefault((e["from"], e["to"], e["type"]), []).append(e)
    for e in wr:
        if e["origin"] != "written" or e["from"] > e["to"]:
            continue
        twins = by_pair.get((e["to"], e["from"], e["inverse"]), [])
        if twins and not any(key(t) == key(e) for t in twins):
            t = twins[0]
            show = lambda x: x["layer"] if x["layer"] == "prep" else (f"S{x['date']}" if x.get("date") is not None else f"S{x.get('start')} → " + (f"S{x['end']}" if x.get("end") is not None else ""))
            problems.append(f"{e['from']} and {e['to']}: '{e['type']}' is {show(e)} on {e['from']} but {show(t)} on {e['to']}; make them match or keep one")
    return edges, problems, session_note

def edge_state(e, at):
    """current, past, later or event, seen after session `at`."""
    if e.get("date") is not None:
        return "later" if e["date"] > at else "event"
    if e.get("start") is not None and e["start"] > at:
        return "later"
    if e.get("end") is not None and e["end"] <= at:
        return "past"
    return "current"

# ---------- plans ----------
REQ = re.compile(r"^-\s+(not at|no link|not holds|[a-z]+):\s*(.+)$")

def parse_plan(n):
    reqs, links, links_raw = [], [], []
    for sec, s in sections(n["text"]):
        if sec == "Requires" and s.startswith("- "):
            m = REQ.match(s)
            reqs.append((m.group(1), m.group(2).strip()) if m else ("?", s[2:].strip()))
        elif sec == "Links" and s.startswith("- "):
            m = DRAFT.match(s)
            if m:
                extras = [x.strip() for x in m.group(6).split("·") if x.strip()]
                links.append({"from": m.group(1).strip(), "family": m.group(2), "type": m.group(3).strip(),
                              "weight": int(m.group(4)), "to": m.group(5).strip(),
                              "date": next((snum(x) for x in extras if SES.match(x)), None),
                              "note": " · ".join(x for x in extras if not SES.match(x)) or None})
            else:
                links_raw.append(s)
    return reqs, links, links_raw

KINDS = {"", "beat", "reveal", "complication", "decision", "entrance", "exit", "scene", "pressure", "clock", "bottleneck"}   # empty means beat
IN_SCENE = ("beat", "reveal", "complication", "decision", "entrance", "exit")   # the cards a scene is made of
yes = lambda v: str(v or "").strip().lower() in ("true", "yes", "1")
aslist = lambda v: v if isinstance(v, list) else [v] if v not in (None, "") else []
CLOCK = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")

def parse_options(text):
    """A decision's `## Options`: `- [[Plan]] · what the character chooses`, or, when the outcome is no plan of its own,
    `- what the character chooses · what happens`. Returns [(plan or None, choice, outcome)]."""
    out = []
    for sec, s in sections(text):
        if sec == "Options" and s.startswith("- "):
            left, _, right = (x.strip() for x in s[2:].partition("·"))
            m = re.match(r"\[\[", left) and LINK.match(left)
            out.append((m.group(1).strip(), right, "") if m else (None, left, right))
    return out

def plan_shape_checks(notes, problems):
    """Plan kinds, decision options and `for:` lanes (docs/osse/branching.md)."""
    for nm, n in notes.items():
        if n["type"] != "plan":
            continue
        fm = n["fm"]
        kind = str(fm.get("kind") or "").strip().lower()
        if kind not in KINDS:
            problems.append(f"{nm}: kind '{kind}' is not one of {', '.join(sorted(KINDS - {''}))}")
        where = fm.get("where")
        if where and link_name(where) and (link_name(where) not in notes or notes[link_name(where)]["type"] != "place"):
            problems.append(f"{nm}: where [[{link_name(where)}]] is not a place note")
        for v in fm.get("present") if isinstance(fm.get("present"), list) else [fm.get("present")] if fm.get("present") else []:
            t = link_name(v)
            if t and t not in notes:
                problems.append(f"{nm}: present [[{t}]] points to a missing note")
        if any(fm.get(k) for k in ("where", "when", "present", "purpose")) and kind != "scene":
            problems.append(f"{nm}: where, when, present and purpose belong on a scene: set kind: scene or move them to the scene")
        for key, kinds in (("cue", IN_SCENE), ("who", ("entrance", "exit")), ("reveals", ("reveal",)), ("leads_to", ("exit",)), ("critical", ("decision",)), ("anytime", IN_SCENE)):
            if fm.get(key) and (kind or "beat") not in kinds:
                problems.append(f"{nm}: {key} belongs on {' or '.join(kinds)}, not {kind or 'beat'}")
        for v in aslist(fm.get("who")):
            t = link_name(v)
            if t and t not in notes:
                problems.append(f"{nm}: who [[{t}]] points to a missing note")
        for v in aslist(fm.get("reveals")):
            t = link_name(v)
            if t and (t not in notes or notes[t]["type"] != "secret"):
                problems.append(f"{nm}: reveals [[{t}]] is not a secret note")
        for v in aslist(fm.get("leads_to")):
            t = link_name(v)
            if not t or t not in notes or notes[t]["type"] != "plan":
                problems.append(f"{nm}: leads_to '{v}' must be [[a plan]]")
        if fm.get("anytime") and not fm.get("scene"):
            problems.append(f"{nm}: anytime belongs on a card in a scene: set scene: \"[[Scene plan]]\"")
        if kind in ("entrance", "exit") and not fm.get("scene"):
            problems.append(f"{nm}: an {kind} happens in a scene: set scene: \"[[Scene plan]]\"")
        sc = fm.get("scene")
        if sc:
            t = link_name(sc)
            if not t or t not in notes or notes[t]["type"] != "plan" or str(notes[t]["fm"].get("kind") or "").strip().lower() != "scene":
                problems.append(f"{nm}: scene '{sc}' must be [[a plan]] with kind: scene")
            elif kind == "scene":
                problems.append(f"{nm}: a scene cannot sit inside another scene")
        ck = fm.get("clock")
        if ck not in (None, ""):
            m = CLOCK.match(str(ck))
            if not m or int(m.group(2)) < 2 or int(m.group(1)) > int(m.group(2)):
                problems.append(f"{nm}: clock '{ck}' must read filled/segments, like 1/6")
            if kind != "clock":
                problems.append(f"{nm}: has a clock, so set kind: clock")
        opts = parse_options(n["text"])
        for target, choice, outcome in opts:
            if not target:
                if not choice or not outcome:
                    problems.append(f"{nm}: an option is either - [[Plan]] · what they choose, or - what they choose · what happens")
            elif target not in notes or notes[target]["type"] != "plan":
                problems.append(f"{nm}: option [[{target}]] is not a plan note")
        if opts and kind != "decision":
            problems.append(f"{nm}: has Options, so set kind: decision")
        for v in (fm.get("for") or []) if isinstance(fm.get("for"), list) else [fm.get("for")] if fm.get("for") else []:
            who = link_name(v) or str(v).strip()
            if not who or who not in notes or notes[who]["type"] not in ("pc", "party"):
                problems.append(f"{nm}: for '{v}' must name a player character or The Party")

def evaluate(req, notes, edges, current, status_of):
    """Return (result, why): result is True, False, None (unknown) or 'manual'."""
    kind, arg = req
    parts = [p.strip() for p in arg.split("·")]
    ln = lambda p: link_name(p)
    def note(nm):
        return notes.get(nm)
    def missing(nm):
        return (None, f"[[{nm}]] has no note")
    def state(nm):
        return str(note(nm)["fm"].get("state") or "").strip().lower()
    if kind == "check":
        return "manual", arg
    if kind in ("alive", "dead", "met", "unmet", "hidden", "revealed", "open", "plan", "played", "state"):
        nm = ln(parts[0])
        if not nm:
            return None, "no [[note]] named"
        if not note(nm):
            return missing(nm)
        fm = note(nm)["fm"]
        if kind == "alive":
            st = state(nm); since = fm.get("state_since") or ""
            return (st not in GONE, f"{nm} is {st or 'not marked'}" + (f" ({since})" if since else ""))
        if kind == "dead":
            st = state(nm)
            return (st in GONE, f"{nm} is {st or 'not marked'}")
        if kind == "state":
            want = {w.strip().lower() for w in (parts[1] if len(parts) > 1 else "").split(",") if w.strip()}
            st = state(nm)
            return (st in want, f"{nm} is {st or 'not marked'}, needs {', '.join(sorted(want))}")
        if kind in ("met", "unmet"):
            fs = fm.get("first_seen") or ""
            seen = bool(snum(fs) is not None and snum(fs) <= current)
            return ((seen if kind == "met" else not seen), f"{nm} " + (f"first seen {fs}" if seen else "not yet at the table"))
        if kind in ("hidden", "revealed"):
            rv = fm.get("revealed") or ""
            out = snum(rv) is not None and snum(rv) <= current
            return ((out if kind == "revealed" else not out), f"{nm} " + (f"revealed {rv}" if out else "still hidden"))
        if kind == "open":
            st = str(fm.get("status") or "open").lower()
            return (st == "open", f"{nm} is {st}")
        if kind in ("plan", "played"):
            st = status_of.get(nm, str(fm.get("status") or "draft"))
            ok = (st in LIVE or st == "played") if kind == "plan" else st == "played"
            return (ok, f"plan {nm} is {st}")
    if kind in ("at", "not at", "holds", "not holds"):
        if len(parts) < 2 or not ln(parts[0]) or not ln(parts[1]):
            return None, "needs two [[notes]] separated by ·"
        a, b = ln(parts[0]), ln(parts[1])
        for nm in (a, b):
            if not note(nm):
                return missing(nm)
        if kind in ("at", "not at"):
            loc = link_name(note(a)["fm"].get("location"))
            here = loc == b
            return ((here if kind == "at" else not here), f"{a} is at {loc or 'unknown'}")
        holder = link_name(note(b)["fm"].get("holder"))
        has = holder == a
        return ((has if kind == "holds" else not has), f"{b} is held by {holder or 'no one recorded'}")
    if kind in ("link", "no link"):
        if len(parts) < 3 or "/" not in parts[1]:
            return None, "write it as [[A]] · family/type · [[B]]"
        a, typ, b = ln(parts[0]), parts[1].split("/", 1)[1].strip(), ln(parts[2])
        for nm in (a, b):
            if not nm or not note(nm):
                return missing(nm or "?")
        hit = None
        for e in edges:
            if e["origin"] in ("plain", "log") or edge_state(e, current) not in ("current", "event"):
                continue
            if (e["from"] == a and e["to"] == b and e["type"] == typ) or (e["from"] == b and e["to"] == a and e["inverse"] == typ):
                hit = e; break
        why = f"{a} {typ} {b}: " + (("yes" + (f" ({hit['layer']})" if hit["layer"] == "prep" else "")) if hit else "no such link now")
        return ((hit is not None) if kind == "link" else hit is None, why)
    if kind == "by":
        k = snum(parts[0])
        if k is None:
            return None, "write it as by: S18"
        return (current < k, f"current session is S{current}")
    return None, f"unknown requirement '{kind}'"

def set_props(path, props, log_line):
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return
    end = text.find("\n---", 3)
    head, body = text[:end], text[end:]
    for k, v in props.items():
        line = f'{k}: "{v}"' if v and any(c in str(v) for c in ':#[]"') else f"{k}: {v}"
        if v in ("", None):
            line = f"{k}:"
        if re.search(rf"(?m)^{k}:.*$", head):
            head = re.sub(rf"(?m)^{k}:.*$", lambda _m: line, head, count=1)
        else:
            head += "\n" + line
    text = head + body
    if log_line:
        if re.search(r"(?m)^## Log\s*$", text):
            text = text.rstrip("\n") + "\n" + log_line + "\n"
        else:
            text = text.rstrip("\n") + "\n\n## Log\n" + log_line + "\n"
    open(path, "w", encoding="utf-8").write(text)

def check_plans(notes, edges, current, problems):
    plans = {nm: n for nm, n in notes.items() if n["type"] == "plan"}
    status_of = {nm: str(n["fm"].get("status") or "draft").lower() for nm, n in plans.items()}
    parsed = {nm: parse_plan(n) for nm, n in plans.items()}
    report, newly, revived, repruned = {}, [], [], []
    for nm, (reqs, links, raw) in parsed.items():
        for s in raw:
            problems.append(f"{nm}: plan link not understood (write [[A]] · family/type · weight · [[B]]): '{s}'")
    changed = True
    while changed:   # cascade: a plan that needs a pruned plan is pruned in the same run
        changed = False
        for nm, (reqs, links, raw) in parsed.items():
            if status_of[nm] not in LIVE:
                continue
            explicit = {link_name(a) for k, a in reqs if k in ("dead", "state")}
            implicit = []
            for l in links:
                for end_ in (l["from"], l["to"]):
                    if end_ in notes and end_ not in explicit and notes[end_]["type"] != "plan" and ("alive", f"[[{end_}]]") not in implicit:
                        implicit.append(("alive", f"[[{end_}]]"))
            fm, kind = notes[nm]["fm"], str(notes[nm]["fm"].get("kind") or "").strip().lower()
            for key, k, req in (("who", "entrance", "alive"), ("reveals", "reveal", "hidden")):   # who comes in must be able to; a secret can only come out once
                for t in (link_name(v) for v in aslist(fm.get(key))) if kind == k else ():
                    if t in notes and t not in explicit and (req, f"[[{t}]]") not in implicit:
                        implicit.append((req, f"[[{t}]]"))
            results = []
            for r in reqs + [x for x in implicit if x not in reqs]:
                res, why = evaluate(r, notes, edges, current, status_of)
                results.append((r, res, why, r not in reqs))
            report[nm] = results
            failed = [(r, why) for r, res, why, _ in results if res is False]
            if failed:
                r, why = failed[0]
                plain = LINK.sub(lambda m_: m_.group(1), r[1])
                reason = f"needs {r[0]}: {plain}, but {why}"
                status_of[nm] = "pruned"; changed = True
                (repruned if notes[nm]["fm"].get("pruned") else newly).append((nm, reason))
                notes[nm]["fm"].update({"status": "pruned", "pruned": f"S{current}", "pruned_by": reason})
                if not DRY:
                    set_props(os.path.join(VAULT, notes[nm]["path"]), {"status": "pruned", "pruned": f"S{current}", "pruned_by": reason},
                              f"- S{current}: pruned by the build. {reason}.")
    for nm in plans:   # Tom set a pruned plan back to draft and it now holds: clear the old prune
        if status_of[nm] in LIVE and notes[nm]["fm"].get("pruned"):
            revived.append(nm)
            notes[nm]["fm"].update({"pruned": "", "pruned_by": ""})
            if not DRY:
                set_props(os.path.join(VAULT, notes[nm]["path"]), {"pruned": "", "pruned_by": ""},
                          f"- S{current}: back to {status_of[nm]}; every requirement holds again.")
    for nm, (reqs, links, raw) in parsed.items():
        for r, res, why, imp in report.get(nm, []):
            if res is None:
                problems.append(f"{nm}: requirement '{r[0]}: {r[1]}' cannot be checked: {why}")
    return plans, status_of, parsed, report, newly, revived, repruned

# ---------- outputs ----------
def first_line(fm):
    for k in ("summary", "about"):
        v = fm.get(k)
        if isinstance(v, str) and v:
            return v
    return ""

def render_index(notes):
    out = ["---", "type: index", "---", "", "> [!info] Index",
           f"> Every note in the vault, one line each ({len(notes)} notes). Rebuilt by `tools/osse/build.py` in the homebrew repo. Do not edit by hand.", ""]
    for folder, _ in ORDER:
        items = sorted((n for n in notes.values() if n["folder"] == folder), key=lambda n: n["name"].lower())
        if not items:
            continue
        out += [f"## {folder} ({len(items)})", ""]
        for n in items:
            fm = n["fm"]
            tags = [t for t in (fm.get("stage") if fm.get("stage") in ("prep", "draft") else "",
                                fm.get("state") if fm.get("state") in GONE | {"missing", "captured"} else "",
                                fm.get("status") if n["type"] in ("plan", "thread") else "") if t]
            aka = f" (also: {', '.join(n['aliases'])})" if n["aliases"] else ""
            out.append(f"- [[{n['name']}]]{aka}" + (f" `{' · '.join(tags)}`" if tags else "") + (f": {first_line(fm)}" if first_line(fm) else ""))
        out.append("")
    return "\n".join(out)

def render_board(notes, plans, status_of, parsed, report, newly, current):
    nxt = current + 1
    mark = {True: "✅", False: "❌", None: "❓", "manual": "✋"}
    def line(nm):
        fm = notes[nm]["fm"]
        bits = [b for b in (fm.get("target") or "", fm.get("thread") and LINK.sub(r"\1", fm["thread"]) or "") if b]
        return f"- [[{nm}]]" + (f" ({', '.join(bits)})" if bits else "") + (f": {first_line(fm)}" if first_line(fm) else "")
    def reqs(nm):
        rows = []
        for r, res, why, imp in report.get(nm, []):
            if res is True and imp:
                continue
            rows.append(f"    - {mark[res]} {r[0]}: {r[1]}" + (f" *({why})*" if res is not True else "") + (" *(implicit)*" if imp else ""))
        return rows
    live = [nm for nm in plans if status_of[nm] in LIVE]
    tgt = lambda nm: snum(notes[nm]["fm"].get("target")) if snum(notes[nm]["fm"].get("target")) is not None else 9999
    ready = sorted([nm for nm in live if status_of[nm] == "ready"], key=lambda x: (tgt(x), x))
    stale = sorted([nm for nm in live if tgt(nm) <= current], key=lambda x: (tgt(x), x))
    drafts = sorted([nm for nm in live if status_of[nm] == "draft" and nm not in stale], key=lambda x: (tgt(x), x))
    manual = sorted([nm for nm in live if any(res == "manual" for _, res, _, _ in report.get(nm, []))])
    pruned = sorted([nm for nm in plans if status_of[nm] == "pruned"], key=lambda x: (-(snum(notes[x]["fm"].get("pruned")) or 0), x))
    played = sorted([nm for nm in plans if status_of[nm] == "played"], key=lambda x: (-(snum(notes[x]["fm"].get("played")) or 0), x))
    out = ["---", "type: board", "---", "", "> [!info] Plan board",
           f"> Every plan checked against canon after S{current}. Rebuilt by `tools/osse/build.py` in the homebrew repo; do not edit. "
           "✅ holds · ❌ failed · ❓ cannot be checked · ✋ needs your judgment.", ""]
    if newly:
        out += ["## Pruned by this build", ""] + [f"- [[{nm}]]: {why}" for nm, why in newly] + [""]
    out += [f"## Ready (next table is S{nxt})", ""]
    for nm in ready:
        out += [line(nm)] + reqs(nm)
    out += ["" if ready else "- none", ""]
    out += ["## Stale (target has passed: retarget or drop)", ""]
    for nm in stale:
        out += [line(nm)]
    out += ["" if stale else "- none", ""]
    out += ["## Drafts", ""]
    for nm in drafts:
        out += [line(nm)] + reqs(nm)
    out += ["" if drafts else "- none", ""]
    out += ["## Judgment calls on live plans", ""]
    for nm in manual:
        out += [f"- [[{nm}]]"] + [f"    - ✋ {r[1]}" for r, res, _, _ in report[nm] if res == "manual"]
    out += ["" if manual else "- none", ""]
    out += ["## Pruned", ""] + ([f"- [[{nm}]] ({notes[nm]['fm'].get('pruned') or '?'}): {notes[nm]['fm'].get('pruned_by') or 'pruned by hand'}" for nm in pruned] or ["- none"]) + [""]
    out += ["## Played", ""] + ([f"- [[{nm}]] ({notes[nm]['fm'].get('played') or '?'})" for nm in played] or ["- none"]) + [""]
    dropped = sorted(nm for nm in plans if status_of[nm] == "dropped")
    out += ["## Dropped", ""] + ([f"- [[{nm}]]" for nm in dropped] or ["- none"]) + [""]
    return "\n".join(out)

def render_glossary(notes):
    cats = [("Places", ("place",)), ("People", ("pc", "npc")), ("Factions & peoples", ("faction",)), ("Other", ("item", "lore", "secret", "thread"))]
    out = ["---", "type: glossary", "---", "", "> [!info] Name and spelling glossary",
           "> Every proper noun in canon and prep, for spelling checks on the session transcript and the transcript bot's word list. Draft names are left out. Rebuilt by `tools/osse/build.py` in the homebrew repo.", ""]
    for label, kinds in cats:
        names = []
        for n in notes.values():
            if n["type"] in kinds and n["fm"].get("stage") != "draft" and n["type"] not in ("secret", "thread"):
                names.append(n["name"] + (f" ({', '.join(n['aliases'])})" if n["aliases"] else ""))
        out.append(f"- **{label}:** " + ", ".join(sorted(names, key=str.lower)))
    return "\n".join(out) + "\n"

PALETTE = {"pc": "#7F77DD", "party": "#7F77DD", "npc": "#D4537E", "faction": "#D85A30", "place": "#1D9E75",
           "item": "#E0A526", "lore": "#378ADD", "thread": "#2BB5C9", "secret": "#A32D2D", "session": "#5F5E5A", "plan": "#B4B2A9"}

def render_canvas(notes, edges, current):
    if HUB not in notes:
        return None
    hub_links = []
    for e in edges:
        if e["origin"] not in ("written", "property") or edge_state(e, current) in ("past", "later") or not e["weight"]:
            continue
        if e["from"] == HUB:
            hub_links.append((e["family"], e["to"], e["type"], e["weight"], e["layer"]))
        elif e["to"] == HUB:
            hub_links.append((e["family"], e["from"], e["inverse"], e["weight"], e["layer"]))
    seen, uniq = set(), []
    for h in sorted(hub_links, key=lambda h: -h[3]):
        if h[1] not in seen:
            seen.add(h[1]); uniq.append(h)
    cnodes = [{"id": "hub", "type": "file", "file": notes[HUB]["path"], "x": -170, "y": -50, "width": 340, "height": 100, "color": "#7F77DD"}]
    cedges, fams = [], []
    for h in uniq:
        if h[0] not in fams:
            fams.append(h[0])
    span = 2 * math.pi / max(1, len(fams))
    radius = {5: 600, 4: 1100, 3: 1600, 2: 2100, 1: 2500}
    for fi, fam in enumerate(fams):
        items = [h for h in uniq if h[0] == fam]
        for wv in sorted({h[3] for h in items}, reverse=True):
            ring = [h for h in items if h[3] == wv]
            r = max(radius[wv], int(300 * (len(ring) + 1) / span))
            for j, (_, tgt, label, w, layer) in enumerate(ring):
                a = fi * span + span * (j + 1) / (len(ring) + 1) - math.pi / 2
                nid = f"n{len(cnodes)}"
                cnodes.append({"id": nid, "type": "file", "file": notes[tgt]["path"], "x": int(r * math.cos(a)) - 130,
                               "y": int(r * math.sin(a)) - 35, "width": 260, "height": 70, "color": PALETTE.get(notes[tgt]["type"], "#888780")})
                cedges.append({"id": f"e{len(cedges)}", "fromNode": "hub", "toNode": nid,
                               "label": f"{label}{' (prep)' if layer == 'prep' else ''} {'●' * w}", "color": PALETTE.get(notes[tgt]["type"], "#888780")})
                if layer == "prep":
                    cedges[-1]["styleAttributes"] = {"path": "long-dashed"}   # Advanced Canvas draws prep links dashed
        a = fi * span + span / 2 - math.pi / 2
        cnodes.append({"id": f"s{fi}", "type": "text", "text": f"## {fam}", "x": int(2700 * math.cos(a)) - 150,
                       "y": int(2700 * math.sin(a)) - 40, "width": 300, "height": 80})
    def hit(a, b, pad=30):
        return a["x"] < b["x"] + b["width"] + pad and b["x"] < a["x"] + a["width"] + pad and a["y"] < b["y"] + b["height"] + pad and b["y"] < a["y"] + a["height"] + pad
    placed = [cnodes[0]]
    for n in cnodes[1:]:
        cx, cy = n["x"] + n["width"] / 2, n["y"] + n["height"] / 2
        d = math.hypot(cx, cy) or 1
        steps = 0
        while any(hit(n, m) for m in placed) and steps < 40:
            n["x"] += int(120 * cx / d); n["y"] += int(120 * cy / d); steps += 1
        placed.append(n)
    on_map = {n["file"]: n["id"] for n in cnodes if n.get("type") == "file"}
    pairs = set()
    for e in edges:
        if not e["weight"] or e["origin"] != "written" or HUB in (e["from"], e["to"]) or edge_state(e, current) in ("past", "later"):
            continue
        a, b = on_map.get(notes[e["from"]]["path"]), on_map.get(notes[e["to"]]["path"])
        k = frozenset((e["from"], e["to"]))
        if a and b and k not in pairs:
            pairs.add(k)
            cedges.append({"id": f"x{len(cedges)}", "fromNode": a, "toNode": b, "toEnd": "none",
                           "label": f"{e['type']} {'●' * e['weight']}", "color": "#888780"})
    return {"nodes": cnodes, "edges": cedges}

def note_checks(notes, edges, parsed, status_of, problems):
    played = {int(n["fm"]["number"]) for n in notes.values() if n["type"] == "session" and str(n["fm"].get("number", "")).isdigit()}
    for n in notes.values():
        for key in ("first_seen", "state_since", "revealed", "opened", "closed", "played"):
            v = str(n["fm"].get(key) or "").strip()
            if v and v != "prep" and (snum(v) is None or snum(v) not in played) and not (n["type"] == "plan" and key == "played" and snum(v) is not None):
                problems.append(f"{n['name']}: {key} is '{v}', which is not a played session with a note (canon comes only from play; use prep or leave it empty)")
    live_named = set()
    for nm, (reqs, links, raw) in parsed.items():
        if status_of.get(nm) in LIVE:
            for l in links:
                live_named |= {l["from"], l["to"]}
            for r in reqs:
                live_named |= set(x.strip() for x in LINK.findall(r[1]))
            live_named |= set(x.strip() for x in LINK.findall(notes[nm]["text"]))
    for n in notes.values():
        fm, t = n["fm"], n["type"]
        if t in ("session", "plan", "party"):
            continue
        st = fm.get("stage")
        if st not in ("canon", "prep", "draft"):
            problems.append(f"{n['name']}: stage must be canon, prep or draft")
        if st == "canon" and t not in ("secret",) and snum(fm.get("first_seen")) is None:
            problems.append(f"{n['name']}: stage is canon but first_seen is empty")
        if st in ("prep", "draft") and snum(fm.get("first_seen")) is not None:
            problems.append(f"{n['name']}: has first_seen {fm.get('first_seen')} but stage is {st}; set stage: canon")
        if st == "draft" and n["name"] not in live_named:
            problems.append(f"{n['name']}: draft note that no live plan uses (keep, promote to prep, or let it rest)")

if __name__ == "__main__":
    notes = collect()
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--assume" and i + 1 < len(argv):
            target, _, kv = argv[i + 1].partition(":")
            key, _, val = kv.strip().partition("=")
            if target.strip() not in notes or not key.strip():
                sys.exit(f"--assume needs 'Note name: key=value', got {argv[i + 1]!r}")
            notes[target.strip()]["fm"][key.strip()] = val.strip()
            print(f"ASSUMING {target.strip()}: {key.strip()} = {val.strip()}")
    vocab = vocabulary()
    played = [int(n["fm"]["number"]) for n in notes.values()
              if n["type"] == "session" and str(n["fm"].get("number", "")).isdigit() and n["fm"].get("status", "played") == "played"]
    current = max(played) if played else 0
    edges, problems, session_note = build_graph(notes, vocab, current)
    plans, status_of, parsed, report, newly, revived, repruned = check_plans(notes, edges, current, problems)
    note_checks(notes, edges, parsed, status_of, problems)
    plan_shape_checks(notes, problems)
    draft_edges = []
    for nm, (reqs, links, raw) in parsed.items():
        for l in links:
            if l["type"] not in vocab:
                problems.append(f"{nm}: unknown type '{l['family']}/{l['type']}' in plan links")
            draft_edges.append(dict(l, layer="draft", origin="plan", plan=nm, status=status_of[nm],
                                    inverse=vocab.get(l["type"], {}).get("inverse", l["type"]),
                                    form=vocab.get(l["type"], {}).get("form", "verb")))
    w = (lambda name, text: None) if DRY else (lambda name, text: open(os.path.join(VAULT, name), "w", encoding="utf-8").write(text))
    w("Index.md", render_index(notes))
    w("Plan board.md", render_board(notes, plans, status_of, parsed, report, newly, current))
    w("Glossary.md", render_glossary(notes))
    nodes = []
    for n in notes.values():
        node = {"id": n["name"], "path": n["path"], "type": n["type"], "aliases": n["aliases"]}
        for k in ("summary", "importance", "stage", "state", "state_since", "first_seen", "location", "holder", "in",
                  "status", "target", "revealed", "race", "role", "kind", "player", "number", "pronouns",
                  "for", "hp", "hp_max", "hp_temp", "slots", "conditions", "sheet_at", "ddb", "class", "played",
                  "where", "when", "present", "purpose", "scene", "cue", "who", "reveals", "leads_to", "critical", "anytime", "clock"):
            v = n["fm"].get(k)
            if v not in (None, "", []):
                node[k] = LINK.sub(r"\1", v) if isinstance(v, str) else [LINK.sub(r"\1", x) if isinstance(x, str) else x for x in v] if isinstance(v, list) else v
        if n["type"] == "plan":
            node["status"] = status_of.get(n["name"], node.get("status"))
        t = terms.type_term(n["type"], n["fm"].get("kind") if isinstance(n["fm"].get("kind"), str) else "")
        if t:
            node["term"] = t
        elif n["type"] not in terms.GENERATED:
            problems.append(f"{n['name']}: type '{n['type']}' with kind '{n['fm'].get('kind') or ''}' has no standard term; add it to tools/osse/vocab.py TYPES")
        nodes.append(node)
    for e in edges + draft_edges:
        m = terms.link_term(e.get("family", ""), e.get("type", ""))
        if m:
            e["term"], e["pattern"], e["direction"] = m["term"], m["pattern"], m["direction"]
        elif e.get("family") not in ("link", "property", "log") and e.get("origin") in ("written", "plan"):
            problems.append(f"{e['from']}: link type '{e.get('family')}/{e.get('type')}' has no standard term; add it to tools/osse/vocab.py LINKS")
    if not DRY:
      json.dump({"hub": HUB, "built": TODAY, "current_session": current, "types": vocab, "problems": problems,
               "nodes": nodes, "edges": edges + draft_edges},
              open(os.path.join(VAULT, ".osse", "graph.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cv = render_canvas(notes, edges, current)
    if cv:
        w("Map.canvas", json.dumps(cv, ensure_ascii=False, indent=1))
    live = sum(1 for s in status_of.values() if s in LIVE)
    print(f"Built after S{current}: {len(notes)} notes; {sum(1 for e in edges if e['origin'] == 'written')} written links, "
          f"{len(draft_edges)} draft links; {live} live plans, {sum(1 for s in status_of.values() if s == 'pruned')} pruned.")
    for nm, why in newly:
        print(f"PRUNED: {nm}: {why}")
    for nm, why in repruned:
        print(f"PRUNED AGAIN (set back to draft but still impossible): {nm}: {why}")
    for nm in revived:
        print(f"REVIVED: {nm}: every requirement holds again")
    if DRY and newly:
        print("(dry run: nothing was written; these plans would be pruned)")
    for p in problems:
        print("PROBLEM:", p)
    if not DRY:
        import pages
        total, changed, _, ptotal = pages.build_pages()
        print(f"Pages: {total} DM pages in vault/, {ptotal} player pages in codex/, {changed} files changed" + ("; commit and push them" if changed else ""))
