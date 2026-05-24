"""
Graft Vedic Extensions (U+1CD0-U+1CFF) outlines from Noto Sans Devanagari
into Baloo Tammudu 2 Telugu.

The donor outlines are copied as-is into the recipient's glyf table; above-marks
are translated down ~300 units so they sit above Telugu base characters
rather than above a Devanagari headstroke (which Telugu lacks). All marks are
classified in GDEF and given zero advance width.

Notes & limitations:
- No GPOS anchor work is done. Marks position by their natural Y-offset, which
  is approximate. Refining requires per-base anchor tables.
- Telugu has no native Vedic mark-to-base rules; renderers stack via OT shaping.
- Donor names retained internally as uni1CXX per Baloo's naming convention.
"""
from __future__ import annotations
import argparse
import os
import sys
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.misc.transform import Offset


class _GlyfGlyphSet:
    """Minimal glyph-set adapter so DecomposingRecordingPen can resolve
    component refs against a raw glyf table."""
    def __init__(self, glyf):
        self._glyf = glyf
    def __contains__(self, name):
        return name in self._glyf.glyphs
    def __getitem__(self, name):
        glyph = self._glyf[name]
        return _DrawableGlyph(glyph, self._glyf)


class _DrawableGlyph:
    def __init__(self, glyph, glyf):
        self._glyph = glyph
        self._glyf = glyf
    def draw(self, pen):
        self._glyph.draw(pen, self._glyf)
    def drawPoints(self, pen):
        self._glyph.drawPoints(pen, self._glyf)


def flatten_composite(donor_glyph: Glyph, d_glyf) -> Glyph:
    """Return a simple (non-composite) glyph by inlining all component refs."""
    gs = _GlyfGlyphSet(d_glyf)
    rec = DecomposingRecordingPen(gs)
    donor_glyph.draw(rec, d_glyf)
    out_pen = TTGlyphPen(None)
    rec.replay(out_pen)
    return out_pen.glyph()

# Codepoints to graft: the Vedic Extensions block plus the four Devanagari-block
# Vedic accent marks (U+0951–U+0954), which are routinely used to mark Vedic
# prosody in Indic scripts including Telugu.
VEDIC_CODEPOINTS = list(range(0x0951, 0x0955)) + list(range(0x1CD0, 0x1D00))
ABOVE_MARK_THRESHOLD = 500      # Y bbox max above this = above-mark
# Align each above-mark's bbox bottom to this Y. Baloo's Candrabindu_above
# sits at Y[635,865]; Halant at Y[527,919]. Bottom ≈ 600 lands new marks in
# the same band regardless of their individual height.
TARGET_ABOVE_BOTTOM_Y = 600
# Baloo Tammudu 2 positions zero-advance marks via negative-X-baked geometry.
# Candrabindu_above center_x ≈ -375; Halant center_x ≈ -262. We center each
# imported mark at the midpoint of these so it lands roughly over a typical
# Telugu base (advance ~600).
TARGET_MARK_CENTER_X = -300


def bbox(glyph: Glyph, glyf_table):
    """Return (xmin, xmax, ymin, ymax) of a simple glyph, or None if empty."""
    if glyph.numberOfContours <= 0:
        return None
    coords, _, _ = glyph.getCoordinates(glyf_table)
    if not coords:
        return None
    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    return min(xs), max(xs), min(ys), max(ys)


def is_above_mark(glyph: Glyph, glyf_table) -> bool:
    b = bbox(glyph, glyf_table)
    return b is not None and b[3] > ABOVE_MARK_THRESHOLD


def translate_glyph(glyph: Glyph, glyf_table, dx: int, dy: int) -> Glyph:
    """Re-emit a (simple, non-composite) glyph with coordinates shifted."""
    if glyph.numberOfContours <= 0:
        return glyph
    # Use a TTGlyphPen with a TransformPen wrapper for the shift
    pen = TTGlyphPen(None)
    transform_pen = TransformPen(pen, Offset(dx, dy))
    # Draw via fontTools' ttProgram-friendly path
    glyph.draw(transform_pen, glyf_table)
    new_glyph = pen.glyph()
    return new_glyph


