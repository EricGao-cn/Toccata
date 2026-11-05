import Foundation
import Darwin
import XCTest
@testable import toccata_studio

final class PersonalDistributionTests: XCTestCase {
    private func fixture() throws -> URL {
        let physical = realpath(NSTemporaryDirectory(), nil)!
        let tempRoot = URL(fileURLWithPath: String(cString: physical), isDirectory: true)
        free(physical)
        let directory = tempRoot.appendingPathComponent("PersonalDistributionTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return directory
    }

    func testOrdinaryDirectoryTraversalTerminatesAtFilesystemRoot() throws {
        let root = try fixture()
        try PersonalDistribution.validateDirectory(root)
        try PersonalDistribution.validateDirectory(root.appendingPathComponent("not-created-yet"))
    }

    func testDatabaseAndAncestorLinksAreRejected() throws {
        let root = try fixture()
        let data = root.appendingPathComponent("data")
        try FileManager.default.createDirectory(at: data, withIntermediateDirectories: true)
        let original = root.appendingPathComponent("original")
        try Data("synthetic".utf8).write(to: original)
        let database = data.appendingPathComponent("tasks.sqlite")
        try FileManager.default.createSymbolicLink(at: database, withDestinationURL: original)
        XCTAssertThrowsError(try PersonalDistribution.validateDirectory(data))
        try FileManager.default.removeItem(at: database)
        try FileManager.default.linkItem(at: original, to: database)
        XCTAssertThrowsError(try PersonalDistribution.validateDirectory(data))
        let alias = root.appendingPathComponent("alias")
        try FileManager.default.createSymbolicLink(at: alias, withDestinationURL: data)
        XCTAssertThrowsError(try PersonalDistribution.validateDirectory(alias))
    }

    func testPendingMaintenancePreventsOpeningData() throws {
        let root = try fixture()
        let data = root.appendingPathComponent("data")
        let pending = root.appendingPathComponent(".data.maintenance.pending.json")
        try Data("synthetic transaction".utf8).write(to: pending)
        XCTAssertThrowsError(try PersonalDistribution.validateDirectory(data))
        XCTAssertFalse(FileManager.default.fileExists(atPath: data.path))
    }
}
