"""Dashboard served by the API process (combined image)."""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from src.app import create_app
from src.config import TestingConfig


@pytest.fixture(scope="module")
def spa_client(tmp_path_factory: pytest.TempPathFactory) -> Any:
    dist = tmp_path_factory.mktemp("dist")
    (dist / "index.html").write_text("<html>shell</html>")
    (dist / "pulse.html").write_text("<html>pulse</html>")
    (dist / "robots.txt").write_text("User-agent: *\n")
    (dist / "assets").mkdir()
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)")
    (dist / "geo").mkdir()
    (dist / "geo" / "countries.json").write_text("{}")
    (dist.parent / "secret.txt").write_text("outside the dist root")

    class _SpaConfig(TestingConfig):
        DASHBOARD_DIST = str(dist)

    return create_app(_SpaConfig).test_client()


def test_root_serves_shell_with_csp(spa_client: Any) -> None:
    response = spa_client.get("/")
    assert response.status_code == 200
    assert response.data == b"<html>shell</html>"
    assert response.headers["Cache-Control"] == "no-cache"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_client_side_route_falls_back_to_shell(spa_client: Any) -> None:
    response = spa_client.get("/sessions/abc123")
    assert response.status_code == 200
    assert response.data == b"<html>shell</html>"


def test_prerendered_page_is_served_in_place(spa_client: Any) -> None:
    response = spa_client.get("/pulse")
    assert response.status_code == 200
    assert response.data == b"<html>pulse</html>"
    assert response.headers["Cache-Control"] == "no-cache"


def test_hashed_asset_is_immutable(spa_client: Any) -> None:
    response = spa_client.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["Cache-Control"]


def test_missing_asset_is_404_not_shell(spa_client: Any) -> None:
    assert spa_client.get("/assets/gone-000000.js").status_code == 404


def test_geo_is_cached_but_not_immutable(spa_client: Any) -> None:
    response = spa_client.get("/geo/countries.json")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=604800"
    assert spa_client.get("/geo/nope.json").status_code == 404


def test_plain_file_is_served(spa_client: Any) -> None:
    response = spa_client.get("/robots.txt")
    assert response.status_code == 200
    assert response.data == b"User-agent: *\n"


def test_unknown_api_path_keeps_json_404(spa_client: Any) -> None:
    response = spa_client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.get_json()["code"] == 404


def test_api_routes_still_win(spa_client: Any) -> None:
    assert spa_client.get("/health").get_json() is not None
    spec = spa_client.get("/api/v1/openapi.json")
    assert spec.status_code == 200
    assert spec.get_json()["info"]["title"] == "Honeywatch"
    # Trailing-slash redirect must not be swallowed by the catch-all.
    assert spa_client.get("/api/v1/sessions").status_code == 308


def test_path_traversal_does_not_escape_dist(spa_client: Any) -> None:
    response = spa_client.get("/../secret.txt")
    assert b"outside the dist root" not in response.data
    response = spa_client.get("/assets/..%2f..%2fsecret.txt")
    assert b"outside the dist root" not in response.data


def test_api_only_without_dashboard_dist(client: Any) -> None:
    assert client.get("/").status_code == 404


def test_dist_is_a_directory(spa_client: Any) -> None:
    # Guards the fixture itself: a typo there would turn every test above
    # into a shell fallback.
    dist = pathlib.Path(spa_client.application.config["DASHBOARD_DIST"])
    assert (dist / "index.html").is_file()
