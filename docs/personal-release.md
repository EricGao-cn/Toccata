# 个人稳定版：打包、安装、备份、迁移与回滚

## 当前阶段和身份

个人版本基于上游 `v0.1.4`，通过个人 GitHub Release 分发，本机手动安装。既有个人标签和安装包不移动、不覆盖；当前准备版本为 `1.1.1 / build 3`，发布说明见 [personal-v1.1.1](releases/personal-v1.1.1.md)。须验收并获得相应授权后才能提交、打新标签、推送和发布。配置位于 `scripts/personal/release.json`，不会改写上游 `shared/app-version.json` 或移动上游标签。

| 类型 | Bundle ID | 数据目录 | 采集与更新 |
| --- | --- | --- | --- |
| 上游日用版 | `com.toccata.studio` | `~/Library/Application Support/Toccata/` | 沿用上游 |
| 隔离开发版 | `cn.ericgao.toccata.dev.<worktree-id>` | 各工作树的独立测试目录 | task-only，沿用开发入口 |
| 个人候选包 | 开发身份再加 `.candidate` | 当前工作树测试目录下的 `personal-candidate/` | 不启动采集、不请求输入监控；可手动检查个人发布，不能应用内安装 |
| 个人稳定版 | `cn.ericgao.toccata.personal` | `~/Library/Application Support/Toccata-Personal/` | 独立个人采集服务；检查个人 GitHub 发布，手动下载安装 |

默认安装位置为 `~/Applications/Toccata Personal.app`。上游 `/Applications/Toccata.app` 保留原样。个人编译入口固定 SDK 26.2，不放宽上游 SDK 26.5 guard；正式包记录实际 SDK、架构、提交、个人 Tag 和上游基线。

个人版客户端和采集服务都固定使用个人数据命名空间；不会沿用旧 `TOCCATA_DATA_DIR`、`db_path` 或 `socket_path` 将其指回上游数据。运行时会拒绝目录/数据库的符号链接、关键文件硬链接及待恢复的维护事务，防止别名绕过隔离或中断后误开不匹配的数据。候选包使用更严格的开发命名空间，包含的采集二进制只用于核验完整打包，不会由候选客户端启动。

## 本轮允许做的准备

```bash
./scripts/personal/dev init
./scripts/personal/dev check
python3 -B scripts/personal/release.py plan
python3 -B scripts/personal/maintenance.py plan
python3 -B -m unittest discover -s scripts/tests -p test_personal_release.py -v
python3 -B scripts/personal/release.py build-candidate
```

这些命令不会安装 App、迁移真实记录、修改登录项或授权输入监控。测试只操作临时模拟 App、合成 SQLite 库和 Markdown。候选构建允许未提交源码，但清楚标记 `personal-candidate` 与 dirty 状态，正式安装器会拒绝它。

产物在 `.local-dev/personal-packages/candidate-<id>/`，另有 ZIP 和 `.zip.sha256`。目录内包含完整 `.app`（客户端、同版个人采集 helper、资源）、`release.json` 及其校验值。验证示例：

```bash
python3 -B scripts/personal/release.py verify /absolute/path/to/candidate-directory --candidate
```

这是 ad-hoc 签名的本机自用候选包，不代表 Developer ID 签名、公证或公开发行。

## 正式包的前置条件

1. 验收本次流程实现，明确授权后提交并合入 `codex/personal`。
2. 选定最终个人版本，在该已接受的干净提交创建固定的 **annotated** `personal-v<version>` Tag；不移动或复用个人 Tag，不覆盖任何上游 Tag。
3. 记录提交 SHA、Tag 对象、上游 SHA、SDK 和安装包 SHA-256。
4. 再执行正式构建：

```bash
python3 -B scripts/personal/release.py build-release --tag personal-v1.1.1
python3 -B scripts/personal/release.py verify /absolute/path/to/personal-v1.1.1
```

源码不干净、Tag 与 HEAD 不一致、不是 annotated Tag、提交未纳入个人主线、上游 Tag 与固定 SHA 不一致时，正式构建拒绝执行。不会自动提交、打 Tag、推送、发布、安装或启动。正式输出目录已存在时拒绝覆盖。

## 个人 GitHub Release：本地准备、草稿、人工发布

