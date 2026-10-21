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

## Free iOS testing from Windows

The public repository uses free, standard GitHub-hosted macOS runners to
compile the iOS app and run its simulator protocol tests. A manual workflow
can also package an **unsigned** iOS device IPA; install/signing is then
attempted locally on your Windows PC with AltStore/AltServer and a free Apple
Account. This avoids paid Apple membership, TestFlight, paid cloud services,
and a Mac. The hosted runner cannot connect to or test your iPhone.

| Step | Windows only |
|---|---|
| Edit Swift source | ✅ |
| Compile an unsigned device IPA on a hosted macOS runner | ✅ |
| Sign and install on Windows using a free Apple Account | ✅ Attempt with AltStore; Apple limitations apply |
| Verify ReplayKit screen capture on an actual iPhone | ❌ Requires you to install and test on your iPhone |

> **Testing boundary:** CI can compile the iOS targets, run protocol tests in
> a simulator, and verify the device IPA contains the broadcast extension.
> None of those checks proves ReplayKit captures or streams a real iPhone
> screen. Only the manual device test below can establish that.

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
* **Build unsigned iOS IPA for free sideloading** is manually started from
  Actions. It uses macOS to build an unsigned device IPA and verifies that
  the app, extension ID, and receiver address are packaged. It does not sign,
  install, or test on an iPhone.

No Apple credentials or repository secrets are used. GitHub documents
standard hosted runners as free and unlimited for public repositories; this
repository is public. If its visibility changes, check the account's Actions
quota and billing first.

---


## Part 2 — iOS app (free cloud build and Windows sideload)

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

### 2.2 Create the unsigned device IPA

1. Find the Windows PC's Wi-Fi IPv4 address with `ipconfig`.
2. In GitHub, open **Actions → Build unsigned iOS IPA for free sideloading
   → Run workflow**. Enter a unique reverse-DNS bundle ID, such as
   `com.yourname.mlbbdraftai`, and the PC IPv4 address.
3. Wait for the run to complete. Download the
   `MLBBDraftAI-unsigned-ipa` artifact from the run and extract the `.ipa`.
   The workflow builds the app and extension, checks that the extension is
   embedded with the expected bundle ID, and checks the receiver address in
   both Info.plists. The IPA is **not signed**.

### 2.3 Install and sign from Windows with a free Apple Account

The practical free route is [AltStore Classic](https://altstore.io/) with
[AltServer for Windows](https://faq.altstore.io/altstore-classic/how-to-install-altstore-windows.md).
It uses your free Apple Account to sign sideloaded apps. It does not require
TestFlight, paid Apple membership, or a Mac. AltStore is third-party software;
review its documentation and security model before entering your Apple
credentials.

1. Install iTunes and iCloud for Windows using AltStore's current Windows
   setup instructions. AltStore currently requires the versions downloaded
   directly from Apple rather than Microsoft Store versions.
2. Install AltServer, connect and trust your iPhone over USB, and follow
   AltStore's steps to install AltStore on the phone using your Apple Account.
3. On the iPhone, trust the developer profile if prompted. On iOS 16 and
   later, enable **Developer Mode** under **Settings → Privacy & Security**
   if requested.
4. In AltStore, use **My Apps → +** to select the downloaded IPA and allow
   AltStore/AltServer to sign and install it. The app includes a ReplayKit
   broadcast extension; the free Apple Account/AltStore provisioning path
   may reject this extension or its entitlements. If it does, there is no
   supported way to bypass that Apple restriction under these constraints.
5. Free personal provisioning expires after 7 days and has Apple limits on
   app IDs, devices, and simultaneously installed sideloaded apps. Keep
   AltServer available on the PC and follow AltStore's refresh instructions;
   reinstall/re-sign after expiry if refresh fails.

### 2.4 Verify ReplayKit on the real iPhone

CI and unsigned packaging cannot exercise the system ReplayKit broadcaster or
prove that a physical phone sends frames. Only perform this end-to-end check
after AltStore successfully installs the app:

1. On Windows, allow the receiver through the firewall using
   `windows\\open-firewall.ps1` as Administrator.
2. Start the receiver using the token embedded by this workflow:
   `python -m receiver --token mlbb-phase1`. Keep the dashboard open at
   `http://127.0.0.1:8080/`.
3. Put the iPhone and PC on the same non-isolated Wi-Fi. Launch the app, allow
   Local Network access, tap **Start Screen Broadcast**, choose **MLBB Screen
   Upload**, and confirm the iOS broadcast prompt.
4. Verify on the Windows dashboard that `frames_received` and
   `frames_processed` increase, a JPEG snapshot is present, and the live
   image updates. If no frames arrive, inspect the receiver's token/firewall
   output and verify the receiver IP embedded in this IPA.

Do not treat a successful simulator run, CI build, or AltStore installation
as proof of real-device capture. Record a successful device test only after
observing frames from the actual iPhone in the Windows dashboard.

---

## Part 3 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Dashboard shows "Waiting for the iPhone" | Phone never connected | Check the PC firewall rules; confirm the workflow's receiver-host input matches the PC's IP and the token matches on both sides. |
| Status: **auth_failed** | Token mismatch | Use `--token mlbb-phase1` on the PC to match the token embedded in this free-build IPA. |
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

---

## 📋 Verification status

| ✅ Item | Description | Status |
|---|---|---|
| **Windows receiver tests** | `pytest` and socket/dashboard smoke test | **PASS** (43 tests and smoke test, previously run locally) |
| **Swift protocol tests** | Shared protocol tests on GitHub-hosted iOS Simulator | **PASS** (8 tests, prior workflow run) |
| **Unsigned app and extension builds** | GitHub-hosted macOS compile-only build | **PASS** (prior workflow run) |
| **Unsigned device IPA workflow** | Package app and extension; verify IDs and receiver config | **PASS** (GitHub run 39565485591; unsigned artifact inspected on Windows) |
| **Real iPhone installation and broadcast** | Install via AltStore and stream to Windows receiver | **NOT RUN** |

---

### Windows Pre-Flight Checklist

- [ ] Python 3.10+ installed ✅ (3.13.12)
- [ ] venv created: `py -3.13 -m venv .venv`
- [ ] Dependencies installed: `py -3.13 -m pip install -r requirements.txt`
- [ ] Receiver starts with `python -m receiver --token mlbb-phase1`
- [ ] Dashboard accessible at `http://127.0.0.1:8080/`
- [ ] Firewall rules: `powershell -ExecutionPolicy Bypass -File .\open-firewall.ps1`
- [ ] PC's Wi-Fi IP noted (run `ipconfig`); use it for the workflow input

### ❌ Known Limitations (do not treat as bugs)

- The hosted macOS runner cannot connect directly to or test a physical iPhone
- AltStore may reject signing the ReplayKit extension under a free Apple Account; this must be tried on-device
- Free Apple Account provisioning expires after 7 days and is subject to Apple's app ID/device/app limits
- Real-device streaming has **not been verified**
- JPEG re-encode quality difference between iPhone (`uiImage.jpegData`) and Python OpenCV may cause slight visual variation
- No hero recognition, draft engine, or AI analysis included (Phase 1 scope: live feed only)

---
*Verified: Windows Python receiver 43/43 tests and smoke test passed; GitHub macOS build/test CI passed, and the unsigned device IPA was built and inspected. The IPA has not been installed on a phone, and no real-device ReplayKit test has been performed.*
