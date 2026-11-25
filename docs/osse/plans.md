# Plans: the draft layer

A plan is one idea for the future: a scene, a reveal, a twist, an NPC's next move. Plans are cheap. Write many, prune freely. Examples are made up.

```
---
type: plan
stage: draft
status: draft        # draft | ready | played | dropped | pruned
kind: beat           # beat (or empty) | reveal | complication | decision | entrance | exit | scene | clock | pressure | bottleneck (docs/osse/branching.md)
for: "[[Mira Holt]]"  # optional: the player character (or The Party) whose board it sits on
summary: "one line"
scene: "[[The night market]]"   # optional: the scene plan this happens in
cue: "Mira sees the knife"       # optional, in a scene: what triggers it
target: S14          # optional: the session it is aimed at
thread: "[[The Grey Patron]]"   # optional
updated: 2026-11-18
played:              # session, set when it happens
pruned:              # written by the build
pruned_by:           # written by the build
---

## Idea
What happens and why it is interesting.

## Requires
- alive: [[Mira Holt]]
- hidden: [[The bridge was sabotaged]]
- no link: [[Mira Holt]] · social/enemy · [[The Party]]
- plan: [[Mira's offer]]
- by: S18
- check: the party still has reason to go back to the docks

## Links
- [[Mira Holt]] · deed/betrayed · 4 · [[The Party]] · at the gala

## Log
```

**Kinds and options.** A `decision` lists its choices under `## Options`, one per line: `- [[Plan]] · what they choose`; several choices may lead to the same plan. A `scene` sets the stage: `where:` (a place, as a [[link]] when the vault has it), `when:`, `present:` (a list of who is there when it opens) and `purpose:`. Its cards name it with `scene:` and carry a `cue:`: beats, reveals (`reveals: "[[A secret]]"`), complications, decisions (`critical: true` when it can end or remake a character), entrances (`who:`) and exits (`leads_to: ["[[Next scene]]"]`, or `who:` for someone leaving). A `clock` carries `clock: 0/6` (segments filled / segments). Kinds, boards and the research behind them: [branching.md](branching.md).

**Statuses.** `draft`: an idea. `ready`: Tom wants it at the next table. `played`: it happened (set `played: S14`). `dropped`: Tom set it aside. `pruned`: the build found it impossible. Only `draft` and `ready` are live.

## Requirements
One per line under `## Requires`. The build checks every live plan against current canon and prep after every change:

| Line | Holds when |
| --- | --- |
| `alive: [[X]]` | X's state is not dead, destroyed or disbanded |
| `dead: [[X]]` | X's state is dead, destroyed or disbanded |
| `state: [[X]] · captured` | X's state is exactly that (several allowed: `captured, missing`) |
| `met: [[X]]` / `unmet: [[X]]` | X has / has not reached the table (`first_seen`) |
| `hidden: [[S]]` / `revealed: [[S]]` | secret S is still hidden / has been revealed |
| `at: [[X]] · [[Place]]` / `not at: …` | X's `location` is / is not that place |
| `holds: [[Who]] · [[Thing]]` / `not holds: …` | the thing's `holder` is / is not that one |
| `link: [[A]] · family/type · [[B]]` / `no link: …` | a current canon or prep link of that type joins A to B (either direction) / none does |
| `open: [[Thread]]` | the thread is still open |
| `plan: [[P]]` | plan P is still live or played |
| `played: [[P]]` | plan P has been played |
| `by: S18` | the current session is before S18 |
| `check: words` | a judgment the script cannot test; listed for Tom every session (`osse.py plans --checks`) |

**Implicit requirements.** Every note named in `## Links` must be alive (or standing, intact, active). A plan that needs one in another state says so with `dead:` or `state:`, and the implicit one is dropped. An entrance needs its `who:` alive; a reveal needs its `reveals:` secret hidden.

**Draft links** use the connection grammar with both ends written out: `- [[A]] · family/type · weight · [[B]] · note`. A stamp on a draft link is the hoped-for session, not canon. Draft links never go on entity notes; `osse.py walk NAME --plans` shows them.

## Pruning
- When a requirement of a live plan fails, the build sets `status: pruned`, `pruned: S<current>` and `pruned_by:` (which line failed and why), and adds a Log line. Pruning cascades through `plan:` requirements. Nothing is deleted.
- If Tom sets a pruned plan back to `draft` without fixing what failed, the next build prunes it again and says so.
- A plan whose `target` has passed is flagged **stale**, not pruned; Tom retargets or drops it. A `check:` line is never auto-pruned.
- **Overrides.** If play contradicts a plan in a way no requirement captures, prune it by hand during the sync (`status: pruned`, `pruned_by: "overtaken by S14: …"`) and add the missing requirement to any similar plan.
- **Preview** before writing a change: `python3 tools/osse/build.py --dry --assume "Mira Holt: state=dead"` lists what it would prune.
