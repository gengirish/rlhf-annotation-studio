from __future__ import annotations

import json

import httpx
import pytest

from rlhf_studio.client import RLHFClient
from rlhf_studio.exceptions import AuthenticationError, NotFoundError, RLHFAPIError, ValidationError


def test_api_key_header_on_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-api-key") == "rlhf_test"
        return httpx.Response(200, json={"packs": [], "total": 0, "limit": 50, "offset": 0, "has_more": False})

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test", api_key="rlhf_test")
    client._client = httpx.Client(transport=transport, timeout=30.0)
    client.list_packs()


def test_bearer_token_header_when_no_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer jwt-token"
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test", token="jwt-token")
    client._client = httpx.Client(transport=transport, timeout=30.0)
    client.list_datasets()


def test_404_raises_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "missing"})

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0)
    with pytest.raises(NotFoundError) as ei:
        client.get_pack("nope")
    assert ei.value.status_code == 404
    assert "missing" in ei.value.detail


def test_401_raises_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0)
    with pytest.raises(AuthenticationError):
        client.list_datasets()


def test_422_raises_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"detail": [{"loc": ["body", "name"], "msg": "field required", "type": "missing"}]},
        )

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0)
    with pytest.raises(ValidationError) as ei:
        client.create_dataset("x", [])
    assert "body.name" in ei.value.detail or "field required" in ei.value.detail


def test_500_raises_generic_rlhf_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "Internal error"})

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0)
    with pytest.raises(RLHFAPIError) as ei:
        client.list_packs()
    assert type(ei.value) is RLHFAPIError
    assert ei.value.status_code == 500


def test_list_packs_returns_parsed_list() -> None:
    payload = {
        "packs": [{"slug": "a", "name": "A", "id": "550e8400-e29b-41d4-a716-446655440000"}],
        "total": 1,
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/tasks/packs"
        assert request.url.params.get("offset") == "2"
        assert request.url.params.get("limit") == "50"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0, base_url="http://test")
    out = client.list_packs(skip=2, limit=50)
    assert out == payload["packs"]


def test_export_dataset_returns_string_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/datasets/ds1/versions/3/export" in str(request.url)
        assert "format=dpo" in str(request.url)
        return httpx.Response(200, json={"data": '{"x":1}\n', "format": "dpo", "task_count": 1, "filename": "out.jsonl"})

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0, base_url="http://test")
    text = client.export_dataset("ds1", version=3, format="dpo")
    assert text == '{"x":1}\n'


def test_exams_flow_endpoints_and_payloads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/exams":
            if request.method == "GET":
                return httpx.Response(200, json=[{"id": "exam-1"}])
            if request.method == "POST":
                body = json_bytes(request)
                assert body["title"] == "Final Exam"
                assert body["task_pack_id"] == "pack-1"
                assert body["duration_minutes"] == 30
                return httpx.Response(200, json={"id": "exam-1", **body})
        if request.url.path == "/api/v1/exams/exam-1/attempts/start":
            return httpx.Response(200, json={"id": "attempt-1", "exam_id": "exam-1"})
        if request.url.path == "/api/v1/exams/exam-1/attempts/attempt-1/answer":
            body = json_bytes(request)
            assert request.method == "PUT"
            assert body["task_id"] == "q1"
            assert body["annotation_json"]["preference"] == 0
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/api/v1/exams/exam-1/attempts/attempt-1/submit":
            return httpx.Response(200, json={"status": "submitted"})
        if request.url.path == "/api/v1/exams/exam-1/attempts/attempt-1/result":
            return httpx.Response(200, json={"status": "released", "score": 0.9})
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0, base_url="http://test")

    exams = client.list_exams()
    assert exams == [{"id": "exam-1"}]

    created = client.create_exam(
        "Final Exam",
        "pack-1",
        30,
        pass_threshold=0.8,
        max_attempts=2,
        description="Enterprise exam",
        is_published=True,
    )
    assert created["is_published"] is True

    attempt = client.start_exam_attempt("exam-1")
    assert attempt["id"] == "attempt-1"

    saved = client.save_exam_answer(
        "exam-1",
        "attempt-1",
        "q1",
        {"preference": 0, "dimensions": {"safety": 5}},
        time_spent_seconds=14.5,
    )
    assert saved["ok"] is True

    submitted = client.submit_exam_attempt("exam-1", "attempt-1")
    assert submitted["status"] == "submitted"

    result = client.get_exam_attempt_result("exam-1", "attempt-1")
    assert result["status"] == "released"


def test_exam_review_release_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/exams/review/attempts":
            return httpx.Response(200, json=[{"id": "attempt-1"}])
        if request.url.path == "/api/v1/exams/review/attempts/attempt-1/release":
            body = json_bytes(request)
            assert body["release"] is True
            assert body["review_notes"] == "Approved"
            return httpx.Response(200, json={"id": "attempt-1", "status": "released"})
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    client = RLHFClient(base_url="http://test")
    client._client = httpx.Client(transport=transport, timeout=30.0, base_url="http://test")

    rows = client.list_exam_review_attempts()
    assert rows == [{"id": "attempt-1"}]

    released = client.release_exam_attempt_review("attempt-1", review_notes="Approved")
    assert released["status"] == "released"


def json_bytes(request: httpx.Request) -> dict:
    raw = request.content.decode("utf-8")
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
    return parsed
