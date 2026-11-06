<p align="center"><img src="shared/branding/toccata-app-icon.png" alt="Toccata Personal" width="96"></p>

# Toccata Personal

[简体中文](README.md) · **English**

This is the personal fork maintained at [EricGao-cn/Toccata](https://github.com/EricGao-cn/Toccata), based on [KMnO4-zx/Toccata](https://github.com/KMnO4-zx/Toccata). It retains upstream tasks and local keyboard activity, adding independent daily Markdown notes and research progress reviews.

[Download personal DMG](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg) · [SHA-256](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg.sha256) · [All personal releases](https://github.com/EricGao-cn/Toccata/releases) · [Apache-2.0](LICENSE)

## Download and use

The published personal release is **personal-v1.1.1 / build 3**, based on upstream **v0.1.4** and built by GitHub Actions. Its current package targets Apple Silicon Macs running macOS 13 or later. Check the personal releases page for later versions.

1. Download the personal DMG and verify it against its SHA-256 file. Historical installation ZIPs remain available; GitHub Source code archives contain source only.
2. Open the image, then use Finder → Go → Go to Folder and enter `~/Applications`. Quit an existing personal instance before dragging `Toccata Personal.app` there. Create the folder first if necessary.
3. Eject the image and launch `~/Applications/Toccata Personal.app`, rather than running from the DMG or a development worktree.
4. Tasks and daily notes work independently. To enable keyboard statistics, confirm Input Monitoring in System Settings → Privacy & Security. Do not run the upstream and personal collectors simultaneously.

The App currently uses an **ad-hoc signature and has not been Developer ID notarized**. Users confirm system permissions and security prompts themselves. Update checks offer personal stable versions and their download pages; they never download or install updates automatically. Existing 1.1.0 installations can remain in use. Version 1.1.1 mainly changes building and publishing; users choose whether to install it.

## Personal workflow

- **Daily notes:** one Markdown file per day, whole-page editing, autosave and date-based browsing. Menu bar and workbench share drafts. No required templates or automatic TODO creation.
- **Review:** switch between notes and tasks for a selected date range, copy the current content, or explicitly copy everything for a weekly report.
- **Tasks:** retain upstream tasks, subtasks, pinning, drag ordering and calendar views.

## Separate data from upstream

| Distribution | Default data location |
| --- | --- |
| Personal stable App | `~/Library/Application Support/Toccata-Personal/` |
| Upstream App | `~/Library/Application Support/Toccata/` |
| Isolated development and candidate Apps | Per-worktree test directories, usually under `~/Library/Application Support/Toccata-Dev/` |

Daily notes live at `daily-notes/YYYY-MM-DD.md` inside the personal data directory. First use may start with empty personal data, retaining the upstream App and data without migration. Back up before updating an existing personal installation: downgrading the App does not roll back its database. Databases, notes, backups, machine configuration and toolchains stay out of Git.

See the [personal distribution guide](docs/personal-release.md) for installation, backup, optional migration and rollback.

## Branches and maintenance

| Branch or tag | Role |
| --- | --- |
| `main` | Pure upstream mirror; follows `upstream/main` without personal modifications |
| `codex/personal` | GitHub default branch and long-lived personal mainline for accepted features and upstream integrations |
| `codex/feat/*` | Feature development from the personal mainline; integrate after testing, review and authorization |
| `codex/sync/*` | Integrate a selected upstream tag or commit from the personal mainline; verify before merging back |
| `personal-vX.Y.Z` | Fixed personal release tags; never moved or reused after release |

Update mirror `main` as upstream advances. Integrate upstream into the personal mainline by release or reviewed batch, rather than automatically merging every commit. Start personal development from `codex/personal`. See the [development/worktree guide](docs/personal-development.md) and [Agent rules](AGENTS.md).

[Daily development CI](.github/workflows/personal-ci.yml) checks and tests pushes to personal feature, sync and mainline branches. It needs no release tag and does not package installers or create Release drafts. It takes effect once a branch containing the workflow is committed and pushed. See the [development CI procedure](docs/personal-development.md#日常开发-ci) for scope and test policies.

## Build and release

Personal packages are built and verified with `scripts/personal/release.py`, then prepared as DMG (with ZIP compatibility) using `scripts/personal/publish.py`. The active [personal Actions workflow](.github/workflows/personal-release.yml) builds the DMG and SHA-256 and creates a Release draft when a new personal tag is pushed. It also supports manual runs from the personal mainline; final publication remains a maintainer decision. Version 1.1.1 completed this cloud build and draft upload flow; existing 1.1.0 packages were built locally. The inherited upstream workflow targets the upstream distribution and is not the personal publishing entry point.

Personal builds use SDK 26.2; upstream entry points retain their SDK 26.5 requirement. After acceptance and integration, authorize creation and push of a new fixed tag, which triggers building and draft upload; local manual packaging remains available. The workflow never overwrites an existing Release or draft or moves a tag. Final publication and installation require separate confirmation; none implicitly replaces the daily-use App. See the [personal Actions procedure](docs/personal-release.md#个人-github-actions构建-dmg-并停在草稿).

## Upstream and license

The original project is maintained by [KMnO4-zx](https://github.com/KMnO4-zx). This fork retains upstream attribution, licensing and acknowledgments. First-person statements in the upstream introduction below belong to its author.

<details>
<summary>Upstream introduction and general documentation (original text retained)</summary>

<p align="center">
  <img src="shared/branding/toccata-app-icon.png" alt="Toccata" width="96">
</p>

<h1 align="center">Toccata</h1>

<p align="center">
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

<p align="center">
  <strong>Capture ideas. See your effort.</strong><br>
  <em>Curious about your net active thinking time?</em>
</p>

<p align="center">
  <a href="https://github.com/KMnO4-zx/Toccata/releases">Download</a> ·
  <a href="develop.md">Developer Guide (Chinese)</a> ·
  <a href="CONTRIBUTING.md#english">Contribute</a> ·
  <a href="LICENSE">Apache-2.0</a>
</p>

## Why I Built This

I never used to bother with to-do apps. Keeping everything in my head worked just fine. Then work and study started piling up, and I finally needed somewhere to write things down.

My needs were simple: quickly see what I'd finished and what was still left to do, then pull up the week's tasks to write my weekly report. So I tried TickTick. I hated using it, and they still wanted my money!

**No way. So I built my own.**

I also really wanted to build something that tracks **“net active thinking time.”** Of all those hours at my computer every day, how much of that time is my mind actually active? Since I was already building my own app, I figured I'd add that too.

The name comes from [toccata](https://www.dictionary.com/browse/toccata), a piece of music for the keyboard. Its root is the Italian *toccare*, meaning “to touch.” I like that connection: fingers touch keys, and thoughts slowly become something you can see.

## To-Do Management

- **Capture on the fly**: open the menu bar window to add or edit tasks, with completed and pending items in view.
- **Organize at your pace**: break tasks into subtasks in the main window, write details in Markdown, set dates, and browse the task calendar.
- **Sort and pin**: reorder or pin whole task groups in the main window and menu bar, with subtasks following their parent. Sort by creation time, name, or planned date.
- **Review your week**: gather completed and unfinished tasks, copy them with one click, and use them as the starting point for your weekly report.
- **Daily notes (personal fork)**: one local Markdown file per day, with full-page editing from the menu bar and date-based browsing in the workbench. Review notes and tasks separately, copy the current tab or both, and find the independent files using “Open notes folder”.

![To-do management: main workspace on the left, menu bar window on the right](images/todo-management.png)

## Keyboard Activity: Net Active Thinking Time

There's something else I want to know: of all the time I spend at my computer, how much of it am I actually active? Taking a screenshot every few seconds and asking AI to analyze what I'm doing leaves me uneasy about privacy. So I turned to keyboard input.

My thinking is simple: **to the computer, I'm providing input; to myself, I'm producing output. When we're producing output, our minds are definitely active.** At that moment, the connection between me and the computer is right there, at the fingertips of both hands.

> And there's the connection: Toccata comes from the Italian *toccare*, “to touch.”

I want to use the keyboard to record the time I spend putting something out into the world. I call it **“net active thinking time.”** Honestly, I find that idea pretty sexy 🤔

- **Keyboard heatmap**: see which keys you use most, with live feedback as you press them.
- **Activity timeline**: see when you were typing throughout the day, and look back at your app usage and Fn hold time.
- **Local records**: key codes, timestamps, hold durations, and associated apps are recorded on your Mac. Capture takes no screenshots and records no audio.

![Keyboard activity: per-key heatmap and activity timelines for the last seven days](images/keyboard-activity.png)

> “Net active thinking time” is the idea behind this project. The actual duration is estimated from keyboard activity; it cannot directly measure thought or capture all the effort spent reading and thinking. Fn hold time serves as an estimate of spoken output and may also include shortcut use. See the [counting rules (Chinese)](develop.md#按键次数与活跃时间计算). The screenshots above use demo data.

## Get Started

For **Apple Silicon Macs · macOS 13+**. Download the DMG from [Releases](https://github.com/KMnO4-zx/Toccata/releases), then drag `Toccata.app` into Applications.

Once you have a version with in-app updates, use **About Toccata → Check for Updates** to download a newer release, then choose **Install and Restart**. Downloads can be cancelled or retried; tasks and keyboard records are saved before installation. The release page remains available when there is no compatible package. Older versions need one manual upgrade first.

Keyboard tracking requires permission under **System Settings → Privacy & Security → Input Monitoring**. Task management works independently.

Toccata stays in the menu bar and shows a Dock icon by default. Hide it under **Settings → General settings**. Click its menu bar icon to add and manage tasks, or right-click and choose **Open Workspace** for the full interface. Closing the workspace keeps Toccata running in the background; choose **Quit Toccata** to stop the app.

**Settings → General settings** brings together appearance, language, water reminders, launch at login, Dock visibility, and About. The appearance, language, and About shortcuts remain at the bottom left. Launch at login is off by default.

The menu bar panel also includes **Activity overview**, with Keyboard and Apps pages for today or yesterday. The Keyboard page shows a per-key heatmap and 15-minute activity segments with hover details. The scrollable Apps page lists every app by active time, showing both active time and key presses. Set **Default menu bar page** to Task management, Task calendar, or Activity overview under General settings. Task management is the default; each reopening uses your configured page.

Open General settings, or right-click the menu bar icon and choose **Water reminders…** to enable reminders based on key presses. The default interval is 8,192 presses, with a fresh count each day. You can change the interval and send a test notification. Enabling reminders requires notification permission; counts use the existing input monitoring records. Reminders continue with the workspace closed and stop when you quit the app.

Want to make it your own? Build instructions and development notes are in [develop.md (Chinese)](develop.md).

## Contributing

Contributions to code, documentation, translations, and testing are welcome. See the [contribution guide](CONTRIBUTING.md#english). The Windows port is looking for contributors: discuss ideas and pick a feature in [Windows support #1](https://github.com/KMnO4-zx/Toccata/issues/1), with client work in [apps/toccata-windows/](apps/toccata-windows/README.md#english).

## Thanks 🙏

- <img src="images/logos/kimi.png" width="20" height="20" alt="Kimi Logo"> &nbsp; Thanks to the **[Kimi Global Ambassador Program](https://www.kimi.com/zh-cn/lp/kimi-ambassador)**. Kimi K3.1 Pro is a great model for visual design!
- <img src="images/logos/openai-rounded.svg" width="20" height="20" alt="OpenAI Logo"> &nbsp; Thanks to the **[OpenAI Codex for Open Source program](https://developers.openai.com/community/codex-for-oss)** for giving me 12 months of ChatGPT Pro. GPT 6 Astra is a great coding model!
- <img src="images/logos/volcengine.png" width="20" height="20" alt="Volcengine Logo"> &nbsp; Thanks to the **[Volcengine Hero Program](https://developer.volcengine.com/)**. Doubao's multimodal capabilities are excellent!
- <img src="images/logos/datawhale.png" width="20" height="20" alt="Datawhale Logo"> &nbsp; Thanks to **[Datawhale](https://datawhale.cn/)**. A place to meet wonderful people on the same journey.

</details>
