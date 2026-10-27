# LeBian Asset Mirrors and Recovery

## What is available

The recovered files are **not one standard Android `.obb` expansion file**. For client build 1.1.0.96 / version 153, LeBian streams individual Cocos resources under `assets/res/`. The supplied XAPK contains the base package and a `NewAssets.apk` split; the LeBian index describes additional files absent from those APKs.

The `assets/lbresinfo` index supplies each resource path, expected byte size, and CRC32. The package's `assets/tryflag` supplies the versioned publication prefix. Use those values from the same XAPK; do not guess prefixes for other versions.

## Public mirrors

The client and recovery logs identify these static fallback hosts:

- Primary: `rcdnaws.loveota.net`
- Fallback: `rcdnukd.loveota.net`

For the version 153 package examined here, a resource URL follows this pattern:

```text
http://<mirror>/<first-line-of-assets/tryflag>/<path-from-lbresinfo>
```

The tested prefix was `gameres/trialres/800643/153/aab10b12520b3c6598639a04e5dc4121/`. On 2026-10-17, a single one-byte HTTP Range request to the same small indexed JSON resource returned `206 Partial Content` from each mirror. Earlier preservation runs recovered and integrity-checked all 4,215 indexed resources from the primary mirror. These observations show the endpoints served the tested paths at those times; they do not guarantee future availability.

The exact 4,540-byte sample route used for the current mirror check was:

```text
http://rcdnaws.loveota.net/gameres/trialres/800643/153/aab10b12520b3c6598639a04e5dc4121/assets/res/import/7f/7f76450f-3725-4050-a617-83ab94337d40.json
http://rcdnukd.loveota.net/gameres/trialres/800643/153/aab10b12520b3c6598639a04e5dc4121/assets/res/import/7f/7f76450f-3725-4050-a617-83ab94337d40.json
```

The LeBian domain resolver was also observed returning `www.g.cn` instead of a usable asset host. The recovery scripts therefore use the two static fallback hostnames identified in the client, and construct requests only for exact paths in the supplied index.

## Reproduce the recovery locally

Python 3.10 or later is required. No APK, resource bundle, index, or extracted game data is included in this repository. Use an XAPK you are authorized to inspect. The analyzer expects an XAPK containing `com.oversea.spinarena.apk` and `NewAssets.apk`.

First, generate a local index and extract the version prefix:

```powershell
python project/backend_local/tools/analyze_lebian_stream.py `
  'D:\Preservation\SpiralWarrior.xapk' `
  --output 'D:\Preservation\index'
```

This writes `lebian_stream_resource_index.csv`, `tryflag.txt`, a path inventory, and a summary under the chosen output directory. Those generated files are local analysis data; do not commit them.

Start with a small, slower sample:

```powershell
python project/backend_local/tools/download_streamed_resources.py `
  --index 'D:\Preservation\index\lebian_stream_resource_index.csv' `
  --tryflag 'D:\Preservation\index\tryflag.txt' `
  --output-dir 'D:\Preservation\recovered' `
  --max-files 4 --workers 1 --interval 1.0
```

After confirming the sample is correct, run the full indexed recovery:

```powershell
python project/backend_local/tools/download_streamed_resources.py `
  --index 'D:\Preservation\index\lebian_stream_resource_index.csv' `
  --tryflag 'D:\Preservation\index\tryflag.txt' `
  --output-dir 'D:\Preservation\recovered' `
  --workers 2 --interval 0.5
```

The downloader is restricted to indexed `assets/res/` JSON, MP3, PKM, and PNG paths. It uses at most two workers, spaces request starts by at least half a second by default, retries each host a limited number of times, honors `Retry-After`, resumes `.part` files when Range requests are accepted, and checks the indexed size and CRC32 before promoting a file. Valid existing files are re-used. It writes files under `resources/assets/res/` and a recovery log, manifest, and percentage summary under `reports/` in the selected output directory.

CRC32 checks accidental corruption against the package index; it is not a cryptographic authenticity proof. The downloader also records SHA-256 for local comparison, but the original index does not contain authoritative SHA-256 values for the missing files.

## Findings for the examined build

For version 153, the index identified 4,215 absent resources totaling 562,138,078 bytes (about 536 MiB). They include JSON metadata, MP3 audio, PKM textures, and PNG images. Re-run the analyzer for another XAPK and use its own index and `tryflag`; counts and paths may differ by version.

Unauthenticated public retrieval does not itself grant permission to redistribute game assets. Keep recovered files and generated indexes outside this repository unless you have confirmed the relevant rights. The scripts deliberately do not enumerate paths or fetch anything outside the supplied index.
