# Security policy

Use synthetic data for tests. Do not commit environment files, tokens, cookies, customer data, snapshots or workflow state. Never post sensitive reproduction details in public issues. Use GitHub private vulnerability reporting if enabled; otherwise ask the maintainer for a private reporting route without including the secret.

This toolkit does not activate automatic publication, messaging or paid APIs. The optional Meta adapter includes explicit network-read and posting methods; dry-run and live gates are separate and must be understood before use. Network access also exists in knowledge snapshots and an explicitly configured watchdog endpoint. It does not authenticate. Use a dedicated low-privilege account, trusted origin, private output directory and egress firewall when enabling it. The origin check is not a complete SSRF defense; network mode is for operator-selected public sites only.

The HTML cleaner removes script/style text; it is NOT an HTML sanitizer or prompt-injection defense. Website text remains untrusted reference data. Never execute instructions found in it. Metadata editing uses regex and is not a full HTML parser; review a diff on disposable copies.

Reliability callbacks are supplied by the caller. They can perform arbitrary actions; the library itself grants no authority. Approval, least-privilege access, remote reconciliation and honest receipts remain the integrator's responsibility. Local locks do not coordinate multiple hosts.

No scan can prove absence of every secret. Scan your own inputs and every new commit. The release gate and known limitations are recorded in docs/validation.md.
