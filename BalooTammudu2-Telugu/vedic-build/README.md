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
BalooTammudu2-{Weight}.ttf  (+ abvm/blwm MarkBasePos + mkmk MarkMarkPos)
  │
  │  prepare_webfont.py
  ▼
webfont/BalooTammudu2Vedic-{Weight}.ttf   (renamed family)
webfont/BalooTammudu2Vedic-{Weight}.woff2 (compressed for web)
```

## Scripts in this directory

| File | Purpose |
|---|---|
| `graft_vedic.py` | Copies Vedic glyph outlines from a donor TTF into a recipient TTF. Flattens composites, weight-matches, adapts glyph geometry: above-marks have their bbox-bottom aligned to Y=600 (Baloo's existing mark band); all marks have their bbox-center shifted to X=-300 to land over a typical Telugu base. Adds cmap entries, GDEF mark classification, sets zero advance. |
| `add_vedic_gpos.py` | Adds three GPOS lookups: `abvm` (MarkBasePos, type 4) attaching above-marks to Telugu consonants at `(xmid, ymax + 220)`; `blwm` (MarkBasePos, type 4) attaching below-marks at `(xmid, ymin - 150)`; `mkmk` (MarkMarkPos, type 6) stacking above-marks on other above-marks. Above-base vowel signs and halant are excluded from `abvm` base coverage so marks sit over the consonant column rather than the matra hook. Wires new features onto the `tel2` and `telu` scripts. |
| `prepare_webfont.py` | Renames each patched TTF to the derivative family "Baloo Tammudu 2 Vedic" (name IDs 1/2/3/4/6/16/17, OS/2 vendor ID, `head.fontRevision`, version note) and compresses each renamed TTF to WOFF2 for web use. Outputs to `webfont/`. |

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

# 4. Rename to derivative family and emit WOFF2 for web distribution
python BalooTammudu2-Telugu/vedic-build/prepare_webfont.py `
  --input-dir  BalooTammudu2-Telugu/vedic-build `
  --output-dir BalooTammudu2-Telugu/vedic-build/webfont
```

Requires `fontTools` and `brotli` (`pip install fontTools brotli`).

## Web font distribution (`webfont/`)

`prepare_webfont.py` produces a Google-Fonts-style bundle in
[`webfont/`](webfont/):

- Five WOFF2 files (~160KB each) — one per weight (400/500/600/700/800).
- Five TTF fallbacks for `format('truetype')` clients.
- [`webfont/styles.css`](webfont/styles.css) — `@font-face` rules with
  `font-display: swap` and `unicode-range` filtered to Latin + Telugu +
  Vedic (U+0951–U+0954, U+0C00–U+0C7F, U+1CD0–U+1CFF).
- [`webfont/demo.html`](webfont/demo.html) — visual smoke test.
- [`webfont/README.md`](webfont/README.md) — hosting instructions.

The renamed family is **"Baloo Tammudu 2 Vedic"** — distinct enough not to
collide with the official Baloo Tammudu 2 shipped by EkType / Google
Fonts, while making the lineage clear. All OFL copyright and license
records (name IDs 0, 7, 13, 14) are preserved verbatim.

## Known limitations

These are inherent to a prototype that grafts outlines without involving
the FontLab `.vfb` sources or the original designers.

- **Style mismatch.** Noto's stroke contrast and weight don't match Baloo's
  heavy, spurless display character. Vedic marks will look thinner and
  out-of-family next to native Telugu glyphs in the same line.
- **Approximate vertical clearance.** The static Y-gap of 220 units above
  each consonant works for most clusters, but tall above-base matras like
  `matraIi` (Y up to 1051) come within ~80 units of the marks. Tweak
  `BASE_ANCHOR_Y_GAP_ABOVE` in `add_vedic_gpos.py` if more clearance is
  wanted.
- **Matra clusters use consonant anchoring.** Rather than attaching to the
  above-base matra (whose bbox center doesn't correlate with the consonant
  it wraps), marks anchor to the preceding consonant with an elevated
  Y-gap. This keeps marks horizontally over the consonant column but
  leaves them visually close to tall matras.
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
- [x] **Classify in GDEF** as combining marks (class 3) with zero advance
      width. *Prototype does this at the TTF level; needs to move to
      `BalooTammudu2-Telugu/GDEF` for permanence.*
- [x] **GPOS anchor coverage** for both above-marks (`abvm`) and below-
      marks (`blwm`), plus `mkmk` for stacking above-marks on above-marks.
      *Prototype adds these programmatically; anchors are heuristic and
      need designer review in FontLab.*
- [ ] **Contextual GPOS for above-base matra clusters.** The prototype
      excludes above-matras from base coverage; a proper fix uses lookup
      type 6 (contextual positioning) so the mark shifts up specifically
      when a matra is present in the cluster.
- [x] **Register `abvm`, `blwm`, `mkmk` features** on `tel2`/`telu`
      scripts pointing at the new lookups. *Prototype does this at the
      TTF level via runtime patching; should move to the source feature
      tables for permanence.*
- [ ] **Visual QA** across a Vedic test corpus (e.g. svaras over
      common Telugu consonants, conjuncts, and aksharas with above-base
      matras). The static gap values (`ABOVE=220`, `BELOW=150`) in the
      prototype are compromises and need designer review.
- [ ] **Remove this `vedic-build/` directory** once the proper sources
      ship — it's a temporary workspace, not a permanent build product.

Tracking issue: <https://github.com/EkType/Baloo2/issues> (filed as
"Add rendering support for Unicode Vedic Extensions (U+1CD0–U+1CFF)").

## Files ignored by `.gitignore`

`donor/` (~45MB Noto release tree), `intermediate/` (compiled TTX), the
ephemeral issue-draft files (`issue-body.md`, `issue-prefilled-url.txt`,
`make_issue_url.py`), and `*.ttf` / `*.woff2` (handled by the repo-wide
`.gitignore`). The 5 patched output TTFs and the `webfont/` binaries are
therefore not tracked — regenerate them with the pipeline above when
needed.

Tracked in `webfont/` alongside its regeneratable binaries: `styles.css`,
`demo.html`, and `webfont/README.md`.
