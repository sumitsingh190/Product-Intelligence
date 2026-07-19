import time
import uuid
from contextlib import asynccontextmanager

import structlog
import app.models  # Register all ORM models before request handling
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import api_router
from app.config import settings
from app.utils.logging import configure_logging

configure_logging()
log=structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", app=settings.app_name, version=settings.app_version, env=settings.app_env)
    #Verify database connectivity
    from app.database import engine
    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    log.info("database_connected")

    #Verify Redis connectivity
    try:
        from redis.asyncio import Redis
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        await redis.aclose()
        log.info("redis_connected")
    except Exception as exc:  # noqa: BLE001
        log.warning("redis_connectivity_check_failed", error=str(exc))
    
    #Initialize DuckDB analytics schema (idempotent; safe on every boot)
    try:
        from app.analytics.duckdb_manager import initialize_schema
        initialize_schema()
    except Exception as e: # noqa: BLE001
        log.warning("duckdb_init_failed", error=str(e))

    yield

    log.info("shutdown")
    await engine.dispose()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous Product Operating System API",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

# CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    @app.middleware("http")
    async def request_id_nodleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()
        
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000    

        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        
        response.headers["X-Request-ID"] = request_id
        return response


        #Prometheus metrics
    if settings.prometheus_enabled:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")

        #OpenTelemetry instrumentation
    if settings.otel_enabled:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            from app.database import engine as _db_engine
            SQLAlchemyInstrumentor().instrument(engine=_db_engine.sync_engine)
        except Exception as e: # noqa: BLE001
            log.warning("otel_sqlalchemy_instrument_failed", error=str(e))
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor 
            RedisInstrumentor().instrument()
        except Exception as e: # noqa> BLE001
            log.warning("otel_redis_instrument_failed", error=str(e))

    #API router
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    #Health check
    @app.get("/health", tags=["Health"])
    async def health():
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
        }
    
    @app.get("/", tags=["Root"])
    async def root():
        return {"message": f"Welcome to {settings.app_name} API", "docs": "/docs"}

    #Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        log.error("unhandled_exception", exc_info=exc, path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    
    return app

app=create_app()