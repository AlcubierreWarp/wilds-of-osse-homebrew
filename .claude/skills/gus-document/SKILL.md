---
name: gus-document
description: Write a new or revised Marshal Intelligence document for Gus (a Field Manual chapter, an annex, an emergency protocol or another Gus handout) and file it, sealed, in Gus's memory archive (screen/gus.html). Use whenever Tom asks for a new Gus document or handout, or to change one already in the archive.
---

# Gus documents in the archive

Gus's documents live in the archive relay, and the archive page lays them out as letter-sized Marshal pages. A new document goes into the archive **sealed**: only Tom sees it, in game master view. Tom reveals it or pushes it to Gus's screen himself, at the table. Never reveal or push from here.

## 1. Write it

- **Voice, numbering and taxonomy:** follow the `gus-intel-docs` skill in this repo (Steven, the gags, sincere beats, field exercises, `1.1` / `A.1` / `STEP 1` numbering, cross-reference style, and what already exists).
- **Canon:** check story facts against the Ossë vault (`python3 tools/osse/osse.py card GUS`). Played sessions outrank plans. Never put a DM secret on a handout unless Tom says so.
- **Which layout:** the `kind` field picks it, and each kind keeps its own look.
- **Standard unless Tom says emergency.** Use `protocol` only when Tom explicitly calls the document an emergency protocol or emergency directive. Protocols go on the archive's Emergency tab, which flashes red on Gus's screen when Tom pushes one. Every other document is a standard one (`manual`, `annex`, or `report`/`letter`/`other`) and goes on the Files tab.

| Document | kind | Title | ref | Look |
|---|---|---|---|---|
| Field Manual chapter | `manual` | `Chapter Three: Infiltration` | `MI/FM-03 · Field manual for the construct operative` | Series bar, navy chapter block, numbered rules |
| Annex to a chapter | `annex` | `Social camouflage` | `MI/FM-01/ANX-B · Annex B to Chapter One` | FILE / AUTHOR / DECRYPTED FOR / REVIEWED BY grid, parts |
| Emergency protocol | `protocol` | `Handler signal lost` | `Emergency protocol EP-07` | Oxblood band with trigger box, hazard stripe, numbered steps |
| Anything else | `letter`, `report`, `log`, `other` | free | free | Oxblood band with From / To / Dated |

**A note on its own** (green ink filed as its own listing, between chapters or annexes): `kind: other`, a short `title`, blank `ref`, `classification`, `from`, `to` and `date`, `order` to place it in the list, and `[note]` as the first line of the body. The archive lists it as a Handwritten note and shows it as a loose lined sheet in green handwriting, with no Marshal letterhead. Blank lines split paragraphs.

For an annex, `from` is `Author. Reviewed by Reviewer` and the grid splits it. For a protocol, `date` is `Trigger: …` and a lead line `**Status: active.**` fills the status.

## 2. The markup

| Write | Get |
|---|---|
| Lines before the first rule | Page opening: first line is the subtitle, the rest the italic intro |
| `[stamp: Eyes only]` | A rubber stamp (beside the title when in the opening) |
| `**1.1 Title.** text` then `*incident note*` on the next line | A numbered rule with its grey italic note |
| `## Part one · Display` | A navy section heading |
| `## Field exercise · Chapter Three` then `- task` lines | The checkbox exercise box; a plain line after the tasks is its italic closer |
| `## Addendum · …` before the first rule, ending with `[stamp: Released]` and `*Signature*` | The clipped card beside the chapter title |
| `## Step 1 · Confirm` … `## Final step · Grief` | Numbered protocol steps; the final one is boxed |
| `+ **Handler alive.** text` | Side-by-side decision boxes inside a step |
| `- [ ] order` | Checkbox orders |
| `> lines` (last short line is the signature) | A quoted letter card |
| `\| Observed \| Assessment \|` rows | A table, first row as header |
| `\|\|words\|\|` | Blacked out; Gus's copy never holds the words |
| `[ink: note]` (`//` breaks the line) | A green handwritten note under the rule, box or paragraph above it; see Green ink in `gus-intel-docs` |
| `[sticky: note]` (`//` breaks the line) | A sticky note in green ink, pressed on at the right margin |
| `---` then two lines | The footer: left line, right line |
| `[page]` | A new page (only when one page clearly is not enough) |

The four documents already in the archive are the best examples. A game master can read their source in the archive editor (Edit).

## 3. File it

1. Write the document to the session scratchpad. A sealed document is a game secret, so it never reaches Gus's screen until Tom reveals it; it is fine in the repo if Tom wants a copy kept. Start it with the header block described at the top of `relay/gus/add_doc.py`: `id` (for example `mi-fm-03`, `mi-fm-01-anx-b`, `ep-09`), `kind`, `title`, `ref`, `classification`, `from`, `to`, `date`, and a `note` for Tom (why it exists, when to hand it over).
2. Try it against the local stand-in first: start the `gus-relay-mock` and `screen` previews, run `/usr/bin/python3 -I relay/gus/add_doc.py <file> --mock`, open `http://localhost:8713/gus.html?relay=http://localhost:8714#gm=test-gm` and look at every page at desktop and phone width. Fix anything that runs long or wraps badly.
3. File it for real: `/usr/bin/python3 -I relay/gus/add_doc.py <file>`. It reads the game master key from the Keychain itself. It refuses to change a document Gus can already see unless Tom asked for that change, in which case add `--update-revealed`.
4. Tell Tom what the document is, that it is sealed in his archive, and when it is meant to be handed over. Point out any new canon it creates.

`--pdf file.pdf` attaches a PDF copy, which the page's Open PDF button then opens. Without one, Open PDF builds a PDF of the Marshal pages in the browser and downloads it.
