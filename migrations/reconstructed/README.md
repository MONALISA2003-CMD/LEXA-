# Reconstructed equivalents and replay-only deltas

Every `.equivalent.sql` file here is a labelled engineering reconstruction from observed LEXA schema, available checked-in migrations, the available `027_release_convergence.sql`, and application/test contracts. **None is claimed to be the exact historical source which was applied to the live database.** The six original source paths stay missing, and `scripts/check_migration_sources.py --strict` must continue to fail until exact bytes are recovered.

## Safe use

- Do not move these files into `migrations/<historical-id>.sql`.
- Do not replay these files against production or any branch containing irreplaceable data.
- Use a newly-created isolated LEXA replay database, pinned hashes, synthetic fixtures and backups.
- For non-empty data, prove a backfill before enforcing required columns. The `011` equivalent deliberately refuses to guess product-price context/unit backfills.
- `016_payments_tenant_identity_compatibility.equivalent.sql` addresses a missing composite key observed when checked-in 016 replay failed; it is a schema compatibility delta, not a claim about historical source.
- `schema_observation_compatibility.equivalent.sql` is a catalogue-delta candidate. It is not part of the historical chain and has not passed a fresh parity replay in this increment.

Before any release decision, rerun the current files on a brand-new disposable database, capture hashes/object deltas, verify policy roles and predicate semantics and test cross-tenant denials. Review every SQL file before use.
