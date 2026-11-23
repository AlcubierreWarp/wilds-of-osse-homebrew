#!/usr/bin/env python3
"""How the Ossë vault's words map to standard terms. The single source for types, properties and link types.

The world is treated as real: a person is schema:Person, a city schema:City, with no "fictional" tag on each
entry (the whole vault is one fictional world, said once). Same hierarchy as Tom's Brain:
  1. the most specific Schema.org term;
  2. another registered standard (FOAF Relationship `rel:`, XFN `xfn:`, SKOS `skos:`, PROV-O `prov:`);
  3. an `osse:` term, only for what our world lacks (magic, gods, planes) or the game layer (sessions,
     canon/prep/draft, secrets, plans). Every osse: term names a standard parent in OSSE_TERMS.
Never invent another prefix.

Link patterns (as in Brain):
  property  holder relates to the other note by `term`.
  action    an Action of class `term` (actionStatus CompletedActionStatus unless noted); the holder is the agent.
Direction: "as written" reads holder -> other; "reversed" reads other -> holder.
Noun types read "Other is holder's <type>"; verb types read "holder <type> Other" (see Relationship types.md).

  python3 tools/osse/vocab.py --md      rewrite docs/osse/vocabulary.md
  python3 tools/osse/vocab.py --check   check every schema: term against a Schema.org snapshot, when one is on this Mac
"""
import json, os, sys

PREFIXES = {
    "schema": "https://schema.org/",
    "rel": "http://purl.org/vocab/relationship/",
    "xfn": "http://gmpg.org/xfn/11#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "prov": "http://www.w3.org/ns/prov#",
    "osse": "https://github.com/AlcubierreWarp/wilds-of-osse-homebrew/blob/main/tools/osse/vocab.py#",
}

