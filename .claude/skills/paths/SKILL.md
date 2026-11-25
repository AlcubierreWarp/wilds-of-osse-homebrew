---
name: paths
description: Draft onto Tom's Session planner boards (once called Paths ahead) from a brain dump, clean up what is on them, or bring them into the Ossë vault. Use when Tom brain dumps scenes, decisions, beats or a session framework, asks to build out, tidy or fix something on the Session planner or Paths ahead, or asks to read, sync, formalize or "bring in" the board, the paths, his branches or the cards he added.
---

# Work on the Session planner boards

| Tom asks for | Do |
| --- | --- |
| A brain dump turned into cards, or something built out, tidied, linked or fixed on the page | **Draft on the boards** (below). Nothing goes into the vault |
| The board brought into the vault | Steps 1 to 4 |
| Where a session sits in the campaign | `python3 tools/osse/paths_sync.py arcs` prints the Arc planner (`vault/arcs.html`): each arc's start, end and session cards. Read it before drafting a session, so the draft moves its arc toward its end. A card linked to a session is that session’s name on the Session planner too. Change arcs only on the pages; nothing there goes into the vault |

## Draft on the boards
1. **Read.** `python3 tools/osse/paths_sync.py board S14` (no session for all) prints what is there with its ids. `python3 tools/osse/osse.py brief`, then `card` for each person, place and secret involved. Read the live plans on the same subject (`osse.py plans`): place an existing plan rather than writing a card that repeats it.
2. **Write a draft file** in the scratchpad, never in the repo. The format is at the top of `tools/osse/paths_draft.py`: `cards` (scenes hold their own), `place`, `links`, `edit`, `relabel`, `unlink`, `remove`, `order`, `layout`.
   - Tom's words and ideas lead. Build out what he gave; mark anything you add beyond it when you show the outline, and ask about gaps that change the story instead of filling them.
   - A scene carries its situation (where, when, who is there when it opens, what is going on) and its purpose. Its cards are beats, reveals, complications, decisions, entrances and exits, each with a `cue`: what triggers it at the table. Prefer a cue to an arrow; draw arrows only where one thing must follow another, and from a decision. Set `who` on a card when a player character is in it: the scene then shows on that character's board, so leave it out for someone only talked about. Few cards: one turn each, never a chain of lines of dialogue. Give every scene its exits, each linked to the scene it leads to; `critical` marks a decision that can end or remake a character.
   - A card that can happen at any point in its scene gets `anytime: true` and still a cue; nothing leads to it. Cards that follow one another stay in the flow.
   - A scene that can move in the session (it ties to no other) gets `float: true`, with `after` / `before` (scene keys or ids) only where the story limits it. `board` prints floating scenes with `~`.
   - Every decision has two or three options. An option that opens something is a link labelled with the choice; one that only has a result is listed in `options` as `{"label": choice, "text": what happens}`. Two choices may lead to the same card. Bring branches back together (`docs/osse/branching.md`).
   - Card text is a line or two in table-ready words, to run from; a cue is one short line. Titles are short and never repeat a plan's name. Never contradict canon; never write a secret as known to a player character who does not know it.
   - A clean-up edits Tom's cards in place (`edit`, `relabel`) and keeps his meaning. Remove a card only when he agreed to it.
3. **Preview.** `python3 tools/osse/paths_sync.py draft FILE` checks it and prints the outline. Fix what it lists. Show Tom the outline, phone-sized, with your additions and questions. Wait for his yes.
4. **Write.** The same with `--write`. It refuses if Tom changed the boards since the preview: preview again and check that it still fits. An open page picks the draft up within 20 seconds. The cards read "Claude's draft" until Tom changes them, then "yours".
5. **Undo.** `python3 tools/osse/paths_sync.py undraft` says what it would take off, keeping what Tom changed since; add `--write` to do it. The last 20 drafts are kept in the vault's `.osse/paths-drafts/`.
6. Report what is on which boards, and what is still open. Bring nothing into the vault unless he asks.

# Bring the boards into the vault

Tom plans on the Session planner page (`vault/paths.html`): two views of the whole session (Running order and Canvas), then a board per player character and one for the World (what moves without the party); one tab per session; he places plans on a session's canvas, draws links, adds, edits and deletes cards, and drops plans. The page saves to the Gus relay; the vault does not change until this skill runs. Rules: `docs/osse/branching.md` and `docs/osse/plans.md`.

