import SwiftUI

struct SidebarFooterView: View {
    @ObservedObject private var interfaceLanguage = LanguageSettings.shared
    var openAbout: () -> Void
    @EnvironmentObject private var appearance: AppearanceSettings
    @EnvironmentObject private var updateChecker: UpdateChecker
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var showsAppearancePicker = false
    @State private var showsLanguagePicker = false
    @State private var isAboutHovered = false

    private var availableUpdate: AvailableUpdate? {
        if case let .available(update) = updateChecker.state { return update }
        return nil
    }

    var body: some View {
        let _ = interfaceLanguage.language
        VStack(alignment: .leading, spacing: 7) {
            aboutButton
            appearanceButton
            languageButton
                .padding(.bottom, 7)
            CaptureStatusView()
                .font(.system(size: 12))
                .labelStyle(SidebarFooterLabelStyle())
                .padding(.horizontal, 10)
            Text(L10n.tr("任务随时可用 · 数据保存在本机"))
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 10)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
    }

    private var languageButton: some View {
        Button {
            showsAppearancePicker = false
            showsLanguagePicker.toggle()
        } label: {
            HStack(spacing: 0) {
                Label {
                    Text(interfaceLanguage.language.nativeName)
                } icon: {
                    Image(systemName: "globe")
                        .foregroundStyle(Color.accentColor)
                }
                    .labelStyle(SidebarFooterLabelStyle())
                Spacer(minLength: 4)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(.secondary)
            }
            .font(.system(size: 12))
            .foregroundStyle(.primary)
            .padding(.horizontal, 10)
            .padding(.vertical, 9)
            .background(Color.primary.opacity(0.045), in: RoundedRectangle(cornerRadius: 8))
            .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .popover(isPresented: $showsLanguagePicker, arrowEdge: .top) {
            languagePicker
        }
        .accessibilityIdentifier("sidebar-language-picker")
        .accessibilityLabel(L10n.tr("界面语言"))
        .accessibilityValue(interfaceLanguage.language.nativeName)
        .help(L10n.tr("切换中英文，任务内容保持原文。"))
    }

    private var languagePicker: some View {
        SettingsPopoverOptions(title: L10n.tr("语言"), options: AppLanguage.allCases,
                               selection: interfaceLanguage.language, optionTitle: { $0.nativeName }) { language in
            showsLanguagePicker = false
            interfaceLanguage.select(language, reduceMotion: reduceMotion)
        }
        .frame(width: interfaceLanguage.language == .english ? 220 : 170)
    }

    private var aboutButton: some View {
        Button {
            showsAppearancePicker = false
            showsLanguagePicker = false
            openAbout()
        } label: {
            HStack(spacing: 0) {
                Label(L10n.tr("关于 Toccata"), systemImage: "info.circle")
                    .labelStyle(SidebarFooterLabelStyle())
                    .foregroundStyle(.primary)
                Spacer(minLength: 4)
                if let update = availableUpdate {
                    // A quiet beacon: a newer release is waiting in About.
                    Circle()
                        .fill(Color.orange)
                        .frame(width: 7, height: 7)
                        .shadow(color: Color.orange.opacity(0.55), radius: 2.5)
                        .padding(.trailing, 6)
                        .transition(.scale.combined(with: .opacity))
                        .accessibilityLabel(L10n.tr("发现新版本 v\(update.version)"))
                }
                Text(AppVersion.current.displayVersion)
                    .font(.system(size: 11))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            .animation(reduceMotion ? nil : WorkspaceMotion.sidebarSelectionFade,
                       value: updateChecker.state)
            .font(.system(size: 12))
            .lineLimit(1)
            .padding(.horizontal, 10)
            .padding(.vertical, 9)
            .background(Color.primary.opacity(isAboutHovered ? 0.055 : 0),
                        in: RoundedRectangle(cornerRadius: 8))
            .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .onHover { isAboutHovered = $0 }
        .accessibilityIdentifier("sidebar-about-toccata")
        .accessibilityLabel(L10n.tr("关于 Toccata"))
        .accessibilityValue(availableUpdate.map {
            L10n.tr("\(AppVersion.current.displayVersion)，发现新版本 v\($0.version)")
        } ?? AppVersion.current.displayVersion)
        .help(availableUpdate.map { L10n.tr("发现新版本 v\($0.version)，点击查看更新") }
              ?? L10n.tr("查看版本信息与检查更新"))
    }

    private var appearanceButton: some View {
        Button {
            showsLanguagePicker = false
            showsAppearancePicker.toggle()
        } label: {
            HStack(spacing: 0) {
                Label {
                    Text(appearance.mode.title)
                } icon: {
                    Image(systemName: "circle.lefthalf.filled")
                        .foregroundStyle(Color.accentColor)
                }
                    .labelStyle(SidebarFooterLabelStyle())
                Spacer(minLength: 4)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(.secondary)
            }
            .font(.system(size: 12))
            .foregroundStyle(.primary)
            .padding(.horizontal, 10)
            .padding(.vertical, 9)
            .background(Color.primary.opacity(0.045), in: RoundedRectangle(cornerRadius: 8))
            .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .popover(isPresented: $showsAppearancePicker, arrowEdge: .top) {
            appearancePicker
        }
        .accessibilityLabel(L10n.tr("外观模式"))
        .accessibilityValue(appearance.mode.title)
        .help(L10n.tr("切换月之亮面、月之暗面或跟随系统"))
    }

    private var appearancePicker: some View {
        SettingsPopoverOptions(title: L10n.tr("外观"), options: AppearanceMode.allCases,
                               selection: appearance.mode, optionTitle: { $0.title }) { mode in
            showsAppearancePicker = false
            appearance.mode = mode
        }
        .frame(width: interfaceLanguage.language == .english ? 220 : 170)
    }

}

private struct SidebarFooterLabelStyle: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 8) {
            configuration.icon.frame(width: 16, alignment: .leading)
            configuration.title
        }
    }
}
