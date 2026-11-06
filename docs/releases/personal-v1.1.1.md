# Toccata Personal 1.1.1

本版本基于上游 v0.1.4，保留每日 Markdown 记录、任务、回顾和手动检查更新功能。本次主要更新个人版的构建与发布流程。

- 个人安装包由 GitHub Actions 在 Apple Silicon runner 上构建，固定使用 SDK 26.2，提供 DMG、SHA-256 校验文件和发布清单。
- 云端构建检查固定 annotated 标签与个人主线提交，运行脚本、个人采集 core 和非交互 Swift 测试，验证 App 签名、DMG 内容、只读挂载及正常卸载。
- 构建成功后只创建 Release 草稿；核对构建日志、安装包、校验值和发布说明后，再人工确认正式发布。
- 草稿上传拒绝覆盖已有发布或草稿；使用固定 artifact ID，重新核对源码提交、标签对象和下载文件的 SHA-256。上传失败保留现场，不自动重试、删除或正式发布。

App 仍从 `EricGao-cn/Toccata` 手动检查个人正式版本并打开下载页，不会自动下载安装更新。现有个人版继续使用独立的 `Toccata-Personal` 数据目录，本版本不要求迁移上游数据。

安装包适用于 Apple Silicon Mac、macOS 13 及以上，为 ad-hoc 签名、未做 Developer ID 公证。首次使用可从空个人数据开始；更新已有个人版前正常退出并备份数据。原版 App、原数据，以及 personal-v1.1.0 的标签和 ZIP/DMG 下载均保留。降级 App 不会自动回滚数据库。
