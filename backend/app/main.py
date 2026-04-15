import logging
import time as _time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import warm_pool
from app.routers import (
    api_keys,
    audit,
    auth,
    certificates,
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app")

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 30  # requests per window


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
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        t0 = _time.perf_counter()
        response = await call_next(request)
        response.headers["X-Response-Time"] = f"{(_time.perf_counter() - t0) * 1000:.0f}ms"
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

    @app.middleware("http")
    async def rate_limit_inference(request: Request, call_next):
        if request.url.path.startswith("/api/v1/inference/") and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            now = _time.time()
            window = _rate_limit_store[client_ip]
            window[:] = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
            if len(window) >= _RATE_LIMIT_MAX:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                )
            window.append(now)
        return await call_next(request)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(
            "Unhandled error [request_id=%s] %s %s",
            request_id,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
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
    app.include_router(certificates.router, prefix="/api/v1")
    return app


app = create_app()