固定更新源为 `EricGao-cn/Toccata`。个人版在“关于 Toccata → 个人版更新”中手动检查 `personal-vX.Y.Z` 正式发布，并提供“打开下载页”。仅打开关于窗口不联网；不会下载、解压或安装更新，也不会上传任务、日记和键盘记录。不使用仓库的通用 latest 标记，按数值比较个人标签，排除上游标签、草稿、预览版和非法版本。列表分页最多 10 页；读取不完整时显示失败，不误报已是最新。

当前客户端匿名检查公开发布。私有仓库、尚无个人正式发布、限流或网络失败均显示可重试的状态；可用发布页面入口在浏览器登录查看，不向 App 写入 GitHub token。普通上游构建继续使用原上游更新流程。

下面是**未来得到相应授权后**的发布步骤，本地准备不会隐式推送或发布：

1. 验收并合入 `codex/personal`，为干净提交创建新的固定 annotated 标签，再生成并验证正式包。候选包不能发布为稳定版。
2. 使用独立入口准备发布素材：

```bash
python3 -B scripts/personal/publish.py prepare \
  --package /absolute/path/to/personal-v1.1.1 \
  --notes docs/releases/personal-v1.1.1.md \
  --format dmg \
  --output /absolute/path/to/new-github-release-bundle
python3 -B scripts/personal/publish.py plan \
  --bundle /absolute/path/to/new-github-release-bundle
```

准备入口读取已验证正式包、固定标签和个人主线包含关系；只打包白名单中的 App、包内发布清单及其校验值，不收集包旁边的开发数据或运行目录。默认输出 `Toccata-Personal-<version>-<arch>.dmg`、SHA-256、清单和发布说明；也可显式使用 `--format zip` 保持原 ZIP 分发方式。既有 ZIP 发布素材及其校验仍兼容，不覆盖已有输出。

DMG 使用无加密、无交互许可协议的压缩只读 UDZO 容器。验证先制作校验值一致的私有镜像副本并设为只读文件，再仅将该副本只读挂载到私有目录；不会关闭或复用用户手动打开的原镜像。卷根目录只允许 App、两个清单文件和安装说明，隐藏目录也不豁免；读取 JSON/说明前检查文件类型和大小，拒绝符号链接、FIFO 及超大文本。App 签名、文件内容、权限和源镜像校验通过后，按私有副本对应的整盘设备正常推出，并再次确认设备及挂载点消失。若设备与其他镜像共用、归属无法确认、创建中断，或挂载/推出后无法确认设备已消失，工具保留现场和 recovery.json，不强制推出，不递归删除可能仍在使用的目录，也不发布半成品。ZIP 路径仍重新解压验证；两种格式都在校验结束后复核素材未变。整个过程不安装或启动 App。

镜像根目录包含 `Toccata Personal.app`、`release.json`、清单校验值和 `安装说明.txt`。说明沿用个人安装位置 `~/Applications/Toccata Personal.app`，不写入构建机器用户名，也不放置指向系统 `/Applications` 的快捷方式，避免把现有个人安装混成两个入口。打开 DMG 后，在 Finder 用“前往文件夹”打开 `~/Applications`，退出旧个人版后拖入 App，推出镜像再启动。

安装说明是有大小上限的 UTF-8 文本，并须标明对应个人版版本；验证不依赖当前工具的逐字文案，以便旧 DMG 在说明措辞更新后仍可校验。外层素材 SHA-256 继续核对原镜像的完整字节。

仅将已验收 App 从 ZIP 改装进 DMG 时，应用版本、签名与原标签不变；当前已安装版本无需重装。给既有 Release 追加 DMG 和校验文件仍须单独授权，并先检查远端资产及发布策略；保留原 ZIP 链接，不移动标签或覆盖已发布资产。

3. **另行授权**后将个人分支和固定标签推送到自己的仓库。本工具不执行 push，也不在远端自动创建标签。
4. **获得上传授权**后创建 GitHub 草稿。默认仍只输出计划，实际上传要求两个执行标记：

```bash
python3 -B scripts/personal/publish.py create-draft \
  --bundle /absolute/path/to/new-github-release-bundle
# 获准上传后追加：--execute --ack-upload
```

上传入口固定仓库、核对远端 annotated 标签对象与提交、拒绝覆盖已有正式发布或草稿，再用 `gh release create --draft --verify-tag` 上传。联网前会复制并重新验证私有上传快照，上传只读取该快照，避免等待期间源文件的编辑混入。ZIP 的顶层内容必须是 App 和两个清单文件，归档名称中的架构须与包清单一致。GitHub CLI 需预先认证；接口失败或标签不匹配时拒绝写入。不自动发布、替换或删除草稿；上传失败时保留原素材目录与远端现场，先在 GitHub 检查，不盲目重试覆盖。

