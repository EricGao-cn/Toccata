import AppKit
import Combine
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
    @ObservedObject var notes: DailyNotesStore
    let day: String
    var surface = "workbench"
    var focusRequest: UUID?
    var command: DailyNoteEditorCommand?
    var fontSize: CGFloat = 14
    private var text: String { notes.documents[day]?.text ?? "" }

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
        let font = NSFont.systemFont(ofSize: fontSize)
        if editor.font != font { editor.font = font }
        editor.setAccessibilityLabel(L10n.tr("每日记录正文"))
        if coordinator.day != day {
            coordinator.rememberPosition()
            coordinator.day = day
            coordinator.clearUndoHistory()
            editor.string = text
            let position = Coordinator.positions[surface + ":" + day] ?? Position(selection: NSRange(location: (text as NSString).length, length: 0), scroll: .zero)
            editor.setSelectedRange(clamped(position.selection, length: (text as NSString).length))
            scroll.contentView.scroll(to: position.scroll)
        } else if editor.string != text, !editor.hasMarkedText() {
            let selection = editor.selectedRange()
            coordinator.clearUndoHistory()
            editor.string = text
            editor.setSelectedRange(clamped(selection, length: (text as NSString).length))
        }
        if let focusRequest, coordinator.lastFocusRequest != focusRequest {
            coordinator.lastFocusRequest = focusRequest
            editor.focusWhenAttached = true
            DispatchQueue.main.async { [weak editor] in editor?.applyRequestedFocus() }
        }
        coordinator.schedule(command)
    }

    static func dismantleNSView(_ view: NSScrollView, coordinator: Coordinator) { coordinator.detach() }

    private func clamped(_ range: NSRange, length: Int) -> NSRange {
        let start = min(range.location, length)
        return NSRange(location: start, length: min(range.length, length - start))
    }

    struct Position { let selection: NSRange; let scroll: NSPoint }

    @MainActor
    final class Coordinator: NSObject, NSTextViewDelegate {
        static var positions: [String: Position] = [:]
        var parent: DailyNoteTextEditor
        fileprivate weak var editor: DailyNotesNativeTextView?
        var day: String?
        var lastFocusRequest: UUID?
        private var lastCommand: DailyNoteEditorCommand?
        private let editorUndoManager = UndoManager()
        private var documentReload: AnyCancellable?

        init(_ parent: DailyNoteTextEditor) {
            self.parent = parent
            super.init()
            let center = NotificationCenter.default
            center.addObserver(self, selector: #selector(undoOrRedoDidFinish),
                               name: .NSUndoManagerDidUndoChange, object: editorUndoManager)
            center.addObserver(self, selector: #selector(undoOrRedoDidFinish),
                               name: .NSUndoManagerDidRedoChange, object: editorUndoManager)
            documentReload = parent.notes.willReloadDocument.sink { [weak self] day in
                guard let self, self.day == day else { return }
                self.editor?.commitMarkedText()
            }
        }

        func undoManager(for view: NSTextView) -> UndoManager? { editorUndoManager }

        func clearUndoHistory() {
            editor?.breakUndoCoalescing()
            editorUndoManager.removeAllActions()
        }

        func schedule(_ command: DailyNoteEditorCommand?) {
            guard let command, lastCommand != command else { return }
            lastCommand = command
            // Applying an edit publishes the draft. Wait until SwiftUI finishes updating the view.
            DispatchQueue.main.async { [weak self] in self?.perform(command) }
        }

        private func perform(_ command: DailyNoteEditorCommand) {
            guard let editor, let window = editor.window, let day,
                  parent.command == command, let action = command.consume(for: day) else { return }
            window.makeFirstResponder(editor)
            editor.commitMarkedText()
            switch action {
            case .end:
                editor.setSelectedRange(NSRange(location: (editor.string as NSString).length, length: 0))
            case .insertTime:
                let formatter = DateFormatter()
                formatter.locale = Locale(identifier: "en_US_POSIX")
                formatter.dateFormat = "HH:mm"
                let timestamp = "\n\n## \(formatter.string(from: Date()))\n"
                let range = editor.selectedRange()
                editor.breakUndoCoalescing()
                guard editor.shouldChangeText(in: range, replacementString: timestamp) else { return }
                editor.replaceCharacters(in: range, with: timestamp)
                editor.setSelectedRange(NSRange(location: range.location + (timestamp as NSString).length, length: 0))
                editor.didChangeText()
                editor.breakUndoCoalescing()
            }
            editor.scrollRangeToVisible(editor.selectedRange())
        }

        func textDidChange(_ notification: Notification) { publishText() }

        // AppKit can apply undo and redo without calling the text view delegate.
        @objc private func undoOrRedoDidFinish(_ notification: Notification) { publishText() }

        private func publishText() {
            guard let editor, let day else { return }
            parent.notes.update(day, text: editor.string)
            rememberPosition()
        }

        func textViewDidChangeSelection(_ notification: Notification) { rememberPosition() }

        func detach() {
            guard let editor else { return }
            editor.focusWhenAttached = false
            editor.commitMarkedText()
            if let window = editor.window, window.firstResponder === editor {
                window.makeFirstResponder(nil)
            }
            rememberPosition()
            clearUndoHistory()
            editor.delegate = nil
            self.editor = nil
            documentReload?.cancel()
        }

        func rememberPosition() {
            guard let day, let editor else { return }
            Self.positions[parent.surface + ":" + day] = Position(selection: editor.selectedRange(), scroll: editor.enclosingScrollView?.contentView.bounds.origin ?? .zero)
        }
    }
}

private final class DailyNotesNativeTextView: NSTextView {
    var focusWhenAttached = false

    override func resignFirstResponder() -> Bool {
        commitMarkedText()
        return super.resignFirstResponder()
    }

    func commitMarkedText() {
        guard hasMarkedText() else { return }
        // AppKit can discard the marked text when this editor loses focus or is removed.
        unmarkText()
        didChangeText()
    }

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
