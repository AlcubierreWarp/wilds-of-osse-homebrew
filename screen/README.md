# DM Screen tools: The Toast (Session 12)

Small single-file tools for the 5e.tools DM Screen. Add one with a panel's **Embed** option and paste its address.
They need GitHub Pages turned on for this repository (Settings, Pages, deploy from the `main` branch).

| Tool | Address |
|---|---|
| Round clock | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/clock.html |
| Champions | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/champions.html |
| Knives' turn | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/knives.html |
| Crowd die | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/crowd.html |
| Voices | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/voices.html |
| Initiative | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/initiative.html |
| Stat blocks | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/statblocks.html |
| All seven in one | https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/all.html |

The clock, champions, knives and crowd panels share one fight state in the browser and stay in sync.
Voices reads `voices-toast.json` by default; add `?data=<address of another JSON file>` to reuse it for a different scene.
Stat blocks reads `stats-toast.json` by default; add `?stats=<address of another JSON file>` to reuse it. These blocks reflect the Session 12 table rules (player-rolled defense, static damage), not the raw homebrew entries.

## Session 13: The Last Bell

One page, `s13.html`, holds every panel. Everything shares one state in the browser, so a name marked dead or a clue ticked in one panel shows in the others.

Base: https://alcubierrewarp.github.io/wilds-of-osse-homebrew/screen/s13.html

Whole screen, three tabs laid out for a vertical monitor. Add the tab to the end of the base address:

| Tab | Add | Movements |
|---|---|---|
| Last Bell | `#tab1` | 1 |
| Aftermath | `#tab2` | 2 and 3 |
| Hard Out | `#tab3` | 4 and 5 |

The Next button in Spotlight moves to the right tab by itself. Keys 1, 2 and 3 also switch tabs.

Single panels, one per 5e.tools Embed. Use these on a landscape screen:

| Panel | Add |
|---|---|
| Spotlight | `#panel=spot` |
| Roll call | `#panel=roll` |
| The Hand | `#panel=hand` |
| Initiative | `#panel=init` |
| Evidence | `#panel=evidence` |
| Voices | `#panel=voices` |
| Speeches | `#panel=speech` |
| Stat blocks | `#panel=stats` |
| Sealed | `#panel=sealed` |
