<p align="center"><img src="shared/branding/toccata-app-icon.png" alt="Toccata Personal" width="96"></p>

# Toccata Personal

**简体中文** · [English](README_EN.md)

这是 [EricGao-cn/Toccata](https://github.com/EricGao-cn/Toccata) 维护的个人 Fork，基于 [KMnO4-zx/Toccata](https://github.com/KMnO4-zx/Toccata)。保留上游任务与本地键盘活动功能，加入独立的每日 Markdown 记录和科研过程回顾。

[下载个人版 DMG](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg) · [SHA-256](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg.sha256) · [全部个人发布](https://github.com/EricGao-cn/Toccata/releases) · [Apache-2.0](LICENSE)

## 下载与使用

已发布个人版 **personal-v1.1.1 / build 3**，基于上游 **v0.1.4**，由 GitHub Actions 构建。当前安装包适用于 Apple Silicon Mac、macOS 13 及以上。后续版本请查看个人发布页。

1. 下载个人版 DMG，按随附 SHA-256 文件核对下载。历史 ZIP 安装包继续保留；GitHub 的 Source code 压缩包只含源码。
2. 打开镜像，在 Finder 的“前往 → 前往文件夹”输入 `~/Applications`。退出已有个人版后，将 `Toccata Personal.app` 拖入；如无该文件夹，先新建。
3. 推出镜像，从 `~/Applications/Toccata Personal.app` 启动，不直接从 DMG 或开发工作树运行。
4. 任务与每日记录可独立使用。需要键盘统计时，由用户在“系统设置 → 隐私与安全性 → 输入监控”确认权限；不要同时运行原版和个人版的采集服务。

当前 App 是 **ad-hoc 签名，未做 Developer ID 公证**；系统权限和放行由用户确认。更新检查只提供个人正式版本与下载页，不自动下载安装。现有 1.1.0 可继续使用；1.1.1 主要更新构建与发布流程，是否安装由用户决定。

## 个人工作流

- **每日记录**：每天一个 Markdown 文件，整页续写、自动保存、按日期回看；菜单栏和工作台共享编辑草稿，不强制模板，也不自动生成 TODO。
- **回顾**：按日期范围切换每日记录和任务，分别复制当前内容，或显式复制全部，作为周报素材。
- **任务管理**：保留上游的任务、子任务、置顶、拖拽排序及日历功能。

## 数据与原版隔离

| 类型 | 默认数据位置 |
| --- | --- |
| 个人正式版 | `~/Library/Application Support/Toccata-Personal/` |
| 上游原版 | `~/Library/Application Support/Toccata/` |
| 隔离开发与候选版 | 独立工作树配置的测试目录，通常位于 `~/Library/Application Support/Toccata-Dev/` |

每日记录存放在个人数据目录的 `daily-notes/YYYY-MM-DD.md`。首次使用可以从空个人数据开始，保留原版 App 和数据，不要求迁移。更新已有个人版前先备份；降级 App 不会自动回滚数据库。数据库、日记、备份、本机配置和工具链不提交到 Git。

具体安装、备份、可选迁移及回滚流程见 [个人稳定版说明](docs/personal-release.md)。

## 分支与维护

| 分支或标签 | 职责 |
| --- | --- |
| `main` | 纯上游镜像，只跟随 `upstream/main`，不加入个人修改 |
| `codex/personal` | GitHub 默认分支和个人长期主线，接收验收过的功能及上游同步 |
| `codex/feat/*` | 从个人主线开始开发，测试、审查后按授权合回个人主线 |
| `codex/sync/*` | 从个人主线选择上游标签或明确提交做同步，验证后再合回 |
| `personal-vX.Y.Z` | 固定个人发布标签，发布后不移动或复用 |

上游的新提交先更新镜像 `main`，个人主线按版本或批次吸收，不逐个提交自动合并。功能开发从 `codex/personal` 出发，避免在镜像分支上做个人定制。详见 [开发与工作树流程](docs/personal-development.md) 和 [Agent 规则](AGENTS.md)。

[日常开发 CI](.github/workflows/personal-ci.yml) 随个人功能分支、同步分支和个人主线的 push 检查与测试，不要求发布标签，不打安装包或创建 Release 草稿；包含该工作流的分支提交并推送后才会生效。具体范围和测试策略见 [开发 CI 说明](docs/personal-development.md#日常开发-ci)。

## 构建与发布

个人包通过 `scripts/personal/release.py` 构建、校验，再由 `scripts/personal/publish.py` 整理 DMG（兼容 ZIP）及发布素材。已启用的 [个人 Actions 工作流](.github/workflows/personal-release.yml) 在推送新个人标签后自动构建 DMG、SHA-256 并创建 Release 草稿，也支持从个人主线手动运行；正式发布仍由维护者核对后确认。1.1.1 已通过该流程完成云端构建与草稿上传；既有 1.1.0 安装包来自此前本机构建。仓库继承的上游发布工作流面向原版，不用来发布个人包。

个人构建使用 SDK 26.2；上游入口仍保留自己的 SDK 26.5 要求。已验收提交合入个人主线后，按授权创建并推送新标签，触发构建和草稿上传；也可继续本机手动打包。工作流不覆盖同名发布或草稿，不移动标签。正式发布和安装分别确认，任何一步都不隐式替换日用 App。详见 [个人 Actions 流程](docs/personal-release.md#个人-github-actions构建-dmg-并停在草稿)。

## 上游与许可证

上游项目由 [KMnO4-zx](https://github.com/KMnO4-zx) 维护，本仓库保留其来源、许可证和致谢。上游介绍中的第一人称叙述属于原作者。

<details>
<summary>上游项目介绍与通用说明（保留原文）</summary>

<p align="center">
  <img src="shared/branding/toccata-app-icon.png" alt="Toccata" width="96">
</p>

<h1 align="center">Toccata</h1>

<p align="center">
  <strong>简体中文</strong> · <a href="README_EN.md">English</a>
</p>

<p align="center">
  <strong>记下想法，看见投入</strong><br>
  <em>想看下你的思维净活跃时长吗？</em>
</p>

<p align="center">
  <a href="https://github.com/KMnO4-zx/Toccata/releases">下载安装</a> ·
  <a href="develop.md">开发指南</a> ·
  <a href="CONTRIBUTING.md">参与贡献</a> ·
  <a href="LICENSE">Apache-2.0</a>
</p>

## 起因

我以前从来不用 ToDo 应用，觉得事情放在脑子里完全 OK。最近工作、学习的事越来越多，终于还是得找个地方记下来。

需求很简单：随手打开就能看到已完成和未完成的任务，到了周末，把这周的事情拿出来写周报。于是试了滴答清单，做的太烂了，居然还想收我的钱！

**No way，那就自己做一个。**

我还很想做一个能记录 **「思维净活跃时长」** 的东西。每天在电脑前待那么久，到底有多少时间是我的思维活跃时间？既然都自己写了，那就把这个也一起做进去。

名字取自键盘乐曲 [Toccata](https://www.dictionary.com/browse/toccata)（托卡塔），源于意大利语 *toccare*，意为“触碰”。我喜欢这个联想：双手触键，想法慢慢变成眼前的东西。

## ToDo 管理

- **随手记**：菜单栏打开小窗，快速添加、编辑任务，完成与待办都能看到。
- **慢慢理**：主界面里拆分子任务，用 Markdown 写详情，按需安排日期、查看任务日历。
- **排序与置顶**：主界面和菜单栏都能整组拖动、置顶任务，子任务跟随；也可按创建时间、名称或计划时间排序。
- **周末回顾**：汇总本周完成与尚未完成的事，一键复制为周报素材，再写自己的总结。
- **每日记录（个人定制）**：每天一篇本地 Markdown，菜单栏整页续写，工作台按日期浏览和补写；回顾可切换每日记录与任务，分别复制或复制全部。记录独立于任务，文件可从“打开记录文件夹”找到。

![ToDo 管理：左侧工作台，右侧菜单栏小窗](images/todo-management.png)

## 键盘活跃：思维净活跃时长

我还想知道一件事：用电脑的这些时间里，到底有多少是我本人在活跃。每隔几秒截一张图，再让 AI 分析我在干什么，这种方式隐私很难保证。所以我想从键盘输入入手。

我的想法很简单：**对电脑来说，我是在输入；对我自己来说，我是在输出。人在输出的时候，思维一定是活跃的。** 此时我和电脑的连接，就是双手十指之间的触碰。

> 回收伏笔：Toccata 源自意大利语 *toccare*，意为“触碰”。

我想用键盘记录自己在对外输出的时间，把它叫作 **「思维净活跃时长」**。这个概念在我看来很性感 🤔

- **按键热力图**：看看哪些键最常用，按下时也有实时反馈。
- **活跃时间线**：按天查看输入发生在哪些时段，也能回顾常用应用和 Fn 按住时长。
- **本机记录**：记录键码、时间、按住时长与应用归属，数据保存在本机，采集过程不截图、不录音。

![键盘活跃：逐键热力图与最近 7 天的活跃时间线](images/keyboard-activity.png)

> 「思维净活跃时长」是项目的创作概念，实际计时根据键盘活动估算，无法直接测量思维，也无法覆盖阅读、思考等全部投入。Fn 时长用于估算语音输出，也可能包含快捷键操作。详见[计算规则](develop.md#按键次数与活跃时间计算)。以上图片使用演示数据。

## 开始使用

适用于 **Apple Silicon Mac · macOS 13+**。从 [Releases](https://github.com/KMnO4-zx/Toccata/releases) 下载 DMG，将 `Toccata.app` 拖入“应用程序”即可安装。

安装支持应用内更新的版本后，可在“关于 Toccata → 检查更新”中下载新版，下载完成后点击“安装并重启”。下载支持取消和重试，安装前会保存任务与键盘记录；没有兼容安装包时仍可打开发布页。旧版本首次升级仍需手动安装。

键盘记录需要在“系统设置 → 隐私与安全性 → 输入监控”中授权；任务管理可以独立使用。

Toccata 常驻菜单栏，默认显示 Dock 图标，可在“设置 → 通用配置”中隐藏。点击菜单栏图标即可添加和管理任务；右键选择“打开工作台”查看完整界面。关闭工作台后继续在后台运行，选择“退出 Toccata”才会结束应用。

“设置 → 通用配置”集中提供外观、语言、喝水提醒、登录自启、Dock 图标和关于入口；左下角的外观、语言和关于入口继续保留。登录自启默认关闭。

菜单栏小窗新增“活动速览”，可在键盘与应用页面之间切换，查看今日或昨日数据。键盘页展示逐键热力图和 15 分钟活跃色条，悬停可查看详情；应用页按活跃时长列出全部应用，同时显示时长和按键次数，列表可滚动。通用配置中的“状态栏默认页面”可选择任务管理、任务日历或活动速览，默认任务管理；每次重新打开小窗都会使用这个选择。

在通用配置中，或右键菜单栏图标选择“喝水提醒…”，可开启按键计数提醒。默认每累计 8,192 次按键提醒一次，每天重新计数；可调整间隔、发送测试通知。首次开启需允许系统通知，按键计数沿用输入监控记录。关闭工作台后仍会提醒，退出应用后停止。

想按自己的习惯修改？构建与二次开发说明都在 [develop.md](develop.md)。


## 参与贡献

欢迎一起完善代码、文档、翻译和测试，参与方式见 [贡献指南](CONTRIBUTING.md)。Windows 版正在招募贡献者，欢迎到 [Windows 版本支持 #1](https://github.com/KMnO4-zx/Toccata/issues/1) 交流方案、认领功能；独立开发目录为 [apps/toccata-windows/](apps/toccata-windows/README.md)。

## 致谢 🙏

- <img src="images/logos/kimi.png" width="20" height="20" alt="Kimi Logo"> &nbsp; 感谢 **[Kimi 全球大使计划](https://www.kimi.com/zh-cn/lp/kimi-ambassador)**。 Kimi K3.1 Pro 是一个在审美设计领域很棒的模型！
- <img src="images/logos/openai-rounded.svg" width="20" height="20" alt="OpenAI Logo"> &nbsp; 感谢 **[OpenAI Codex For Open Source 计划](https://developers.openai.com/community/codex-for-oss)**，赠予我 12 个月的 ChatGPT Pro 订阅。GPT 6 Astra 是一个很棒的 Coding 模型！
- <img src="images/logos/volcengine.png" width="20" height="20" alt="火山引擎 Logo"> &nbsp; 感谢 **[火山 Hero 计划](https://developer.volcengine.com/)**。 豆包的多模态能力确实非常棒！
- <img src="images/logos/datawhale.png" width="20" height="20" alt="Datawhale Logo"> &nbsp; 感谢 **[Datawhale](https://datawhale.cn/)**。 在 Datawhale 可以遇到优秀的同行人。

</details>
