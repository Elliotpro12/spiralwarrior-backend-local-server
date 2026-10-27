# Spiral Warrior Local Backend

This is a community compatibility backend for local testing. **It is not the original backend.** The current estimate is that at most **25% of the original backend** has been reconstructed. A complete inventory of the original service is unavailable, so this is not a measured percentage.

## What is included

- Local username/email accounts, test sessions, and separate player profiles.
- HTTP routes for login, local notices, test purchases, mail, and synthetic ranking responses.
- A WebSocket server with profile synchronization and partial handlers for Adventure, rewards, inventory/parts, some GP operations, the PvE campaign, and Lottery.
- Local persistence using SQLite for accounts and JSON files for profiles.

Research reports document the evidence for each flow. A handler or synthetic response does not prove that the original server behaved the same way.

## Known gaps

Level and GP progression are incomplete. Some PvE routes and rewards are missing; ad rewards are still in progress; Lottery needs a complete test through the game interface; and Friend/Chat are outside the confirmed protocol. Ranking and mail are test fixtures. Rates, caps, and eligibility rules remain unknown for several systems.

## Run the backend

Requirements: Windows 10/11 and Python 3.10 or later. The Python backend uses the standard library. Client testing additionally needs an emulator, ADB, and Frida for dynamic observations; see [`CONTRIBUTING_AI.md`](CONTRIBUTING_AI.md).

To repeat the documented dynamic tests, use an emulator with root access and local ADB enabled, or a rooted phone. ADB must be installed on the PC and connected to the device. The backend can be run and studied without that device.

From the repository root, run the backend on this PC:

```powershell
python project/backend_local/run_local_server.py
```

### Emulator on the same PC: forward the local ports

The patched APK redirects its HTTP requests to `127.0.0.1:18765` and receives the WebSocket address `127.0.0.1:18766`. Inside Android, `127.0.0.1` is the emulator itself, not the Windows host. When the emulator and backend run on the same PC, keep the backend in its default loopback mode and forward both ports with the emulator's ADB executable:

```powershell
adb devices -l
$serial = "127.0.0.1:5559" # Replace with the emulator serial shown above.
adb -s $serial reverse tcp:18765 tcp:18765
adb -s $serial reverse tcp:18766 tcp:18766
adb -s $serial reverse --list
```

If `adb` is not on `PATH`, call the `adb.exe` bundled with LDPlayer or MuMu instead. The serial varies by emulator instance; use the value reported by `adb devices -l`. Repeat the forwarding commands after reconnecting the emulator. Remove the forwards with `adb -s $serial reverse --remove tcp:18765` and `adb -s $serial reverse --remove tcp:18766`.

The launcher's `/healthz` check only verifies that Windows can reach the HTTP service; it does not test connectivity from Android. A successful health check alone is not proof that the game can reach the backend.

To listen on the local network, run:

```powershell
python project/backend_local/run_local_server.py --lan
```

LAN mode binds the services to the network interfaces, detects this PC's private IPv4 address, and advertises HTTP on port `18765` and WebSocket on port `18766`. The phone and PC must be on the same local network, and the client must point to the IP printed by the server. If automatic detection selects another interface, provide the IPv4 address assigned to this PC:

```powershell
python project/backend_local/run_local_server.py --lan --lan-ip 192.168.1.25
```

### Generate a local `.bat` launcher

The repository includes the generator but excludes all `.bat` files. From the repository root, generate a LAN launcher with:

```powershell
python project/backend_local/generate_lan_launcher.py
```

Then start it with:

```powershell
.\project\backend_local\start_local_server_lan.bat
```

Git ignores the generated `.bat`; share the generator script and these commands, not the generated file.

### Windows Firewall for the local subnet

If Windows blocks incoming connections, open PowerShell as Administrator and add a rule limited to local-subnet devices:

```powershell
Get-NetFirewallRule -DisplayName 'Spiral Warrior LAN beta backend' -ErrorAction SilentlyContinue |
  Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'Spiral Warrior LAN beta backend' `
  -Direction Inbound -Action Allow -Protocol TCP `
  -LocalPort 18765,18766 -RemoteAddress LocalSubnet -Profile Any
```

Remove the rule later with:

```powershell
Get-NetFirewallRule -DisplayName 'Spiral Warrior LAN beta backend' -ErrorAction SilentlyContinue |
  Remove-NetFirewallRule
```

LAN mode does not use HTTPS and must not be exposed to the internet. Passwords and sessions in this build are for testing; do not use real accounts.

## Catalogs and local files

Client catalogs in `data/*.json`, databases, profiles, logs, and experimental responses are not distributed. See [`data/README.md`](data/README.md). The `experiments/area-list-localhost.base64` fixture is included because it is a synthetic response created for local testing, not a capture from the original server.

The server starts without `data/local_free_purchase_catalog.json`; it prints a warning and uses an empty purchase catalog. Purchase claims then return `unknown_local_product` and grant no items. Supply a local catalog from a client copy you are authorized to inspect to enable catalog-backed local purchase rewards. Other systems that rely on excluded catalogs may return incomplete results.

## Components

- `server.py`: local HTTP routes.
- `ws_probe_server.py`: local WebSocket protocol handlers.
- `account_store.py`: accounts, hashed credentials, and test sessions.
- `mail_fixture.py`: synthetic mail state.
- `run_local_server.py`: local and LAN launcher.

The server implements only observed contracts or behavior clearly marked as synthetic; unsupported methods are rejected. Do not configure a public instance without completing authentication, encrypted transport, operational security, validation, and data review.

## License and APK

The original APK, modified APK, and recovered game assets are not included. No license has been assigned to this repository while rights to the code and client-derived data are under review. Do not add an open-source license or upload catalogs or binaries before that review is complete.

