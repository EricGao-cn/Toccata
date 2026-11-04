import Foundation

enum DailyReviewTab: String, CaseIterable, Identifiable {
    case notes, tasks
    var id: Self { self }
    var title: String { self == .notes ? L10n.tr("每日记录") : L10n.tr("任务") }
}

enum ResearchReviewCopyScope { case notes, tasks, all }

enum ResearchReviewExport {
    static func markdown(scope: ResearchReviewCopyScope, notes: String, tasks: String) -> String {
        switch scope {
        case .notes: return notes
        case .tasks: return tasks
        case .all: return notes + "\n\n---\n\n" + tasks
        }
    }
}
