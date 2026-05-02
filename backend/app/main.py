from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import create_db_and_tables
from app.models import *
from app.routers import invoices, parties, rates, old_gold, products, expenses, stocks, advances
import os

app = FastAPI(
    title="Jewellery Billing App",
    description="Complete billing system for jewellery shop",
    version="1.0.0"
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
routers = [
    invoices.router,
    parties.router,
    rates.router,
    old_gold.router,
    products.router,
    expenses.router,
    stocks.router,
    advances.router,
]

for router in routers:
    app.include_router(router)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    print("✅ Database tables created / verified")

@app.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/invoices")
