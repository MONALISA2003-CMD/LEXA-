"""LEXA Phase 1 intelligence contracts and policy controls.

This package deliberately has no provider client, database session, arbitrary SQL,
or business-write capability. Provider calls may only be reached through an API
route that checks the central LEXA policy first.
"""

CONTRACT_VERSION = "1.0"
POLICY_VERSION = "phase1-v1"
