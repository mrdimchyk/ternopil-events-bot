# Render webhook runtime

The Telegram bot is exposed as a Render web service so the service can use the free instance type. Telegram sends updates to the webhook endpoint configured automatically from `RENDER_EXTERNAL_URL`.

Scheduled event collection remains in GitHub Actions. The web service health endpoint is `/`.
