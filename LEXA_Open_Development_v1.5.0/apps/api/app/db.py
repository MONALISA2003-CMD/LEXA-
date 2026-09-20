import re

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)

if settings.database_app_role:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", settings.database_app_role):
        raise ValueError("DATABASE_APP_ROLE must be a simple PostgreSQL role identifier")

    @event.listens_for(engine, "connect")
    def _set_application_role(dbapi_connection, _connection_record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {settings.database_app_role}")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
