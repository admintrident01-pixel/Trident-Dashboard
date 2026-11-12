-- DRAFT FOR LOCAL REVIEW ONLY. Not executed in any cloud project.
-- Target: asxogtpndlsgwdjcxxdv (Trident Migration Sydney).
-- Compatibility checkpoint, not the final normalized performance schema.
-- No business records, credential values, file contents or sample seed data.
-- Runtime grants, connection role and end-to-end concurrency tests are still required.

begin;

create schema trident_migration;
revoke all on schema trident_migration from public, anon, authenticated;

create table trident_migration.app_state (
  id text primary key check (id = 'main'),
  revision bigint not null check (revision >= 0),
  state jsonb not null check (jsonb_typeof(state) = 'object'),
  copied_source_revision bigint not null check (copied_source_revision >= 0),
  copied_at timestamptz not null default now()
);

alter table trident_migration.app_state enable row level security;
-- No browser-facing policies. Raw state includes protected business/account data.
revoke all on trident_migration.app_state from public, anon, authenticated;

-- Preserve the existing API's compare-and-swap contract. A stale expected revision
-- must return false; it must never silently overwrite a newer booking or quote.
create function trident_migration.commit_state(expected_revision bigint, next_state jsonb)
returns boolean
language plpgsql
security invoker
set search_path = pg_catalog
as $$
declare changed bigint;
begin
  if next_state is null or jsonb_typeof(next_state) <> 'object' then
    raise exception 'State must be a JSON object';
  end if;
  update trident_migration.app_state
     set revision = revision + 1, state = next_state
   where id = 'main' and revision = expected_revision;
  get diagnostics changed = row_count;
  return changed = 1;
end;
$$;

revoke all on function trident_migration.commit_state(bigint, jsonb)
  from public, anon, authenticated;

-- Intentionally no runtime grants or initial INSERT. Configure a reviewed server-only
-- role, load only a fresh verified authoritative snapshot, and validate privately.
-- File objects need a separate private bucket and byte/checksum reconciliation.
-- Replication must preserve the source revision, detect rollback/out-of-order input,
-- and remain one-way until an explicitly approved production cutover.

commit;
