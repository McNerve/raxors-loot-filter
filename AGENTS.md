# Raxor's Loot Filter

RuneLite loot filter for the Loot Filters plugin. Daily driver. Load via [FilterScape](https://filterscape.xyz/).

## Identity

Heat over chips. Grocery aisle for role. Icons are a policy, not 300 one-offs.

Do not clone Typical-Whack / Joe module names, `VAR_` prefixes, or the 11-module warehouse. Item lists and area coords are game facts — those may overlap. Architecture may not.

## Pipeline (top → bottom)

1. `identity` — base paint, prices, despawn, icon policy knobs
2. `pickup` — menu sort flags
3. `floor` — hide / show
4. `where` — area hide / show
5. `aisle` — category + per-item chips (collapsed groups)
6. `heat` — value temperature; wins over aisle
7. `always` — uniques, alchs, clues, RDT; alchs lock by default
8. `kits` — backpack ping, UIM deathpile, LMS silence
9. `final` — last hide/show + generated sort ladder
10. `facts` — hidden. Areas, account types, item name lists

## Conventions

- `RAX_` — Filterscape-facing config
- `FACT_` — game facts (coords, name lists). Never shown in the UI
- Style bodies stay expanded property lists so Filterscape's style editor works
- One `define:input:<module>` namespace per visible module
- Groups default to `expanded: false`
- Sounds: `tier3.wav`, `tier4.wav`, `uniques.wav`, `clues.wav` in `~/.runelite/loot-filters/sounds`
- Alch icon: `~/.runelite/loot-filters/icons/alch.png`
- Filterscape headers: `src/group_icons.json` + `src/sprites.json`. Skills use named `SKILL_*` from RuneLite `SpriteID` (197–221). Rooms use the signature drop. Never Joe's 42xx skill-tab archives or `1531` GE pin.

## Commands

```bash
python3 tools/build.py
```

Writes `dist/raxors-loot-filter.rs2f`. Import that file (or its GitHub raw URL) in Filterscape.

Rebuild after editing `src/` or after changing the Joe seed path.

## Do not

- Commit to `main` — branch `feat/`
- Copy `VAR_` / Nismo `NLF_` / Cuzco names back in
- Split aisle back into "category styles" + "individual styles"
- Put heat before aisle (expensive food would stay a chip)
- Use Joe's 42xx / 56xx sprite archives for headers
