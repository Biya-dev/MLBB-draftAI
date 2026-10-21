# MLBB Draft AI — Phase 1: Live Screen Feed

A **local-only** pipeline that streams your iPhone screen to your
Windows PC over your own Wi-Fi, and shows it on a live dashboard.

```
 iPhone (ReplayKit Broadcast Upload Extension)
        │  TCP, JPEG frames, local Wi-Fi only
        ▼
 Windows PC  ──  Python + OpenCV receiver  ──►  FastAPI dashboard
                                                   http://PC-IP:8080/
```

**Phase 1 scope:** reliable live screen feed + dashboard + status/errors.
Hero recognition and draft recommendations are deliberately **not** included yet.

---

## iOS from Windows using cloud macOS

Apple's Xcode does not run on Windows, but GitHub Actions can build and sign
the app on a hosted macOS runner, upload it to TestFlight, and let you install
it on your iPhone. This supported TestFlight path requires Apple Developer
Program membership (currently US$99/year; price and availability vary by
region). The hosted runner cannot connect directly to your iPhone; TestFlight
is the hand-off for installation.

| Step | Windows only |
|---|---|
| Edit Swift source | ✅ |
| Compile and sign on a hosted macOS runner | ✅ With the manual TestFlight workflow |
| Install from TestFlight | ✅ |
| Connect Xcode to iPhone over USB from the runner | ❌ |

> **Honesty statement:** the Python receiver is **fully tested and working**
> on this Windows machine (43 automated tests + a live smoke test). The
> Swift/iOS code has been compiled and its protocol tests passed in the
> GitHub-hosted macOS simulator workflow, but it has **NOT been installed or
> run on a real iPhone**. TestFlight enables installation, but only a live
> device test verifies screen capture and streaming.

---


## Part 1 — Windows receiver (works today, fully tested)

### 1.1 Requirements

* Python 3.10+ — you have **3.13.12** ✅
* A private Wi-Fi network (your Wi-Fi profile is already `Private` ✅)

### 1.2 Install

```powershell
cd c:\Users\bijaya.chauhan\MLBB-draftAI\windows
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

All dependencies are free and open source: `opencv-python`, `numpy`,
`fastapi`, `uvicorn`.

### 1.3 Run the receiver

```powershell
python -m receiver --token mlbb-phase1
```

Expected banner:

```
================================================================
 MLBB Draft AI - Screen Receiver (Phase 1)
================================================================
 Dashboard : http://127.0.0.1:8080/
            http://192.168.1.158:8080/
 Ingest   : TCP 0.0.0.0:8765 (iPhone streams here)
 Token    : set
================================================================
```

Open **http://127.0.0.1:8080/** in your browser.

### 1.4 Windows Firewall (one time)

Open **PowerShell as Administrator** (right-click → *Run as administrator*):

```powershell
cd c:\Users\bijaya.chauhan\MLBB-draftAI\windows
.\open-firewall.ps1
```

This creates two **Private-profile-only** inbound rules:

| Port | Purpose |
|---|---|
| TCP **8765** | iPhone → PC screen frames |
| TCP **8080** | Browser → PC dashboard |

To undo: `.\open-firewall.ps1 -Remove`

<details>
<summary>Manual alternative (GUI)</summary>

1. `Win + R` → type `wf.msc` → Enter
2. **Inbound Rules** → **New Rule**
3. **Port** → TCP → Specific local ports: `8765, 8080` → Next
4. **Allow the connection** → Next
5. **Profile** → tick **Private** only → Next
6. **Name**: `MLBB Draft AI` → Finish
</details>

### 1.5 Verify the receiver without an iPhone

The receiver ships with a synthetic sender so you can prove the whole PC side
works before touching the iOS half:

```powershell
python -m receiver.smoke_test --token mlbb-phase1 --frames 30 --fps 15
```

Expected output:

```
[smoke] ingest port 59320
[smoke] stats: {'frames_received': 30, 'frames_processed': 30, 'frames_dropped': 0, 'decode_errors': 0}
[smoke] snapshot.jpg: 34632 bytes, header=b'\xff\xd8'
[smoke] RESULT: PASS
### 1.6 Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Expected: **43 passed**.

