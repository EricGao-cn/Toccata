import AppKit
import SwiftUI

@MainActor
final class DailyNotesNavigation: ObservableObject {
    static let shared = DailyNotesNavigation()
    @Published var requestedDay: String?
}

@MainActor
struct DailyNoteDocumentEditor: View {
    @ObservedObject private var notes = DailyNotesStore.shared
    let day: String
    var compact = false
    var focusRequest: UUID?
    @State private var command: DailyNoteEditorCommand?

    var body: some View {
        VStack(spacing: 0) {
            if let error = notes.errors[day] ?? notes.scanError {
                VStack(alignment: .leading, spacing: 7) {
                    Text(error).font(.caption).textSelection(.enabled)
                    HStack {
                        if notes.conflicts.contains(day) {
                            Button(L10n.tr("保留我的版本")) { notes.resolveConflict(day, keepLocal: true) }
                            Button(L10n.tr("采用文件版本")) { notes.resolveConflict(day, keepLocal: false) }
                        } else {
                            Button(L10n.tr("重试")) { notes.refresh(); notes.load(day); _ = notes.save(day) }
                        }
                    }
                    .controlSize(.small)
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.orange.opacity(0.12))
            }
            HStack(spacing: compact ? 8 : 14) {
                Button { command = DailyNoteEditorCommand(action: .insertTime, day: day) } label: {
                    Label(L10n.tr("插入时间"), systemImage: "clock")
                }
                Button { command = DailyNoteEditorCommand(action: .end, day: day) } label: {
                    Label(L10n.tr("跳到末尾"), systemImage: "arrow.down.to.line")
                }
                Spacer(minLength: 0)
                Text(status).foregroundStyle(.secondary)
                    .accessibilityLabel(L10n.tr("记录保存状态"))
                    .accessibilityValue(status)
            }
            .buttonStyle(.borderless)
            .font(.system(size: compact ? 10 : 12))
            .padding(.horizontal, compact ? 12 : 16)
            .padding(.vertical, 9)
            if let document = notes.documents[day] {
                DailyNoteTextEditor(text: Binding(
                    get: { notes.documents[day]?.text ?? document.text },
                    set: { notes.update(day, text: $0) }
                ), day: day, surface: compact ? "menu" : "workbench", focusRequest: focusRequest, command: command, fontSize: compact ? 13 : 14)
                .id(day)
                .overlay(alignment: .topLeading) {
                    if document.text.isEmpty {
                        Text(L10n.tr("记下刚才做的、想到的……"))
                            .foregroundStyle(.tertiary).font(.system(size: compact ? 13 : 14))
                            .padding(.leading, 13).padding(.top, 10).allowsHitTesting(false)
                    }
                }
            } else {
                Spacer()
                Text(L10n.tr("正在读取记录…")).foregroundStyle(.secondary)
                Spacer()
            }
        }
        .task(id: day) { notes.load(day) }
        .onDisappear { _ = notes.savePendingDrafts() }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didResignActiveNotification)) { _ in
            _ = notes.savePendingDrafts()
        }
    }

    private var status: String {
        if notes.errors[day] != nil { return L10n.tr("未保存") }
        if notes.documents[day]?.isDirty == true { return L10n.tr("保存中…") }
        return notes.documents[day]?.diskData == nil ? L10n.tr("输入后保存") : L10n.tr("已保存")
    }
}

@MainActor
struct DailyNotesWorkspaceView: View {
    @ObservedObject private var notes = DailyNotesStore.shared
    @ObservedObject private var language = LanguageSettings.shared
    @Binding var selectedDay: String
    var canReturnToReview = false
    var onReturnToReview: () -> Void = {}
    @State private var showsCalendar = false
    @State private var displayedMonth = Date()
    @State private var referenceDate = Date()

    private var today: String { DailyNoteDate.key(referenceDate) }
    private var days: [String] { Set(notes.recordedDays + [selectedDay, today]).sorted(by: >) }

