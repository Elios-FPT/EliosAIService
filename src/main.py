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


def load_logging_config() -> dict | None:
    """Load logging configuration from YAML file.

    Returns:
        Logging config dict if file exists, None otherwise
    """
    logging_config_path = Path(__file__).parent / "infrastructure" / "config" / "logging.yaml"
    if logging_config_path.exists():
        with open(logging_config_path, 'r') as f:
            return yaml.safe_load(f)
    return None


# Configure logging at module level - this runs when uvicorn imports the module
# This ensures logging is configured before uvicorn can add default handlers
_log_config = load_logging_config()
if _log_config:
    # Clear existing handlers to ensure clean setup before applying config
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.propagate = False

    # Clear handlers from loggers that will be configured
    # This prevents handler accumulation when dictConfig is applied
    logger_names = ['sqlalchemy', 'sqlalchemy.engine', 'uvicorn', 'uvicorn.error', 'uvicorn.access', 'src', 'src.main']
    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

    # Apply our config (disable_existing_loggers: true ensures clean reset)
    logging.config.dictConfig(_log_config)

# Get logger (now properly configured)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events.
    """
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database
    logger.info("Initializing database connection...")

    # Configure SQLAlchemy logging level based on debug mode
    # Since we disabled echo in engine config, we control logging via logger level
    sqlalchemy_engine_logger = logging.getLogger('sqlalchemy.engine')
    sqlalchemy_engine_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

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
    import asyncio
    import sys

    import uvicorn

    settings = get_settings()

    # Detect PyCharm debugger to avoid loop_factory compatibility issue
    # PyCharm's debugger patches asyncio.run() but doesn't support loop_factory parameter
    is_pycharm_debugger = "pydevd" in sys.modules

    if is_pycharm_debugger:
        # Use alternative startup method for PyCharm debugger compatibility
        # This avoids the loop_factory parameter that PyCharm's patched asyncio.run() doesn't support
        config = uvicorn.Config(
            "src.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=settings.debug,
            log_config=None,  # Logging configured at module level
            access_log=False,  # Disable uvicorn's access log
        )
        server = uvicorn.Server(config)
        asyncio.run(server.serve())
    else:
        # Normal startup for non-PyCharm environments
        # Logging is configured at module level
        # Pass None to prevent uvicorn from adding its own handlers
        uvicorn.run(
            "src.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=settings.debug,
            log_config=None,  # Logging configured at module level
            access_log=False,  # Disable uvicorn's access log
        )
