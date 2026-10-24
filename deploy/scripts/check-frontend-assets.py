#!/usr/bin/env python3
"""Verify that the running KA Lite instance serves its frontend assets."""

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request

REQUIRED = [
    ("/_generated/dynamic.css", "text/css", 1),
    ("/_generated/dynamic.js", "javascript", 1),
    ("/static/fonts/style.css", "text/css", 1000),
    ("/static/css/distributed/khan-site.css", "text/css", 100000),
    ("/static/images/horizontal-logo-small.png", "image/png", 3000),
    ("/static/images/logo_10_enlarged_2.png", "image/png", 100000),
    ("/static/images/distributed/favicon.ico", "image/", 500),
    ("/static/images/distributed/FLE.png", "image/png", 1000),
    ("/static/images/distributed/CC-BY-NC-SA.png", "image/png", 500),
    ("/static/django_js_reverse/js/reverse.js", "javascript", 50000),
    ("/static/js/i18n/en.js", "javascript", 1000),
    ("/static/js/distributed/bundles/bundle_common.js", "javascript", 500000),
    ("/static/js/distributed/bundles/bundle_base.js", "javascript", 500000),
    ("/static/js/distributed/bundles/bundle_homepage.js", "javascript", 20000),
    ("/static/js/inline/bundles/bundle_bootstrap.js", "javascript", 50000),
    ("/static/js/inline/bundles/bundle_inline_help.js", "javascript", 20000),
    ("/static/fonts/fontawesome-webfont.woff", "font", 20000),
]


def fetch(base, path):
    request = urllib.request.Request(urllib.parse.urljoin(base, path))
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, response.headers.get("content-type", ""), response.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8008")
    args = parser.parse_args()
    base = args.base.rstrip("/") + "/"
    failures = []

    for path, content_type, minimum in REQUIRED:
        try:
            status, served_type, body = fetch(base, path)
            problem = None
            if status != 200:
                problem = "status %s" % status
            elif content_type not in served_type:
                problem = "content-type %r (expected %r)" % (served_type, content_type)
            elif len(body) < minimum:
                problem = "size %d (expected at least %d)" % (len(body), minimum)
            if problem:
                failures.append("%s: %s" % (path, problem))
                print("FAIL %-58s %s" % (path, problem))
            else:
                print("PASS %-58s %-24s %d bytes" % (path, served_type, len(body)))
        except urllib.error.HTTPError as error:
            failures.append("%s: HTTP %s" % (path, error.code))
            print("FAIL %-58s HTTP %s" % (path, error.code))
        except Exception as error:
            failures.append("%s: %r" % (path, error))
            print("FAIL %-58s %r" % (path, error))

    if failures:
        print("\n%d frontend asset check(s) failed" % len(failures))
        return 1
    print("\nAll %d frontend asset checks passed" % len(REQUIRED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
