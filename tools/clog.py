#!/usr/bin/env python3
"""Build src/collection_log.json from the OSRS wiki Collection log page.

Only pages whose slots can hit the floor. Chest/crate/interface pages are
dropped. Each remaining slot is rare (scream) or log (always-show, quiet).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "collection_log.json"
WIKI = "https://oldschool.runescape.wiki/w/Collection_log?action=raw"
UA = "raxors-loot-filter (github.com/McNerve/raxors-loot-filter)"

# Tabs we keep. Clues/minigames/pets-overview are not ground loot.
KEEP_TABS = {"Bosses", "Other"}

# These clog pages never (or almost never) put the unique on the floor.
CHEST = {
    "Barrows Chests",
    "The Fight Caves",
    "The Inferno",
    "Fortis Colosseum",
    "The Gauntlet",
    "Chambers of Xeric",
    "Theatre of Blood",
    "Tombs of Amascut",
    "Wintertodt",
    "Tempoross",
}

# Other-tab pages that are shop, notes, or cosmetics.
SKIP_PAGES = {
    "Aerial Fishing",
    "All Pets",
    "Boat Paints",
    "Camdozaal",
    "Chompy Bird Hunting",
    "Colossal Wyrm Agility",
    "Creature Creation",
    "Forestry",
    "Fossil Island Notes",
    "Hunter Guild",
    "Lost Schematics",
    "Monkey Backpacks",
    "Motherlode Mine",
    "My Notes",
    "Ocean Encounters",
    "Random Events",
    "Rooftop Agility",
    "Sailing Miscellaneous",
    "Sea Treasures",
    "Shayzien Armour",
    "Shooting Stars",
    "Skilling Pets",
    "Miscellaneous",
}

# Clog slots that are on the page but are common loot, not a screenshot unique.
LOG_EXACT = {
    "Dragon knife",
    "Dragon thrownaxe",
    "Soiled page",
    "Burnt page",
    "Soaked page",
    "Desiccated page",
    "Huasca seed",
    "Atlatl dart",
    "Sunfire splinters",
    "Zulrah's scales",
    "Zul-andra teleport",
    "Mole skin",
    "Mole claw",
    "Immaculate mole skin",
    "Ancient essence",
    "Ancient shard",
    "Nihil shard",
    "Frozen tear",
    "Araxyte venom sac",
    "Spider cave teleport",
    "Oathplate shards",
    "Chromium ingot",
    "Demon tear",
    "Mokhaiotl waystone",
    "Key master teleport",
    "Charged ice",
    "Granite dust",
    "Bolt rack",
    "Spirit flakes",
    "Uncut onyx",
    "Barrel of demonic tallow (full)",
    "Chasm teleport scroll",
    "Ardeaglais teleport",
    "Giant egg sac(full)",
    "Pristine spider silk",
    "Gryphon feather",
    "Iasor seed",
    "Kronos seed",
    "Attas seed",
    "Beef",
    "Cow slippers",
    "Mooleta",
}

LOG_SUFFIX = (" seed", " page", " teleport")

# Followers. They do not land on the floor.
PETS = {
    "Abyssal orphan", "Baby Mole", "Baby mole", "Kalphite Princess", "Kalphite princess",
    "Pet smoke devil", "Pet Smoke Devil", "Skotos", "Venenatis spiderling",
    "Callisto cub", "Vet'ion Jr.", "Vet'ion jr.", "Scorpia's offspring",
    "Prince Black Dragon", "Prince black dragon", "Pet snakeling", "Pet Snakeling",
    "Pet kree'arra", "Pet Kree'arra", "Pet general graardor", "Pet General Graardor",
    "Pet zilyana", "Pet Zilyana", "Pet k'ril tsutsaroth", "Pet K'ril Tsutsaroth",
    "Pet kraken", "Pet Kraken", "Hellpuppy", "Pet dark core", "Pet Dark Core",
    "Pet penance queen", "Heron", "Rock golem", "Beaver", "Baby chinchompa",
    "Baby chinchompha", "Giant squirrel", "Tangleroot", "Rift guardian", "Rocky",
    "Herbi", "Chompy chick", "Pet chaos elemental", "Pet Chaos Elemental",
    "Pet dagannoth supreme", "Pet Dagannoth Supreme", "Pet dagannoth prime",
    "Pet Dagannoth Prime", "Pet dagannoth rex", "Pet Dagannoth Rex",
    "Noon", "Midnight", "Ikkle Hydra", "Ikkle hydra", "Sraracha", "Sarachnis cub",
    "Youngllef", "Corrupted youngllef", "Little Nightmare", "Little nightmare",
    "Lil' Zik", "Lil' zik", "Tumeken's guardian", "Nexling", "Wisp", "Butch",
    "Lil'viathan", "Baron", "Muphin", "Quetzin", "Smol Heredit", "Smol heredit",
    "Nid", "Huberte", "Moxi", "Yami", "Maggot marquess", "Bran", "Dom",
    "TzRek-Jad", "Jal-Nib-Rek", "Olmlet", "Phoenix", "Tiny tempor", "Smolcano",
    "Scurry", "Beef", "Mooleta", "Aggy", "Gull", "Vorki",
}

HEAD = re.compile(r"^(={2,})([^=]+)\1\s*$")
PLINK = re.compile(r"\{\{plink\|([^}|]+)")


def fetch() -> str:
    req = urllib.request.Request(WIKI, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def parse_pages(text: str) -> list[dict]:
    tab = None
    page = None
    buf: list[str] = []
    pages: list[dict] = []

    def flush():
        if page and tab:
            pages.append({"tab": tab, "page": page, "raw": "".join(buf)})
        buf.clear()

    for line in text.splitlines(keepends=True):
        m = HEAD.match(line.rstrip("\n"))
        if not m:
            buf.append(line)
            continue
        depth = len(m.group(1))
        name = m.group(2).strip()
        if depth == 2:
            flush()
            page = None
            tab = name
        elif depth >= 3:
            flush()
            page = name
    flush()
    return pages


def items_from(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in PLINK.finditer(raw):
        name = m.group(1).strip()
        if name.startswith("File:") or name.endswith("staff of collection"):
            continue
        if name.startswith("Collection log"):
            continue
        if name in PETS or name.startswith("Pet "):
            continue
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def band(name: str) -> str:
    if name in LOG_EXACT:
        return "log"
    if name.endswith(LOG_SUFFIX):
        return "log"
    return "rare"


def expand(name: str) -> list[str]:
    names = [name]
    if " (uncharged)" in name:
        names.append(name.replace(" (uncharged)", ""))
    if " (inert)" in name:
        names.append(name.replace(" (inert)", ""))
    if " (empty)" in name:
        names.append(name.replace(" (empty)", ""))
    if " (full)" in name:
        names.append(name.replace(" (full)", ""))
    # wiki sometimes title-cases "of/the"
    alt = name.replace(" of the Dead", " of the dead")
    if alt != name:
        names.append(alt)
    return list(dict.fromkeys(names))


def slug(page: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", page.lower()).strip("_")
    return s[:40]


def main() -> None:
    try:
        text = fetch()
    except Exception as e:
        print(f"wiki fetch failed ({e}); using cached session copy", file=sys.stderr)
        cache = Path(
            "/Users/steve/.grok/sessions/%2FUsers%2Fsteve/01a0064f-0271-7a80-ab87-a324c381558d/web_fetch/5.txt"
        )
        text = cache.read_text()

    pages = []
    skipped = []
    for p in parse_pages(text):
        if p["tab"] not in KEEP_TABS:
            continue
        if p["page"] in CHEST or p["page"] in SKIP_PAGES:
            skipped.append(p["page"])
            continue
        items = items_from(p["raw"])
        if not items:
            continue
        rare: list[str] = []
        log: list[str] = []
        for it in items:
            for n in expand(it):
                (log if band(it) == "log" else rare).append(n)
        pages.append(
            {
                "id": slug(p["page"]),
                "tab": p["tab"],
                "page": p["page"],
                "rare": rare,
                "log": log,
            }
        )

    OUT.write_text(json.dumps({"pages": pages, "skipped": skipped}, indent=2) + "\n")
    rare_n = sum(len(p["rare"]) for p in pages)
    log_n = sum(len(p["log"]) for p in pages)
    print(f"wrote {OUT.relative_to(ROOT)} — {len(pages)} pages, {rare_n} rare, {log_n} log")
    for p in pages:
        print(f"  {p['page']}: {len(p['rare'])} rare / {len(p['log'])} log")


if __name__ == "__main__":
    main()
