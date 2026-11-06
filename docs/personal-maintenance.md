# 个人数据维护：备份、迁移与回滚

本页用于需要处理数据的专项维护。日常只替换 App 时，使用 [普通 App 更新](personal-release.md#普通-app-更新)，无需先制作迁移副本。当前工具不会把普通更新自动转换为数据迁移。

## 命令与授权

| 命令 | 实际作用 | 默认行为 |
| --- | --- | --- |
| `backup` | 为指定 App 和数据目录生成一致性快照，保留源目录 | 输出计划 |
| `verify-backup` | 读取快照并校验清单、权限和数据库 | 执行只读校验 |
| `stage-migration` | 从快照制作数据副本并转换目标路径 | 输出计划 |
| `install` | 备份当前个人目标后，成对替换 App 与数据 | 输出计划 |
| `rollback` | 保留当前状态后，恢复快照中的 App 与数据 | 输出计划 |
| `recover` | 按日志处理一次中断的成对替换事务 | 输出计划 |

`backup`、`stage-migration`、`install`、`rollback`、`recover` 的实际执行都要求当次授权和 `--execute --ack-stopped`。这些标记表示已经确认正常退出，工具不会代替用户退出程序、强制结束服务、修改系统权限或启动 App。文档中的命令用于说明接口，不构成执行授权；示例里的 `/absolute/path/to/...` 须换成已核对的实际路径。

真实数据操作前先用合成数据演练；迁移和恢复在副本上验证。数据、备份、本机配置及工具链不提交到 Git，也不上传到 Release。

## 离线维护前的准备

正常退出有关的 Toccata 客户端及采集 helper，并暂停外部编辑器等写入者。只关闭窗口不算退出。工具会核对进程和数据锁，无法确认退出时拒绝继续；出现未保存提示时先完成保存，不强退。

副本验收期间可以继续日常使用源版本。正式切换前必须重新退出写入者并生成最新快照，不能把几天前的演练副本覆盖到已经新增记录的目标中。

## 备份

备份读取指定 App 和数据根目录，生成新的快照，不替换它们。个人版备份计划示例：

```bash
python3 -B scripts/personal/maintenance.py backup \
  --app "$HOME/Applications/Toccata Personal.app" \
  --data "$HOME/Library/Application Support/Toccata-Personal" \
  --output /absolute/path/to/new-personal-backup
```

常用存放位置为 `~/Toccata-Backups/`，每次使用全新子目录，工具拒绝覆盖已有备份。获准执行并确认退出后，才在同一命令末尾追加 `--execute --ack-stopped`。生成后再校验：

```bash
python3 -B scripts/personal/maintenance.py verify-backup \
  /absolute/path/to/existing-personal-backup
```

范围包括指定 `.app`、任务库、键盘原始库、每日 Markdown 与附件、配置和数据目录内其他普通文件。SQLite 使用备份 API 纳入已提交的 WAL 记录，输出独立数据库，并记录 `quick_check`、各表行数、文件 SHA-256 和权限清单。单独复制仍在写入的 `tasks.sqlite` 或 `toccata.db` 不能代替一致性备份。系统权限、登录项和数据目录外的偏好需要单独检查，工具不自动复制旧偏好 plist。

当前支持的快照格式为 **schema 2**；缺少完整性信息的 schema 1 预演快照不能用于正式恢复。备份前后会核对源树，发现内容、文件集合或权限变化时拒绝发布快照。源路径相互包含、符号链接、非法文件、应用库的孤立 WAL 或恢复 journal，以及未设计映射的自定义数据库/socket 路径也会被拒绝。

数据根目录中的 socket/lock 和 SQLite WAL/SHM 按运行时文件处理；日记附件即使同名仍按普通文件保留。macOS SQLite 在 WAL 转为 DELETE 并关闭连接后可能留下 `-shm`。工具只在**新副本**中确认数据库文件头为回滚日志格式、且没有 WAL 或恢复 journal 时清理残留 SHM；存在 journal（即使为空）或转换未完成就拒绝继续，不删除可能承载数据的文件。旧 schema 2 快照可以包含完整独立库加残留 SHM；清理只发生于新的迁移副本，旧备份保持不变。仍为 WAL 模式或带恢复日志的旧快照会被拒绝，不尝试忽略或强行恢复日志。

备份或校验失败时保留源数据和现场，不通过删除真实数据目录内的 WAL、SHM、journal 或锁文件来强行继续。

## 数据迁移副本

适用于从上游原版接管数据、转换数据目录或合并明确选定的日记。若首次使用选择空个人数据，则无需迁移。已有个人版的普通 App 更新也不需要这一步。

从上游迁移时，先按上一节备份 `/Applications/Toccata.app` 和 `~/Library/Application Support/Toccata/`。上游备份作为迁移来源保留；它不是个人目标的回滚快照。然后查看副本计划：

```bash
python3 -B scripts/personal/maintenance.py stage-migration \
  --backup /absolute/path/to/verified-source-backup \
  --output /absolute/path/to/new-staged-data \
  --target-data "$HOME/Library/Application Support/Toccata-Personal"
```

执行标记仍为 `--execute --ack-stopped`。该命令读取已校验备份，在全新目录中复制数据，将 `config.json` 的数据库和 socket 路径改为个人目标，并检查数据库清单和记录数量；原数据、原备份和正式目标目录不被替换。

`stage-migration` 是副本准备与路径转换，不负责预先运行目标 App 的数据库 schema 升级。若新版有此类升级，还需按发布说明专门验证副本与兼容性。

需要接入开发试用时留下的真实日记，可在明确选定范围后添加 `--extra-notes /absolute/path/to/chosen/daily-notes`。不导入整个开发任务库；同名且内容不同的日记拒绝自动合并，先在副本中人工处理。中途出错不会发布半成品 staging 目录。

副本验收包括任务数量、名称、详情、日期、子任务、完成状态、置顶、排序、键盘历史、应用统计，以及日记日期、内容和附件。测试环境与跳过项应明确记录，副本验证之后仍需人工验收。候选客户端关闭采集，不能把历史数据读取成功当作真实采集验收。

## 成对安装

仅当方案明确需要同时替换 App 与准备好的数据时使用。**`maintenance.py install` 不是普通 App 更新命令，也没有免备份参数。**

```bash
python3 -B scripts/personal/maintenance.py install \
  --package /absolute/path/to/verified-stable-package \
  --staged-data /absolute/path/to/validated-staged-data \
  --backup /absolute/path/to/new-personal-before-install
```

`--package` 指含 `.app`、`release.json` 和清单校验值的已验证正式包目录，不是 DMG 文件或 GitHub Source code ZIP。进入实际替换前，工具始终创建当前个人目标的最新快照，再分别准备和校验 App、数据副本，随后成对替换。候选包、错误身份、校验失败或仍带 WAL/SHM 的非独立 staging 数据均被拒绝；不能用删除日志的方式绕过检查。

目标固定为 `~/Applications/Toccata Personal.app` 和 `~/Library/Application Support/Toccata-Personal`，不会替换原版 App 或上游数据。首次安装也记录个人目标原本是否存在，供对应回滚使用。普通异常会尝试恢复原来的一对；原路径和失败文件保留为唯一命名的历史副本，不自动清理。工具不会自动启动安装后的 App。

## 中断恢复

这是成对安装/回滚事务的恢复入口，与主动降级不同。App 和数据可能位于不同文件系统，工具在第一次 live 重命名前写入并刷盘 `<backup>.transaction.json`，以及个人数据目录旁的 `.Toccata-Personal.maintenance.pending.json`。进程中断后日志与快照保留。

待恢复标记存在时，个人客户端、collector 和后续安装/回滚拒绝继续。应先处理该事务，不把中断状态当作正常回滚点。保持有关程序退出，先查看计划：

```bash
python3 -B scripts/personal/maintenance.py recover \
  --backup /absolute/path/to/transaction-backup
```

获准后追加 `--execute --ack-stopped`。工具校验日志、快照、目标与原始版本，保留中断后出现的文件，恢复原来的一对并清理标记；已经完成的事务只完成标记清理，不回退到旧版本。恢复可重复执行，未开始变更的旧日志不能影响后来的安装。回滚若被中断，使用其 `--recovery-backup` 对应的日志恢复到回滚前状态，再决定是否重试。

不要手工删除 pending 标记。日志或原始恢复树损坏时，保留现场并核对备份，不猜测恢复。日志与复制结果使用 fsync，但不承诺跨卷数据库事务或硬件/断电损坏的恢复保证。普通手动 App 替换没有该工具的事务日志，不应编造一个 backup 路径调用 `recover`。

## 成对回滚

只有与个人目标路径匹配的完整快照才能恢复这一对。上游备份不直接用于个人回滚；**只换回旧 App 不会恢复旧数据库，也不证明旧 App 能读取新版库。**

正常退出个人版及 helper，检查登录启动等设置，再查看计划：

```bash
python3 -B scripts/personal/maintenance.py rollback \
  --backup /absolute/path/to/matching-personal-before-install \
  --recovery-backup /absolute/path/to/new-personal-before-rollback
```

获准执行后追加 `--execute --ack-stopped`。工具先保存当前 App 和数据（含升级后新增记录），再恢复匹配快照；身份、路径或校验失败时拒绝替换。回滚后的正式数据是旧快照，后来的新增任务和日记保存在 recovery backup，需要另行核对取回，不能直接覆盖合并两份 SQLite 文件。

首次安装的快照若记录个人目标不存在，回滚恢复到该状态，当前个人版与数据仍保存在恢复副本中；原上游 App 和数据继续保留。输入监控、通知、登录项等系统设置由用户检查，脚本不自动恢复系统授权或覆盖旧偏好 plist。

## 维护验收与清理

- 计划与实际执行分开；活跃进程、数据锁或待恢复事务阻止不安全操作。
- SQLite 快照保留已提交记录，Markdown 与附件保留原文，校验涵盖内容与权限。
- 成对安装和回滚核对 App/数据匹配；中断恢复保留现场与新增工作。
- 个人版手动检查更新可用，应用内下载安装保持禁用；采集不包含截图、音频或输入正文。

备份、`.previous-*`、`.failed-*`、恢复副本、候选包和工作树的清理由用户另行决定，不自动删除或清空废纸篓。维护工具的历史准备阶段见 [历史记录](personal-history.md)。
