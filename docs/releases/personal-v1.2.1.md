# Toccata Personal 1.2.1

个人版本 **1.2.1 / build 5**，基于上游 **v0.1.5 / 40d0641**。

## 每日记录

- 点击「插入时间」会在光标处插入当前时间的 Markdown 标题，并触发自动保存。
- 切页时会将输入法仍在组合的文字保存到草稿。外部编辑同一份记录时，会提示冲突并保留两个版本。
- 当前编辑器独立管理撤销历史。撤销和重做都会同步到草稿，切页后窗口不会再保留已卸载编辑器的撤销记录。

## 安装与更新

提供适用于 **Apple Silicon Mac、macOS 13 及以上**的 `Toccata-Personal-1.2.1-arm64.dmg`，以及 SHA-256 校验文件和发布清单。安装包固定使用 **macOS SDK 26.2** 构建，为 ad-hoc 签名，未做 Developer ID 公证。

更新前先完成保存，正常退出个人版和采集服务，再备份数据并校验安装包。将镜像内的 `Toccata Personal.app` 替换到 `~/Applications`，推出镜像后从安装位置打开。沿用 `Toccata-Personal` 数据目录和现有数据库结构，无需迁移。详见[普通 App 更新](../personal-release.md#普通-app-更新)。
