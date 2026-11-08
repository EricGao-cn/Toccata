#!/bin/bash
# Package a built Toccata app without installing or launching it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/Toccata.app"
SKIP_BUILD=false

usage() {
    cat <<'USAGE'
Usage: ./scripts/package-dmg.sh [--skip-build]

Build Toccata, then create dist/Toccata-<version>-<arch>.dmg and its SHA-256 file.
  --skip-build  Package the existing dist/Toccata.app after validation.
  -h, --help    Show this help.

The DMG opens as a styled install window (drag Toccata onto Applications,
with first-launch Gatekeeper guidance). Installation notes are included
as a hidden file. Layout assets live in scripts/dmg-assets. Packaging
briefly opens a Finder window to bind the background to the volume.
This script does not install the app, launch it, or change login items or permissions.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-build) SKIP_BUILD=true ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$SKIP_BUILD" = false ]; then
    "$ROOT/scripts/build-app.sh"
fi

PLIST="$APP/Contents/Info.plist"
STUDIO="$APP/Contents/MacOS/Toccata"
HELPER="$APP/Contents/MacOS/toccata-core"
if [ ! -f "$PLIST" ] || [ ! -x "$STUDIO" ] || [ ! -x "$HELPER" ]; then
    printf 'Missing built app or helper: %s\nRun ./scripts/build-app.sh first.\n' "$APP" >&2
    exit 1
fi

VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")"
source "$ROOT/scripts/macos-toolchain.sh"
verify_toccata_macos_sdk "$STUDIO" "$HELPER"

BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$PLIST")"
if [[ ! "$VERSION" =~ ^[0-9]+([.][0-9]+){0,2}$ ]]; then
    printf 'Invalid app version for DMG filename: %s\n' "$VERSION" >&2
    exit 1
fi
if [ "$BUNDLE_ID" != 'com.toccata.studio' ]; then
    printf 'Unexpected app bundle identifier: %s\n' "$BUNDLE_ID" >&2
    exit 1
fi

/usr/bin/codesign --verify --deep --strict "$APP"
/usr/bin/codesign --verify --strict "$HELPER"

architectures() {
    /usr/bin/lipo -archs "$1" | /usr/bin/tr ' ' '\n' | LC_ALL=C /usr/bin/sort | /usr/bin/xargs
}

STUDIO_ARCHS="$(architectures "$STUDIO")"
HELPER_ARCHS="$(architectures "$HELPER")"
if [ "$STUDIO_ARCHS" != "$HELPER_ARCHS" ]; then
    printf 'App/helper architecture mismatch: app=%s helper=%s\n' "$STUDIO_ARCHS" "$HELPER_ARCHS" >&2
    exit 1
fi
case "$STUDIO_ARCHS" in
    arm64) ARCH=arm64 ;;
    x86_64) ARCH=x86_64 ;;
    'arm64 x86_64') ARCH=universal ;;
    *) printf 'Unsupported app architecture: %s\n' "$STUDIO_ARCHS" >&2; exit 1 ;;
esac

mkdir -p "$DIST"
STAGING="$(mktemp -d "$DIST/.Toccata-dmg.XXXXXX")"
trap 'rm -rf "$STAGING"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

PAYLOAD="$STAGING/payload"
mkdir -p "$PAYLOAD"
/usr/bin/ditto "$APP" "$PAYLOAD/Toccata.app"
/bin/ln -s /Applications "$PAYLOAD/Applications"
cat > "$PAYLOAD/安装说明.txt" <<'INSTALL'
Toccata 安装说明

1. 将 Toccata.app 拖到 Applications 文件夹，然后推出此磁盘映像。
2. 从“应用程序”打开 Toccata。任务与键盘活动记录保存在本机。
3. Toccata 常驻菜单栏，默认显示 Dock 图标，可在“设置 → 通用配置”中隐藏。关闭工作台后继续在后台运行，选择“退出 Toccata”结束应用。
4. “登录时启动”默认关闭，可在“设置 → 通用配置”中按需开启。登录自动启动时不打开工作台。建议先完成拖拽安装，再开启此选项。
5. 如需记录键盘活动，请自行在“系统设置 → 隐私与安全性 → 输入监控”中开启 Toccata。任务功能可独立使用。
6. 右键菜单栏图标，选择“喝水提醒…”可开启按键计数提醒。首次开启需允许通知，可使用“发送测试通知”检查显示效果。
7. v0.1.3 build 21 及后续版本支持在“关于 Toccata → 检查更新”中下载新版，再点击“安装并重启”。v0.1.2、原 v0.1.3 build 20 及更早版本需先退出应用，再手动替换一次。安装后可在“关于 Toccata”中复制版本信息，核对当前版本和 Build；请从可写的应用程序目录运行，勿直接从只读 DMG 中更新。

