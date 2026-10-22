import re

from sqlalchemy import create_engine, event, text
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
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
    pool_recycle=settings.database_pool_recycle_seconds,
    pool_use_lifo=True,
    connect_args=ENGINE_CONNECT_ARGS,
)

def apply_application_role(connection, role: str | None = None) -> None:
    """Switch the current transaction to LEXA's least-privilege database role.

    Use this for ORM sessions and direct engine connections alike. `SET LOCAL`
    is transaction-scoped and safe with Neon/PgBouncer transaction pooling.
    """
    selected_role = settings.database_app_role if role is None else role
    if not selected_role:
        return
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", selected_role):
        raise ValueError("DATABASE_APP_ROLE must be a simple PostgreSQL role identifier")
    connection.exec_driver_sql(f"SET LOCAL ROLE {selected_role}")


if settings.database_app_role and not re.fullmatch(r"[a-z_][a-z0-9_]*", settings.database_app_role):
    raise ValueError("DATABASE_APP_ROLE must be a simple PostgreSQL role identifier")


@event.listens_for(Session, "after_begin")
def _set_application_role_per_transaction(session, transaction, connection):
    # Reapply request-scoped RLS context at every transaction start. SET LOCAL
    # context is cleared by commit, so a later ORM refresh would otherwise be
    # filtered by forced RLS.
    apply_application_role(connection)
    tenant_id = session.info.get("lexa_tenant_id")
    if tenant_id is not None:
        connection.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant_id, true), "
                "set_config('app.user_id', :user_id, true)"
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(session.info.get("lexa_user_id") or ""),
            },
        )
    connection.exec_driver_sql("SET LOCAL statement_timeout = '15s'")
    connection.exec_driver_sql("SET LOCAL lock_timeout = '3s'")
    connection.exec_driver_sql("SET LOCAL idle_in_transaction_session_timeout = '30s'")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
