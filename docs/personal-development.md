# Toccata 个人开发说明

个人 Fork 采用功能 worktree、个人主线和固定版本安装包的流程。定制代码允许公开，第一阶段手动更新个人稳定版，不默认向上游提 Issue 或 PR。

本文描述当前能用的开发入口，以及尚待实现的个人稳定分发约定。初始化、构建和测试均不意味着授权提交、推送、发布、安装或迁移日用数据。

## 分支和 worktree

| 分支或标记 | 用途 |
| --- | --- |
| `main` | 干净的上游镜像，仅跟随 `upstream/main` |
| `codex/personal` | 个人主线，接收验收过的功能和上游升级 |
| `codex/feat/<name>` | 单个功能；较大改动使用独立 worktree |
| `codex/sync/<upstream-tag>` | 从个人主线出发，单独验证上游合并 |
| `personal-vX.Y.Z` | 后续个人稳定版本的固定 Tag；不能移动或复用 |

功能在自己的分支开发、检查和测试，通过后合回个人主线。小改动不必额外创建 worktree。稳定版本用 Tag 追溯，暂不增加长期 `stable` 分支。紧急修复从稳定 Tag 分支，之后合回个人主线。

worktree 共享 Git 对象和分支信息，不共享未提交文件、忽略配置或运行环境。不要强行让同一分支同时出现在两个 worktree 中，也不要把一个目录的 `.local-dev/config.json` 复制给另一个目录。已提交的规则和脚本会随个人主线进入新 worktree；仅存在于未提交工作区的文件不会自动带过去。

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

**当前主目录兼容旧环境**：首次初始化会保留现有 `.local-dev/data/`、`cn.ericgao.toccata.dev` 身份及 `.local-dev/cargo`、`rustup`，不移动数据库，不改写已有数据配置。因此这里的 `.local-dev` 不只是缓存，不能整体删除。删除其他 worktree 之前也要先确认需要保留的文件和外置数据。

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
| 个人稳定版，尚未创建 | 计划使用 `cn.ericgao.toccata.personal` 和独立的 `Toccata-Personal` 数据目录 |

构建脚本只生成本地、ad-hoc 签名的任务管理 App，不内嵌采集服务。生成的启动器会固定测试数据路径；不要绕过启动器直接运行包内的 `ToccataDevBinary`。日常使用 `dev run`，它会核对已构建 App 的身份、SDK 和数据路径是否仍匹配配置。

脚本拒绝官方/个人稳定数据目录及其父子路径、错误的数据库/socket 重定向和符号链接运行文件。现有数据配置有问题时会报错，不会静默修复或覆盖。配置和打包机制不等于数据库同步，开发库不能作为稳定版升级时的数据来源。

开发版的上游更新页面仍来自现有应用源码；它不是个人更新渠道。不要使用它安装个人版本。未来需要显式关闭开发版安装更新，并给个人稳定版配置专属渠道；本阶段不改更新器。

## SDK 和验证

本地个人开发固定 SDK 26.2，不调用或放宽 `scripts/macos-toolchain.sh`。上游构建、DMG 打包和发布 workflow 仍要求 SDK 26.5。个人开发配置中的 `release` 仅表示优化构建，仍然是隔离开发包，不是个人稳定发行包。

```bash
./scripts/personal/dev test-scripts
./scripts/personal/dev test-core
./scripts/personal/dev test-swift
# 有完整 Xcode 时，按 CI 范围跳过交互式 WebKit 测试：
./scripts/personal/dev test-swift --skip MarkdownWebEditorTests
git diff --check
```

`test` 依次运行脚本、Rust、Swift 测试。当前 Command Line Tools 不包含 XCTest，Swift 测试会明确失败并显示未运行；不能把其他测试通过当作全套通过。WebKit 测试还需要交互式桌面。`core` 仅供明确需要采集测试时手动运行，只构建并运行 debug 服务，不接受 `--release` 等构建参数；不会被初始化、构建或启动开发 App 隐式调用。

截至 2026-11-01，SDK 26.2 已验证能构建并运行任务开发版；基线审查通过 39 项 Python 测试（含 14 项个人配置测试）、28 项 Rust 测试，以及入口的构建和签名检查。个人配置测试包含临时 Git 仓库中的实际 worktree 初始化和移除，验证了工具链共享、身份隔离及外置数据保留。Swift 测试仍缺少 XCTest。曾出现一次退出保存提示，后续 SDK 26.2 包装器/原生启动及 SDK 26.5 隔离对照未自然复现，原因仍未确认。不能记为已修复，也不能归因于 SDK。旧诊断记录保留在本机 `.local-dev/diagnostics/`；它们不是重建开发环境的依赖。

## 后续个人稳定版和手动更新

这一节是分发约定，**当前没有个人稳定包构建、安装或自动更新命令**。

个人稳定分发需要独立入口，不能通过把开发配置指向日用数据来冒充稳定安装器。

1. 将验收过的功能合入个人主线，冻结干净提交。
2. 从该提交构建候选包，在独立标识、偏好和测试数据的验收副本中验证。
3. 记录个人版本、固定 Tag、完整 SHA、上游基线、SDK、架构和安装包校验值。
4. 经用户授权，退出个人稳定版并做一致性备份，再手动替换个人稳定 App。
5. 新版只迁移自己的稳定库；保留上一安装包和匹配的数据备份。回退 App 不代表数据库可以安全降级。

首次从上游正式版接管数据需要单独安排备份和副本验证，不复用上游的应用身份。不要直接复制仍在写入的单个 SQLite 文件；WAL 可能包含未合并数据。先验证备份与恢复，再考虑迁移日用记录。

个人版本建议独立记录，例如个人 `1.0.0` 基于上游 `v0.1.2 / 7020d69`。现有版本校验、Bundle ID、更新器和发布 workflow 尚不支持这套分发规则，不能仅改一个仓库名或 Tag 就认为接入完成。上游 `shared/app-version.json`、Rust 版本的一致性检查继续保留。个人版本配置与对应测试在分发任务中再实现。

## 吸收上游更新

先获取实际发布 Tag 和变更说明；`main` 仅作上游镜像。从个人主线创建 `codex/sync/<tag>` 及临时 worktree，合并选定 Tag，逐处核对数据库迁移、任务行为、分发配置与更新源。用测试数据和备份副本验证后合回个人主线，再发布下一个个人版本。源码合并不会自动更新已安装 App。

保留合并历史，不反复重写已发布个人主线，不移动既有 Tag。自己的公开 Fork 可用于后续代码备份和发布，但提交、推送与发布仍按当次任务授权执行，不默认向上游创建 PR。
