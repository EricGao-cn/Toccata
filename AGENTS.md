# Repository Guidelines

## Scope & Branches
This personal fork may contain public customizations. Keep `main` as an upstream mirror; integrate accepted work into `codex/personal`. Use `codex/feat/<name>` or `codex/sync/<upstream-tag>` branches with separate worktrees for substantial features or upstream upgrades. Upstream PRs/issues are optional, only when requested. Personal distribution uses manual updates and the separate entry points described in `docs/personal-release.md`; personal in-app installation updates remain disabled.

## Feature Chat Workflow
For new feature implementation, read this file and `docs/personal-development.md`; inspect directory, branch, and existing changes. Start from committed `codex/personal` in a dedicated worktree. Reuse an already-correct feature worktree; do not create another unnecessarily. If detached, create `codex/feat/<name>` there. Run `dev init` and `dev check` using the entry below; verify isolated identity, data, and outputs before implementation.

After implementation, test, review, and report results, skipped checks, and remaining issues. Commit and merge only when authorized; honor explicit advance authorization without asking again. Commit approval alone does not authorize merging. Merge into `codex/personal` from its owning checkout after checking its state, then verify integration. Completion never implies push, release, installation, or archiving.

Before an authorized archive, confirm work is merged, preserved, or discarded as the user directed; inspect remaining changes/untracked/needed ignored files, and gracefully stop only this worktree's development processes. Preserve needed artifacts and external data. Do not force cleanup with unsaved work or treat an archive snapshot as a merge.

## Project Structure
- `apps/toccata-studio/Sources/`, `Tests/`, `Resources/`: SwiftUI/AppKit client, XCTest suites, bundled assets.
- `core/toccata-core/src/`: Rust collector, SQLite writer, socket IPC, inline tests.
- `shared/`: contracts and canonical layout/version resources. Read `shared/protocol.md` before changing storage, IPC, or statistics.
- `scripts/personal/`: reproducible development setup; `docs/personal-development.md`: fork workflow.
- `scripts/tests/`: Python tests. Windows remains a planning directory.

## Development Commands
Run from the repository root:

```bash
./scripts/personal/dev init          # Preserve or initialize this checkout
./scripts/personal/dev check         # Verify identity, paths, SDK, tools
./scripts/personal/dev build         # Build an isolated task-only app
./scripts/personal/dev run
./scripts/personal/dev test-core
./scripts/personal/dev test-scripts
./scripts/personal/dev test-swift     # Requires full Xcode and XCTest
git diff --check
```

Personal development uses SDK 26.2; upstream scripts retain SDK 26.5. Never weaken the upstream SDK guard. Keep machine paths, databases, toolchains, and outputs ignored. Initialize each worktree; ignored files are not copied.

## Isolation & Releases
Each development worktree needs independent bundle identity, preferences, data, and build output; only toolchains/download caches may be shared. Preserve legacy development data during setup. Never point development at upstream/personal stable data or embed/start collection implicitly. Keep collection local without screenshots, audio, or typed text.

Personal stable distribution needs a separate entry point; never turn the development launcher into a stable installer by redirecting it to daily-use data.

Use `scripts/personal/release.py` for candidate/tagged packaging and `maintenance.py` for offline backup, staging, paired installation, rollback and interrupted-transaction recovery. Maintenance commands default to plans; real execution needs task-specific authorization, normal shutdown checks, and explicit execution flags. Never remove pending transaction markers to bypass recovery. Candidate builds cannot be installed as stable releases and never start collection. Rehearse on synthetic data before any real-data operation.

Stable releases require an accepted clean commit, fixed personal tag, SHA, SDK, and checksum. Preserve upstream tags. Validate backup/restore and migrations on copies; downgrading an app does not roll back its database. Building does not authorize installation/publication. Follow task-specific authorization; local commit approval never implies permission to push.

## Style & Verification
Use four-space indentation, Swift `UpperCamelCase` types/files and `lowerCamelCase` members, Rust `snake_case` functions/modules, and `cargo fmt`. Keep Chinese/English UI text aligned; synchronize canonical resources. Use XCTest `*Tests.swift`, Rust `#[test]`, and Python `test_*.py`; add meaningful regression coverage. WebKit tests need an interactive desktop. Report unavailable/skipped checks explicitly. The intermittent quit warning remains unconfirmed. When commits are authorized, use focused `feat:`, `fix:`, `docs:`, `chore:`, or `perf:` messages.
