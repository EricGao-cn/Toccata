"""Protect development identities and data while rebuilding disposable setups."""

import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("personal_dev", ROOT / "scripts/personal/dev.py")
DEV = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEV)


class PersonalDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="td-", dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.checkout("source")
        self.state = self.base / "state"
        self.environment = mock.patch.dict(os.environ, {}, clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop("TOCCATA_DEV_CONFIG", None)

    def checkout(self, name):
        root = self.base / name
        folder = root / "scripts/personal"
        folder.mkdir(parents=True)
        shutil.copy(ROOT / "scripts/personal/dev-defaults.json", folder)
        return root

    def initialize(self, root=None):
        return DEV.initialize(root or self.root, state_root=self.state)[0]

    def command_with_global_cargo(self, *args):
        shutil.copy(ROOT / "scripts/personal/dev.py", self.root / "scripts/personal/dev.py")
        fake_bin = self.base / "global-bin"
        fake_bin.mkdir()
        marker = self.base / "global-cargo-used"
        cargo = fake_bin / "cargo"
        cargo.write_text('#!/bin/sh\nprintf used > "$FAKE_CARGO_LOG"\n')
        cargo.chmod(0o755)
        env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
                   FAKE_CARGO_LOG=str(marker))
        result = subprocess.run([sys.executable, str(self.root / "scripts/personal/dev.py"), *args],
                                cwd=self.root, env=env, text=True, capture_output=True)
        return result, marker

    def test_copied_configuration_cannot_reuse_another_checkout_identity(self):
        self.initialize()
        other = self.checkout("copied-config")
        (other / ".local-dev").mkdir()
        shutil.copy(self.root / ".local-dev/config.json", other / ".local-dev/config.json")
        with self.assertRaisesRegex(DEV.SetupError, "checkout"):
            DEV.initialize(other, state_root=self.state)

    def test_missing_local_rust_never_falls_back_to_global_cargo(self):
        self.initialize()
        result, marker = self.command_with_global_cargo("fetch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("setup-rust", result.stderr)
        self.assertFalse(marker.exists())

    def test_core_rejects_unsupported_profile_before_building(self):
        self.initialize()
        result, marker = self.command_with_global_cargo("core", "--release")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(marker.exists())

    def test_real_worktree_keeps_data_after_removal_and_shares_toolchains(self):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

        def git(*args):
            return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(self.root), *args],
                                  env=env, text=True, capture_output=True, check=True)

        (self.root / ".gitignore").write_text('/.local-dev/\n')
        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "Fixture baseline")
        first = self.initialize()
        other = self.base / "actual-worktree"
        git("worktree", "add", "-b", "fixture-feature", str(other))
        second = self.initialize(other)
        self.assertEqual(DEV.common_checkout_root(other), self.root)
        self.assertEqual(second["cargo_home"], first["cargo_home"])
        self.assertNotEqual(second["bundle_id"], first["bundle_id"])
        self.assertNotEqual(second["data_dir"], first["data_dir"])
        git("worktree", "remove", str(other))
        self.assertTrue(Path(second["data_dir"]).is_dir())

    def test_repeat_initialization_preserves_configuration_and_data(self):
        config = self.initialize()
        path = self.root / ".local-dev/config.json"
        before = path.read_bytes(), path.stat().st_mtime_ns
        fixture = Path(config["data_dir"]) / "tasks.sqlite"
        fixture.write_bytes(b"existing development data")
        repeated, created = DEV.initialize(self.root, state_root=self.base / "different")
        self.assertFalse(created)
        self.assertEqual(repeated, config)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertEqual(fixture.read_bytes(), b"existing development data")

    def test_worktrees_share_only_toolchains_not_identity_or_data(self):
        first = self.initialize()
        other = self.checkout("feature")
        with mock.patch.object(DEV, "common_checkout_root", return_value=self.root):
            second = self.initialize(other)
        for key in ("worktree_id", "bundle_id", "app_name", "data_dir"):
            self.assertNotEqual(first[key], second[key], key)
        for key in ("cargo_home", "rustup_home"):
            self.assertEqual(first[key], second[key])
        self.assertEqual(DEV.worktree_id(other), DEV.worktree_id(other))
        self.assertFalse(Path(second["data_dir"]).is_relative_to(other))

    def test_legacy_setup_is_adopted_without_rewriting_data_settings(self):
        legacy = self.root / ".local-dev"
        app = legacy / "out/Toccata Dev.app/Contents"
        app.mkdir(parents=True)
        (app / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": DEV.DEV_ID_PREFIX}))
        data = legacy / "data"
        data.mkdir()
        settings = data / "config.json"
        settings.write_text(json.dumps({"activity_window_secs": 7, "db_path": str(data / "toccata.db")}))
        before = settings.read_bytes(), settings.stat().st_mtime_ns
        config = self.initialize()
        self.assertEqual(config["data_dir"], str(data))
        self.assertEqual(config["bundle_id"], DEV.DEV_ID_PREFIX)
        self.assertEqual((settings.read_bytes(), settings.stat().st_mtime_ns), before)

    def test_rejects_daily_use_directories_and_identifiers(self):
        config = self.initialize()
        support = Path.home() / "Library/Application Support"
        for data in (support / "Toccata", support / "Toccata/db", support / "Toccata-Personal", Path.home()):
            with self.subTest(data=data), self.assertRaises(DEV.SetupError):
                DEV.validate(self.root, dict(config, data_dir=str(data)))
        for identity in ("com.toccata.studio", "cn.ericgao.toccata.personal", "cn.ericgao.toccata.devil"):
            with self.subTest(identity=identity), self.assertRaises(DEV.SetupError):
                DEV.validate(self.root, dict(config, bundle_id=identity))

    def test_rejects_redirected_database_and_symlinked_runtime_files(self):
        config = self.initialize()
        data = Path(config["data_dir"])
        settings = data / "config.json"
        settings.write_text(json.dumps({"db_path": str(self.base / "elsewhere.sqlite")}))
        with self.assertRaisesRegex(DEV.SetupError, "escapes"):
            DEV.validate(self.root, config)
        settings.write_text("{}")
        target = self.base / "other.sqlite"
        target.write_bytes(b"not development data")
        (data / "tasks.sqlite").symlink_to(target)
        with self.assertRaisesRegex(DEV.SetupError, "symlinked"):
            DEV.validate(self.root, config)

    def test_rejects_unsafe_config_paths_and_overlong_sockets(self):
        with mock.patch.dict(os.environ, {"TOCCATA_DEV_CONFIG": str(self.base / "outside.json")}):
            with self.assertRaises(DEV.SetupError):
                DEV.local_config_path(self.root)
        config = self.initialize()
        with self.assertRaisesRegex(DEV.SetupError, "socket"):
            DEV.validate(self.root, dict(config, data_dir=str(self.base / ("long" * 40))))

    def test_rejects_toolchains_in_daily_use_paths_and_redirected_outputs(self):
        config = self.initialize()
        for key in ("cargo_home", "rustup_home"):
            with self.subTest(key=key), self.assertRaisesRegex(DEV.SetupError, "protected"):
                DEV.validate(self.root, dict(config, **{key: "/Applications/Toccata.app/tools"}))
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / ".local-dev/out").symlink_to(outside)
        with self.assertRaisesRegex(DEV.SetupError, "escapes"):
            DEV.validate(self.root, config)

    def test_task_only_packaging_refuses_an_embedded_collector(self):
        config = self.initialize()
        env = DEV.environment(self.root, config)
        macos = Path(env["TOCCATA_DEV_APP"]) / "Contents/MacOS"
        macos.mkdir(parents=True)
        helper = macos / "toccata-core"
        helper.write_bytes(b"unexpected collector")
        with self.assertRaisesRegex(DEV.SetupError, "collection helper"):
            DEV.assemble_bundle(self.root, config, env, self.base / "unused-binary")
        self.assertEqual(helper.read_bytes(), b"unexpected collector")

    def test_launcher_pins_data_even_with_conflicting_inherited_environment(self):
        config = self.initialize()
        # Exercise shell quoting with an apostrophe in the data directory.
        config["data_dir"] = str(self.base / "test's data")
        DEV.validate(self.root, config)
        binary_dir = self.base / "binary"
        bundle = binary_dir / "toccata-studio_toccata-studio.bundle"
        bundle.mkdir(parents=True)
        binary = binary_dir / "toccata-studio"
        binary.write_text('#!/bin/bash\nprintf "%s" "$TOCCATA_DATA_DIR"\n')
        binary.chmod(0o755)
        shared = self.root / "shared"
        shared.mkdir()
        (shared / "app-version.json").write_text('{"version":"0.1.2","build":"19"}')
        env = DEV.environment(self.root, config)
        app = DEV.assemble_bundle(self.root, config, env, binary_dir)
        info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
        self.assertEqual(info["CFBundleIdentifier"], config["bundle_id"])
        self.assertEqual(info["ToccataDevelopmentDataDirectory"], config["data_dir"])
        self.assertFalse((app / "Contents/MacOS/toccata-core").exists())
        output = subprocess.check_output([str(app / "Contents/MacOS/ToccataDev")],
            text=True, env=dict(os.environ, TOCCATA_DATA_DIR="/unwanted/daily-data"))
        self.assertEqual(output, config["data_dir"])

    def test_sdk_guard_rejects_a_different_sdk_before_building(self):
        config = self.initialize()
        env = DEV.environment(self.root, config)
        with mock.patch.object(DEV.subprocess, "check_output", return_value="26.5\n") as query:
            with self.assertRaisesRegex(DEV.SetupError, "requires SDK 26.2"):
                DEV.require_sdk(config, env)
            self.assertEqual(query.call_count, 1)
        self.assertNotIn("SDKROOT", {k: v for k, v in env.items() if k not in os.environ})


if __name__ == "__main__":
    unittest.main()
