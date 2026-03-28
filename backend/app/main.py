from fastapi import FastAPI
from app.database import create_db_and_tables
from app.models import *

app = FastAPI(title="Jewellery Billing App", description="Complete billing system for jewellery shop",
              version="1.0.0")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    print("✅ Database tables created / verified")

@app.get("/")
def root():
    return {"message": "Jewellery Billing API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}