#!/usr/bin/env python3
"""Insert Phase 3 client API helpers into the hash-pinned LEXA API client."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: extend-api-helpers.py PATH_TO_apps/web/lib/api.ts")
path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

new_symbols = (
    "export type BusinessProfile =",
    "export function getBusinessProfile(",
    "export function createBusinessProfile(",
    "export function updateBusinessProfile(",
    "export function createBranch(",
    "export function updateBranch(",
)
collisions = [symbol for symbol in new_symbols if symbol in source]
if collisions:
    raise SystemExit(f"Refusing to duplicate existing Phase 3 API helpers: {collisions}")

branch_type = 'export type Branch = { id:string; tenant_id:string; name:string; code:string; status:string };'
profile_type = 'export type BusinessProfile = { id:string; tenant_id:string; legal_name:string; display_name:string; country_code:string; currency_code:string };\n'
if source.count(branch_type) != 1:
    raise SystemExit("Expected exactly one Branch type declaration; no changes made to api.ts")
source = source.replace(branch_type, profile_type + branch_type, 1)

branch_getter = 'export function getBranches() { return getJson<Branch[]>("/api/v1/organization/branches"); }'
profile_helpers = '''export function getBusinessProfile() { return getJson<BusinessProfile | null>("/api/v1/organization/profile"); }
export function createBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}) { return getJson<BusinessProfile>("/api/v1/organization/profile", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function updateBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}) { return getJson<BusinessProfile>("/api/v1/organization/profile", { method:"PATCH", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
'''
if source.count(branch_getter) != 1:
    raise SystemExit("Expected exactly one getBranches helper; no changes made to api.ts")
source = source.replace(branch_getter, profile_helpers + branch_getter, 1)

warehouse_getter = 'export function getWarehouses() { return getJson<Warehouse[]>("/api/v1/organization/warehouses"); }'
branch_helpers = '''export function createBranch(body: {name:string; code:string}) { return getJson<Branch>("/api/v1/organization/branches", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function updateBranch(id:string, body: {name:string; code:string}) { return getJson<Branch>(`/api/v1/organization/branches/${encodeURIComponent(id)}`, { method:"PATCH", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
'''
if source.count(warehouse_getter) != 1:
    raise SystemExit("Expected exactly one getWarehouses helper; no changes made to api.ts")
source = source.replace(warehouse_getter, branch_helpers + warehouse_getter, 1)

path.write_text(source, encoding="utf-8")
