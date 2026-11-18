# Upstream dependencies

Install upstream capabilities from their maintainers, not copies of live files:

- OpenClaw and bundled skills/plugins: https://github.com/openclaw/openclaw ; https://docs.openclaw.ai/cli/skills ; https://docs.openclaw.ai/tools/plugin
- Google Workspace CLI: https://github.com/steipete/gogcli ; use only reviewed OAuth scopes and your own account.
- Apify: https://docs.apify.com/ ; paid runs require independent billing approval; no Actors run here.
- WordPress REST: https://developer.wordpress.org/rest-api/ ; WooCommerce Store API: https://developer.woocommerce.com/docs/apis/store-api/
- Meta: https://developers.facebook.com/docs/ ; TikTok: https://developers.tiktok.com/doc/overview/
- Overture Maps: https://docs.overturemaps.org/ ; OSM licensing: https://www.openstreetmap.org/copyright
- requests: https://requests.readthedocs.io/ (Apache-2.0); dependencies retain upstream licenses.

Catalog presence/loaded status does not verify account scopes or operation. No third-party skill code is vendored. Inspect the installed OpenClaw CLI help before installing any optional capability; no bulk plugin install command is supplied.
