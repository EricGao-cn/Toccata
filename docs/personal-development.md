# Toccata 个人开发说明

个人 Fork 采用功能 worktree、个人主线、日常开发 CI 和固定标签发布的流程。定制代码允许公开，个人 App 通过 GitHub Release 分发并手动更新，不默认向上游提 Issue 或 PR。

本文是当前开发操作手册，发布与日用更新见 [个人稳定版流程](personal-release.md)，早期准备阶段和验收结果见 [历史记录](personal-history.md)。初始化、构建和测试均不意味着授权提交、推送、发布、安装或迁移日用数据。

`AGENTS.md` 是 Agent 默认读取的执行规则，保持简短，集中说明必须遵守的工作方式和边界。本文主要是供维护者阅读的操作手册，解释步骤、原因和例外，Agent 处理相关任务时也要参考。两者保持一致；新功能对话只需说明功能目标和验收标准，不必重复整段固定开场。

## 分支和 worktree

| 分支或标记 | 用途 |
| --- | --- |
| `main` | 干净的上游镜像，仅跟随 `upstream/main` |
| `codex/personal` | 个人主线，接收验收过的功能和上游升级 |
| `codex/feat/<name>` | 单个功能；较大改动使用独立 worktree |
| `codex/sync/<upstream-tag>` | 从个人主线出发，单独验证上游合并 |
| `personal-vX.Y.Z` | 个人正式发布的固定 Tag；不能移动或复用 |

GitHub 默认分支使用 `codex/personal`，让仓库首页和新克隆以个人版本为主；`main` 继续作为上游镜像，这两个职责独立。更新镜像不意味着立即更新个人主线：优先选择上游正式标签或一批明确提交，在 `codex/sync/*` 中审查、验证后整合。

功能在自己的分支开发、检查和测试，通过后按授权合回个人主线。新功能对话默认使用独立 worktree；小型维护或已有功能的继续修改可复用当前合适的工作目录，不必重复创建 worktree。稳定版本用 Tag 追溯，暂不增加长期 `stable` 分支。紧急修复从稳定 Tag 分支，之后合回个人主线。

worktree 共享 Git 对象和分支信息，不共享未提交文件、忽略配置或运行环境。不要强行让同一分支同时出现在两个 worktree 中，也不要把一个目录的 `.local-dev/config.json` 复制给另一个目录。已提交的规则和脚本会随个人主线进入新 worktree；仅存在于未提交工作区的文件不会自动带过去。

## 新功能对话的默认启动

1. 在 Codex 的 Toccata 项目中新建对话，**开启“新建工作树”，起始分支选择 `codex/personal`**。这会以个人主线为起点创建独立目录，不是在原目录直接开发。默认不夹带其他任务的未提交改动。
2. Agent 先阅读 `AGENTS.md` 和本文，确认功能目标、验收条件、本次授权范围，并检查当前目录、分支和 Git 状态。已有正确的功能 worktree 时直接复用，不重复创建，也不覆盖其中已有改动。
3. 若新 worktree 处于 detached HEAD，在其中创建 `codex/feat/<name>`。不要在原主目录先切走个人主线，也不要强制在两个目录同时检出 `codex/personal`。“创建并检出新分支”只操作分支，本身不创建独立工作目录。
4. 在功能 worktree 根目录运行 `./scripts/personal/dev init` 和 `./scripts/personal/dev check`，核对应用标识、数据目录、构建输出及工具链。仅工具链和下载缓存可共享，不复制其他目录的本机配置或日用数据库。
5. 在本次功能范围内实现、测试和自审，汇报改动、验证结果、未运行检查及剩余问题。初始化或隔离检查失败时先解决或报告阻碍，不绕过保护去使用正式环境。

以后新对话可以只写：

```text
新增功能：[目标及预期行为]。
验收标准：[可检查的结果]。
```

工作位置和基线仍需在界面中选对；仓库规则不能补救一个已经选错来源的 worktree。未提交的规则变更也不会自动进入从旧个人主线新建的对话。

## 日常开发 CI

独立入口为 [personal-ci.yml](../.github/workflows/personal-ci.yml)。包含该工作流的个人分支提交并推送后，以下 push 会触发检查：`codex/feat/**`、`codex/sync/**`、`codex/personal`。新建功能分支不要求先合入个人主线，也不要求更新版本号、写发布说明或创建标签。`main`、上游分支和标签推送不触发该工作流；删除分支时检查 job 跳过。本地编辑和本地提交不会触发远端运行。

日常 CI 仅在 `EricGao-cn/Toccata` 运行，以推送事件的精确 SHA 检出代码，使用只读 `contents` 权限且不保留 checkout 凭据，不传入 PAT、GitHub secrets 或发布 token。按分支 ref 分组，新 push 会取消同组较早的日常 CI；日常 CI 与发布工作流使用不同的并发组。事件与权限遵循 [GitHub 工作流语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)，分组行为见 [并发规则](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)。

