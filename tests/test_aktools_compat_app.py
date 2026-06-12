from __future__ import annotations

from fastapi.testclient import TestClient


def test_aktools_homepage_uses_compatible_template_response():
    from src.integrations.aktools_compat_app import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code != 500
    assert "TemplateResponse() missing" not in response.text


def test_aktools_version_route_still_available():
    from src.integrations.aktools_compat_app import app

    client = TestClient(app)
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert "ak_current_version" in body
    assert "at_current_version" in body
