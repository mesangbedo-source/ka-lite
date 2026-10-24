#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "${ROOT}/data" "${ROOT}/content" "${ROOT}/database/staging" \
         "${ROOT}/logs" "${ROOT}/backups" "${ROOT}/vendor"

if [ ! -f "${ROOT}/kalite.env" ]; then
    cp "${ROOT}/kalite.env.example" "${ROOT}/kalite.env"
    chmod 600 "${ROOT}/kalite.env"
    echo "Created ${ROOT}/kalite.env"
fi

"${ROOT}/scripts/fetch-static-wheel.sh"

echo
echo "Next steps:"
echo "  1. Edit ${ROOT}/kalite.env and set KA_LITE_ADMIN_PASSWORD."
echo "  2. Optionally place a compatible content_khan_en.sqlite in ${ROOT}/database/staging/."
echo "  3. Run: cd ${ROOT} && docker compose build"
echo "  4. Run: docker compose up -d"
echo "  5. Open http://127.0.0.1:8008/ and verify the frontend."
