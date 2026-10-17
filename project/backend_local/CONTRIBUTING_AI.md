# Guide for AI Coding Agents

## Project status and scope

This repository contains a local compatibility backend for Spiral Warrior. It is not a copy of the original server. The current estimate is **at most 25% of the original backend reconstructed**. Do not increase that estimate by counting synthetic routes, isolated experiments, or code that has not been verified with the game client.

Before starting, read:

1. The root `README.md`.
2. `project/backend_local/README_GITHUB.md`.
3. The reports relevant to the feature and client flow you will work on.

Label findings as:

- **Observed:** directly captured from the client or reproduced in the game.
- **Inferred:** consistent with evidence but not yet confirmed.
- **Unknown:** a contract, rule, or response that is not yet known.

Do not invent routes, protocol fields, rewards, limits, rates, errors, or original-server responses. Clearly label synthetic local responses.

## Project tools

### Backend development

- Windows 10/11, PowerShell, and Git.
- Python 3.10 or later. The server uses the standard library. Local game data catalogs are provided separately and are not part of this repository.
- Node.js/npm only for JavaScript client tasks or REA installation; Node is not required to run the Python backend.

### Android client testing

- For dynamic client tests, use LDPlayer or MuMu Player with root access and local ADB enabled, or a rooted phone. Without one of these, work on the backend and static analysis, and mark dynamic behavior as unverified.
- Android SDK Platform-Tools (`adb`) and an active local ADB connection for installing the client, interacting with the device, and collecting logs.
- Frida on the PC and a compatible `frida-server` for the Android architecture and Frida version. The research environment recorded Frida 17.16.0; verify the versions available in your own setup.
- Android SDK Build-Tools (`aapt`, `apksigner`, `zipalign`) and Apktool to inspect and validate local packages. The research notes record Build-Tools 35.0.1 and Apktool 3.0.3.

### Reverse engineering

- REA (`morluto/rea`) with its `reverse-engineer-anything` skill and, when needed, its MCP configuration.
- Ghidra 12.1.4 or IDA Free for native analysis. These are alternatives; installing both is unnecessary.
- Androguard 4.1.4 for programmatic DEX inspection.
- JADX may help with Java/DEX inspection, but it was not found on `PATH` in the last environment review. Confirm it is installed before relying on it.
- Frida for runtime observations. Hooks are temporary diagnostic tools. When a fix depends on a hook, move that behavior into the APK and/or backend, then verify it with Frida detached.

These versions describe the research workstation; they are not dependencies installed by this repository. Do not upload installers, emulators, APKs, `frida-server`, Ghidra/IDA databases, or signing keys.

## Install REA

The recommended approach is to ask the coding agent to prepare REA and review its setup plan. For example:

> Install the REA `reverse-engineer-anything` skill from https://github.com/morluto/rea and configure it for this agent if needed. First inspect the requirements and proposed changes. Reuse Ghidra or IDA if already installed; do not install another analysis engine or change existing settings without explaining the change. At the end, report which skill and tools are available.

To install only the skill:

```powershell
npx skills add morluto/rea --skill reverse-engineer-anything
```

For guided REA/MCP setup, the REA project documents `npx rea-agents setup`. REA requires a compatible Node.js release: 22.x (22.19 or later), 24.x (24.11 or later), or 26 or later. Installing the skill alone does not install the MCP server or a native analysis engine. Verify availability and get approval before making configuration changes that require it.

Sources: <https://github.com/morluto/rea> and <https://github.com/morluto/rea/blob/main/docs/installation.md>.

## Required feature workflow

Use this sequence for each game feature. The goal is a reproducible client flow that works with the local backend and without Frida hooks.

### 1. Establish a safe baseline

- Read the existing implementation, reports, and relevant client call sites before changing code.
- Record the app build, backend revision, emulator/device and Android version, test account type, and exact steps to reproduce.
- Start from a working copy of the patched APK. Never edit or overwrite the original APK or its reserved backup.
- Use a disposable account and profile. Do not use the project owner's personal beta account.
- Reproduce the flow once with Frida detached. Save relevant logs and the visible result, with credentials, tokens, email addresses, and personal data removed.

### 2. Use Frida to discover the contract

- Attach Frida only for the investigation. Hook the smallest relevant methods and keep each trace focused on one action.
- Capture the caller, request method and path, sanitized request fields, callback/result method, response fields, and the state change shown in the game.
- If a temporary hook changes or supplies a response, record exactly what it changes. This can prove a hypothesis or help make the flow work during research, but it is not a completed fix.
- Compare the trace with static analysis, backend logs, and existing reports. Mark each conclusion observed, inferred, or unknown.
- Keep hook scripts, dumps, and sensitive traces local; do not commit them.