此打包脚本默认生成 ad-hoc 签名的本机测试包，未执行 Apple 公证。
正式分发需另行完成 Developer ID 签名、Hardened Runtime、Apple 公证及公证票据装订。
打开磁盘映像和拖拽安装不会自动修改登录项或输入监控权限。
INSTALL

# Styled install window: background art plus a Finder layout template for
# window bounds and icon positions. The background alias is volume-specific
# and is bound by Finder on the staging volume below. Regenerate the artwork
# with scripts/dmg-assets/render-background.sh after editing the design.
mkdir -p "$PAYLOAD/.background"
/bin/cp "$ROOT/scripts/dmg-assets/background.png" "$PAYLOAD/.background/background.png"
/bin/cp "$ROOT/scripts/dmg-assets/DS_Store" "$PAYLOAD/.DS_Store"
/usr/bin/chflags hidden "$PAYLOAD/安装说明.txt"

# Validate the copied payload before creating the final read-only image.
/usr/bin/codesign --verify --deep --strict "$PAYLOAD/Toccata.app"
DMG_NAME="Toccata-$VERSION-$ARCH.dmg"
STAGED_DMG="$STAGING/$DMG_NAME"

# The background alias in .DS_Store is volume-specific, so it must be created
# on the final volume: stage read-write, let Finder bind the background, then
# convert (block-level copy keeps the volume UUID, so the alias survives).
# The committed DS_Store template supplies window bounds, icon size/positions.
if [ -e /Volumes/Toccata ]; then
    printf 'Eject the mounted "Toccata" volume before packaging.\n' >&2
    exit 1
fi
PAYLOAD_MB="$(/usr/bin/du -sm "$PAYLOAD" | /usr/bin/cut -f1)"
RW_DMG="$STAGING/readwrite.dmg"
/usr/bin/hdiutil create -size "$((PAYLOAD_MB + 32))m" -fs HFS+ -volname Toccata "$RW_DMG" -quiet
/usr/bin/hdiutil attach "$RW_DMG" -nobrowse -quiet
cleanup() {
    if /usr/bin/hdiutil info | /usr/bin/grep -q "$RW_DMG"; then
        /usr/bin/hdiutil detach /Volumes/Toccata -quiet 2>/dev/null || true
    fi
    rm -rf "$STAGING"
}
trap cleanup EXIT
/usr/bin/ditto "$PAYLOAD" /Volumes/Toccata
/usr/bin/osascript <<'APPLESCRIPT'
tell application "Finder"
    tell disk "Toccata"
        open
        set background picture of icon view options of container window to ¬
            (POSIX file "/Volumes/Toccata/.background/background.png")
        close
    end tell
end tell
delay 1
APPLESCRIPT
/usr/bin/hdiutil detach /Volumes/Toccata -quiet
/usr/bin/hdiutil convert "$RW_DMG" -format UDZO -imagekey zlib-level=9 -o "$STAGED_DMG" -quiet
/usr/bin/hdiutil verify "$STAGED_DMG"
(
    cd "$STAGING"
    /usr/bin/shasum -a 256 "$DMG_NAME"
) > "$STAGING/$DMG_NAME.sha256"

# Keep any previous package until the replacement has passed verification.
/bin/mv -f "$STAGED_DMG" "$DIST/$DMG_NAME"
/bin/mv -f "$STAGING/$DMG_NAME.sha256" "$DIST/$DMG_NAME.sha256"
printf 'Packaged: %s\nArchitecture: %s\nSHA-256: ' "$DIST/$DMG_NAME" "$STUDIO_ARCHS"
/bin/cat "$DIST/$DMG_NAME.sha256"
