"""
Database Reset & Initialization Script for Jewellery Billing App
Cleanses all test records and reinitializes fresh tables ready for owner setup (/auth/setup).
"""
import sys
import os
from sqlalchemy import text
from sqlmodel import SQLModel, create_engine, Session

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import *

SUPABASE_URL = "postgresql://postgres.vllqmncytxrylwpnkldd:KusumSahu1606@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
SQLITE_URL = "sqlite:///./test.db"

def reset_database(db_url: str, label: str):
    print(f"\n=======================================================")
    print(f"Connecting to {label} Database...")
    print(f"=======================================================")
    try:
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {"sslmode": "require"}
        engine = create_engine(db_url, connect_args=connect_args)
        
        with engine.connect() as conn:
            if "postgresql" in db_url or "postgres" in db_url:
                print("Dropping existing tables in PostgreSQL public schema...")
                conn.execute(text("DROP SCHEMA public CASCADE;"))
                conn.execute(text("CREATE SCHEMA public;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO postgres;"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
                conn.commit()
            else:
                print("Dropping SQLite metadata tables...")
                SQLModel.metadata.drop_all(engine)

        print("Recreating fresh tables according to SQLModel schema...")
        SQLModel.metadata.create_all(engine)

        with engine.connect() as conn:
            if "postgresql" in db_url or "postgres" in db_url:
                tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")).fetchall()
                table_names = [t[0] for t in tables]
            else:
                tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
                table_names = [t[0] for t in tables]

        print(f"SUCCESS: {len(table_names)} clean tables created successfully in {label} DB:")
        for name in sorted(table_names):
            print(f"  + {name}")

        print(f"\n{label} Database is 100% clean and ready for first-time store setup at /auth/setup!")
        return True
    except Exception as e:
        print(f"ERROR resetting {label} DB: {e}")
        return False

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "supabase"
    
    if target in ("supabase", "all"):
        reset_database(SUPABASE_URL, "Supabase Production")
    
    if target in ("sqlite", "all"):
        reset_database(SQLITE_URL, "Local SQLite")
