import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.training import router as training_router
from app.api.admin import router as admin_router
from app.grpc.server import serve_grpc
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import AegisHealthException

# Register persistence callback (import triggers registration)
import app.services.training_service  # noqa: F401

setup_logging()

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _allowed_cors_origins() -> list[str]:
    extra = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    return list(dict.fromkeys(_DEFAULT_CORS_ORIGINS + extra))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.services.fleet_sync import sync_fleet
        sync_fleet()
    except Exception:
        pass
    grpc_thread = threading.Thread(
        target=lambda: asyncio.run(serve_grpc(
            settings.grpc_port,
            tls_cert=settings.grpc_tls_cert,
            tls_key=settings.grpc_tls_key,
        )),
        daemon=True,
    )
    grpc_thread.start()
    yield


app = FastAPI(
    title="AegisHealth",
    description="Federated Learning Framework for Privacy-Preserving Health Anomaly Detection",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(training_router, prefix="/api/training", tags=["training"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.exception_handler(AegisHealthException)
async def aegis_exception_handler(_request: Request, exc: AegisHealthException) -> JSONResponse:
    """Map AegisHealth domain exceptions to HTTP responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.get("/api/health")
async def health_check():
    """Detailed health: orchestrator status, Supabase connectivity."""
    from app.schemas.common import HealthResponse

    orchestrator_ready = True
    supabase_connected = False
    try:
        from app.core.orchestrator import get_orchestrator
        get_orchestrator()
    except Exception:
        orchestrator_ready = False

    try:
        from app.db.supabase_client import get_supabase
        get_supabase().table("clients").select("id").limit(1).execute()
        supabase_connected = True
    except Exception:
        pass

    status = "healthy" if (orchestrator_ready and supabase_connected) else "degraded"
    return HealthResponse(
        status=status,
        service="aegishealth-orchestrator",
        orchestrator_ready=orchestrator_ready,
        supabase_connected=supabase_connected,
    )
