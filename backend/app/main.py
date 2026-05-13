from fastapi.responses import RedirectResponse, FileResponse
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.models import *
from app.routers import invoices, parties, rates, old_gold, products, expenses, stocks, advances, settings, scan, reports, exports, dashboard, auth, ledger
from app.dependencies import require_login, add_login_redirect_handler
from app.config import settings as app_settings

app = FastAPI(
    title="Jewellery Billing App",
    description="Complete billing system for jewellery shop",
    version="1.0.0"
)

app.add_middleware(SessionMiddleware, secret_key=app_settings.SECRET_KEY)
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
]

for router in protected:
    app.include_router(router, dependencies=[Depends(require_login)])

@app.on_event("startup")
def on_startup():
    pass

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")
