# Branching: how plans become paths

Session planner, once called Paths ahead (`vault/paths.html`, built by `tools/osse/paths.py`) is Tom's planning board: the whole session as a Running order and as a Canvas, then one board per player character and one for the World (every thread that moves without the party knowing and could still reach them). In the store the session canvas is the lane `The Party` and the World is `world`. This page sets the rules behind it and how they sit on the vault. Examples are made up.

## What the research says, and what we took

| Practice | Source | What it means for Ossë |
| --- | --- | --- |
| **Prep situations, not plots** | Justin Alexander, *Don't Prep Plots* (The Alexandrian) | A plan is a situation to put in front of the party, never a script. Plans stay `draft` until play happens; canon is written from play only. |
| **Branch and bottleneck** | Sam Kabo Ashwell, *Standard Patterns in Choice-Based Games* | Branches fan out, then meet again at beats most paths reach. Keeps prep finite: a pure tree (a "time cave") doubles with every choice. Ossë marks these meeting points as `kind: bottleneck`. |
| **Delayed branching and state** | Ashwell; Choice of Games | Choices matter later through state, not instant forks. Ossë's state is the graph: secrets hidden or revealed, people alive or dead, plans played. `## Requires` reads that state. |
| **Node-based design and the Three Clue Rule** | The Alexandrian, *Node-Based Scenario Design*, *Three Clue Rule* | Nodes are people, places, organizations and events joined by clues. For any conclusion you need, write at least three ways to reach it. A secret's `## How it could come out` lines are its clues; the board shows the count and asks for three. |
| **Fronts and grim portents** | *Dungeon World*, Fronts | The world moves when the party does not. What a danger does if no one stops it is `kind: pressure`: a plan that fires when they stall. |
| **Secrets and clues, apart from where they are found** | Mike Shea, *Return of the Lazy Dungeon Master* | Secrets are written without fixing how they come out. Ossë already keeps secrets as their own notes; plans only say they need one hidden or revealed. |
| **Character-first prep; flags** | Shea, *Review the Characters*; Burning Wheel Beliefs | Start from each character and what they want, not from the plot. Each board starts from where the character stands at the end of the last session. |
| **Scenes and beats** | Robert McKee, *Story*; screenwriting practice | A scene is a unit of place, time and people that sets the stage; a beat is one exchange or turn inside it. Ossë marks the stage as `kind: scene` with its situation (`where:`, `when:`, `present:`, and the Idea) and its `purpose:`; the cards inside it name it with `scene:`. |
| **French scenes; cues** | French classical theatre; stage practice | A new unit starts whenever someone comes in or goes out. Ossë marks these `kind: entrance` and `kind: exit`. Every card in a scene carries a `cue:`, what triggers it, so most beats need no fixed order. |
| **Progress clocks** | John Harper, *Blades in the Dark* | A clock is a circle cut into segments; fill one when time passes or things go wrong, and something happens when it is full. Ossë marks it `kind: clock` with `clock: filled/segments`. |
| **Decision points** | Choice-based design generally | A decision is a choice the character faces, with options. Two choices can lead to the same outcome. Ossë marks it `kind: decision` with an `## Options` section. |

## The board

