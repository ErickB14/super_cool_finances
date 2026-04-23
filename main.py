from fastapi import FastAPI
from dotenv import load_dotenv
import os
load_dotenv()

from database import engine, Base, SessionLocal
from routers import accounts, movements, audit, auth
from core.security import seed_default_users

APP_ENV = os.getenv("PYTHON_ENV", "development").lower()
AUTO_BOOTSTRAP_DB = os.getenv("AUTO_BOOTSTRAP_DB", "true").lower() == "true"

# In production (e.g., Render), prefer migrations and explicit seed jobs.
if APP_ENV != "production" and AUTO_BOOTSTRAP_DB:
	Base.metadata.create_all(bind=engine)
	with SessionLocal() as db:
		seed_default_users(db)

app = FastAPI(title="Balance API")


@app.get("/health")
def health_check():
	return {"status": "ok"}

app.include_router(accounts.router)
app.include_router(movements.router)
app.include_router(audit.router)
app.include_router(auth.router)
