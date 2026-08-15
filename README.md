# Raxor's Loot Filter

Daily-driver loot filter for RuneLite's [Loot Filters](https://runelite.net/plugin-hub/show/loot-filters) plugin.

Built for [FilterScape](https://filterscape.xyz/). Eight modules, not a warehouse.

## Look

- **Aisle** — role chips (food, runes, herbs, raids…). Joe-style item icons by default, one switch to change them all.
- **Heat** — ink-on-pill temperature. Green → blue → amber → crimson. Beats aisle when an item is actually worth something.
- **Always** — uniques, clues, alchs, RDT. Alchs lock gold.

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