# ---------- osse: terms, each with its standard parent ----------
OSSE_TERMS = {
    # the world: what ours lacks
    "osse:Spell": ("schema:DefinedTerm", "A spell or magical working, by name. Rules text lives in 5e.tools, not here."),
    "osse:Magic": ("schema:DefinedTerm", "A school, tradition or phenomenon of magic."),
    "osse:Religion": ("schema:DefinedTerm", "A faith and its teachings."),
    "osse:Deity": ("schema:Person", "A god or divine being."),
    "osse:Plane": ("schema:Place", "A plane of existence."),
    "osse:CreatureKind": ("schema:Taxon", "A kind of creature or people (race, species). Stat blocks live in 5e.tools."),
    "osse:People": ("schema:Organization", "A people or confederacy, treated as a group that can act."),
    "osse:MagicItem": ("schema:Product", "A magic item or artifact. Its card lives in the homebrew file when it has one."),
    "osse:Construct": ("schema:Product", "A made, animated thing."),
    # the game layer
    "osse:PlaySession": ("schema:Event", "One session at the table. Session stamps (S1, S2...) are the vault's clock."),
    "osse:Thread": ("schema:Question", "An open question or goal the party knows about: mystery, quest, debt, promise."),
    "osse:importance": ("schema:additionalProperty", "1 to 5: how central to the story."),
    "osse:stage": ("prov:wasGeneratedBy", "canon (came out in play), prep (decided, unseen) or draft (an idea)."),
    "osse:firstSeen": ("prov:wasGeneratedBy", "The played session where it first reached the table."),
    "osse:state": ("schema:additionalProperty", "alive, dead, missing...; standing, destroyed...; intact, lost..."),
    "osse:stateSince": ("prov:wasGeneratedBy", "The session the state came out in play, or prep."),
    "osse:revealed": ("prov:wasGeneratedBy", "The session the party learned a secret."),
    "osse:knownBy": ("schema:knowsAbout", "Who in the world knows a secret (reverse of knowsAbout)."),
    "osse:storyRole": ("schema:roleName", "ally, mentor, antagonist, quest giver..."),
    "osse:player": ("schema:additionalProperty", "Who plays a player character (first name only)."),
    "osse:characterClass": ("schema:additionalProperty", "D&D class and level."),
    "osse:voice": ("schema:additionalProperty", "How to play the NPC at the table."),
    "osse:wants": ("schema:additionalProperty", "What the NPC wants."),
    "osse:fear": ("schema:additionalProperty", "What the NPC fears."),
    "osse:planStatus": ("schema:actionStatus", "draft, ready, played, dropped or pruned."),
    "osse:Pressure": ("schema:PlanAction", "What the world does if the party does not act: a front's grim portent. Fires when they stall."),
    "osse:Bottleneck": ("schema:PlanAction", "A beat most branches reach, where paths meet again (branch and bottleneck)."),
    "osse:Scene": ("schema:PlanAction", "A planned scene: a place, the people present and the situation; it sets the stage for the beats, decisions, pressures and clocks inside it."),
    "osse:Beat": ("schema:PlanAction", "One key moment inside a scene or encounter."),
    "osse:Clock": ("schema:PlanAction", "A progress clock: time pressure in a scene, or something that happens when its segments fill."),
    "osse:clock": ("schema:additionalProperty", "A clock's progress: segments filled / segments."),
    "osse:pathOf": ("schema:about", "The player character, or The Party, whose path a plan sits on in Paths ahead."),
    "osse:hitPoints": ("schema:additionalProperty", "Hit points at the end of the last session: current, maximum, temporary."),
    "osse:spellSlots": ("schema:additionalProperty", "Spell slots left at the end of the last session, by level."),
    "osse:conditions": ("schema:additionalProperty", "Conditions and lasting effects at the end of the last session."),
    "osse:sheetAt": ("prov:wasGeneratedBy", "The session whose end the hit points and spell slots were read at."),
    "osse:targetSession": ("schema:startTime", "The session a plan is aimed at."),
    "osse:requires": ("schema:additionalProperty", "A plan requirement checked against canon by the build."),
    "osse:inWorldDate": ("schema:startDate", "An in-world date, when known."),
    # link types with no standard term
    "osse:guardianOf": ("skos:related", "Has charge of a ward."),
    "osse:ally": ("schema:knows", "On the same side, by choice."),
    "osse:informantOf": ("schema:knows", "Feeds information to."),
    "osse:handlerOf": ("schema:knows", "Runs an agent or informant."),
    "osse:owesDebtTo": ("skos:related", "Owes a debt to."),
    "osse:protects": ("schema:knows", "Keeps safe."),
    "osse:distrusts": ("schema:knows", "Distrusts."),
    "osse:admires": ("schema:knows", "Admires."),
    "osse:agentOf": ("schema:worksFor", "Acts for, often secretly."),
    "osse:rules": ("skos:related", "Rules a place or people."),
    "osse:prisonerOf": ("skos:related", "Held prisoner by."),
    "osse:alliedWith": ("skos:related", "Allied, as groups."),
    "osse:atWarWith": ("skos:related", "At war, as groups."),
    "osse:splinterOf": ("schema:parentOrganization", "Broke away from."),
    "osse:commands": ("schema:member", "Gives orders to."),
    "osse:routeTo": ("skos:related", "A road or route leads to."),
    "osse:near": ("skos:related", "Close to."),
    "osse:origin": ("schema:birthPlace", "Comes from (a person, people or thing)."),
    "osse:holds": ("schema:owns", "Carries or has in hand, whoever owns it."),
    "osse:lost": ("skos:related", "Lost."),
    "osse:seeks": ("schema:seeks", "Looking for a thing or person."),
    "osse:suspects": ("schema:knowsAbout", "Suspects."),
    "osse:hides": ("schema:knowsAbout", "Keeps hidden."),
    "osse:worships": ("skos:related", "Worships."),
    "osse:priestOf": ("schema:memberOf", "Serves as a priest of."),
    "osse:blessedBy": ("skos:related", "Blessed by."),
    "osse:caused": ("skos:related", "Brought about."),
    "osse:clueTo": ("schema:about", "Is a clue to."),
    "osse:KillAction": ("schema:Action", "Killing."),
    "osse:CaptureAction": ("schema:TakeAction", "Taking someone captive."),
    "osse:RescueAction": ("schema:Action", "Rescuing or saving."),
    "osse:FreeAction": ("schema:Action", "Setting free."),
    "osse:BetrayAction": ("schema:InteractAction", "Betraying."),
    "osse:AttackAction": ("schema:Action", "Attacking."),
    "osse:HireAction": ("schema:Action", "Hiring."),
    "osse:CurseAction": ("schema:Action", "Cursing."),
    "osse:HealAction": ("schema:Action", "Healing."),
    "osse:FrameAction": ("schema:Action", "Framing someone for a deed."),
    "osse:StealAction": ("schema:TakeAction", "Stealing."),
    "osse:PromiseAction": ("schema:Action", "Promising."),
}

