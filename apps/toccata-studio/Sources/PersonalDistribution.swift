import Foundation

/// Compiled only into the separate personal distribution entry point.
enum PersonalDistribution {
    static var isPersonal: Bool {
        #if TOCCATA_PERSONAL
        return true
        #else
        return false
        #endif
    }

    static var isCandidate: Bool {
        #if TOCCATA_PERSONAL_CANDIDATE
        return true
        #else
        return false
        #endif
    }

    static var dataDirectory: URL? {
        guard isPersonal else { return nil }
        let support = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support")
        if isCandidate {
            guard let path = Bundle.main.object(forInfoDictionaryKey: "ToccataCandidateDataDirectory") as? String else {
                preconditionFailure("Personal candidate has no isolated data directory")
            }
            let directory = checkedDirectory(URL(fileURLWithPath: path).standardizedFileURL)
            let allowed = support.appendingPathComponent("Toccata-Dev").resolvingSymlinksInPath().path + "/"
            precondition(directory.path.hasPrefix(allowed), "Candidate data must stay in the development namespace")
            return directory
        }
        return checkedDirectory(support.appendingPathComponent("Toccata-Personal", isDirectory: true))
    }

    static func validateDirectory(_ directory: URL) throws {
        let pending = directory.deletingLastPathComponent().appendingPathComponent(".\(directory.lastPathComponent).maintenance.pending.json")
        do {
            _ = try FileManager.default.attributesOfItem(atPath: pending.path)
            throw CocoaError(.fileReadNoPermission)
        } catch let error as CocoaError where error.code == .fileReadNoSuchFile || error.code == .fileNoSuchFile {
            // No interrupted maintenance operation owns this data directory.
        }
        var ancestors = [URL(fileURLWithPath: "/", isDirectory: true)]
        var current = ancestors[0]
        // Foundation standardization can rewrite /private/var back to the /var
        // symlink on macOS. Validate the supplied physical path component by component.
        for component in directory.path.split(separator: "/") {
            current.appendPathComponent(String(component), isDirectory: true)
            ancestors.append(current)
        }
        let files = ["config.json", "toccata.sock", "toccata.lock", "daily-notes"] +
            ["tasks.sqlite", "toccata.db"].flatMap { [$0, $0 + "-wal", $0 + "-shm"] }
        for url in ancestors + files.map({ directory.appendingPathComponent($0) }) {
            do {
                let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
                guard attributes[.type] as? FileAttributeType != .typeSymbolicLink else {
                    throw CocoaError(.fileReadInvalidFileName)
                }
                if attributes[.type] as? FileAttributeType == .typeRegular,
                   ((attributes[.referenceCount] as? NSNumber)?.intValue ?? 1) > 1 {
                    throw CocoaError(.fileReadInvalidFileName)
                }
            } catch let error as CocoaError where error.code == .fileReadNoSuchFile || error.code == .fileNoSuchFile {
                continue
            }
        }
    }

    private static func checkedDirectory(_ directory: URL) -> URL {
        do { try validateDirectory(directory); return directory }
        catch { preconditionFailure("Personal data path is linked or needs maintenance recovery before opening: \(directory.path)") }
    }
}
