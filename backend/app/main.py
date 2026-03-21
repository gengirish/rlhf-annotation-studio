from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, health, sessions


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="RLHF Annotation API",
        version="0.1.0",
        root_path=settings.root_path or "",
        docs_url="/api/docs" if settings.debug else "/api/docs",
    )

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
    app.include_router(sessions.router, prefix="/api/v1")
    return app


app = create_app()
