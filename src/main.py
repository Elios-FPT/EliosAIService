"""Main application entry point.

This module sets up the FastAPI application with all routes and middleware.
"""

from datetime import datetime

def debug_print(msg: str):
    """Helper function to print debug messages with timestamps."""
    print(f"DEBUG [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]: {msg}", flush=True)

debug_print("Starting imports...")

import asyncio
debug_print("asyncio imported")

import logging
import logging.config
debug_print("logging imported")

import sys
debug_print("sys imported")

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID
debug_print("stdlib imports done")

import yaml
debug_print("yaml imported")

from fastapi import FastAPI, WebSocket
debug_print("FastAPI imported")

from fastapi.middleware.cors import CORSMiddleware
debug_print("CORS middleware imported")

debug_print("About to import local modules...")

from .adapters.api.rest import health_routes
debug_print("health_routes imported")

from .adapters.api.rest.interview_routes import router as interview_router
debug_print("interview_routes imported")

from .adapters.api.websocket.interview_handler import handle_interview_websocket
debug_print("websocket handler imported")

from .infrastructure.config import get_settings
debug_print("settings imported")

from .infrastructure.database import close_db, init_db
debug_print("database modules imported")


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

# TEMPORARILY DISABLED: Event loop policy setting at module level
# This was causing hangs during import. We'll set it in the main block instead.
# On Windows, configure event loop policy to use SelectorEventLoop
# This is required for psycopg (used by AsyncPostgresSaver) compatibility
# ProactorEventLoop doesn't support the select operations that psycopg needs
# if sys.platform == "win32" and "pydevd" not in sys.modules:
#     try:
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#         logger.debug("Event loop policy set to WindowsSelectorEventLoopPolicy")
#     except Exception as e:
#         logger.warning(f"Failed to set event loop policy: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events.
    """
    debug_print("lifespan startup started")
    settings = get_settings()
    debug_print(f"Got settings: {settings.app_name}")
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database
    debug_print("About to initialize database...")
    logger.info("Initializing database connection...")

    # Configure SQLAlchemy logging level based on debug mode
    # Since we disabled echo in engine config, we control logging via logger level
    sqlalchemy_engine_logger = logging.getLogger('sqlalchemy.engine')
    sqlalchemy_engine_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    debug_print("About to call init_db()...")
    await init_db()
    debug_print("init_db() completed")
    logger.info("Database connection established")

    debug_print("lifespan startup complete, yielding...")
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


# Debug: Print before creating app
debug_print("About to create FastAPI app...")

# Create application instance
app = create_app()

# Debug: Print to verify module import completed
debug_print("FastAPI app created, module import complete")


if __name__ == "__main__":
    debug_print("Entering main block")
    import uvicorn
    debug_print("uvicorn imported")

    settings = get_settings()
    debug_print(f"Got settings in main: {settings.api_host}:{settings.api_port}")

    # Detect PyCharm debugger to avoid loop_factory compatibility issue
    # PyCharm's debugger patches asyncio.run() but doesn't support loop_factory parameter
    is_pycharm_debugger = "pydevd" in sys.modules
    debug_print(f"PyCharm debugger detected: {is_pycharm_debugger}")

    # On Windows, ensure event loop policy is set (PyCharm debugger may need this set here)
    if sys.platform == "win32":
        debug_print("Setting event loop policy for Windows...")
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            debug_print("Event loop policy set successfully")
            logger.info("Event loop policy set to WindowsSelectorEventLoopPolicy for Windows")
        except Exception as e:
            debug_print(f"Failed to set event loop policy: {e}")
            logger.warning(f"Failed to set event loop policy: {e}")

    if is_pycharm_debugger:
        debug_print("Using PyCharm-compatible startup method...")
        # PyCharm's debugger patches asyncio.run() and doesn't support loop_factory
        # We need to manually create and run the event loop
        config = uvicorn.Config(
            "src.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=settings.debug,
            log_config=None,  # Logging configured at module level
            access_log=False,  # Disable uvicorn's access log
        )
        debug_print("Uvicorn config created, creating server...")
        server = uvicorn.Server(config)
        debug_print("Server created, about to start server...")

        # Manually create and run the event loop to avoid PyCharm's patched asyncio.run()
        debug_print("Creating new event loop...")
        loop = None
        try:
            # Get or create event loop with the policy we set
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            debug_print("Event loop created and set")

            debug_print("Starting server.serve()...")
            # Run the server in the event loop
            # The server will handle signal handlers internally
            loop.run_until_complete(server.serve())
            debug_print("Server started successfully")
        except KeyboardInterrupt:
            debug_print("Server interrupted by user")
        except Exception as e:
            debug_print(f"Error starting server: {e}")
            import traceback
            debug_print(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            if loop:
                debug_print("Closing event loop...")
                try:
                    # Cancel all pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    # Wait for tasks to complete cancellation
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                finally:
                    loop.close()
                    debug_print("Event loop closed")
    else:
        debug_print("Using normal uvicorn.run()...")
        # Normal startup (Windows will use SelectorEventLoop due to policy set above)
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
