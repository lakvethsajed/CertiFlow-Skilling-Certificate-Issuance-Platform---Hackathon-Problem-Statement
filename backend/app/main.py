from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.routers.auth import router as auth_router
from app.routers.state import router as state_router
from app.routers.student_activation import router as student_activation_router
from app.routers.student_auth import router as student_auth_router
from app.routers.student_portal import router as student_portal_router
from app.routers.workflow import router as workflow_router

app = FastAPI(title="CertiFlow", max_body_size=4 * 1024 * 1024)


@app.middleware("http")
async def api_headers(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    origin = request.headers.get("origin")
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and origin
        and origin not in settings().allowed_origins
    ):
        response = JSONResponse(
            {"message": "Request origin is not allowed."}, status_code=403
        )
    else:
        response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    body = exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail}
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def request_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {
            "message": "Check the submitted information.",
            "details": [
                {"field": list(error["loc"]), "message": error["msg"]}
                for error in exc.errors()
            ],
        },
        status_code=400,
    )


@app.exception_handler(IntegrityError)
async def integrity_error(_request: Request, _exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {"message": "This operation conflicts with an existing record."},
        status_code=409,
    )


app.include_router(auth_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")

app.include_router(state_router, prefix="/api")
app.include_router(student_activation_router, prefix="/api")
app.include_router(student_auth_router, prefix="/api")
app.include_router(student_portal_router, prefix="/api")
