import AppKit
import SwiftUI

@MainActor
struct DailyReviewView: View {
    @ObservedObject private var notes = DailyNotesStore.shared
    @ObservedObject private var language = LanguageSettings.shared
    @EnvironmentObject private var tasks: TaskStore
    @Binding var range: TaskReviewRange
    @Binding var tab: DailyReviewTab
    let onEditDay: (String) -> Void
    @State private var referenceDate = Date()
    @State private var showsRangePicker = false
    @State private var copyMessage = ""
    @State private var copyError = false
    @State private var selectedTaskID: String?
    @State private var taskQuery = ""

    private var dates: CalendarDateRange { range.dateRange(relativeTo: referenceDate) }
    private var snapshot: TaskReviewSnapshot { TaskReviewSnapshot(tasks: tasks.tasks, range: range, referenceDate: referenceDate, query: taskQuery) }
    private var entries: [DailyNoteDocument] {
        let first = DailyNoteDate.key(dates.start)
        let last = DailyNoteDate.key(dates.end)
        return notes.documents.values.filter { $0.hasContent && $0.id >= first && $0.id <= last }.sorted { $0.id < $1.id }
    }

    var body: some View {
        let _ = language.language
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(L10n.tr("回顾")).font(.system(size: 25, weight: .bold, design: .rounded))
                        Text(snapshot.dateLabel).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    HStack(spacing: 3) {
                        Button { copy(tab == .notes ? .notes : .tasks) } label: {
                            Label(tab == .notes ? L10n.tr("复制每日记录") : L10n.tr("复制任务"), systemImage: "doc.on.doc")
                        }
                        Menu {
                            Button(L10n.tr("复制全部（每日记录＋任务）")) { copy(.all) }
                                .help(L10n.tr("复制所选时段的全部记录和任务，不应用任务搜索。"))
                        } label: { Image(systemName: "chevron.down") }
                        .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                        .accessibilityLabel(L10n.tr("更多复制选项"))
                    }.controlSize(.small)
                }
                HStack(spacing: 7) {
                    ForEach(TaskReviewPeriod.allCases) { period in
                        Button(period == .thisWeek ? L10n.tr("本周") : L10n.tr("最近 7 天")) { range = .preset(period) }
                            .tint(range == .preset(period) ? .accentColor : .secondary)
                    }
                    Button(L10n.tr("自定义时段")) { showsRangePicker = true }
                        .popover(isPresented: $showsRangePicker, arrowEdge: .bottom) {
                            CalendarDateRangePicker(initialRange: dates, referenceDate: referenceDate,
                                onCancel: { showsRangePicker = false },
                                onApply: { range = .custom($0); showsRangePicker = false })
                        }
                }.buttonStyle(.bordered).controlSize(.small)
                HStack {
                    Picker(L10n.tr("回顾内容"), selection: $tab) {
                        ForEach(DailyReviewTab.allCases) { item in Text(item.title).tag(item) }
                    }
                    .labelsHidden().pickerStyle(.segmented).frame(width: 200).id(language.language)
                    Spacer()
                    Text(copyMessage).font(.caption).foregroundStyle(.secondary)
                }
                if let error = notes.reviewError(in: dates), tab == .notes {
                    Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled)
                }
            }
            .padding(24)
            Divider()
            // Retain both scroll views when switching tabs; only their visibility changes.
            ZStack {
                notesList.opacity(tab == .notes ? 1 : 0).allowsHitTesting(tab == .notes).accessibilityHidden(tab != .notes)
                taskList.opacity(tab == .tasks ? 1 : 0).allowsHitTesting(tab == .tasks).accessibilityHidden(tab != .tasks)
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear { referenceDate = Date(); notes.refresh() }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in notes.refresh() }
        .onReceive(Timer.publish(every: 60, on: .main, in: .common).autoconnect()) { referenceDate = $0 }
        .onReceive(tasks.$tasks.dropFirst()) { _ in referenceDate = Date(); copyMessage = "" }
        .onChange(of: range) { _ in copyMessage = "" }
        .onChange(of: tab) { _ in copyMessage = "" }
        .onReceive(notes.$documents.dropFirst()) { _ in copyMessage = "" }
        .alert(L10n.tr("无法复制回顾"), isPresented: $copyError) {
            Button(L10n.tr("好"), role: .cancel) {}
        } message: { Text(L10n.tr("请先处理记录的读取或保存错误，再重试复制。")) }
        .sheet(isPresented: Binding(get: { selectedTaskID != nil }, set: { if !$0 { selectedTaskID = nil } })) {
            VStack(spacing: 0) {
                HStack { Spacer(); Button(L10n.tr("完成")) { selectedTaskID = nil } }.padding(12)
                if let selectedTaskID, let task = tasks.task(id: selectedTaskID) {
                    TaskDetailView(task: task, onSelect: { self.selectedTaskID = $0 })
                }
            }.frame(width: 620, height: 640)
        }
    }

    private var notesList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 22) {
                if entries.isEmpty {
                    Text(L10n.tr("这段时间还没有每日记录。"))
                        .foregroundStyle(.secondary).padding(.vertical, 30)
                }
                ForEach(entries) { entry in
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Button(entry.id) { onEditDay(entry.id) }.font(.headline).buttonStyle(.borderless)
                            Spacer()
                            Button(L10n.tr("编辑当天")) { onEditDay(entry.id) }.buttonStyle(.borderless).font(.caption)
                        }
                        DailyNoteReadingView(text: entry.text)
                        Divider().padding(.top, 10)
                    }
                }
            }.padding(24).frame(maxWidth: .infinity, alignment: .leading)
        }.id(range)
    }

    private var taskList: some View {
        TasksView(mode: .review, selection: $selectedTaskID, embeddedReview: true,
                  reviewRange: $range, reviewQuery: $taskQuery, reviewReferenceDate: referenceDate)
    }

    private func copy(_ scope: ResearchReviewCopyScope) {
        if scope != .tasks {
            guard notes.prepareReview(in: dates) else { copyError = true; return }
        }
        let taskMarkdown = scope == .all
            ? TaskReviewSnapshot(tasks: tasks.tasks, range: range, referenceDate: referenceDate).markdown : snapshot.markdown
        let markdown = ResearchReviewExport.markdown(scope: scope,
            notes: DailyNotesExport.markdown(documents: entries, range: dates), tasks: taskMarkdown)
        NSPasteboard.general.clearContents()
        if NSPasteboard.general.setString(markdown, forType: .string) { copyMessage = L10n.tr("已复制") }
        else { copyMessage = L10n.tr("复制失败，请重试") }
    }
}

private struct DailyNoteReadingView: View {
    let text: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(TaskMarkdownParser.blocks(from: text)) { block in
                switch block.kind {
                case .heading(let level, let text): Text(TaskMarkdownInline.attributedString(text)).font(level <= 2 ? .headline : .subheadline).padding(.top, 4)
                case .paragraph(let text): Text(TaskMarkdownInline.attributedString(text))
                case .unorderedItem(let text): Text("• ") + Text(TaskMarkdownInline.attributedString(text))
                case .orderedItem(let number, let text): Text("\(number). ") + Text(TaskMarkdownInline.attributedString(text))
                case .quote(let text): Text(TaskMarkdownInline.attributedString(text)).foregroundStyle(.secondary).padding(.leading, 12)
                case .code(_, let text): Text(text).font(.system(.body, design: .monospaced)).padding(10).frame(maxWidth: .infinity, alignment: .leading).background(Color.primary.opacity(0.04), in: RoundedRectangle(cornerRadius: 6))
                case .divider: Divider()
                }
            }
        }.textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
    }
}
