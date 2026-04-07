from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user, require_admin
from app.db import get_db
from app.models.annotator import Annotator
from app.models.dataset import Dataset, DatasetVersion
from app.schemas.dataset import (
    BulkImportRequest,
    DatasetCreate,
    DatasetDetailRead,
    DatasetListResponse,
    DatasetRead,
    DatasetVersionCreate,
    DatasetVersionRead,
    ExportResponse,
)
from app.services.dataset_service import DELETED_TAG, DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _is_deleted(ds: Dataset) -> bool:
    tags = ds.tags if isinstance(ds.tags, list) else []
    return DELETED_TAG in tags


async def _dataset_read_with_version_count(db: AsyncSession, ds: Dataset) -> DatasetRead:
    result = await db.execute(
        select(func.count()).select_from(DatasetVersion).where(DatasetVersion.dataset_id == ds.id),
    )
    cnt = int(result.scalar_one() or 0)
    base = DatasetRead.model_validate(ds)
    return base.model_copy(update={"version_count": cnt})


def _require_org_dataset(current_user: Annotator, ds: Dataset) -> None:
    if current_user.org_id is None or ds.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dataset not accessible for this organization",
        )


async def _get_dataset_or_404(db: AsyncSession, dataset_id: uuid.UUID) -> Dataset:
    ds = await db.get(Dataset, dataset_id)
    if ds is None or _is_deleted(ds):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return ds


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> DatasetRead:
    ds = await DatasetService.create_dataset(db, current_user, body)
    return await _dataset_read_with_version_count(db, ds)


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> DatasetListResponse:
    if current_user.org_id is None:
        return DatasetListResponse(items=[], total=0)

    visible = and_(
        Dataset.org_id == current_user.org_id,
        not_(Dataset.tags.contains([DELETED_TAG])),
    )
    count_result = await db.execute(select(func.count()).select_from(Dataset).where(visible))
    total = int(count_result.scalar_one() or 0)

    result = await db.execute(
        select(Dataset)
        .where(visible)
        .order_by(Dataset.created_at.desc())
        .offset(skip)
        .limit(limit),
    )
    rows = result.scalars().all()
    items = [await _dataset_read_with_version_count(db, ds) for ds in rows]
    return DatasetListResponse(items=items, total=total)


@router.post("/import", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def bulk_import_dataset(
    body: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> DatasetRead:
    ds = await DatasetService.create_dataset_from_bulk_import(db, current_user, body)
    return await _dataset_read_with_version_count(db, ds)


@router.get("/{dataset_id}", response_model=DatasetDetailRead)
async def get_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> DatasetDetailRead:
    result = await db.execute(
        select(Dataset).options(selectinload(Dataset.versions)).where(Dataset.id == dataset_id),
    )
    ds = result.scalar_one_or_none()
    if ds is None or _is_deleted(ds):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    _require_org_dataset(current_user, ds)

    base = await _dataset_read_with_version_count(db, ds)
    versions = sorted(ds.versions, key=lambda v: v.version)
    return DatasetDetailRead(
        **base.model_dump(),
        versions=[DatasetVersionRead.model_validate(v) for v in versions],
    )


@router.post(
    "/{dataset_id}/versions", response_model=DatasetVersionRead, status_code=status.HTTP_201_CREATED
)
async def create_dataset_version(
    dataset_id: uuid.UUID,
    body: DatasetVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> DatasetVersionRead:
    ds = await _get_dataset_or_404(db, dataset_id)
    _require_org_dataset(current_user, ds)
    ver = await DatasetService.create_version(
        db,
        dataset_id,
        current_user,
        list(body.source_pack_ids),
        body.notes,
    )
    return DatasetVersionRead.model_validate(ver)


@router.get("/{dataset_id}/versions/{version}", response_model=DatasetVersionRead)
async def get_dataset_version(
    dataset_id: uuid.UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> DatasetVersionRead:
    ds = await _get_dataset_or_404(db, dataset_id)
    _require_org_dataset(current_user, ds)
    result = await db.execute(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version == version,
        ),
    )
    ver = result.scalar_one_or_none()
    if ver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return DatasetVersionRead.model_validate(ver)


@router.get("/{dataset_id}/versions/{version}/export", response_model=ExportResponse)
async def export_dataset_version(
    dataset_id: uuid.UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
    format: str = Query("jsonl", alias="format"),
    train_ratio: float | None = Query(None, ge=0.0, le=1.0),
    val_ratio: float | None = Query(None, ge=0.0, le=1.0),
    test_ratio: float | None = Query(None, ge=0.0, le=1.0),
    filters: str | None = Query(None, description="JSON object of export filters"),
) -> ExportResponse:
    ds = await _get_dataset_or_404(db, dataset_id)
    _require_org_dataset(current_user, ds)
    result = await db.execute(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version == version,
        ),
    )
    ver = result.scalar_one_or_none()
    if ver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    allowed = {"jsonl", "dpo", "orpo", "hf_dataset", "csv"}
    if format not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"format must be one of {sorted(allowed)}",
        )

    split: dict[str, float] | None = None
    if any(r is not None for r in (train_ratio, val_ratio, test_ratio)):
        split = {}
        if train_ratio is not None:
            split["train"] = train_ratio
        if val_ratio is not None:
            split["validation"] = val_ratio
        if test_ratio is not None:
            split["test"] = test_ratio
        if not split:
            split = None

    filters_obj: dict[str, Any] | None = None
    if filters is not None and filters.strip():
        try:
            parsed = json.loads(filters)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"filters must be valid JSON: {exc}",
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="filters must be a JSON object",
            )
        filters_obj = parsed

    data, task_count, filename = DatasetService.export(
        ver,
        format_name=format,
        split=split,
        filters=filters_obj,
    )
    return ExportResponse(data=data, format=format, task_count=task_count, filename=filename)


@router.get("/{dataset_id}/diff")
async def diff_dataset_versions(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
    v1: int = Query(..., description="Earlier version number"),
    v2: int = Query(..., description="Later version number"),
) -> dict[str, Any]:
    ds = await _get_dataset_or_404(db, dataset_id)
    _require_org_dataset(current_user, ds)

    r1 = await db.execute(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version == v1,
        ),
    )
    r2 = await db.execute(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version == v2,
        ),
    )
    ver1 = r1.scalar_one_or_none()
    ver2 = r2.scalar_one_or_none()
    if ver1 is None or ver2 is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return DatasetService.diff_versions(ver1, ver2)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_admin),
) -> Response:
    ds = await db.get(Dataset, dataset_id)
    if ds is None or _is_deleted(ds):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    _require_org_dataset(current_user, ds)
    await DatasetService.soft_delete_dataset(db, dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
