import Foundation
import XCTest
@testable import toccata_studio

@MainActor
final class DailyNotesTests: XCTestCase {
    private let day = "2026-11-04"

    func testEmptyVisitAndClearedNewDraftDoNotCreateFiles() throws {
        let store = try fixture()
        store.load(day)
        XCTAssertEqual(store.documents[day]?.text, "")
        XCTAssertFalse(FileManager.default.fileExists(atPath: store.directory.path))
        store.update(day, text: "temporary")
        store.update(day, text: " \n")
        XCTAssertTrue(store.savePendingDrafts())
        XCTAssertFalse(FileManager.default.fileExists(atPath: store.fileURL(day).path))
    }

    func testRawMarkdownSurvivesSaveAndReloadExactly() throws {
        let store = try fixture()
        let text = "## 10:20\n中文与公式 $x^2$\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```python\n  print('  ')\n```\n![图](assets/a.png)\n\n"
        store.load(day)
        store.update(day, text: text)
        XCTAssertTrue(store.savePendingDrafts())
        let reopened = DailyNotesStore(directory: store.directory, registerForQuit: false)
        reopened.refresh()
        XCTAssertEqual(reopened.documents[day]?.text, text)
        XCTAssertEqual(try Data(contentsOf: store.fileURL(day)), Data(text.utf8))
        XCTAssertEqual(reopened.recordedDays, [day])
    }

    func testPendingFlushSavesAllDaysInsteadOfOnlyVisibleDay() throws {
        let store = try fixture()
        for key in ["2026-11-03", day] {
            store.load(key)
            store.update(key, text: key)
        }
        XCTAssertTrue(store.savePendingDrafts())
        XCTAssertEqual(try String(contentsOf: store.fileURL("2026-11-03"), encoding: .utf8), "2026-11-03")
        XCTAssertEqual(try String(contentsOf: store.fileURL(day), encoding: .utf8), day)
    }

    func testExternalEditReloadsOnlyCleanDocument() throws {
        let store = try savedFixture()
        try Data("external".utf8).write(to: store.fileURL(day), options: .atomic)
        store.refresh()
        XCTAssertEqual(store.documents[day]?.text, "external")
        XCTAssertTrue(store.errors.isEmpty)
    }

    func testConflictDoesNotOverwriteAndResolutionBacksUpExternalVersion() throws {
        let store = try savedFixture()
        store.update(day, text: "my draft")
        try Data("external".utf8).write(to: store.fileURL(day), options: .atomic)
        XCTAssertFalse(store.savePendingDrafts())
        XCTAssertEqual(try String(contentsOf: store.fileURL(day), encoding: .utf8), "external")
        XCTAssertEqual(store.documents[day]?.text, "my draft")
        XCTAssertTrue(store.conflicts.contains(day))
        store.resolveConflict(day, keepLocal: true)
        XCTAssertEqual(try String(contentsOf: store.fileURL(day), encoding: .utf8), "my draft")
        XCTAssertEqual(try backups(store), ["external"])
        XCTAssertFalse(store.documents[day]!.isDirty)
    }

    func testAdoptingExternalVersionPreservesLocalDraftInBackup() throws {
        let store = try savedFixture()
        store.update(day, text: "my draft")
        try Data("external".utf8).write(to: store.fileURL(day), options: .atomic)
        store.refresh()
        store.resolveConflict(day, keepLocal: false)
        XCTAssertEqual(store.documents[day]?.text, "external")
        XCTAssertEqual(try backups(store), ["my draft"])
    }

    func testExternalDeletionIsAConflictForDirtyDocument() throws {
        let store = try savedFixture()
        store.update(day, text: "unsaved")
        try FileManager.default.removeItem(at: store.fileURL(day))
        XCTAssertFalse(store.savePendingDrafts())
        XCTAssertTrue(store.conflicts.contains(day))
        XCTAssertFalse(FileManager.default.fileExists(atPath: store.fileURL(day).path))
    }

