"""
Production-ready FastAPI application for railway optimization system.

Orchestrates:
- Database initialization and connection pooling
- Service setup (PredictionService model training, etc.)
- Middleware and CORS configuration
- Route registration
- Lifespan events (startup/shutdown)
- Logging configuration

Features:
- Docker-ready with environment variable configuration
- Proper connection pooling and session management
- Graceful startup/shutdown
- Request tracing and logging
- CORS for frontend communication
- Health check endpoint
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings, configure_logging
from app.models import Base
from app.apis.routes import router, get_db_session as routes_get_db_session
from app.services import PredictionService
from app.repositories import TrainRepository, SectionRepository


# ============================================================================
# Global Configuration
# ============================================================================

logger = logging.getLogger(__name__)

# Global engine and session factory - initialized during startup
engine = None
SessionLocal = None


# ============================================================================
# Lifespan Events
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown events.

    Startup:
    - Initialize database engine
    - Create tables
    - Train PredictionService models

    Shutdown:
    - Close database engine
    """
    global engine, SessionLocal

    settings = get_settings()

    # ========== STARTUP ==========
    logger.info("Starting FastAPI application...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log level: {settings.log_level}")

    # --- Config validation: fail fast on missing essentials ---
    database_url = settings.database_url or _parse_database_url(settings.supabase_url)
    if not database_url:
        raise RuntimeError(
            "No database configured. Set DATABASE_URL or SUPABASE_URL in your .env file. "
            "See .env.example for reference."
        )

    try:
        # 1. Database Engine Setup
        logger.info("Initializing database engine...")

        logger.debug(f"Database URL: {database_url}")

        # Create engine with connection pooling
        if database_url.startswith("postgresql"):
            # Supabase free tier has a hard limit of ~10 connections in session mode.
            # With hot-reload and multiple services, we must keep the pool very small.
            # pool_size=3: max 3 persistent connections (well under the 10-connection limit)
            # max_overflow=2: allow 2 extra temporary connections under load
            # pool_recycle=300: close and replace connections older than 5 minutes
            #   to prevent stale connections after hot-reloads or network blips
            # pool_pre_ping=True: test connection health before using from pool
            engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=3,
                max_overflow=2,
                pool_recycle=300,
                pool_pre_ping=True,
                echo=False,
            )
        else:
            # Testing/Development: SQLite with StaticPool
            from sqlalchemy.pool import StaticPool
            engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False,
            )

        # Create session factory
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )

        logger.info("Database engine initialized")

        # 2. Create Tables
        logger.info("Creating database tables...")
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.warning(f"Could not create/verify tables (DB may be unreachable): {e}")
            logger.warning("Server will start but DB operations will fail until connection is restored")

        # 3. Verify Database Connection
        logger.info("Verifying database connection...")
        try:
            with SessionLocal() as session:
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                logger.info(f"Database connected. Tables found: {tables}")
                logger.info(f"Number of tables: {len(tables)}")
        except SQLAlchemyError as e:
            logger.warning(f"Database connection check failed: {e}")
            logger.warning("Server starting without confirmed DB connection")

        # 4. Override Dependency Injection
        logger.info("Configuring dependency injection...")
        _setup_dependency_overrides(app)
        logger.info("Dependency injection configured")

        # 5. Initialize PredictionService Models (Optional - can be slow)
        logger.info("Initializing PredictionService models...")
        try:
            _initialize_prediction_models()
            logger.info("PredictionService models initialized")
        except Exception as e:
            # Log warning but don't fail startup - models can be trained on first use
            logger.warning(f"PredictionService model initialization deferred: {e}")

        logger.info("Application startup complete")

        yield  # Application runs here

        # ========== SHUTDOWN ==========
        logger.info("Shutting down application...")

        if engine:
            logger.info("Closing database connections...")
            engine.dispose()
            logger.info("Database connections closed")

        logger.info("Application shutdown complete")

    except Exception as e:
        logger.critical(f"Fatal error during app initialization: {e}", exc_info=True)
        raise


# ============================================================================
# Database Configuration Functions
# ============================================================================

def _parse_database_url(supabase_url: str) -> str:
    """
    Parse Supabase URL to PostgreSQL connection string.

    Input: https://cxovemicthldzvtqaevt.supabase.co
    Output: postgresql://user:password@host:port/database

    For testing, supports:
    Input: sqlite:///path/to/db.sqlite
    Output: sqlite:///path/to/db.sqlite
    """
    # If already a database URL, return as-is
    if supabase_url.startswith(("sqlite://", "postgresql://", "postgresql+psycopg2://")):
        return supabase_url

    # Otherwise, construct PostgreSQL URL from Supabase
    # Default Supabase PostgreSQL: host:5432/postgres
    # In production, would parse and construct properly
    # For now, return as-is (requires proper environment setup)

    if supabase_url.startswith("https://"):
        # Extract project ID from URL
        project_id = supabase_url.replace("https://", "").replace(".supabase.co", "")

        # Default PostgreSQL connection
        # In production, use proper credentials
        return (
            f"postgresql+psycopg2://postgres.{project_id}:password@"
            f"{project_id}.supabase.co:5432/postgres"
        )

    # Fallback: use as-is
    return supabase_url


