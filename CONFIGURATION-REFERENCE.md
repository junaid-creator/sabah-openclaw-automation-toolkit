# Configuration reference

No environment file is automatically sourced. All credential values are operator supplied outside Git. Native OpenClaw configuration is separate from these Python APIs; verify your installed schema before applying any example.

| Component | Configuration / activation | Default / required evidence |
|---|---|---|
| Local state | TOOLKIT_STATE_DIR; private absolute path | Do not put state in checkout; no customer data in fixtures |
| Runtime timezone | TOOLKIT_TIMEZONE; IANA name | UTC where unspecified; review every schedule |
| Notification account | TOOLKIT_WHATSAPP_ACCOUNT, TOOLKIT_TELEGRAM_ACCOUNT | Explicit matching authorized recipient mapping required |
| WordPress | WP(origin,user,application_password,allow_network,allow_write) | Both flags false; HTTPS origin and /wp-json routes only |
| Google Sheets | GogSheets(account,client,allow_reads,allow_writes) | Read/write opt-ins; reviewed digest, exact tab/schema and readback |
| Meta | See Meta adapter config in operations guide | Explicit live admission, account/media-host and approval checks |
| TikTok | client_id, client_secret, expected_open_id, approved_media_hosts, token_provider | External OAuth; live_enabled false; prepare makes reads when called |
| Apify | actor_slug, expected_actor_id, token_provider, state/evidence paths | allow_network false; explicit digest authorization and bounded billing evidence |
| Overture | absolute downloader executable, W/S/E/N bbox, fresh output | allow_download false; no implicit enrichment/outreach |
| Blog | run/date, account/recipient, root, asset_root, adapters | Required research, images, draft, validation, receipt integrations |
| Trusted bridge | private SQLite path, independent key bytes, exact routes, clock | No key default; >=32 bytes; signed direct events <=300 seconds old |
| Support delivery | operator policy callback and sender callback | enabled false; destination fixed by signed event; uncertain sends never repeat |
| Setup scaffold | --destination, optional --apply | Dry run; new directory only; activation always false |

Full call contracts and test names: [module guide](docs/modules.md), [platform adapters](docs/platform-adapters.md), [operations](docs/operations-modules.md), [bridge](docs/trusted-bridge.md).

The scaffold's activation-plan.json is a toolkit manifest, **not** an OpenClaw config schema. The routing example uses agents.entries and a test allowlist. Configure the default agent through the installed UI/CLI; current documented default designation is agents.defaults.systemAgent.agentId. Inspect and merge, never replace live configuration. Select models using the installed provider onboarding flow or documented agents add --model option. Never use customer content to choose account, sender, tool, signing key or destination.

## Expanded configuration examples

- examples/product-sites.json: independent sites/accounts, owner tuples, verified
  site user, credential ENV references, metadata allowlist and exclusive-writer
  prerequisite. Keep state outside Git. No live account identifiers are supplied.
- plugins/product-owner-bridge/config.example.json: fixed Python/checkout paths,
  trusted native routes/aliases, private engine/config/receipt roots, independent
  signing-key reference and child environment allowlist. Network/writes disabled.
- examples/local-voice.json: explicit executable/model paths, reviewed licenses
  and profile/script mapping. No download or automatic account activation.
- examples/gateway-monitor.json: exact health endpoints, reviewed integrity
  hashes, maintenance/state paths and verified owner alert destination. No restart.
- examples/recovery-allowlist.json: runtime-private explicit source-kind mapping,
  not a list of production paths. Snapshot outputs may contain secrets: never Git.

Use separate credentials/state/keys for independent trust domains. Never reuse
someone else's owner IDs, phone numbers, ledgers, OAuth state or standing approval.
All templates are inert until independently configured and authorized.
