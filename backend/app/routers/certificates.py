from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.db import get_db
from app.models import Annotator
from app.schemas.certificate import CertificateCreate, CertificatePublic, CertificateRead
from app.services import certificate_service

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.post("", response_model=CertificateRead, status_code=status.HTTP_201_CREATED)
async def issue_certificate(
    body: CertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_admin),
) -> CertificateRead:
    cert = await certificate_service.issue_certificate(db, body, current_user)
    return CertificateRead.model_validate(cert)


@router.get("", response_model=list[CertificateRead])
async def list_all_certificates(
    db: AsyncSession = Depends(get_db),
    _user: Annotator = Depends(require_admin),
) -> list[CertificateRead]:
    certs = await certificate_service.list_all_certificates(db)
    return [CertificateRead.model_validate(c) for c in certs]


@router.get("/mine", response_model=list[CertificateRead])
async def list_my_certificates(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> list[CertificateRead]:
    certs = await certificate_service.list_my_certificates(db, current_user.id)
    return [CertificateRead.model_validate(c) for c in certs]


@router.get("/{certificate_id}/public", response_model=CertificatePublic)
async def get_certificate_public(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CertificatePublic:
    """Public endpoint - no auth required. Returns limited certificate info."""
    cert = await certificate_service.get_certificate_public(db, certificate_id)
    return CertificatePublic.model_validate(cert)
