from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile


ENV_PATH = Path(".env")
EPISODES_JSON = Path("data/episodes.json")
TRANSCRIPT_DIR = Path("data/transcripts")
JSON_OUTPUT = TRANSCRIPT_DIR / "128_tencent_asr_raw_transcript.json"
MARKDOWN_OUTPUT = TRANSCRIPT_DIR / "128_tencent_asr_raw_transcript.md"
TARGET_TITLE_PREFIX = "128. Manus决定出售前最后的访谈"
DEFAULT_REGION = "ap-shanghai"
ENGINE_MODEL_TYPE = "16k_zh_large"
POLL_INTERVAL_SECONDS = 30
MAX_WAIT_SECONDS = 3600


def load_env_values(env_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    for key in ("TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"):
        if not values.get(key):
            raise ValueError(f"Missing required env key: {key}")

    values.setdefault("TENCENTCLOUD_REGION", DEFAULT_REGION)
    return values


def load_episodes(path: Path = EPISODES_JSON) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def find_episode(
    episodes: list[dict[str, Any]],
    title_prefix: str = TARGET_TITLE_PREFIX,
) -> dict[str, Any]:
    for episode in episodes:
        if str(episode.get("title", "")).startswith(title_prefix):
            return episode
    raise ValueError(f"Episode not found: {title_prefix}")


def create_client(env_values: dict[str, str]) -> asr_client.AsrClient:
    cred = credential.Credential(
        env_values["TENCENTCLOUD_SECRET_ID"],
        env_values["TENCENTCLOUD_SECRET_KEY"],
    )
    http_profile = HttpProfile()
    http_profile.endpoint = "asr.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    return asr_client.AsrClient(
        cred,
        env_values.get("TENCENTCLOUD_REGION", DEFAULT_REGION),
        client_profile,
    )


def submit_rec_task(client: asr_client.AsrClient, audio_url: str) -> int:
    request = models.CreateRecTaskRequest()
    request.EngineModelType = ENGINE_MODEL_TYPE
    request.ChannelNum = 1
    request.ResTextFormat = 3
    request.SourceType = 0
    request.Url = audio_url

    response = client.CreateRecTask(request)
    data = json.loads(response.to_json_string())
    return int(data["Data"]["TaskId"])


def get_task_status(client: asr_client.AsrClient, task_id: int) -> dict[str, Any]:
    request = models.DescribeTaskStatusRequest()
    request.TaskId = task_id
    response = client.DescribeTaskStatus(request)
    data = json.loads(response.to_json_string())
    return data["Data"]


def wait_for_task(client: asr_client.AsrClient, task_id: int) -> dict[str, Any]:
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        task = get_task_status(client, task_id)
        status = task.get("Status")
        status_str = str(task.get("StatusStr", "")).lower()

        if status == 2 or status_str == "success":
            return task
        if status == 3 or status_str in {"failed", "fail"}:
            raise RuntimeError(task.get("ErrorMsg") or f"ASR task failed: {task}")

        print(f"task_id: {task_id}, status: {task.get('StatusStr') or status}")
        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"ASR task timeout: {task_id}")


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    whole_seconds = milliseconds // 1000
    milliseconds %= 1000
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def segment_from_detail(detail: dict[str, Any]) -> dict[str, Any]:
    text = detail.get("FinalSentence") or detail.get("FinalSentenceText") or ""
    return {
        "start": round(float(detail.get("StartMs", 0)) / 1000, 3),
        "end": round(float(detail.get("EndMs", 0)) / 1000, 3),
        "text": str(text).strip(),
    }


def build_transcript_payload(
    title: str,
    audio_url: str,
    task: dict[str, Any],
) -> dict[str, Any]:
    details = task.get("ResultDetail") or []
    segments = [segment_from_detail(detail) for detail in details]
    if not segments and task.get("Result"):
        segments = [{"start": 0.0, "end": 0.0, "text": str(task["Result"]).strip()}]

    return {
        "title": title,
        "audio_url": audio_url,
        "provider": "tencent_asr",
        "engine_model_type": ENGINE_MODEL_TYPE,
        "task_id": task.get("TaskId"),
        "status": task.get("Status"),
        "status_str": task.get("StatusStr"),
        "result": task.get("Result", ""),
        "segments": segments,
        "raw_task": task,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# {payload['title']}", ""]
    for segment in payload["segments"]:
        start = format_timestamp(float(segment["start"]))
        end = format_timestamp(float(segment["end"]))
        lines.append(f"[{start} - {end}] {segment['text']}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any]) -> None:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    with JSON_OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with MARKDOWN_OUTPUT.open("w", encoding="utf-8") as file:
        file.write(render_markdown(payload))


def main() -> int:
    env_values = load_env_values(ENV_PATH.read_text(encoding="utf-8"))
    episode = find_episode(load_episodes())
    client = create_client(env_values)
    task_id = submit_rec_task(client, episode["audio_url"])
    print(f"task_id: {task_id}")

    task = wait_for_task(client, task_id)
    payload = build_transcript_payload(
        title=episode["title"],
        audio_url=episode["audio_url"],
        task=task,
    )
    write_outputs(payload)

    print(f"segments: {len(payload['segments'])}")
    print(f"json: {JSON_OUTPUT}")
    print(f"markdown: {MARKDOWN_OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
