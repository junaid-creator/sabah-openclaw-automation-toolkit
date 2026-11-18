# Local browser verification

Use Python >=3.12 and install requirements.txt plus requirements-render.txt. Provision upstream Chromium with `python -m playwright install chromium` on the isolated target, or select an existing executable using --chromium. No production browser profile, cookies or website state is reused.

`python -m toolkit.browser_verification --html /private/product.html --checks /private/checks.json --output /private/new-evidence`

Checks JSON: `[{"selector":".badge","text":"Save 20%","count":1}]`. HTML must be private owner-only, <=2 MB; output directory must not already exist. Desktop 1440x1000 and mobile 390x844 are both tested for exact normalized text, element counts and visibility. Screenshots are hashed. JavaScript is disabled, service workers blocked and all browser requests aborted. References in HTML never grant network access.

`python tests/browser_fixture_acceptance.py --output /private/new-fixture-evidence` reproduces two viewport-positive cases and two hidden-badge negatives. This is actual Chromium execution, not a mock. It does not prove live Woo cart/checkout, JavaScript hydration, payment methods, account permissions, screenshot semantic quality or production website administration. For those, separately authorize isolated website fixture deployment and reviewed scoped browser actions.

Rollback is removal of this isolated evidence directory after retaining required audit records; this tool changes no website. Do not use real customer HTML snapshots in the public repository.
