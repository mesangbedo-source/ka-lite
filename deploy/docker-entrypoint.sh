#!/bin/sh
# KA Lite 0.17.5 container entrypoint.
#
# Idempotent bootstrap, in order:
#   1. sanity-check the writable KA Lite home (/data)
#   2. install the recovered content database if it is missing/invalid
#      (a *copy* is made; the seed file itself is only ever read)
#   3. initialise the application database once (kalite manage setup) and
#      make sure an administrator account exists
#   4. collect the static files if the frontend bundle set is missing
#   5. optionally re-derive local video availability from CONTENT_ROOT
#      (KA_LITE_REANNOTATE=1, or automatically after seeding)
#   6. exec the requested command so the server becomes PID 1 and receives
#      SIGTERM directly from the container runtime
set -eu

KALITE_HOME="${KALITE_HOME:-/data}"
export KALITE_HOME
export KALITE_CONTENT_ROOT="${KALITE_CONTENT_ROOT:-/content}"

APP_DB="${KALITE_HOME}/database/data.sqlite"
INIT_MARKER="${KALITE_HOME}/.ka-lite-initialized"
CONTENT_DB="${KALITE_HOME}/database/content_khan_en.sqlite"
SEED_DB="${SEED_CONTENT_DB:-/seed/staging/content_khan_en.sqlite}"
SEED_SHA="${SEED_CONTENT_DB_SHA256:-}"

ADMIN_USER="${KA_LITE_ADMIN_USER:-admin}"
ADMIN_PASS="${KA_LITE_ADMIN_PASSWORD:-}"
ADMIN_EMAIL="${KA_LITE_ADMIN_EMAIL:-admin@example.invalid}"

log() { echo "[ka-lite-init] $*" >&2; }

# Returns 0 if $1 is a readable content database with at least one video row.
# Python 2.7's sqlite3 module has no ``uri`` argument, so open the existing
# file directly; both helpers only issue SELECTs.
content_db_ok() {
    python - "$1" <<'PY'
import os, sqlite3, sys
path = sys.argv[1]
if not os.path.isfile(path):
    sys.exit(1)
try:
    conn = sqlite3.connect(path)
    n = conn.execute("select count(*) from item where kind='Video'").fetchone()[0]
    sys.exit(0 if n > 0 else 1)
except Exception:
    sys.exit(1)
PY
}

# Returns the number of Django superusers in the application database.
superuser_count() {
    python - "$APP_DB" <<'PY'
import os, sqlite3, sys
path = sys.argv[1]
if not os.path.isfile(path):
    print(0)
    sys.exit(0)
try:
    conn = sqlite3.connect(path)
    print(conn.execute("select count(*) from auth_user where is_superuser=1").fetchone()[0])
except Exception:
    print(0)
PY
}

# ------------------------------------------------------------------ 0. checks
if [ ! -d "${KALITE_HOME}" ] || [ ! -w "${KALITE_HOME}" ]; then
    log "FATAL: KALITE_HOME (${KALITE_HOME}) is missing or not writable by uid $(id -u)"
    exit 1
fi
mkdir -p "${KALITE_HOME}/database" "${KALITE_HOME}/logs"

# contentload/settings.py creates CONTENT_ROOT/assessment/khan at import time.
# When /content is mounted read-only these directories must already exist.
if [ -d "${KALITE_CONTENT_ROOT}" ] && [ -w "${KALITE_CONTENT_ROOT}" ]; then
    mkdir -p "${KALITE_CONTENT_ROOT}/assessment/khan"
fi

SEEDED=0

# ------------------------------------------------------- 1. content database
if content_db_ok "${CONTENT_DB}"; then
    log "Content database present: ${CONTENT_DB}"
else
    if [ ! -f "${SEED_DB}" ]; then
        log "WARNING: seed content database not found at ${SEED_DB}; skipping"
    else
        if [ -n "${SEED_SHA}" ]; then
            actual="$(sha256sum "${SEED_DB}" | cut -d' ' -f1)"
            if [ "${actual}" != "${SEED_SHA}" ]; then
                log "FATAL: seed database checksum mismatch"
                log "  expected: ${SEED_SHA}"
                log "  actual  : ${actual}"
                exit 1
            fi
            log "Seed content database checksum verified: ${actual}"
        fi
        cp -f "${SEED_DB}" "${CONTENT_DB}.tmp"
        chmod 0640 "${CONTENT_DB}.tmp"
        mv -f "${CONTENT_DB}.tmp" "${CONTENT_DB}"
        SEEDED=1
        log "Installed content database: ${CONTENT_DB} ($(sha256sum "${CONTENT_DB}" | cut -d' ' -f1))"
    fi
fi

# --------------------------------------------------- 2. application database
run_setup() {
    kalite manage setup --noinput \
        --username="${ADMIN_USER}" \
        --password="${ADMIN_PASS}" \
        --email="${ADMIN_EMAIL}" \
        --no-assessment-items
}

if [ ! -f "${INIT_MARKER}" ]; then
    log "Initialisation marker absent; running one-time 'kalite manage setup'"
    if [ -z "${ADMIN_PASS}" ]; then
        log "FATAL: KA_LITE_ADMIN_PASSWORD must be set for the first initialisation"
        exit 1
    fi
    run_setup
    touch "${INIT_MARKER}"
    log "Application database initialised at ${APP_DB}"
else
    log "Existing application database found: ${APP_DB}"
    if [ -n "${ADMIN_PASS}" ] && [ "$(superuser_count)" -eq 0 ]; then
        log "No superuser in ${APP_DB}; re-running setup to create '${ADMIN_USER}'"
        run_setup
    fi
fi

# ---------------------------------------------------- 3. frontend static files
# Images built before the ka-lite-static overlay have a partial STATIC_ROOT
# without browserify bundles, which renders the UI unstyled.  Collecting again
# is cheap and idempotent; without --clear it never deletes existing files.
STATIC_BUNDLE="${KALITE_HOME}/httpsrv/static/js/distributed/bundles/bundle_common.js"
if [ ! -s "${STATIC_BUNDLE}" ]; then
    log "Frontend bundles missing from ${KALITE_HOME}/httpsrv/static; running collectstatic"
    kalite manage collectstatic --noinput || \
        log "WARNING: collectstatic failed; the UI may render without styling"
fi

# ------------------------------------------ 4. local availability annotation
if [ "${SEEDED}" = "1" ] || [ "${KA_LITE_REANNOTATE:-0}" = "1" ]; then
    log "Scanning ${KALITE_CONTENT_ROOT} and annotating local availability"
    kalite manage annotate_content_items --language=en || \
        log "WARNING: annotate_content_items failed; continuing with existing data"
fi

log "Starting: $*"
exec "$@"
