import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills/human-html/activate_hooks.py"
SPEC = importlib.util.spec_from_file_location("activate_hooks", SCRIPT)
activate_hooks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activate_hooks)


class ActivateHooksTest(unittest.TestCase):
    def test_windsurf_adapter_preserves_missing_optional_fields(self):
        wrapper = SCRIPT.parent / "hooks/human-html-windsurf.sh"
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [wrapper, "advisory"],
                input=json.dumps({
                    "agent_action_name": "pre_write_code",
                    "tool_info": {"file_path": str(Path(tmp) / "release-plan.md")},
                }),
                text=True,
                capture_output=True,
                cwd=tmp,
                check=True,
            )
        self.assertIn("human-html advisory", result.stderr)

    def test_merges_all_agents_without_clobbering_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            existing = home / ".claude/settings.json"
            existing.parent.mkdir()
            existing.write_text(
                json.dumps({"theme": "dark", "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": []}]}})
            )

            first = activate_hooks.activate(home=home, skill_dir=SCRIPT.parent)
            snapshots = {path: path.read_text() for path in first}
            second = activate_hooks.activate(home=home, skill_dir=SCRIPT.parent)

            self.assertEqual(snapshots, {path: path.read_text() for path in second})
            claude = json.loads(existing.read_text())
            self.assertEqual("dark", claude["theme"])
            self.assertEqual(2, len(claude["hooks"]["PreToolUse"]))

            cursor = json.loads((home / ".cursor/hooks.json").read_text())
            self.assertEqual(1, cursor["version"])
            self.assertEqual(1, len(cursor["hooks"]["preToolUse"]))
            self.assertIn("human-html-advisory-cursor.sh", cursor["hooks"]["preToolUse"][0]["command"])

            codex = json.loads((home / ".codex/hooks.json").read_text())
            self.assertEqual(1, len(codex["hooks"]["PostToolUse"]))

            windsurf = json.loads((home / ".codeium/windsurf/hooks.json").read_text())
            self.assertEqual(1, len(windsurf["hooks"]["pre_write_code"]))
            self.assertEqual(1, len(windsurf["hooks"]["post_write_code"]))
            self.assertEqual(1, len(windsurf["hooks"]["post_run_command"]))

    def test_rejects_invalid_existing_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            config = home / ".cursor/hooks.json"
            config.parent.mkdir()
            config.write_text("not json")

            with self.assertRaisesRegex(ValueError, "Invalid JSON"):
                activate_hooks.activate(home=home, skill_dir=SCRIPT.parent)


if __name__ == "__main__":
    unittest.main()
