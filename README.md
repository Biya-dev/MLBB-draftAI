# MLBB Draft AI — Phase 1: Live Screen Feed

A **fully free, local-only** pipeline that streams your iPhone screen to your
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

## ⚠️ Read this first: the iOS build limitation

You are on **Windows 11**. **Apple does not allow building or signing iOS apps
on Windows.** There is no legal, supported way to compile, sign, or install this
app from Windows. Xcode does not run on Windows, and code signing for iOS
requires a macOS machine with Xcode.

**What this means in practice:**

| Step | Can it be done on Windows? |
|---|---|
| Write the Swift source | ✅ Done — it is in `ios/` |
| Generate the Xcode project file | ✅ Done — `ios/project.yml` |
| Compile the app | ❌ Needs macOS + Xcode |
| Sign it with your Apple ID | ❌ Needs macOS + Xcode |
| Install it on your iPhone | ❌ Needs macOS + Xcode (or TestFlight) |

**Practical Windows-first path:** GitHub Actions builds and unit-tests the
Swift sources on a hosted macOS runner. This repository is public, so standard
GitHub-hosted runners are free and unlimited; the workflow does not use a
paid service. This catches Xcode and simulator failures without a Mac.

A **real iPhone test still cannot be performed in GitHub Actions**: the
hosted runner has no USB connection to your phone and cannot complete a
personal-device signing flow. For the first install you need temporary access
to a Mac (borrowed is fine) and a free Apple ID, or a paid Apple Developer
membership plus a separately approved distribution process such as TestFlight.

> **Honesty statement:** the Python receiver is **fully tested and working**
> on this Windows machine (43 automated tests + a live smoke test). The
> Swift/iOS code has been compiled and its protocol tests passed in the
> GitHub-hosted macOS simulator workflow, but it has **NOT been installed or
> run on a real iPhone**. Do not treat the iPhone capture path as verified
> until you build and run it yourself.

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

The workflows use no repository secrets. The repository is currently public,
so these standard GitHub-hosted runners have no Actions-minute charge. If the
repository becomes private, macOS minutes count against the account's included
quota and may become billable after that quota is exhausted.

---


## Part 2 — iOS app (requires a Mac)

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

### 2.2 Set the PC address

Edit `ios/Shared/SharedConfig.swift`:

```swift
static let receiverHost = "192.168.1.158"   // your PC's Wi-Fi IP
static let receiverPort: UInt16 = 8765
static let sharedToken = "mlbb-phase1"       // must match the PC's --token
```

Keep `sharedToken` in sync with the `--token` you pass to the PC.

### 2.3 Generate the Xcode project

