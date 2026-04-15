from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotator import Annotator
from app.models.certificate import Certificate
from app.schemas.certificate import CertificateCreate


async def issue_certificate(
    db: AsyncSession,
    body: CertificateCreate,
    issuer: Annotator,
) -> Certificate:
    annotator = await db.get(Annotator, body.annotator_id)
    if not annotator:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Annotator not found")

    cert = Certificate(
        annotator_id=body.annotator_id,
        title=body.title,
        description=body.description,
        certificate_type=body.certificate_type,
        source_id=body.source_id,
        recipient_name=annotator.name,
        issued_by=issuer.id,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


async def list_my_certificates(
    db: AsyncSession,
    annotator_id: UUID,
) -> list[Certificate]:
    result = await db.execute(
        select(Certificate)
        .where(Certificate.annotator_id == annotator_id)
        .order_by(Certificate.issued_at.desc())
    )
    return list(result.scalars().all())


async def get_certificate_public(
    db: AsyncSession,
    certificate_id: UUID,
) -> Certificate:
    cert = await db.get(Certificate, certificate_id)
    if not cert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    return cert


async def list_all_certificates(
    db: AsyncSession,
) -> list[Certificate]:
    result = await db.execute(
        select(Certificate).order_by(Certificate.issued_at.desc())
    )
    return list(result.scalars().all())
