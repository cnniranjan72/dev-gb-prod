from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.auth_routes import router as auth_router
from .api.routes import router
from .api.state import set_dataset
from .core.config import settings
from .services.datasource import resolve_dataset


logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("windlens")

DESCRIPTION = """
WindLens serves UK national wind-generation analytics for day-ahead procurement
review. Data: Elexon BMRS FUELHH (actual wind, WIND) and WINDFOR (wind
forecasts). See /api/metadata for the dataset snapshot provenance and the
analysis-period facts.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .api.state import DatasetState

    if DatasetState.instance is not None:
        logger.info("dataset already injected (tests); skipping lifespan load")
        yield
        return
    logger.info("loading dataset (mode=%s)...", settings.data_mode)
    dataset = resolve_dataset(settings)
    set_dataset(dataset)
    logger.info(
        "dataset loaded: actuals=%d forecast_vintages=%d period=%s..%s",
        len(dataset.actuals),
        sum(len(v) for v in dataset.forecasts_by_hour_end.values()),
        dataset.period_start.date(),
        dataset.period_end.date(),
    )
    yield
    from .api.state import DatasetState

    if DatasetState.instance is dataset:
        DatasetState.instance = None


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan, description=DESCRIPTION)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(router)
app.include_router(auth_router)


def main() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
