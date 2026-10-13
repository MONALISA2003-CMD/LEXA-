import re

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

ENGINE_CONNECT_ARGS = {
    # Neon PgBouncer rejects PostgreSQL session GUCs in startup options.
    # Apply bounded timeouts transaction-locally in the Session hook below.
    "prepare_threshold": None,
    "connect_timeout": 10,
}

engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_timeout=10,
    pool_recycle=900,
    connect_args=ENGINE_CONNECT_ARGS,
)

if settings.database_app_role and not re.fullmatch(r"[a-z_][a-z0-9_]*", settings.database_app_role):
    raise ValueError("DATABASE_APP_ROLE must be a simple PostgreSQL role identifier")


@event.listens_for(Session, "after_begin")
def _set_application_role_per_transaction(session, transaction, connection):
    # SET LOCAL works with transaction pooling and avoids startup packet GUCs.
    if settings.database_app_role:
        connection.exec_driver_sql(f"SET LOCAL ROLE {settings.database_app_role}")
    connection.exec_driver_sql("SET LOCAL statement_timeout = '15s'")
    connection.exec_driver_sql("SET LOCAL lock_timeout = '3s'")
    connection.exec_driver_sql("SET LOCAL idle_in_transaction_session_timeout = '30s'")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
