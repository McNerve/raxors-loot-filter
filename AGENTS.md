# Raxor's Loot Filter

RuneLite loot filter. Daily driver. Load via [FilterScape](https://filterscape.xyz/).

## Names

OSRS words only. Not Aisle / Heat / Kits / Ember.

## Pipeline (top → bottom). Later wins.

`apply` overwrites earlier `apply`. `rule` is terminal.

1. `display` — icons, prices, despawn, beam/sound masters
2. `loot_order` — take-menu sort switches
3. `hide` — junk, value floors, ownership
4. `locations` — this room only (can force-show after hide)
5. `categories` — food, runes, herbs, raid supplies
6. `value` — Low / Medium / High / Insane (Ground Items buckets)
7. `rares` — uniques, alchs, RDT
8. `alerts` — pets, keys, clues-in-containers, forgotten ammo/cannon, mutes
9. `final` — last hide/show + sort ladder
10. `facts` — hidden. Areas, account types, item lists

Value must stay below Categories. Rares below Value. Alerts last so mutes stick.

## Conventions

- `RAX_` — Filterscape config
- `FACT_` — game facts
- Style bodies stay expanded property lists
- One `define:input:<module>` namespace per visible module
- Groups `expanded: false`
- Sounds in `~/.runelite/loot-filters/sounds`
- `src/group_icons.json` + `src/sprites.json` — named `SKILL_*`, not Joe 42xx
- File MUST start with `/*@ define:module`

## Commands

```bash
python3 tools/build.py
```

## Do not

- Commit to `main`
- Copy `VAR_` / Nismo / Cuzco / Joe module names
- Split categories back into two warehouses
- Put value above categories
- Use Joe's 42xx sprite archives
