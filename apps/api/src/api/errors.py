"""RFC 7807 problem+json error handling and domain error → HTTP mapping."""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from studio_core.credits import InsufficientCredits
from studio_core.generation import (
    ConcurrencyLimitError,
    GenerationServiceError,
    IdempotencyConflictError,
    InvalidParamsError,
    MissingInputError,
    ModelTaskMismatchError,
    PermissionDeniedError,
)
from studio_core.observability import capture_exception


def problem_response(
    status: int,
    error_code: str,
    detail: str,
    request: Request | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a RFC 7807 problem+json response."""
    body: dict[str, Any] = {
        "type": f"https://studio.example.com/errors/{error_code.lower()}",
        "title": error_code.replace("_", " ").title(),
        "status": status,
        "detail": detail,
        "error_code": error_code,
    }
    if request is not None:
        body["instance"] = str(request.url)
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach domain exception → HTTP status code mappings to the app."""

    @app.exception_handler(PermissionDeniedError)
    async def handle_permission_denied(
        request: Request, exc: PermissionDeniedError
    ) -> JSONResponse:
        return problem_response(403, exc.code, exc.message, request)

    @app.exception_handler(ModelTaskMismatchError)
    async def handle_model_task_mismatch(
        request: Request, exc: ModelTaskMismatchError
    ) -> JSONResponse:
        return problem_response(422, exc.code, exc.message, request)

    @app.exception_handler(InvalidParamsError)
    async def handle_invalid_params(request: Request, exc: InvalidParamsError) -> JSONResponse:
        return problem_response(422, exc.code, exc.message, request)

    @app.exception_handler(MissingInputError)
    async def handle_missing_input(request: Request, exc: MissingInputError) -> JSONResponse:
        return problem_response(422, exc.code, exc.message, request)

    @app.exception_handler(InsufficientCredits)
    async def handle_insufficient_credits(
        request: Request, exc: InsufficientCredits
    ) -> JSONResponse:
        return problem_response(402, "INSUFFICIENT_CREDITS", str(exc), request)

    @app.exception_handler(ConcurrencyLimitError)
    async def handle_concurrency_limit(
        request: Request, exc: ConcurrencyLimitError
    ) -> JSONResponse:
        return problem_response(429, exc.code, exc.message, request)

    @app.exception_handler(IdempotencyConflictError)
    async def handle_idempotency_conflict(
        request: Request, exc: IdempotencyConflictError
    ) -> JSONResponse:
        return problem_response(409, exc.code, exc.message, request)

    @app.exception_handler(GenerationServiceError)
    async def handle_generation_service_error(
        request: Request, exc: GenerationServiceError
    ) -> JSONResponse:
        # Catch-all for other domain errors — default to 422
        status = 404 if exc.code == "PROJECT_NOT_FOUND" else 422
        if exc.code == "MODEL_NOT_FOUND":
            status = 404
        return problem_response(status, exc.code, exc.message, request)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            # Already formatted as problem detail or custom dict
            content = dict(exc.detail)
            if "status" not in content:
                content["status"] = exc.status_code
            if "type" not in content:
                code = content.get("error_code", "ERROR")
                content["type"] = f"https://studio.example.com/errors/{str(code).lower()}"
            if "title" not in content:
                content["title"] = str(content.get("error_code", "Error")).replace("_", " ").title()
            if "detail" not in content:
                content["detail"] = str(exc.detail)
            if "error_code" not in content:
                content["error_code"] = "HTTP_ERROR"
            content["instance"] = str(request.url)
            return JSONResponse(
                status_code=exc.status_code,
                content=content,
                media_type="application/problem+json",
                headers=exc.headers,
            )
        error_code = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            422: "UNPROCESSABLE_ENTITY",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_SERVER_ERROR",
            503: "SERVICE_UNAVAILABLE",
        }.get(exc.status_code, "HTTP_ERROR")
        return problem_response(
            status=exc.status_code,
            error_code=error_code,
            detail=str(exc.detail),
            request=request,
        )

    @app.exception_handler(404)
    async def handle_not_found(request: Request, exc: Any) -> JSONResponse:
        return problem_response(404, "NOT_FOUND", "The requested resource was not found.", request)

    @app.exception_handler(405)
    async def handle_method_not_allowed(request: Request, exc: Any) -> JSONResponse:
        return problem_response(
            405, "METHOD_NOT_ALLOWED", "HTTP method not allowed for this endpoint.", request
        )

    @app.exception_handler(500)
    async def handle_internal_error(request: Request, exc: Any) -> JSONResponse:
        if isinstance(exc, Exception):
            capture_exception(
                exc,
                request_id=getattr(request.state, "request_id", None),
                path=request.url.path,
                method=request.method,
                user_id=getattr(request.state, "user_id", None),
            )
        return problem_response(
            500, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", request
        )
