from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.lifespan import lifespan
from app.core.limiter import limiter
from app.core.settings import get_settings
from app.features.auth.router import router as auth_router
from app.features.butler.router import router as butler_router
from app.features.health.router import router as health_router
from app.features.roles.router import router as roles_router
from app.features.users.router import router as users_router


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/api/documentation",
        redoc_url="/api/redocumentation",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    if not settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(butler_router)
    app.include_router(users_router)
    app.include_router(roles_router)

    return app


app = create_app()