检查包括推送范围的空白错误、规范资源同步、Python 脚本回归、个人 core 测试、上游完整 Swift 逻辑测试和个人模式专门测试。新分支没有有效的 before SHA，或 rebase 后旧提交不在检出历史中时，空白检查改用当前提交与个人主线的共同祖先。Swift 沿用已验证的双模式：上游模式只跳过交互式 WebKit 测试；个人模式使用 `TOCCATA_PERSONAL` 编译并只运行 `PersonalDistributionTests|PersonalReleaseUpdateTests`，覆盖数据路径保护以及禁止下载、准备和自动安装的策略，避免把两种分发模式的安装预期混在一起。各测试阶段有独立超时，最后检查测试未改变受版本管理的源码或资源。

runner 固定使用 Apple Silicon `macos-26` 和 Xcode 26.2，通过个人 `dev` 入口检查实际 SDK 与固定 Rust 版本，状态与工具链放在 runner 临时目录，构建输出留在忽略的 `.local-dev` 中。不读取本机配置、日用 App 或真实数据，不启动采集服务。回归测试可在临时 fixture 中构造合成归档；工作流不调用候选/正式打包或安装入口，不上传 artifact，不创建标签、Release 草稿或正式发布。既有 `personal-release.yml` 仍只负责固定个人标签的发布流程。

本地检查和隔离试用仍先进行；经授权推送分支后，日常 CI 补充本机缺少完整 Xcode 时无法运行的 XCTest。CI 通过不代表已合并、已发布或已安装，WebKit 交互验收仍需本地桌面。

## 审查后提交与合并

默认顺序为：实现 → 测试与审查 → 汇报 → 用户授权 → 功能分支本地提交 → 合并个人主线 → 验证结果。

用户只要求开发功能时，完成实现和验证后先汇报，不自动提交或合并。用户可在开始前或验收后明确授权，例如：

```text
审查通过后，把这个功能本地提交并合并到 codex/personal；不要推送，也不要更新日用 App。
```

已有明确的提前授权时，在满足条件后直接执行，不再重复询问；验证失败或存在阻塞问题时先报告，不以“已授权”为由跳过检查。只授权提交不等于授权合并，授权本地提交和合并也不等于授权推送、发布、安装或归档。

合并时先检查功能分支和目标目录的状态，保护已有改动。在已经检出 `codex/personal` 的工作目录中执行合并，不在功能 worktree 强制检出被占用的个人主线。若有冲突，解决后重新运行相关验证；无法确认行为时报告问题。完成后确认功能提交已包含在个人主线中，并检查最终差异和工作区状态。主线已有新改动时，还需验证整合后的结果，不能只依赖合并前的测试。

这些 Git 操作可由 Agent 执行，维护者不必手动输入命令。结束对话、“移交到本地”或生成一个功能提交，都不代替显式合并。合并源码不会自动构建、发布或替换稳定 App。

## 归档前检查

功能完成并合并后，可以归档该功能对话。归档前由 Agent 检查并报告：

- 功能已按授权提交，并确认包含在 `codex/personal` 中；若放弃功能或暂不合并，由用户明确决定如何保留或放弃成果，不为收尾而强行合并。
- 功能 worktree 的未提交修改、未跟踪文件以及需要保留的忽略文件均已检查和处理；不能仅凭 `git status` 干净就认为本机配置、日志或其他忽略文件已保存。
- 本 worktree 的开发 App、测试进程和需要落盘的编辑已正常结束。只处理当前任务拥有的进程，不退出或操作上游正式版、个人稳定版或其他 worktree 的 App。出现保存失败时先解决或报告，不强制清理。
- 需要保留的安装包、日志、配置和测试数据已有明确存放位置。外置数据不会因为源码已经合并而自动迁移或删除；共享工具链也不能当成本 worktree 的临时文件清掉。

Codex 托管 worktree 可能随对话归档而被清理。归档快照不是 Git 合并，不能代替对忽略文件和外置数据的管理。完成检查后，由用户在界面归档或明确要求 Agent 归档；合并授权本身不包含归档、删除功能分支或删除外置数据。未经授权，不自动归档或清理。

## 配置和文件边界

| 文件或目录 | 内容 |
| --- | --- |
| `scripts/personal/dev-defaults.json` | 可纳入 Git 的默认配置：SDK 26.2、Rust 1.99.1、开发身份前缀、debug 构建 |
| `scripts/personal/dev`、`dev.py` | 可重建的初始化、检查、构建、启动和测试入口 |
| `.local-dev/config.json` | 本机绝对路径、当前 worktree 身份；被忽略 |
| `.local-dev/{swift,target,cache,out}` | 当前工作目录专用的构建产物和缓存；被忽略 |
| 外置开发状态目录 | 新目录的测试数据和共享工具链；不进入 Git |

