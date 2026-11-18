# Template 5 source-parity correction

Final source comparison found that the public adaptation still selected only the foreground crop of the hero and used SVG slice, even though the separately deployed original had been corrected. This release changes only the isolated public port:

- poster_catalog: Template 5 now uses the full lower-half hero and proportional meet, like Template 3. No foreground-only crop.
- catalog.css: only Template 5 hero mask is disabled. Existing public position, dimensions, branding placeholders and copy are unchanged.

No production source file was edited or reverted. The current original renderer/CSS hashes still match the separately recorded deployment. This is not permission to activate or modify any production template.

The new regression test requires full hero viewBox 0 400 800 400 on the 800x800 synthetic atlas, xMidYMid meet and mask-image:none; Template 2 retains slice. Existing six-template/language tests remain. Actual 18 language renders and six draft/review/approval/dispatch fixture runs are revalidated separately; simulated receipts never prove live publication. No genuine-brand/QR/semantic acceptance is transferred from the private deployment.

Rollback, if needed in a separate target: revert only the public renderer/CSS correction to the preceding reviewed commit, preserve all media/review/publication ledgers and re-render/review new artifacts. Never replace an already approved artifact without fresh approval.
