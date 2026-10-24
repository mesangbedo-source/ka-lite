# Static asset vendor directory

`deploy/vendor/` is intentionally ignored by Git. The compiled frontend assets
are distributed by Learning Equality as the official `ka-lite-static` 0.17.5
wheel; they are not committed here.

Run:

```bash
./scripts/fetch-static-wheel.sh
```

The script downloads:

```text
ka_lite_static-0.17.5-py2-none-any.whl
sha256 0d6ffe5518a542107fd08ffe0669f77d3f622f4e7fd465e9a8b60e0f8aae6b04
```

and verifies the checksum before the Docker build uses it. If the PyPI URL is
unavailable, download the same wheel manually from
<https://pypi.org/project/ka-lite-static/0.17.5/> and place it here.
