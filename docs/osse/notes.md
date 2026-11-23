# Notes, links, secrets, threads and sessions

Rules for writing the vault's notes. Examples are made up. See [README.md](README.md) for the layers and the build.

## Entities: one thing, one note
- Before creating a note, run `python3 tools/osse/osse.py find NAME` for the name and its aliases. If it exists, add to it.
- File name: the canonical spelling from the glossary, with diacritics and apostrophes (`Ëlmar's Reach`). Replace `:` with ` -`; never use `* " \ / < > | ? # ^ [ ]`. Titles go in `aliases`, not the file name, unless the character is always called by the title.
- A name mentioned once with no detail stays in the session note; it does not get a note.

### Properties every entity has
```
type: npc
aliases: []
summary: "one line: who or what this is to the campaign"
importance: 3          # 1 to 5: how central to the story
stage: canon           # canon | prep | draft
first_seen: S4         # first session it appeared in actual play; empty while prep or draft
state: alive           # see below
state_since: S4
updated: 2026-11-18
notion: ""             # the Notion page it was seeded from, if any
```
- **stage** follows `first_seen`: a note with `first_seen` is canon, and `first_seen` needs a session summary or transcript that shows it. Decided but not yet in play is prep. A note that exists only because a plan imagines it is draft.
- When a prep or draft note reaches the table, set `first_seen` and `stage: canon`, and add its first Session Log row.
- A draft note no live plan links to is flagged as orphaned. Tom decides whether to keep it, promote it, or leave it.
- **importance** 5: the spine (PCs, the main antagonist). 4: recurring and load-bearing. 3: regular. 2: met once, could return. 1: colour. Claude drafts it; when Tom changes it, set `importance_set: Tom` and never change it back.

### State, place and holder
Plan requirements are checked against these, so keep them current.
- `state`: people `alive`, `dead`, `missing`, `captured`, `hospitalized`, `unknown`. Factions `active`, `disbanded`, `destroyed`. Places `standing`, `destroyed`, `lost`. Things `intact`, `destroyed`, `lost`. `state_since` is the session it came out in play, or `prep` when it is Tom's decision the table has not seen (`state` is the world's truth; `state_since` says whether the table knows).
- `location`: `"[[Place]]"` where a person or thing is now. `holder`: `"[[Who]]"` for a thing someone carries or owns.
- When any of these change: update the property, add a Session Log row, and keep the old value in it (`Taken to the Guild's cells (was at the docks).`).
- Kind-specific, only when known:
  - **pc** `player`, `class`, `race`; at the end of each session (post-session sync, from D&D Beyond): `hp`, `hp_max`, `hp_temp`, `slots`, `conditions`, `sheet_at`; `ddb` is the sheet's address
  - **npc** `race`, `role`, `story_role` (ally, mentor, antagonist, intermediate antagonist, neutral, quest giver), `voice`, `wants`, `fear`
  - **faction** `kind` (house, guild, gang, order, government, people, church), `leader`
  - **place** `kind` (region, city, district, building, ship, landmark, plane), `in` (`"[[Parent place]]"`)
  - **item** `kind` (artifact, magic item, book, construct, document, evidence, garment, jewellery, weapon, ship)
  - **lore** `kind` (history, religion, magic, spell, deity, creature, custom, song, term)
  - **thread** `status` (open, resolved, abandoned), `opened`, `closed`
- A new `kind` needs a line in `TYPES` in `tools/osse/vocab.py`; the build flags one that has none.

### Entity body
Only the sections that have content, in this order:
```
## Now
- Current truth in two to six lines: where they are, what they want, how they stand with the party.

## Who they are        (npc, pc)  /  ## What it is  (everything else)
- Static description: look, voice, history.

> [!secret] DM only
> Prep the players have not learned. Link the [[Secret note]] when there is one.

## Connections
- [[Other note]] · family/type · weight · when · note

## Past
- ended links, with their period

## Session Log
| Session | Updates |
| --- | --- |
| S3 | Arranged for the cart to be sent to the docks. |
```
- **Session Log**: one row per session per note, ascending, terse (one to three short sentences, past tense). Only played sessions, and only what that session's summary or transcript records. No `S0` row: backstory goes in `## Who they are`, tagged prep.
- **The direct tie test.** Information goes on a note only if its subject was present, acted, was acted upon, or was directly and materially changed. Being talked about is not a tie. What Mira says about a rival goes on Mira's note; it goes on the rival's only if the party confirms it or the rival acts on it.
- Every fact outside the Session Log carries its layer: `*(S5)*` when it came out in play in session 5, `*(prep)*` otherwise. An untagged line is prep.
- When a fact changes, replace the line and keep the old value in brackets: `Leads the Guild (previously Captain Vell).`

## Links: typed, weighted, with session time
Same grammar as Tom's Brain vault, with sessions for time. One link per line in `## Connections`:
`- [[Other note]] · family/type · weight · when · note`

- Use only the types in the vault's `Relationship types.md`. If nothing fits, add a type there and a line in `LINKS` in `tools/osse/vocab.py`. `related/related` with a note is the last resort.
- **How a line reads.** Noun types read "Other note is this note's *type*": on Tobin's note, `[[Edric Ash]] · kin/father · 4` means Edric is Tobin's father. Verb types read "this note *type* Other note": on Mira's note, `[[The Lantern Guild]] · role/member of · 4` means Mira is a member.
- **Write each link once.** The reverse comes from the inverse column.
- **Weight** 1 to 5: how much the link matters to the story.
- **When:** a lasting state takes a period (`S3 → S9` ended, `S3 →` still true); a single happening takes one session (`S5`); prep links carry `prep` (write it, so the line says so). A stamp must name a played session with a note.
- **Never delete or relabel a link because the story moved.** End it (`S3 → S9`), move it to `## Past`, and write the new one.
- Properties give links, so a line is optional: `location` gives place/at, `holder` thing/held by, `in` place/located in, `leader` role/led by.
- Link entries to each other, not only to the party. The hub `Characters/The Party.md` holds the party's own links; add one when something reaches importance 3 for the party as a whole.

## Secrets
One note per hidden truth that could be revealed: `The bridge was sabotaged`.
```
type: secret
summary: "the truth, in one line"
importance: 4
revealed:            # session the party learned it; empty while hidden
known_by: []         # who in the world knows it (wikilinks)
```
Body: `## The truth`, `## Who knows`, `## How it could come out`, `## Connections`, `## Session Log`. When the party learns it, set `revealed`, change the matching `prep` links to the session stamp, and add Session Log rows. Plans test secrets with `hidden:` and `revealed:`.

## Threads
Open questions and goals the party knows about: a mystery, a quest, a debt, a promise. Properties `status`, `opened`, `closed`, `importance`. Body: `## The question`, `## What the party knows`, `## Clues` (each with the session it landed, or `not landed`), `## Connections`, `## Session Log`. Plans that advance a thread name it in their `thread` property.

## Sessions
```
---
type: session
number: 4
title: The Drowned Bell
status: played
played_on: 2026-11-08      # real-world date
in_world:                  # optional
summary: "one line"
notion: "link to the Notion session summary"
---
```
Body: `## What happened` (six to twelve bullets), `## What changed` (state changes, new entities, revealed secrets, threads opened or closed, each a wikilink), `## Clues` (landed or not), `## Plans` (played, partly played, overtaken), `## Open going into S5`. `osse.py brief` reads the last one.