## Step 1: Read
`python3 tools/osse/paths_sync.py show` (add a board name to see one). Everything has one copy and is listed once, under the first board it is on:
- **set target**: a plan moved to another session tab, or placed from the tray. `Later` means an empty target.
- **add for**: a plan placed on a board it is not tied to.
- **left in the tray**: a plan whose vault target Tom did not place. Ask before clearing that target.
- **NEW CARD**: Tom's card, with its kind, session, text and links; for a scene, where, who is present and the boards it is on; for a clock, its progress; the scene it sits in. A scene with no players yet is listed under the session canvas until Tom adds some: leave out `present:` rather than guess.
- **set scene**: a plan Tom placed inside a scene.
- **EDITED**: Tom changed a plan's kind, summary or idea, or left a note to Claude.
- **DROP**: Tom dropped a plan.
- **NEW LINK**: Tom's link between two vault plans, with its label.
- **any time**: a card in its scene's Any time section.
- **Running order**: each session's scenes, in the order Tom set in the Running order, with floating scenes marked `~` and their limits. Nothing goes into the vault; when building that session's screen (the `session-screen` skill), run the scenes in this order.

## Step 2: Turn it into vault changes
- Start from `python3 tools/osse/paths_sync.py notes SCENE`: it prints the plan notes the scene and its cards would become (add a folder to write them there, outside the vault), and flags names already taken and links that leave the scene. Tighten those; then check `python3 tools/osse/osse.py scene NAME` after the build against the board.
- The fields on a card keep their names in the note: `when`, `purpose`, `cue`, `critical`, `anytime`; `who` and `present` as lists with [[links]]; `reveals: "[[Secret]]"`; an exit's links out as `leads_to:`. Never write `plan: [[exit]]` into the scene an exit leads to.
- A scene card becomes a `kind: scene` plan with `where:` (a [[link]] when the vault has the place; plain text otherwise, and ask Tom whether it needs a place note) and `present:` (a list; [[links]] for people in the vault, plain text for the rest). Write the scene first, then the cards inside it with `scene: "[[Scene]]"`.
- A clock card becomes a `kind: clock` plan with `clock: filled/segments`; its text is what happens when it fills.
- A NEW CARD becomes a plan note in `Plans/`, written with a short script, following `docs/osse/plans.md`: `stage: draft`, `status: draft`, `kind:` from the card (a `note` card becomes the kind its text describes: usually a beat; ask if unclear), `target:` from its column, `for:` the board's character (not for the World; The Party when it is on the session canvas only and is for all of them; not for a scene whose `present:` already names them), a one-line `summary`, `## Idea` from the card text in Tom's words, tightened.
- Links into a card or between plans:
  - from a decision: each link is one option, so one `## Options` line per link, `- [[Plan]] · label`. Several links to the same plan become several lines to that plan. A listed option with no card becomes `- choice · what happens`. When Tom edited a plan's options, the list `show` prints replaces the whole section. `show` marks an option with no label "(not named)": ask Tom for the choice;
  - labelled "then" or unlabelled, between scenes: `plan: [[Earlier]]` in the later plan's `## Requires`;
  - from Now: no requirement; it only means "from where they stand".
  - any other label: work out what must be true and write it as a requirement (`hidden:`, `alive:`, `met:`…), or `check:` when no rule can test it.
- Add the `## Requires` lines the idea needs (secrets hidden, people alive) and `## Links` for what it would change.
- An EDITED plan: write the new `kind:`, `summary:`, `where:`, `present:` and `clock:` as given. Rewrite `## Idea` from his text, turning names back into `[[links]]`; keep any links he removed only if the idea still needs them. Do what his note asks. If it asks for a new name, never rename the file: add the new name to `aliases` and ask Tom. Add a log line, `- S<cur>: idea revised on the Session planner.`
- A DROP: set `status: dropped` and add a log line. Never delete the note.
- A link from the start of a session (`the start of S15`): no requirement; it means "from where they stand at the start of that session".
- Never write canon. Never copy a plan into an entity note.

## Step 3: Propose, then write
Show Tom the new and changed plans, phone-sized, grouped by board. On approval: write them, run `python3 tools/osse/build.py`, fix every problem it prints.

## Step 4: Swap cards for plans, tidy, publish
- For each card that became a plan: `python3 tools/osse/paths_sync.py adopt CARD_ID "Plan name"`. It keeps its place on every board.
- `python3 tools/osse/paths_sync.py tidy` drops Tom's links that the vault now holds, and plans no longer live.
- `python3 tools/osse/paths_sync.py settle` clears the edits and drops the vault now holds, so the cards show the vault's text again.
- Commit `vault/` and push, so the page shows the new plans.
- Report what changed, and any plan the build pruned.

`python3 tools/osse/paths_sync.py export DIR` writes each board as a `.canvas` file Obsidian can open, if Tom asks.
