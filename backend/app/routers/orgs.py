from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import ROLE_ADMIN, VALID_ROLES, get_current_user, require_reviewer_or_admin
from app.db import get_db
from app.models import Annotator, Organization, ReviewAssignment
from app.schemas.annotator import AnnotatorRead
from app.schemas.organization import OrgCreate, OrgMemberAdd, OrgRead, OrgUpdate, RoleUpdateRequest

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
    current_user.role = ROLE_ADMIN
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
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotator not found for email",
        )

    if member.org_id is not None and member.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Annotator already belongs to another organization",
        )

    member.org_id = org_id
    await db.commit()
    await db.refresh(member)
    return AnnotatorRead.model_validate(member)


@router.put("/{org_id}/members/{member_id}/role", response_model=AnnotatorRead)
async def update_member_role(
    org_id: UUID,
    member_id: UUID,
    body: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> AnnotatorRead:
    await _get_org_or_404(db, org_id)
    _require_org_member(current_user, org_id)
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    member = await db.get(Annotator, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member is not in this organization",
        )

    member.role = body.role
    await db.commit()
    await db.refresh(member)
    return AnnotatorRead.model_validate(member)


@router.get("/{org_id}/team-stats")
async def team_stats(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> list[dict]:
    await _get_org_or_404(db, org_id)
    _require_org_member(current_user, org_id)

    result = await db.execute(
        select(Annotator).where(Annotator.org_id == org_id).order_by(Annotator.name)
    )
    members = result.scalars().all()
    member_ids = [m.id for m in members]
    if not member_ids:
        return []

    cnt_result = await db.execute(
        select(
            ReviewAssignment.annotator_id,
            ReviewAssignment.status,
            func.count().label("n"),
        )
        .where(ReviewAssignment.annotator_id.in_(member_ids))
        .group_by(ReviewAssignment.annotator_id, ReviewAssignment.status)
    )
    by_member: dict[UUID, dict[str, int]] = {}
    for aid, st, n in cnt_result.all():
        by_member.setdefault(aid, {})[st] = int(n)

    out: list[dict] = []
    for m in members:
        raw = by_member.get(m.id, {})
        assigned = raw.get("assigned", 0)
        submitted = raw.get("submitted", 0)
        approved = raw.get("approved", 0)
        rejected = raw.get("rejected", 0)
        total = sum(raw.values())
        out.append(
            {
                "annotator": AnnotatorRead.model_validate(m).model_dump(mode="json"),
                "stats": {
                    "assigned": assigned,
                    "submitted": submitted,
                    "approved": approved,
                    "rejected": rejected,
                    "total": total,
                },
            }
        )
    return out
