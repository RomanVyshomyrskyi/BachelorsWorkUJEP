from fastapi import APIRouter, HTTPException, Depends
from passlib.hash import bcrypt
from sqlmodel import select
from core.config_store import load_config, save_config
from core.db import init_engine, init_db, get_session
from models import User, Settings
from schemas.setup import TestDBRequest, InitRequest


# Router for setup-related endpoints (configuration and DB initialization)
router = APIRouter(prefix="/api/setup", tags=["setup"])

# Load configuration once at module import time (cached value).
# If None, the application is not yet configured.
_cfg = load_config()  # cached in module

@router.get("/status")
def status():
    """
    Return whether the application has been configured.
    Uses the module-level cached _cfg loaded at import time.
    """
    return {"configured": _cfg is not None}

@router.post("/test-db")
def test_db(body: TestDBRequest):
    """
    Test a database DSN by trying to initialize an engine and create tables.
    This endpoint does not persist any configuration; it only verifies the DSN works.
    Returns {"ok": True} on success or {"ok": False, "error": "..."} on failure.
    """
    try:
        # Try to create an engine for the provided DSN and optionally create tables.
        init_engine(body.dsn)
        init_db()  # optional: ensure we can create tables
        return {"ok": True}
    except Exception as e:
        # Return error details for debugging the DSN/DB connectivity.
        return {"ok": False, "error": str(e)}

@router.post("/initialize")
def initialize(body: InitRequest, session=Depends(get_session)):
    """
    Initialize the application configuration and create an initial admin user.
    - Ensures the app isn't already configured.
    - Initializes the DB engine and ensures tables exist.
    - Creates an admin user (idempotent) and site settings.
    - Persists configuration via save_config and updates the module-level cache.
    """
    global _cfg
    if _cfg is not None:
        # Prevent re-initializing an already-configured application.
        raise HTTPException(400, "Already configured")

    # initialize engine + create tables; fail fast with HTTP 400 on error
    try:
        init_engine(body.dsn)
        init_db()
    except Exception as e:
        raise HTTPException(400, f"DB init failed: {e}")

    # idempotent admin create (in case of retries):
    # check if a user with the given email already exists
    existing = session.exec(select(User).where(User.email == str(body.admin_email))).first()
    if not existing:
        # store hashed password, mark as admin
        session.add(User(
            email=str(body.admin_email),
            password_hash=bcrypt.hash(body.admin_password),
            is_admin=True
        ))
    # Always add initial Settings row (could be extended to check existence)
    session.add(Settings(site_name=body.site_name))
    session.commit()  # persist changes to the database

    # update module-level cached config and persist to disk/store
    _cfg = {"dsn": body.dsn, "site_name": body.site_name}
    save_config(_cfg)

    return {"ok": True}
