from sqlalchemy import String, DateTime
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from uuid import UUID

class Base(DeclarativeBase): pass

class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(unique=True)
    legal_name: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    country_code: Mapped[str] = mapped_column(String)
    currency_code: Mapped[str] = mapped_column(String)
    updated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String)
    code: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")

class Warehouse(Base):
    __tablename__ = "warehouses"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String)
    code: Mapped[str] = mapped_column(String)
    branch_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")

class Location(Base):
    __tablename__ = "locations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String)
    code: Mapped[str] = mapped_column(String)
    warehouse_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String, default="ACTIVE")

class PosTerminal(Base):
    __tablename__ = "pos_terminals"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String)
    code: Mapped[str] = mapped_column(String)
    branch_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
