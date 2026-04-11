import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import warm_pool
from app.routers import (
    api_keys,
    audit,
    auth,
    consensus,
    course,
    datasets,
    exams,
    health,
    iaa,
    inference,
    judge,
    metrics,
    orgs,
    quality,
    reviews,
    sessions,
    tasks,
    webhooks,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await warm_pool()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="RLHF Annotation API",
        version="0.1.0",
        root_path=settings.root_path or "",
        docs_url="/api/docs" if settings.debug else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Response-Time"] = f"{(time.perf_counter() - t0) * 1000:.0f}ms"
        return response

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    use_star = not origins or origins == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if use_star else origins,
        allow_credentials=not use_star,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(orgs.router, prefix="/api/v1")
    app.include_router(inference.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(metrics.router, prefix="/api/v1")
    app.include_router(reviews.router, prefix="/api/v1")
    app.include_router(api_keys.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(consensus.router, prefix="/api/v1")
    app.include_router(datasets.router, prefix="/api/v1")
    app.include_router(exams.router, prefix="/api/v1")
    app.include_router(iaa.router, prefix="/api/v1")
    app.include_router(judge.router, prefix="/api/v1")
    app.include_router(quality.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    app.include_router(course.router, prefix="/api/v1")
    return app


app = create_app()
