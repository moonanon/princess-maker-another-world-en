# Game fixes (optional patches)

Fixes to the original game's own behaviour, shipped as separate IPS files on top of the translation
(`tools/rom/build.py --variant ...`). Modules follow the `src/patches/` contract (`NN-topic.py`, `apply(rom)`), run after
every translation module, and may import `src/patches/_layout.py`.

| Dir | Variant | Patch |
| --- | --- | --- |
| `bugfix/` | `bugfix` (and `questing`) | `dist/princess-maker-en-bugfix.ips` — fixes to the original game's bugs, except the quest rating exploit (kept: some players want it) |
| `questing/` | `questing` | `dist/princess-maker-en-questing.ips` — bug fixes + the reputation exploit closed + quest encounters: people act as people (Morality) |

Player-facing notes: `dist/README.md`.
