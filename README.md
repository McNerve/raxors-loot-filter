# Raxor's Loot Filter

Daily-driver loot filter for RuneLite's [Loot Filters](https://runelite.net/plugin-hub/show/loot-filters) plugin.

Built for [FilterScape](https://filterscape.xyz/). Eight modules. Later modules win.

## Modules (top to bottom)

1. **Display** — icons, prices, despawn, beam/sound masters
2. **Loot order** — take-menu
3. **Hide** — junk and ownership
4. **Locations** — this room only
5. **Food / Potions / Runes / Ammo / Herbs / Armour / Prayer / Gathering / Raid supplies / Slayer / Currency** — one accordion row per kind
6. **Value** — Low / Medium / High / Insane
7. **Clues** — whole trail per tier
8. **Rares** — collection log pages (ground slots), alchs, RDT
9. **Alerts** — pets, keys, forgotten ammo/cannon, mutes

## Load it

FilterScape → New filter → Show advanced options → Filter URL. Use the **raw** file, not the GitHub blob page:

```
https://raw.githubusercontent.com/McNerve/raxors-loot-filter/refs/heads/feat/raxor-v1/filter.rs2f
```

```bash
python3 tools/build.py
```

Copy these next to the plugin if you don't already have them from Joe's filter:

- `~/.runelite/loot-filters/sounds/tier3.wav`
- `~/.runelite/loot-filters/sounds/tier4.wav`
- `~/.runelite/loot-filters/sounds/uniques.wav`
- `~/.runelite/loot-filters/sounds/clues.wav`
- `~/.runelite/loot-filters/icons/alch.png`

## Edit

`src/` is the authored filter. `generated/` is compiled from your current Joe seed plus the sort ladder. Don't hand-edit `generated/` or `dist/`.
