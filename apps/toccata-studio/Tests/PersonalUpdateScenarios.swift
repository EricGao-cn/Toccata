import Foundation
#if canImport(toccata_studio)
@testable import toccata_studio
#endif

/// Also runnable with a small swiftc main when this machine lacks XCTest.
enum PersonalUpdateScenarios {
    struct Failure: Error { let message: String }
    static func expect(_ value: Bool, _ message: String) throws {
        if !value { throw Failure(message: message) }
    }
    static func item(_ tag: String, draft: Bool = false, preview: Bool = false) -> [String: Any] {
        ["tag_name": tag, "draft": draft, "prerelease": preview, "html_url": "https://untrusted.example/file"]
    }
    static func response(_ value: Any, url: URL, status: Int = 200) throws -> (Data, URLResponse) {
        (try JSONSerialization.data(withJSONObject: value),
         HTTPURLResponse(url: url, statusCode: status, httpVersion: nil, headerFields: nil)!)
    }

    @MainActor
    static func run() async throws {
        let current = AppVersion(version: "1.1.0", build: "2")
        var requests = 0
        let releases = [item("v99.0.0"), item("personal-v9.0.0", draft: true),
            item("personal-v8.0.0", preview: true), item("personal-v1.9.0"), item("personal-v1.10.0"),
            item("personal-v01.11.0"), item("personal-vv9.0.0"), item("personal-v2.0.0/unsafe")]
        let service = ReleaseUpdateService(channel: .personal) { request in
            requests += 1
            try expect(request.url == ReleaseChannel.personal.releasesAPIURL(page: 1), "wrong personal endpoint")
            try expect(request.httpBody == nil && request.value(forHTTPHeaderField: "Authorization") == nil, "check sends private data")
            return try response(releases, url: request.url!)
        }
        let checker = UpdateChecker(service: service, current: current)
        try expect(requests == 0 && checker.state == .idle, "opening About made a request")
        await checker.check()
        guard case let .available(update) = checker.state else { throw Failure(message: "missing personal update") }
        try expect(update.version == "1.10.0", "numeric comparison or channel filtering failed")
        try expect(update.pageURL.absoluteString == "https://github.com/EricGao-cn/Toccata/releases/tag/personal-v1.10.0", "untrusted release URL")
        try expect(update.package == nil, "personal update exposed one-click installer")

        var pages = 0
        let paginated = ReleaseUpdateService(channel: .personal) { request in
            pages += 1
            try expect(request.url == ReleaseChannel.personal.releasesAPIURL(page: pages), "wrong pagination")
            return try response(pages == 1 ? Array(repeating: item("v99.0.0"), count: 100) : [item("personal-v1.2.0")], url: request.url!)
        }
        let pagedUpdate = try await paginated.check(current: current)
        try expect(pages == 2 && pagedUpdate?.version == "1.2.0", "missed a later page")

        for values in [[], [item("v99.0.0")], [item("personal-v2.0.0", preview: true)]] {
            let empty = ReleaseUpdateService(channel: .personal) { request in try response(values, url: request.url!) }
            do { _ = try await empty.check(current: current); throw Failure(message: "no release reported up-to-date") }
            catch UpdateCheckFailure.noAccessibleRelease {}
        }
        for tag in ["personal-v1.1.0", "personal-v1.0.0"] {
            let older = ReleaseUpdateService(channel: .personal) { request in try response([item(tag)], url: request.url!) }
            let result = try await older.check(current: current)
            try expect(result == nil, "offered a downgrade")
        }
        for (status, failure) in [(404, UpdateCheckFailure.noAccessibleRelease), (403, .rateLimited), (429, .rateLimited), (500, .connectionFailed)] {
            let bad = ReleaseUpdateService(channel: .personal) { request in try response([], url: request.url!, status: status) }
            let failed = UpdateChecker(service: bad, current: current)
            await failed.check()
            try expect(failed.state == .failed(failure), "incorrect HTTP failure state")
        }
        let malformed = ReleaseUpdateService(channel: .personal) { request in
            (Data("not-json".utf8), HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!)
        }
        let invalid = UpdateChecker(service: malformed, current: current)
        await invalid.check()
        try expect(invalid.state == .failed(.invalidResponse), "invalid JSON was accepted")
        let redirected = ReleaseUpdateService(channel: .personal) { _ in
            try response([item("personal-v9.0.0")], url: URL(string: "https://api.github.com/repos/other/repo/releases")!)
        }
        let wrongSource = UpdateChecker(service: redirected, current: current)
        await wrongSource.check()
        try expect(wrongSource.state == .failed(.invalidResponse), "redirected release source was trusted")
        var partialPages = 0
        let partial = ReleaseUpdateService(channel: .personal) { request in
            partialPages += 1
            if partialPages > 1 { throw URLError(.timedOut) }
            return try response(Array(repeating: item("personal-v9.0.0"), count: 100), url: request.url!)
        }
        let partialCheck = UpdateChecker(service: partial, current: current)
        await partialCheck.check()
        try expect(partialCheck.state == .failed(.connectionFailed), "offered an update from an incomplete listing")
        var attempts = 0
        let retry = ReleaseUpdateService(channel: .personal) { request in
            attempts += 1
            if attempts == 1 { throw URLError(.timedOut) }
            return try response([item("personal-v1.2.0")], url: request.url!)
        }
        let retried = UpdateChecker(service: retry, current: current)
        await retried.check()
        try expect(retried.state == .failed(.connectionFailed), "network failure was hidden")
        await retried.check()
        try expect(retried.state == .available(AvailableUpdate(version: "1.2.0",
            pageURL: URL(string: "https://github.com/EricGao-cn/Toccata/releases/tag/personal-v1.2.0")!)), "retry failed")
        var count = 0
        let bounded = ReleaseUpdateService(channel: .personal) { request in
            count += 1
            return try response(Array(repeating: item("personal-v1.2.0"), count: 100), url: request.url!)
        }
        let incomplete = UpdateChecker(service: bounded, current: current)
        await incomplete.check()
        try expect(count == 10 && incomplete.state == .failed(.invalidResponse), "incomplete listing was trusted")

        let upstream = ReleaseUpdateService(channel: .upstream) { request in
            try expect(request.url == ReleaseChannel.upstream.latestAPIURL, "upstream source changed")
            return try response(item("v1.2.0"), url: request.url!)
        }
        let upstreamUpdate = try await upstream.check(current: current)
        try expect(upstreamUpdate?.pageURL.absoluteString == "https://github.com/KMnO4-zx/Toccata/releases/tag/v1.2.0", "upstream link changed")
        if PersonalDistribution.isPersonal { try await installationGuards() }
    }

