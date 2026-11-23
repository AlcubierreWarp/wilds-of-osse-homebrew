# Branching: how plans become paths

Paths ahead (`vault/paths.html`, built by `tools/osse/paths.py`) is Tom's planning board: one board per player character, plus The Party and Around the party. This page sets the rules behind it and how they sit on the vault. Examples are made up.

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
| **Scenes and beats** | Robert McKee, *Story*; screenwriting practice | A scene is a unit of place, time and people that sets the stage; a beat is one exchange or turn inside it. Ossë marks the stage as `kind: scene` (with `where:` and `present:`) and the moments inside it as beats, decisions, clocks and pressures that name it with `scene:`. |
| **Progress clocks** | John Harper, *Blades in the Dark* | A clock is a circle cut into segments; fill one when time passes or things go wrong, and something happens when it is full. Ossë marks it `kind: clock` with `clock: filled/segments`. |
| **Decision points** | Choice-based design generally | A decision is a choice the character faces, with options. Each option leads to its own plan. Ossë marks it `kind: decision` with an `## Options` section. |

## The board

| Part | What it is | In the vault |
| --- | --- | --- |
| **Start cards** | The first session tab starts from **Now**. Each later tab starts from "After S14", listing what is planned for the session before. A link from an earlier session comes in through the start card, dotted | Now is canon; the later start cards are only the board's plan |
| **Now** | Where the character stands at the end of the last played session: location, status, hit points, spell slots, what happened to them lately | The character note: `location`, `state`, `conditions`, `hp`, `hp_max`, `hp_temp`, `slots`, `sheet_at`; the `## Now` lines stamped with the latest session |
| **Session tabs** | One tab and canvas per session: S14, S15, S16… then Later. Tom plans one session at a time; cards can lead to each other within a session. + Session adds the next one; the × on the open tab deletes it (its plans go back to the tray, his cards move to Later, later sessions move up one). Drag a card onto a tab to move it | `target: S15`; Later means no target |
| **Tray** | Live plans for this board not placed yet. At first, every plan with no session target | Live plans; placing one sets its `target` when Tom asks Claude to bring the board in |
| **Cards** | Live plans, by kind (below) | Plan notes |
| **Links** | Solid: the vault already joins them. Dashed red: Tom's, not in the vault yet | `plan: [[X]]` in the later plan's Requires, or a decision's `## Options` |
| **Secret chips** | A secret a card needs hidden or revealed. Tap to try a what-if | `hidden:` / `revealed:` requirements |
| **Scenes on the board** | A scene is a box with its details in a header: where, who is present, the situation. Drag it by the header and the cards inside move with it; drag the corner to resize it. Drop a card inside to set it in the scene. Where and who are picked from the vault's places and people, or typed | `where:`, `present:`; `scene:` on the cards inside |
| **Zoom** | + and − at the top right of the canvas, beside Fit and Key; also pinch or Command-scroll | |
| **Tom's own cards** | New ideas drawn on the board | Become plan notes when Tom asks (the `paths` skill) |
| **Edits** | Tom changes a plan's kind, summary or idea on the board, or leaves Claude a note. The card says "edited · not in vault" | Written into the plan note when Tom asks; the plan keeps its name |
| **Deleting** | The × on a card takes a plan back to the tray, or deletes Tom's own card. Drop this plan (in its panel) removes it from the board and the tray | A dropped plan gets `status: dropped` when Tom asks |

## Plan kinds

`kind:` on a plan note. Empty means beat.

| Kind | Use it for | On the board | Term |
| --- | --- | --- | --- |
| `scene` | The stage: a place, who is there, what is going on. `where:` and `present:` | A box; the cards inside it happen during the scene | `osse:Scene` |
| `beat` | One key moment in a scene or encounter | A card | `osse:Beat` |
| `decision` | A choice the character faces; each option is its own plan | A card listing its options | `schema:ChooseAction` |
| `clock` | Time pressure, or something that happens when it fills. `clock: 2/6` | A card with a segmented clock; tap it to fill a segment | `osse:Clock` |
| `pressure` | What the world does if no one acts | A card | `osse:Pressure` |
| `bottleneck` | A beat most paths reach, where branches meet | A card with a double edge | `osse:Bottleneck` |

A beat, decision, clock or pressure inside a scene names it with `scene: "[[Scene plan]]"`. Scenes do not nest.

```
---
type: plan
kind: scene
status: draft
summary: "A masked ball at the manor, the night the steward goes missing"
where: "[[Aerrowyn Manor]]"
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

Each option is its own plan note. An option plan names the decision under `## Requires` with `plan: [[decision]]` only when it cannot happen without that choice being put to the character. When play makes the choice, the sync marks the chosen plan played and the others `dropped`.

## Which board a plan is on
1. `for:` names one or more player characters, or The Party.
2. Else the characters named in its Links or Requires.
3. Else a character tied at weight 5 to someone it names (shown as "through Corvane Aerrowyn").
4. Else The Party when it names The Party; else Around the party.

## Rules
- The board never changes the vault. Tom's placing, linking and cards wait on the Gus relay (`paths.json`, JSON Canvas 1.0, game master only) until Tom asks Claude to bring them in (the `paths` skill).
- Nothing on the board is canon. The Now card is canon (it reads stamped lines and the sheet values the post-session sync records).
- Keep branches short and bring them back together. Two or three options per decision, and a bottleneck within a few sessions, beat a wide tree.
- Every secret a card needs should have at least three ways it could come out.
- Give each board at least one pressure, so the world moves when the party does not.
