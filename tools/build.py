#!/usr/bin/env python3
"""Compile Raxor's Loot Filter.

Reads the Joe seed (game facts + your hide/chip lists), rewrites it into
Raxor's pipeline, and emits dist/raxors-loot-filter.rs2f.

Authored code lives in src/. This script never copies Typical-Whack module
names, VAR_ prefixes, or the 11-module warehouse.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
GEN = ROOT / "generated"
DIST = ROOT / "dist"
JOE = Path(
    "/Users/steve/Documents/GitHub/dotFiles/runelite/loot-filters/filters/Joe_s_filter.rs2f"
)

MODULE_SPLIT = re.compile(r"/\*@ define:module:(\S+)")
MODULE_HEADER = re.compile(r"/\*@ define:module:.*?^\*/\s*", re.S | re.M)
INPUT_NS = re.compile(r"define:input:\S+")
GROUP_STYLES = re.compile(r"^group:\s*(.+?)\s*Styles\s*$", re.M)


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def raxify(text: str) -> str:
    text = text.replace("VAR_", "RAX_")
    text = text.replace("CONST_", "FACT_")
    return text


def strip_module_header(chunk: str) -> str:
    return MODULE_HEADER.sub("", chunk, count=1).strip() + "\n"


def split_joe(src: str) -> dict[str, str]:
    matches = list(MODULE_SPLIT.finditer(src))
    if not matches:
        die("Joe seed has no modules")
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(src)
        out[m.group(1)] = src[m.start() : end]
    return out


def rewrite_inputs(body: str, namespace: str) -> str:
    return INPUT_NS.sub(f"define:input:{namespace}", body)


def load_sprite_catalog() -> dict[str, int]:
    raw = json.loads((SRC / "sprites.json").read_text())
    return {k: int(v) for k, v in raw.items() if not k.startswith("_")}


def resolve_icon(spec: dict, catalog: dict[str, int]) -> dict:
    if "sprite" in spec:
        name = spec["sprite"]
        if name not in catalog:
            die(f"unknown sprite name {name!r} — add it to src/sprites.json")
        return {
            "type": "sprite",
            "spriteId": catalog[name],
            "spriteIndex": int(spec.get("index", 0)),
        }
    if "item" in spec:
        return {"type": "itemId", "itemId": int(spec["item"])}
    if spec.get("type") in {"sprite", "itemId"}:
        return spec
    return {}


def load_group_icons() -> dict:
    catalog = load_sprite_catalog()
    raw = json.loads((SRC / "group_icons.json").read_text())
    out = {}
    for k, v in raw.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        out[k] = resolve_icon(v, catalog)
    return out


def emit_group_header(name: str, spec: dict) -> str:
    quoted = name if name.startswith('"') else name
    if any(c in name for c in ":/") and not name.startswith('"'):
        quoted = json.dumps(name)
    lines = [
        "/*@ define:group",
        "---",
        f"name: {quoted}",
    ]
    kind = spec.get("type")
    if kind == "sprite":
        lines += [
            "icon:",
            "  type: sprite",
            f"  spriteId: {spec['spriteId']}",
            f"  spriteIndex: {spec.get('spriteIndex', 0)}",
        ]
    elif kind == "itemId":
        lines += [
            "icon:",
            "  type: itemId",
            f"  itemId: {spec['itemId']}",
        ]
    lines += ["expanded: false", "*/", ""]
    return "\n".join(lines)


def inject_group_icons(body: str, icons: dict) -> str:
    found: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"^group: (.+)$", body, re.M):
        key = raw.strip().strip('"')
        if key not in seen:
            seen.add(key)
            found.append(key)
    headers = []
    missing = []
    for key in found:
        spec = icons.get(key)
        if not spec:
            missing.append(key)
            spec = {}
        headers.append(emit_group_header(key, spec))
    if missing:
        print("note: no icon mapped for: " + ", ".join(missing))
    return "".join(headers) + "\n" + body


def collapse_groups(body: str) -> str:
    def inject(match: re.Match) -> str:
        block = match.group(0)
        if re.search(r"^expanded:", block, re.M):
            return block
        return block.replace("\n*/", "\nexpanded: false\n*/", 1)

    return re.sub(r"/\*@ define:group\n---.*?^\*/", inject, body, flags=re.S | re.M)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text)


def emit_hide(mods: dict[str, str], icons: dict) -> None:
    body = strip_module_header(mods["filtering"])
    body = raxify(body)
    body = rewrite_inputs(body, "hide")
    body = collapse_groups(body)
    body = inject_group_icons(body, icons)
    write(GEN / "30_hide_body.rs2f", body)


def emit_locations(mods: dict[str, str], icons: dict) -> None:
    body = strip_module_header(mods["area_based_filtering"])
    body = raxify(body)
    body = rewrite_inputs(body, "locations")
    body = collapse_groups(body)
    body = inject_group_icons(body, icons)
    write(GEN / "40_locations_body.rs2f", body)


def emit_categories(mods: dict[str, str], icons: dict) -> list[str]:
    cat = strip_module_header(mods["item_category_styles"])
    ind = strip_module_header(mods["individual_item_styles"])
    body = cat + "\n" + ind
    body = raxify(body)
    body = rewrite_inputs(body, "categories")
    body = GROUP_STYLES.sub(r"group: \1", body)
    body = collapse_groups(body)
    body = inject_group_icons(body, icons)

    literals: list[str] = []
    seen: set[str] = set()
    for name in re.findall(r'name:"([^"]+)"', body):
        if name not in seen:
            seen.add(name)
            literals.append(name)

    facts = sorted(set(re.findall(r"name:(FACT_[A-Z0-9_]+)", body)))
    quoted = ", ".join(f'"{n}"' for n in literals)
    fact_or = " || ".join(f"name:{f}" for f in facts)
    cond = "name:RAX_CATEGORY_NAMES"
    if fact_or:
        cond = f"({cond} || {fact_or})"

    banner = (
        "// generated categories — Value overwrites these when gp is real.\n"
        f"#define RAX_CATEGORY_NAMES [{quoted}]\n\n"
    )
    force = (
        "\napply (RAX_SHOW_ICONS && RAX_FORCE_CATEGORY_ICON && "
        + cond
        + ") {\n    RAX_CATEGORY_ICON_STYLE\n}\n"
    )
    write(GEN / "50_categories_body.rs2f", banner + body + force)
    emit_kinds(banner + body, force)
    return literals


KINDS = [
    ("food", "Food", "What you eat"),
    ("potions", "Potions", "What you drink"),
    ("runes", "Runes", "What you cast"),
    ("ammo", "Ammo", "What you shoot"),
    ("herbs", "Herbs", "Grimy, clean, secondaries"),
    ("armour", "Armour", "Bronze to dragon"),
    ("prayer", "Prayer", "Bones, ashes, heads"),
    ("gathering", "Gathering", "Ores, bars, logs, seeds"),
    ("raid_supplies", "Raid supplies", "Cox, ToB, ToA, Gauntlet"),
    ("slayer_drops", "Slayer", "Task tokens and junk"),
    ("currency", "Currency", "Coins and tokens"),
]

GROUP_KIND = {
    "Food": "food",
    "Fish": "food",
    "Potato": "food",
    "Pie": "food",
    "Pizza": "food",
    "Raw Fish": "food",
    "Potions": "potions",
    "Runes": "runes",
    "Ammo": "ammo",
    "Fletching": "ammo",
    "Herblore": "herbs",
    "Herbs": "herbs",
    "Metal Equipment": "armour",
    "Prayer": "prayer",
    "Mining": "gathering",
    "Smithing": "gathering",
    "Woodcutting": "gathering",
    "Fishing": "gathering",
    "Farming": "gathering",
    "Construction": "gathering",
    "Logs": "gathering",
    "Ores": "gathering",
    "Bars": "gathering",
    "Gems": "gathering",
    "Fishing Bait": "gathering",
    "Fishing Equipment": "gathering",
    "Chambers of Xeric": "raid_supplies",
    "Theatre of Blood": "raid_supplies",
    "Tombs of Amascut": "raid_supplies",
    "Tormented Demons Drop": "raid_supplies",
    "Gauntlet": "raid_supplies",
    "Slayer": "slayer_drops",
    "Currency": "currency",
    "Misc": "currency",
    "Clue Scrolls": None,
}


def _input_chunks(text: str) -> list[str]:
    starts = [m.start() for m in re.finditer(r"/\*@ define:input:", text)]
    chunks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[start:end]
        cut = chunk.find("apply (RAX_SHOW_ICONS && RAX_FORCE_CATEGORY_ICON")
        if cut != -1:
            chunk = chunk[:cut]
        chunks.append(chunk)
    return chunks


def emit_kinds(body: str, force: str) -> None:
    extras = (SRC / "51_supplies.rs2f").read_text()
    group_headers: dict[str, str] = {}
    for block in re.findall(r"/\*@ define:group\n---.*?^\*/", body, flags=re.S | re.M):
        nm = re.search(r"^name: (.+)$", block, re.M)
        if nm:
            group_headers[nm.group(1).strip().strip('"')] = block
    buckets: dict[str, list[str]] = {kid: [] for kid, _, _ in KINDS}
    skipped = []
    for chunk in _input_chunks(body) + _input_chunks(extras):
        gm = re.search(r"^group: (.+)$", chunk, re.M)
        group = gm.group(1).strip().strip('"') if gm else ""
        kind = GROUP_KIND.get(group)
        if kind is None:
            skipped.append(group or "(no group)")
            continue
        buckets[kind].append(rewrite_inputs(chunk, kind).rstrip() + "\n")
    if skipped:
        print("note: kind-split skipped groups: " + ", ".join(sorted(set(skipped))))

    for i, (kid, name, subtitle) in enumerate(KINDS):
        header = (
            f"/*@ define:module:{kid}\n"
            f"---\n"
            f"name: {name}\n"
            f"subtitle: {subtitle}\n"
            f"description: |\n"
            f"  How this kind looks. Value (below) overwrites once the drop is worth real gp.\n"
            f"*/\n\n"
        )
        extra = ""
        if i == 0:
            extra += "// names used by the force-icon pass\n"
            extra += re.search(r"#define RAX_CATEGORY_NAMES .+", body).group(0) + "\n\n"
        if i == len(KINDS) - 1:
            extra += force + "\n"
        used = []
        seen_g = set()
        for chunk in buckets[kid]:
            gm = re.search(r"^group: (.+)$", chunk, re.M)
            if not gm:
                continue
            gname = gm.group(1).strip().strip('"')
            if gname in seen_g:
                continue
            seen_g.add(gname)
            if gname in group_headers:
                used.append(group_headers[gname] + "\n")
        write(GEN / f"5x_{kid}.rs2f", header + extra + "".join(used) + "".join(buckets[kid]))


def emit_lists(mods: dict[str, str]) -> None:
    alch = mods["alchs"]
    rdt = mods["rare_drop_table"]

    def grab_define(chunk: str, old: str, new: str) -> str:
        m = re.search(
            rf"#define {re.escape(old)} (.+?)(?=\n\n|\n/\*|/\*@|\napply |\nrule |\Z)",
            chunk,
            re.S,
        )
        if not m:
            die(f"missing {old}")
        return f"#define {new} {m.group(1).strip()}\n"

    alchs_body = raxify(grab_define(alch, "VAR_ALCHS_ITEM_LIST", "RAX_ALCHS_LIST"))

    def value_of(define_line: str) -> str:
        return define_line.split(" ", 2)[2].strip()

    write(GEN / "69_lists.rs2f", alchs_body + "\n")
    write(GEN / "69_list_values.txt", value_of(alchs_body) + "\n")

    applies = []
    for m in re.finditer(
        r'apply \(name:"([^"]+)" && quantity:==(\d+)\) \{\s*VAR_RDT_CUSTOMSTYLE\s*\}',
        rdt,
    ):
        applies.append(
            f'apply (name:"{m.group(1)}" && quantity:=={m.group(2)}) {{\n'
            f"    RAX_RDT_STYLE\n"
            f"}}\n"
        )
    # de-dupe while keeping order
    seen = set()
    unique_applies = []
    for a in applies:
        if a not in seen:
            seen.add(a)
            unique_applies.append(a)
    write(GEN / "71_rdt.rs2f", "// generated RDT quantity matches\n" + "".join(unique_applies))


def _json_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


def emit_rooms() -> None:
    raw = json.loads((SRC / "rooms.json").read_text())
    rooms = raw["rooms"]
    icons = load_group_icons()
    lines = ["// authored rooms — after Joe so these hide/show lists win.\n"]
    for room in rooms:
        gid = room["id"].upper()
        group = room["group"]
        quoted = json.dumps(group) if any(c in group for c in ":/") else group
        spec = icons.get(group) or resolve_icon(room.get("icon", {}), load_sprite_catalog())
        lines.append("\n" + emit_group_header(group, spec))
        areas = " || ".join(f"area:{a}" for a in room["areas"])
        show = _json_list(room.get("show", []))
        hide = _json_list(room.get("hide", []))
        lines.append(
            f"""
