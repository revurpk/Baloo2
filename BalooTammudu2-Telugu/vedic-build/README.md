# Vedic Extensions support for Baloo Tammudu 2 (Telugu)

Prototype build that adds rendering support for the Unicode **Vedic
Extensions** block (U+1CD0–U+1CFF) plus the four **Devanagari-block Vedic
accents** (U+0951–U+0954) to all five weights of Baloo Tammudu 2.

This is a **non-authoritative prototype** built on top of the released TTX
artefacts in [`../../TTX/`](../../TTX/). The font's `.vfb` sources in
[`../Regular/VFB/`](../Regular/VFB/) etc. are untouched — for permanent
inclusion the outlines need to land there. A feature request tracking the
broader work has been opened against the upstream
[EkType/Baloo2](https://github.com/EkType/Baloo2/issues) repo.

## What this produces

Five patched TTFs (one per weight) with **45 codepoints** of Vedic mark
support:

| Block | Range | Count |
|---|---|---|
| Devanagari Vedic accents | U+0951–U+0954 | 4 |
| Vedic Extensions | U+1CD0–U+1CFF | 41 |

Each grafted codepoint is:

- Mapped in `cmap` (Windows BMP subtable).
- Classified as a combining mark (GDEF class 3) with zero advance width.
- Positioned over Telugu consonants via a new `abvm` GPOS lookup with
  mark-to-base anchors on 74 Telugu base glyphs.

The seven codepoints in U+1CD0–U+1CFF that aren't covered are either too
recent (U+1CF7 from Unicode 12, U+1CFA from Unicode 13) or unassigned
(U+1CFB–U+1CFF). The donor font doesn't have them either.

## Pipeline

```
TTX/BalooTammudu2-{Weight}.ttx
  │
  │  fontTools.ttx
  ▼
intermediate/BalooTammudu2-{Weight}.ttf
  │
  │  graft_vedic.py
  ▼  (donor: NotoSansDevanagari-{Weight}.ttf, OFL)
BalooTammudu2-{Weight}.ttf  (cmap + glyf + GDEF wired)
  │
  │  add_vedic_gpos.py
  ▼
BalooTammudu2-{Weight}.ttf  (+ abvm MarkBasePos lookup on tel2/telu)
```

## Scripts in this directory

| File | Purpose |
|---|---|
| `graft_vedic.py` | Copies Vedic glyph outlines from a donor TTF into a recipient TTF. Flattens composites, weight-matches, adapts glyph geometry: above-marks have their bbox-bottom aligned to Y=600 (Baloo's existing mark band); all marks have their bbox-center shifted to X=-300 to land over a typical Telugu base. Adds cmap entries, GDEF mark classification, sets zero advance. |
| `add_vedic_gpos.py` | Adds a `MarkBasePos` (GPOS lookup type 4) connecting Vedic above-marks to Telugu consonants. Base anchors at consonant `(xmid, ymax + 220)`, mark anchors at `(xmid, ymin)`. Above-base vowel signs (matras U+0C3E–U+0C56) and halant are excluded from the base coverage so the mark attaches to the consonant directly — the matra is allowed to overlap visually but the mark sits over the consonant column. Registers a new `abvm` feature on the `tel2` and `telu` scripts. |

## Donor font

[Noto Sans Devanagari v2.006](https://github.com/notofonts/devanagari) (SIL
Open Font License). Chosen because it has 41/48 of the assigned Vedic
Extensions codepoints and weight-matches Baloo Tammudu 2 (Regular through
ExtraBold). Outlines are imported as-is and then transformed; no other
changes to the donor are carried over.

The attribution is recorded in the top-level
[`OFL.txt`](../../OFL.txt) as required by OFL §4.

## How to rebuild

From the repo root:

```powershell
# 1. Compile Baloo TTX -> TTF (5 weights, ~12s total)
$weights = 'Regular','Medium','SemiBold','Bold','ExtraBold'
foreach ($w in $weights) {
  python -m fontTools.ttx -q `
    -o "BalooTammudu2-Telugu/vedic-build/intermediate/BalooTammudu2-$w.ttf" `
    "TTX/BalooTammudu2-$w.ttx"
}

# 2. Download donor zip (one-time)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$assets = (Invoke-WebRequest 'https://api.github.com/repos/notofonts/devanagari/releases/latest' `
  -UseBasicParsing -Headers @{'User-Agent'='curl'}).Content | ConvertFrom-Json
Invoke-WebRequest $assets.assets[0].browser_download_url `
  -OutFile 'BalooTammudu2-Telugu/vedic-build/donor/NotoSansDevanagari.zip'
Expand-Archive -Force `
  'BalooTammudu2-Telugu/vedic-build/donor/NotoSansDevanagari.zip' `
  'BalooTammudu2-Telugu/vedic-build/donor/'

# 3. Graft outlines + add GPOS anchors for each weight
foreach ($w in $weights) {
  python BalooTammudu2-Telugu/vedic-build/graft_vedic.py `
    --recipient "BalooTammudu2-Telugu/vedic-build/intermediate/BalooTammudu2-$w.ttf" `
    --donor     "BalooTammudu2-Telugu/vedic-build/donor/NotoSansDevanagari/full/ttf/NotoSansDevanagari-$w.ttf" `
    --output    "BalooTammudu2-Telugu/vedic-build/BalooTammudu2-$w.ttf"
  python BalooTammudu2-Telugu/vedic-build/add_vedic_gpos.py `
    --input  "BalooTammudu2-Telugu/vedic-build/BalooTammudu2-$w.ttf" `
    --output "BalooTammudu2-Telugu/vedic-build/BalooTammudu2-$w.ttf"
}
```

Requires `fontTools` (`pip install fontTools`).

## Known limitations

These are inherent to a prototype that grafts outlines without involving
the FontLab `.vfb` sources or the original designers.

- **Style mismatch.** Noto's stroke contrast and weight don't match Baloo's
  heavy, spurless display character. Vedic marks will look thinner and
  out-of-family next to native Telugu glyphs in the same line.
- **Approximate vertical clearance.** The static Y-gap of 220 units above
  each consonant works for most clusters, but tall above-base matras like
  `matraIi` (Y up to 1051) come within ~80 units of the marks. Tweak
  `BASE_ANCHOR_Y_GAP` in `add_vedic_gpos.py` if more clearance is wanted.
- **No anchors for below-marks.** Only the `abvm` (above-base) lookup was
  added. U+0952 anudatta and the few below-marks in Vedic Extensions still
  rely on the static negative-X-baked positioning from the graft step.
- **Coverage gaps.** Seven Vedic Extensions codepoints (U+1CF7, U+1CFA,
  U+1CFB–U+1CFF) aren't in the donor and remain unrendered.
- **Sources still untouched.** Patches live in this directory only. The
  `.vfb` files need updates from a designer for permanent inclusion.

## TODO — what a proper fix requires

This prototype is a working approximation, not the real fix. For
upstreamable Vedic support in Baloo Tammudu 2 the following needs to
happen in FontLab on the `.vfb` sources, then propagate through the
existing build chain (VFB → AFDKO → TTF/TTX):

- [ ] **Draw native Vedic glyphs** for U+0951–U+0954 and U+1CD0–U+1CFF
      in all five weights, matched to Baloo's heavy spurless display
      style (stroke contrast, weight, x-height). This is the blocker;
      everything else depends on it.
- [ ] **Cover the seven gaps** the donor doesn't have: U+1CF7 (Unicode
      12), U+1CFA (Unicode 13). U+1CFB–U+1CFF are unassigned in Unicode
      and should remain unmapped.
- [ ] **Add entries to** `BalooTammudu2-Telugu/GlyphOrderAndAliasDB`
      mapping each new glyph name (`uni0951` … `uni1CFA`) to its
      codepoint, following the existing naming convention.
- [ ] **Classify in** `BalooTammudu2-Telugu/GDEF` as combining marks
      (class 3) with zero advance width.
- [ ] **Real GPOS anchor design.** Replace the `add_vedic_gpos.py`
      heuristic (consonants at `ymax + 220`, marks at `ymin`) with
      anchors drawn intentionally in FontLab for each base and mark.
      Add anchors for **below-marks too** (U+0952 anudatta etc.) — the
      prototype only handles above-marks.
- [ ] **Handle the above-base matras properly.** The prototype excludes
      them from base coverage so the mark attaches to the consonant
      instead. The right solution is either (a) `mkmk` anchors so the
      Vedic mark attaches to the matra's top, or (b) contextual GPOS
      that raises the mark when a matra is present in the cluster.
- [ ] **Register `abvm` and `blwm` features** on `tel2`/`telu` script
      records pointing at the new lookups, following Baloo's existing
      feature-table structure rather than the runtime patch this
      prototype does.
- [ ] **Visual QA** across a Vedic test corpus (e.g. svaras over
      common Telugu consonants, conjuncts, and aksharas with above-base
      matras). The static `BASE_ANCHOR_Y_GAP = 220` prototype value is
      a compromise and needs designer review.
- [ ] **Remove this `vedic-build/` directory** once the proper sources
      ship — it's a temporary workspace, not a permanent build product.

Tracking issue: <https://github.com/EkType/Baloo2/issues> (filed as
"Add rendering support for Unicode Vedic Extensions (U+1CD0–U+1CFF)").

## Files ignored by `.gitignore`

`donor/` (~45MB Noto release tree), `intermediate/` (compiled TTX), the
ephemeral issue-draft files (`issue-body.md`, `issue-prefilled-url.txt`,
`make_issue_url.py`), and `*.ttf` (handled by the repo-wide
`.gitignore`). The 5 patched output TTFs are therefore not tracked —
regenerate them with the pipeline above when needed.
