# rlhf-studio

Python SDK and CLI for the RLHF Annotation Studio API: task packs, datasets, reviews, IAA, webhooks, and API keys.

## Install

```bash
cd sdk
pip install -e .
# optional dev deps
pip install -e ".[dev]"
```

## Quick start (library)

```python
from rlhf_studio import RLHFClient

client = RLHFClient(api_key="rlhf_your_key_here")
packs = client.list_packs()
iaa = client.compute_iaa(pack_id="00000000-0000-0000-0000-000000000000")
export_text = client.export_dataset(dataset_id="00000000-0000-0000-0000-000000000000", version=1, format="dpo")
```

### Exams quick start (SDK)

```python
from rlhf_studio import RLHFClient

client = RLHFClient(token="eyJ...")

# Annotator flow
exams = client.list_exams()
attempt = client.start_exam_attempt(exam_id=exams[0]["id"])
client.save_exam_answer(
    exam_id=attempt["exam_id"],
    attempt_id=attempt["id"],
    task_id="q1",
    annotation_json={"preference": 0, "justification": "A is safer", "dimensions": {"safety": 5}},
    time_spent_seconds=12.4,
)
submit = client.submit_exam_attempt(exam_id=attempt["exam_id"], attempt_id=attempt["id"])
result = client.get_exam_attempt_result(exam_id=attempt["exam_id"], attempt_id=attempt["id"])

# Reviewer flow
pending = client.list_exam_review_attempts()
if pending:
    client.release_exam_attempt_review(pending[0]["id"], review_notes="Reviewed and released")
```

Use a JWT from `login()` instead of an API key:

```python
client = RLHFClient(token="eyJ...")
```

`task_pack_id`, `dataset_id`, and similar parameters must be UUID strings where the API expects UUIDs. Task pack **slugs** are used on routes such as `GET /api/v1/tasks/packs/{slug}`.

## CLI

Configure a default server and credentials (stored in `~/.rlhf/config.json`):

```bash
rlhf config set --url https://api.example.com --api-key rlhf_xxx
rlhf login --email user@example.com --password secret
```

Common commands:

```bash
rlhf packs list
rlhf packs get my-pack-slug
rlhf packs upload ./my-tasks.json
rlhf datasets list
rlhf datasets export <dataset_uuid> --version 1 --format dpo --output ./output.jsonl
rlhf iaa compute <task_pack_uuid>
rlhf judge run <task_pack_uuid> --model gpt-4
rlhf exams list
rlhf exams start <exam_uuid>
rlhf exams save-answer <exam_uuid> <attempt_uuid> q1 --annotation-json "{\"preference\":0,\"dimensions\":{\"safety\":5}}"
rlhf exams submit <exam_uuid> <attempt_uuid>
rlhf exams result <exam_uuid> <attempt_uuid>
rlhf exams review-list
rlhf exams review-release <attempt_uuid> --review-notes "Approved"
rlhf quality leaderboard
rlhf webhooks list
rlhf api-keys create --name "CI Pipeline"
```

## Exams API coverage

The SDK now supports the exam lifecycle endpoints:

- `list_exams()`, `create_exam(...)`
- `start_exam_attempt(exam_id)`, `get_exam_attempt(exam_id, attempt_id)`
- `save_exam_answer(...)`, `post_exam_integrity_event(...)`
- `submit_exam_attempt(exam_id, attempt_id)`, `get_exam_attempt_result(exam_id, attempt_id)`
- `list_exam_review_attempts()`, `release_exam_attempt_review(...)`

Machine-readable output:

```bash
rlhf --json packs list
```

Environment variables: `RLHF_BASE_URL`, `RLHF_API_KEY`, `RLHF_TOKEN` override saved config when set.

## API coverage note

The client targets `/api/v1/...` routes defined by the Annotation Studio backend. Endpoints such as `POST /api/v1/judge/run` and `GET /api/v1/quality/leaderboard` are included for forward compatibility; ensure your server version exposes them (or expect `404` until they are mounted).

## License

Same as the parent project.
