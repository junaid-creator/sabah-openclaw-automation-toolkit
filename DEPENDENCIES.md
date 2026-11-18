# Dependencies and licensing

## Required for the published Python subset

- Linux/POSIX, Python >=3.11; recorded test interpreter 3.14.4. Other versions are not acceptance-tested here.
- Exact pins in [requirements.txt](requirements.txt): requests and its TLS/encoding/HTTP dependencies, Pillow for decoded image validation.
- Standard library SQLite and file locking; one host/local filesystem. No multi-server locking guarantee.
- Git for source/release checks; optional Gitleaks and pip-audit for release security checks.

No new third-party dependency is added by setup_scaffold or trusted_bridge. Their code is original toolkit integration work, not copied native OpenClaw code. Retained source hashes and license exclusions remain in [provenance](PROVENANCE.json) and [canonical register](docs/canonical-capabilities.json). Dependency licenses remain their own; the toolkit license does not relicense them.

## Optional external dependencies

| Capability | External dependency | Makes reproduction complete by itself? |
|---|---|---|
| Agents, models, native tools | Official OpenClaw + authorized model provider | No; configure isolation/routing and run fresh-agent acceptance |
| Google | Official GOG + OAuth credentials / Sheets API permissions | Lead sync supported; original multi-tab SEO tracker still missing |
| WordPress | Site REST API, application password, SEO-field plugin | Generic adapter supported; site-specific SEO/visual acceptance remains |
| Meta | Authorized Graph API app, account scopes, owned media host | Adapter mocked; integrated worker and live verification remain |
| TikTok | Authorized Business API app, scopes, external OAuth refresh | No shipped OAuth service; live app acceptance needed |
| Overture | Official downloader, data/license compliance | Acquisition/qualification supported; enrichment/orchestration incomplete |
| Apify | Actor, token, billing evidence, allowed cap | History bounded to 2,000 runs; evidence monitor still unported |
| Six posters | Source-derived renderer/CSS, operator fonts/assets, optional Playwright 1.64 | 18 local synthetic language/layout renders pass; genuine QR/semantic/provider integration incomplete |
| Telegram/WhatsApp transport | Native configured channels plus optional product-owner-bridge | Product hook source and fixtures supplied; live activation and other workflow routes NOT TESTED |
| Gateway monitor | Explicit HTTP health probe, independent optional Telegram transport, inert systemd templates | Source/mock-tested monitor provided; service/live alert acceptance NOT TESTED |

Upstream references (128 canonical groups) are not redistributable copies in this toolkit. Obtain them from maintained official distributions and verify their current licenses. gog-clean and wordpress-rest-api-clean derivative provenance remains unresolved: six source records are excluded. No production logo, QR, photography, credentials, session or customer data is included.

## Additional runtime and licensing requirements

Node 24 is required for built-in SQLite support guards; no npm package dependencies
are added. The product bridge requires the official OpenClaw plugin SDK at runtime.
Optional raster rendering uses requirements-render.txt: Playwright 1.64.0
(Apache-2.0), pyee 14.0.0 (MIT; **Python >=3.12**), greenlet 3.5.6 (MIT/PSF-2.0).
The core Python floor remains separate. Actual tested interpreter: Python 3.14.
Chromium and fonts are operator-installed upstream software, not bundled assets.
Local speech uses operator-installed FFmpeg/sherpa-onnx/Piper and separately
reviewed model/voice licenses; no binary/model is redistributed. See local-voice.md
under docs. SVG demo assets are new original toolkit work; the QR is a placeholder.
