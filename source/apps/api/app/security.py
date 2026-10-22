from dataclasses import dataclass

@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str

# Phase 1 boundary: all tenant-scoped services must receive an explicit
# TenantContext. Database RLS policies will enforce the same boundary.
