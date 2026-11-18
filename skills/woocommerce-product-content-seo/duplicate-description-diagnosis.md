# Duplicate product meta description diagnosis

Read when site-level metadata repair is authorized after a product-copy audit finds more than one rendered description tag. A product-copy request alone does not authorize changing theme output.

1. Compare each public tag's value and placement with the saved Rank Math value and product excerpt. Inspect the active theme's `wp_head` callbacks and its supported settings; do not assume all duplicates have one source. On the inspected Hello Elementor theme, `hello_elementor_add_description_meta_tag` echoes `post_excerpt` on singular pages after Rank Math. Its own `hello_elementor_settings_description_meta_tag` option set to string `true` removes that callback. Confirm the current theme still implements this setting before using it; do not edit Rank Math values, product excerpts or theme source to hide the symptom.
2. Back up the exact prior setting, including whether it was unset, and the affected public tags. Use only the theme switch if that is the proven emitter. Verify option readback and fresh public pages for exactly one description whose value equals the intended SEO metadata. Recheck SEO title, canonical and product content, and preserve the original setting for rollback. A failed cache-purge command is not itself proof that fresh public pages retained stale output; check actual responses.

Completion: identified source, bounded setting change or explicit blocker, and affected-page counts with tag values before and after.
