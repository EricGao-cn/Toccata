import CryptoKit
import Darwin
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
        try await packageSelection(current: current)
        try manifestAndCollectorGuards()
        if PersonalDistribution.isCandidate {
            try await installationGuards()
        } else if PersonalDistribution.isPersonal {
            try await personalControllerAllowsExplicitInstall()
        }
    }

    @MainActor
    private static func personalControllerAllowsExplicitInstall() async throws {
        let scratch = FileManager.default.temporaryDirectory.appendingPathComponent("personal-update-controller-\(UUID())")
        let plan = PreparedAppUpdate(target: scratch.appendingPathComponent("Toccata Personal.app"),
            staged: scratch.appendingPathComponent("staged.app"), backup: scratch.appendingPathComponent("backup.app"),
            directory: scratch, originalIdentity: "0:0", version: "1.2.0", personalCDHash: String(repeating: "a", count: 40))
        var installed: PreparedAppUpdate?
        let updater = AppUpdateController(install: { prepared, _ in installed = prepared },
                                          prepare: { _, _ in plan })
        updater.download(AvailableUpdate(version: plan.version, pageURL: ReleaseChannel.personal.releasesURL))
        for _ in 0..<100 where updater.state != .ready { try await Task.sleep(nanoseconds: 10_000_000) }
        try expect(updater.state == .ready && installed == nil, "personal download did not wait for explicit installation")
        updater.install()
        try expect(updater.state == .installing && installed == plan, "explicit personal install did not reach lifecycle")
    }

    private static func packageSelection(current: AppVersion) async throws {
        let version = "1.2.0"
        let tag = "personal-v\(version)"
        let channel = ReleaseChannel.personal
        let name = channel.packageName(version: version, architecture: UpdatePackage.architecture)
        let hash = String(repeating: "a", count: 64)
        let asset: [String: Any] = ["name": name, "size": 23, "state": "uploaded", "digest": "sha256:\(hash)",
                                    "browser_download_url": "https://untrusted.example/replacement"]
        let expected = UpdatePackage(url: channel.packageURL(tag: tag, name: name), size: 23, sha256: hash)
        let cases: [([[String: Any]], UpdatePackage?)] = [
            ([asset], PersonalDistribution.supportsInAppUpdates ? expected : nil),
            ([asset, asset], nil),
            ([asset.merging(["name": "Toccata-1.2.0-arm64.dmg"], uniquingKeysWith: { _, new in new })], nil),
            ([asset.merging(["digest": "sha256:wrong"], uniquingKeysWith: { _, new in new })], nil)
        ]
        for (assets, expectedPackage) in cases {
            let service = ReleaseUpdateService(channel: channel) { request in
                try response([item(tag).merging(["assets": assets], uniquingKeysWith: { _, new in new })], url: request.url!)
            }
            let update = try await service.check(current: current)
            try expect(update?.version == version && update?.package == expectedPackage, "incorrect personal package selection")
        }
        try UpdatePackagePreparer.checkPersonalPackage(expected, version: version)
        let wrongRepo = UpdatePackage(url: ReleaseChannel.upstream.packageURL(tag: tag, name: name), size: 23, sha256: hash)
        do {
            try UpdatePackagePreparer.checkPersonalPackage(wrongRepo, version: version)
            throw Failure(message: "accepted package from upstream")
        } catch UpdateInstallFailure.package {}
    }

    @MainActor
    private static func manifestAndCollectorGuards() throws {
        guard let physical = realpath(NSTemporaryDirectory(), nil) else { throw Failure(message: "cannot resolve fixture directory") }
        defer { free(physical) }
        let scratch = URL(fileURLWithPath: String(cString: physical), isDirectory: true)
            .appendingPathComponent("personal-update-manifest-\(UUID())")
        let channel = ReleaseChannel.personal
        let app = scratch.appendingPathComponent(channel.appName)
        let contents = app.appendingPathComponent("Contents")
        try FileManager.default.createDirectory(at: contents, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: scratch) }
        let version = "1.2.1"
        let commit = String(repeating: "1", count: 40)
        let info: [String: String] = ["CFBundleIdentifier": channel.bundleIdentifier, "CFBundleExecutable": channel.executableName,
            "CFBundleShortVersionString": version, "CFBundleVersion": "5", "ToccataSourceCommit": commit,
            "DTSDKName": "macosx26.2", "ToccataDistributionChannel": "personal-stable", "ToccataUpdateMode": "in-app"]
        func writeInfo(_ info: [String: String]) throws {
            try PropertyListSerialization.data(fromPropertyList: info, format: .xml, options: 0)
                .write(to: contents.appendingPathComponent("Info.plist"))
        }
        try writeInfo(info)
        try UpdatePackagePreparer.checkLocation(app, channel: channel)
        let architecture = UpdatePackage.architecture
        let tag = "personal-v\(version)"
        let manifest: [String: Any] = ["schema_version": 1, "channel": "personal-stable", "version": version,
            "build": "5", "sdk": "26.2", "commit": commit, "tag": tag, "tag_object": String(repeating: "2", count: 40),
            "app": channel.appName, "bundle_id": channel.bundleIdentifier, "architecture": architecture, "dirty": false]
        let package = UpdatePackage(url: channel.packageURL(tag: tag, name: channel.packageName(version: version, architecture: architecture)),
                                    size: 100, sha256: String(repeating: "a", count: 64))
        func writeManifest(_ value: [String: Any]) throws {
            let data = try JSONSerialization.data(withJSONObject: value)
            try data.write(to: scratch.appendingPathComponent("release.json"))
            let sha = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
            try (sha + "\n").write(to: scratch.appendingPathComponent("release.json.sha256"), atomically: true, encoding: .utf8)
        }
        try writeManifest(manifest)
        try Data("fixture".utf8).write(to: scratch.appendingPathComponent("安装说明.txt"))
        try UpdatePackagePreparer.validatePersonalManifest(at: scratch, version: version, package: package)
        try writeManifest(manifest.merging(["dirty": true], uniquingKeysWith: { _, new in new }))
        do {
            try UpdatePackagePreparer.validatePersonalManifest(at: scratch, version: version, package: package)
            throw Failure(message: "accepted dirty manifest")
        } catch UpdateInstallFailure.package {}
        try writeManifest(manifest)
        try writeInfo(info.merging(["ToccataDistributionChannel": "personal-candidate"], uniquingKeysWith: { _, new in new }))
        do {
            try UpdatePackagePreparer.validatePersonalManifest(at: scratch, version: version, package: package)
            throw Failure(message: "accepted candidate app")
        } catch UpdateInstallFailure.package {}

        let collector = CoreProcessController(helperURL: nil, dataDirectory: scratch, socketPath: "fixture", socketIsReachable: { _ in false })
        try expect(collector.isStoppedForPersonalUpdate(), "a missing collector lock blocked updates")
        let lock = scratch.appendingPathComponent("toccata.lock")
        try Data().write(to: lock)
        let descriptor = open(lock.path, O_RDONLY)
        guard descriptor >= 0 else { throw Failure(message: "cannot open fixture lock") }
        defer { close(descriptor) }
        try expect(flock(descriptor, LOCK_EX | LOCK_NB) == 0, "cannot acquire fixture lock")
        try expect(!collector.isStoppedForPersonalUpdate(), "update allowed while collector lock was held")
        try expect(flock(descriptor, LOCK_UN) == 0 && collector.isStoppedForPersonalUpdate(), "released collector lock blocked updates")
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
        } catch UpdateInstallFailure.candidate {}
        let prepared = PreparedAppUpdate(target: scratch.appendingPathComponent("missing.app"),
            staged: scratch.appendingPathComponent("staged.app"), backup: scratch.appendingPathComponent("backup.app"),
            directory: scratch, originalIdentity: "0:0", version: "9.0.0")
        do { try await prepared.startInstaller(); throw Failure(message: "personal helper started") }
        catch UpdateInstallFailure.candidate {}
        let files = try FileManager.default.contentsOfDirectory(atPath: scratch.path)
        try expect(effects == 0 && files.isEmpty,
                   "personal installation guard wrote files or invoked progress")
    }
}
