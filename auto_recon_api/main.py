from __future__ import annotations

from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from redis.asyncio import Redis
from starlette.exceptions import HTTPException as StarletteHTTPException

from auto_recon_api.api.v1.api import api_router
from auto_recon_api.core.config import get_settings
from auto_recon_api.core.logging import configure_logging
from auto_recon_api.db.session import close_engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    app.state.settings = settings

    redis = Redis(
        host='redis',
        port=6379,
        db=0,
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    await redis.ping()

    await FastAPILimiter.init(redis, prefix='recon:rl')
    try:
        yield
    finally:
        await close_engine()
        await redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title='Auto Recon API',
        version='0.1.0',
        lifespan=lifespan,
        docs_url=None if settings.ENV == 'prod' else '/docs',
        redoc_url=None if settings.ENV == 'prod' else '/redoc',
        openapi_url=None if settings.ENV == 'prod' else '/openapi.json',
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
        expose_headers=['X-Request-Id'],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ):
        message = (
            exc.detail if isinstance(exc.detail, str) else 'Request error'
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                'code': 'http_error',
                'message': message,
                'details': exc.detail if not isinstance(
                    exc.detail, str
                ) else None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                'code': 'validation_error',
                'message': 'Invalid input',
                'details': exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={
                'code': 'internal_error',
                'message': 'Internal server error',
            },
        )

    app.include_router(api_router, prefix='/api/v1')
    return app


app = create_app()
