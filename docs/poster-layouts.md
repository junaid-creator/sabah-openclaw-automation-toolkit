# Six original poster layout structures

The port retains the original Template 1 reference geometry, Templates 2–5 catalog
geometry and Template 6 one-hero dual-brand layout/CSS. It is not six newly invented
rectangles. Brand/contact/image/font inputs are replaceable. Production sources and
the locked original template were not modified.

## Install locally

Core build/config tests use the normal requirements. Actual raster rendering adds
requirements-render.txt and **Python >=3.12** because pyee 14 requires it:

    python -m pip install -r requirements.txt -r requirements-render.txt
    python -m playwright install chromium

The browser install downloads upstream software; review its requirements on your
new isolated host. No fonts or models are downloaded by this toolkit. You may use
an explicitly selected already-installed Chromium with --chromium instead.

Configure examples/poster-content.json with your private local atlas and licensed
fonts, original/authorized branding, accurate contact text and genuine QR asset.
Create a private non-group/world-writable output root. Then:

    python -m toolkit.poster_render --config /private/poster.json --output-root /private/renders --request-id campaign-001

The renderer rejects unsupported template/language, missing paired copy, wrong
service count and unsafe/missing local assets. Defaults to ENGLISH. Template IDs
1–6 are exact; there is no silent substitution. Campaign copy is escaped.

Template 1 and catalog bases preserve the top-four-panels/bottom-hero atlas
convention. Template 4 contains the complete bottom panorama; Template 6 extracts
one bottom hero and separates the two brand/contact columns. The current six-style
controller deliberately excludes legacy style aliases and recruitment variants.
It does not generate photos or copy, rotate campaign schedules or create Sheet jobs.

## Rendering and retry contract

A hash includes exact content/brand, image/font bytes, CSS and renderer code.
The same request and inputs validate existing output hashes and reuse it. Changed
inputs need a new revision identity; stale/missing output proof blocks. Rendering
uses data-embedded local assets and rejects external requests. PNG and JPEG are
1080x1350. Text-fit shrinks only to the original declared minima; boxes/layout are
not expanded to hide overflow. A failed geometry check retains private diagnostics
and is not a production-ready result.

The real local browser acceptance covers six templates and three explicit language
modes with synthetic atlas/assets, plus retry/drift checks where reported in
poster-render-acceptance.json. Earlier failures are retained in the acceptance
record: unsafe staging permissions were corrected, and Template 6's first
adaptation omitted its original bilingual wrapper classes; those exact original
classes were restored without changing layout CSS. No failure is counted as a pass.

This is layout/crop/decoded-dimension acceptance, NOT semantic product-image review,
real QR decoding, provider generation, brand authorization or social publication.
An exported QR placeholder cannot pass a real QR gate. Long/novel copy and other
fonts require their own actual render and review. Template 1–6 English contact-sheet
inspection confirmed distinct source-derived structures, not actual campaign truth.

## Public source map

- toolkit/poster_reference.py: original Template 1 base/header/footer/atlas logic.
- toolkit/poster_catalog.py: original four catalog arrangements.
- toolkit/poster_cobrand.py: original dual-brand one-hero structure.
- toolkit/poster_render.py: portable validation, local browser/render receipt.
- poster_templates/: original adapted CSS and clearly labeled replaceable SVGs.

See [asset licenses](../poster_templates/ASSET-LICENSES.md). Rendering is not an
exact recreation of the live branded production environment; the full social
draft/approval/independent review/Sheet/transport workflow remains PARTIALLY PORTED.