    var body: some View {
        let _ = language.language
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 0) {
                Text(L10n.tr("每日记录")).font(.headline).padding(.horizontal, 16).padding(.top, 20)
                HStack {
                    Button {
                        displayedMonth = DailyNoteDate.date(selectedDay) ?? Date()
                        showsCalendar.toggle()
                    } label: {
                        HStack(spacing: 5) {
                            Text(L10n.monthTitle(DailyNoteDate.date(selectedDay) ?? Date(), calendar: .current))
                            Image(systemName: "chevron.down").font(.caption2)
                        }
                    }
                    .buttonStyle(.borderless)
                    .popover(isPresented: $showsCalendar, arrowEdge: .bottom) {
                        DailyNotesMonthPicker(displayedMonth: $displayedMonth, selectedDay: selectedDay,
                                              recordedDays: Set(notes.recordedDays), today: referenceDate) { day in
                            select(day)
                            showsCalendar = false
                        }
                    }
                    Spacer(minLength: 3)
                    Button(L10n.tr("今天")) { select(today) }.buttonStyle(.borderless)
                }
                .font(.system(size: 12)).padding(16)
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 4) {
                            ForEach(days, id: \.self) { day in
                                Button { select(day) } label: {
                                    VStack(alignment: .leading, spacing: 5) {
                                        Text(dayTitle(day)).font(.system(size: 13, weight: .medium))
                                        Text(notes.documents[day]?.summary.isEmpty == false ? notes.documents[day]!.summary : L10n.tr("尚未填写"))
                                            .font(.system(size: 11)).foregroundStyle(.secondary).lineLimit(1)
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading).padding(10)
                                    .background(day == selectedDay ? Color.accentColor.opacity(0.12) : Color.clear, in: RoundedRectangle(cornerRadius: 7))
                                }
                                .buttonStyle(.plain)
                                .accessibilityAddTraits(day == selectedDay ? .isSelected : [])
                                .id(day)
                            }
                        }.padding(.horizontal, 8)
                    }
                    .onChange(of: selectedDay) { day in proxy.scrollTo(day) }
                }
                Divider()
                Button { notes.openFolder() } label: { Label(L10n.tr("打开记录文件夹"), systemImage: "folder") }
                    .buttonStyle(.borderless).font(.caption).padding(14)
            }
            .frame(width: 215)
            Divider()
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(dayTitle(selectedDay)).font(.system(size: 23, weight: .semibold))
                        Text(selectedDay + ".md").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 8)
                    if canReturnToReview {
                        Button(L10n.tr("返回回顾"), action: onReturnToReview).controlSize(.small)
                    }
                    if selectedDay != today {
                        Button(L10n.tr("回到今天")) { select(today) }.controlSize(.small)
                    }
                }
                .padding(22)
                Divider()
                DailyNoteDocumentEditor(day: selectedDay)
                Divider()
                HStack {
                    Text(selectedDay == today ? L10n.tr("今天") : L10n.tr("历史记录"))
                    Spacer()
                    Text(L10n.tr("自动保存为 Markdown"))
                }
                .font(.caption).foregroundStyle(.secondary).padding(14)
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear { notes.refresh(); notes.load(selectedDay) }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in notes.refresh() }
        .onReceive(Timer.publish(every: 60, on: .main, in: .common).autoconnect()) { referenceDate = $0 }
    }

    private func select(_ day: String) {
        NSApp.keyWindow?.makeFirstResponder(nil)
        _ = notes.savePendingDrafts()
        notes.load(day)
        selectedDay = day
    }

    private func dayTitle(_ day: String) -> String {
        guard let date = DailyNoteDate.date(day) else { return day }
        return date.formatted(.dateTime.month().day().weekday(.wide).locale(L10n.locale))
    }
}