新目录默认把状态放在 `~/Library/Application Support/Toccata-Dev/`。目录路径的散列用于生成固定 worktree ID、独立 Bundle ID 和应用名称；切换分支不会改变同一目录的身份。每个目录的数据独立，构建输出也独立。关联 worktree 自动复用主目录配置中的 Cargo/Rustup 路径，只共享工具链和下载缓存。

配置绑定工作目录的物理路径，复制或移动后不能直接复用。需要迁移目录时，应先单独核对配置和数据中的绝对路径；不会自动搬迁或删除原外置数据，不通过修改身份绕过隔离检查。

**旧开发环境的兼容行为仍生效**：初始化会保留现有 `.local-dev/data/`、`cn.ericgao.toccata.dev` 身份及 `.local-dev/cargo`、`rustup`，不移动数据库，不改写已有数据配置。因此这里的 `.local-dev` 不只是缓存，不能整体删除。删除其他 worktree 之前也要先确认需要保留的文件和外置数据。

## 从新目录重建开发环境

在仓库根目录执行：

```bash
./scripts/personal/dev init
./scripts/personal/dev setup-rust
./scripts/personal/dev fetch
./scripts/personal/dev check
./scripts/personal/dev build
./scripts/personal/dev run
```

`init` 不下载依赖，已有配置会校验后原样保留。`setup-rust` 从 Rust 官方安装固定版本到专用目录，不修改 shell 配置；本机已安装的 stable 恰好为 1.99.1 时直接复用。Rust 命令会校验专用工具链和固定版本，缺失时明确报错，不退回全局 `cargo`。`fetch` 使用 `Cargo.lock`，不运行服务。Swift 包没有远程第三方依赖。

新目录首次初始化时，可以显式指定较短的开发状态目录，或复用已有工具链：

```bash
./scripts/personal/dev init \
  --state-root "/absolute/short/Toccata-Dev" \
  --tools-root "/absolute/shared-toolchains"
```

`--tools-root` 下应包含 `cargo/` 和 `rustup/`。这两个选项只影响首次生成配置；重复运行不会重置已有路径。macOS socket 路径有长度限制，脚本会拒绝过长路径。后续调整本机配置时，先退出对应开发 App、检查路径，再编辑 `.local-dev/config.json` 并重建；不自动迁移旧数据。

旧入口 `.local-dev/dev` 和 Bash 用的 `.local-dev/env.sh` 仅作兼容转发，源配置以仓库内脚本和本机 JSON 为准。新目录不需要复制旧脚本。高级验证可使用 `TOCCATA_DEV_CONFIG` 选择本工作目录 `.local-dev/` 内另一份配置；也必须经过身份与路径校验。

## App 和数据隔离

| 类型 | 身份与数据 |
| --- | --- |
| 上游正式版 | 原 `com.toccata.studio`、原数据目录；个人脚本不安装或替换它 |
| 开发版 | `cn.ericgao.toccata.dev.<worktree-id>`，独立偏好和测试数据；旧主目录保留历史身份 |
| 个人候选包 | 开发身份加 `.candidate`，测试目录下的 `personal-candidate/`；关闭采集与在线安装，可手动检查个人发布 |
| 个人稳定版 | `cn.ericgao.toccata.personal` 和独立的 `Toccata-Personal` 数据目录；构建、发布和安装各需单独授权 |

`dev build` 只生成本地、ad-hoc 签名的任务管理 App，不内嵌采集服务。生成的启动器会固定测试数据路径；不要绕过启动器直接运行包内的 `ToccataDevBinary`。日常使用 `dev run`，它会核对已构建 App 的身份、SDK 和数据路径是否仍匹配配置。包含完整 helper 的候选/正式包由独立的 `release.py` 构建，不与此入口混用。

脚本拒绝官方/个人稳定数据目录及其父子路径、错误的数据库/socket 重定向和符号链接运行文件。现有数据配置有问题时会报错，不会静默修复或覆盖。配置和打包机制不等于数据库同步，开发库不能作为稳定版升级时的数据来源。

