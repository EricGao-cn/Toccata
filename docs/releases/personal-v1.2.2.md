# Toccata Personal 1.2.2

个人版本 **1.2.2 / build 6**，沿用上游 **v0.1.5 / 40d0641**。

## 应用内更新

- 在“关于 Toccata → 个人版更新”检查 `EricGao-cn/Toccata` 的正式个人版本。发现兼容新版后，可在应用内下载、校验并点击“安装并重启”。
- 安装前会保存任务和每日记录，等待采集服务停止。程序会校验 DMG 的 SHA-256、应用签名和个人版清单。替换或重启命令失败时会尝试恢复原 App。
- 更新只替换 App，继续使用原来的 `Toccata-Personal` 数据目录和数据库结构。

## 从旧版升级

**`1.2.1` 及之前版本请先手动更新一次。** 保存并正常退出后，备份现有数据，校验 `Toccata-Personal-1.2.2-arm64.dmg`，再用镜像中的 `Toccata Personal.app` 替换 `~/Applications` 中的个人版。推出镜像后从安装位置启动。后续兼容的正式版本可直接从应用内更新。详见[普通 App 更新](../personal-release.md#普通-app-更新)。

安装包适用于 Apple Silicon Mac、macOS 13 及以上，使用 macOS SDK 26.2 构建，采用 ad-hoc 签名，未做 Apple 公证。
