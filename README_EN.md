<p align="center"><img src="shared/branding/toccata-app-icon.png" alt="Toccata Personal" width="96"></p>

# Toccata Personal

[简体中文](README.md) · **English**

Capture daily explorations. Review your ideas and progress.

Toccata Personal is a macOS menu bar App combining daily Markdown notes, tasks and local keyboard activity. Jot down experiments, ideas and validation results, then review your work at the end of a day or week.

[Download personal DMG](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg) · [SHA-256](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg.sha256) · [All releases](https://github.com/EricGao-cn/Toccata/releases)

## Daily notes and review

- **One Markdown file per day:** whole-page writing and autosave for what you tried, what comes next and which ideas you validated or ruled out.
- **Write quickly, browse by day:** continue a note in the menu bar panel; browse and edit dates in the workspace, with a pop-up calendar for jumping to a day.
- **Weekly report material:** review notes and tasks over a date range, then copy the current content or everything.
- **Independent notes and tasks:** keep exploration in your notes and create a task when you have a concrete goal to finish.

## Task management

- Quickly add and edit tasks from the menu bar, and collect ideas in the inbox.
- Use subtasks, Markdown descriptions, pinning and drag ordering.
- Schedule tasks by date, see plans in the calendar and review progress.

![Task management and the menu bar panel](images/todo-management.png)

## Keyboard activity

- **Key heatmap:** see frequently used keys and live press feedback.
- **Activity timeline:** review typing periods, commonly used apps and Fn hold durations by day.
- **Activity overview:** check today's or yesterday's keyboard and app activity from the menu bar.

Active time is estimated from keyboard activity and cannot cover all reading, thinking or other effort. Fn time can also include shortcuts. This and the task screenshot use demo data from the original project.

![Keyboard heatmap and activity timeline](images/keyboard-activity.png)

## Get started

The current personal release is **1.1.1**, for **Apple Silicon Macs · macOS 13+**.

Download and verify the DMG, place `Toccata Personal.app` in `~/Applications`, eject the image and launch the App. Tasks and daily notes work independently; confirm Input Monitoring when first enabling keyboard tracking or when requested by the system.

The App stays in the menu bar and can keep running with its workspace closed. General settings provide appearance, language, launch at login, Dock visibility and water reminders.

Existing users can check for a personal release from About Toccata and open its download page. Replace the App manually to update, keeping the existing data directory. The current package has not been Developer ID notarized; see [installation and update instructions](docs/personal-release.md#普通-app-更新).

## Data and privacy

Tasks, daily notes and keyboard activity stay on your Mac. Keyboard tracking captures no typed text, screenshots or audio. Manually checking for updates contacts the personal GitHub release source.

Daily notes are Markdown files in `~/Library/Application Support/Toccata-Personal/daily-notes/`, accessible through the App's note-folder action. The personal and upstream Apps store data separately, so you can retain the original App and records.

## Origin and license

This personal fork is maintained at [EricGao-cn/Toccata](https://github.com/EricGao-cn/Toccata), based on [KMnO4-zx/Toccata](https://github.com/KMnO4-zx/Toccata), adding independent daily notes and research progress reviews.

Licensed under [Apache-2.0](LICENSE). The original introduction, author's narrative and acknowledgments are preserved in the [previous README archive](docs/upstream-readme-en.md).
