# KA Lite 0.17.5 maintenance deployment
#
# This Dockerfile builds the source tree in this repository. The source tree
# already contains the compatibility patches on the maintenance branch.
#
# The compiled frontend bundles are NOT committed. Run
# deploy/scripts/fetch-static-wheel.sh once to download the official
# ka-lite-static 0.17.5 wheel, then build with Docker Compose.
#
# Upstream: https://github.com/learningequality/ka-lite
# Fork:     https://github.com/mesangbedo-source/ka-lite

FROM python:2.7-slim@sha256:6c1ffdff499e29ea663e6e67c9b6b9a3b401d554d2c9f061f9a45344e3992363

ARG KA_LITE_STATIC_VERSION=0.17.5
ARG KA_LITE_STATIC_SHA256=0d6ffe5518a542107fd08ffe0669f77d3f622f4e7fd465e9a8b60e0f8aae6b04
ARG KA_LITE_UID=10001
ARG KA_LITE_GID=10001

LABEL org.opencontainers.image.title="KA Lite 0.17.5 working maintenance fork" \
      org.opencontainers.image.version="working.1" \
      org.opencontainers.image.description="Community maintenance build of KA Lite 0.17.5; not an official Learning Equality release" \
      org.opencontainers.image.source="https://github.com/mesangbedo-source/ka-lite" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    KALITE_HOME=/data \
    KALITE_CONTENT_ROOT=/content \
    KALITE_LISTEN_PORT=8008

COPY . /usr/src/ka-lite

RUN set -eux; \
    printf 'deb http://archive.debian.org/debian buster main\ndeb http://archive.debian.org/debian-security buster/updates main\n' > /etc/apt/sources.list; \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99archive; \
    apt-get update; \
    apt-get install -y --no-install-recommends net-tools=1.60+git20180626.aebd88e-1; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

RUN set -eux; \
    pip install --no-cache-dir --upgrade "pip==20.3.4" "setuptools==44.1.1" "wheel==0.37.1"; \
    pip install --no-cache-dir /usr/src/ka-lite; \
    pip install --no-cache-dir --upgrade "setuptools==44.1.1"; \
    python -m compileall -q /usr/local/lib/python2.7/site-packages/kalite >/dev/null || true

COPY deploy/vendor/ka_lite_static-${KA_LITE_STATIC_VERSION}-py2-none-any.whl /tmp/
RUN set -eux; \
    echo "${KA_LITE_STATIC_SHA256}  /tmp/ka_lite_static-${KA_LITE_STATIC_VERSION}-py2-none-any.whl" | sha256sum -c -; \
    mkdir -p /tmp/ka-lite-static; \
    python -c 'import sys, zipfile; z = zipfile.ZipFile(sys.argv[1]); z.extractall(sys.argv[2], [n for n in z.namelist() if "/static/" in n or "/static-libraries/" in n])' \
        "/tmp/ka_lite_static-${KA_LITE_STATIC_VERSION}-py2-none-any.whl" /tmp/ka-lite-static; \
    KALITE_PKG="$(python -c 'import kalite, os; print(os.path.dirname(kalite.__file__))')"; \
    cp -a /tmp/ka-lite-static/kalite/. "${KALITE_PKG}/"; \
    test -s "${KALITE_PKG}/distributed/static/js/distributed/bundles/bundle_common.js"; \
    rm -rf /tmp/ka-lite-static "/tmp/ka_lite_static-${KA_LITE_STATIC_VERSION}-py2-none-any.whl"

RUN pip freeze > /usr/local/share/ka-lite-pip-freeze.txt \
 && python -c "import kalite.version as v; print(v.VERSION)" > /usr/local/share/ka-lite-version.txt

RUN set -eux; \
    groupadd --gid ${KA_LITE_GID} kalite; \
    useradd --uid ${KA_LITE_UID} --gid ${KA_LITE_GID} --no-create-home \
            --home-dir /data --shell /usr/sbin/nologin kalite; \
    install -d -o ${KA_LITE_UID} -g ${KA_LITE_GID} -m 0750 /data; \
    install -d -o ${KA_LITE_UID} -g ${KA_LITE_GID} -m 0750 /content

COPY deploy/docker-entrypoint.sh /usr/local/bin/ka-lite-entrypoint
RUN chmod 0755 /usr/local/bin/ka-lite-entrypoint

VOLUME ["/data"]
EXPOSE 8008

USER ${KA_LITE_UID}:${KA_LITE_GID}
WORKDIR /data

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
    CMD ["python", "-c", "import urllib2,sys; sys.exit(0 if urllib2.urlopen('http://127.0.0.1:8008/', timeout=8).getcode() == 200 else 1)"]

ENTRYPOINT ["/usr/local/bin/ka-lite-entrypoint"]
CMD ["kalite", "start", "--foreground", "--skip-job-scheduler", "--port=8008"]