/*@ define:input:locations
type: stringlist
label: {group} force shown
group: {quoted}
*/
#define RAX_ROOM_{gid}_SHOW {show}

/*@ define:input:locations
type: stringlist
label: {group} force hidden
group: {quoted}
*/
#define RAX_ROOM_{gid}_HIDE {hide}

apply (({areas}) && name:RAX_ROOM_{gid}_HIDE) {{
    hidden = true;
}}

apply (({areas}) && name:RAX_ROOM_{gid}_SHOW) {{
    hidden = false;
}}
"""
        )
    write(GEN / "41_rooms.rs2f", "".join(lines))


def emit_uniques() -> None:
    raw = json.loads((SRC / "collection_log.json").read_text())
    pages = raw["pages"]
    icons = load_group_icons()
    rare_union: list[str] = []
    log_union: list[str] = []
    rare_seen: set[str] = set()
    log_seen: set[str] = set()
    lines = [
        "// collection log pages — ground slots only. rare screams, log is quiet.\n"
    ]
    for page in pages:
        gid = page["id"].upper()
        group = page["page"]
        quoted = json.dumps(group) if any(c in group for c in ":'/") else group
        spec = icons.get(group) or {}
        lines.append("\n" + emit_group_header(group, spec))
        rare = page.get("rare") or []
        log = page.get("log") or []
        for name in rare:
            if name not in rare_seen:
                rare_seen.add(name)
                rare_union.append(name)
        for name in log:
            if name not in log_seen and name not in rare_seen:
                log_seen.add(name)
                log_union.append(name)
        lines.append(
            f"""
