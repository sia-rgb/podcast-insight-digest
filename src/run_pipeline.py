from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Any


LOG_ROOT = Path("logs/runs")


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str], Path], CommandResult]


def parse_episode_selection(selection: str) -> list[str]:
    text = selection.strip()
    if re.fullmatch(r"\d+", text):
        return [text]

    match = re.fullmatch(r"(\d+)-(\d+)", text)
    if not match:
        raise ValueError("请输入单集编号，例如 140，或连续范围，例如 130-139")

    start = int(match.group(1))
    end = int(match.group(2))
    if start > end:
        raise ValueError("集数范围必须从小到大，例如 130-139")

    return [str(number) for number in range(start, end + 1)]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_run_dir() -> Path:
    return LOG_ROOT / timestamp()


def command_text(command: list[str]) -> str:
    return " ".join(command)


def append_pipeline_log(run_dir: Path, message: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "pipeline.log").open("a", encoding="utf-8") as file:
        file.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")


def write_command_log(
    log_path: Path,
    stage: str,
    episode: str | None,
    result: CommandResult,
    started_at: float,
    ended_at: float,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"time: {datetime.now().isoformat(timespec='seconds')}",
        f"stage: {stage}",
        f"episode: {episode or ''}",
        f"command: {command_text(result.command)}",
        f"started_at: {datetime.fromtimestamp(started_at).isoformat(timespec='seconds')}",
        f"ended_at: {datetime.fromtimestamp(ended_at).isoformat(timespec='seconds')}",
        f"duration_seconds: {ended_at - started_at:.3f}",
        f"returncode: {result.returncode}",
        "",
        "stdout:",
        result.stdout,
        "",
        "stderr:",
        result.stderr,
        "",
    ]
    with log_path.open("w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def run_command(command: list[str], log_path: Path) -> CommandResult:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output_lines: list[str] = []

    if process.stdout:
        try:
            for line in process.stdout:
                print(line, end="")
                output_lines.append(line)
        finally:
            process.stdout.close()

    returncode = process.wait()
    return CommandResult(
        command=command,
        returncode=returncode,
        stdout="".join(output_lines),
        stderr="",
    )


def run_stage(
    stage: str,
    command: list[str],
    log_path: Path,
    runner: Runner,
    episode: str | None = None,
) -> CommandResult:
    started_at = time.time()
    result = runner(command, log_path)
    ended_at = time.time()
    write_command_log(log_path, stage, episode, result, started_at, ended_at)
    return result


def failure_item(
    episode: str | None,
    stage: str,
    result: CommandResult,
    log_path: Path,
) -> dict[str, Any]:
    return {
        "episode": episode,
        "stage": stage,
        "returncode": result.returncode,
        "log": str(log_path),
        "error": (result.stderr or result.stdout).strip(),
    }


def save_summary(run_dir: Path, summary: dict[str, Any]) -> None:
    with (run_dir / "result_summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)


def run_pipeline(
    selection: str,
    run_dir: Path | None = None,
    runner: Runner = run_command,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    episodes = parse_episode_selection(selection)
    actual_run_dir = run_dir or default_run_dir()
    actual_run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "selection": selection,
        "episodes": episodes,
        "successful": [],
        "failed": [],
        "log_dir": str(actual_run_dir),
        "summary_dir": "summaries",
    }

    append_pipeline_log(actual_run_dir, f"start selection={selection}")
    print(f"日志目录：{actual_run_dir}")

    fetch_log = actual_run_dir / "fetch_episodes.log"
    print("开始拉取 RSS...")
    fetch_result = run_stage(
        stage="fetch",
        command=[python_executable, str(Path("src") / "fetch_episodes.py")],
        log_path=fetch_log,
        runner=runner,
    )
    if fetch_result.returncode != 0:
        summary["failed"].append(failure_item(None, "fetch", fetch_result, fetch_log))
        append_pipeline_log(actual_run_dir, "fetch failed, stop pipeline")
        save_summary(actual_run_dir, summary)
        return summary
    print("RSS 完成")

    for episode in episodes:
        append_pipeline_log(actual_run_dir, f"episode {episode} start")
        print(f"开始处理第 {episode} 集")

        asr_log = actual_run_dir / f"{episode}_tencent_asr.log"
        print(f"第 {episode} 集 ASR 开始...")
        asr_result = run_stage(
            stage="asr",
            command=[
                python_executable,
                str(Path("src") / "tencent_asr_episode.py"),
                episode,
            ],
            log_path=asr_log,
            runner=runner,
            episode=episode,
        )
        if asr_result.returncode != 0:
            summary["failed"].append(failure_item(episode, "asr", asr_result, asr_log))
            append_pipeline_log(actual_run_dir, f"episode {episode} asr failed, skip summarize")
            print(f"第 {episode} 集 ASR 失败，已跳过总结")
            print(f"日志：{asr_log}")
            continue
        print(f"第 {episode} 集 ASR 完成")

        summarize_log = actual_run_dir / f"{episode}_summarize.log"
        print(f"第 {episode} 集总结开始...")
        summarize_result = run_stage(
            stage="summarize",
            command=[
                python_executable,
                str(Path("src") / "summarize_transcript.py"),
                episode,
            ],
            log_path=summarize_log,
            runner=runner,
            episode=episode,
        )
        if summarize_result.returncode != 0:
            summary["failed"].append(
                failure_item(episode, "summarize", summarize_result, summarize_log)
            )
            append_pipeline_log(actual_run_dir, f"episode {episode} summarize failed")
            print(f"第 {episode} 集总结失败")
            print(f"日志：{summarize_log}")
            continue

        summary["successful"].append(episode)
        append_pipeline_log(actual_run_dir, f"episode {episode} success")
        print(f"第 {episode} 集总结完成")

    append_pipeline_log(actual_run_dir, "pipeline finished")
    save_summary(actual_run_dir, summary)
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    successful = ", ".join(summary["successful"]) or "无"
    failed = ", ".join(item["episode"] or item["stage"] for item in summary["failed"]) or "无"
    print("本次任务完成")
    print(f"成功：{successful}")
    print(f"失败：{failed}")
    print(f"日志目录：{summary['log_dir']}")
    print(f"总结目录：{summary['summary_dir']}")


def main() -> int:
    selection = sys.argv[1] if len(sys.argv) > 1 else input("请输入播客集数，例如 140 或 130-139：").strip()
    try:
        summary = run_pipeline(selection)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1

    print_summary(summary)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
