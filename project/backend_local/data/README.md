# Local data files

This directory may contain local JSON catalogs and runtime state. Git intentionally excludes those files because some catalogs are derived from game-client data and their redistribution rights have not been reviewed. Account databases, profiles, and logs must also stay local.

## Starting the backend without catalogs

The local server can start without `local_free_purchase_catalog.json`. It prints a warning and uses an empty purchase catalog. Login and other available routes can still be tested, but purchase claims return `unknown_local_product` and grant no items until a valid local purchase catalog is supplied.

Other catalog-backed game systems may return incomplete results when their local data files are absent. The backend's startup does not prove that those systems are fully configured.

## Preparing local data

If you have a client copy and are authorized to inspect its data, create the catalog files needed for your test in this directory. Keep them on your workstation; do not add them to Git or share them without reviewing their provenance and redistribution rights. The server accepts a custom purchase catalog path through `--free-purchase-catalog` when running `server.py` directly; otherwise it looks for `local_free_purchase_catalog.json` in this directory.

Never publish account databases, profiles, test-account details, logs, tokens, extracted game assets, or private catalog files.