### 3. Prove the smallest working behavior

- Use the temporary hook to test the smallest response or behavior that makes the client complete the action. Keep a before/after record of the screen and relevant state.
- Confirm what the client expects on success and failure, including follow-up requests and callbacks. Do not silence errors with a generic success response.
- Check that rewards or inventory changes belong to the authenticated player, persist to that player's profile, and do not apply twice if the client retries.
- Treat unobserved rules and values as unknown. Do not use a successful hook experiment as evidence that the original server behaved the same way.

### 4. Implement the permanent path

- Port the confirmed behavior into the local backend: route handling, input validation, player ownership, persistence, response format, and retry/idempotency behavior.
- Patch only a working copy of the APK when a permanent client change is needed, such as directing the client to the local backend or fixing the request/callback path. Keep the patch small and document it.
- Remove the dependency on runtime hooks. Do not ship a Frida script, injected hook, or a requirement to attach Frida to use the feature.
- If evidence shows the feature needs no APK change, document why and still prove that the unmodified client path works with the backend.

### 5. Verify with hooks off

- Stop and relaunch the game with Frida detached and no hook scripts loaded. Reproduce the full flow from a clean process.
- Confirm the user-visible result and the backend's persisted state. Restart the game and confirm the state remains.
- Repeat the action where safe to check duplicate requests, retry behavior, and idempotency. Check expected failure cases as well as success.
- Recheck the nearby menu or flow that could be affected by the change. Use a disposable profile and temporary test data.
- If the client still needs Frida, the feature is not yet complete. Record the failure and return to the trace; do not report it as fixed.

### 6. Package and clean up APKs

- Build, align, sign, and install the patched working copy. Keep the original APK and its reserved backup unchanged and outside the public repository.
- After installation, test the latest APK on the target emulator/device and confirm the feature still works without Frida. Record the version, signing result, and SHA-256 for the delivered build.
- Once the new build passes those checks, remove older **agent-generated** APKs from the delivery/build folder and leave only the newest APK there, so the user does not accumulate large files.
- Never delete the original APK, its reserved backup, or the newest verified APK during cleanup. Do not remove the previous working build until the replacement has installed and passed verification.
- Do not commit APKs, `.bat` files, extracted resources, or local catalogs. The launcher generator may be shared; the `.bat` it generates is local and ignored by Git.

### 7. Report the result

For each feature, report:

- What was directly observed, what was inferred, and what remains unknown.
- The Frida methods/hooks used for discovery and what they established; confirm that final verification ran with hooks detached.
- Backend and APK files changed, endpoint/contract added or updated, and the resulting client behavior.
- Device/emulator, app build, test steps, persistence/retry results, and any regressions or remaining failures.
- The newest verified APK location and SHA-256 if an APK was produced; confirm older generated APKs were cleaned up while the original and backup were preserved.

Do not claim success based only on a hook-assisted run, a server unit test, or a UI animation. Confirm the complete flow in the game with the permanent backend/APK path.

## Data and privacy

- Do not commit SQLite databases, profiles, test accounts, email addresses, logs, tokens, JWT responses, dumps, screenshots with personal information, or local configuration files.
- Catalogs under `data/*.json` come from game client tables. They are excluded from Git pending a rights review. Do not force-add them.
- Keep the original and patched APKs outside the repository. The `.gitignore` blocks APKs by extension; do not use `git add -f` to bypass this.
- The LAN listener is for trusted local-network testing only. Do not expose ports to the public internet or describe the server as production-ready.
- `generate_lan_launcher.py` may be shared; the `.bat` it creates is local and Git ignores it. Do not force it into the repository.
- Do not add an open-source license until the rights to each code and data component have been reviewed.

## Suggested task kickoff

> Read this agent guide and the report for the requested system. Summarize the existing evidence, unknowns, and a safe baseline before editing. Use a disposable account and working APK copy. Use Frida hooks only to understand and temporarily prove the client contract; then implement the permanent behavior in the local backend and, when needed, the APK. Verify the complete flow with Frida detached. Preserve the original APK and its backup. After the newest APK passes verification, remove older agent-generated APKs and keep only the latest in the delivery folder. Keep the backend reconstruction estimate at 25% or less, and do not commit APKs, recovered resources, personal data, or local configuration.