def _setup_dependency_overrides(app: FastAPI) -> None:
    """
    Override FastAPI dependencies to use app-level database engine and session.

    This allows the dependency injection in routes.py to use the persistent
    engine created during startup instead of creating a new one per request.
    """

    def get_db_session_override() -> Session:
        """
        Database session dependency that uses the app-level engine.
        Properly manages session lifecycle with try/finally.
        """
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    # Override the get_db_session dependency from routes
    app.dependency_overrides[routes_get_db_session] = get_db_session_override


def _initialize_prediction_models() -> None:
    """
    Initialize PredictionService models during startup.

    This is optional and can be deferred to first use if startup time is critical.
    Models train on first prediction call if not pre-trained.
    """
    try:
        # Create a temporary session for initialization
        with SessionLocal() as session:
            train_repo = TrainRepository(session)
            section_repo = SectionRepository(session)

            # Create models directory
            models_dir = Path("./models")
            models_dir.mkdir(exist_ok=True)

            # Initialize PredictionService
            predictor = PredictionService(
                train_repo,
                section_repo,
                model_dir=models_dir,
            )

            # Check if models exist
            delay_model_path = models_dir / "delay_regressor.pkl"

            # Train models if they don't exist (optional)
            # Uncomment to train on startup
            # if not delay_model_path.exists():
            #     logger.info("Training PredictionService models (this may take a moment)...")
            #     predictor.train_models()
            #     logger.info("PredictionService models trained")

            logger.debug("PredictionService initialized")

    except Exception as e:
        # Log but don't fail - models train on first use
        logger.debug(f"Could not pre-initialize models: {e}")


# ============================================================================
# Middleware Functions
# ============================================================================

class RequestIDMiddleware:
    """Middleware to add request tracing with unique IDs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope["request_id"] = request_id

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_header)


async def request_logging_middleware(request: Request, call_next):
    """Middleware to log all HTTP requests and responses."""
    request_id = request.scope.get("request_id", "unknown")

    # Log request
    logger.debug(
        f"[{request_id}] {request.method} {request.url.path} "
        f"| Client: {request.client.host if request.client else 'unknown'}"
    )

    response = await call_next(request)

    # Log response
    logger.debug(
        f"[{request_id}] {request.method} {request.url.path} "
        f"| Status: {response.status_code}"
    )

    return response


async def error_handling_middleware(request: Request, call_next):
    """Middleware to handle and log errors gracefully."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(
            f"!!! UNHANDLED EXCEPTION for {request.method} {request.url.path}: {str(e)}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "exception": str(e),
                "type": type(e).__name__
            },
        )


# ============================================================================
# Utility Functions (must be defined before app creation)
# ============================================================================

def _get_cors_origins(settings) -> list:
    """
    Get CORS origins based on environment.

    Development: Allow localhost and 127.0.0.1
    Production: Restrict to specific domains (from settings if available)
    """
    if settings.environment == "development":
        return [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://localhost:5173",  # Vite default
            "http://localhost:8080",  # Vue default
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:3002",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
        ]
    else:
        # Production: restrict to known domains
        # Can be configured via CORS_ORIGINS environment variable
        return [
            "https://yourdomain.com",
        ]


# ============================================================================
# FastAPI App Creation
# ============================================================================

# Configure logging first
settings = get_settings()
configure_logging(settings)

# Create FastAPI app with lifespan
app = FastAPI(
    title="Railway Optimization System",
    description="Production-grade railway schedule optimization and conflict resolution",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


# ============================================================================
# Middleware Setup (order matters - applied bottom to top)
# ============================================================================

# Error handling (innermost) - wrap async function with BaseHTTPMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=error_handling_middleware)

# Request logging
app.add_middleware(BaseHTTPMiddleware, dispatch=request_logging_middleware)

# Gzip compression
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)

# CORS (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(settings),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)


# ============================================================================
# Route Registration
# ============================================================================

app.include_router(
    router,
    prefix="",
    tags=["railway-control"],
)

logger.info(f"Routes registered: {len(app.routes)} routes")


# ============================================================================
# Health Check Endpoint (Fallback - also in routes)
# ============================================================================

@app.get("/health/live", tags=["health"])
async def health_live():
    """Kubernetes-compatible liveness probe."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
async def health_ready():
    """Kubernetes-compatible readiness probe."""
    try:
        # Quick database check
        if SessionLocal:
            with SessionLocal() as session:
                from sqlalchemy import text as _text
                session.execute(_text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)},
        )


# ============================================================================
# Application Info
# ============================================================================

logger.info(
    f"FastAPI app created: {app.title} v{app.version} | "
    f"Environment: {settings.environment}"
)

 
