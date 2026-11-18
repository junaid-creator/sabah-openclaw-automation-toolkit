# Troubleshooting

- ModuleNotFoundError: activate the venv, install requirements and run from the checkout root.
- Invalid language: use ENGLISH, ARABIC or BILINGUAL; no automatic bilingual default.
- Network disabled: use --fixture for safe tests. Only use --allow-network for a trusted public site you intend to query.
- Snapshot has 100 entries: the original refresher fetches only the first page. Do not claim full-site coverage; pagination remains unimplemented.
- Lock held: another operation is active; inspect it rather than deleting locks or forcing retries.
- Review latch: reconcile the remote outcome explicitly. Never clear it just to retry.
- Metadata mismatch: regex-based editing supports limited markup forms; inspect source/diff rather than assuming success.
- Skill installed but commands unavailable: the separate toolkit checkout/venv must remain accessible.

Provider continuation failures, Gateway failures and browser relay pairing are upstream operational issues; this project does not alter production runtime configuration to repair them.
