"""FastAPI application for Orbit REST API."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ExceptionHandler

from memory_engine.config import EngineConfig
from orbit.logger import configure_logging, get_logger
from orbit.models import (
    ApiKeyCreateRequest,
    ApiKeyIssueResponse,
    ApiKeyListResponse,
    ApiKeyRevokeResponse,
    ApiKeyRotateRequest,
    ApiKeyRotateResponse,
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
    PilotProRequestResponse,
    RetrieveRequest,
    RetrieveResponse,
    StatusResponse,
    TenantMetricsResponse,
    TimeRange,
)
from orbit_api.auth import AuthContext, require_auth_context
from orbit_api.config import ApiConfig
from orbit_api.service import (
    AccountMappingError,
    ApiKeyAuthenticationError,
    IdempotencyConflictError,
    OrbitApiService,
    PlanQuotaExceededError,
    RateLimitExceededError,
    RateLimitSnapshot,
)
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

    if config.cors_allow_origins:
        allow_origins = (
            ["*"] if any(item == "*" for item in config.cors_allow_origins) else config.cors_allow_origins
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset",
                "Retry-After",
                "X-Idempotency-Replayed",
                "X-Orbit-Error-Code",
            ],
        )

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[config.per_minute_limit],
        headers_enabled=True,
    )
    app.state.limiter = limiter
    app.state.rate_limit = config.per_minute_limit
    def slowapi_rate_limit_handler(
        request: Request,
        exc: RateLimitExceeded,
    ) -> JSONResponse:
        base_response = cast(
            JSONResponse,
            _rate_limit_exceeded_handler(request, exc),
        )
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": {
                    "message": "Too many requests. Retry after the rate-limit window resets.",
                    "error_code": "rate_limit_exceeded",
                }
            },
        )
        for key, value in base_response.headers.items():
            response.headers[key] = value
        response.headers["X-Orbit-Error-Code"] = "rate_limit_exceeded"
        return response

    app.add_exception_handler(
        RateLimitExceeded,
        cast(ExceptionHandler, slowapi_rate_limit_handler),
    )
    app.add_middleware(SlowAPIMiddleware)

    configure_telemetry(app, config)

    @app.middleware("http")
    async def observe_http_metrics(request: Request, call_next: Callable) -> Response:
        service = _service_from_app(app)
        try:
            response = await call_next(request)
        except Exception:  # pylint: disable=broad-exception-caught
            service.record_http_response(500)
            raise
        service.record_http_response(response.status_code)
        if (
            request.url.path.startswith("/v1/dashboard")
            and response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        ):
            service.record_dashboard_auth_failure()
        return response

    limit = limiter.limit

    def get_service() -> OrbitApiService:
        return _service_from_app(app)

    def get_auth_context(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_security)],
        service: Annotated[OrbitApiService, Depends(get_service)],
    ) -> AuthContext:
        if credentials is not None:
            bearer_token = credentials.credentials.strip()
            if bearer_token.startswith("orbit_pk_"):
                try:
                    context = service.authenticate_api_key(
                        bearer_token,
                        source=f"{request.method} {request.url.path}",
                    )
                except ApiKeyAuthenticationError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid API key.",
                    ) from exc
                request.state.auth_context = context
                return context
        context = require_auth_context(credentials=credentials, config=service.config)
        try:
            context = service.resolve_account_context(context)
        except AccountMappingError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        request.state.auth_context = context
        return context

    def _require_any_scope(auth: AuthContext, allowed_scopes: tuple[str, ...]) -> AuthContext:
        if "admin" in auth.scopes or "*" in auth.scopes:
            return auth
        if any(scope in auth.scopes for scope in allowed_scopes):
            return auth
        joined = ", ".join(allowed_scopes)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope. Need one of: {joined}",
        )

    def require_read_scope(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        return _require_any_scope(auth, ("read", "memory:read"))

    def require_write_scope(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        return _require_any_scope(auth, ("write", "memory:write"))

    def require_feedback_scope(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        return _require_any_scope(
            auth,
            ("feedback", "memory:feedback", "write", "memory:write"),
        )

    def require_keys_read_scope(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        return _require_any_scope(auth, ("keys:read", "read"))

    def require_keys_write_scope(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        return _require_any_scope(auth, ("keys:write", "write"))

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
        auth: Annotated[AuthContext, Depends(require_write_scope)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> IngestResponse:
        if len(payload.content) > config.max_ingest_content_chars:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"content exceeds ORBIT_MAX_INGEST_CONTENT_CHARS="
                    f"{config.max_ingest_content_chars}"
                ),
            )
        try:
            result, snapshot, replayed = service.ingest_with_quota(
                account_key=auth.subject,
                request=payload,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except IdempotencyConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except RateLimitExceededError as exc:
            raise _rate_limit_exception(exc) from exc
        _apply_rate_headers(response, snapshot)
        response.headers["X-Idempotency-Replayed"] = "true" if replayed else "false"
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
        auth: Annotated[AuthContext, Depends(require_read_scope)],
        query: Annotated[str, Query(min_length=1, max_length=config.max_query_chars)],
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
        result = service.retrieve(retrieve_request, account_key=auth.subject)
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
        auth: Annotated[AuthContext, Depends(require_feedback_scope)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> FeedbackResponse:
        try:
            result, snapshot, replayed = service.feedback_with_quota(
                account_key=auth.subject,
                request=payload,
                idempotency_key=idempotency_key,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except IdempotencyConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except RateLimitExceededError as exc:
            raise _rate_limit_exception(exc) from exc
        _apply_rate_headers(response, snapshot)
        response.headers["X-Idempotency-Replayed"] = "true" if replayed else "false"
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
        auth: Annotated[AuthContext, Depends(require_write_scope)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> IngestBatchResponse:
        if not payload.events:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="events batch cannot be empty",
            )
        if len(payload.events) > config.max_batch_items:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"events batch exceeds ORBIT_MAX_BATCH_ITEMS={config.max_batch_items}",
            )
        if any(
            len(item.content) > config.max_ingest_content_chars
            for item in payload.events
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"one or more events exceed ORBIT_MAX_INGEST_CONTENT_CHARS="
                    f"{config.max_ingest_content_chars}"
                ),
            )
        try:
            items, snapshot, replayed = service.ingest_batch_with_quota(
                account_key=auth.subject,
                events=payload.events,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except IdempotencyConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except RateLimitExceededError as exc:
            raise _rate_limit_exception(exc) from exc
        _apply_rate_headers(response, snapshot)
        response.headers["X-Idempotency-Replayed"] = "true" if replayed else "false"
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
        auth: Annotated[AuthContext, Depends(require_feedback_scope)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> FeedbackBatchResponse:
        if not payload.feedback:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="feedback batch cannot be empty",
            )
        if len(payload.feedback) > config.max_batch_items:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"feedback batch exceeds ORBIT_MAX_BATCH_ITEMS="
                    f"{config.max_batch_items}"
                ),
            )
        try:
            items, snapshot, replayed = service.feedback_batch_with_quota(
                account_key=auth.subject,
                feedback=payload.feedback,
                idempotency_key=idempotency_key,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except IdempotencyConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except RateLimitExceededError as exc:
            raise _rate_limit_exception(exc) from exc
        _apply_rate_headers(response, snapshot)
        response.headers["X-Idempotency-Replayed"] = "true" if replayed else "false"
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
        auth: Annotated[AuthContext, Depends(require_read_scope)],
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

    @app.get("/v1/tenant-metrics", response_model=TenantMetricsResponse)
    def tenant_metrics_endpoint(
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(require_read_scope)],
    ) -> TenantMetricsResponse:
        return service.tenant_metrics(auth.subject)

    @app.post("/v1/auth/validate", response_model=AuthValidationResponse)
    def validate_endpoint(
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthValidationResponse:
        return service.validate_token(auth)

    @app.post(
        "/v1/dashboard/pilot-pro/request",
        response_model=PilotProRequestResponse,
    )
    @limit(config.dashboard_key_per_minute_limit)
    def request_pilot_pro_endpoint(
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(require_keys_write_scope)],
    ) -> PilotProRequestResponse:
        response.headers["Cache-Control"] = "no-store"
        result = service.request_pilot_pro(
            account_key=auth.subject,
            actor_subject=_actor_subject(auth),
            actor_email=_actor_email(auth),
            actor_name=_actor_name(auth),
        )
        log.info(
            "request_pilot_pro",
            account=auth.subject,
            created=result.created,
            email_sent=result.email_sent,
            path=str(request.url.path),
        )
        return result

    @app.post(
        "/v1/dashboard/keys",
        response_model=ApiKeyIssueResponse,
        status_code=status.HTTP_201_CREATED,
    )
    @limit(config.dashboard_key_per_minute_limit)
    def issue_api_key_endpoint(
        payload: ApiKeyCreateRequest,
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(require_keys_write_scope)],
    ) -> ApiKeyIssueResponse:
        response.headers["Cache-Control"] = "no-store"
        try:
            result = service.issue_api_key(
                account_key=auth.subject,
                name=payload.name,
                scopes=payload.scopes,
                actor_subject=_actor_subject(auth),
            )
        except PlanQuotaExceededError as exc:
            raise _plan_quota_exception(exc) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        log.info(
            "issue_api_key",
            account=auth.subject,
            key_id=result.key_id,
            path=str(request.url.path),
        )
        return result

    @app.get("/v1/dashboard/keys", response_model=ApiKeyListResponse)
    @limit(config.dashboard_key_per_minute_limit)
    def list_api_keys_endpoint(
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(require_keys_read_scope)],
        limit_count: Annotated[int, Query(alias="limit", ge=1, le=100)] = 50,
        cursor: str | None = None,
    ) -> ApiKeyListResponse:
        response.headers["Cache-Control"] = "no-store"
        try:
            result = service.list_api_keys(
                account_key=auth.subject,
                limit=limit_count,
                cursor=cursor,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        log.info(
            "list_api_keys",
            account=auth.subject,
            count=len(result.data),
            path=str(request.url.path),
        )
        return result

    @app.post("/v1/dashboard/keys/{key_id}/revoke", response_model=ApiKeyRevokeResponse)
    @limit(config.dashboard_key_per_minute_limit)
    def revoke_api_key_endpoint(
        key_id: str,
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(require_keys_write_scope)],
    ) -> ApiKeyRevokeResponse:
        response.headers["Cache-Control"] = "no-store"
        try:
            result = service.revoke_api_key(
                account_key=auth.subject,
                key_id=key_id,
                actor_subject=_actor_subject(auth),
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        log.info(
            "revoke_api_key",
            account=auth.subject,
            key_id=result.key_id,
            path=str(request.url.path),
        )
        return result

    @app.post(
        "/v1/dashboard/keys/{key_id}/rotate",
        response_model=ApiKeyRotateResponse,
        status_code=status.HTTP_201_CREATED,
    )
    @limit(config.dashboard_key_per_minute_limit)
    def rotate_api_key_endpoint(
        key_id: str,
        payload: ApiKeyRotateRequest,
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(require_keys_write_scope)],
    ) -> ApiKeyRotateResponse:
        response.headers["Cache-Control"] = "no-store"
        try:
            result = service.rotate_api_key(
                account_key=auth.subject,
                key_id=key_id,
                name=payload.name,
                scopes=payload.scopes,
                actor_subject=_actor_subject(auth),
            )
        except KeyError as exc:
            service.record_dashboard_key_rotation_failure()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            service.record_dashboard_key_rotation_failure()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except Exception:
            service.record_dashboard_key_rotation_failure()
            raise
        log.info(
            "rotate_api_key",
            account=auth.subject,
            revoked_key_id=result.revoked_key_id,
            new_key_id=result.new_key.key_id,
            path=str(request.url.path),
        )
        return result

    @app.get("/v1/memories", response_model=PaginatedMemoriesResponse)
    @limit(config.per_minute_limit)
    def list_memories_endpoint(
        request: Request,
        response: Response,
        service: Annotated[OrbitApiService, Depends(get_service)],
        auth: Annotated[AuthContext, Depends(require_read_scope)],
        limit_count: Annotated[int, Query(alias="limit", ge=1, le=100)] = 100,
        cursor: str | None = None,
    ) -> PaginatedMemoriesResponse:
        snapshot = _consume_or_raise(
            service.consume_query_quota,
            account_key=auth.subject,
            amount=1,
        )
        result = service.list_memories(
            limit=limit_count,
            cursor=cursor,
            account_key=auth.subject,
        )
        _apply_rate_headers(response, snapshot)
        log.info(
            "list_memories",
            account=auth.subject,
            count=len(result.data),
            path=str(request.url.path),
        )
        return result

    return app


def _actor_subject(auth: AuthContext) -> str:
    raw = auth.claims.get("auth_subject")
    normalized = str(raw).strip() if raw is not None else ""
    return normalized or auth.subject


def _actor_email(auth: AuthContext) -> str | None:
    raw = auth.claims.get("email")
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    return normalized or None


def _actor_name(auth: AuthContext) -> str | None:
    raw = auth.claims.get("name")
    if raw is None:
        return None
    normalized = str(raw).strip()
    return normalized or None


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
        raise _rate_limit_exception(exc) from exc


def _rate_limit_exception(exc: RateLimitExceededError) -> HTTPException:
    headers = {
        **exc.snapshot.as_headers(),
        "Retry-After": str(exc.retry_after_seconds),
        "X-Orbit-Error-Code": exc.error_code,
    }
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "message": exc.detail,
            "error_code": exc.error_code,
        },
        headers=headers,
    )


def _plan_quota_exception(exc: PlanQuotaExceededError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "message": exc.detail,
            "error_code": exc.error_code,
        },
        headers={"X-Orbit-Error-Code": exc.error_code},
    )
