import json
import logging
from contextlib import asynccontextmanager
from time import monotonic
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.identity import router as identity_router
from app.api.errors import ApiError
from app.api.events import router as events_router
from app.api.rooms import router as rooms_router
from app.api.faculty import router as faculty_router
from app.api.personal import router as personal_router
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from app.config import Settings
from app.db.connection import make_engine
from app.repositories.demo import get_demo_event
from app.schemas.contracts import DemoEventResponse, ErrorResponse, LiveResponse, ReadyResponse

log = logging.getLogger("almanac")
logging.basicConfig(level=logging.INFO, format="%(message)s")

def create_app(settings=None, now=None):
    settings = settings or Settings()
    engine = make_engine(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="Almanac API", version="0.7.0", lifespan=lifespan,
                  description="Phase 6: owned dialogue, clarification, history and current saved records. Demo data is synthetic.")
    app.state.intent_model = None
    if settings.nlp_mode == 'hybrid':
        from app.nlp.intent_model import load_model
        try:
            app.state.intent_model = load_model(settings.intent_model_path)
        except (OSError, ValueError):
            log.warning('Configured intent artifact unavailable or incompatible')
    app.state.engine = engine
    app.state.settings = settings
    app.state.now = now or (lambda: datetime.now(timezone.utc))
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                       allow_headers=["Content-Type", "X-CSRF-Token"], expose_headers=["X-Request-ID", "Retry-After"])
    app.include_router(identity_router)
    app.include_router(events_router)
    app.include_router(rooms_router)
    app.include_router(faculty_router)
    app.include_router(personal_router)

    static_dir = Path(__file__).parent / "static"

    @app.get("/", include_in_schema=False)
    def testing_page():
        return FileResponse(static_dir / "testing.html", headers={
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            "X-Content-Type-Options": "nosniff",
        })

    @app.get("/testing.js", include_in_schema=False)
    def testing_script():
        return FileResponse(static_dir / "testing.js", media_type="text/javascript",
                            headers={"X-Content-Type-Options": "nosniff"})


    @app.get('/rooms-testing.js',include_in_schema=False)
    def room_testing_script():
        return FileResponse(static_dir / 'rooms-testing.js',media_type='text/javascript',headers={'X-Content-Type-Options':'nosniff'})

    @app.get('/faculty-testing.js',include_in_schema=False)
    def faculty_testing_script():
        return FileResponse(static_dir / 'faculty-testing.js',media_type='text/javascript',headers={'X-Content-Type-Options':'nosniff'})

    @app.get('/personal-testing.js',include_in_schema=False)
    def personal_testing_script():
        return FileResponse(static_dir / 'personal-testing.js',media_type='text/javascript',headers={'X-Content-Type-Options':'nosniff'})

    def error(request, status, code, message, fields=None):
        return JSONResponse(status_code=status, content={"error": {
            "code": code, "message": message, "field_errors": fields or [],
            "request_id": request.state.request_id}})

    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        request.state.request_id = str(uuid4())
        start = monotonic()
        try:
            if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 16384:
                        response = error(request, 413, "request_too_large", "Request body exceeds 16 KiB")
                        break
                else:
                    request._body = bytes(body)
                    response = await call_next(request)
            else:
                response = await call_next(request)
        except Exception:
            # Deliberately exclude exception text, request text, URL query, cookies and credentials.
            response = error(request, 500, "internal_error", "An internal service error occurred")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        route = request.scope.get("route")
        log.info(json.dumps({"request_id": request.state.request_id,
                             "method": request.method, "route": getattr(route, "path", "unmatched"),
                             "status": response.status_code, "duration_ms": round((monotonic()-start)*1000, 2)}))
        return response

    @app.exception_handler(ApiError)
    async def api_error(request, exc):
        response = error(request, exc.status, exc.code, exc.message, exc.field_errors)
        response.headers.update(exc.headers)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return error(request, 503, "dependency_unavailable", "Database or schema unavailable")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        codes = {404: ("not_found", "Resource not found"), 405: ("method_not_allowed", "Method not allowed")}
        code, message = codes.get(exc.status_code, ("request_failed", "Request failed"))
        return error(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = [{"field": ".".join(map(str, e["loc"])), "message": "Invalid value"} for e in exc.errors()]
        return error(request, 422, "validation_error", "Request validation failed", fields)

    @app.get("/api/v1/health/live", response_model=LiveResponse, tags=["operations"])
    def live():
        return LiveResponse()

    @app.get("/api/v1/health/ready", response_model=ReadyResponse,
             responses={503: {"model": ReadyResponse}}, tags=["operations"])
    def ready(request: Request):
        checks = {"database": "unavailable", "schema": "unavailable", "nlp": "ok" if settings.nlp_mode=="baseline" or app.state.intent_model is not None else "unavailable"}
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                checks["database"] = "ok"
                revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                if revision == "0006":
                    conn.execute(text("SELECT id FROM demo_events LIMIT 0"))
                    conn.execute(text("SELECT token_hash FROM web_sessions LIMIT 0"))
                    conn.execute(text("SELECT user_id FROM student_profiles LIMIT 0"))
                    conn.execute(text("SELECT id FROM events LIMIT 0"))
                    conn.execute(text("SELECT state,version FROM conversations LIMIT 0"))
                    conn.execute(text("SELECT id FROM rooms LIMIT 0"))
                    conn.execute(text("SELECT id FROM booking_exceptions LIMIT 0"))
                    conn.execute(text("SELECT id FROM faculty LIMIT 0"))
                    conn.execute(text("SELECT id FROM office_hour_exceptions LIMIT 0"))
                    conn.execute(text("SELECT user_id FROM deleted_requests LIMIT 0"))
                    conn.execute(text("SELECT id FROM saved_records LIMIT 0"))
                    checks["schema"] = "ok"
        except SQLAlchemyError:
            pass
        healthy = all(v == "ok" for v in checks.values())
        body = ReadyResponse(status="ready" if healthy else "not_ready", checks=checks,
                             request_id=request.state.request_id, nlp_mode=settings.nlp_mode)
        return JSONResponse(status_code=200 if healthy else 503, content=body.model_dump())

    @app.get("/api/v1/demo/event", response_model=DemoEventResponse, tags=["demo"],
             responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
    def demo_event(request: Request):
        try:
            with engine.connect() as conn:
                row = get_demo_event(conn)
        except SQLAlchemyError:
            return error(request, 503, "dependency_unavailable", "Database or schema unavailable")
        if row is None:
            return error(request, 404, "demo_not_seeded", "Run the explicit demo seed command first")
        return DemoEventResponse(**row)

    return app