# ---------- types: (vault type, kind or "") -> term ----------
TYPES = {
    ("pc", ""): "schema:Person",
    ("npc", ""): "schema:Person",
    ("party", ""): "schema:Organization",
    ("faction", ""): "schema:Organization",
    ("faction", "house"): "schema:Organization",
    ("faction", "guild"): "schema:Organization",
    ("faction", "gang"): "schema:Organization",
    ("faction", "order"): "schema:Organization",
    ("faction", "church"): "schema:Organization",
    ("faction", "government"): "schema:GovernmentOrganization",
    ("faction", "people"): "osse:People",
    ("place", ""): "schema:Place",
    ("place", "region"): "schema:AdministrativeArea",
    ("place", "city"): "schema:City",
    ("place", "district"): "schema:Place",
    ("place", "building"): "schema:Place",
    ("place", "landmark"): "schema:LandmarksOrHistoricalBuildings",
    ("place", "ship"): "schema:Place",
    ("place", "plane"): "osse:Plane",
    ("item", ""): "schema:Product",
    ("item", "artifact"): "osse:MagicItem",
    ("item", "magic item"): "osse:MagicItem",
    ("item", "book"): "schema:Book",
    ("item", "construct"): "osse:Construct",
    ("item", "document"): "schema:CreativeWork",
    ("item", "evidence"): "schema:Product",
    ("item", "garment"): "schema:Product",
    ("item", "jewellery"): "schema:Product",
    ("item", "weapon"): "schema:Product",
    ("item", "ship"): "schema:Vehicle",
    ("lore", ""): "schema:DefinedTerm",
    ("lore", "term"): "schema:DefinedTerm",
    ("lore", "custom"): "schema:DefinedTerm",
    ("lore", "history"): "schema:Event",
    ("lore", "song"): "schema:MusicComposition",
    ("lore", "magic"): "osse:Magic",
    ("lore", "religion"): "osse:Religion",
    ("lore", "spell"): "osse:Spell",
    ("lore", "deity"): "osse:Deity",
    ("lore", "creature"): "osse:CreatureKind",
    ("secret", ""): "schema:Claim",
    ("thread", ""): "osse:Thread",
    ("plan", ""): "osse:Beat",
    ("plan", "beat"): "osse:Beat",
    ("plan", "scene"): "osse:Scene",
    ("plan", "clock"): "osse:Clock",
    ("plan", "decision"): "schema:ChooseAction",
    ("plan", "pressure"): "osse:Pressure",
    ("plan", "bottleneck"): "osse:Bottleneck",
    ("session", ""): "osse:PlaySession",
    ("chronicle", ""): "schema:Article",
}
GENERATED = {"reference", "board", "glossary", "index", "dashboard", "map"}   # notes the build writes or Tom's dashboards

# ---------- properties: vault key -> term (None: vault bookkeeping, no term) ----------
PROPS = {
    "summary": "schema:description", "aliases": "schema:alternateName", "updated": "schema:dateModified",
    "importance": "osse:importance", "stage": "osse:stage", "first_seen": "osse:firstSeen",
    "state": "osse:state", "state_since": "osse:stateSince", "location": "schema:location",
    "holder": "osse:holds (reversed)", "in": "schema:containedInPlace", "leader": "schema:member (reversed: led by)",
    "pronouns": "schema:pronouns", "race": "osse:CreatureKind", "role": "schema:jobTitle", "story_role": "osse:storyRole",
    "voice": "osse:voice", "wants": "osse:wants", "fear": "osse:fear", "player": "osse:player", "class": "osse:characterClass",
    "kind": "(chooses the type above)", "map": "schema:hasMap", "notion": "prov:hadPrimarySource",
    "revealed": "osse:revealed", "known_by": "osse:knownBy", "status": "osse:planStatus / schema:actionStatus",
    "opened": "osse:firstSeen", "closed": "schema:endTime", "target": "osse:targetSession", "played": "schema:endTime",
    "number": "schema:position", "title": "schema:name", "played_on": "schema:startDate", "in_world": "osse:inWorldDate",
    "thread": "schema:about", "session": "schema:about", "for": "osse:pathOf",
    "hp": "osse:hitPoints", "hp_max": "osse:hitPoints", "hp_temp": "osse:hitPoints", "slots": "osse:spellSlots",
    "conditions": "osse:conditions", "sheet_at": "osse:sheetAt", "ddb": "schema:sameAs",
    "where": "schema:location", "present": "schema:attendee", "scene": "schema:superEvent", "clock": "osse:clock",
    "type": None, "importance_set": None, "pruned": None, "pruned_by": None, "place": None,
}

