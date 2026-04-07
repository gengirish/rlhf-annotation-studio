from __future__ import annotations

import httpx


class RLHFAPIError(Exception):
    def __init__(self, status_code: int, detail: str, response: httpx.Response | None = None):
        self.status_code = status_code
        self.detail = detail
        self.response = response
        super().__init__(f"[{status_code}] {detail}")


class AuthenticationError(RLHFAPIError):
    pass


class NotFoundError(RLHFAPIError):
    pass


class ValidationError(RLHFAPIError):
    pass
