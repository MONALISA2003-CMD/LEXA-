# Billing hold — LEXA Phase 7

Deferred until the final production phase:
- Creating a paid isolated staging cache if the account's free allowance is insufficient.
- Enabling paid automatic database backup scheduling or other paid backup features.
- Any other paid infrastructure needed to complete production rollout.

Do not use the production Redis/cache for staging. Do not apply Phase 7 migrations to production before the isolated authenticated staging gate passes. Existing one-time selective backup/snapshot is not a substitute for automatic backups or a byte-identical clone.
