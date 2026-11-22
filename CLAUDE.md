# wilds-of-osse-homebrew

Homebrew content for the Wilds of Ossë D&D 5e campaign, packaged for 5e.tools, plus the game master screen pages in `screen/`. Players load the combined file by its raw link.

Change model: Direct. Commit to main.

## Commands
- Build: `python3 tools/build.py` (merges `src/` into `wilds-of-osse.json`)
- Check before every commit: `python3 tools/build.py && python3 -c "import json; d=json.load(open('wilds-of-osse.json')); assert d['_meta']['sources']; print(len(d.get('monster', [])), 'creatures')"`

## Where things live
- `src/`: the content, one file per group, and `_meta.json` (source block, version, timestamps). Edit these.
- `wilds-of-osse.json`: the combined file players load. Generated; never edit it by hand.
- `tools/build.py`: the merge script.
- `screen/`: game master screen pages. One page per session, `screen/sNN.html`.
- `relay/gus/`: the AWS relay behind `screen/gus.html` (Gus's memory archive). `deploy.sh` deploys it; keys live in the macOS Keychain.
- `.claude/skills/session-screen/`: how to build and publish a session screen. Follow it for every new one.
- `.claude/skills/gus-document/`: how to write a new Gus document and file it, sealed, in Gus's archive. Follow it for every new one.
- `.github/workflows/build-homebrew.yml`: rebuilds and commits the combined file when `src/` changes.

## Conventions
- Follow the 5e.tools homebrew schema. Keep each creature in the file for its group.
- After the Action rebuilds the combined file it commits to main, so pull before the next change.

## Hard rules
- Never rename or move `wilds-of-osse.json`, and never rename the repository or the `main` branch: players' saved raw link depends on all three.
- This repository is public. No personal details, no secrets.
