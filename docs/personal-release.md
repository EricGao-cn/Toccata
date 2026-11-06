# 个人稳定版：发布与日常更新

## 当前状态与身份

截至 2026-11-06，个人版发布、日常开发 CI 和手动更新均已验收使用。本页描述当前流程；早期“只准备、不安装”等限制与当时的测试结果见 [历史验收记录](personal-history.md)。文档描述能力，不构成一次新的执行授权。

个人版本基于上游 `v0.1.4`，通过个人 GitHub Release 分发，本机手动安装。既有个人标签和安装包不移动、不覆盖；当前个人稳定版为 `1.1.1 / build 3`，已通过 Actions 构建并核验后正式发布，说明见 [personal-v1.1.1](releases/personal-v1.1.1.md)。后续版本须验收并获得相应授权后才能提交、打新标签、推送和发布。配置位于 `scripts/personal/release.json`，不会改写上游 `shared/app-version.json` 或移动上游标签。

| 类型 | Bundle ID | 数据目录 | 采集与更新 |
| --- | --- | --- | --- |
| 上游日用版 | `com.toccata.studio` | `~/Library/Application Support/Toccata/` | 沿用上游 |
| 隔离开发版 | `cn.ericgao.toccata.dev.<worktree-id>` | 各工作树的独立测试目录 | task-only，沿用开发入口 |
| 个人候选包 | 开发身份再加 `.candidate` | 当前工作树测试目录下的 `personal-candidate/` | 不启动采集、不请求输入监控；可手动检查个人发布，不能应用内安装 |
| 个人稳定版 | `cn.ericgao.toccata.personal` | `~/Library/Application Support/Toccata-Personal/` | 独立个人采集服务；检查个人 GitHub 发布，手动下载安装 |

默认安装位置为 `~/Applications/Toccata Personal.app`。上游 `/Applications/Toccata.app` 保留原样。个人编译入口固定 SDK 26.2，不放宽上游 SDK 26.5 guard；正式包记录实际 SDK、架构、提交、个人 Tag 和上游基线。

个人版客户端和采集服务都固定使用个人数据命名空间；不会沿用旧 `TOCCATA_DATA_DIR`、`db_path` 或 `socket_path` 将其指回上游数据。运行时会拒绝目录/数据库的符号链接、关键文件硬链接及待恢复的维护事务，防止别名绕过隔离或中断后误开不匹配的数据。候选包使用更严格的开发命名空间，包含的采集二进制只用于核验完整打包，不会由候选客户端启动。

## 先选择需要的操作