@MainActor
struct DailyNotesMonthPicker: View {
    @Binding var displayedMonth: Date
    let selectedDay: String
    let recordedDays: Set<String>
    let today: Date
    let onSelect: (String) -> Void
    private let calendar = Calendar.current

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Button { move(-1) } label: { Image(systemName: "chevron.left") }.accessibilityLabel(L10n.tr("上个月"))
                Spacer()
                Text(L10n.monthTitle(displayedMonth, calendar: calendar)).font(.headline)
                Spacer()
                Button { move(1) } label: { Image(systemName: "chevron.right") }
                    .accessibilityLabel(L10n.tr("下个月"))
                    .disabled(calendar.dateInterval(of: .month, for: displayedMonth)!.end > today)
            }
            .buttonStyle(.borderless)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 3), count: 7), spacing: 4) {
                ForEach(["一", "二", "三", "四", "五", "六", "日"], id: \.self) { day in
                    Text(L10n.key(day)).font(.caption).foregroundStyle(.secondary)
                }
                ForEach(TaskCalendarModel.days(in: displayedMonth, calendar: calendar)) { cell in
                    let key = DailyNoteDate.key(cell.date)
                    let selected = key == selectedDay
                    Button { onSelect(key) } label: {
                        VStack(spacing: 3) {
                            Text("\(calendar.component(.day, from: cell.date))")
                            Circle().fill(recordedDays.contains(key) ? Color.accentColor : .clear).frame(width: 4, height: 4)
                        }
                        .frame(maxWidth: .infinity).frame(height: 33)
                        .background(selected ? Color.accentColor.opacity(0.15) : .clear, in: RoundedRectangle(cornerRadius: 6))
                        .opacity(cell.isInDisplayedMonth ? 1 : 0.35)
                    }
                    .buttonStyle(.plain)
                    .disabled(cell.date > calendar.startOfDay(for: today))
                    .accessibilityLabel(key + (recordedDays.contains(key) ? L10n.tr("，有记录") : L10n.tr("，暂无记录，可补写")))
                    .accessibilityAddTraits(selected ? .isSelected : [])
                }
            }
            Label(L10n.tr("有记录的日期显示圆点，空白日期可补写"), systemImage: "circle.fill")
                .font(.system(size: 10)).foregroundStyle(.secondary)
        }
        .padding(16).frame(width: 290)
    }

    private func move(_ offset: Int) { displayedMonth = TaskCalendarModel.month(byAdding: offset, to: displayedMonth, calendar: calendar) }
}

@MainActor
struct MenuDailyNotesView: View {
    @ObservedObject private var notes = DailyNotesStore.shared
    @EnvironmentObject private var presentation: MenuTaskPresentation
    @State private var day = DailyNoteDate.key(Date())
    @State private var focusRequest = UUID()

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 5) {
                    Text(L10n.tr("每日记录")).font(.headline)
                    Text(day).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                if day != DailyNoteDate.key(Date()) {
                    Button(L10n.tr("今天")) { openToday() }.controlSize(.small)
                }
            }.padding(16)
            Divider()
            DailyNoteDocumentEditor(day: day, compact: true, focusRequest: focusRequest)
            Divider()
            Button {
                _ = notes.savePendingDrafts()
                DailyNotesNavigation.shared.requestedDay = day
                presentation.openWorkbench()
            } label: { Label(L10n.tr("在工作台展开"), systemImage: "arrow.up.right.square") }
                .buttonStyle(.borderless).font(.caption).padding(12)
        }
        .onAppear { openToday() }
        .onChange(of: presentation.openGeneration) { _ in openToday() }
        .onChange(of: presentation.isMenuVisible) { visible in if !visible { _ = notes.savePendingDrafts() } }
        // An editing session keeps its date through midnight. The next opening starts today.
    }

    private func openToday() {
        NSApp.keyWindow?.makeFirstResponder(nil)
        _ = notes.savePendingDrafts()
        notes.refresh()
        day = DailyNoteDate.key(Date())
        notes.load(day)
        focusRequest = UUID()
    }
}