### 1.7 Continuous integration

GitHub Actions runs automatically on pushes and pull requests to `master`:

* **Python CI** runs the receiver tests on Python 3.10--3.13 and performs the
  socket + dashboard smoke test with ephemeral ports.
* **iOS Build & Swift Tests** uses a GitHub-hosted macOS runner to generate
  the Xcode project, compile both targets without signing, and run the Swift
  protocol tests in an available iOS Simulator. It is compile/simulator
  verification only--not a real-device test.
* **Build and Upload iOS App to TestFlight** is manually started after
  configuring Apple signing/API secrets. It signs and uploads the app to App
  Store Connect; it does not connect to or test an iPhone.

The existing build/test workflows require no secrets. The optional TestFlight
workflow requires the secrets described below. Check GitHub Actions usage
limits for the current repository/account.

---


## Part 2 — iOS app (cloud build and TestFlight)

### 2.1 Files

```
ios/
├── project.yml                      XcodeGen spec (generates the .xcodeproj)
├── Shared/
│   ├── SharedConfig.swift           PC address, port, token, FPS, quality
│   ├── SharedStatus.swift           extension → app status sharing
│   └── WireProtocol.swift           the wire format (must match Python)
├── MLBBDraftAI/                     container app
│   ├── AppModel.swift
│   ├── ContentView.swift
│   └── Info.plist
├── BroadcastExtension/              the screen capture extension
│   ├── BroadcastSampleHandler.swift ReplayKit capture + JPEG + send
│   ├── FrameSender.swift            TCP client with reconnect/backoff
│   └── Info.plist
└── BroadcastExtensionTests/
    └── WireProtocolTests.swift
```

### 2.2 One-time Apple setup

