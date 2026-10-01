"""
app/main.py

FastAPI application entry point.
Configures the app, registers routers, and sets up global middleware.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import health, chat
from app.core.database import engine
from app.models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for the application.
    Runs on startup and shutdown.
    """
    # Create database tables on startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown logic goes here if needed


def create_application() -> FastAPI:
    """
    Application factory.

    Using a factory function makes the app easy to test in isolation
    and keeps the global namespace clean.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Backend API for the Healthcare Monitoring Assistant. "
            "Provides health monitoring, AI-assisted analysis, "
            "and medication tracking capabilities."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------ #
    # Middleware
    # ------------------------------------------------------------------ #
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],       # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ #
    # Routers
    # ------------------------------------------------------------------ #
    application.include_router(health.router)
    application.include_router(chat.router)

    return application


# Module-level app instance consumed by Uvicorn
app = create_application()
