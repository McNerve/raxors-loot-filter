#!/usr/bin/env python3
"""Compile Raxor's Loot Filter.

Reads the Joe seed (game facts + your hide/chip lists), rewrites it into
Raxor's pipeline, and emits dist/raxors-loot-filter.rs2f.

Authored code lives in src/. This script never copies Typical-Whack module
names, VAR_ prefixes, or the 11-module warehouse.
"""

from __future__ import annotations

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


def emit_floor(mods: dict[str, str]) -> None:
    body = strip_module_header(mods["filtering"])
    body = raxify(body)
    body = rewrite_inputs(body, "floor")
    body = collapse_groups(body)
    write(GEN / "30_floor_body.rs2f", body)


def emit_where(mods: dict[str, str]) -> None:
    body = strip_module_header(mods["area_based_filtering"])
    body = raxify(body)
    body = rewrite_inputs(body, "where")
    body = collapse_groups(body)
    write(GEN / "40_where_body.rs2f", body)


def emit_aisle(mods: dict[str, str]) -> list[str]:
    cat = strip_module_header(mods["item_category_styles"])
    ind = strip_module_header(mods["individual_item_styles"])
    body = cat + "\n" + ind
    body = raxify(body)
    body = rewrite_inputs(body, "aisle")
    body = GROUP_STYLES.sub(r"group: \1", body)
    body = collapse_groups(body)

    literals: list[str] = []
    seen: set[str] = set()
    for name in re.findall(r'name:"([^"]+)"', body):
        if name not in seen:
            seen.add(name)
            literals.append(name)

    facts = sorted(set(re.findall(r"name:(FACT_[A-Z0-9_]+)", body)))
    quoted = ", ".join(f'"{n}"' for n in literals)
    fact_or = " || ".join(f"name:{f}" for f in facts)
    cond = "name:RAX_AISLE_NAMES"
    if fact_or:
        cond = f"({cond} || {fact_or})"

    banner = (
        "// generated aisle — chips + families. Heat overwrites value.\n"
        f"#define RAX_AISLE_NAMES [{quoted}]\n\n"
    )
    force = (
        "\napply (RAX_FORCE_AISLE_ICON && "
        + cond
        + ") {\n    RAX_AISLE_ICON_STYLE\n}\n"
    )
    write(GEN / "50_aisle_body.rs2f", banner + body + force)
    return literals


def emit_lists(mods: dict[str, str]) -> None:
    uni = mods["uniques"]
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

    uniques_body = raxify(grab_define(uni, "VAR_UNIQUES_LIST", "RAX_UNIQUES_LIST"))
    alchs_body = raxify(grab_define(alch, "VAR_ALCHS_ITEM_LIST", "RAX_ALCHS_LIST"))
    # bodies include the #define line; stash values for marker splice
    def value_of(define_line: str) -> str:
        return define_line.split(" ", 2)[2].strip()

    write(GEN / "69_lists.rs2f", uniques_body + "\n" + alchs_body + "\n")
    write(
        GEN / "69_list_values.txt",
        value_of(uniques_body) + "\n---\n" + value_of(alchs_body) + "\n",
    )

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
    SRC / "10_identity.rs2f",
    SRC / "20_pickup.rs2f",
    SRC / "30_floor.rs2f",
    GEN / "30_floor_body.rs2f",
    SRC / "40_where.rs2f",
    GEN / "40_where_body.rs2f",
    SRC / "50_aisle.rs2f",
    GEN / "50_aisle_body.rs2f",
    SRC / "60_heat.rs2f",
    SRC / "70_always.rs2f",
    GEN / "71_rdt.rs2f",
    SRC / "80_kits.rs2f",
    GEN / "90_final.rs2f",
    GEN / "99_facts.rs2f",
]


def concat() -> Path:
    missing = [p for p in ORDER if not p.exists()]
    if missing:
        die("missing pieces:\n  " + "\n  ".join(str(p) for p in missing))
    values = (GEN / "69_list_values.txt").read_text().split("\n---\n", 1)
    uniques_val = values[0].strip()
    alchs_val = values[1].strip()

    parts = []
    for p in ORDER:
        text = p.read_text()
        if p.name == "70_always.rs2f":
            text = text.replace("/*{{RAX_UNIQUES_LIST}}*/", uniques_val)
            text = text.replace("/*{{RAX_ALCHS_LIST}}*/", alchs_val)
        parts.append(f"// ---- {p.relative_to(ROOT)} ----\n")
        parts.append(text.rstrip() + "\n\n")
    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / "raxors-loot-filter.rs2f"
    out.write_text("".join(parts))
    return out


def validate(path: Path) -> None:
    text = path.read_text()
    errors: list[str] = []
    if text.count("{") != text.count("}"):
        errors.append(f"brace mismatch {{ {text.count('{')} }} {text.count('}')}")
    if "VAR_" in text:
        errors.append("leaked VAR_ prefix")
    if "CONST_" in text:
        errors.append("leaked CONST_ prefix")
    if 'name = "Raxor\'s Loot Filter"' not in text:
        errors.append("missing meta name")
    for needle in (
        "define:module:identity",
        "define:module:pickup",
        "define:module:floor",
        "define:module:where",
        "define:module:aisle",
        "define:module:heat",
        "define:module:always",
        "define:module:kits",
    ):
        if needle not in text:
            errors.append(f"missing {needle}")
    banned = ("Typical-Whack", "typical-whack", "Nismo", "Cuzco", "Joe's filter")
    for b in banned:
        if b in text:
            errors.append(f"banned string {b!r}")
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
        "uniques",
        "alchs",
        "rare_drop_table",
        "constants",
    )
    for n in need:
        if n not in mods:
            die(f"Joe seed missing module {n}: {sorted(mods)}")

    GEN.mkdir(parents=True, exist_ok=True)
    emit_floor(mods)
    emit_where(mods)
    emit_aisle(mods)
    emit_lists(mods)
    emit_final()
    emit_facts(mods)
    out = concat()
    validate(out)
    lines = out.read_text().count("\n") + 1
    print(f"wrote {out.relative_to(ROOT)} ({lines} lines)")


if __name__ == "__main__":
    main()
