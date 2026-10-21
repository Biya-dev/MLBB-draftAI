import ReplayKit
import SwiftUI
import UIKit

/// Main screen. The only real action is starting a broadcast, which iOS
/// requires the user to trigger explicitly.
struct ContentView: View {

    @EnvironmentObject private var model: AppModel

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {

                    section("Receiver") {
                        LabeledRow(label: "PC address",
                                   value: "\(SharedConfig.receiverHost):\(SharedConfig.receiverPort)")
                        LabeledRow(label: "Auth token",
                                   value: SharedConfig.sharedToken.isEmpty
                                         ? "(none)" : "configured")
                        LabeledRow(label: "Max frame width",
                                   value: "\(SharedConfig.maxFrameWidth) px")
                        LabeledRow(label: "Target rate",
                                   value: "\(Int(SharedConfig.targetFPS)) FPS")
                    }

                    section("Screen Broadcast") {
                        Text("iOS only shares your screen while a broadcast is running. Press the button below, then confirm in the sheet. You can also start it from Control Center > Screen Recording.")
                            .font(.footnote)
                            .foregroundColor(.secondary)
                            .fixedSize(horizontal: false, vertical: true)

                        BroadcastPickerButton()
                            .frame(maxWidth: .infinity)
                            .frame(height: 44)
                    }

                    section("Status") {
                        HStack(spacing: 8) {
                            Circle()
                                .fill(statusColor)
                                .frame(width: 10, height: 10)
                            Text(model.status)
                                .font(.callout)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Text("Updated \(model.lastUpdate.formatted(date: .omitted, time: .standard))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    section("Next steps") {
                        step("1", "On the PC run: python -m receiver --token \(SharedConfig.sharedToken)")
                        step("2", "Open http://\(SharedConfig.receiverHost):8080/")
                        step("3", "Start the broadcast here and confirm in the sheet")
                        step("4", "Watch the live screen appear on the PC dashboard")
                    }

                }
                .padding(16)
            }
            .navigationTitle("MLBB Draft AI")
        }
    }

    private var statusColor: Color {
        if model.statusIsStale { return .gray }
        if model.status.lowercased().contains("error") { return .red }
        if model.status.lowercased().contains("connected") { return .green }
        return .orange
    }

    // -- small view helpers ----------------------------------------------
    @ViewBuilder
    private func section<Content: View>(
        _ title: String, @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.headline)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(12)
    }

    @ViewBuilder
    private func step(_ number: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(number)
                .font(.caption.bold())
                .frame(width: 20, height: 20)
                .background(Color.accentColor.opacity(0.2))
                .clipShape(Circle())
            Text(text)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// Apple's broadcast picker bridged into SwiftUI. Tapping it remains an
/// explicit user action, as required by ReplayKit's privacy model.
struct BroadcastPickerButton: UIViewRepresentable {
    func makeUIView(context: Context) -> RPSystemBroadcastPickerView {
        let picker = RPSystemBroadcastPickerView(frame: .zero)
        let bundleID = Bundle.main.bundleIdentifier ?? "mlbb.draftai.app"
        picker.preferredExtension = bundleID + ".BroadcastExtension"
        picker.showsMicrophoneButton = false
        return picker
    }

    func updateUIView(_ uiView: RPSystemBroadcastPickerView, context: Context) {}
}

/// A label / value row.
struct LabeledRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label).foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.system(.callout, design: .monospaced))
                .multilineTextAlignment(.trailing)
        }
        .font(.callout)
    }
}
