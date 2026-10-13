#!/bin/sh
# All-in-one image entrypoint: apply migrations, then serve the API + dashboard.
#
# Migrations need schema-owner rights; the API only needs SELECT. Set
# MIGRATE_POSTGRES_USER / MIGRATE_POSTGRES_PASSWORD to the owner account and
# POSTGRES_USER / POSTGRES_PASSWORD to the read-only one. Left unset, both
# steps share the POSTGRES_* account.
set -eu

POSTGRES_USER="${MIGRATE_POSTGRES_USER:-${POSTGRES_USER:-}}" \
POSTGRES_PASSWORD="${MIGRATE_POSTGRES_PASSWORD:-${POSTGRES_PASSWORD:-}}" \
    alembic upgrade head

# Keep the owner credentials out of the serving process.
unset MIGRATE_POSTGRES_USER MIGRATE_POSTGRES_PASSWORD

exec gunicorn -c gunicorn.conf.py "src.app:create_app()"
