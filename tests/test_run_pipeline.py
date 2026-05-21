import importlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


class RunPipelineTest(unittest.TestCase):
    def test_module_exists(self):
        module = importlib.util.find_spec("src.run_pipeline")

        self.assertIsNotNone(module)

    def test_parse_episode_selection_accepts_single_and_range(self):
        from src.run_pipeline import parse_episode_selection

        self.assertEqual(parse_episode_selection("140"), ["140"])
        self.assertEqual(parse_episode_selection("130-132"), ["130", "131", "132"])

    def test_parse_episode_selection_rejects_descending_range(self):
        from src.run_pipeline import parse_episode_selection

        with self.assertRaises(ValueError):
            parse_episode_selection("139-130")

    def test_run_pipeline_fetches_once_and_skips_failed_episode(self):
        from src.run_pipeline import CommandResult, run_pipeline

        commands = []

        def fake_runner(command, log_path):
            commands.append(command)
            if command[-1] == "131" and "tencent_asr_episode.py" in command[1]:
                return CommandResult(command, 1, "", "asr failed")
            return CommandResult(command, 0, "ok", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            summary = run_pipeline(
                "130-132",
                run_dir=run_dir,
                runner=fake_runner,
                python_executable="python",
            )

            self.assertEqual(summary["successful"], ["130", "132"])
            self.assertEqual(summary["failed"][0]["episode"], "131")
            self.assertEqual(summary["failed"][0]["stage"], "asr")
            self.assertEqual(len([cmd for cmd in commands if "fetch_episodes.py" in cmd[1]]), 1)
            self.assertFalse(any(cmd[-1] == "131" and "summarize_transcript.py" in cmd[1] for cmd in commands))
            self.assertTrue((run_dir / "pipeline.log").exists())
            self.assertTrue((run_dir / "result_summary.json").exists())

            with (run_dir / "result_summary.json").open("r", encoding="utf-8") as file:
                saved_summary = json.load(file)
            self.assertEqual(saved_summary["successful"], ["130", "132"])

    def test_run_command_streams_child_output_to_console(self):
        from src.run_pipeline import run_command

        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            command = [sys.executable, "-c", "print('child output')"]

            with redirect_stdout(output):
                result = run_command(command, Path(temp_dir) / "command.log")

            self.assertEqual(result.returncode, 0)
            self.assertIn("child output", output.getvalue())
            self.assertIn("child output", result.stdout)

    def test_run_pipeline_prints_progress_before_long_running_steps(self):
        from src.run_pipeline import CommandResult, run_pipeline

        def fake_runner(command, log_path):
            return CommandResult(command, 0, "ok", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            run_dir = Path(temp_dir) / "run"

            with redirect_stdout(output):
                run_pipeline(
                    "130",
                    run_dir=run_dir,
                    runner=fake_runner,
                    python_executable="python",
                )

            console_text = output.getvalue()
            self.assertIn("日志目录：", console_text)
            self.assertIn("开始拉取 RSS", console_text)
            self.assertIn("开始处理第 130 集", console_text)
            self.assertIn("第 130 集 ASR 开始", console_text)
            self.assertIn("第 130 集总结开始", console_text)


if __name__ == "__main__":
    unittest.main()