5. 在 GitHub 草稿中人工核对版本、说明、DMG（或兼容 ZIP）和校验值，**另行授权发布**后点击 Publish release，保持为正式版本。App 随后才能检测到它。历史版本和标签保留。

从发布页下载个人安装包 DMG，或历史版本保留的安装包 ZIP；GitHub 自动提供的 Source code 压缩包不是可运行安装包。DMG 挂载后、ZIP 解压后均含 `Toccata Personal.app` 和配套 `release.json`，也可作为下述维护安装入口的 `--package` 来源。GitHub 分发不替代已有数据备份；需要接管旧数据时才使用可选迁移流程。应用内一键安装保持禁用。当前 App 为 ad-hoc 签名，DMG 本身不会使其获得 Developer ID 公证。

## 个人 GitHub Actions：构建 DMG 并停在草稿

独立入口为 [personal-release.yml](../.github/workflows/personal-release.yml)，复用上述 `release.py`、`publish.py` 和 `disk_image.py`。上游 `release.yml` 保持原样。此入口需先验收、合入并推送后才会在 GitHub 生效；本地实现和测试不会触发它。

启用后的触发方式：

- **推送新个人标签**：`personal-vX.Y.Z` 的 tag push 自动开始构建并创建草稿。普通分支推送、上游标签和 PR 不触发。未来授权推送个人标签时，也应明确知道这会开始云端构建和草稿上传。
- **手动重跑**：GitHub → Actions → Personal release draft → Run workflow，分支选 `codex/personal`，填写已推送的固定个人标签。只在尚无同名 Release 或草稿时可用；重跑不会覆盖之前的输出。

新版本必须先更新 `scripts/personal/release.json` 的个人版本/build，以及 `docs/releases/personal-vX.Y.Z.md`，验收、提交并合入个人主线后创建 annotated 标签。标签必须指向包含本工作流和 CI 入口的提交，且已纳入 `codex/personal`；版本、固定上游基线和工作区状态仍由正式打包入口核对。不要用旧 `personal-v1.1.0` 测试，也不要为重试移动或重用标签。首次云端构建使用新的 `personal-v1.1.1`，保留既有发布。

工作流只允许 `EricGao-cn/Toccata`，使用 Apple Silicon `macos-26` runner，显式选择 `/Applications/Xcode_26.2.app/Contents/Developer` 并检查 SDK 26.2、固定 Rust 版本和 arm64 架构。runner 若不再提供该 Xcode/SDK，构建直接失败，不退回默认 SDK。工具链、测试数据和输出都在临时 runner / `.local-dev` / `dist` 内，不需要本机配置、App 或数据库。

两个 job 的职责与权限：

1. **build（contents: read）**：先检出已接受的 `codex/personal`，用其中的校验脚本解析 annotated 标签并确认提交属于个人主线，之后才检出解析所得的精确 SHA；不先运行待校验标签里的脚本。再次核对标签对象未变、版本、上游基线、非空更新说明与远端同名发布，再初始化隔离环境，分别运行脚本回归、个人 core、上游完整 Swift 逻辑测试及个人模式专门测试。上游模式仅跳过交互式 `MarkdownWebEditorTests`；个人模式单独运行 `PersonalDistributionTests|PersonalReleaseUpdateTests`，其中包含禁止下载、准备和安装的保护验证。上游自动安装的正向测试只在上游模式运行，避免在个人版明确拒绝回调后无限等待。各测试阶段有独立超时和日志步骤。只读 token 的草稿可见性有限，最终防重检查仍在持写权限的 draft job 中执行。构建完整 ad-hoc 签名 App，生成并只读挂载校验 DMG；将 DMG、两个清单及校验文件、更新说明、发布素材元数据作为 Actions artifact 保留 14 天。另将提交、标签对象和 DMG SHA-256 作为独立 job 输出。
2. **draft（contents: write、actions: read）**：从精确构建提交检出代码，按 build 输出的固定 artifact ID，显式通过当前仓库和当前 workflow run 的 REST 接口下载素材。`actions: read` 只用于读取 artifact；ID 缺失或非法时失败，不退回下载全部 artifact。只重跑失败的草稿 job 时仍使用原成功 build 的 ID，不按新 attempt 猜测名称。再次核对固定标签、主线、App 签名、DMG 内容、清单、架构与独立 job 输出的 SHA-256，并将 artifact 更新说明与标签中的已提交原文比对。创建私有上传快照后，仅执行 `gh release create --draft --verify-tag`。上传后用认证的分页 Release 列表定位唯一草稿，再按数字 Release ID 回读状态、版本、说明和全部四个附件的 SHA-256，并再次检查远端标签对象和提交未变，通过后输出草稿链接；不使用仅针对已发布版本的按标签查询接口。`GH_TOKEN` 只传给校验/上传脚本；官方 checkout/download action 使用各自 job 的 token，checkout 不保留认证信息。不使用长期 PAT，不执行 push、移动标签、删除或覆盖资产。

