"""
Rename the patched TTFs to a distinct family and emit WOFF2 web fonts.

Renames the family from "Baloo Tammudu 2" to a derivative name so the web
release does not collide with the official Baloo Tammudu 2 shipped by
EkType/Google Fonts. Updates all relevant name-table records, the version
string, the OS/2 typographic family, and the PostScript name. Preserves
the OFL copyright/license records and the Noto donor attribution added in
the earlier graft step.

Also compresses each renamed TTF into WOFF2 for web use.

Usage:
    python prepare_webfont.py --input-dir . --output-dir webfont/
"""
from __future__ import annotations
import argparse
import os
import sys
from datetime import date
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import compress

# Derivative family name. Kept close to the original so users understand
# the lineage, but distinct enough to avoid identity collision with the
# official Baloo Tammudu 2. This is the derivative name; the official
# Baloo Tammudu 2 fonts remain the authoritative source.
NEW_FAMILY = "Baloo Tammudu 2 Vedic"
NEW_PS_FAMILY = "BalooTammudu2Vedic"
NEW_VERSION_MAJOR = 1
NEW_VERSION_MINOR = 0
NEW_VERSION_NOTE = (
    "1.000; Vedic derivative prototype; grafts U+0951-U+0954 and "
    "U+1CD0-U+1CFF from Noto Sans Devanagari (OFL)"
)


# Name IDs the OFL requires to preserve verbatim
OFL_PRESERVED_IDS = {0, 7, 13, 14}


def set_name(name_table, name_id, value, platforms=None):
    """Set a name-table record across all matching platform/encoding/lang
    triples that already exist, so we don't leave stale ID copies behind."""
    if platforms is None:
        platforms = [
            (3, 1, 0x409),   # Windows / Unicode BMP / en-US
            (1, 0, 0),       # Mac / Roman / English (legacy)
        ]
    for platformID, platEncID, langID in platforms:
        name_table.setName(value, name_id, platformID, platEncID, langID)


def rename_font(font, weight_name):
    """Rewrite the name table to the derivative family/subfamily."""
    name = font['name']

    # Basic 4-name family. When the subfamily is one of the "RIBBI" four
    # (Regular / Italic / Bold / Bold Italic) OT recommends using IDs 1/2
    # for those and omitting 16/17. Since we have 5 weights, we use the
    # typographic family (16) + typographic subfamily (17) for the full
    # family so applications see all five, and put a RIBBI-friendly pair in
    # 1/2 that maps ExtraBold/Medium/SemiBold into "Regular" style.
    if weight_name == "Regular":
        set_name(name, 1, NEW_FAMILY)
        set_name(name, 2, "Regular")
    elif weight_name == "Bold":
        set_name(name, 1, NEW_FAMILY)
        set_name(name, 2, "Bold")
    else:
        # For Medium, SemiBold, ExtraBold: the "traditional" 4-family view
        # collapses them into a subfamily under a family suffixed with the
        # weight; the typographic pair (16/17) keeps them together.
        set_name(name, 1, f"{NEW_FAMILY} {weight_name}")
        set_name(name, 2, "Regular")

    # Typographic family/subfamily (used by modern apps to keep all 5
    # weights under one family).
    set_name(name, 16, NEW_FAMILY)
    set_name(name, 17, weight_name)

    # Full name (ID 4) and PostScript name (ID 6).
    set_name(name, 4, f"{NEW_FAMILY} {weight_name}")
    set_name(name, 6, f"{NEW_PS_FAMILY}-{weight_name}")

    # Unique identifier (ID 3). Convention: "vendor; PS-name; version".
    set_name(name, 3, f"revurpk; {NEW_PS_FAMILY}-{weight_name}; {NEW_VERSION_MAJOR}.{NEW_VERSION_MINOR:03d}")

    # Version string (ID 5).
    set_name(name, 5, f"Version {NEW_VERSION_NOTE}")

    # head.fontRevision matches the version.
    font['head'].fontRevision = NEW_VERSION_MAJOR + NEW_VERSION_MINOR / 1000

    # OS/2 achVendID: neutral 4-char tag for the derivative build. Vendor
    # tags are informal; "PRVR" identifies revurpk's derivative.
    font['OS/2'].achVendID = "PRVR"


def rename_and_save(input_path, output_ttf_path, weight_name):
    font = TTFont(input_path)
    rename_font(font, weight_name)
    os.makedirs(os.path.dirname(output_ttf_path) or '.', exist_ok=True)
    font.save(output_ttf_path)


def make_woff2(ttf_path, woff2_path):
    compress(ttf_path, woff2_path)


def process_weight(input_dir, output_dir, weight):
    src = os.path.join(input_dir, f"BalooTammudu2-{weight}.ttf")
    out_ttf = os.path.join(output_dir, f"{NEW_PS_FAMILY}-{weight}.ttf")
    out_woff2 = os.path.join(output_dir, f"{NEW_PS_FAMILY}-{weight}.woff2")
    rename_and_save(src, out_ttf, weight)
    make_woff2(out_ttf, out_woff2)
    return out_ttf, out_woff2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True,
                    help="Directory with BalooTammudu2-*.ttf (patched, anchored)")
    ap.add_argument("--output-dir", required=True,
                    help="Where to write renamed TTFs and WOFF2s")
    args = ap.parse_args()

    weights = ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold"]
    for w in weights:
        ttf, woff2 = process_weight(args.input_dir, args.output_dir, w)
        ttf_kb = os.path.getsize(ttf) // 1024
        woff2_kb = os.path.getsize(woff2) // 1024
        print(f"  {w:10s} TTF {ttf_kb:5d}KB  WOFF2 {woff2_kb:5d}KB")


if __name__ == "__main__":
    sys.exit(main() or 0)