# ---------- link types: "family/type" -> (pattern, term, direction) ----------
A, R = "as written", "reversed"
LINKS = {
    # kin (from Brain's mapping where the type exists there)
    "kin/father": ("property", "schema:parent", A), "kin/mother": ("property", "schema:parent", A),
    "kin/parent": ("property", "schema:parent", A), "kin/son": ("property", "schema:children", A),
    "kin/daughter": ("property", "schema:children", A), "kin/child": ("property", "schema:children", A),
    "kin/brother": ("property", "schema:sibling", A), "kin/sister": ("property", "schema:sibling", A),
    "kin/sibling": ("property", "schema:sibling", A), "kin/husband": ("property", "schema:spouse", A),
    "kin/wife": ("property", "schema:spouse", A), "kin/spouse": ("property", "schema:spouse", A),
    "kin/betrothed": ("property", "rel:engagedTo", A),
    "kin/grandparent": ("property", "rel:grandparentOf", R), "kin/grandfather": ("property", "rel:grandparentOf", R),
    "kin/grandmother": ("property", "rel:grandparentOf", R), "kin/grandchild": ("property", "rel:grandchildOf", R),
    "kin/grandson": ("property", "rel:grandchildOf", R), "kin/granddaughter": ("property", "rel:grandchildOf", R),
    "kin/aunt or uncle": ("property", "schema:relatedTo", A), "kin/nephew or niece": ("property", "schema:relatedTo", A),
    "kin/uncle": ("property", "schema:relatedTo", A), "kin/aunt": ("property", "schema:relatedTo", A),
    "kin/nephew": ("property", "schema:relatedTo", A), "kin/niece": ("property", "schema:relatedTo", A),
    "kin/cousin": ("property", "schema:relatedTo", A), "kin/relative": ("property", "schema:relatedTo", A),
    "kin/ancestor": ("property", "rel:ancestorOf", R), "kin/descendant": ("property", "rel:descendantOf", R),
    "kin/guardian": ("property", "osse:guardianOf", R), "kin/ward": ("property", "osse:guardianOf", A),
    "kin/creator": ("property", "schema:creator", A), "kin/creation": ("property", "schema:creator", R),
    # social
    "social/friend": ("property", "rel:friendOf", A), "social/ally": ("property", "osse:ally", A),
    "social/rival": ("property", "rel:antagonistOf", A), "social/enemy": ("property", "rel:enemyOf", A),
    "social/lover": ("property", "xfn:sweetheart", A), "social/mentor": ("property", "rel:mentorOf", R),
    "social/student": ("property", "rel:apprenticeTo", R), "social/contact": ("property", "rel:acquaintanceOf", A),
    "social/informant": ("property", "osse:informantOf", R), "social/handler": ("property", "osse:handlerOf", R),
    "social/creditor": ("property", "osse:owesDebtTo", A), "social/debtor": ("property", "osse:owesDebtTo", R),
    "social/protector": ("property", "osse:protects", R), "social/protected": ("property", "osse:protects", A),
    "social/distrusts": ("property", "osse:distrusts", A), "social/distrusted by": ("property", "osse:distrusts", R),
    "social/admires": ("property", "osse:admires", A), "social/admired by": ("property", "osse:admires", R),
    # role
    "role/member of": ("property", "schema:memberOf", A), "role/has member": ("property", "schema:memberOf", R),
    "role/leads": ("property", "schema:member", R), "role/led by": ("property", "schema:member", A),
    "role/serves": ("property", "schema:worksFor", A), "role/served by": ("property", "schema:worksFor", R),
    "role/works for": ("property", "schema:worksFor", A), "role/employs": ("property", "schema:worksFor", R),
    "role/commands": ("property", "osse:commands", A), "role/commanded by": ("property", "osse:commands", R),
    "role/agent of": ("property", "osse:agentOf", A), "role/has agent": ("property", "osse:agentOf", R),
    "role/patron of": ("property", "schema:sponsor", R), "role/backed by": ("property", "schema:sponsor", A),
    "role/founded": ("property", "schema:founder", R), "role/founded by": ("property", "schema:founder", A),
    "role/rules": ("property", "osse:rules", A), "role/ruled by": ("property", "osse:rules", R),
    "role/prisoner of": ("property", "osse:prisonerOf", A), "role/holds prisoner": ("property", "osse:prisonerOf", R),
    "role/allied with": ("property", "osse:alliedWith", A), "role/at war with": ("property", "osse:atWarWith", A),
    "role/splinter of": ("property", "osse:splinterOf", A), "role/has splinter": ("property", "osse:splinterOf", R),
    # place
    "place/located in": ("property", "schema:containedInPlace", A), "place/contains": ("property", "schema:containsPlace", A),
    "place/lives in": ("property", "schema:homeLocation", A), "place/home of": ("property", "schema:homeLocation", R),
    "place/based at": ("property", "schema:location", A), "place/base of": ("property", "schema:location", R),
    "place/at": ("property", "schema:location", A), "place/whereabouts of": ("property", "schema:location", R),
    "place/from": ("property", "osse:origin", A), "place/origin of": ("property", "osse:origin", R),
    "place/near": ("property", "osse:near", A), "place/route to": ("property", "osse:routeTo", A),
    "place/visited": ("action", "schema:TravelAction", A), "place/visited by": ("action", "schema:TravelAction", R),
    # thing
    "thing/holds": ("property", "osse:holds", A), "thing/held by": ("property", "osse:holds", R),
    "thing/owns": ("property", "schema:owns", A), "thing/owned by": ("property", "schema:owns", R),
    "thing/made": ("property", "schema:creator", R), "thing/made by": ("property", "schema:creator", A),
    "thing/seeks": ("property", "osse:seeks", A), "thing/sought by": ("property", "osse:seeks", R),
    "thing/stole": ("action", "osse:StealAction", A), "thing/stolen by": ("action", "osse:StealAction", R),
    "thing/lost": ("property", "osse:lost", A), "thing/lost by": ("property", "osse:lost", R),
    "thing/gave": ("action", "schema:GiveAction", A), "thing/given by": ("action", "schema:GiveAction", R),
    # deed
    "deed/killed": ("action", "osse:KillAction", A), "deed/killed by": ("action", "osse:KillAction", R),
    "deed/captured": ("action", "osse:CaptureAction", A), "deed/captured by": ("action", "osse:CaptureAction", R),
    "deed/rescued": ("action", "osse:RescueAction", A), "deed/rescued by": ("action", "osse:RescueAction", R),
    "deed/saved": ("action", "osse:RescueAction", A), "deed/saved by": ("action", "osse:RescueAction", R),
    "deed/freed": ("action", "osse:FreeAction", A), "deed/freed by": ("action", "osse:FreeAction", R),
    "deed/betrayed": ("action", "osse:BetrayAction", A), "deed/betrayed by": ("action", "osse:BetrayAction", R),
    "deed/attacked": ("action", "osse:AttackAction", A), "deed/attacked by": ("action", "osse:AttackAction", R),
    "deed/defeated": ("action", "schema:WinAction", A), "deed/defeated by": ("action", "schema:WinAction", R),
    "deed/hired": ("action", "osse:HireAction", A), "deed/hired by": ("action", "osse:HireAction", R),
    "deed/bargained with": ("action", "schema:TradeAction", A), "deed/met": ("property", "rel:hasMet", A),
    "deed/cursed": ("action", "osse:CurseAction", A), "deed/cursed by": ("action", "osse:CurseAction", R),
    "deed/healed": ("action", "osse:HealAction", A), "deed/healed by": ("action", "osse:HealAction", R),
    "deed/interrogated": ("action", "schema:AskAction", A), "deed/interrogated by": ("action", "schema:AskAction", R),
    "deed/framed": ("action", "osse:FrameAction", A), "deed/framed by": ("action", "osse:FrameAction", R),
    # knowledge
    "knowledge/knows": ("property", "schema:knowsAbout", A), "knowledge/known by": ("property", "schema:knowsAbout", R),
    "knowledge/suspects": ("property", "osse:suspects", A), "knowledge/suspected by": ("property", "osse:suspects", R),
    "knowledge/hides": ("property", "osse:hides", A), "knowledge/hidden by": ("property", "osse:hides", R),
    "knowledge/searching for": ("property", "osse:seeks", A), "knowledge/searched for by": ("property", "osse:seeks", R),
    # faith
    "faith/worships": ("property", "osse:worships", A), "faith/worshipped by": ("property", "osse:worships", R),
    "faith/priest of": ("property", "osse:priestOf", A), "faith/has priest": ("property", "osse:priestOf", R),
    "faith/blessed by": ("property", "osse:blessedBy", A), "faith/blessed": ("property", "osse:blessedBy", R),
    # lore
    "lore/part of": ("property", "schema:isPartOf", A), "lore/includes": ("property", "schema:hasPart", A),
    "lore/about": ("property", "schema:about", A), "lore/subject of": ("property", "schema:about", R),
    "lore/tied to": ("property", "skos:related", A),
    "lore/caused": ("property", "osse:caused", A), "lore/caused by": ("property", "osse:caused", R),
    # story
    "story/involved in": ("property", "schema:about", R), "story/involves": ("property", "schema:about", A),
    "story/clue to": ("property", "osse:clueTo", A), "story/has clue": ("property", "osse:clueTo", R),
    "story/wants": ("action", "schema:WantAction", A), "story/wanted by": ("action", "schema:WantAction", R),
    "story/promised": ("action", "osse:PromiseAction", A), "story/promised by": ("action", "osse:PromiseAction", R),
    "story/appears in": ("property", "schema:mentions", R), "story/features": ("property", "schema:mentions", A),
    # last resort
    "related/related": ("property", "skos:related", A),
}