    func testWriteFailureRetainsDraftAndRetrySucceeds() throws {
        let store = try fixture()
        store.load(day)
        store.update(day, text: "keep this draft")
        try Data("blocking file".utf8).write(to: store.directory)
        XCTAssertFalse(store.savePendingDrafts())
        XCTAssertEqual(store.documents[day]?.text, "keep this draft")
        XCTAssertTrue(store.documents[day]!.isDirty)
        try FileManager.default.removeItem(at: store.directory)
        XCTAssertTrue(store.savePendingDrafts())
        XCTAssertEqual(try String(contentsOf: store.fileURL(day), encoding: .utf8), "keep this draft")
    }

    func testRejectsInvalidNamesSymlinksAndNonUTF8WithoutOverwriting() throws {
        let store = try savedFixture()
        store.load("../escape")
        XCTAssertNil(store.documents["../escape"])
        let linkedDay = "2026-11-03"
        try FileManager.default.createSymbolicLink(at: store.fileURL(linkedDay), withDestinationURL: store.fileURL(day))
        store.load(linkedDay)
        XCTAssertNil(store.documents[linkedDay])
        XCTAssertNotNil(store.errors[linkedDay])
        try Data([0xff, 0xfe, 0xff]).write(to: store.fileURL("2026-11-02"))
        store.load("2026-11-02")
        XCTAssertNil(store.documents["2026-11-02"])
        XCTAssertNotNil(store.errors["2026-11-02"])
    }

    func testDatesAreStrictAndUseRequestedTimeZone() throws {
        XCTAssertNil(DailyNoteDate.date("2026-02-30"))
        XCTAssertNil(DailyNoteDate.date("2026-1-2"))
        XCTAssertNil(DailyNoteDate.date("../../foo"))
        let utc = TimeZone(secondsFromGMT: 0)!
        let shanghai = TimeZone(secondsFromGMT: 8 * 3600)!
        let date = ISO8601DateFormatter().date(from: "2026-11-03T18:00:00Z")!
        XCTAssertEqual(DailyNoteDate.key(date, timeZone: utc), "2026-11-03")
        XCTAssertEqual(DailyNoteDate.key(date, timeZone: shanghai), "2026-11-04")
    }

    func testReviewBoundsOrderAndCopyScopeStayIndependent() throws {
        let zone = TimeZone(secondsFromGMT: 0)!
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        let range = CalendarDateRange(start: DailyNoteDate.date("2026-11-02", timeZone: zone)!,
                                      end: DailyNoteDate.date(day, timeZone: zone)!, calendar: calendar)
        let raw = "```md\n# do not rewrite this code\n```\n"
        let entries = [DailyNoteDocument(id: day, text: raw, diskData: nil),
                       DailyNoteDocument(id: "2026-11-01", text: "excluded", diskData: nil),
                       DailyNoteDocument(id: "2026-11-02", text: "first", diskData: nil)]
        let notes = DailyNotesExport.markdown(documents: entries, range: range, timeZone: zone)
        XCTAssertFalse(notes.contains("excluded"))
        XCTAssertTrue(notes.contains(raw))
        XCTAssertLessThan(notes.range(of: "first")!.lowerBound, notes.range(of: raw)!.lowerBound)
        XCTAssertEqual(ResearchReviewExport.markdown(scope: .tasks, notes: notes, tasks: "tasks only"), "tasks only")
        XCTAssertEqual(ResearchReviewExport.markdown(scope: .notes, notes: notes, tasks: "tasks only"), notes)
        XCTAssertTrue(ResearchReviewExport.markdown(scope: .all, notes: notes, tasks: "tasks only").contains("tasks only"))
    }

