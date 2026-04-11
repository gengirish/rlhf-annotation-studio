from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from rlhf_studio.client import RLHFClient
from rlhf_studio.exceptions import RLHFAPIError

CONFIG_DIR = Path.home() / ".rlhf"
CONFIG_PATH = CONFIG_DIR / "config.json"

console = Console(stderr=True)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def root_context(ctx: click.Context) -> dict[str, Any]:
    c: click.Context | None = ctx
    while c is not None and c.parent is not None:
        c = c.parent
    if c is None or not isinstance(c.obj, dict):
        return {}
    return c.obj


def build_client(
    base_url: str | None,
    api_key: str | None,
    token: str | None,
) -> RLHFClient:
    cfg = load_config()
    url = base_url or os.environ.get("RLHF_BASE_URL") or cfg.get("base_url") or "http://localhost:8000"
    key = api_key if api_key is not None else os.environ.get("RLHF_API_KEY") or cfg.get("api_key")
    tok = token if token is not None else os.environ.get("RLHF_TOKEN") or cfg.get("token")
    return RLHFClient(base_url=url, api_key=key, token=tok)


def _print_json(data: Any) -> None:
    console.print_json(data=data)


def _print_result(data: Any, as_json: bool) -> None:
    if as_json:
        _print_json(data)
        return
    if isinstance(data, list):
        if not data:
            console.print("[dim](empty)[/dim]")
            return
        if isinstance(data[0], dict):
            table = Table(show_header=True)
            keys = list(data[0].keys())
            for k in keys:
                table.add_column(str(k))
            for row in data[:200]:
                table.add_row(*[str(row.get(k, ""))[:80] for k in keys])
            console.print(table)
            if len(data) > 200:
                console.print(f"[dim]… {len(data) - 200} more rows[/dim]")
        else:
            for item in data:
                console.print(str(item))
    elif isinstance(data, dict):
        console.print(JSON.from_data(data))
    else:
        console.print(str(data))


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--base-url", envvar="RLHF_BASE_URL", default=None, help="API base URL (overrides config).")
@click.option("--api-key", envvar="RLHF_API_KEY", default=None, help="API key (overrides config).")
@click.option("--token", envvar="RLHF_TOKEN", default=None, help="JWT token (overrides config).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON.")
@click.pass_context
def cli(
    ctx: click.Context,
    base_url: str | None,
    api_key: str | None,
    token: str | None,
    as_json: bool,
) -> None:
    """RLHF Annotation Studio CLI."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = build_client(base_url, api_key, token)
    ctx.obj["as_json"] = as_json


@cli.command()
@click.option("--email", required=True)
@click.option("--password", prompt=True, hide_input=True)
@click.pass_context
def login(ctx: click.Context, email: str, password: str) -> None:
    """Sign in and save JWT to ~/.rlhf/config.json."""
    client: RLHFClient = ctx.obj["client"]
    as_json: bool = ctx.obj["as_json"]
    try:
        data = client.login(email=email, password=password)
    except RLHFAPIError as e:
        if as_json:
            console.print_json(data={"error": True, "status_code": e.status_code, "detail": e.detail})
        else:
            console.print(f"[red]Login failed:[/red] {e.detail}")
        sys.exit(1)
    cfg = load_config()
    cfg["token"] = data.get("token")
    if "base_url" not in cfg:
        cfg["base_url"] = str(client._base_url)
    save_config(cfg)
    if as_json:
        console.print_json(data={"ok": True, "annotator": data.get("annotator"), "session_id": str(data.get("session_id"))})
    else:
        console.print("[green]Logged in.[/green] Token saved to ~/.rlhf/config.json")


@cli.group("config")
def config_group() -> None:
    """Manage CLI configuration."""


@config_group.command("set")
@click.option("--url", "base_url", default=None, help="API base URL.")
@click.option("--api-key", "api_key", default=None, help="API key (stored in plain text).")
@click.option("--token", default=None, help="JWT bearer token.")
@click.option("--clear-token", is_flag=True, help="Remove saved token.")
@click.option("--clear-api-key", is_flag=True, help="Remove saved API key.")
def config_set(
    base_url: str | None,
    api_key: str | None,
    token: str | None,
    clear_token: bool,
    clear_api_key: bool,
) -> None:
    """Save default URL and credentials."""
    cfg = load_config()
    if base_url:
        cfg["base_url"] = base_url.rstrip("/")
    if api_key is not None:
        cfg["api_key"] = api_key
    if token is not None:
        cfg["token"] = token
    if clear_token:
        cfg.pop("token", None)
    if clear_api_key:
        cfg.pop("api_key", None)
    save_config(cfg)
    console.print("[green]Configuration updated.[/green]")


@config_group.command("show")
def config_show() -> None:
    """Show current config (secrets redacted)."""
    cfg = load_config()
    safe = {**cfg}
    if safe.get("token"):
        safe["token"] = "***"
    if safe.get("api_key"):
        safe["api_key"] = "***"
    console.print_json(data=safe)


@cli.group("packs")
@click.pass_context
def packs(ctx: click.Context) -> None:
    """Task packs."""
    _ = ctx


@packs.command("list")
@click.pass_context
def packs_list(ctx: click.Context) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        rows = client.list_packs()
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(rows, as_json)


@packs.command("get")
@click.argument("pack_id")
@click.pass_context
def packs_get(ctx: click.Context, pack_id: str) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.get_pack(pack_id)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@packs.command("upload")
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def packs_upload(ctx: click.Context, filepath: str) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.upload_pack(filepath)
    except (RLHFAPIError, ValueError) as e:
        if isinstance(e, ValueError):
            if as_json:
                console.print_json(data={"error": True, "detail": str(e)})
            else:
                console.print(f"[red]{e}[/red]")
            sys.exit(1)
        _die(e, as_json)
    _print_result(row, as_json)


@cli.group("datasets")
@click.pass_context
def datasets(ctx: click.Context) -> None:
    """Datasets."""
    _ = ctx


@datasets.command("list")
@click.pass_context
def datasets_list(ctx: click.Context) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        rows = client.list_datasets()
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(rows, as_json)


@datasets.command("export")
@click.argument("dataset_id")
@click.option("--version", type=int, required=True)
@click.option("--format", "export_format", default="jsonl", show_default=True)
@click.option("--output", "-o", type=click.Path(), default=None)
@click.pass_context
def datasets_export(
    ctx: click.Context,
    dataset_id: str,
    version: int,
    export_format: str,
    output: str | None,
) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        text = client.export_dataset(dataset_id, version=version, format=export_format)
    except RLHFAPIError as e:
        _die(e, as_json)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        if as_json:
            console.print_json(
                data={"ok": True, "path": output, "bytes": len(text.encode("utf-8"))},
            )
        else:
            console.print(f"[green]Wrote[/green] {output}")
    elif as_json:
        console.print_json(data={"data": text})
    else:
        console.print(text)


@cli.group("iaa")
@click.pass_context
def iaa_group(ctx: click.Context) -> None:
    """Inter-annotator agreement."""
    _ = ctx


@iaa_group.command("compute")
@click.argument("pack_id")
@click.pass_context
def iaa_compute(ctx: click.Context, pack_id: str) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.compute_iaa(pack_id)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@cli.group("judge")
@click.pass_context
def judge_group(ctx: click.Context) -> None:
    """LLM-as-judge runs."""
    _ = ctx


@judge_group.command("run")
@click.argument("pack_id")
@click.option("--model", default=None)
@click.pass_context
def judge_run(ctx: click.Context, pack_id: str, model: str | None) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.run_judge(pack_id, model=model)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@cli.group("exams")
@click.pass_context
def exams_group(ctx: click.Context) -> None:
    """Exam lifecycle and review workflows."""
    _ = ctx


@exams_group.command("list")
@click.pass_context
def exams_list(ctx: click.Context) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        rows = client.list_exams()
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(rows, as_json)


@exams_group.command("start")
@click.argument("exam_id")
@click.pass_context
def exams_start(ctx: click.Context, exam_id: str) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.start_exam_attempt(exam_id)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@exams_group.command("attempt")
@click.argument("exam_id")
@click.argument("attempt_id")
@click.pass_context
def exams_attempt(ctx: click.Context, exam_id: str, attempt_id: str) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.get_exam_attempt(exam_id, attempt_id)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@exams_group.command("save-answer")
@click.argument("exam_id")
@click.argument("attempt_id")
@click.argument("task_id")
@click.option(
    "--annotation-json",
    required=True,
    help="JSON object string for annotation payload, e.g. '{\"preference\":0,\"dimensions\":{\"safety\":5}}'.",
)
@click.option("--time-spent-seconds", type=float, default=None)
@click.pass_context
def exams_save_answer(
    ctx: click.Context,
    exam_id: str,
    attempt_id: str,
    task_id: str,
    annotation_json: str,
    time_spent_seconds: float | None,
) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        parsed = json.loads(annotation_json)
        if not isinstance(parsed, dict):
            raise ValueError("--annotation-json must decode to a JSON object")
        row = client.save_exam_answer(
            exam_id,
            attempt_id,
            task_id=task_id,
            annotation_json=parsed,
            time_spent_seconds=time_spent_seconds,
        )
    except ValueError as e:
        if as_json:
            console.print_json(data={"error": True, "detail": str(e)})
        else:
            console.print(f"[red]{e}[/red]")
        sys.exit(1)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@exams_group.command("submit")
@click.argument("exam_id")
@click.argument("attempt_id")
@click.pass_context
def exams_submit(ctx: click.Context, exam_id: str, attempt_id: str) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.submit_exam_attempt(exam_id, attempt_id)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@exams_group.command("result")
@click.argument("exam_id")
@click.argument("attempt_id")
@click.pass_context
def exams_result(ctx: click.Context, exam_id: str, attempt_id: str) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.get_exam_attempt_result(exam_id, attempt_id)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@exams_group.command("review-list")
@click.pass_context
def exams_review_list(ctx: click.Context) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        rows = client.list_exam_review_attempts()
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(rows, as_json)


@exams_group.command("review-release")
@click.argument("attempt_id")
@click.option("--review-notes", default=None)
@click.option("--release/--no-release", default=True)
@click.pass_context
def exams_review_release(
    ctx: click.Context,
    attempt_id: str,
    review_notes: str | None,
    release: bool,
) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.release_exam_attempt_review(
            attempt_id,
            release=release,
            review_notes=review_notes,
        )
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@cli.group("quality")
@click.pass_context
def quality_group(ctx: click.Context) -> None:
    """Annotator quality."""
    _ = ctx


@quality_group.command("leaderboard")
@click.pass_context
def quality_leaderboard(ctx: click.Context) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.get_leaderboard()
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@cli.group("webhooks")
@click.pass_context
def webhooks_group(ctx: click.Context) -> None:
    """Webhook endpoints."""
    _ = ctx


@webhooks_group.command("list")
@click.pass_context
def webhooks_list(ctx: click.Context) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        rows = client.list_webhooks()
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(rows, as_json)


@cli.group("api-keys")
@click.pass_context
def api_keys_group(ctx: click.Context) -> None:
    """API keys for automation."""
    _ = ctx


@api_keys_group.command("create")
@click.option("--name", required=True)
@click.option("--scope", "scopes", multiple=True, help="Repeat for each scope (default: server default).")
@click.pass_context
def api_keys_create(ctx: click.Context, name: str, scopes: tuple[str, ...]) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        row = client.create_api_key(name, scopes=list(scopes) if scopes else None)
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(row, as_json)


@api_keys_group.command("list")
@click.pass_context
def api_keys_list(ctx: click.Context) -> None:
    obj = root_context(ctx)
    client: RLHFClient = obj["client"]
    as_json: bool = obj["as_json"]
    try:
        rows = client.list_api_keys()
    except RLHFAPIError as e:
        _die(e, as_json)
    _print_result(rows, as_json)


def _die(e: RLHFAPIError, as_json: bool) -> None:
    if as_json:
        console.print_json(data={"error": True, "status_code": e.status_code, "detail": e.detail})
    else:
        console.print(f"[red]API error:[/red] {e.detail} [dim](HTTP {e.status_code})[/dim]")
    sys.exit(1)
