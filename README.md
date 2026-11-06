<p align="center"><img src="shared/branding/toccata-app-icon.png" alt="Toccata Personal" width="96"></p>

# Toccata Personal

**简体中文** · [English](README_EN.md)

记下每天的探索，回看思路与进展。

Toccata Personal 是一个 macOS 菜单栏应用，将每日 Markdown 记录、任务管理和本地键盘活动放在一起。适合随手记下实验、想法和验证结果，在一天或一周结束时回顾自己的工作。

[下载个人版 DMG](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg) · [SHA-256](https://github.com/EricGao-cn/Toccata/releases/download/personal-v1.1.1/Toccata-Personal-1.1.1-arm64.dmg.sha256) · [全部版本](https://github.com/EricGao-cn/Toccata/releases)

## 每日记录与回顾

- **每天一篇 Markdown**：整页续写、自动保存，记录做过什么、接下来想尝试什么，以及验证或排除了哪些思路。
- **随手记，按天找**：菜单栏小窗快速续写；工作台按日期浏览、补写，通过月历跳转到某一天。
- **整理周报素材**：按日期范围查看每日记录与任务，支持复制当前内容或复制全部。
- **记录与任务独立**：探索过程可以留在笔记中，有明确完成目标时再建立任务。

## 任务管理

- 在菜单栏小窗快速添加和编辑任务，用收集箱暂存想法。
- 支持子任务、Markdown 详情、置顶和拖拽排序。
- 按日期安排任务，通过日历查看计划，在回顾中查看进展。

![任务管理与菜单栏小窗](images/todo-management.png)

## 键盘活跃

- **按键热力图**：查看常用按键与实时按下反馈。
- **活跃时间线**：按天查看输入时段，回顾常用应用和 Fn 按住时长。
- **活动速览**：在菜单栏查看今日或昨日的键盘与应用活动。

活跃时间基于键盘活动估算，不能覆盖阅读、思考等全部投入；Fn 时长也可能包含快捷键操作。下方及任务截图沿用原项目的演示数据。

![键盘热力图与活跃时间线](images/keyboard-activity.png)

## 开始使用

当前个人版为 **1.1.1**，适用于 **Apple Silicon Mac · macOS 13+**。

下载并校验 DMG，将 `Toccata Personal.app` 放到 `~/Applications`，推出镜像后启动。任务和每日记录可以独立使用；首次启用键盘记录或系统要求时，需确认输入监控权限。

App 常驻菜单栏，关闭工作台后仍可在后台运行。外观、语言、登录自启、Dock 显示和喝水提醒可在通用配置中调整。

已有个人版可通过“关于 Toccata → 个人版更新”检查新版并打开下载页，更新时手动替换 App，继续使用原数据目录。当前安装包未做 Developer ID 公证；具体步骤见 [安装与更新说明](docs/personal-release.md#普通-app-更新)。

## 数据与隐私

任务、每日记录和键盘活动保存在本机。键盘记录不采集输入正文、不截图、不录音；手动检查更新会访问个人 GitHub 发布源。

每日记录是 `~/Library/Application Support/Toccata-Personal/daily-notes/` 中的 Markdown 文件，也可从 App 打开记录文件夹。个人版与原版分别保存数据，可以保留原版 App 和记录。

## 来源与许可证

本项目是 [EricGao-cn/Toccata](https://github.com/EricGao-cn/Toccata) 维护的个人 Fork，基于 [KMnO4-zx/Toccata](https://github.com/KMnO4-zx/Toccata)，加入独立每日记录与科研过程回顾。

采用 [Apache-2.0](LICENSE) 许可证。原项目介绍、作者叙述和致谢保存在 [原 README 存档](docs/upstream-readme.md)。