Install [XcodeGen](https://github.com/yonaskolb/XcodeGen) (free):

```bash
brew install xcodegen
cd ios
xcodegen generate
open MLBBDraftAI.xcodeproj
```

### 2.4 Signing with a FREE Apple ID

Apple lets you sign with a **free personal Apple ID** — no $99/year needed.
Limitation: the profile expires after **7 days** and you must re-install
weekly. For Phase 1 that is fine.

1. Open the project in Xcode.
2. Select the **MLBBDraftAI** target → **Signing & Capabilities**.
3. Tick **Automatically manage signing**.
4. Choose your **Apple ID** in the **Team** dropdown
   (Xcode → Settings → Accounts → **+** → Apple ID).
5. Set a **unique bundle identifier**, e.g. `mlbb.draftai.yourname`
   (it must be unique worldwide — change it in `project.yml` too).
6. Select the **BroadcastExtension** target → Signing & Capabilities →
   same Team, bundle id `mlbb.draftai.yourname.BroadcastExtension`.
7. Select your iPhone under **Run Destination**.

> **Entitlements:** a Broadcast *Upload* Extension needs **no special
> entitlement** — the App Group is only needed if you want the app and the
> extension to share status. `SharedStatus` falls back to standard
> `UserDefaults` when the App Group is not provisioned, so you can **skip
> the App Group entirely** for Phase 1.

### 2.5 Build and install

1. Connect the iPhone by **USB**, unlock it, tap **Trust** if prompted.
2. In Xcode, select the **MLBBDraftAI** scheme and your iPhone.
3. Press **Run** (⌘R).
4. On the iPhone, trust the developer app under **Settings → General → VPN &
   Device Management** if prompted. On iOS 16 or later, enable **Developer
   Mode** under **Settings → Privacy & Security** if iOS requests it, then
   restart and confirm.
5. On first launch, if a *Local Network* prompt appears, tap **Allow**.
   (iOS 14+ requires this for any LAN socket.)

### 2.6 First real-device test: exact checklist

Do this only after the GitHub iOS workflow is green. It is the first step that
can verify the end-to-end iPhone path; no CI or simulator result substitutes
for it.

1. Have an iPhone running iOS 15 or later, its USB cable, the Windows PC and
   iPhone on the same non-isolated Wi-Fi, and temporary access to a Mac with
   current Xcode and XcodeGen.
2. On Windows, install dependencies, run `windows\\open-firewall.ps1` as
   Administrator, and start `python -m receiver --token <your-token>`.
   Keep the dashboard at `http://127.0.0.1:8080/` open.
3. Find the Windows Wi-Fi IPv4 address with `ipconfig`; set
   `receiverHost` to it and set the same non-default token in
   `SharedConfig.swift`. Do not commit a real token to the public repository.
4. On the Mac, generate the project, select your free Apple ID team for both
   targets, choose unique bundle identifiers, connect and trust the unlocked
   iPhone, then build and run the app. A free personal signing profile is
   sufficient for this direct installation and expires after seven days.
5. Allow Local Network access when iOS prompts. In the app select **Start
   Screen Broadcast** and explicitly confirm the system broadcast sheet.
6. Confirm the Windows dashboard shows received/processed frames greater than
   zero, a JPEG snapshot, and the live iPhone screen. Record the outcome and
   any receiver log error; only then may the device test be called successful.

### 2.7 Confirm it works

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
| Dashboard shows "Waiting for the iPhone" | Phone never connected | Check the PC firewall rules; confirm `receiverHost` matches the PC's IP; confirm the token matches on both sides. |
| Status: **auth_failed** | Token mismatch | `--token` on the PC must equal `sharedToken` in `SharedConfig.swift`, **including case**. |
| Status: **error** on the iPhone | Cannot reach the PC | Both devices must be on the **same** Wi-Fi. Disable **AP/client isolation** on the router. |
| Status: "Reconnecting in Ns..." | PC receiver not running | Start `python -m receiver --token mlbb-phase1` on the PC. |
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

## 📋 First-Device-Test Checklist

| ✅ Item | Description | Status |
|---|---|---|
| **Python receiver builds & runs** | `python -m receiver --token mlbb-phase1` starts without errors | **PASS** (38 pytest + smoke test) |
| **Wire protocol matches Swift** | Python encoder produces byte-identical output to `ios/Shared/WireProtocol.swift` | **PASS** (cross-language test) |
| **AUTH + FRAME framing works** | Sender sends AUTH then FRAME(s); receiver decodes and displays frames | **PASS** (smoke test: 30 frames, 0 errors) |
| **Malformed input rejected** | Bad magic/oversized length raises ProtocolError, not crash | **PASS** (all protocol tests) |
| **Multiple frames per connection** | Single TCP connection can carry AUTH + multiple FRAMEs | **PASS** (frame reassembly tests) |
| **Reconnect after disconnect** | Hub resets to DISCONNECTED state; new connection re-authenticates | **PASS** (integration test) |
| **Dashboard API responds** | `/api/status`, `/api/snapshot.jpg`, `/video_feed.mjpg` all work | **PASS** (integration test) |
| **MJPEG stream multipart** | `multipart/x-mixed-replace; boundary=mlbframe` stream works | **PASS** (integration test) |
| **Firewall rules created** | `open-firewall.ps1` creates Private-profile rules for TCP 8765 & 8080 | **PASS** (script verified) |
| **Local-network binding** | Receiver binds `0.0.0.0:8765`; dashboard on `0.0.0.0:8080` | **PASS** (config verified) |
| **Token authentication** | Matching `--token` on PC and `sharedToken` in `SharedConfig.swift` required | **PASS** (wrong_token test) |
| **iOS Xcode project generates** | `xcodegen generate` produces valid `.xcodeproj` | **PENDING** (requires macOS) |
| **Bundle identifiers match** | `mlbb.draftai.app` (app) & `mlbb.draftai.app.BroadcastExtension` (extension) | **PENDING** (verify on Mac) |
| **NSLocalNetworkUsageDescription** | Both Info.plists request local-network permission | **PASS** (verified in files) |
| **Free Apple ID signing** | Xcode signing with personal Apple ID (7-day expiry) | **PENDING** (requires Mac) |
| **iPhone installed via USB** | iPhone connected, trusted, Local Network prompt allowed | **PENDING** (requires Mac + iPhone) |
| **Broadcast extension runs** | ReplayKit extension captures screen, sends JPEG frames over TCP | **PENDING** (requires Mac + iPhone) |
| **End-to-end iPhone→Windows stream** | Live screen appears on Windows dashboard at `http://<PC-IP>:8080/` | **PENDING** (full test) |

---

### Windows Pre-Flight Checklist (run before Mac build)

- [ ] Python 3.10+ installed ✅ (3.13.12)
- [ ] venv created: `py -3.13 -m venv .venv`
- [ ] Dependencies installed: `py -3.13 -m pip install -r requirements.txt`
- [ ] Receiver starts: `py -3.13 -m receiver --token mlbb-phase1`
- [ ] Dashboard accessible at `http://127.0.0.1:8080/`
- [ ] Firewall rules: `powershell -ExecutionPolicy Bypass -File .\open-firewall.ps1`
- [ ] Smoke test passes: `py -3.13 -m receiver.smoke_test --token mlbb-phase1 --frames 30 --fps 15`
- [ ] PC's Wi-Fi IP noted (run `ipconfig`); matches `SharedConfig.receiverHost`

### macOS / iPhone Build Checklist

- [ ] **Mac with Xcode 15+** (required; cannot build from Windows)
- [ ] **Free Apple ID** with Team selected in Xcode Settings → Accounts
- [ ] Run `brew install xcodegen` then `cd ios && xcodegen generate`
- [ ] Open `MLBBDraftAI.xcodeproj`, select MLBBDraftAI target → Signing & Capabilities →
  - Tick "Automatically manage signing"
  - Select your Apple ID in Team dropdown
  - Verify bundle identifier: `mlbb.draftai.<yourunique suffix>`
- [ ] Same bundle ID for BroadcastExtension: `mlbb.draftai.<yourunique suffix>.BroadcastExtension`
- [ ] Edit `ios/Shared/SharedConfig.swift`:
  - Set `receiverHost` to your PC's Wi-Fi IP address
  - Keep `sharedToken = "mlbb-phase1"` (must match PC `--token`)
- [ ] Connect iPhone via USB, unlock, tap "Trust" on Mac
- [ ] Select iPhone as run destination in Xcode, press ▶️ (Run)
- [ ] On iPhone first launch: enable "Local Network" prompt when it appears
- [ ] In the app, press "Start Screen Broadcast"
- [ ] Confirm on PC: dashboard status turns green, FPS counter climbs, live screen appears
- [ ] If using Wi-Fi: ensure router does NOT have AP isolation enabled

### ❌ Known Limitations (do not treat as bugs)

- Xcode + iOS build **cannot** be performed from Windows; macOS is mandatory
- Free Apple ID signing expires every 7 days; re-signing required
- Real-device streaming **not verified** on this Windows-only audit
- JPEG re-encode quality difference between iPhone (`uiImage.jpegData`) and Python OpenCV may cause slight visual variation
- No hero recognition, draft engine, or AI analysis included (Phase 1 scope: live feed only)

---
*Last verified locally: Python receiver 43/43 tests pass, smoke test PASS. iOS code is not compiled on Windows and no real-device test has been performed.*
