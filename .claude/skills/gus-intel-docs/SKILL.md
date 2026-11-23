---
name: gus-intel-docs
description: The voice, gags and numbering of GUS's Marshal Intelligence documents (Field Manual chapters, annexes, emergency protocols and other GUS handouts). Use with the gus-document skill whenever Tom wants a new or revised GUS document, or to check one already written sounds right.
---

# GUS Marshal Intelligence documents: voice and numbering

GUS (General Service Unit Seven, played by Shane) receives in-fiction handouts from **Marshal Intelligence, Construct Directorate** of the Arcane Marshals. Every document is written by **Steven (Construct)**, one of many identical spy constructs who all use the cover name Steven. Together they form one oddly personal field manual: bureaucratic, deadpan and literal, and every so often sincere.

This skill is how the documents sound and how they are numbered. The `gus-document` skill is how one is laid out and filed, sealed, in GUS's archive (`screen/gus.html`); the archive page does all the layout, so there is no HTML, CSS or PDF step here.

## 1. Before writing

1. **See what exists.** The archive is the registry: open `screen/gus.html` in game master view (see `gus-document`) and read every document and its note for Tom. Running gags, withdrawn entries and open threads that are not on the page are in the vault note `GUS archive registry` when it exists (`python3 tools/osse/osse.py card "GUS archive registry"`). It is DM-only: never on Gus's screen.
2. **Check canon** when the document touches story facts (handlers, NPCs, missions, GUS's past): `python3 tools/osse/osse.py card GUS`, then any entry it names. Played sessions outrank plans. Never put a DM secret on a handout unless Tom says so.
3. **Settle the format**: chapter, annex, emergency protocol, or another kind (section 4).
4. If the request is clear, draft straight away. Tom reviews it and redirects. Ask first only when a choice would change the story, such as revealing a secret or killing an NPC.

## 2. Voice and tone

The author is a construct writing for another construct, about humans, as if humans were a strange field environment.

**Core moves:**
- **Literal precision about soft things.** A smile lasts two to four seconds. Lower the head eleven degrees. Raise the voice by one setting. One "ha" is polite, three are suspicious.
- **Rule, then undercut.** Each rule is 1 to 3 short declarative sentences, and the joke lands in the last one. "Never leave by the door you entered. If a room has only one door, reconsider the room."
- **Exceptions to exceptions.** "Trust no one. Exception: Steven. Exception to the exception: any Steven you have not met."
- **The document knows it is a document.** "Memorise this chapter, then destroy it. As this chapter is stored inside you, skip the second step." "This protocol will now reseal. / It will not."
- **Incident notes.** An italic note after a rule hints at what went wrong before. "This clarification was added after an incident."
- **Humans as specimens.** "Water leaking from the eyes: Sadness. Or joy. Or onions. Check for onions first."
- **Instructions taken too literally, then corrected.** If an order could be read too literally, add the correction inside the order. "Operate independently... This does not apply to your unit. Keep your unit."

**Steven gags (running):**
- Steven is always the author. The REVIEWED BY field is also Steven, with variants such as "Steven (a different one)".
- Make fun of Steven and the Stevens, not Gus: the cover name is always Steven, any Steven will do, a Steven will not react, there are a lot of Stevens.
- New chapters are delivered in play by a Steven using the contact protocol from Chapter One, 1.6. Each Steven looks different each time.

**Gus is unique:** Tom points out Gus's uniqueness at the table himself. Do not add new lines saying Gus is one of a kind, the only Gus, and so on, unless Tom asks. The lines that already exist (Wrent's letter and EP-07's final step) are approved.

**Sincere beats:**
- They are rare, and they belong mostly in emergency protocols.
- Deliver them straight, usually as a quoted letter or a final step.
- Follow them with one dry institutional line, never a joke that cancels them: "We have not edited it. We wanted to."

**Green ink (DM only: it is Vigil):**
- Handwritten notes in green ink, written straight to Gus about the chapters and lessons. Three forms (markup in `gus-document`):
  - **Scribbled on a page:** `[ink: note]` on its own line, under the rule, box or paragraph above it.
  - **Sticky note on a page:** `[sticky: note]`, pressed on at the right margin.
  - **A note filed on its own,** with its own listing between chapters or annexes: a file whose body starts with `[note]`.
- **Only when Tom asks.** The notes are tied to plot. Never add green ink to a document, or file a note, unless Tom asks for that note.
- The writer is a different voice from the Stevens: one person writing to Gus in the second person, short and plain, with no bureaucratic framing. Gus is never told who writes them. No name, no initial, no signature. The green ink is the only mark until Tom says otherwise.
- Ease in. Tom moves the stage; never jump ahead of it.
  1. **Mysterious** (current stage). Standard writing, no jokes. One or two notes per document at most, often a single word or one line. They show someone is watching Gus's field work: a correction, a nudge to reread a rule, a plain "Seen." Tie them to things Gus actually did at the table (check `osse.py card GUS`).
  2. **Dry.** The same economy, with a trace of personality: an aside that quietly disagrees with a rule or a Steven.
  3. **Human humour about construct things.** A construct who has tried these rules from the inside and finds them funny, using human jokes about bot life.
- Never mock Gus, never reveal a DM secret, and never say Gus is one of a kind (see above).

**Party winks:** Point at other PCs indirectly through tells or examples, and never by name. For example, "A cat demanding things: not an emotion, this is nobility. Comply." for Princess Timbit.

**Field Exercises:**
- Chapters and annexes end with a Field Exercise box of 1 to 3 checkbox tasks. Each is a small side mission Shane can actually play at the table.
- Completing it unlocks the next document, and the footer says so.
- At least one task should involve a Steven, a stranger, or the contact protocol.

**Mechanics of writing:**
- No em dashes. The dash before a letter signature ("— M.W.") is the one exception.
- Avoid "It's not X, it's Y" reversal sentences. The short "X, not Y" rule lines that already exist are fine, but don't lean on the pattern.
- Match the existing spelling: "Memorise", "practised".
- Section numbers prefix every rule: `1.1`, `A.1`, `STEP 1`. Rule titles are uppercase.

## 3. Document taxonomy and numbering

| Type | Title pattern | File code | Rule numbering | Body class |
|---|---|---|---|---|
| Field Manual chapter | Chapter N: <Title> | `MI / FM-0N` | `N.1`, `N.2`... | `fmt-chapter` |
| Annex to a chapter | Annex X to Chapter N: <Title> | `MI / FM-0N / ANX-X` | `X.1`, `X.2`... | `fmt-annex` |
| Emergency Protocol | Emergency Protocol EP-NN: <Title> | `EP-NN` | `STEP 1`... `FINAL STEP` | `fmt-ep` |

- Chapters are the core manual and run in order. Annexes hang off a chapter and are lettered A, B, C... for that chapter.
- Emergency protocols auto-unseal on a trigger and are numbered irregularly (EP-07 exists; there is no EP-01 through EP-06 on file, and nobody explains why).
- Cross-reference with the full form: "Chapter One, 1.6", "Annex A to Chapter One (A.11)".

## 4. New kinds of document

New kinds are welcome: a dossier, a mission briefing, a requisition form GUS fills in, a performance review from Steven, a memo, a cover-identity card, a decoded intercept, a certificate of completion.
- Give it its own file code (for example `MI / DOS-NN` for dossiers) and a self-referential gag on the document itself, as the others have ("will now reseal / it will not", "skip the second step").
- The archive lays out `letter`, `report`, `log` and `other` with the oxblood From / To / Dated band. A kind that needs its own look is a change to `screen/gus.html` and to `KINDS` in `relay/gus/add_doc.py`; keep the archive's palette, fonts and frame so the set still reads as one manual.

## 5. After Tom approves a document

Add a line for it to the vault note `GUS archive registry` (create it in `Lore/` as `type: lore`, `kind: term`, `stage: prep` if it does not exist yet): code, title, status (issued, sealed, planned), hand-over trigger, a one-line summary of each rule, every green-ink note and its stage, and any new cross-references, gags, withdrawn entries or threads. Run `python3 tools/osse/build.py`.