上传前校验失败不会创建草稿；上传中断或上传后回读失败可能留下需要检查的草稿，错误会提示先查看发布页，工作流不会自动重试、删除或覆盖它。同标签并发最多执行一个运行，不取消正在构建/上传的运行；GitHub 可能用较新的等待运行替换旧的等待运行。后来的运行若发现已有草稿/发布就失败并保留现场。先核对 Actions 日志、artifact 和 GitHub 草稿，再决定后续操作；不要自动清除失败草稿或重用已发布标签。

正式发布始终在 GitHub 草稿核对后由维护者点击 **Publish release**，工作流没有 publish 模式。草稿不会被 App 的更新检查识别；发布也不会安装到本机。当前仍为 ad-hoc 签名、未公证，Actions 不会自动改变签名方式；本地手动打包和 ZIP 兼容入口继续可用。

工具链参考：[macOS runner 镜像](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md)、[GitHub 事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[工作流权限](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)。首次远端运行前应确认仓库 Actions 已启用且策略允许固定 SHA 的官方 actions；之后另行授权推送和执行，不为本地验证修改仓库设置。

首次运行还须确认 Fork 包含配置中的固定上游标签；`main` 已包含上游提交不代表同名标签也已同步。若缺失，只能在核对本地与上游标签对象完全一致后单独同步，不覆盖既有标签。仅修正 Actions 编排时，可从个人主线手动运行修正后的工作流并指定原有固定个人标签；App 仍构建该标签的原提交，工作流提交与 App 源码提交分别记录，不移动标签。

## 当前首次使用方案：全新个人数据，不迁移

按当前使用决定，首次个人版安装采用全新的 `Toccata-Personal` 数据目录，不迁移上游任务、键盘历史或开发试用数据。原版 App、原数据和已做的备份保留，不删除、不重置。

本轮只实现和隔离验证，不实际安装。后续获准安装时，正常退出原版及 helper，将经过验证的个人 App 放到 `~/Applications/Toccata Personal.app`，核对个人目标目录原本不存在，再首次启动建立空数据库。若目标已有 App 或数据，先核对其来源，不能通过清空目录来强行按全新安装处理。两套采集服务不同时运行，输入监控等系统权限由用户确认。

下载检查不依赖迁移。以下迁移与成对安装流程作为可选维护能力保留，当前首次安装不以迁移演练为前置条件；今后个人版自身更新仍须备份已有数据。

## 可选迁移：先快照，再副本验证

以下为**未来正式迁移时的操作说明**，本轮不执行。所有 `backup`、`stage-migration`、`install`、`rollback` 命令默认只输出计划；真正执行必须显式追加 `--execute --ack-stopped`，并先完成该阶段的用户授权。脚本不会替用户退出程序、停止服务、修改系统权限或启动应用。

### 1. 正常退出并保存

通过 App 的“退出 Toccata”正常退出上游、个人版及开发版，等待其 helper 停止，并暂停外部编辑器对记录目录的写入。脚本会检查进程和数据锁，无法验证退出时拒绝执行。不要仅关闭工作台，不要强杀仍有未保存内容的进程。整个维护期间保持应用和所有写入者退出；这不是在线协同迁移协议。

测试副本验收期间可以继续使用原版；**正式切换前必须重新退出并制作最新快照**，不能用几天前的演练副本覆盖后续新增的日常记录。

### 2. 备份上游 App 和数据

先查看计划（示例路径，输出目录必须全新）：

```bash
python3 -B scripts/personal/maintenance.py backup \
  --app /Applications/Toccata.app \
  --data "$HOME/Library/Application Support/Toccata" \
  --output "$HOME/Toccata-Backups/upstream-before-personal"
```

获准正式执行并确认退出后，才在同一命令末尾追加 `--execute --ack-stopped`。

备份包含原 App、任务库、键盘原始库、每日记录与附件、配置及其他普通数据文件。SQLite 使用备份 API 合并已提交 WAL 数据，不是单独拷贝 `tasks.sqlite`；备份库转为独立文件，带 `quick_check`、各表行数、文件 SHA-256 和目录/文件权限清单。SQLite 逻辑快照会保留源数据库权限；校验也会发现执行权限被修改。备份前后检查源树，发现内容、文件集合或权限变化时拒绝发布快照。只有数据根目录中的 socket/lock 和 SQLite WAL/SHM 属于运行时文件；日记附件即使同名也保留。

本轮审查后的备份格式为 **schema 2**，旧 schema 1 的预演快照需要重新生成。工具不会把缺少完整性信息的旧预演结果用于正式恢复。

macOS SQLite 可能在 WAL 转为 DELETE 并关闭连接后仍留下 `-shm`。备份工具只在新建副本中确认数据库文件头为回滚日志格式（读写版本均为 1）、且不存在 WAL 或恢复 journal 后清除残留 SHM；存在 journal（即使为空）或转换未完成时拒绝继续，不删除可能承载数据的文件。旧 schema 2 备份的兼容范围是完整的独立数据库加残留 SHM；只清理新生成的迁移副本，保留旧备份原样。备份验证和安装前校验在连接 SQLite 前检查这些条件；旧备份若仍是 WAL 模式或带有 WAL/恢复 journal，会直接拒绝，不尝试恢复或忽略日志。源数据若带有回滚 journal，也须先另行恢复，备份入口不打开其数据库。迁移输出在发布前还须通过与安装入口相同的数据校验，日记附件中的同名文件不受清理影响。

备份拒绝覆盖已有输出、路径相互包含、符号链接、非法文件、应用库的孤立 WAL、指向源目录之外的数据库或 socket。自定义数据库/socket 文件名也需要先设计明确映射，不会只改配置路径而遗漏原库。应用自身的根目录数据库会转成 SQLite 快照；日记目录内的 `.db`、`-wal`、`-shm` 附件仍按普通文件逐字节保存。备份保留数据库及子目录权限，目录清单与模式一同校验。备份目录使用私有权限，不放进 Git 或云端。

```bash
python3 -B scripts/personal/maintenance.py verify-backup "$HOME/Toccata-Backups/upstream-before-personal"
```

### 3. 生成迁移副本

```bash
python3 -B scripts/personal/maintenance.py stage-migration \
  --backup "$HOME/Toccata-Backups/upstream-before-personal" \
  --output /absolute/path/to/new-staging-data
```

同样默认只输出计划。执行时只读取已校验备份，输出到全新副本，将 `config.json` 的数据库与 socket 路径改为个人版目标。数据库表内容和 Markdown 原文保持不变，原备份不修改。

若要保留开发试用中写下的真实日记，可以显式加 `--extra-notes /absolute/path/to/chosen/daily-notes`；不要导入开发版测试任务库。已有同名且内容不同的日记会拒绝合并，不会覆盖；先在副本中人工处理。任何中途错误都不会发布半成品 staging 目录。

验收副本时核对：任务数量、名称、详情、日期、子任务关系、完成状态、置顶、手动排序，键盘历史与应用统计，日记日期和附件。完整 Xcode 不可用时需明确记录 XCTest 未运行；副本验证不能替代最终人工验收。候选版关闭采集，历史库可用于读取验证；真实采集能力留到获准切换后验证。

## 安装个人版

固定 Tag 的正式包通过校验、迁移副本验收后，先查看安装计划：

```bash
python3 -B scripts/personal/maintenance.py install \
  --package /absolute/path/to/extracted/personal-v1.1.0 \
  --staged-data /absolute/path/to/new-staging-data \
  --backup "$HOME/Toccata-Backups/personal-before-install"
```

只有得到正式切换授权后才追加执行参数。安装器拒绝候选包、校验失败的包、带 WAL/SHM 的非独立 staging 数据，以及个人目标位置中身份不匹配的 App。它先备份个人目标的当前状态（首次安装也记录“原本不存在”），在各目标文件系统中准备并重新校验 App 和数据，再成对替换。普通异常会恢复原来的一对；进程退出等中断按下一节恢复。维护操作互斥执行，输出采用不覆盖已有目标的原子发布。原路径和失败文件都保留为带唯一标识的历史副本，不自动清理。

## 中断恢复：先 recover，再启动 App

App 和数据可能位于不同文件系统，因此成对替换不是跨卷的瞬时原子操作。工具在第一次 live 重命名前写入并刷盘 `<backup>.transaction.json`，以及个人数据目录旁的 `.Toccata-Personal.maintenance.pending.json`。普通异常会按日志恢复；若发生进程强制退出，日志和安装前快照保留在磁盘。

待恢复标记存在时，个人版客户端、collector 和后续安装/回滚都会拒绝继续。工具在开始 live 替换前再次检查退出状态；若应用重新启动则终止操作并保留新工作，不强退应用。保持 App 退出，先查看恢复计划：

```bash
python3 -B scripts/personal/maintenance.py recover \
  --backup "$HOME/Toccata-Backups/personal-before-install"
```

获得实际恢复授权后才追加 `--execute --ack-stopped`。工具校验快照、日志、目标路径及原始版本，保留中断后出现的文件，恢复原来的一对，并清除待恢复标记。恢复可以重复执行；已完成的事务只清理标记，不会回退到更旧版本。未开始写入的陈旧日志不能影响后来的安装。回滚本身若被中断，使用其 `--recovery-backup` 所对应的日志恢复到“回滚开始前”的状态，再决定是否重试回滚。

不要手工删除 pending 标记来强行打开 App。日志或原始恢复树损坏时，工具会拒绝猜测并保留文件；需要人工核对完整备份后恢复。日志和复制结果使用 fsync，但不承诺对所有文件系统、损坏硬件或断电情形提供数据库级跨卷事务保证。

安装完成后由用户手动打开 `~/Applications/Toccata Personal.app`，完成验收。输入监控、通知、登录启动和外观等设置不直接复制旧 plist；新身份的系统权限需要重新确认。首次迁移可以按实际需要手动恢复偏好，避免把旧登录项或旧路径带入个人版。未确认前保持原上游 App 和原数据原样，不同时运行两套采集服务。

安装器不会自动打开新 App；因此安装本身不会开始采集。稳定客户端实际运行后仍使用本地采集模型，不采集截图、音频或输入正文。原始任务/日记只保存在本机。

## 回滚：恢复应用与数据这一对

先关闭个人版“登录时启动”，正常退出个人版及 helper，再查看回滚计划：

```bash
python3 -B scripts/personal/maintenance.py rollback \
  --backup "$HOME/Toccata-Backups/personal-before-install" \
  --recovery-backup "$HOME/Toccata-Backups/personal-before-rollback"
```

未来授权执行时追加执行参数。先完整保留当前版本及其新增工作，再恢复安装前 App 和数据库。回滚快照必须与目标路径匹配，App 必须是个人稳定身份；校验失败时不替换当前数据。**只换回旧 App 不会回退数据库。**恢复旧快照后，后来的新增日记和任务仍在 recovery backup 中，必要时另行人工取回，不能将两份 SQLite 文件直接覆盖合并。

首次安装的安装前快照记录个人版不存在；回滚会把当前个人 App 和数据保留为恢复副本，并恢复到个人目标不存在的状态。原上游 App 和原目录从未被替换，可继续使用。若后续个人版已有新工作，先处理 recovery backup，再决定何时重新开始在上游记录，避免分叉。

登录项、输入监控、通知等系统设置仍由用户人工检查；脚本只恢复 App 和本地数据，不自动改写系统授权或将旧偏好 plist 覆盖到新身份。

所有历史 `.previous-*`、`.failed-*`、备份、候选包和工作树都由用户另行决定清理；本流程不自动归档或删除。

## 本轮验收清单

- 计划命令无副作用，缺少执行/退出确认参数会拒绝实际变更。
- 活跃进程或数据锁阻止离线操作，程序不强退其他版本。
- WAL 中的已提交记录进入快照，原始 Markdown 与附件逐字节保留。
- 损坏备份、同名日记冲突、源/目标交叠、符号链接、外置路径会被拒绝。
- App 与数据同步升级；注入第二阶段失败后能恢复原状态。
- 回滚恢复匹配版本与数据，并保留回滚前新增的工作。
- 正式包要求固定个人 Tag、干净且已接受的提交、正确 SDK 与完整校验值。
- 候选包不触及上游/个人稳定数据，不启动 collector；个人版在线更新入口禁用。
