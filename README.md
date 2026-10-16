# Spiral Warrior Community Backend

This repository contains the local backend code used to test a community restoration of Spiral Warrior. **It is not the original backend** and does not communicate with it.

## Current scope

Our estimate is that **at most 25% of the original backend has been reconstructed**. This is a cautious estimate, not a measured percentage against a complete service list: the original server is unavailable, and many of its routes and rules remain unknown.

The current implementation is a compatibility backend based on observed requests, client testing, and synthetic or locally extracted data. Flows with partial implementations or tests include local accounts, separate profiles, Adventure, some rewards and inventory, parts and lineups, some GP operations, the PvE campaign, free local purchases, and the gacha protocol. Email and ranking are synthetic test services. See [`project/backend_local/README_GITHUB.md`](project/backend_local/README_GITHUB.md) for details and limitations.

Still incomplete are, among other things, full level and GP progression, several rewards, ad rewards without ads, parts of PvE, the gacha flow through the game interface, and social services. Rates and rules that have not been observed are marked as unknown; they are not presented as behavior of the original server.

## Run on Windows

Python 3.10 or later is required. The server uses Python's standard library, along with local data catalogs that are not included in this repository because they come from the game client and require a rights review. Read [`project/backend_local/data/README.md`](project/backend_local/data/README.md) before preparing those files.

To run the server on this PC, use `python project/backend_local/run_local_server.py`. Instructions for testing from a phone on the same Wi-Fi network, generating a local `.bat` launcher, and configuring the firewall are in [`project/backend_local/README_GITHUB.md`](project/backend_local/README_GITHUB.md).

The LAN mode does not include HTTPS and is not designed to be exposed to the internet. Do not use real accounts or publish your network's IP address.

## Contributing with a coding agent

Read [`project/backend_local/CONTRIBUTING_AI.md`](project/backend_local/CONTRIBUTING_AI.md) before changing the server. It covers the workflow, tools, REA installation, and starter instructions for agents. REA is the reverse-engineering skill linked by the original project: <https://github.com/morluto/rea>.

## APK, resources, and license

This repository does not include the modified APK, the original APK, or recovered game resources. Do not upload them unless you have confirmed that you are authorized to redistribute them. This repository also does not publish APK download links. The backend code and catalogs derived from the client have different licensing and provenance; **no license is assigned to the repository until we review which parts we can license**. Making a repository private would not grant rights you do not have.

The `.gitignore` keeps only an allowlisted selection of the backend visible and excludes APKs, backups, extracted resources, local research, account data, logs, signing keys, and JSON catalogs derived from the game. Review `git status` before each publication, and do not force-add ignored files without reviewing their provenance and permissions.
