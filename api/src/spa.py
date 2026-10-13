"""Serve the compiled dashboard from the API process.

Replaces the dashboard's own nginx (dashboard/nginx.conf) in the combined
image: same lookup order, cache windows and security headers, so the browser
sees no difference. Only registered when `DASHBOARD_DIST` is set.
"""

from __future__ import annotations

import os
import pathlib

from flask import Flask, Response, abort, send_from_directory
from werkzeug.security import safe_join

# Mirrors dashboard/security-headers.conf. The nosniff / frame / referrer
# baseline comes from security_headers.py.
_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
        "form-action 'none'"
    ),
    "Permissions-Policy": (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
        "magnetometer=(), gyroscope=(), accelerometer=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}

# Hashed build output: cached 30d. A missing one is a real 404, never the SPA
# shell, or a stale chunk URL would come back as HTML.
_ASSET_SUFFIXES = (".js", ".css", ".woff", ".woff2", ".png", ".jpg", ".svg", ".ico")
_ASSET_CACHE = "public, max-age=2592000, immutable"
# Map geometry carries no content hash, so it must be able to revalidate.
_GEO_CACHE = "public, max-age=604800"
# HTML stays fresh so a deploy is picked up on the next load.
_HTML_CACHE = "no-cache"


def init_spa(app: Flask, dist: str) -> None:
    """Register the catch-all route serving the dashboard build in `dist`."""
    root = pathlib.Path(dist)

    def _exists(name: str) -> bool:
        full = safe_join(str(root), name)
        return full is not None and os.path.isfile(full)

    def _send(name: str, cache_control: str | None) -> Response:
        response = send_from_directory(root, name)
        if cache_control is not None:
            response.headers["Cache-Control"] = cache_control
        response.headers.update(_HEADERS)
        return response

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        # Unknown API paths keep the JSON 404 envelope.
        if path == "api" or path.startswith("api/"):
            abort(404)

        if path.startswith("geo/"):
            if not _exists(path):
                abort(404)
            return _send(path, _GEO_CACHE)

        if path.endswith(_ASSET_SUFFIXES):
            if not _exists(path):
                abort(404)
            return _send(path, _ASSET_CACHE)

        if _exists(path):
            cache = _HTML_CACHE if path.endswith(".html") else None
            return _send(path, cache)

        # Prerendered pages are flat files (/pulse -> pulse.html); anything
        # else is a client-side route and gets the shell.
        prerendered = f"{path}.html"
        if path and _exists(prerendered):
            return _send(prerendered, _HTML_CACHE)
        return _send("index.html", _HTML_CACHE)
