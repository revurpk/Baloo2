"""
Add GPOS MarkBasePos anchors so Vedic above-marks attach correctly
to Telugu base glyphs (consonants and above-base vowel signs).

Without this lookup, the grafted Vedic marks rely on static negative-X-baked
geometry, which only positions correctly over a single average-width base.
For complex clusters like నమో॑ (Na+Ma+matraOo+udatta), the mark lands at the
wrong place because its position is computed from the cursor after the last
glyph in the cluster, not from the cluster's visual top-center.

With GPOS MarkBasePos:
- Each Telugu base glyph (consonant or above-matra) gets a top-center anchor.
- Each Vedic above-mark gets a bottom-center "mark anchor".
- The shaper places the mark so its anchor coincides with the base's anchor.

A new 'abvm' feature is registered on Telugu scripts (tel2, telu) referencing
the new lookup.
"""
from __future__ import annotations
import argparse
import os
import sys
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot

VEDIC_CODEPOINTS = list(range(0x0951, 0x0955)) + list(range(0x1CD0, 0x1D00))
ABOVE_THRESHOLD_Y = 500  # mark glyphs with ymax > this are above-marks
# Anchor placement constants
BASE_ANCHOR_Y_GAP = 220      # base anchor this far above the consonant top;
                             # chosen so the mark clears matraOo (Y max 947)
                             # which is ~116 taller than a typical consonant (831)
MARK_ANCHOR_OFFSET = 0       # mark anchor sits at the mark's bbox bottom

# Codepoints of Telugu above-base vowel signs that we do NOT use as bases.
# We want the abvm mark to attach to the consonant directly (not to the matra
# bbox center, which is biased toward the matra's hook rather than the
# consonant body). Marks then sit horizontally over the consonant — what the
# user expects — and the elevated BASE_ANCHOR_Y_GAP keeps them clear of the
# matra geometry above the consonant.
EXCLUDED_BASE_CODEPOINTS = {
    0x0C3E,  # matraAa
    0x0C3F,  # matraI
    0x0C40,  # matraIi
    0x0C46,  # matraE
    0x0C47,  # matraEe
    0x0C48,  # matraAi
    0x0C4A,  # matraO
    0x0C4B,  # matraOo
    0x0C4C,  # matraAu
    0x0C55,  # Lengthmark
    0x0C56,  # matraAiLengthmark
    0x0C4D,  # Halant (virama; not a base for Vedic marks)
}


def get_bbox(font, glyph_name):
    """Return (xmin, xmax, ymin, ymax) or None for empty/composite glyphs."""
    glyf = font['glyf']
    g = glyf[glyph_name]
    if g.numberOfContours <= 0:
        return None
    coords, _, _ = g.getCoordinates(glyf)
    if not coords:
        return None
    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    return min(xs), max(xs), min(ys), max(ys)


def make_anchor(x, y):
    a = ot.Anchor()
    a.Format = 1
    a.XCoordinate = int(round(x))
    a.YCoordinate = int(round(y))
    return a


def make_coverage(glyph_names, font):
    """Build a Coverage table with glyphs sorted by glyphID (required by spec)."""
    order = font.getGlyphOrder()
    glyph_index = {g: i for i, g in enumerate(order)}
    cov = ot.Coverage()
    cov.glyphs = sorted(glyph_names, key=lambda g: glyph_index[g])
    return cov


def build_mark_base_pos(font, base_anchors, mark_anchors):
    """Build a single MarkBasePos subtable.

    base_anchors: {glyph_name: (x, y)}
    mark_anchors: {glyph_name: (x, y)}   -- all in class 0 (above)
    """
    sub = ot.MarkBasePos()
    sub.Format = 1
    sub.ClassCount = 1

    order = font.getGlyphOrder()
    glyph_index = {g: i for i, g in enumerate(order)}
    mark_glyphs = sorted(mark_anchors.keys(), key=lambda g: glyph_index[g])
    base_glyphs = sorted(base_anchors.keys(), key=lambda g: glyph_index[g])

    sub.MarkCoverage = make_coverage(mark_glyphs, font)
    sub.BaseCoverage = make_coverage(base_glyphs, font)

    mark_array = ot.MarkArray()
    mark_records = []
    for gn in mark_glyphs:
        x, y = mark_anchors[gn]
        rec = ot.MarkRecord()
        rec.Class = 0
        rec.MarkAnchor = make_anchor(x, y)
        mark_records.append(rec)
    mark_array.MarkRecord = mark_records
    mark_array.MarkCount = len(mark_records)
    sub.MarkArray = mark_array

    base_array = ot.BaseArray()
    base_records = []
    for gn in base_glyphs:
        x, y = base_anchors[gn]
        rec = ot.BaseRecord()
        rec.BaseAnchor = [make_anchor(x, y)]
        base_records.append(rec)
    base_array.BaseRecord = base_records
    base_array.BaseCount = len(base_records)
    sub.BaseArray = base_array

    return sub


