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
rlhf quality leaderboard
rlhf webhooks list
rlhf api-keys create --name "CI Pipeline"
```

Machine-readable output:

```bash
rlhf --json packs list
```

Environment variables: `RLHF_BASE_URL`, `RLHF_API_KEY`, `RLHF_TOKEN` override saved config when set.

## API coverage note

The client targets `/api/v1/...` routes defined by the Annotation Studio backend. Endpoints such as `POST /api/v1/judge/run` and `GET /api/v1/quality/leaderboard` are included for forward compatibility; ensure your server version exposes them (or expect `404` until they are mounted).

## License

Same as the parent project.
