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

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse
debug_print("FastAPI imported")

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
debug_print("CORS middleware imported")

debug_print("About to import local modules...")

from .controllers.rest import health_routes
debug_print("health_routes imported")

from .controllers.rest.interview_routes import router as interview_router
debug_print("interview_routes imported")

from .controllers.rest.prompt_routes import router as prompt_router
debug_print("prompt_routes imported")

from .controllers.rest.feedback_routes import router as feedback_router
debug_print("feedback_routes imported")
from .controllers.rest.question_routes import router as question_router
debug_print("question_routes imported")

from .controllers.websocket.interview_handler import handle_interview_websocket
debug_print("websocket handler imported")

from .infrastructure.config import get_settings
debug_print("settings imported")

from .infrastructure.database import close_db, init_db
debug_print("database modules imported")

from .infrastructure.middleware.auth_middleware import AuthMiddleware
debug_print("auth middleware imported")


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


def configure_log_levels_from_settings(settings):
    """Adjust log levels based on settings.debug and settings.log_level.

    This should be called after settings are loaded to override
    the hardcoded levels in logging.yaml.

    Note: We need to set both logger level AND handler level for loggers
    with propagate=False, since they won't inherit from parent loggers.
    """
    # Determine target log level
    if settings.debug:
        target_level = logging.DEBUG
    else:
        # Map log_level string to logging constant
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        target_level = level_map.get(settings.log_level.upper(), logging.INFO)

    # Update all relevant loggers
    loggers_to_update = [
        'src.main',
        'src.application',
        'src.adapters',
        'sqlalchemy.engine',
    ]

    for logger_name in loggers_to_update:
        logger_obj = logging.getLogger(logger_name)
        logger_obj.setLevel(target_level)

        # CRITICAL: Also set handler levels for loggers with propagate=False
        # These loggers won't inherit from root, so handler level matters
        for handler in logger_obj.handlers:
            handler.setLevel(target_level)

        # Use print for configuration messages since logger level might not be set yet
        print(f"[LOG CONFIG] Set {logger_name} logger and handlers to {logging.getLevelName(target_level)}")

    # Update root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(target_level)

    # Also update root logger handlers if any
    for handler in root_logger.handlers:
        handler.setLevel(target_level)

    print(f"[LOG CONFIG] Set root logger and handlers to {logging.getLevelName(target_level)}")

    # Special handling for sqlalchemy.engine - ensure it has a handler
    # This is critical because it has propagate=False in YAML
    sqlalchemy_engine_logger = logging.getLogger('sqlalchemy.engine')
    if not sqlalchemy_engine_logger.handlers:
        # If no handler, add console handler (shouldn't happen, but safety check)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(target_level)
        # Use the same formatter as configured in YAML
        try:
            from colorlog import ColoredFormatter
            formatter = ColoredFormatter(
                "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(cyan)s%(name)s%(reset)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'bold_red',
                }
            )
            console_handler.setFormatter(formatter)
        except ImportError:
            # Fallback to standard formatter if colorlog not available
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(formatter)
        sqlalchemy_engine_logger.addHandler(console_handler)
        print(f"[LOG CONFIG] Added console handler to sqlalchemy.engine logger")

    # Double-check sqlalchemy.engine level and handler level
    sqlalchemy_engine_logger.setLevel(target_level)
    for handler in sqlalchemy_engine_logger.handlers:
        handler.setLevel(target_level)
    print(f"[LOG CONFIG] Verified sqlalchemy.engine logger: level={logging.getLevelName(sqlalchemy_engine_logger.level)}, handlers={len(sqlalchemy_engine_logger.handlers)}")


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

    # Configure log levels based on settings (override YAML defaults)
    configure_log_levels_from_settings(settings)

    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.debug("=== DEBUG LOGGING TEST ===")
    logger.debug("If you see this message, debug logging is working correctly!")

    # Initialize database
    debug_print("About to initialize database...")
    logger.info("Initializing database connection...")

    # NOTE: SQLAlchemy logging is now configured in configure_log_levels_from_settings()
    # No need to set it here again

    debug_print("About to call init_db()...")
    await init_db()
    debug_print("init_db() completed")
    logger.info("Database connection established")

    # Start event publisher (Kafka producer)
    from .infrastructure.dependency_injection import get_container
    container = get_container()
    try:
        await container.start_event_publisher()
        debug_print("Event publisher started")
        logger.info("Event publisher started successfully")
    except Exception as e:
        debug_print(f"Failed to start event publisher: {e}")
        # Non-critical: Continue startup even if Kafka fails
        logger.warning(f"Event publisher failed to start: {e}", exc_info=True)

    # Initialize TTS adapter at startup (prevents first-use delay)
    # This eliminates ~12 second delay on first question generation
    debug_print("Initializing TTS adapter at startup...")
    logger.info("Initializing TTS adapter at startup (to prevent first-use delay)...")
    try:
        await container.start_tts_adapter()
        logger.info("TTS adapter initialized successfully at startup")
        debug_print("TTS adapter initialized at startup")
    except Exception as e:
        # Log warning but don't fail startup - TTS will be created lazily on first request
        logger.warning(
            f"Failed to initialize TTS adapter at startup: {e}. "
            "TTS adapter will be created lazily on first request. "
            "This may cause a delay (~12s) on the first TTS call.",
            exc_info=True
        )
        debug_print(f"TTS adapter initialization failed at startup: {e}")

    # Start candidate event consumer in background (non-blocking)
    candidate_consumer = None
    consumer_task = None
    try:
        candidate_consumer = container.candidate_event_consumer()
        await candidate_consumer.start()
        import asyncio as _asyncio

        consumer_task = _asyncio.create_task(candidate_consumer.consume_events())
        logger.info("Candidate event consumer started successfully")
    except Exception as e:
        logger.warning(
            f"Failed to start candidate event consumer: {e}. "
            "Candidate delete events will not be processed until this is fixed.",
            exc_info=True,
        )

    # Optionally initialize LangGraph checkpointer at startup
    # This prevents first-request timeouts when the feature is enabled
    if settings.langgraph_checkpointer_init_on_startup:
        debug_print("Initializing LangGraph checkpointer at startup...")
        logger.info("Initializing LangGraph checkpointer at startup (to prevent first-request timeout)...")
        try:
            from .infrastructure.dependency_injection import get_container
            container = get_container()
            checkpointer = await container.get_checkpointer()
            logger.info("LangGraph checkpointer initialized successfully at startup")
            debug_print("Checkpointer initialized at startup")
        except Exception as e:
            # Log warning but don't fail startup - checkpointer will be created lazily on first request
            logger.warning(
                f"Failed to initialize LangGraph checkpointer at startup: {e}. "
                "Checkpointer will be created lazily on first request. "
                "This may cause a delay on the first request that uses the checkpointer.",
                exc_info=True
            )
            debug_print(f"Checkpointer initialization failed at startup: {e}")

    debug_print("lifespan startup complete, yielding...")
    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Stop event publisher (flush pending messages)
    from .infrastructure.dependency_injection import get_container
    container = get_container()
    try:
        await container.stop_event_publisher()
        debug_print("Event publisher stopped")
        logger.info("Event publisher stopped successfully")
    except Exception as e:
        debug_print(f"Error stopping event publisher: {e}")
        logger.warning(f"Error stopping event publisher: {e}", exc_info=True)

    # Stop candidate event consumer if it was started
    try:
        if candidate_consumer is not None:
            await candidate_consumer.stop()
        if consumer_task is not None:
            import asyncio as _asyncio

            consumer_task.cancel()
            with contextlib.suppress(Exception):
                await consumer_task
        logger.info("Candidate event consumer stopped")
    except Exception as e:
        logger.warning(f"Error stopping candidate event consumer: {e}", exc_info=True)

    try:
        await container.stop_checkpointer_heartbeat()
    except Exception as e:
        logger.warning(f"Error stopping checkpointer heartbeat: {e}", exc_info=True)

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

    # Exception logging middleware (must be first to catch all exceptions)
    class ExceptionLoggingMiddleware(BaseHTTPMiddleware):
        """Middleware to catch and log all exceptions at ASGI level."""
        async def dispatch(self, request: StarletteRequest, call_next):
            try:
                response = await call_next(request)
                return response
            except Exception as exc:
                import traceback

                # Log the full exception with traceback
                logger.error(
                    f"ASGI-level exception: {type(exc).__name__}: {exc}",
                    exc_info=True,
                    extra={
                        "path": str(request.url.path),
                        "method": request.method,
                        "query_params": str(request.query_params),
                    }
                )

                # Print to stderr for immediate visibility (useful in Docker logs)
                print(f"\n{'='*80}", file=sys.stderr, flush=True)
                print(f"ASGI ERROR: Exception in {request.method} {request.url.path}", file=sys.stderr, flush=True)
                print(f"Exception type: {type(exc).__name__}", file=sys.stderr, flush=True)
                print(f"Exception message: {exc}", file=sys.stderr, flush=True)
                print(f"\nFull traceback:", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)
                print(f"{'='*80}\n", file=sys.stderr, flush=True)

                # Re-raise to let FastAPI's exception handler process it
                raise

    app.add_middleware(ExceptionLoggingMiddleware)

    # Auth middleware (after exception logging, before CORS)
    app.add_middleware(
        AuthMiddleware,
        role_header_name=settings.auth_role_header_name,
        user_id_header_name=settings.auth_user_id_header_name,
        role_prefix=settings.auth_role_prefix,
        allowed_roles=settings.auth_allowed_roles,
    )

    # CORS middleware (after auth)
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
    app.include_router(
        prompt_router, prefix=settings.api_prefix, tags=["Prompt Management"]
    )
    app.include_router(
        feedback_router, prefix=settings.api_prefix, tags=["Feedback"]
    )
    app.include_router(
        question_router, prefix=settings.api_prefix, tags=["Questions"]
    )

    # WebSocket endpoint for real-time interview
    @app.websocket("/ws/interviews/{interview_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        interview_id: UUID,
    ):
        """WebSocket endpoint for real-time interview communication."""
        await handle_interview_websocket(websocket, interview_id)

    # Global exception handler to catch and log all unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch all unhandled exceptions and log them with full context."""
        import traceback

        # Log the full exception with traceback
        logger.error(
            f"Unhandled exception in ASGI application: {type(exc).__name__}: {exc}",
            exc_info=True,
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "query_params": str(request.query_params),
            }
        )

        # Print to stderr for immediate visibility (useful in Docker logs)
        print(f"\n{'='*80}", file=sys.stderr, flush=True)
        print(f"ERROR: Unhandled exception in {request.method} {request.url.path}", file=sys.stderr, flush=True)
        print(f"Exception type: {type(exc).__name__}", file=sys.stderr, flush=True)
        print(f"Exception message: {exc}", file=sys.stderr, flush=True)
        print(f"\nFull traceback:", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr, flush=True)

        # Return a generic error response (don't expose internal details in production)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_type": type(exc).__name__,
            }
        )

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
