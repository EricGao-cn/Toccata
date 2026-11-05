# 个人稳定版：打包、安装、备份、迁移与回滚

## 当前阶段和身份

这是本地手动发布流程。首次个人版本暂定 `1.0.0 / build 1`，基于上游 `v0.1.4`；发布前仍可调整。配置位于 `scripts/personal/release.json`，不会改写上游 `shared/app-version.json` 或移动上游标签。

| 类型 | Bundle ID | 数据目录 | 采集与更新 |
| --- | --- | --- | --- |
| 上游日用版 | `com.toccata.studio` | `~/Library/Application Support/Toccata/` | 沿用上游 |
| 隔离开发版 | `cn.ericgao.toccata.dev.<worktree-id>` | 各工作树的独立测试目录 | task-only，沿用开发入口 |
| 个人候选包 | 开发身份再加 `.candidate` | 当前工作树测试目录下的 `personal-candidate/` | 不启动采集、不请求输入监控、禁用在线安装更新 |
| 个人稳定版 | `cn.ericgao.toccata.personal` | `~/Library/Application Support/Toccata-Personal/` | 独立个人采集服务、手动更新 |

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
python3 -B scripts/personal/release.py build-release --tag personal-v1.0.0
python3 -B scripts/personal/release.py verify /absolute/path/to/personal-v1.0.0
```

源码不干净、Tag 与 HEAD 不一致、不是 annotated Tag、提交未纳入个人主线、上游 Tag 与固定 SHA 不一致时，正式构建拒绝执行。不会自动提交、打 Tag、推送、发布、安装或启动。正式输出目录已存在时拒绝覆盖。

## 首次切换：先快照，再副本验证

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
  --package /absolute/path/to/extracted/personal-v1.0.0 \
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
