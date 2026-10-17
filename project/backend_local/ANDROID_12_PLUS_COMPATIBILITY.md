# Android 12+ Compatibility: LeBian Startup Workaround

## Scope of the finding

The confirmed reproduction is narrow: Spiral Warrior 1.1.0.96 (client version 153) on LDPlayer running Android 14 / API 34 with the x86_64 ABI. In that setup, the original package crashed in LeBian's native `AssetRedirector.init()` during `attachBaseContext`, before Cocos initialized. A test copy with LeBian disabled passed that crash point and reached the Cocos startup path.

This is a tested workaround for that environment, not proof that every Android 12+ failure has the same cause. Android 12/13, physical ARM64 devices, and other emulator configurations still need their own runs.

## The setting

In the base APK, open `assets/lebian/globalSettings.xml`. The original setting is:

```xml
<setting key="use_lebian" value="true"/>
```

For a test build, change only that value to `false`:

```xml
<setting key="use_lebian" value="false"/>
```

The XML comment identifies this as LeBian's SDK-wide switch. The Android 14 test log reported `USE_LEBIAN=false`; the `AssetRedirector` SIGSEGV did not recur, and the process proceeded to Cocos initialization.

## Resource loading must be handled separately

Turning LeBian off also removes its normal streaming and cache bridge. In the tested build, `LebianGetResCachePath()` returned an empty path with this flag disabled. Simply changing the XML can therefore leave Cocos unable to locate streamed files and can produce a black screen or missing-resource errors.

The successful test paired the flag change with two additional conditions:

1. The version 153 resource set was present in the app's private LeBian cache tree:

   ```text
   /data/user/0/com.oversea.spinarena/lebian/cacheFiles/com.oversea.spinarena-153/assets/
   ```

2. The patched Cocos `main.js` added the real resource root to `jsb.fileUtils.getSearchPaths()`. When the LeBian bridge returned no path, the test build derived the app's writable root and used the versioned cache path as a fallback.

The cache suffix and location are package-specific. For another build, inspect the installed app's actual resource root and derive the path from that package; do not copy `153` blindly. Resources can instead be bundled or provisioned through another controlled local mechanism, but the final client must still resolve them before loading the first scene.

## Safe test procedure

1. Preserve the original APK, any original split APKs, and the reserved backup. Make a separate working copy and back up test-device app data before replacing or uninstalling anything.
2. Confirm whether the installation is a single APK or a split package. `globalSettings.xml` is in the base APK. If the package uses splits, rebuild the complete set and sign all APKs with the same test key; do not mix a modified base with an original split signed by another key.
3. Change only `use_lebian` in the working copy, rebuild and sign it, and install that matching build set on the test device.
4. Provide the required game resources in the expected version-specific location, then patch the Cocos search path fallback if LeBian no longer supplies it.
5. Start from a cold launch with Frida detached. Check logcat for `USE_LEBIAN=false`, confirm the LeBian native crash is absent, and verify Cocos loads `Login.fire` and reaches `LoginScene onLoad!`.
6. Re-run the test on each Android version and ABI you intend to support. Record whether the login flow and later scenes work; reaching the login scene alone does not prove authentication or gameplay.

## What the workaround changes

Disabling LeBian bypassed the observed native startup crash in the tested emulator, but it also disables LeBian SDK behavior such as its normal resource streaming/update path. A compatible SDK update remains the cleaner long-term fix. The workaround does not rely on changing `targetSdkVersion` or granting broad storage permissions; those changes were not shown to fix this crash.

Treat this as a compatibility patch for a controlled preservation build. Keep the original package untouched, keep the patch reproducible, and verify the actual cache path and scene load on the target device before calling it fixed.
