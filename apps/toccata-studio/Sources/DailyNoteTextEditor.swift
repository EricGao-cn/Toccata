import AppKit
import SwiftUI

final class DailyNoteEditorCommand: Equatable {
    enum Action { case insertTime, end }
    let action: Action
    let day: String
    let token = UUID()
    private var consumed = false

    init(action: Action, day: String) { self.action = action; self.day = day }
    static func == (lhs: DailyNoteEditorCommand, rhs: DailyNoteEditorCommand) -> Bool { lhs.token == rhs.token }

    /// Consumption belongs to the request, not the native view, which is rebuilt
    /// when the date changes. A stale request must not run on a different day.
    func consume(for day: String) -> Action? {
        guard !consumed else { return nil }
        consumed = true
        return self.day == day ? action : nil
    }
}

/// A lossless Markdown editor: user-authored syntax never passes through an HTML serializer.
struct DailyNoteTextEditor: NSViewRepresentable {
    @Binding var text: String
    let day: String
    var surface = "workbench"
    var focusRequest: UUID?
    var command: DailyNoteEditorCommand?
    var fontSize: CGFloat = 14

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        let editor = DailyNotesNativeTextView()
        editor.isRichText = false
        editor.allowsUndo = true
        editor.isAutomaticQuoteSubstitutionEnabled = false
        editor.isAutomaticDashSubstitutionEnabled = false
        editor.isAutomaticTextReplacementEnabled = false
        editor.isAutomaticSpellingCorrectionEnabled = false
        editor.isContinuousSpellCheckingEnabled = false
        editor.drawsBackground = false
        editor.textColor = .labelColor
        editor.insertionPointColor = .labelColor
        editor.font = .systemFont(ofSize: fontSize)
        editor.textContainerInset = NSSize(width: 8, height: 10)
        editor.isVerticallyResizable = true
        editor.isHorizontallyResizable = false
        editor.autoresizingMask = [.width]
        editor.textContainer?.widthTracksTextView = true
        editor.textContainer?.containerSize = NSSize(width: 0, height: CGFloat.greatestFiniteMagnitude)
        editor.delegate = context.coordinator
        editor.setAccessibilityLabel(L10n.tr("每日记录正文"))
        scroll.documentView = editor
        context.coordinator.editor = editor
        updateNSView(scroll, context: context)
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        let coordinator = context.coordinator
        coordinator.parent = self
        guard let editor = coordinator.editor else { return }
        editor.font = .systemFont(ofSize: fontSize)
        editor.setAccessibilityLabel(L10n.tr("每日记录正文"))
        if coordinator.day != day {
            coordinator.rememberPosition()
            coordinator.day = day
            editor.undoManager?.removeAllActions()
            editor.string = text
            let position = Coordinator.positions[surface + ":" + day] ?? Position(selection: NSRange(location: (text as NSString).length, length: 0), scroll: .zero)
            editor.setSelectedRange(clamped(position.selection, length: (text as NSString).length))
            scroll.contentView.scroll(to: position.scroll)
        } else if editor.string != text, !editor.hasMarkedText() {
            let selection = editor.selectedRange()
            editor.undoManager?.removeAllActions()
            editor.string = text
            editor.setSelectedRange(clamped(selection, length: (text as NSString).length))
        }
        if let focusRequest, coordinator.lastFocusRequest != focusRequest {
            coordinator.lastFocusRequest = focusRequest
            if let editor = editor as? DailyNotesNativeTextView {
                editor.focusWhenAttached = true
                DispatchQueue.main.async { [weak editor] in editor?.applyRequestedFocus() }
            }
        }
        if let action = command?.consume(for: day) {
            editor.window?.makeFirstResponder(editor)
            switch action {
            case .end:
                editor.setSelectedRange(NSRange(location: (editor.string as NSString).length, length: 0))
                editor.scrollRangeToVisible(editor.selectedRange())
            case .insertTime:
                let formatter = DateFormatter()
                formatter.dateFormat = "HH:mm"
                editor.insertText("\n\n## \(formatter.string(from: Date()))\n", replacementRange: editor.selectedRange())
            }
        }
    }

    static func dismantleNSView(_ view: NSScrollView, coordinator: Coordinator) { coordinator.rememberPosition() }

    private func clamped(_ range: NSRange, length: Int) -> NSRange {
        let start = min(range.location, length)
        return NSRange(location: start, length: min(range.length, length - start))
    }

    struct Position { let selection: NSRange; let scroll: NSPoint }

    final class Coordinator: NSObject, NSTextViewDelegate {
        static var positions: [String: Position] = [:]
        var parent: DailyNoteTextEditor
        weak var editor: NSTextView?
        var day: String?
        var lastFocusRequest: UUID?

        init(_ parent: DailyNoteTextEditor) { self.parent = parent }
        func textDidChange(_ notification: Notification) {
            guard let editor else { return }
            parent.text = editor.string
            rememberPosition()
        }
        func textViewDidChangeSelection(_ notification: Notification) { rememberPosition() }
        func rememberPosition() {
            guard let day, let editor else { return }
            Self.positions[parent.surface + ":" + day] = Position(selection: editor.selectedRange(), scroll: editor.enclosingScrollView?.contentView.bounds.origin ?? .zero)
        }
    }
}

private final class DailyNotesNativeTextView: NSTextView {
    var focusWhenAttached = false
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        applyRequestedFocus()
    }
    func applyRequestedFocus() {
        guard focusWhenAttached, let window else { return }
        focusWhenAttached = false
        window.makeFirstResponder(self)
    }
}
