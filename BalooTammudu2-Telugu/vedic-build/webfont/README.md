# Baloo Tammudu 2 Vedic — web font distribution

Web-ready derivative of Baloo Tammudu 2 that adds rendering for the
Unicode Vedic Extensions block (U+1CD0–U+1CFF) and the four Devanagari
Vedic accents (U+0951–U+0954).

## Contents

| File | Purpose |
|---|---|
| `BalooTammudu2Vedic-{Weight}.woff2` | Web font (preferred) — one per weight. ~160KB each. |
| `BalooTammudu2Vedic-{Weight}.ttf` | TrueType fallback for `format('truetype')` clients. |
| `styles.css` | `@font-face` rules for all five weights with `font-display: swap` and `unicode-range` filtered to Latin + Telugu + Vedic. |
| `demo.html` | Visual smoke test — renders sample Vedic Sanskrit strings across all weights. |

Weights: Regular (400), Medium (500), SemiBold (600), Bold (700), ExtraBold (800).

## Usage

Copy `styles.css` and the `*.woff2` files to your site (they must live in the
same directory unless you edit the `url()` paths in `styles.css`), then:

```html
<link rel="stylesheet" href="/fonts/baloo-tammudu-2-vedic/styles.css">
<style>
  body { font-family: 'Baloo Tammudu 2 Vedic', system-ui, sans-serif; }
</style>
```

Ship with an aggressive cache header — the filenames are stable per build:

```
Cache-Control: public, max-age=31536000, immutable
```

## License

Licensed under the SIL Open Font License, Version 1.1. See the top-level
[`OFL.txt`](../../../OFL.txt) for the full text and the required attribution
for the donor outlines (Noto Sans Devanagari, © 2022 The Noto Project
Authors).

## Not an official release

This is a **prototype** derivative built by grafting outlines from Noto
Sans Devanagari into the released Baloo Tammudu 2 TTX. The `.vfb` sources
in `../Regular/VFB/` etc. are unchanged. Anyone can rebuild it from the
pipeline documented in [`../README.md`](../README.md).

For a proper native implementation, follow the tracking issue at
<https://github.com/EkType/Baloo2/issues>.
