import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.db.session import SessionLocal
from app.services.lifecycle_service import LifecycleService

logger = logging.getLogger("lifeos.lifecycle")

HOUSEKEEPING_INTERVAL_SECONDS = 60


def _run_housekeeping() -> None:
    """Silent cleanup of calendar events for already-resolved tasks."""
    session = SessionLocal()

    try:
        removed = LifecycleService(session).cleanup_stale_calendar_events()

        if removed:
            session.commit()
            logger.info("Removed stale calendar events: %s", removed)

    except Exception:
        session.rollback()
        logger.exception("Lifecycle housekeeping failed")

    finally:
        session.close()


async def _housekeeping_loop() -> None:
    while True:
        await asyncio.to_thread(_run_housekeeping)
        await asyncio.sleep(HOUSEKEEPING_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_housekeeping_loop())

    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="LIFEOS",
    description="Agentic Personal Operating System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    router,
    prefix="/api",
)


@app.get("/")
def root():
    return {
        "name": "LIFEOS",
        "version": "0.1.0",
        "status": "running",
    }