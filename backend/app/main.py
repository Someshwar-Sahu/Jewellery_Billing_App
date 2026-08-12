from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.models import *
from app.routers import invoices, parties, rates, old_gold, products, expenses, stocks, advances, settings, scan, reports, exports, dashboard, auth, ledger, rough_bill
import json as _json_main
from app.dependencies import require_login, add_login_redirect_handler
from app.config import settings as app_settings
from app.database import get_session
from sqlmodel import SQLModel, create_engine, Session

engine = create_engine(app_settings.DATABASE_URL)

app = FastAPI(
    title="Jewellery Billing App",
    description="Complete billing system for jewellery shop",
    version="1.0.0"
)

# same_site="lax" provides strong CSRF protection.
# https_only is left to default (False) to prevent accidental lockouts on proxy-hosted deployments (like Render) where proxy headers might not be perfectly forwarded.
app.add_middleware(SessionMiddleware, secret_key=app_settings.SECRET_KEY, same_site="lax")
add_login_redirect_handler(app)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/manifest.json", include_in_schema=False)
def serve_manifest():
    """PWA manifest — must be served from root, not /static/"""
    return FileResponse("app/static/manifest.json", media_type="application/manifest+json")

@app.get("/sw.js", include_in_schema=False)
def serve_sw():
    """Service worker — MUST be at root scope to intercept all app routes"""
    return FileResponse("app/static/sw.js", media_type="application/javascript")

app.include_router(auth.router)

# Routers
protected = [
    invoices.router,
    parties.router,
    rates.router,
    old_gold.router,
    products.router,
    expenses.router,
    stocks.router,
    advances.router,
    settings.router,
    scan.router,
    reports.router,
    exports.router,
    dashboard.router,
    ledger.router, 
    rough_bill.router,
]

for router in protected:
    app.include_router(router, dependencies=[Depends(require_login)])

invoices.templates.env.filters["fromjson"] = lambda s: _json_main.loads(s) if s else {}

@app.get("/health", include_in_schema=True)
def health_check(session: Session = Depends(get_session)):
    """Health check endpoint to keep Supabase and Render active 24/7."""
    from sqlmodel import text
    from datetime import datetime
    try:
        session.exec(text("SELECT 1")).first()
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "active",
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "error",
                "detail": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

@app.get("/keep-alive", include_in_schema=False)
def keep_alive(session: Session = Depends(get_session)):
    """Lightweight ping endpoint for uptime monitors."""
    return health_check(session=session)

async def _keep_alive_background_loop():
    """Background task running every 10 minutes to prevent Render sleep and Supabase pausing."""
    import asyncio
    import os
    import urllib.request
    from sqlmodel import text

    await asyncio.sleep(10)  # Initial delay after server boot
    while True:
        try:
            # 1. Ping Supabase PostgreSQL connection
            with Session(engine) as session:
                session.exec(text("SELECT 1")).first()

            # 2. Self-ping Render URL if configured
            app_url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("APP_URL")
            if app_url:
                target = f"{app_url.rstrip('/')}/health"
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: urllib.request.urlopen(target, timeout=10).read())
        except Exception as e:
            print(f"[Keep-Alive] Warning: {e}")

        await asyncio.sleep(600)  # Ping every 10 minutes

@app.on_event("startup")
def on_startup():
    import asyncio
    SQLModel.metadata.create_all(engine)
    asyncio.create_task(_keep_alive_background_loop())

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")