def graft(recipient_path: str, donor_path: str, output_path: str) -> dict:
    recipient = TTFont(recipient_path)
    donor = TTFont(donor_path)

    r_glyf = recipient['glyf']
    d_glyf = donor['glyf']
    r_hmtx = recipient['hmtx']
    d_hmtx = donor['hmtx']
    d_cmap = donor.getBestCmap()

    # Find a 4-3 (Windows Unicode BMP) cmap subtable to extend in recipient
    target_cmap_subtables = []
    for sub in recipient['cmap'].tables:
        if (sub.platformID, sub.platEncID) in [(3, 1), (3, 10), (0, 3), (0, 4)]:
            target_cmap_subtables.append(sub)
    if not target_cmap_subtables:
        raise RuntimeError("Recipient has no Unicode cmap subtable to extend")

    # Ensure GDEF.GlyphClassDef exists; we'll add new glyphs as mark (class 3)
    gdef = recipient.get('GDEF')
    if gdef is None or gdef.table.GlyphClassDef is None:
        raise RuntimeError("Recipient missing GDEF GlyphClassDef")
    gcd = gdef.table.GlyphClassDef

    grafted = []
    skipped = []
    existing = set(recipient.getGlyphOrder())

    for cp in VEDIC_CODEPOINTS:
        if cp not in d_cmap:
            continue
        new_name = f"uni{cp:04X}"
        if new_name in existing:
            skipped.append((cp, "already in recipient"))
            continue
        existing.add(new_name)

        donor_name = d_cmap[cp]
        donor_glyph = d_glyf[donor_name]

        # Flatten composite glyphs so we don't carry over component refs
        # to donor-only glyph names that won't exist in the recipient.
        if donor_glyph.isComposite():
            donor_glyph = flatten_composite(donor_glyph, d_glyf)

        # Compute Y-shift adaptively: above-marks land with bbox-bottom at the
        # target Y. Short above-marks shift less, tall above-marks shift more.
        # Below-marks and other geometries are left where they are.
        b = bbox(donor_glyph, d_glyf)
        if b is not None and b[3] > ABOVE_MARK_THRESHOLD:
            dy = int(round(TARGET_ABOVE_BOTTOM_Y - b[2]))
        else:
            dy = 0

        # Compute X-shift so the mark's geometric center lands at TARGET_MARK_CENTER_X.
        # This emulates Baloo's existing negative-X-baked mark convention so
        # zero-advance marks visually land over a typical Telugu base.
        if b is not None:
            xmin, xmax, _, _ = b
            current_center_x = (xmin + xmax) / 2
            dx = int(round(TARGET_MARK_CENTER_X - current_center_x))
        else:
            dx = 0

        if dx or dy:
            new_glyph = translate_glyph(donor_glyph, d_glyf, dx, dy)
        else:
            new_glyph = donor_glyph

        # Install the glyph
        r_glyf[new_name] = new_glyph

        # Force zero advance; lsb at original bbox left
        if new_glyph.numberOfContours > 0:
            coords, _, _ = new_glyph.getCoordinates(r_glyf)
            xs = [x for x, _ in coords] if coords else [0]
            lsb = min(xs) if xs else 0
        else:
            lsb = 0
        r_hmtx.metrics[new_name] = (0, lsb)

        # cmap mapping
        for sub in target_cmap_subtables:
            sub.cmap[cp] = new_name

        # GDEF: classify as mark
        gcd.classDefs[new_name] = 3

        grafted.append((cp, donor_name, new_name, dx, dy))

    # r_glyf.__setitem__ appends to its internal glyphOrder; sync the font's
    # master glyph order list to match so cmap/GDEF/hmtx all resolve names.
    recipient.setGlyphOrder(list(r_glyf.glyphOrder))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    recipient.save(output_path)

    return {"grafted": grafted, "skipped": skipped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipient", required=True)
    ap.add_argument("--donor", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    result = graft(args.recipient, args.donor, args.output)
    print(f"Grafted {len(result['grafted'])} Vedic codepoints into {args.output}")
    above = sum(1 for *_, dy in result['grafted'] if dy)
    print(f"  Above-marks Y-aligned to bbox-bottom={TARGET_ABOVE_BOTTOM_Y}: {above}")
    print(f"  Marks centered to X={TARGET_MARK_CENTER_X}: {len(result['grafted'])}")
    if result['skipped']:
        print(f"  Skipped: {len(result['skipped'])}")
        for cp, reason in result['skipped']:
            print(f"    U+{cp:04X}: {reason}")


if __name__ == "__main__":
    sys.exit(main() or 0)