/*@ define:input:rares
type: boolean
label: Highlight {group}
group: {quoted}
*/
#define RAX_CLOG_{gid} true

/*@ define:input:rares
type: stringlist
label: Rare slots
group: {quoted}
*/
#define RAX_CLOG_{gid}_RARE {_json_list(rare)}

apply (RAX_UNIQUE_ENABLE && RAX_CLOG_{gid} && name:RAX_CLOG_{gid}_RARE) {{
    hidden = false;
    RAX_UNIQUE_STYLE
}}
"""
        )
        if log:
            lines.append(
                f"""
/*@ define:input:rares
type: stringlist
label: Log slots
group: {quoted}
*/
#define RAX_CLOG_{gid}_LOG {_json_list(log)}

apply (RAX_NOTABLE_ENABLE && RAX_CLOG_{gid} && name:RAX_CLOG_{gid}_LOG) {{
    hidden = false;
    RAX_NOTABLE_STYLE
}}
"""
            )
    lines.append(f"\n#define RAX_UNIQUES_LIST {_json_list(rare_union)}\n")
    write(GEN / "70_uniques_body.rs2f", "".join(lines))
    write(GEN / "70_notable.txt", _json_list(log_union) + "\n")
    print(f"clog emit: {len(pages)} pages, {len(rare_union)} rare, {len(log_union)} log")


def emit_clues() -> None:
    raw = json.loads((SRC / "clues.json").read_text())
    lines = ["// authored clue families — scroll/box/nest/bottle/geode/casket.\n"]
    for tier in raw["tiers"]:
        tid = tier["id"].upper()
        label = tier["label"]
        items = _json_list(tier["items"])
        style = (
            f'textColor = "#FFFFFFFF"; backgroundColor = "#80908062"; '
            f'borderColor = "{tier["border"]}"; textAccentColor = "#FF000000"; '
            f'menuTextColor = "{tier["border"]}"; sound = "clues.wav"; icon = CurrentItem();'
        )
        lines.append(
            f"""