| 场景 | App 与数据如何处理 | 使用入口 |
| --- | --- | --- |
| 普通 App 更新 | 替换个人 `.app`，继续使用现有个人数据目录 | 下方手动更新流程；无需先做迁移副本 |
| 一致性备份 | 读取指定 App 和数据，保存新快照，不替换源目录 | [备份](personal-maintenance.md#备份) |
| 数据迁移 | 从已校验备份制作副本、转换路径，先验收副本 | [数据迁移副本](personal-maintenance.md#数据迁移副本) |
| 成对安装 | 先备份个人目标，再同时替换 App 与已准备数据 | [成对安装](personal-maintenance.md#成对安装) |
| 成对回滚 | 保存当前工作后恢复匹配的旧 App/数据快照 | [成对回滚](personal-maintenance.md#成对回滚) |
| 中断恢复 | 按事务日志处理未完成的成对替换，不等于主动降级 | [中断恢复](personal-maintenance.md#中断恢复) |

普通更新不主动搬移或覆盖数据目录。新 App 启动时可能升级自己的数据库 schema，应先阅读发布说明；数据路径、身份或数据库兼容性发生变化时，单独安排备份和副本验证。

## 首次安装个人版

在没有个人 App 和个人数据的目标上，下载并校验正式 DMG，将 App 放到 `~/Applications/Toccata Personal.app`，推出镜像后启动，可建立空个人数据。原版 App 与上游数据保留，不要求导入它们。若要接管原版记录，按 [数据迁移流程](personal-maintenance.md#数据迁移副本)准备；若个人目标已存在，先核对来源，不能通过清空目录强行当作首次安装。

## 普通 App 更新

适用于已经安装个人版、继续使用同一身份与数据目录的情况：

1. 在当前个人版“关于 Toccata → 个人版更新”点击“检查更新”，通过“打开下载页”进入正式 Release。
2. 下载 DMG 和 SHA-256，核对版本、架构、校验值与发布说明。GitHub 的 Source code 压缩包只含源码。
3. 根据当次方案决定备份；默认建议为有价值的数据保留一致性备份，尤其是发布说明涉及数据库变化时。明确选择不备份只适用于该次更新，不提供数据回滚保障。
4. 完成保存，从 App 菜单正常退出个人版，等待采集 helper 停止。
5. 若当次方案包含备份，先按 [备份流程](personal-maintenance.md#备份)生成并校验快照。随后打开 DMG，将其中的 `Toccata Personal.app` 拖到 `~/Applications` 替换已有个人 App；数据目录保留原位。
6. 推出镜像，从安装位置启动，核对版本、任务、每日记录、键盘历史与采集连接。输入监控等权限按系统实际提示由用户确认，不自动改写系统授权。

这一流程无需调用 `stage-migration` 或 `maintenance.py install`，不手工处理真实库的 WAL/SHM。后者是必须备份并替换数据的成对维护入口，没有免备份参数。仅保留旧 App 或安装包也不能恢复旧数据库；需要完整回滚能力时使用 [匹配快照与成对回滚](personal-maintenance.md#成对回滚)。

若替换或启动失败，保留数据目录，保持有关程序退出，核对安装位置、包完整性及版本兼容性后处理；不要通过清数据或删除日志来修复。若存在维护事务的 pending 标记，先按 [中断恢复](personal-maintenance.md#中断恢复)处理。

固定更新源为 `EricGao-cn/Toccata`。个人版在“关于 Toccata → 个人版更新”中手动检查 `personal-vX.Y.Z` 正式发布，并提供“打开下载页”。仅打开关于窗口不联网；不会下载、解压或安装更新，也不会上传任务、日记和键盘记录。不使用仓库的通用 latest 标记，按数值比较个人标签，排除上游标签、草稿、预览版和非法版本。列表分页最多 10 页；读取不完整时显示失败，不误报已是最新。

当前客户端匿名检查公开发布。私有仓库、尚无个人正式发布、限流或网络失败均显示可重试的状态；可用发布页面入口在浏览器登录查看，不向 App 写入 GitHub token。普通上游构建继续使用原上游更新流程。

## 本地候选构建与校验

以下入口供维护者做隔离开发和候选验收，不是普通用户更新 App 的前置步骤。

```bash
./scripts/personal/dev init
./scripts/personal/dev check
python3 -B scripts/personal/release.py plan
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

1. 更新 `scripts/personal/release.json` 的个人版本/build 和对应发布说明；待发布改动完成测试、审查和隔离验收，按授权提交并合入 `codex/personal`。
2. 选定最终个人版本，在该已接受的干净提交创建固定的 **annotated** `personal-v<version>` Tag；不移动或复用个人 Tag，不覆盖任何上游 Tag。
3. 记录提交 SHA、Tag 对象和固定上游基线；构建后记录实际 SDK、架构、安装包及清单的 SHA-256。
4. 选择 Actions 构建或下方本地备用入口。示例中的 `personal-v1.2.0` 仅为新版本示例；实际标签须匹配版本配置、已创建且尚未发布。既有 `personal-v1.1.1` 不移动、不复用：

```bash
python3 -B scripts/personal/release.py build-release --tag personal-v1.2.0
python3 -B scripts/personal/release.py verify /absolute/path/to/personal-v1.2.0
```

源码不干净、Tag 与 HEAD 不一致、不是 annotated Tag、提交未纳入个人主线、上游 Tag 与固定 SHA 不一致时，正式构建拒绝执行。不会自动提交、打 Tag、推送、发布、安装或启动。正式输出目录已存在时拒绝覆盖。

## 本地正式包与发布素材

这是当前可用的本地备用发布流程。常规云端发布见 [个人 GitHub Actions](#个人-github-actions构建-dmg-并停在草稿)；本地准备、上传和正式发布按当次授权分别执行：

1. 验收并合入 `codex/personal`，为干净提交创建新的固定 annotated 标签，再生成并验证正式包。候选包不能发布为稳定版。
2. 使用独立入口准备发布素材：

```bash
python3 -B scripts/personal/publish.py prepare \
  --package /absolute/path/to/personal-v1.2.0 \
  --notes docs/releases/personal-v1.2.0.md \
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

3. 按当次授权推送个人分支和固定标签。本地工具不执行 push，也不自动创建远端标签；**新个人标签 push 会同时触发 Actions**，同一标签只选择一个上传入口。
4. 常规发布由 Actions 创建草稿，不再手工重复上传。若当次方案选本地备用上传，先处理该标签的自动运行、确认没有运行中的自动上传或同名草稿/发布，再使用下方入口。默认只输出计划，实际上传要求授权和两个执行标记：

```bash
python3 -B scripts/personal/publish.py create-draft \
  --bundle /absolute/path/to/new-github-release-bundle
# 获准上传后追加：--execute --ack-upload
```

上传入口固定仓库、核对远端 annotated 标签对象与提交、拒绝覆盖已有正式发布或草稿，再用 `gh release create --draft --verify-tag` 上传。联网前会复制并重新验证私有上传快照，上传只读取该快照，避免等待期间源文件的编辑混入。ZIP 的顶层内容必须是 App 和两个清单文件，归档名称中的架构须与包清单一致。GitHub CLI 需预先认证；接口失败或标签不匹配时拒绝写入。不自动发布、替换或删除草稿；上传失败时保留原素材目录与远端现场，先在 GitHub 检查，不盲目重试覆盖。

5. 在 GitHub 草稿中核对版本、说明、DMG（或兼容 ZIP）和校验值，按发布授权确认正式发布，或明确授权 Agent 完成。App 随后才能检测到它。历史版本和标签保留。

从发布页下载个人安装包 DMG，或历史版本保留的安装包 ZIP；GitHub 自动提供的 Source code 压缩包不是可运行安装包。DMG 挂载后、ZIP 解压后含 `Toccata Personal.app` 和配套清单；其中的正式包目录也可作为 [成对安装](personal-maintenance.md#成对安装)的 `--package` 来源，但只有需要同时替换数据时才用该入口。GitHub 分发不替代已有数据备份。应用内一键安装保持禁用；ad-hoc 签名的 App 不会因为增加 DMG 获得 Developer ID 公证。

## 个人 GitHub Actions：构建 DMG 并停在草稿

已接入的独立入口为 [personal-release.yml](../.github/workflows/personal-release.yml)，复用 `release.py`、`publish.py` 和 `disk_image.py`。上游 `release.yml` 保持原样。个人分支 push 运行的是只检查测试的日常 CI；个人发布由新固定标签触发，本地编辑和本地测试不触发远端工作流。

发布触发方式：

- **推送新个人标签**：`personal-vX.Y.Z` 的 tag push 自动开始构建并创建草稿。普通分支推送、上游标签和 PR 不触发。未来授权推送个人标签时，也应明确知道这会开始云端构建和草稿上传。
- **手动重跑**：GitHub → Actions → Personal release draft → Run workflow，分支选 `codex/personal`，填写已推送的固定个人标签。只在尚无同名 Release 或草稿时可用；重跑不会覆盖之前的输出。

新版本必须先更新 `scripts/personal/release.json` 的个人版本/build，以及 `docs/releases/personal-vX.Y.Z.md`，验收、提交并合入个人主线后创建 annotated 标签。标签必须指向包含本工作流和 CI 入口的提交，且已纳入 `codex/personal`；版本、固定上游基线和工作区状态仍由正式打包入口核对。新发布使用全新个人标签，不用已发布版本试传，也不为重试移动或重用标签。

工作流只允许 `EricGao-cn/Toccata`，使用 Apple Silicon `macos-26` runner，显式选择 `/Applications/Xcode_26.2.app/Contents/Developer` 并检查 SDK 26.2、固定 Rust 版本和 arm64 架构。runner 若不再提供该 Xcode/SDK，构建直接失败，不退回默认 SDK。工具链、测试数据和输出都在临时 runner / `.local-dev` / `dist` 内，不需要本机配置、App 或数据库。

两个 job 的职责与权限：

1. **build（contents: read）**：先检出已接受的 `codex/personal`，用其中的校验脚本解析 annotated 标签并确认提交属于个人主线，之后才检出解析所得的精确 SHA；不先运行待校验标签里的脚本。再次核对标签对象未变、版本、上游基线、非空更新说明与远端同名发布，再初始化隔离环境，分别运行脚本回归、个人 core、上游完整 Swift 逻辑测试及个人模式专门测试。上游模式仅跳过交互式 `MarkdownWebEditorTests`；个人模式单独运行 `PersonalDistributionTests|PersonalReleaseUpdateTests`，其中包含禁止下载、准备和安装的保护验证。上游自动安装的正向测试只在上游模式运行，避免在个人版明确拒绝回调后无限等待。各测试阶段有独立超时和日志步骤。只读 token 的草稿可见性有限，最终防重检查仍在持写权限的 draft job 中执行。构建完整 ad-hoc 签名 App，生成并只读挂载校验 DMG；将 DMG、两个清单及校验文件、更新说明、发布素材元数据作为 Actions artifact 保留 14 天。另将提交、标签对象和 DMG SHA-256 作为独立 job 输出。
2. **draft（contents: write、actions: read）**：从精确构建提交检出代码，按 build 输出的固定 artifact ID，显式通过当前仓库和当前 workflow run 的 REST 接口下载素材。`actions: read` 只用于读取 artifact；ID 缺失或非法时失败，不退回下载全部 artifact。只重跑失败的草稿 job 时仍使用原成功 build 的 ID，不按新 attempt 猜测名称。再次核对固定标签、主线、App 签名、DMG 内容、清单、架构与独立 job 输出的 SHA-256，并将 artifact 更新说明与标签中的已提交原文比对。创建私有上传快照后，仅执行 `gh release create --draft --verify-tag`。上传后用认证的分页 Release 列表定位唯一草稿，再按数字 Release ID 回读状态、版本、说明和全部四个附件的 SHA-256，并再次检查远端标签对象和提交未变，通过后输出草稿链接；不使用仅针对已发布版本的按标签查询接口。`GH_TOKEN` 只传给校验/上传脚本；官方 checkout/download action 使用各自 job 的 token，checkout 不保留认证信息。不使用长期 PAT，不执行 push、移动标签、删除或覆盖资产。

上传前校验失败不会创建草稿；上传中断或上传后回读失败可能留下需要检查的草稿，错误会提示先查看发布页，工作流不会自动重试、删除或覆盖它。同标签并发最多执行一个运行，不取消正在构建/上传的运行；GitHub 可能用较新的等待运行替换旧的等待运行。后来的运行若发现已有草稿/发布就失败并保留现场。先核对 Actions 日志、artifact 和 GitHub 草稿，再决定后续操作；不要自动清除失败草稿或重用已发布标签。

正式发布在草稿核验后由维护者确认，可在 GitHub 点击 **Publish release**，也可明确授权 Agent 核验后执行；工作流本身没有 publish 模式。草稿不会被 App 的更新检查识别；发布也不会安装到本机。当前仍为 ad-hoc 签名、未公证，Actions 不会自动改变签名方式；本地手动打包和 ZIP 兼容入口继续可用。

工具链参考：[macOS runner 镜像](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md)、[GitHub 事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[工作流权限](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)。远端执行时核对仓库 Actions 策略允许固定 SHA 的官方 actions，推送和执行按当次授权；本地验证不修改仓库设置。

Fork 须包含配置中的固定上游标签；`main` 已包含上游提交不代表同名标签也已同步。若缺失，只能在核对本地与上游标签对象完全一致后单独同步，不覆盖既有标签。仅修正 Actions 编排时，可从个人主线手动运行修正后的工作流并指定尚无同名 Release/草稿的固定个人标签；App 仍构建该标签的原提交，工作流提交与 App 源码提交分别记录，不移动标签。

## 数据维护与历史记录

普通 App 更新按上文操作。需要备份、数据迁移、成对安装/回滚或事务中断恢复时，使用 [个人数据维护](personal-maintenance.md)，按实际工具能力和当次授权执行。已有备份、旧安装包、恢复现场和工作树不自动清理。

早期准备阶段的授权边界、首次空数据安装选择和分阶段测试结果归档于 [历史验收记录](personal-history.md)，不再混入当前安装步骤。