def type_term(vtype, kind=""):
    """The standard term for a note's type and kind; None when unmapped."""
    kind = (kind or "").strip().lower()
    return TYPES.get((vtype, kind)) or (TYPES.get((vtype, "")) if not kind else None)


def link_term(family, ltype):
    m = LINKS.get(f"{family}/{ltype}")
    return {"pattern": m[0], "term": m[1], "direction": m[2]} if m else None


def all_curies():
    out = set(TYPES.values()) | {m[1] for m in LINKS.values()} | set(OSSE_TERMS) | {p for p, _ in OSSE_TERMS.values()}
    for v in PROPS.values():
        if v and v.split()[0].count(":") == 1 and not v.startswith("("):
            out.add(v.split()[0])
    return out


def check():
    bad = [c for c in all_curies() if c.split(":")[0] not in PREFIXES]
    missing_parent = [t for t in all_curies() if t.startswith("osse:") and t not in OSSE_TERMS]
    snap = os.path.expanduser("~/Projects/brain/vocab/snapshots/schemaorg-30.1.json")
    unknown = []
    if os.path.exists(snap):
        known = {t["curie"] for t in json.load(open(snap, encoding="utf-8"))["terms"]}
        unknown = sorted(c for c in all_curies() if c.startswith("schema:") and c not in known)
    else:
        print("(no Schema.org snapshot on this machine; schema: terms not checked)")
    for label, xs in (("unregistered prefix", bad), ("osse: term with no entry", missing_parent),
                      ("not in Schema.org 30.1", unknown)):
        for x in xs:
            print(f"VOCAB: {label}: {x}")
    return not (bad or missing_parent or unknown)


