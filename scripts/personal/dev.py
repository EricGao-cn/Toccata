#!/usr/bin/env python3
"""Rebuildable task-only development setup; never installs an application."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEV_ID_PREFIX = "cn.ericgao.toccata.dev"


class SetupError(Exception):
    pass


def read_json(path):
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise SetupError(f"Expected a JSON object: {path}")
        return value
    except (OSError, ValueError) as error:
        raise SetupError(f"Cannot read {path}: {error}") from error


def local_config_path(root):
    path = Path(os.environ.get("TOCCATA_DEV_CONFIG", root / ".local-dev/config.json"))
    path = (path if path.is_absolute() else root / path).resolve()
    if root / ".local-dev" not in path.parents:
        raise SetupError("TOCCATA_DEV_CONFIG must be inside this checkout's .local-dev directory")
    return path


def common_checkout_root(root):
    try:
        value = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
            text=True, stderr=subprocess.DEVNULL).strip()
        common = Path(value)
        return (common if common.is_absolute() else root / common).resolve().parent
    except subprocess.CalledProcessError:
        return root


def worktree_id(root):
    return "w" + hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]


def validate(root, config):
    keys = ["worktree_id", "sdk_version", "rust_version", "bundle_id", "app_name",
            "configuration", "data_dir", "cargo_home", "rustup_home"]
    if config.get("schema_version") != 1 or any(not isinstance(config.get(k), str) for k in keys):
        raise SetupError("Invalid development configuration schema")
    if not re.fullmatch(r"[A-Za-z0-9-]+", config["worktree_id"]):
        raise SetupError("Invalid worktree identity")
    if config["worktree_id"] != worktree_id(root):
        raise SetupError("Configuration belongs to another checkout; initialize this directory separately")
    if not (config["bundle_id"] == DEV_ID_PREFIX or config["bundle_id"].startswith(DEV_ID_PREFIX + ".")):
        raise SetupError("Bundle ID must stay in the dedicated development namespace")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*", config["bundle_id"]):
        raise SetupError("Invalid bundle identifier")
    if config["bundle_id"] == DEV_ID_PREFIX and common_checkout_root(root) != root:
        raise SetupError("The legacy development identity is reserved for the primary checkout")
    if (not config["app_name"].startswith("Toccata Dev") or
            any(c in config["app_name"] for c in "/\\\n\r\0")):
        raise SetupError("Invalid development app name")
    if config["configuration"] not in ("debug", "release"):
        raise SetupError("Configuration must be debug or release")
    if not re.fullmatch(r"\d+\.\d+", config["sdk_version"]):
        raise SetupError("Invalid SDK version")
    if not re.fullmatch(r"\d+\.\d+\.\d+", config["rust_version"]):
        raise SetupError("Use a fixed numeric Rust version")
    for key in ("data_dir", "cargo_home", "rustup_home"):
        if not Path(config[key]).is_absolute():
            raise SetupError(f"{key} must be absolute")
    support = Path.home() / "Library/Application Support"
    protected_paths = (support / "Toccata", support / "Toccata-Personal",
                       Path("/Applications/Toccata.app"), Path("/Applications/Toccata Personal.app"))
    for key in ("data_dir", "cargo_home", "rustup_home"):
        target = Path(config[key]).resolve()
        for protected in protected_paths:
            protected = protected.resolve()
            if target == protected or protected in target.parents or target in protected.parents:
                raise SetupError(f"{key} overlaps a protected daily-use directory")
    local = root / ".local-dev"
    for name in ("swift", "target", "cache", "out", "downloads"):
        if local not in (local / name).resolve().parents:
            raise SetupError("A development output directory escapes .local-dev")
    data = Path(config["data_dir"]).resolve()
    if len(str(data / "toccata.sock").encode()) >= 104:
        raise SetupError("Data path exceeds the macOS Unix socket limit; choose a shorter state root")
    for name in ("tasks.sqlite", "tasks.sqlite-wal", "tasks.sqlite-shm", "toccata.db", "toccata.sock"):
        if (data / name).is_symlink():
            raise SetupError(f"Refusing symlinked runtime file: {data / name}")
    settings = data / "config.json"
    if settings.is_symlink():
        raise SetupError("Refusing a symlinked data configuration")
    if settings.exists():
        settings = read_json(settings)
        for key, name in (("db_path", "toccata.db"), ("socket_path", "toccata.sock")):
            value = settings.get(key)
            if value is not None and (not isinstance(value, str) or Path(value).resolve() != data / name):
                raise SetupError(f"Existing {key} escapes the isolated data directory")
    return config


def initialize(root, state_root=None, tools_root=None):
    path = local_config_path(root)
    if path.exists():
        return validate(root, read_json(path)), False
    defaults = read_json(root / "scripts/personal/dev-defaults.json")
    identity = worktree_id(root)
    state = Path(state_root).expanduser().resolve() if state_root else (
        Path.home() / "Library/Application Support/Toccata-Dev")
    config = {
        "schema_version": 1, "worktree_id": identity,
        "sdk_version": defaults["sdk_version"], "rust_version": defaults["rust_version"],
        "bundle_id": defaults["bundle_id_prefix"] + "." + identity,
        "app_name": defaults["app_name_prefix"] + " " + identity,
        "configuration": defaults["configuration"], "data_dir": str(state / identity / "data"),
        "cargo_home": str(state / "toolchains/cargo"), "rustup_home": str(state / "toolchains/rustup"),
    }
    common_root = common_checkout_root(root)
    common_config = common_root / ".local-dev/config.json"
    if common_config.exists():
        common = read_json(common_config)
        for key in ("cargo_home", "rustup_home"):
            config[key] = common[key]
    if (root / ".local-dev/cargo/bin/rustup").exists():
        config.update(cargo_home=str(root / ".local-dev/cargo"), rustup_home=str(root / ".local-dev/rustup"))
    if tools_root:
        tools = Path(tools_root).expanduser().resolve()
        config.update(cargo_home=str(tools / "cargo"), rustup_home=str(tools / "rustup"))
    # Adopt the existing development setup without moving or rewriting its data.
    legacy_app = root / ".local-dev/out/Toccata Dev.app/Contents/Info.plist"
    legacy_data = root / ".local-dev/data"
    if common_root == root and legacy_app.exists() and legacy_data.is_dir():
        info = plistlib.loads(legacy_app.read_bytes())
        if info.get("CFBundleIdentifier") == DEV_ID_PREFIX:
            config.update(bundle_id=DEV_ID_PREFIX, app_name="Toccata Dev", data_dir=str(legacy_data))
    validate(root, config)
    data = Path(config["data_dir"])
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    settings = data / "config.json"
    if not settings.exists():
        with settings.open("x") as output:
            json.dump({"db_path": str(data / "toccata.db"), "socket_path": str(data / "toccata.sock")}, output, indent=2)
            output.write("\n")
        settings.chmod(0o600)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        json.dump(config, output, indent=2)
        output.write("\n")
    path.chmod(0o600)
    return config, True


def environment(root, config):
    env = os.environ.copy()
    local = root / ".local-dev"
    env.update({
        "TOCCATA_DEV_ROOT": str(root), "TOCCATA_DEV_HOME": str(local),
        "TOCCATA_DATA_DIR": config["data_dir"], "TOCCATA_DEV_BUNDLE_ID": config["bundle_id"],
        "TOCCATA_DEV_APP": str(local / "out" / (config["app_name"] + ".app")),
        "TOCCATA_DEV_SDK_VERSION": config["sdk_version"],
        "CARGO_HOME": config["cargo_home"], "RUSTUP_HOME": config["rustup_home"],
        "CARGO_TARGET_DIR": str(local / "target"),
        "CLANG_MODULE_CACHE_PATH": str(local / "cache/clang"),
        "SWIFTPM_MODULECACHE_OVERRIDE": str(local / "cache/swift"),
        "RUSTUP_TOOLCHAIN": config["rust_version"], "RUSTUP_AUTO_INSTALL": "0",
    })
    env["PATH"] = str(Path(config["cargo_home"]) / "bin") + os.pathsep + env.get("PATH", "")
    rustup = Path(config["cargo_home"]) / "bin/rustup"
    if rustup.exists():
        # A matching stable alias reuses this machine's existing installation.
        stable = subprocess.run([str(rustup), "run", "stable", "rustc", "--version"],
                                env=env, text=True, capture_output=True)
        if stable.returncode == 0 and stable.stdout.startswith("rustc " + config["rust_version"] + " "):
            env["RUSTUP_TOOLCHAIN"] = "stable"
    return env


def run(args, root, env, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=root, env=env, check=True, **kwargs)


def require_sdk(config, env):
    selected = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-version"], env=env, text=True).strip()
    if selected != config["sdk_version"]:
        raise SetupError(f"Local development requires SDK {config['sdk_version']}; selected: {selected}")
    env["SDKROOT"] = subprocess.check_output(
        ["xcrun", "--sdk", "macosx" + selected, "--show-sdk-path"], env=env, text=True).strip()


def require_rust(config, env):
    tools = Path(env["CARGO_HOME"]) / "bin"
    if any(not (tools / name).is_file() for name in ("rustup", "rustc", "cargo")):
        raise SetupError("Install the dedicated Rust toolchain first: ./scripts/personal/dev setup-rust")
    result = subprocess.run([str(tools / "rustc"), "--version"], env=env, text=True, capture_output=True)
    if result.returncode or not result.stdout.startswith("rustc " + config["rust_version"] + " "):
        raise SetupError("Configured Rust version is unavailable; run ./scripts/personal/dev setup-rust")
    return tools / "cargo"


def swift_options(root, env):
    local = root / ".local-dev"
    return ["--package-path", root / "apps/toccata-studio", "--sdk", env["SDKROOT"],
            "--scratch-path", local / "swift", "--disable-sandbox",
            "--config-path", local / "cache/spm-config", "--security-path", local / "cache/spm-security",
            "--cache-path", local / "cache/spm"]


def assemble_bundle(root, config, env, binary_dir):
    app = Path(env["TOCCATA_DEV_APP"])
    if root / ".local-dev/out" not in app.resolve().parents:
        raise SetupError("Development app output escapes .local-dev/out")
    macos, resources = app / "Contents/MacOS", app / "Contents/Resources"
    if (macos / "toccata-core").exists():
        raise SetupError("Refusing a development bundle containing a collection helper")
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    # Replace rather than truncate an executable that might still be running.
    temporary = macos / "ToccataDevBinary.new"
    shutil.copy2(binary_dir / "toccata-studio", temporary)
    temporary.replace(macos / "ToccataDevBinary")
    shutil.copytree(binary_dir / "toccata-studio_toccata-studio.bundle",
                    resources / "toccata-studio_toccata-studio.bundle", dirs_exist_ok=True)
    launcher = macos / "ToccataDev"
    launcher.write_text('#!/bin/bash\nset -euo pipefail\nexport TOCCATA_DATA_DIR=' +
                        shlex.quote(config["data_dir"]) +
                        '\nexec "$(dirname "$0")/ToccataDevBinary" "$@"\n')
    launcher.chmod(0o755)
    version = read_json(root / "shared/app-version.json")
    info = {"CFBundleIdentifier": config["bundle_id"], "CFBundleExecutable": "ToccataDev",
            "CFBundleName": config["app_name"], "CFBundleDisplayName": config["app_name"],
            "CFBundlePackageType": "APPL", "CFBundleShortVersionString": version["version"],
            "CFBundleVersion": version["build"], "DTSDKName": "macosx" + config["sdk_version"],
            "ToccataDevelopmentDataDirectory": config["data_dir"],
            "LSMinimumSystemVersion": "13.0", "LSUIElement": True, "NSHighResolutionCapable": True,
            "NSSupportsAutomaticTermination": False, "NSSupportsSuddenTermination": False}
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "env", "check", "setup-rust", "fetch", "build", "run",
                                            "core", "test-core", "test-swift", "test-scripts", "test"])
    parser.add_argument("--state-root", help="Fresh setup: external development state directory")
    parser.add_argument("--tools-root", help="Fresh setup: shared directory containing cargo/ and rustup/")
    args, extra = parser.parse_known_args()
    if extra and args.command not in ("fetch", "run", "test-core", "test-swift", "test"):
        parser.error(f"Unsupported arguments for {args.command}: {' '.join(extra)}")
    if args.command == "init":
        if extra:
            parser.error("Unknown init arguments")
        config, created = initialize(ROOT, args.state_root, args.tools_root)
        print(("Created " if created else "Preserved ") + str(local_config_path(ROOT)))
        print("Development data: " + config["data_dir"])
        return
    if args.state_root or args.tools_root:
        parser.error("--state-root and --tools-root are init-only options")
    path = local_config_path(ROOT)
    if not path.exists():
        raise SetupError("Initialize this checkout first: ./scripts/personal/dev init")
    config = validate(ROOT, read_json(path))
    env = environment(ROOT, config)
    if args.command == "env":
        for key, value in env.items():
            if os.environ.get(key) != value:
                print("export " + key + "=" + shlex.quote(value))
        return
    if args.command == "check":
        print(f"SDK: {config['sdk_version']} (personal); upstream standard remains 26.5", flush=True)
        print(f"Bundle ID: {config['bundle_id']}\nApp: {env['TOCCATA_DEV_APP']}\nData: {env['TOCCATA_DATA_DIR']}", flush=True)
        print(f"Cargo: {env['CARGO_HOME']}\nRustup: {env['RUSTUP_HOME']}", flush=True)
        require_sdk(config, env)
        cargo = require_rust(config, env)
        run([Path(env["CARGO_HOME"]) / "bin/rustc", "--version"], ROOT, env)
        run([cargo, "--version"], ROOT, env)
        if subprocess.run(["xcrun", "--find", "xctest"], env=env, capture_output=True).returncode:
            print("Swift XCTest unavailable: full Xcode is required; app builds remain available.")
        return
    if args.command == "setup-rust":
        rustup = Path(env["CARGO_HOME"]) / "bin/rustup"
        if not rustup.exists():
            installer = ROOT / ".local-dev/downloads/rustup-init.sh"
            installer.parent.mkdir(parents=True, exist_ok=True)
            run(["curl", "--proto", "=https", "--tlsv1.2", "--fail", "--location", "--show-error",
                 "--connect-timeout", "20", "--max-time", "180", "https://sh.rustup.rs", "-o", installer], ROOT, env)
            run(["sh", installer, "-y", "--no-modify-path", "--profile", "minimal", "--default-toolchain", "none"], ROOT, env)
        if env["RUSTUP_TOOLCHAIN"] != "stable":
            run([rustup, "toolchain", "install", config["rust_version"], "--profile", "minimal",
                 "--component", "rustfmt", "--component", "clippy"], ROOT, env)
        run([Path(env["CARGO_HOME"]) / "bin/rustc", "--version"], ROOT, env)
        return
    if args.command == "fetch":
        run([require_rust(config, env), "fetch", "--locked", *extra], ROOT, env)
        return
    if args.command == "run":
        launcher = Path(env["TOCCATA_DEV_APP"]) / "Contents/MacOS/ToccataDev"
        if not launcher.exists():
            raise SetupError("Build first: ./scripts/personal/dev build")
        info = plistlib.loads((launcher.parent.parent / "Info.plist").read_bytes())
        if (info.get("CFBundleIdentifier") != config["bundle_id"] or
                info.get("ToccataDevelopmentDataDirectory") != config["data_dir"] or
                info.get("DTSDKName") != "macosx" + config["sdk_version"]):
            raise SetupError("Built app identity, data path, or SDK differs from local configuration; rebuild first")
        os.execve(str(launcher), [str(launcher), *extra], env)
    if args.command in ("test", "test-scripts"):
        run(["python3", "-B", "-m", "unittest", "discover", "-s", "scripts/tests"], ROOT, env)
        if args.command == "test-scripts":
            return
    require_sdk(config, env)
    if args.command in ("test", "test-core"):
        run([require_rust(config, env), "test", "--locked", *(extra if args.command == "test-core" else [])], ROOT, env)
        if args.command == "test-core":
            return
    if args.command in ("test", "test-swift"):
        if subprocess.run(["xcrun", "--find", "xctest"], env=env, capture_output=True).returncode:
            raise SetupError("Swift tests NOT RUN: Command Line Tools lack XCTest; install compatible full Xcode")
        run(["bash", ROOT / "scripts/sync-assets.sh"], ROOT, env)
        run(["swift", "test", *swift_options(ROOT, env), *extra], ROOT, env)
        return
    if args.command == "core":
        run([require_rust(config, env), "build", "--locked"], ROOT, env)
        binary = Path(env["CARGO_TARGET_DIR"]) / "debug/toccata-core"
        os.execve(str(binary), [str(binary)], env)
    if args.command == "build":
        if extra:
            parser.error("Set build configuration in .local-dev/config.json")
        run(["bash", ROOT / "scripts/sync-assets.sh"], ROOT, env)
        options = [*swift_options(ROOT, env), "--configuration", config["configuration"]]
        run(["swift", "build", *options], ROOT, env)
        binary_dir = Path(subprocess.check_output(["swift", "build", *map(str, options), "--show-bin-path"],
                                                 cwd=ROOT, env=env, text=True).strip())
        metadata = subprocess.check_output(["xcrun", "vtool", "-show-build", str(binary_dir / "toccata-studio")],
                                            env=env, text=True)
        if set(re.findall(r"^\s*sdk\s+(\S+)", metadata, re.MULTILINE)) != {config["sdk_version"]}:
            raise SetupError("Built binary does not use the configured development SDK")
        app = assemble_bundle(ROOT, config, env, binary_dir)
        run(["codesign", "--force", "--sign", "-", app], ROOT, env)
        run(["codesign", "--verify", "--deep", "--strict", app], ROOT, env)
        print("Built isolated task-only app: " + str(app))


if __name__ == "__main__":
    try:
        main()
    except (SetupError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print("Development setup: " + str(error), file=sys.stderr)
        sys.exit(1)
