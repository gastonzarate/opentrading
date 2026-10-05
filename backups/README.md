# Backups de la DB de opentrading

| Archivo | Fecha (UTC) | Contenido | SHA-256 |
|---|---|---|---|
| `opentrading-db-20261005.dump` | 2026-10-05 | Forward-test #6 + agente general, 2026-08-07 → 2026-10-05 (6.316 corridas, 706 operaciones) | `a358b41b7d2a9b1797dc59e96d7350c897c73d235386321d32882023d2a4dbe2` |

Formato: `pg_dump -Fc -Z9 --no-owner --no-privileges` (Postgres 17).

Restaurar:

```bash
createdb opentrading_restore
pg_restore --no-owner -d opentrading_restore backups/opentrading-db-20261005.dump
```
