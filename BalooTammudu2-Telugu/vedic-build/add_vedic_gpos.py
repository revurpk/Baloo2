"""
Add GPOS MarkBasePos and MarkMarkPos anchors so Vedic marks attach
correctly to Telugu base glyphs and stack over above-base matras.

Three lookups are created and wired onto the Telugu scripts (tel2, telu):

- abvm (MarkBasePos): Vedic above-marks attach to Telugu consonants at
  the consonant's top-center + BASE_ANCHOR_Y_GAP.
- blwm (MarkBasePos): Vedic below-marks attach to Telugu consonants at
  the consonant's bottom-center - BASE_ANCHOR_Y_GAP.
- mkmk (MarkMarkPos): when an above-base matra (matraOo, matraEe, etc.)
  is already GDEF-marked (which they aren't by default) OR when a Vedic
  mark follows another Vedic mark, stack them cleanly.

Above-base matras are still excluded from abvm base coverage so the mark
sits over the consonant column, not the matra hook. mkmk fills in the
"stack one Vedic mark on another" case.
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
BASE_ANCHOR_Y_GAP_ABOVE = 220  # abvm base anchor this far above consonant top;
                               # chosen so the mark clears matraOo (Y up to 947)
                               # which is ~116 taller than a typical consonant
BASE_ANCHOR_Y_GAP_BELOW = 150  # blwm base anchor this far below consonant bottom
MARK_ANCHOR_OFFSET = 0         # mark anchor at the mark's bbox bottom (above)
                               # or top (below)

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


def build_mark_mark_pos(font, base_mark_anchors, mark_anchors):
    """Build a MarkMarkPos (lookup type 6) subtable.

    In mkmk, one mark (the 'base mark') carries an anchor that a following
    mark attaches to. Structurally identical to MarkBasePos but the base
    coverage is over mark glyphs.
    """
    sub = ot.MarkMarkPos()
    sub.Format = 1
    sub.ClassCount = 1

    order = font.getGlyphOrder()
    glyph_index = {g: i for i, g in enumerate(order)}
    mark1_glyphs = sorted(mark_anchors.keys(), key=lambda g: glyph_index[g])
    mark2_glyphs = sorted(base_mark_anchors.keys(), key=lambda g: glyph_index[g])

    sub.Mark1Coverage = make_coverage(mark1_glyphs, font)
    sub.Mark2Coverage = make_coverage(mark2_glyphs, font)

    mark1_array = ot.Mark1Array()
    mark1_records = []
    for gn in mark1_glyphs:
        x, y = mark_anchors[gn]
        rec = ot.MarkRecord()
        rec.Class = 0
        rec.MarkAnchor = make_anchor(x, y)
        mark1_records.append(rec)
    mark1_array.MarkRecord = mark1_records
    mark1_array.MarkCount = len(mark1_records)
    sub.Mark1Array = mark1_array

    mark2_array = ot.Mark2Array()
    mark2_records = []
    for gn in mark2_glyphs:
        x, y = base_mark_anchors[gn]
        rec = ot.Mark2Record()
        rec.Mark2Anchor = [make_anchor(x, y)]
        mark2_records.append(rec)
    mark2_array.Mark2Record = mark2_records
    mark2_array.Mark2Count = len(mark2_records)
    sub.Mark2Array = mark2_array

    return sub


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


def add_lookup(gpos_table, subtable, lookup_type):
    """Append a new lookup. Returns the lookup index."""
    lk = ot.Lookup()
    lk.LookupType = lookup_type
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


def collect_vedic_marks_by_zone(font):
    """Return (above_marks, below_marks) — Vedic mark glyphs partitioned by
    where their outline sits relative to the baseline."""
    cmap = font.getBestCmap()
    gdef = font['GDEF'].table.GlyphClassDef.classDefs
    above, below = [], []
    for cp in VEDIC_CODEPOINTS:
        name = cmap.get(cp)
        if not name or gdef.get(name) != 3:
            continue
        b = get_bbox(font, name)
        if b is None:
            continue
        if b[3] > ABOVE_THRESHOLD_Y:
            above.append(name)
        else:
            below.append(name)
    return above, below


def add_anchors(input_path, output_path):
    font = TTFont(input_path)

    bases = collect_telugu_bases(font)
    above_marks, below_marks = collect_vedic_marks_by_zone(font)

    # abvm: base anchor at (xmid, ymax + gap_above), mark anchor at (xmid, ymin)
    abvm_base_anchors = {}
    for gn in bases:
        b = get_bbox(font, gn)
        if b is None:
            continue
        xmin, xmax, _, ymax = b
        abvm_base_anchors[gn] = ((xmin + xmax) / 2, ymax + BASE_ANCHOR_Y_GAP_ABOVE)

    abvm_mark_anchors = {}
    for gn in above_marks:
        b = get_bbox(font, gn)
        if b is None:
            continue
        xmin, xmax, ymin, _ = b
        abvm_mark_anchors[gn] = ((xmin + xmax) / 2, ymin + MARK_ANCHOR_OFFSET)

    # blwm: base anchor at (xmid, ymin - gap_below), mark anchor at (xmid, ymax)
    blwm_base_anchors = {}
    for gn in bases:
        b = get_bbox(font, gn)
        if b is None:
            continue
        xmin, xmax, ymin, _ = b
        blwm_base_anchors[gn] = ((xmin + xmax) / 2, ymin - BASE_ANCHOR_Y_GAP_BELOW)

    blwm_mark_anchors = {}
    for gn in below_marks:
        b = get_bbox(font, gn)
        if b is None:
            continue
        xmin, xmax, _, ymax = b
        blwm_mark_anchors[gn] = ((xmin + xmax) / 2, ymax - MARK_ANCHOR_OFFSET)

    gpos = font['GPOS'].table

    abvm_idx = None
    if abvm_base_anchors and abvm_mark_anchors:
        sub = build_mark_base_pos(font, abvm_base_anchors, abvm_mark_anchors)
        abvm_idx = add_lookup(gpos, sub, 4)
        add_feature_to_scripts(gpos, 'abvm', abvm_idx, {'tel2', 'telu'})

    blwm_idx = None
    if blwm_base_anchors and blwm_mark_anchors:
        sub = build_mark_base_pos(font, blwm_base_anchors, blwm_mark_anchors)
        blwm_idx = add_lookup(gpos, sub, 4)
        add_feature_to_scripts(gpos, 'blwm', blwm_idx, {'tel2', 'telu'})

    # mkmk: stack a following above-mark on top of a preceding above-mark.
    # Anchor on the "base mark" at its (xmid, ymax + small gap); anchor on
    # the incoming mark at its (xmid, ymin). Only above-marks participate;
    # below-mark stacking is rare enough to skip in a prototype.
    mkmk_idx = None
    if len(above_marks) >= 2:
        base_mark_anchors = {}
        mkmk_mark_anchors = {}
        for gn in above_marks:
            b = get_bbox(font, gn)
            if b is None:
                continue
            xmin, xmax, ymin, ymax = b
            base_mark_anchors[gn] = ((xmin + xmax) / 2, ymax + 30)
            mkmk_mark_anchors[gn] = ((xmin + xmax) / 2, ymin)
        sub = build_mark_mark_pos(font, base_mark_anchors, mkmk_mark_anchors)
        mkmk_idx = add_lookup(gpos, sub, 6)
        add_feature_to_scripts(gpos, 'mkmk', mkmk_idx, {'tel2', 'telu'})

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    font.save(output_path)

    return {
        'bases': len(bases),
        'above_marks': len(above_marks),
        'below_marks': len(below_marks),
        'abvm_lookup': abvm_idx,
        'blwm_lookup': blwm_idx,
        'mkmk_lookup': mkmk_idx,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    r = add_anchors(args.input, args.output)
    print(f"Wrote {args.output}")
    print(f"  Telugu base glyphs: {r['bases']}")
    print(f"  abvm lookup #{r['abvm_lookup']}: {r['above_marks']} above-marks")
    print(f"  blwm lookup #{r['blwm_lookup']}: {r['below_marks']} below-marks")
    if r['mkmk_lookup'] is not None:
        print(f"  mkmk lookup #{r['mkmk_lookup']}: above-mark stacking")


if __name__ == "__main__":
    sys.exit(main() or 0)
