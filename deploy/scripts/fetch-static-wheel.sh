#!/bin/sh
set -eu

VERSION="0.17.5"
SHA256="0d6ffe5518a542107fd08ffe0669f77d3f622f4e7fd465e9a8b60e0f8aae6b04"
URL="https://files.pythonhosted.org/packages/5b/a6/4b435d8d646499f6a1a745ad4326d5ff4917ca68b2b4a25e3103cb257850/ka_lite_static-${VERSION}-py2-none-any.whl"

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEST="${ROOT}/vendor/ka_lite_static-${VERSION}-py2-none-any.whl"
mkdir -p "${ROOT}/vendor"

verify() {
    python3 - "$1" "$SHA256" <<'PY'
import hashlib, sys
path, expected = sys.argv[1], sys.argv[2]
digest = hashlib.sha256()
with open(path, "rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
actual = digest.hexdigest()
print("sha256:", actual)
if actual != expected:
    raise SystemExit("checksum mismatch: expected %s" % expected)
PY
}

if [ -f "${DEST}" ]; then
    verify "${DEST}"
    echo "Using existing ${DEST}"
    exit 0
fi

echo "Downloading official ka-lite-static ${VERSION} wheel..."
python3 - "$URL" "${DEST}.part" <<'PY'
import sys, urllib.request
url, destination = sys.argv[1], sys.argv[2]
request = urllib.request.Request(url, headers={"User-Agent": "ka-lite-maintenance/working.1"})
with urllib.request.urlopen(request, timeout=120) as response, open(destination, "wb") as handle:
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        handle.write(chunk)
PY
mv "${DEST}.part" "${DEST}"
verify "${DEST}"
echo "Saved ${DEST}"
