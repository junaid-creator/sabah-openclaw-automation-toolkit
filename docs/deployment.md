# Deployment

No installer creates services, cron jobs, webhooks or agents. Start with the synthetic CLI examples in a low-privilege account and a private working directory. Only give an agent execution access to the commands and directories it actually needs. Keep customer-support and administrative account permissions separate.

Optional scheduling is deliberately not shipped as a live timer. Before scheduling, choose an explicit timezone, a command with a finite timeout, collision handling and a reviewed output destination. Test it manually offline first. Never translate a request for a draft into approval to publish. Cron declarations are examples of infrastructure design, not supported publication adapters in this release.
