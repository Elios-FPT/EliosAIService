"""Main application entry point.

This module sets up the FastAPI application with all routes and middleware.
"""

import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import yaml
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .adapters.api.rest import health_routes
from .adapters.api.rest.interview_routes import router as interview_router
from .adapters.api.websocket.interview_handler import handle_interview_websocket
from .infrastructure.config import get_settings
from .infrastructure.database import close_db, init_db

# Configure logging from YAML
logging_config_path = Path(__file__).parent / "infrastructure" / "config" / "logging.yaml"
if logging_config_path.exists():
    with open(logging_config_path, 'r') as f:
        config = yaml.safe_load(f)
        logging.config.dictConfig(config)
else:
    # Fallback to basic config if YAML not found
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database
    logger.info("Initializing database connection...")
    await init_db()
    logger.info("Database connection established")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    logger.info("Closing database connections...")
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered mock interview platform",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_routes.router, tags=["Health"])
    app.include_router(
        interview_router, prefix=settings.api_prefix, tags=["Interviews"]
    )

    # WebSocket endpoint for real-time interview
    @app.websocket("/ws/interviews/{interview_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        interview_id: UUID,
    ):
        """WebSocket endpoint for real-time interview communication."""
        await handle_interview_websocket(websocket, interview_id)

    # TODO: Add more routers as they are implemented
    # app.include_router(cv_routes.router, prefix=settings.api_prefix, tags=["CV"])
    # app.include_router(question_routes.router, prefix=settings.api_prefix, tags=["Questions"])

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