| Part | What it is | In the vault |
| --- | --- | --- |
| **Start cards** | The first session tab starts from **Now**. Each later tab starts from "After S14", listing what is planned for the session before. A link from an earlier session comes in through the start card, dotted | Now is canon; the later start cards are only the board's plan |
| **Now** | Where the character stands at the end of the last played session: location, status, hit points, spell slots, what happened to them lately | The character note: `location`, `state`, `conditions`, `hp`, `hp_max`, `hp_temp`, `slots`, `sheet_at`; the `## Now` lines stamped with the latest session |
| **Session tabs** | One tab and canvas per session: S14, S15, S16… then Later. Tom plans one session at a time; cards can lead to each other within a session. + Session brings in a session built in the Arc planner, or adds a new one, in an arc or outside them; the × on the open tab deletes it on every board (its plans go back to the tray, his cards move to Later, later sessions move up one). Drag a card onto a tab to move it | `target: S15`; Later means no target |
| **Sessions and arcs** | A session's name, what happens in it and its arc are one card, the same record in the Session planner (the name beside the tabs) and the Arc planner. A card in the Arc planner that is not in the Session planner is an idea; a session can also stay outside the arcs. Planned sessions are numbered by the order of their cards: reorder them in the Arc planner and their tabs, scenes, cards and links take the new numbers. Deleting a session in the Session planner leaves its card as an idea; deleting a card leaves a session with something in it on its own | Arcs never go into the vault |
| **Card types** | A row of buttons, each with its symbol, above both whole-session views and every board. Click one to add it to the scene that is open, or to free canvas; drag one to place it on the canvas, in a scene, or in the Running order | Tom's own cards |
| **Tray** | Live plans for this board not placed yet. At first, every plan with no session target | Live plans; placing one sets its `target` when Tom asks Claude to bring the board in |
| **Cards** | Live plans, by kind (below) | Plan notes |
| **Links** | Solid: the vault already joins them. Dashed red: Tom's, not in the vault yet | `plan: [[X]]` in the later plan's Requires, or a decision's `## Options` |
| **Options** | Each link out of a decision is one option, labelled with the choice; the card lists them. Two choices can lead to the same card: draw a link for each (or tap "Another choice leading here" on the first) | One `## Options` line per link |
| **Secret chips** | A secret a card needs hidden or revealed. Tap to try a what-if | `hidden:` / `revealed:` requirements |
| **Scenes on the board** | A scene is a box with its details in a header: its situation (where, when, who is there, what is going on) and its purpose. Its cards are beats, reveals, complications, decisions, entrances and exits, each with a cue; its panel has a button to add each. Drag it by the header and the cards inside move with it; drag the corner to resize it. Drop a card inside to set it in the scene. Where and who are picked from the vault's places and people, or typed | `where:`, `when:`, `present:`, `purpose:`; `scene:` and `cue:` on the cards inside |
| **One copy** | Every plan, card, scene and link exists once, however many boards show it: change it on one and it changes on all. Session tabs are shared too. Only a thing's place on each canvas is its own; a card inside a scene keeps the same place in the box everywhere | |
| **Scenes on several boards** | A scene shows, with its cards, on the board of every player character listed as present or named by an entrance (The Party: every character's board), on the session canvas, and on any board it was put on. The × on it takes it off that board only, and takes that character off who is present | `present:` |
| **Session canvas** | The second of the two whole-session buttons. Everything in the session, whoever it is for: scenes numbered and joined in running order, loose cards underneath in a column per board. Line up lays it out again from the running order. A plan dropped here goes on the boards it is tied to; × takes it off every board | Nothing |
| **Running order** | The first of the two whole-session buttons. Per session, its scenes as small cards in running order: drag one by its ⠿ to move it, or onto another session's tab. The Scene button (or Add a scene) starts a new one; + Players on a scene adds or removes players, and the scene appears on or leaves their boards to match; the buttons in a scene add a card inside. Exits come last and say where they lead. So a session can be built scenes first. Tap a scene to list its cards as a tree: each sits under the card whose arrow leads to it. Drag a card onto another to make it follow that one (onto a decision, it becomes an option and asks for the choice), between two to sit beside them, onto a scene to add it there, or back to "Not in a scene". Arrows and places on the canvas follow, and a card with others under it takes them along. Drag in plans not placed yet from the list on the right. Tap a card to open its panel. Name pills use the session screens' colours (filled: listed as present; outlined: on their board only); tap one to open the scene on that board | Nothing; the running order stays on the relay (`order`), and Claude follows it when building the session screen |
| **Zoom** | + and − at the top right of the canvas, beside Fit and Key; also pinch or Command-scroll | |
| **Tom's own cards** | New ideas drawn on the board | Become plan notes when Tom asks (the `paths` skill) |
| **Claude's drafts** | Tom brain dumps in a session of this repo, or asks for a clean-up; Claude shows an outline, then puts scenes, cards and links on the boards. Cards say "Claude's draft" until Tom changes them, and a whole draft can be taken back off | Nothing until Tom asks (the `paths` skill) |
| **Edits** | Tom changes a plan's kind, summary or idea on the board, or leaves Claude a note. The card says "edited · not in vault" | Written into the plan note when Tom asks; the plan keeps its name |
| **Deleting** | The × on a card takes a plan back to the tray, or deletes Tom's own card. Drop this plan (in its panel) removes it from the board and the tray | A dropped plan gets `status: dropped` when Tom asks |

## Plan kinds

`kind:` on a plan note. Empty means beat.

| Kind | Use it for | On the board | Term |
| --- | --- | --- | --- |
| `scene` | The stage. Situation: `where:`, `when:`, `present:` (who is there when it opens) and the Idea. `purpose:` what it is for | A box; the cards inside it happen during the scene | `osse:Scene` |
| `beat` | A turn that could happen in a scene. `cue:` | A card | `osse:Beat` |
| `reveal` | A beat where something comes out. `cue:`, `reveals:` (the secret) | A card | `osse:Reveal` |
| `complication` | A beat that turns the scene against what someone wants. `cue:` | A card | `osse:Complication` |
| `decision` | A choice the character faces; each link out of it is one option. `cue:`; `critical: true` when it can end or remake a character | A card listing its options; a critical one is filled red | `schema:ChooseAction` |
| `entrance` | Someone comes in. `cue:`, `who:` | A card | `osse:Entrance` |
| `exit` | A way the scene can end, `leads_to:` the next scenes; or someone leaving, `who:`. `cue:` | A card listing where it leads | `osse:Exit` |
| `clock` | Time pressure, or something that happens when it fills. `clock: 2/6` | A card with a segmented clock; tap it to fill a segment | `osse:Clock` |
| `pressure` | What the world does if no one acts | A card | `osse:Pressure` |
| `bottleneck` | A beat most paths reach, where branches meet | A card with a double edge | `osse:Bottleneck` |

A card inside a scene names it with `scene: "[[Scene plan]]"`. Scenes do not nest. Beat, reveal, complication, decision, entrance and exit are the kinds offered inside a scene; clocks, pressures and bottlenecks belong outside (one placed in a scene before this still works).

What the graph does with them: an `entrance` needs its `who:` alive, and a `reveal` needs its secret still hidden, so the build prunes either when that stops being true. An exit's `leads_to:` requires nothing of the next scene, so several exits can lead to it. `python3 tools/osse/osse.py scene NAME` puts a scene back together from its notes; `python3 tools/osse/paths_sync.py notes SCENE` turns a scene on the boards into notes.

```
---
type: plan
kind: scene
status: draft
summary: "A masked ball at the manor, the night the steward goes missing"
where: "[[Aerrowyn Manor]]"
when: "the night of the ball"
purpose: "introduce the courier; force a choice about the steward"
present: ["[[Corvane Aerrowyn]]", "[[The Party]]", "a masked courier"]
target: S15
---
```

## Decisions

```
---
type: plan
kind: decision
status: draft
summary: "Belaskro must answer Corvane about his father and sister"
for: "[[Belaskro Tich]]"
---
## Idea
Corvane asks him to send for Aldous and Sloane.

## Options
- [[Belaskro tells Corvane the truth]] · he tells the truth
- [[Belaskro lies to Corvane]] · he covers for himself

## Requires
- alive: [[Corvane Aerrowyn]]
```

Each option leads to a plan note; several options may lead to the same one, one line each. An option plan names the decision under `## Requires` with `plan: [[decision]]` only when it cannot happen without that choice being put to the character. When play makes the choice, the sync marks the chosen plan played and the others `dropped`.

## Which board a plan is on
1. `for:` names one or more player characters, or The Party.
2. Else the characters named in its Links or Requires. A scene is also on the board of everyone in its `present:`.
3. Else a character tied at weight 5 to someone it names (shown as "through Corvane Aerrowyn").
4. Else the session canvas (the whole party) when it names The Party; else the World.

## Rules
- The board never changes the vault. Tom's placing, linking and cards wait on the Gus relay (`paths.json`: one store of `items`, `cards`, `edits`, `edges` and `order`, plus each board as JSON Canvas 1.0 under `lanes`; game master only) until Tom asks Claude to bring them in (the `paths` skill).
- The page looks for changes every 20 seconds and before every save, and merges them record by record, so a draft from a session and Tom's own changes (on any device) both survive. Where both changed the same thing, the page's change wins.
- Nothing on the board is canon. The Now card is canon (it reads stamped lines and the sheet values the post-session sync records).
- Keep branches short and bring them back together. Two or three options per decision, and a bottleneck within a few sessions, beat a wide tree.
- Every secret a card needs should have at least three ways it could come out.
- Give each board at least one pressure, so the world moves when the party does not.
