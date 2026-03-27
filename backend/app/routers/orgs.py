from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator, Organization
from app.schemas.annotator import AnnotatorRead
from app.schemas.organization import OrgCreate, OrgMemberAdd, OrgRead, OrgUpdate

router = APIRouter(prefix="/orgs", tags=["orgs"])


async def _get_org_or_404(db: AsyncSession, org_id: UUID) -> Organization:
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


def _require_org_member(current_user: Annotator, org_id: UUID) -> None:
    if current_user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )


@router.post("", response_model=OrgRead, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrgCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> OrgRead:
    existing = await db.execute(select(Organization).where(Organization.slug == body.slug.strip()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization slug '{body.slug}' already exists",
        )

    org = Organization(name=body.name.strip(), slug=body.slug.strip())
    db.add(org)
    await db.flush()
    current_user.org_id = org.id
    await db.commit()
    await db.refresh(org)
    await db.refresh(current_user)
    return OrgRead.model_validate(org)


@router.get("/{org_id}", response_model=OrgRead)
async def get_org(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> OrgRead:
    org = await _get_org_or_404(db, org_id)
    _require_org_member(current_user, org_id)
    return OrgRead.model_validate(org)


@router.put("/{org_id}", response_model=OrgRead)
async def update_org(
    org_id: UUID,
    body: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> OrgRead:
    org = await _get_org_or_404(db, org_id)
    _require_org_member(current_user, org_id)

    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        org.name = data["name"].strip()
    if "plan_tier" in data and data["plan_tier"] is not None:
        org.plan_tier = data["plan_tier"].strip()
    if "max_seats" in data:
        org.max_seats = data["max_seats"]
    if "max_packs" in data:
        org.max_packs = data["max_packs"]

    await db.commit()
    await db.refresh(org)
    return OrgRead.model_validate(org)


@router.get("/{org_id}/members", response_model=list[AnnotatorRead])
async def list_org_members(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> list[AnnotatorRead]:
    await _get_org_or_404(db, org_id)
    _require_org_member(current_user, org_id)

    result = await db.execute(
        select(Annotator).where(Annotator.org_id == org_id).order_by(Annotator.name)
    )
    members = result.scalars().all()
    return [AnnotatorRead.model_validate(m) for m in members]


@router.post("/{org_id}/members", response_model=AnnotatorRead, status_code=status.HTTP_201_CREATED)
async def add_org_member(
    org_id: UUID,
    body: OrgMemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> AnnotatorRead:
    await _get_org_or_404(db, org_id)
    _require_org_member(current_user, org_id)

    result = await db.execute(select(Annotator).where(Annotator.email == str(body.email)))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotator not found for email")

    if member.org_id is not None and member.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Annotator already belongs to another organization",
        )

    member.org_id = org_id
    await db.commit()
    await db.refresh(member)
    return AnnotatorRead.model_validate(member)
