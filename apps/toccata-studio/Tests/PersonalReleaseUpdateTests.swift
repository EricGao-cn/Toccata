import XCTest
@testable import toccata_studio

final class PersonalReleaseUpdateTests: XCTestCase {
    @MainActor
    func testPersonalChannelScenarios() async throws {
        try await PersonalUpdateScenarios.run()
    }
}