    private func fixture() throws -> DailyNotesStore {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("ToccataDailyNotesTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: root) }
        return DailyNotesStore(directory: root.appendingPathComponent("notes"), registerForQuit: false)
    }

    func testEditorRequestsAreConsumedOnceAcrossDateRebuilds() {
        let command = DailyNoteEditorCommand(action: .insertTime, day: day)
        XCTAssertNotNil(command.consume(for: day))
        XCTAssertNil(command.consume(for: "2026-11-03"))
        XCTAssertNil(command.consume(for: day))
        let pending = DailyNoteEditorCommand(action: .insertTime, day: day)
        XCTAssertNil(pending.consume(for: "2026-11-03"))
        XCTAssertNil(pending.consume(for: day))
    }

    func testDeletedUnreadableFileClearsItsReadError() throws {
        let store = try savedFixture()
        let badDay = "2026-11-01"
        try Data([0xff]).write(to: store.fileURL(badDay))
        store.refresh()
        XCTAssertNotNil(store.errors[badDay])
        try FileManager.default.removeItem(at: store.fileURL(badDay))
        store.refresh()
        XCTAssertNil(store.errors[badDay])
    }

    func testReviewIgnoresOutOfRangeConflictButKeepsDraftAndQuitFailure() throws {
        let store = try savedFixture()
        let oldDay = "2026-10-01"
        store.load(oldDay)
        store.update(oldDay, text: "original")
        XCTAssertTrue(store.savePendingDrafts())
        store.update(oldDay, text: "my unsaved draft")
        try Data("external".utf8).write(to: store.fileURL(oldDay), options: .atomic)
        let date = DailyNoteDate.date(day)!
        XCTAssertTrue(store.prepareReview(in: CalendarDateRange(start: date, end: date)))
        XCTAssertTrue(store.documents[oldDay]!.isDirty)
        XCTAssertEqual(store.documents[oldDay]?.text, "my unsaved draft")
        XCTAssertFalse(store.savePendingDrafts())
        let oldDate = DailyNoteDate.date(oldDay)!
        XCTAssertFalse(store.prepareReview(in: CalendarDateRange(start: oldDate, end: oldDate)))
    }

    func testKeepLocalVersionBacksUpInvalidExternalBytes() throws {
        let store = try savedFixture()
        store.update(day, text: "local text")
        let bytes = Data([0xff, 0xfe, 0xff])
        try bytes.write(to: store.fileURL(day), options: .atomic)
        XCTAssertFalse(store.savePendingDrafts())
        store.resolveConflict(day, keepLocal: true)
        XCTAssertEqual(try Data(contentsOf: store.fileURL(day)), Data("local text".utf8))
        let files = try FileManager.default.contentsOfDirectory(at: store.directory.appendingPathComponent("Backups"), includingPropertiesForKeys: nil)
        XCTAssertTrue(try files.contains { try Data(contentsOf: $0) == bytes })
    }

    func testAutosaveKeepsLatestTextAcrossRapidEditsAndDates() async throws {
        let store = try fixture()
        store.load(day)
        store.load("2026-11-03")
        store.update(day, text: "first")
        store.update("2026-11-03", text: "yesterday")
        store.update(day, text: "latest 中文\n")
        try await Task.sleep(nanoseconds: 650_000_000)
        XCTAssertEqual(try String(contentsOf: store.fileURL(day), encoding: .utf8), "latest 中文\n")
        XCTAssertEqual(try String(contentsOf: store.fileURL("2026-11-03"), encoding: .utf8), "yesterday")
    }

    private func savedFixture() throws -> DailyNotesStore {
        let store = try fixture()
        store.load(day)
        store.update(day, text: "original")
        XCTAssertTrue(store.savePendingDrafts())
        return store
    }

    private func backups(_ store: DailyNotesStore) throws -> [String] {
        try FileManager.default.contentsOfDirectory(at: store.directory.appendingPathComponent("Backups"), includingPropertiesForKeys: nil)
            .map { try String(contentsOf: $0, encoding: .utf8) }
    }
}
