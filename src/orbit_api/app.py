"""FastAPI application for Orbit REST API."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import PlainTextResponse
from starlette.types import ExceptionHandler

from memory_engine.config import EngineConfig
from orbit.logger import configure_logging, get_logger
from orbit.models import (
    AuthValidationResponse,
    FeedbackBatchRequest,
    FeedbackBatchResponse,
    FeedbackRequest,
    FeedbackResponse,
    IngestBatchRequest,
    IngestBatchResponse,
    IngestRequest,
    IngestResponse,
    PaginatedMemoriesResponse,
    RetrieveRequest,
    RetrieveResponse,
    StatusResponse,
    TimeRange,
)
from orbit_api.auth import AuthContext, require_auth_context
from orbit_api.config import ApiConfig
from orbit_api.service import OrbitApiService, RateLimitExceededError, RateLimitSnapshot
from orbit_api.telemetry import configure_telemetry

_security = HTTPBearer(auto_error=False)


def create_app(
    api_config: ApiConfig | None = None,
    engine_config: EngineConfig | None = None,
) -> FastAPI:
    config = api_config or ApiConfig.from_env()
    configure_logging()
    log = get_logger("orbit.api")

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
        yield
        service = _service_from_app(app_instance)
        service.close()

    app = FastAPI(
        title="Orbit API",
        version=config.api_version,
        description="Memory infrastructure API for developer applications.",
        lifespan=lifespan,
    )
    app.state.orbit_service = OrbitApiService(
        api_config=config,
        engine_config=engine_config,
    )

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[config.per_minute_limit],
        headers_enabled=True,
    )
    app.state.limiter = limiter
    app.state.rate_limit = config.per_minute_limit
    app.add_exception_handler(
        RateLimitExceeded,
        cast(ExceptionHandler, _rate_limit_exceeded_handler),
    )
    app.add_middleware(SlowAPIMiddleware)

    configure_telemetry(app, config)

    limit = limiter.limit

    def get_service() -> OrbitApiService:
        return _service_from_app(app)

    def get_auth_context(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_security)],
        service: Annotated[OrbitApiService, Depends(get_service)],
    ) -> AuthContext:
        context = require_auth_context(credentials=credentials, config=service.config)
        request.state.auth_context = context
        return context

    @app.post(
        "/v1/ingest",
        response_model=IngestResponse,
        status_code=status.HTTP_201_CREATED,
    )
    @limit(config.per_minute_limit)
    def ingest_endpoint(
        payload: IngestRequest,
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> IngestResponse:
        snapshot = _consume_or_raise(
            service.consume_event_quota,
            account_key=auth.subject,
            amount=1,
        )
        result = service.ingest(payload)
        _apply_rate_headers(response, snapshot)
        log.info(
            "ingest",
            account=auth.subject,
            memory_id=result.memory_id,
            stored=result.stored,
            path=str(request.url.path),
        )
        return result

    @app.get("/v1/retrieve", response_model=RetrieveResponse)
    @limit(config.per_minute_limit)
    def retrieve_endpoint(
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
        query: Annotated[str, Query(min_length=1)],
        limit_count: Annotated[int, Query(alias="limit", ge=1, le=100)] = 10,
        entity_id: str | None = None,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> RetrieveResponse:
        snapshot = _consume_or_raise(
            service.consume_query_quota,
            account_key=auth.subject,
            amount=1,
        )
        retrieve_request = RetrieveRequest(
            query=query,
            limit=limit_count,
            entity_id=entity_id,
            event_type=event_type,
            time_range=_build_time_range(start_time, end_time),
        )
        result = service.retrieve(retrieve_request)
        _apply_rate_headers(response, snapshot)
        log.info(
            "retrieve",
            account=auth.subject,
            returned=len(result.memories),
            path=str(request.url.path),
        )
        return result

    @app.post("/v1/feedback", response_model=FeedbackResponse)
    @limit(config.per_minute_limit)
    def feedback_endpoint(
        payload: FeedbackRequest,
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> FeedbackResponse:
        snapshot = _consume_or_raise(
            service.consume_event_quota,
            account_key=auth.subject,
            amount=1,
        )
        try:
            result = service.feedback(payload)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        _apply_rate_headers(response, snapshot)
        log.info(
            "feedback",
            account=auth.subject,
            memory_id=result.memory_id,
            path=str(request.url.path),
        )
        return result

    @app.post("/v1/ingest/batch", response_model=IngestBatchResponse)
    @limit(config.per_minute_limit)
    def ingest_batch_endpoint(
        payload: IngestBatchRequest,
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> IngestBatchResponse:
        snapshot = _consume_or_raise(
            service.consume_event_quota,
            account_key=auth.subject,
            amount=len(payload.events),
        )
        items = service.ingest_batch(payload.events)
        _apply_rate_headers(response, snapshot)
        log.info(
            "ingest_batch",
            account=auth.subject,
            count=len(items),
            path=str(request.url.path),
        )
        return IngestBatchResponse(items=items)

    @app.post("/v1/feedback/batch", response_model=FeedbackBatchResponse)
    @limit(config.per_minute_limit)
    def feedback_batch_endpoint(
        payload: FeedbackBatchRequest,
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> FeedbackBatchResponse:
        snapshot = _consume_or_raise(
            service.consume_event_quota,
            account_key=auth.subject,
            amount=len(payload.feedback),
        )
        try:
            items = service.feedback_batch(payload.feedback)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        _apply_rate_headers(response, snapshot)
        log.info(
            "feedback_batch",
            account=auth.subject,
            count=len(items),
            path=str(request.url.path),
        )
        return FeedbackBatchResponse(items=items)

    @app.get("/v1/status", response_model=StatusResponse)
    def status_endpoint(
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> StatusResponse:
        return service.status(auth.subject)

    @app.get("/v1/health")
    def health_endpoint(
        service: Annotated[OrbitApiService, Depends(get_service)],
    ) -> dict[str, str]:
        return service.health()

    @app.get("/v1/metrics", response_class=PlainTextResponse)
    def metrics_endpoint(
        service: Annotated[OrbitApiService, Depends(get_service)],
    ) -> str:
        return service.metrics_text()

    @app.post("/v1/auth/validate", response_model=AuthValidationResponse)
    def validate_endpoint(
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthValidationResponse:
        return service.validate_token(auth)

    @app.get("/v1/memories", response_model=PaginatedMemoriesResponse)
    @limit(config.per_minute_limit)
    def list_memories_endpoint(
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
        limit_count: Annotated[int, Query(alias="limit", ge=1, le=100)] = 100,
        cursor: str | None = None,
    ) -> PaginatedMemoriesResponse:
        snapshot = _consume_or_raise(
            service.consume_query_quota,
            account_key=auth.subject,
            amount=1,
        )
        result = service.list_memories(limit=limit_count, cursor=cursor)
        _apply_rate_headers(response, snapshot)
        log.info(
            "list_memories",
            account=auth.subject,
            count=len(result.data),
            path=str(request.url.path),
        )
        return result

    return app


def _service_from_app(app: FastAPI) -> OrbitApiService:
    service = getattr(app.state, "orbit_service", None)
    if not isinstance(service, OrbitApiService):
        msg = "Orbit service not initialized"
        raise RuntimeError(msg)
    return service


def _build_time_range(
    start_time: datetime | None,
    end_time: datetime | None,
) -> TimeRange | None:
    if start_time is None and end_time is None:
        return None
    resolved_start = start_time or datetime.fromtimestamp(0, tz=UTC)
    resolved_end = end_time or datetime.now(UTC)
    return TimeRange(start=resolved_start, end=resolved_end)


def _apply_rate_headers(response: Response, snapshot: RateLimitSnapshot) -> None:
    for key, value in snapshot.as_headers().items():
        response.headers[key] = value


def _consume_or_raise(
    consume_fn: Callable[..., RateLimitSnapshot],
    account_key: str,
    amount: int,
) -> RateLimitSnapshot:
    try:
        return consume_fn(account_key=account_key, amount=amount)
    except RateLimitExceededError as exc:
        headers = {
            **exc.snapshot.as_headers(),
            "Retry-After": str(exc.retry_after_seconds),
        }
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
            headers=headers,
        ) from exc
