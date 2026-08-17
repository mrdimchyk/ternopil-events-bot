from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_render_uses_free_web_service_for_webhook_runtime():
    render = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "type: web" in render
    assert "plan: free" in render
    assert "runtime: docker" in render
    assert "region: frankfurt" in render
    assert "dockerfilePath: ./Dockerfile" in render
    assert "name: ternopil-events-bot" in render
    assert "healthCheckPath: /" in render
    assert "key: TELEGRAM_BOT_TOKEN" in render
    assert "key: DATABASE_URL" in render
    assert "key: CITY_NAME" in render
    assert "value: Ternopil" in render
    assert "key: TIMEZONE" in render
    assert "value: Europe/Kyiv" in render

    assert "FROM python:3.12-slim" in dockerfile
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile


def test_render_does_not_define_secrets_as_plain_values():
    render = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "TELEGRAM_BOT_TOKEN\n        value:" not in render
    assert "DATABASE_URL\n        value:" not in render