普通任务开发版的上游更新页面仍来自现有应用源码；它不是个人更新渠道，不用于安装个人版本。个人候选包及稳定包通过独立编译入口手动检查 `EricGao-cn/Toccata` 的个人正式发布并打开下载页，仍禁用在线安装更新，采用手动校验包与离线安装流程。`scripts/personal/publish.py` 默认把已验证正式包整理为 DMG（可用 `--format zip` 保持 ZIP 兼容），不重新编译 App；本地草稿上传默认只输出计划。个人 Actions 入口在新标签推送或主线手动运行时构建 DMG 并创建草稿，没有正式发布模式；授权推送个人标签时需包含这项影响。操作流程见 [个人稳定版说明](personal-release.md#个人-github-actions构建-dmg-并停在草稿)。

## SDK 和验证

本地个人开发固定 SDK 26.2，不调用或放宽 `scripts/macos-toolchain.sh`。上游构建、DMG 打包和发布 workflow 仍要求 SDK 26.5。个人开发配置中的 `release` 仅表示优化构建，仍然是隔离开发包，不是个人稳定发行包。

```bash
./scripts/personal/dev test-scripts
./scripts/personal/dev test-core --features personal-distribution
# 以下两条需要完整 Xcode；分别验证上游模式与个人模式：
./scripts/personal/dev test-swift --skip MarkdownWebEditorTests
./scripts/personal/dev test-swift --filter 'PersonalDistributionTests|PersonalReleaseUpdateTests' -Xswiftc -DTOCCATA_PERSONAL
git diff --check
```

`test` 依次运行脚本、Rust、Swift 测试，CI 显式选择上述双模式与 WebKit 排除范围。只装 Command Line Tools 时，Swift 测试会明确报 XCTest 不可用；云端完整 Xcode 可以补充这些验证。报告中分别列出本地与云端结果、测试范围和跳过项，不能把脚本/Rust 通过等同于 XCTest 已运行。WebKit 测试还需要交互式桌面。`core` 仅供明确需要采集测试时手动运行，只构建并运行 debug 服务，不接受 `--release` 等构建参数；不会被初始化、构建或启动开发 App 隐式调用。

早期本地环境限制、退出提示和各阶段验收结果归档于 [历史记录](personal-history.md)。当前验证以对应提交的日志为准，机器诊断文件不是新 worktree 的重建依赖。

## 个人发布与日用更新

日常开发 CI、个人发布和日用 App 更新是独立操作：分支 push 只检查测试；新固定标签 push 触发构建和草稿上传；草稿经核验后确认发布；用户再手动下载安装。个人版可以检查更新、打开下载页，应用内自动下载安装保持禁用。

发布步骤见 [个人稳定版流程](personal-release.md#个人-github-actions构建-dmg-并停在草稿)：验收改动并按授权合入个人主线，更新 `scripts/personal/release.json` 与对应发布说明，再创建并推送新的固定 annotated 标签。候选包用于独立身份和测试数据中的验收；正式发布必须基于已接受的干净提交，不能通过重定向开发数据路径冒充稳定版。

已有个人版通常按 [普通 App 更新](personal-release.md#普通-app-更新)替换程序，继续使用原个人数据目录，不要求先执行数据迁移。备份根据当次授权安排，默认建议为有价值数据保留一致性快照；一次明确免备份的更新不代表后续默认免备份。新 App 启动时若升级数据库，是否能降级取决于版本兼容性，单独换回旧 App 不能恢复旧库。

接管上游记录、转换数据路径或恢复旧状态时，使用 [数据维护流程](personal-maintenance.md)。`maintenance.py install` 始终备份并成对替换 App/数据，需要已准备的数据副本，不是免备份的 App 更新入口。迁移、备份、回滚和中断恢复各有不同作用，不能通过删除 live WAL/SHM 或 pending 标记绕过校验。源码合并、构建和发布均不自动授权这些操作。

个人版本独立记录，已保留既有固定标签和安装包；当前个人稳定版为 `1.1.1 / build 3`，继续基于上游 `v0.1.4 / d5bd542`，发布说明见 [personal-v1.1.1](releases/personal-v1.1.1.md)。配置位于 `scripts/personal/release.json`；构建记录个人 Tag、SHA、SDK、架构和校验值，并验证已接受的干净提交。上游 `shared/app-version.json`、Rust 版本的一致性检查继续保留。新正式包须待验收、提交并合入个人主线，再获准创建新标签后生成；候选 ZIP 不能充当正式包安装，既有标签不移动或复用。

## 吸收上游更新

先获取实际发布 Tag 和变更说明；`main` 仅作上游镜像。从个人主线创建 `codex/sync/<tag>` 及临时 worktree，合并选定 Tag，逐处核对数据库迁移、任务行为、分发配置与更新源。用测试数据和备份副本验证后合回个人主线，再发布下一个个人版本。源码合并不会自动更新已安装 App。

保留合并历史，不反复重写已发布个人主线，不移动既有 Tag。自己的公开 Fork 可用于后续代码备份和发布，但提交、推送与发布仍按当次任务授权执行，不默认向上游创建 PR。