/*@ define:input:clues
type: style
label: {label}
group: Trail
exampleItem: {tier["example"]}
exampleItemId: {tier["exampleId"]}
*/
#define RAX_CLUE_{tid}_STYLE {style}

#define FACT_CLUE_{tid} {items}

apply (RAX_CLUE_ENABLE && name:FACT_CLUE_{tid}) {{
    hidden = false;
    RAX_CLUE_{tid}_STYLE
}}
"""
        )
    write(GEN / "65_clues_body.rs2f", "".join(lines))


def value_bands() -> list[tuple[int, int | None]]:
    bands: list[tuple[int, int | None]] = []
    for i in range(10):
        bands.append((i * 10, (i + 1) * 10))
    for step, start, stop in (
        (100, 100, 1000),
        (1000, 1000, 10000),
        (10000, 10000, 100000),
        (100000, 100000, 1000000),
        (1000000, 1000000, 10000000),
        (10000000, 10000000, 100000000),
        (100000000, 100000000, 1000000000),
        (100000000, 1000000000, 2000000000),
    ):
        n = start
        while n < stop:
            bands.append((n, n + step))
            n += step
    bands.append((2000000000, None))
    return bands


def emit_final() -> None:
    bands = value_bands()
    lines = [
        "/*@ define:module:final",
        "hidden: true",
        "name: final",
        "*/",
        "",
        "// Last hide/show pass + generated sort ladder (replaces ~800 pasted applies).",
        "",
        "apply (name:RAX_GLOBAL_HIDE) {",
        "    hidden = true;",
        "}",
        "apply (name:RAX_GLOBAL_SHOW) {",
        "    hidden = false;",
        "}",
        "",
        "#define RAX_SORT_BAND(_cond, _lo, _hi, _pri) apply (_cond && value:>=_lo && value:<_hi) { menuSort = _pri; }",
        "#define RAX_SORT_CEIL(_cond, _lo, _pri) apply (_cond && value:>=_lo) { menuSort = _pri; }",
        "",
        "#define RAX_SORT_VALUE (RAX_SORT_BY_VALUE || RAX_SORT_STACKABLES_FIRST)",
        "#define RAX_SORT_STACK (RAX_SORT_STACKABLES_FIRST && (stackable:true || noted:true))",
        "#define RAX_SORT_UNTRADE (RAX_SORT_UNTRADEABLE_FIRST && tradeable:false)",
        "",
    ]

    def emit_scale(cond: str, offset: int) -> None:
        pri = offset
        for lo, hi in bands:
            if hi is None:
                lines.append(f"RAX_SORT_CEIL({cond}, {lo}, {pri})")
            else:
                lines.append(f"RAX_SORT_BAND({cond}, {lo}, {hi}, {pri})")
            pri += 1

    lines.append("// value")
    emit_scale("RAX_SORT_VALUE", 0)
    lines.append("")
    lines.append("// stackable / noted ride above raw value")
    emit_scale("RAX_SORT_STACK", len(bands))
    lines.append("")
    lines.append("// untradeables ride above stackables")
    emit_scale("RAX_SORT_UNTRADE", len(bands) * 2)
    lines.append("")
    pin = len(bands) * 3 + 10
    lines.append(f"apply (name:RAX_SORT_PIN) {{")
    lines.append(f"    menuSort = {pin};")
    lines.append("}")
    write(GEN / "90_final.rs2f", "\n".join(lines) + "\n")


def emit_facts(mods: dict[str, str]) -> None:
    body = strip_module_header(mods["constants"])
    body = raxify(body)
    header = (
        "/*@ define:module:facts\n"
        "hidden: true\n"
        "name: facts\n"
        "*/\n\n"
        "// Game facts. Areas, account types, item name lists.\n\n"
    )
    write(GEN / "99_facts.rs2f", header + body)


ORDER = [
    SRC / "00_header.rs2f",
    SRC / "01_tokens.rs2f",
    SRC / "10_display.rs2f",
    SRC / "20_loot_order.rs2f",
    SRC / "30_hide.rs2f",
    GEN / "30_hide_body.rs2f",
    SRC / "31_hide_ext.rs2f",
    SRC / "40_locations.rs2f",
    GEN / "40_locations_body.rs2f",
    GEN / "41_rooms.rs2f",
    *[GEN / f"5x_{kid}.rs2f" for kid, _, _ in KINDS],
    SRC / "60_value.rs2f",
    SRC / "65_clues.rs2f",
    SRC / "70_rares.rs2f",
    GEN / "71_rdt.rs2f",
    SRC / "80_alerts.rs2f",
    GEN / "90_final.rs2f",
    GEN / "99_facts.rs2f",
    SRC / "91_facts_ext.rs2f",
]


def concat() -> Path:
    missing = [p for p in ORDER if not p.exists()]
    if missing:
        die("missing pieces:\n  " + "\n  ".join(str(p) for p in missing))
    alchs_val = (GEN / "69_list_values.txt").read_text().strip()
    uniques_body = (GEN / "70_uniques_body.rs2f").read_text().rstrip()
    notable_val = (GEN / "70_notable.txt").read_text().strip()
    clues_body = (GEN / "65_clues_body.rs2f").read_text().rstrip()

    parts = []
    for p in ORDER:
        text = p.read_text()
        if p.name == "65_clues.rs2f":
            text = text.replace("/*{{RAX_CLUES_BODY}}*/", clues_body)
        if p.name == "70_rares.rs2f":
            text = text.replace("/*{{RAX_UNIQUES_BODY}}*/", uniques_body)
            text = text.replace("/*{{RAX_NOTABLE_LIST}}*/", notable_val)
            text = text.replace("/*{{RAX_ALCHS_LIST}}*/", alchs_val)
        parts.append(text.rstrip() + "\n\n")
    DIST.mkdir(parents=True, exist_ok=True)
    text = "".join(parts)
    text = stamp_group_icons(text, load_group_icons())
    out = DIST / "raxors-loot-filter.rs2f"
    out.write_text(text)
    (ROOT / "filter.rs2f").write_text(text)
    return out


def stamp_group_icons(text: str, icons: dict) -> str:
    """Force every define:group header to use src/group_icons.json."""

    def repl(match: re.Match) -> str:
        block = match.group(0)
        name_m = re.search(r"^name:\s*(.+)$", block, re.M)
        if not name_m:
            return block
        key = name_m.group(1).strip().strip('"')
        spec = icons.get(key)
        if not spec:
            return block
        desc = ""
        dm = re.search(r"^description:\s*\|?\s*\n((?:^[ \t].+\n)+)", block, re.M)
        if dm:
            desc = "description: |\n" + dm.group(1)
        header = emit_group_header(key, spec)
        if desc:
            header = header.replace("expanded: false\n*/", desc + "expanded: false\n*/")
        return header.rstrip() + "\n"

    return re.sub(r"/\*@ define:group\n---.*?^\*/", repl, text, flags=re.S | re.M)


def validate(path: Path) -> None:
    text = path.read_text()
    errors: list[str] = []
    if text.count("{") != text.count("}"):
        errors.append(f"brace mismatch {{ {text.count('{')} }} {text.count('}')}")
    if re.search(r"(?<![A-Za-z])VAR_", text):
        errors.append("leaked VAR_ prefix")
    if re.search(r"(?<![A-Za-z])CONST_", text):
        errors.append("leaked CONST_ prefix")
    if 'name = "Raxor\'s Loot Filter"' not in text:
        errors.append("missing meta name")
    if not text.lstrip().startswith("/*@ define:module:"):
        errors.append("filter MUST start with a define:module comment")
    for needle in (
        "define:module:display",
        "define:module:loot_order",
        "define:module:hide",
        "define:module:locations",
        "define:module:food",
        "define:module:runes",
        "define:module:ammo",
        "define:module:herbs",
        "define:module:armour",
        "define:module:clues",
        "define:module:value",
        "define:module:clues",
        "define:module:rares",
        "define:module:alerts",
    ):
        if needle not in text:
            errors.append(f"missing {needle}")
    banned = ("Typical-Whack", "typical-whack", "Nismo", "Cuzco", "Joe's filter")
    for b in banned:
        if b in text:
            errors.append(f"banned string {b!r}")
    joe_sprites = (1531, 3288, 3231, 4239, 4240, 4241, 4244, 4247, 4248, 4249, 4250, 4253, 4256, 4258, 4328, 4297, 4318)
    for sid in joe_sprites:
        if re.search(rf"spriteId:\s*{sid}\b", text):
            errors.append(f"Joe skill-tab sprite {sid} leaked — use SpriteID names")
    for needle in (
        "Seeking dragon arrow",
        "Elder venator fang",
        "Crimson kisten",
        "Hueycoatl hide",
        "Mokhaiotl cloth",
        "FACT_MAGGOT_KING_AREA",
        "RAX_CLOG_MAGGOT_KING",
        "RAX_CLOG_ALCHEMICAL_HYDRA",
        "Collection log",
        "RAX_CLUE_ELITE_STYLE",
        "Clue nest (elite)",
        "RAX_AMMO_SEEKING_STYLE",
        "RAX_HERBS_HIGH_STYLE",
        "RAX_HIDE_ARMOUR_LOW",
    ):
        if needle not in text:
            errors.append(f"missing {needle!r}")
    if errors:
        die("validation failed:\n  " + "\n  ".join(errors))


def main() -> None:
    if not JOE.exists():
        die(f"Joe seed not found: {JOE}")
    joe = JOE.read_text()
    mods = split_joe(joe)
    need = (
        "filtering",
        "area_based_filtering",
        "item_category_styles",
        "individual_item_styles",
        "alchs",
        "rare_drop_table",
        "constants",
    )
    for n in need:
        if n not in mods:
            die(f"Joe seed missing module {n}: {sorted(mods)}")

    GEN.mkdir(parents=True, exist_ok=True)
    icons = load_group_icons()
    emit_hide(mods, icons)
    emit_locations(mods, icons)
    emit_rooms()
    emit_categories(mods, icons)
    emit_lists(mods)
    emit_uniques()
    emit_clues()
    emit_final()
    emit_facts(mods)
    out = concat()
    validate(out)
    lines = out.read_text().count("\n") + 1
    print(f"wrote {out.relative_to(ROOT)} ({lines} lines)")


if __name__ == "__main__":
    main()
