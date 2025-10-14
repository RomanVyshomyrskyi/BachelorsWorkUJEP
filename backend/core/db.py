from typing import Generator, Optional
from sqlmodel import SQLModel, Session, create_engine

# Lazy-initialized DB engine (set by init_engine). Kept as None until initialization.
_engine = None  # type: Optional[object]

def init_engine(dsn: str):
    """
    Initialize the global DB engine.

    Args:
        dsn: database connection string (DSN) passed to create_engine.
    """
    global _engine
    # create_engine returns a SQLAlchemy Engine; pool_pre_ping helps avoid stale connections
    _engine = create_engine(dsn, pool_pre_ping=True)

def get_engine():
    """
    Return the initialized engine.

    Raises:
        RuntimeError: if init_engine has not been called yet.
    """
    if _engine is None:
        raise RuntimeError("DB engine not initialized. Call init_engine(dsn) first.")
    return _engine

def get_session() -> Generator[Session, None, None]:
    """
    Provide a context-managed SQLModel Session as a generator.

    Intended for use with dependency-injection systems (e.g., FastAPI's Depends).
    Yields:
        A Session instance bound to the global engine.

    Raises:
        RuntimeError: if init_engine has not been called yet.
    """
    if _engine is None:
        raise RuntimeError("DB engine not initialized.")
    # Use a context manager so the session is committed/closed properly after use.
    with Session(_engine) as sess:
        yield sess

def init_db() -> None:
    """
    Create all database tables defined in SQLModel models.

    Call this after init_engine(). Imports models to ensure they are registered
    on SQLModel.metadata before calling create_all.
    """
    import models  # ensure models module is executed so metadata is populated
    SQLModel.metadata.create_all(get_engine())