def add_lookup(gpos_table, subtable):
    """Append a new MarkBasePos lookup. Returns the lookup index."""
    lk = ot.Lookup()
    lk.LookupType = 4  # MarkBasePos
    lk.LookupFlag = 0
    lk.SubTable = [subtable]
    lk.SubTableCount = 1

    gpos_table.LookupList.Lookup.append(lk)
    gpos_table.LookupList.LookupCount = len(gpos_table.LookupList.Lookup)
    return gpos_table.LookupList.LookupCount - 1


def add_feature_to_scripts(gpos_table, feature_tag, lookup_index, script_tags):
    """Create a new Feature pointing at the lookup, then reference its index
    from each named script's DefaultLangSys and LangSysRecords."""
    feat = ot.Feature()
    feat.LookupListIndex = [lookup_index]
    feat.LookupCount = 1
    feat.FeatureParams = None

    fr = ot.FeatureRecord()
    fr.FeatureTag = feature_tag
    fr.Feature = feat

    gpos_table.FeatureList.FeatureRecord.append(fr)
    gpos_table.FeatureList.FeatureCount = len(gpos_table.FeatureList.FeatureRecord)
    new_feature_index = gpos_table.FeatureList.FeatureCount - 1

    for sr in gpos_table.ScriptList.ScriptRecord:
        if sr.ScriptTag not in script_tags:
            continue
        if sr.Script.DefaultLangSys is not None:
            sr.Script.DefaultLangSys.FeatureIndex.append(new_feature_index)
            sr.Script.DefaultLangSys.FeatureCount = len(
                sr.Script.DefaultLangSys.FeatureIndex)
        for lsr in sr.Script.LangSysRecord:
            lsr.LangSys.FeatureIndex.append(new_feature_index)
            lsr.LangSys.FeatureCount = len(lsr.LangSys.FeatureIndex)

    return new_feature_index


def collect_telugu_bases(font):
    """Return base glyph names: consonants and matras that have non-trivial
    above-line extent. Skip below-mark glyphs and pure-spacing glyphs."""
    cmap = font.getBestCmap()
    gdef = font['GDEF'].table.GlyphClassDef.classDefs
    out = []
    for cp in range(0x0C00, 0x0C80):
        if cp in EXCLUDED_BASE_CODEPOINTS:
            continue
        name = cmap.get(cp)
        if not name or not name.endswith('.te'):
            continue
        if gdef.get(name) == 3:
            continue
        b = get_bbox(font, name)
        if b is None:
            continue
        if b[3] < 400:
            continue
        out.append(name)
    return out


def collect_vedic_above_marks(font):
    """Return Vedic mark glyph names whose bbox is in the above-mark region."""
    cmap = font.getBestCmap()
    out = []
    for cp in VEDIC_CODEPOINTS:
        name = cmap.get(cp)
        if not name:
            continue
        b = get_bbox(font, name)
        if b is None:
            continue
        if b[3] > ABOVE_THRESHOLD_Y:
            out.append(name)
    return out


def add_anchors(input_path, output_path):
    font = TTFont(input_path)

    bases = collect_telugu_bases(font)
    marks = collect_vedic_above_marks(font)

    # Build base anchors at (xmid, ymax + gap)
    base_anchors = {}
    for gn in bases:
        b = get_bbox(font, gn)
        if b is None:
            continue
        xmin, xmax, _, ymax = b
        base_anchors[gn] = ((xmin + xmax) / 2, ymax + BASE_ANCHOR_Y_GAP)

    # Build mark anchors at (xmid, ymin)
    mark_anchors = {}
    for gn in marks:
        b = get_bbox(font, gn)
        if b is None:
            continue
        xmin, xmax, ymin, _ = b
        mark_anchors[gn] = ((xmin + xmax) / 2, ymin + MARK_ANCHOR_OFFSET)

    if not base_anchors or not mark_anchors:
        raise RuntimeError(
            f"Need at least one base and one mark; got "
            f"{len(base_anchors)} bases, {len(mark_anchors)} marks")

    gpos = font['GPOS'].table
    sub = build_mark_base_pos(font, base_anchors, mark_anchors)
    lookup_index = add_lookup(gpos, sub)
    add_feature_to_scripts(gpos, 'abvm', lookup_index, {'tel2', 'telu'})

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    font.save(output_path)

    return len(base_anchors), len(mark_anchors), lookup_index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    n_bases, n_marks, lk_idx = add_anchors(args.input, args.output)
    print(f"Added abvm lookup #{lk_idx} to {args.output}")
    print(f"  Base glyphs with above-anchor: {n_bases}")
    print(f"  Mark glyphs with mark-anchor:  {n_marks}")


if __name__ == "__main__":
    sys.exit(main() or 0)
