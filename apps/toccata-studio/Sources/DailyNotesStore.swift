import AppKit
import Combine
import Foundation

/// Filenames describe a local Gregorian date, independent of display language.
enum DailyNoteDate {
    static func key(_ date: Date, timeZone: TimeZone = .current) -> String {
        formatter(timeZone).string(from: date)
    }

    static func date(_ key: String, timeZone: TimeZone = .current) -> Date? {
        guard key.count == 10, key.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil,
              let date = formatter(timeZone).date(from: key), self.key(date, timeZone: timeZone) == key else { return nil }
        return date
    }

    private static func formatter(_ timeZone: TimeZone) -> DateFormatter {
        let value = DateFormatter()
        value.locale = Locale(identifier: "en_US_POSIX")
        value.calendar = Calendar(identifier: .gregorian)
        value.timeZone = timeZone
        value.dateFormat = "yyyy-MM-dd"
        value.isLenient = false
        return value
    }
}

struct DailyNoteDocument: Equatable, Identifiable {
    let id: String
    var text: String
    var diskData: Data?
    var isDirty = false

    var hasContent: Bool { !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    var summary: String {
        text.split(whereSeparator: \.isNewline)
            .first(where: { !$0.trimmingCharacters(in: .whitespaces).hasPrefix("#") })
            .map { String($0.prefix(140)) } ?? ""
    }
}

/// Shared by both editors. Drafts outlive views, and participate in close/quit flushing.
@MainActor
final class DailyNotesStore: ObservableObject, PendingDraftSaving {
    static let shared = DailyNotesStore(directory: AppPaths.supportDirectory.appendingPathComponent("daily-notes", isDirectory: true))

    let directory: URL
    @Published private(set) var documents: [String: DailyNoteDocument] = [:]
    @Published private(set) var errors: [String: String] = [:]
    @Published private(set) var conflicts: Set<String> = []
    @Published private(set) var scanError: String?
    private var saveTask: Task<Void, Never>?

    init(directory: URL, registerForQuit: Bool = true) {
        self.directory = directory
        if registerForQuit { PendingEdits.shared.registerDraftBuffer(self) }
    }

    var recordedDays: [String] {
        documents.values.filter(\.hasContent).map(\.id).sorted(by: >)
    }

