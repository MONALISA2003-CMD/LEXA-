from sqlalchemy import text

from .db import engine


def check_database() -> tuple[bool, str | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, exc.__class__.__name__
