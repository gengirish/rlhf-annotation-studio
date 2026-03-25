"""Compatibility wrapper for the legacy app package.

This module enables `uvicorn rlhf_api.main:app` while migration to `src/` layout
is in progress.
"""

from app.main import app, create_app

__all__ = ["app", "create_app"]