def markdown():
    rows = ["# Ossë vocabulary", "",
            "Generated by `python3 tools/osse/vocab.py --md` from `tools/osse/vocab.py`. Do not edit by hand.", "",
            "The vault is one fictional world, typed as if it were real: plain Schema.org first, then FOAF Relationship (`rel:`),",
            "XFN, SKOS and PROV-O, and an `osse:` term only for magic and for the game itself. Every `osse:` term has a standard parent.", "",
            "## Note types", "", "| Vault type | Kind | Term |", "| --- | --- | --- |"]
    rows += [f"| {t} | {k or 'any'} | `{v}` |" for (t, k), v in TYPES.items()]
    rows += ["", "## Properties", "", "| Vault key | Term |", "| --- | --- |"]
    rows += [f"| `{k}` | {('`' + v + '`') if v and not v.startswith('(') else (v or 'vault bookkeeping')} |" for k, v in PROPS.items()]
    rows += ["", "## Link types", "", "| Vault link | Pattern | Term | Direction |", "| --- | --- | --- | --- |"]
    rows += [f"| {k} | {p} | `{t}` | {d} |" for k, (p, t, d) in LINKS.items()]
    rows += ["", "## osse: terms", "", "| Term | Parent | Meaning |", "| --- | --- | --- |"]
    rows += [f"| `{k}` | `{p}` | {d} |" for k, (p, d) in OSSE_TERMS.items()]
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    if "--md" in sys.argv:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "osse", "vocabulary.md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(markdown())
        print("wrote docs/osse/vocabulary.md")
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
