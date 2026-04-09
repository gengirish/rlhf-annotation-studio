from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from rlhf_studio.exceptions import (
    AuthenticationError,
    NotFoundError,
    RLHFAPIError,
    ValidationError,
)


def _detail_from_response(response: httpx.Response) -> str:
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        text = (response.text or "").strip()
        return text or response.reason_phrase or "Request failed"

    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            parts: list[str] = []
            for item in detail:
                if isinstance(item, dict):
                    loc = item.get("loc", ())
                    msg = item.get("msg", "")
                    parts.append(f"{'.'.join(str(x) for x in loc)}: {msg}")
                else:
                    parts.append(str(item))
            return "; ".join(parts) if parts else json.dumps(body)
        if isinstance(detail, dict):
            return json.dumps(detail)
        if detail is not None:
            return str(detail)
    return str(body)


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    status = response.status_code
    detail = _detail_from_response(response)
    exc: type[RLHFAPIError] = RLHFAPIError
    if status in (401, 403):
        exc = AuthenticationError
    elif status == 404:
        exc = NotFoundError
    elif status == 422:
        exc = ValidationError
    raise exc(status, detail, response=response)


class RLHFClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._token = token
        self._client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        elif self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        url = f"{self._base_url}{path}" if path.startswith("/") else f"{self._base_url}/{path}"
        merged = self._headers()
        if headers:
            merged.update(headers)
        response = self._client.request(
            method,
            url,
            json=json_body,
            params=params,
            content=content,
            headers=merged,
        )
        _raise_for_status(response)
        return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RLHFClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --- Auth ---

    def login(self, email: str, password: str) -> dict[str, Any]:
        r = self._request(
            "POST",
            "/api/v1/auth/login",
            json_body={"email": email, "password": password},
        )
        return r.json()

    def register(self, name: str, email: str, password: str) -> dict[str, Any]:
        r = self._request(
            "POST",
            "/api/v1/auth/register",
            json_body={"name": name, "email": email, "password": password},
        )
        return r.json()

    # --- Task packs ---

    def list_packs(self, skip: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        r = self._request(
            "GET",
            "/api/v1/tasks/packs",
            params={"offset": skip, "limit": limit},
        )
        data = r.json()
        if isinstance(data, dict) and "packs" in data:
            packs = data["packs"]
            return packs if isinstance(packs, list) else []
        return []

    def get_pack(self, pack_id: str) -> dict[str, Any]:
        r = self._request("GET", f"/api/v1/tasks/packs/{pack_id}")
        return r.json()

    def create_pack(self, name: str, tasks: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        slug = kwargs.get("slug")
        if not slug:
            slug = self._slug_from_name(name)
        body: dict[str, Any] = {
            "slug": slug,
            "name": name,
            "tasks_json": tasks,
            "description": kwargs.get("description", ""),
            "language": kwargs.get("language", "general"),
        }
        r = self._request("POST", "/api/v1/tasks/packs", json_body=body)
        return r.json()

    @staticmethod
    def _slug_from_name(name: str) -> str:
        s = name.strip().lower()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        s = s.strip("-") or "task-pack"
        return s[:255]

    def upload_pack(self, filepath: str) -> dict[str, Any]:
        path = Path(filepath)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Task pack file must be a JSON object")

        tasks_json = raw.get("tasks_json")
        if tasks_json is None:
            tasks_json = raw.get("tasks")
        if not isinstance(tasks_json, list):
            raise ValueError("Expected 'tasks_json' or 'tasks' array in JSON file")

        name = raw.get("name") or path.stem
        kwargs: dict[str, Any] = {}
        if raw.get("slug"):
            kwargs["slug"] = raw["slug"]
        if raw.get("description") is not None:
            kwargs["description"] = raw["description"]
        if raw.get("language"):
            kwargs["language"] = raw["language"]
        return self.create_pack(name, tasks_json, **kwargs)

    # --- Annotations (review assignment submit) ---

    def submit_annotation(self, assignment_id: str, annotation: dict[str, Any]) -> dict[str, Any]:
        r = self._request(
            "POST",
            f"/api/v1/reviews/{assignment_id}/submit",
            json_body={"annotation_json": annotation},
        )
        return r.json()

    # --- Datasets ---

    def list_datasets(self, skip: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        r = self._request(
            "GET",
            "/api/v1/datasets",
            params={"skip": skip, "limit": limit},
        )
        data = r.json()
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            return items if isinstance(items, list) else []
        return []

    def create_dataset(self, name: str, pack_ids: list[str], **kwargs: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "source_pack_ids": pack_ids,
            "task_type": kwargs.get("task_type", "mixed"),
            "tags": kwargs.get("tags", []),
        }
        if "description" in kwargs:
            body["description"] = kwargs["description"]
        r = self._request("POST", "/api/v1/datasets", json_body=body)
        return r.json()

    def export_dataset(self, dataset_id: str, version: int, format: str = "jsonl") -> str:
        r = self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/versions/{version}/export",
            params={"format": format},
        )
        data = r.json()
        if isinstance(data, dict) and "data" in data:
            return str(data["data"])
        return r.text

    # --- Reviews ---

    def list_reviews(self, status: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if status is not None and status.strip():
            params["status"] = status.strip()
        r = self._request("GET", "/api/v1/reviews/team", params=params or None)
        data = r.json()
        return data if isinstance(data, list) else []

    def assign_review(self, pack_id: str, task_id: str, annotator_id: str) -> dict[str, Any]:
        body = {
            "task_pack_id": pack_id,
            "task_id": task_id,
            "annotator_id": annotator_id,
        }
        r = self._request("POST", "/api/v1/reviews/assign", json_body=body)
        return r.json()

    # --- IAA ---

    def compute_iaa(self, pack_id: str, task_ids: list[str] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"task_pack_id": pack_id}
        if task_ids is not None:
            body["task_ids"] = task_ids
        r = self._request("POST", "/api/v1/iaa/compute", json_body=body)
        return r.json()

    # --- LLM judge ---

    def run_judge(
        self,
        pack_id: str,
        task_ids: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "task_pack_id": pack_id,
            "task_ids": task_ids,
            "config": {},
        }
        if model:
            body["config"] = {"model": model}
        r = self._request("POST", "/api/v1/judge/evaluate", json_body=body)
        return r.json()

    # --- Quality ---

    def get_quality_score(self, annotator_id: str) -> dict[str, Any]:
        r = self._request("GET", f"/api/v1/quality/score/{annotator_id}")
        return r.json()

    def get_leaderboard(self) -> dict[str, Any]:
        r = self._request("GET", "/api/v1/quality/leaderboard")
        return r.json()

    # --- Webhooks ---

    def create_webhook(self, url: str, events: list[str]) -> dict[str, Any]:
        r = self._request(
            "POST",
            "/api/v1/webhooks",
            json_body={"url": url, "events": events},
        )
        return r.json()

    def list_webhooks(self) -> list[dict[str, Any]]:
        r = self._request("GET", "/api/v1/webhooks")
        data = r.json()
        return data if isinstance(data, list) else []

    # --- API keys ---

    def create_api_key(self, name: str, scopes: list[str] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if scopes is not None:
            body["scopes"] = scopes
        r = self._request("POST", "/api/v1/api-keys", json_body=body)
        return r.json()

    def list_api_keys(self) -> list[dict[str, Any]]:
        r = self._request("GET", "/api/v1/api-keys")
        data = r.json()
        return data if isinstance(data, list) else []