    @MainActor
    private static func installationGuards() async throws {
        var effects = 0
        let updater = AppUpdateController(install: { _, _ in effects += 1 }, prepare: { _, _ in
            effects += 1
            throw UpdateInstallFailure.installer
        })
        let scratch = FileManager.default.temporaryDirectory.appendingPathComponent("personal-update-guards-\(UUID())")
        try FileManager.default.createDirectory(at: scratch, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: scratch) }
        let update = AvailableUpdate(version: "9.0.0", pageURL: ReleaseChannel.personal.releasesURL,
            package: UpdatePackage(url: URL(string: "https://github.com/fixture.zip")!, size: 1, sha256: String(repeating: "a", count: 64)))
        updater.download(update)
        updater.install()
        try expect(effects == 0 && updater.prepared == nil, "personal controller invoked installation")
        do {
            _ = try await UpdatePackagePreparer(target: scratch.appendingPathComponent("missing.app")).prepare(update) { _ in }
            throw Failure(message: "personal preparer accepted an update")
        } catch UpdateInstallFailure.personalManualUpdates {}
        let prepared = PreparedAppUpdate(target: scratch.appendingPathComponent("missing.app"),
            staged: scratch.appendingPathComponent("staged.app"), backup: scratch.appendingPathComponent("backup.app"),
            directory: scratch, originalIdentity: "0:0", version: "9.0.0")
        do { try await prepared.startInstaller(); throw Failure(message: "personal helper started") }
        catch UpdateInstallFailure.personalManualUpdates {}
        let files = try FileManager.default.contentsOfDirectory(atPath: scratch.path)
        try expect(effects == 0 && files.isEmpty,
                   "personal installation guard wrote files or invoked progress")
    }
}
