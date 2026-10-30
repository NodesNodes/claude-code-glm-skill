import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "configure_glm.py"
FAKE_KEY = "unit-test-only.not-a-live-key"


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.settings = self.root / "settings.json"
        self.env = dict(os.environ)
        self.env.pop("ZAI_CODING_PLAN_API_KEY", None)

    def run_script(self, *args, key=None):
        env = dict(self.env)
        if key is not None:
            env["ZAI_CODING_PLAN_API_KEY"] = key
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--settings", str(self.settings), *args],
            env=env, input="", text=True, capture_output=True, timeout=10,
        )
        self.assertNotIn(FAKE_KEY, result.stdout + result.stderr)
        return result

    def test_merge_backup_private_files_and_key_reuse(self):
        original = {
            "model": "sonnet", "theme": "dark",
            "permissions": {"deny": ["Bash(rm *)"]},
            "autoMode": {"soft_deny": ["$defaults"]},
            "env": {"KEEP_ME": "yes", "CLAUDE_CODE_USE_BEDROCK": "1"},
        }
        source = json.dumps(original, indent=4).encode() + b"\n"
        self.settings.write_bytes(source)
        result = self.run_script("configure", key=FAKE_KEY)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(self.settings.read_text())
        for name in ("theme", "permissions", "autoMode"):
            self.assertEqual(actual[name], original[name])
        self.assertEqual(actual["env"]["KEEP_ME"], "yes")
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", actual["env"])
        self.assertEqual(actual["env"]["ANTHROPIC_AUTH_TOKEN"], FAKE_KEY)
        backups = list(self.root.glob("settings.before-glm.*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), source)
        if os.name == "posix":
            for path in (self.settings, backups[0]):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        result = self.run_script("configure", "--client-auto")
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(self.settings.read_text())
        self.assertEqual(updated["permissions"], original["permissions"])
        self.assertEqual(updated["autoMode"], original["autoMode"])
        self.assertEqual(updated["env"]["CLAUDE_CODE_AUTO_MODE_SERVER"], "0")
        status = self.run_script("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertTrue(json.loads(status.stdout)["key_present"])

    def test_no_key_or_bad_json_does_not_change_settings(self):
        self.settings.write_text('{"model":"sonnet"}\n')
        source = self.settings.read_bytes()
        result = self.run_script("configure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.settings.read_bytes(), source)
        self.assertEqual(list(self.root.glob("settings.before-glm.*.json")), [])
        self.settings.write_text('{"private":"' + FAKE_KEY + '", broken')
        source = self.settings.read_bytes()
        result = self.run_script("configure", key=FAKE_KEY)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.settings.read_bytes(), source)

    def test_restore_is_exact_and_saves_current_configuration(self):
        source = b'{ "model": "sonnet", "theme": "dark" }\n'
        self.settings.write_bytes(source)
        result = self.run_script("configure", key=FAKE_KEY)
        self.assertEqual(result.returncode, 0, result.stderr)
        configured = self.settings.read_bytes()
        backup = next(self.root.glob("settings.before-glm.*.json"))
        result = self.run_script("restore", "--backup", str(backup))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.settings.read_bytes(), source)
        self.assertTrue(any(p.read_bytes() == configured
                            for p in self.root.glob("settings.before-glm.*.json")))

    def test_new_settings_with_key_file_and_invalid_context(self):
        key_file = self.root / "coding-plan.key"
        key_file.write_text(FAKE_KEY + "\n")
        result = self.run_script("configure", "--key-file", str(key_file),
                                 "--context-tokens", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.settings.exists())
        result = self.run_script("configure", "--key-file", str(key_file))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.settings.read_text())["model"], "glm-5.3")
        self.assertEqual(list(self.root.glob("settings.before-glm.*.json")), [])

    @unittest.skipUnless(os.name == "posix", "POSIX symlink behavior")
    def test_symlink_refused_without_modifying_target(self):
        target = self.root / "real-settings.json"
        target.write_text('{}\n')
        self.settings.symlink_to(target)
        result = self.run_script("configure", key=FAKE_KEY)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), '{}\n')
        self.assertTrue(self.settings.is_symlink())


if __name__ == "__main__":
    unittest.main()
