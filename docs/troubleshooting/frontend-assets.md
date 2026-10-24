# Troubleshooting: Unstyled KA Lite Frontend / Missing Bundles

## Symptoms

- The homepage is plain HTML with default browser fonts.
- The layout, navigation bar, buttons, and footer are unstyled.
- The splash image appears at an excessive size.
- The login modal or navigation JavaScript does not initialize.
- The browser console may show:
  `Cannot read properties of undefined (reading 'set')`.

## Check the network panel

Open the browser developer tools and reload the homepage. A missing bundle set
shows HTTP 404 for:

```text
/static/js/distributed/bundles/bundle_common.js
/static/js/distributed/bundles/bundle_base.js
/static/js/distributed/bundles/bundle_homepage.js
/static/js/inline/bundles/bundle_bootstrap.js
/static/js/inline/bundles/bundle_inline_help.js
```

`/static/fonts/style.css` may still return 200. That file only declares the
icomoon icon font; it is not the application stylesheet.

## Root cause

KA Lite's GitHub "Source code" archive contains the frontend sources but not
the compiled Browserify bundles. The official PyPI release artifacts include
the bundles:

| Artifact | `bundle_*.js` files |
|---|---:|
| GitHub `v0.17.5` source archive | 0 |
| PyPI `ka-lite-0.17.5.tar.gz` | 22 |
| PyPI `ka_lite-0.17.5-py2-none-any.whl` | 22 |
| PyPI `ka_lite_static-0.17.5-py2-none-any.whl` | 22 |

This is an installation/packaging trap, not a bug in the KA Lite source tree.
Do not patch templates or add a new frontend framework.

## Repair

1. Use the PyPI release artifact, or install the matching `ka-lite-static`
   wheel.
2. For this Docker deployment, run:

   ```bash
   cd deploy
   ./scripts/fetch-static-wheel.sh
   docker compose build
   docker compose up -d --force-recreate
   ```

3. Verify:

   ```bash
   python3 deploy/scripts/check-frontend-assets.py
   ```

4. If an existing data volume still lacks the bundles, the entrypoint runs
   `collectstatic --noinput` automatically when
   `bundle_common.js` is absent. You can also run it manually inside the
   container:

   ```bash
   docker exec ka-lite-maintenance kalite manage collectstatic --noinput
   ```

## Do not

- Do not replace the original templates with a new UI.
- Do not add a new CSS framework or JavaScript framework.
- Do not hide missing assets with CSS.
- Do not run an unrelated KA Lite upgrade.
- Do not run a hard reset that discards existing compatibility patches.

## Expected result

The original KA Lite layout, typography, navigation, logo dimensions, login
modal, learner pages, and administration pages return. The fix changes only
asset packaging and static collection, not the interface design.