    func refresh() {
        do {
            try checkDirectory(directory)
            let urls = FileManager.default.fileExists(atPath: directory.path)
                ? try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey], options: [.skipsHiddenFiles]) : []
            let keys = Set(urls.filter { $0.pathExtension == "md" && DailyNoteDate.date($0.deletingPathExtension().lastPathComponent) != nil }
                .map { $0.deletingPathExtension().lastPathComponent }).union(documents.keys).union(errors.keys)
            scanError = nil
            for key in keys { load(key) }
        } catch { scanError = error.localizedDescription }
    }

    func load(_ day: String) {
        guard DailyNoteDate.date(day) != nil else { return }
        do {
            let data = try read(day)
            if let current = documents[day], current.isDirty {
                if current.diskData != data { reportConflict(day) }
                return
            }
            let text = try decode(data)
            let document = DailyNoteDocument(id: day, text: text, diskData: data)
            if documents[day] != document { documents[day] = document }
            errors.removeValue(forKey: day)
            conflicts.remove(day)
        } catch { errors[day] = error.localizedDescription }
    }

    func update(_ day: String, text: String) {
        guard var document = documents[day], document.text != text else { return }
        document.text = text
        document.isDirty = true
        documents[day] = document
        saveTask?.cancel()
        saveTask = Task { @MainActor [weak self] in
            do { try await Task.sleep(nanoseconds: 400_000_000) } catch { return }
            _ = self?.savePendingDrafts()
        }
    }

    @discardableResult
    func save(_ day: String) -> Bool {
        guard var document = documents[day], document.isDirty else { return true }
        do {
            let current = try read(day)
            guard current == document.diskData else { reportConflict(day); return false }
            // Merely visiting an empty day, or clearing a new draft, creates no file.
            if current == nil && !document.hasContent {
                document.isDirty = false
                documents[day] = document
                errors.removeValue(forKey: day)
                conflicts.remove(day)
                return true
            }
            try checkDirectory(directory)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let data = Data(document.text.utf8)
            try data.write(to: fileURL(day), options: .atomic)
            document.diskData = data
            document.isDirty = false
            documents[day] = document
            errors.removeValue(forKey: day)
            conflicts.remove(day)
            return true
        } catch {
            errors[day] = error.localizedDescription
            return false
        }
    }

    func savePendingDrafts() -> Bool { saveDrafts(in: nil) }

    /// Review export only flushes and validates notes inside its selected period.
    func prepareReview(in range: CalendarDateRange) -> Bool {
        refresh()
        let saved = saveDrafts(in: range)
        return saved && reviewError(in: range) == nil
    }

    func reviewError(in range: CalendarDateRange) -> String? {
        if let scanError { return scanError }
        guard let day = errors.keys.sorted().first(where: { contains($0, in: range) }) else { return nil }
        return "\(day): \(errors[day]!)"
    }

    private func contains(_ day: String, in range: CalendarDateRange) -> Bool {
        day >= DailyNoteDate.key(range.start) && day <= DailyNoteDate.key(range.end)
    }

    private func saveDrafts(in range: CalendarDateRange?) -> Bool {
        if range == nil {
            saveTask?.cancel()
            saveTask = nil
        }
        var success = true
        for day in documents.keys.sorted() where documents[day]?.isDirty == true {
            if let range, !contains(day, in: range) { continue }
            if !save(day) { success = false }
        }
        return success
    }

    /// A resolution always preserves the displaced version in a separate backup.
    func resolveConflict(_ day: String, keepLocal: Bool) {
        guard var document = documents[day], conflicts.contains(day) else { return }
        do {
            let current = try read(day)
            let externalText = keepLocal ? "" : try decode(current)
            try backup(keepLocal ? current : Data(document.text.utf8), day: day)
            document.diskData = current
            if !keepLocal {
                document.text = externalText
                document.isDirty = false
            }
            documents[day] = document
            conflicts.remove(day)
            errors.removeValue(forKey: day)
            if keepLocal { _ = save(day) }
        } catch { errors[day] = error.localizedDescription }
    }

    func fileURL(_ day: String) -> URL { directory.appendingPathComponent(day + ".md") }

    func openFolder() {
        do {
            try checkDirectory(directory)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            NSWorkspace.shared.open(directory)
        } catch { scanError = error.localizedDescription }
    }

    private func read(_ day: String) throws -> Data? {
        guard DailyNoteDate.date(day) != nil else { throw CocoaError(.fileReadInvalidFileName) }
        try checkDirectory(directory)
        let url = fileURL(day)
        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
            guard attributes[.type] as? FileAttributeType == .typeRegular else { throw CocoaError(.fileReadUnsupportedScheme) }
            return try Data(contentsOf: url)
        } catch let error as CocoaError where error.code == .fileReadNoSuchFile || error.code == .fileNoSuchFile { return nil }
    }

    private func decode(_ data: Data?) throws -> String {
        guard let data else { return "" }
        guard let text = String(data: data, encoding: .utf8) else { throw CocoaError(.fileReadInapplicableStringEncoding) }
        return text
    }

    private func checkDirectory(_ url: URL) throws {
        do {
            // Query the filesystem again; URL resource values may cache a previous
            // obstruction and prevent a recovered path from being retried.
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
            guard attributes[.type] as? FileAttributeType == .typeDirectory else { throw CocoaError(.fileReadUnsupportedScheme) }
        } catch let error as CocoaError where error.code == .fileReadNoSuchFile || error.code == .fileNoSuchFile { return }
    }

    private func backup(_ data: Data?, day: String) throws {
        guard let data else { return }
        let folder = directory.appendingPathComponent("Backups", isDirectory: true)
        try checkDirectory(directory)
        try checkDirectory(folder)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try data.write(to: folder.appendingPathComponent("\(day)-\(UUID().uuidString).md"), options: .atomic)
    }

    private func reportConflict(_ day: String) {
        conflicts.insert(day)
        errors[day] = L10n.tr("文件已被其他编辑器修改。请选择保留的版本，另一份会备份到 Backups。")
    }
}

enum DailyNotesExport {
    static func markdown(documents: [DailyNoteDocument], range: CalendarDateRange, timeZone: TimeZone = .current) -> String {
        let start = DailyNoteDate.key(range.start, timeZone: timeZone)
        let end = DailyNoteDate.key(range.end, timeZone: timeZone)
        let notes = documents.filter { $0.hasContent && $0.id >= start && $0.id <= end }.sorted { $0.id < $1.id }
        // Preserve the user's Markdown verbatim, including code fences and heading levels.
        return (["# " + L10n.tr("每日记录"), "\(start) — \(end)"] + notes.map { "## \($0.id)\n\n\($0.text)" }).joined(separator: "\n\n")
    }
}
