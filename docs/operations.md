# عملیات — Operations (backups, restore, monitoring, incidents)

## Backups

- **What:** PostgreSQL dump (custom format) + uploaded attachment files + production Compose and
  `.env` snapshot. Backup directories are root-only because `.env` contains secrets.
- **How:** `./infra/backup/backup.sh /mnt/backups` (retention: 14 daily, 8 weekly archives).
- **Schedule (cron):**
  ```cron
  0 2 * * *  /opt/homo-accountant/infra/backup/backup.sh /mnt/backups >> /var/log/homo-accountant-backup.log 2>&1
  ```
- **Retention:** 14 daily directories plus Monday archives retained for eight weeks.
- **Offsite:** copy `/mnt/backups` off-server daily using encrypted storage (rclone to object
  storage / scp to another host). A local-only backup is not a backup.
- **Verify:** monthly restore rehearsal onto a scratch database:
  `./infra/backup/restore.sh /mnt/backups/homo-accountant-<ts>` (confirm prompt), then check
  a few records and `health/ready`.
- **Rehearsal evidence (slice 9):** the exact backup→restore pipeline was executed against a real
  PostgreSQL 17 instance in the sandbox: `pg_dump --format=custom --no-owner` → `gzip` →
  `gunzip -c | pg_restore --clean --if-exists --no-owner` into a scratch DB. All rows survived
  (users, 13 starter accounts, accounting periods, roles intact). The scripts in `infra/backup/`
  wrap the identical commands; `restore.sh`'s `gunzip -c | pg_restore` pipe is required — feeding
  the gzip file directly to `pg_restore` fails (`not a valid archive`).

## Restore

1. Stop writes: `docker compose -f compose.prod.yaml stop api web` (keep db running).
2. `./infra/backup/restore.sh /path/to/homo-accountant-<ts>` (type `restore` at the prompt).
3. Start: `docker compose -f compose.prod.yaml up -d api web` and verify totals/health.
4. Verify uploaded attachments from the restored `media/` directory.

## Monitoring

- Container health: `docker compose -f compose.prod.yaml ps` (healthchecks defined for all services).
- API: `/api/v1/health/live` + `/api/v1/health/ready`; structured JSON logs (prod) with
  `X-Request-ID` correlation; watch 5xx rate and login 429s.
- OS basics: `docker stats`, `df -h` (watch `pgdata` and `media` volumes), `journalctl -u docker`.
- Alerting (optional, recommended): Uptime-Kuma/Healthchecks.io hitting the two health endpoints.

## Incident basics

1. **Read-only first:** gather `docker compose -f compose.prod.yaml logs --tail=200 <svc>`,
   `X-Request-ID` of the failing request, recent backup timestamps.
2. **Severity:** P1 (data loss/integrity) → stop writes, restore from backup, involve owner.
   P2 (outage) → rollback to previous release sha per `docs/deployment.md` §4.
   P3 (degraded) → monitor and fix in normal flow.
3. **Never** edit posted financial data directly in the DB; fix forward with reversal entries.
4. After resolution: write a blameless postmortem, add a regression test, update runbooks.

## Access & secrets

- Secrets live only in `.env` on the VPS (never in git). Rotate `HOMO_JWT_SECRET` and DB
  passwords on suspicion of compromise (token refresh will force re-login).
- Least-privilege: application DB role has no superuser; admin accounts via bootstrap only.