1. Enroll in the [Apple Developer Program](https://developer.apple.com/programs/)
   and accept the paid membership terms.
2. Choose a unique explicit bundle ID, for example
   `com.yourname.mlbbdraftai`. In Certificates, Identifiers & Profiles, create
   App IDs for that ID and its extension ID
   `com.yourname.mlbbdraftai.BroadcastExtension`.
3. In App Store Connect, create an iOS app record using the main bundle ID
   (SKU can be any unique label). The workflow uses version `1.0` and sets a
   new build number automatically on each run.
4. In App Store Connect → **Users and Access → Integrations → App Store
   Connect API**, create an API key with the **Admin** role so Xcode can
   manage signing assets and upload builds. Download its `.p8` file once and
   note the **Key ID**, **Issuer ID**, and your 10-character **Team ID**.
5. In this GitHub repository, open **Settings → Secrets and variables →
   Actions → New repository secret** and add:

   | Secret name | Value |
   |---|---|
   | `APPLE_TEAM_ID` | Apple Developer Team ID |
   | `APP_STORE_CONNECT_KEY_ID` | API key ID |
   | `APP_STORE_CONNECT_ISSUER_ID` | API issuer ID |
   | `APP_STORE_CONNECT_API_KEY` | Entire contents of the downloaded `.p8` file |
   | `IOS_SHARED_TOKEN` | A token of your choice; use the same value when starting the PC receiver |

   Do not commit the `.p8` file or token. The token is embedded in the app and
   can be extracted, so treat it as protection against accidental LAN
   connections, not as a high-security secret.

### 2.3 Build, upload, and install (no Mac required)

1. On Windows, start the receiver with the same token stored as
   `IOS_SHARED_TOKEN`, for example:

   ```powershell
   python -m receiver --token your-long-random-token
   ```

2. Find the PC's Wi-Fi IPv4 address with `ipconfig`.
3. Push the workflow changes to `master`. In GitHub, open **Actions → Build
   and Upload iOS App to TestFlight → Run workflow**. Enter the registered
   main bundle ID and PC IPv4 address, then start the run.
4. Wait for the run to finish successfully. App Store Connect may take several
   minutes to process the uploaded build.
5. In App Store Connect → **TestFlight**, add your Apple ID as an internal
   tester if it is not already an App Store Connect user. Accept the
   invitation on the iPhone, install Apple's **TestFlight** app, and install
   MLBB Draft AI from the invitation. Internal testing does not require public
   App Store review.
6. Keep the receiver running and phone on the same non-isolated Wi-Fi. Allow
   Local Network access, start the screen broadcast, and confirm frames reach
   the Windows dashboard. This is the first real-device validation; a hosted
   build or simulator test is not.

The workflow uses automatic Xcode signing with the App Store Connect API key.
It gives the app and upload extension matching bundle IDs, assigns a unique
build number, and keeps the signing key on the temporary hosted runner.

### 2.4 Alternative: build and install directly from a Mac

This alternative needs a Mac with Xcode and XcodeGen. Install XcodeGen:

```bash
brew install xcodegen
cd ios
xcodegen generate
open MLBBDraftAI.xcodeproj
```

### 2.5 Direct-device signing with a FREE Apple ID

Apple lets you sign with a **free personal Apple ID** — no $99/year needed.
Limitation: the profile expires after **7 days** and you must re-install
weekly. For Phase 1 that is fine.

This alternative requires access to a Mac; the cloud TestFlight path above
requires paid Apple Developer Program membership instead.

1. Open the project in Xcode.
2. Select the **MLBBDraftAI** target → **Signing & Capabilities**.
3. Tick **Automatically manage signing**.
4. Choose your **Apple ID** in the **Team** dropdown
   (Xcode → Settings → Accounts → **+** → Apple ID).
5. Set a **unique bundle identifier**, e.g. `com.yourname.mlbbdraftai`
   (it must be unique worldwide — set `APP_BUNDLE_ID` in `project.yml`).
6. Select the **BroadcastExtension** target → Signing & Capabilities →
   same Team, bundle ID `com.yourname.mlbbdraftai.BroadcastExtension`.
7. Select your iPhone under **Run Destination**.

> **Entitlements:** a Broadcast *Upload* Extension needs **no special
> entitlement** — the App Group is only needed if you want the app and the
> extension to share status. `SharedStatus` falls back to standard
> `UserDefaults` when the App Group is not provisioned, so you can **skip
> the App Group entirely** for Phase 1.

### 2.6 Build and install from Xcode

1. Connect the iPhone by **USB**, unlock it, tap **Trust** if prompted.
2. In Xcode, select the **MLBBDraftAI** scheme and your iPhone.
3. Press **Run** (⌘R).
4. On the iPhone, trust the developer app under **Settings → General → VPN &
   Device Management** if prompted. On iOS 16 or later, enable **Developer
   Mode** under **Settings → Privacy & Security** if iOS requests it, then
   restart and confirm.
5. On first launch, if a *Local Network* prompt appears, tap **Allow**.
   (iOS 14+ requires this for any LAN socket.)

### 2.7 First real-device test: exact checklist

This is the first step that verifies the end-to-end iPhone path; no CI or
simulator result substitutes for it.

1. Have an iPhone running iOS 15 or later, the Windows PC, and both on the
   same non-isolated Wi-Fi. A Mac is not needed for the TestFlight path.
2. On Windows, install dependencies, run `windows\\open-firewall.ps1` as
   Administrator, and start `python -m receiver --token <your-token>`.
   Keep the dashboard at `http://127.0.0.1:8080/` open.
3. Find the Windows Wi-Fi IPv4 address with `ipconfig`. For TestFlight, enter
   it in the workflow run and use the same token as the `IOS_SHARED_TOKEN`
   GitHub secret and the PC receiver. For a direct Xcode build, set
   `MLBB_RECEIVER_HOST` and `MLBB_SHARED_TOKEN` in `project.yml`.
4. Install the uploaded build from TestFlight, or use the direct Xcode
   installation steps above.
5. Allow Local Network access when iOS prompts. In the app select **Start
   Screen Broadcast** and explicitly confirm the system broadcast sheet.
6. Confirm the Windows dashboard shows received/processed frames greater than
   zero, a JPEG snapshot, and the live iPhone screen. Record the outcome and
   any receiver log error; only then may the device test be called successful.

### 2.8 Confirm it works

1. On the PC, open **http://127.0.0.1:8080/**
2. The **Status** pill should turn **green** and the FPS counter should climb.
3. Your iPhone screen appears in the **Live Screen** panel.

---

**iOS deliberately requires the user to start screen sharing.** There is no
programmatic way around this — it is an OS privacy guarantee.

**A. From the app (recommended)**
1. Open **MLBB Draft AI**.

## Part 3 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Dashboard shows "Waiting for the iPhone" | Phone never connected | Check the PC firewall rules; confirm the workflow's receiver-host input matches the PC's IP and the token matches on both sides. |
| Status: **auth_failed** | Token mismatch | The PC's `--token` must match the `IOS_SHARED_TOKEN` GitHub secret used by the installed build, **including case**. |
| Status: **error** on the iPhone | Cannot reach the PC | Both devices must be on the **same** Wi-Fi. Disable **AP/client isolation** on the router. |
| Status: "Reconnecting in Ns..." | PC receiver not running | Start `python -m receiver --token <your-token>` on the PC. |
| Black / frozen image | Extension throttling too low | Raise `SharedConfig.targetFPS` to 20–30. |
| Very laggy video | Too much data | Lower `targetFPS` to 8–10 or `maxFrameWidth` to 854. |
| "Local Network" prompt denied | iOS local-network privacy | Settings → Privacy → **Local Network** → enable **MLBB Draft AI**. |
| Extension not listed in the picker | Extension not embedded | Verify the app target depends on the extension and it is embedded in the app bundle. |
| Swift protocol-test linker error | Test target config | `BroadcastExtensionTests` compiles the shared `WireProtocol.swift` directly; regenerate the project with `xcodegen generate`. |

### Quick network sanity check (Windows)

```powershell
Get-NetFirewallRule -DisplayName "MLBB Draft AI*" | Format-Table DisplayName, Enabled, Profile
```

---

## Performance limits (tuned in `SharedConfig.swift`)

| Setting | Default | Purpose |
|---|---|---|
| `targetFPS` | 12 | Keeps Wi-Fi usage low; ~25–60 KB/s |
| `maxFrameWidth` | 1280 | iPhone frames are 1170–1290 px wide; scaling saves bandwidth |
| `jpegQuality` | 0.6 | Good enough for a dashboard |
| `maxPayload` (Python) | 4 MiB | Guard against malformed length fields |
| `initialReconnectDelay` | 1 s | First retry after a drop |
| `maxReconnectDelay` | 15 s | Backoff ceiling |
| `connectTimeout` | 8 s | Give up on a silent connect attempt |

---

## Security & privacy

* **Local only.** The receiver binds to your LAN. No cloud service, no
  telemetry, no analytics, no external API.
* **Token auth.** An optional shared token is sent as the first frame; the
  receiver rejects the stream if it does not match.
* **Explicit consent.** iOS shows a system prompt and a red recording
  indicator. The app cannot capture the screen without this.
* **Firewall scoped to Private networks only.**
* **Plain TCP.** Traffic is not encrypted. Acceptable on a home Wi-Fi you
  trust; do not use it on public networks. *(TLS can be added in Phase 2.)*

---

## Protocol reference

Both sides implement the same framing (`ios/Shared/WireProtocol.swift` and
`windows/receiver/protocol.py`):

```
+--------+--------+---------+-----------------------+
| magic  | type   | length  | payload               |
| 4 B    | 1 B    | 4 B     | `length` bytes        |
+--------+--------+---------+-----------------------+
  "MLB1"  0x01 = AUTH (token)
          0x02 = FRAME (JPEG)
```

All multi-byte integers are **big-endian**. Length-prefixed framing means a
partial frame is never mistaken for a complete one, and the magic bytes let
the receiver resynchronise.

`windows/tests/test_cross_language.py` contains a Python port of the Swift
encoder and asserts the two produce **byte-identical** output — run it after
any change to either side.

---

## Phase 2 roadmap (not implemented)

* Hero detection (OpenCV template matching or a small ONNX model)
* Draft state machine + recommendation engine
* Region-of-interest cropping of the hero picker
* Optional TLS + reconnect-with-resume
* Screen recording to disk for replay

2. Tap **Start Screen Broadcast**.
3. In the sheet, pick **MLBB Screen Upload** → **Start Broadcast**.
4. Confirm **Start Broadcast** in the system dialog.

**B. From Control Center**
1. Swipe down from the top-right → tap the **Screen Recording** button.
2. Pick **MLBB Screen Upload** → **Start Broadcast**.

A red pill appears in the status bar while broadcasting.

---

## 📋 Verification status

| ✅ Item | Description | Status |
|---|---|---|
| **Windows receiver tests** | `pytest` and socket/dashboard smoke test | **PASS** (43 tests and smoke test, previously run locally) |
| **Swift protocol tests** | Shared protocol tests on GitHub-hosted iOS Simulator | **PASS** (8 tests, prior workflow run) |
| **Unsigned app and extension builds** | GitHub-hosted macOS compile-only build | **PASS** (prior workflow run) |
| **Cloud TestFlight workflow** | Signed archive and App Store Connect upload | **PENDING** (requires Apple membership and repository secrets) |
| **Real iPhone installation and broadcast** | Install from TestFlight and stream to Windows receiver | **NOT RUN** |

---

### Windows Pre-Flight Checklist

- [ ] Python 3.10+ installed ✅ (3.13.12)
- [ ] venv created: `py -3.13 -m venv .venv`
- [ ] Dependencies installed: `py -3.13 -m pip install -r requirements.txt`
- [ ] Receiver starts with the same token as GitHub's `IOS_SHARED_TOKEN` secret
- [ ] Dashboard accessible at `http://127.0.0.1:8080/`
- [ ] Firewall rules: `powershell -ExecutionPolicy Bypass -File .\open-firewall.ps1`
- [ ] PC's Wi-Fi IP noted (run `ipconfig`); use it for the workflow input

### TestFlight Release Checklist

- [ ] Paid Apple Developer Program membership active
- [ ] App and `.BroadcastExtension` App IDs and an App Store Connect app record created
- [ ] Five required GitHub Actions secrets configured (see section 2.2)
- [ ] `master` contains the TestFlight workflow
- [ ] Manual workflow run succeeds and build finishes App Store Connect processing
- [ ] TestFlight invitation accepted and app installed on the iPhone
- [ ] Real-device broadcast verified against the Windows dashboard

### macOS / iPhone Build Checklist

- [ ] A Mac is needed only for the optional direct Xcode installation path
- [ ] For cloud installation, follow **2.2 One-time Apple setup** and **2.3 Build, upload, and install**

### ❌ Known Limitations (do not treat as bugs)

- Cloud TestFlight installation requires paid Apple Developer Program membership
- The hosted macOS runner cannot connect directly to or test a physical iPhone
- Direct installation with a free Apple ID requires a Mac and expires every 7 days
- Real-device streaming has **not been verified**
- JPEG re-encode quality difference between iPhone (`uiImage.jpegData`) and Python OpenCV may cause slight visual variation
- No hero recognition, draft engine, or AI analysis included (Phase 1 scope: live feed only)

---
*Last verified locally: Python receiver 43/43 tests passed and smoke test passed. The prior hosted macOS workflow built the iOS targets and passed 8 simulator tests; no real-device test has been performed.*
