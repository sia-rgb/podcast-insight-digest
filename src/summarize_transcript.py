from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from openai import OpenAI


ENV_PATH = Path(".env")
TRANSCRIPT_DIR = Path("data/transcripts")
SUMMARY_DIR = Path("summaries")
SUMMARY_PROMPT_PATH = Path("prompts/interview_summary_prompt.md")
DEFAULT_EPISODE_NUMBER = "140"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
CHUNK_MAX_CHARS = 24000
RETRY_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 5
T = TypeVar("T")


def load_env_values(env_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"):
        if not values.get(key):
            raise ValueError(f"Missing required env key: {key}")

    values.setdefault("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL)
    return values


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    whole_seconds = milliseconds // 1000
    milliseconds %= 1000
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def transcript_path(episode_number: str) -> Path:
    return TRANSCRIPT_DIR / f"{episode_number}_tencent_asr_raw_transcript.json"


def safe_filename_part(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")


def clean_intro_text(value: str) -> str:
    text = re.sub(r"^[\s\d.、-]+", "", value.strip())
    text = text.replace("**", "").replace("`", "")
    return text.strip()


def basic_intro_section(summary: str) -> str:
    match = re.search(
        r"##\s*二、被访谈人基本介绍\s*(.*?)(?=\n##\s*三、|\Z)",
        summary,
        flags=re.S,
    )
    return match.group(1).strip() if match else summary


def split_guest_role(value: str) -> tuple[str, str]:
    def clean_person_name(name: str) -> str:
        first_person = re.split(r"[、/]", name, maxsplit=1)[0]
        return re.sub(r"[（(].*?[）)]", "", first_person).strip()

    def clean_role(role_value: str) -> str:
        return re.sub(r"^(是|为|担任)", "", role_value).strip()

    parts = [
        part.strip()
        for part in re.split(r"[，,；;。]\s*", value)
        if part.strip()
    ]
    guest = clean_person_name(parts[0]) if parts else "嘉宾"
    role = "嘉宾"
    if guest != "嘉宾":
        current_role_match = re.search(
            rf"{re.escape(guest)}(?:现任|现为|目前任|目前是|当前任|当前为|现在是)(.+?)(?:，|,|；|;|。|同时|并|$)",
            value,
        )
        if current_role_match:
            role = clean_role(current_role_match.group(1))
        elif len(parts) > 1:
            role = clean_role(parts[1])
    return guest, role


def extract_guest_role_from_summary(summary: str) -> tuple[str, str]:
    section = basic_intro_section(summary)
    lines = [clean_intro_text(line) for line in section.splitlines() if line.strip()]
    candidates = [
        line
        for line in lines
        if "姓名" in line and ("职业" in line or "身份" in line or "访谈人" in line)
    ]
    target = candidates[0] if candidates else (lines[0] if lines else "")

    if "：" in target:
        target = target.split("：", 1)[1]
    elif ":" in target:
        target = target.split(":", 1)[1]

    guest, role = split_guest_role(target)
    return guest or "嘉宾", role or "嘉宾"


def build_summary_filename(title: str, summary: str) -> str:
    number_match = re.match(r"(\d+)\.", title)
    if not number_match:
        raise ValueError(f"Cannot parse episode number from title: {title}")
    episode_number = number_match.group(1)

    guest_name, role = extract_guest_role_from_summary(summary)
    filename = f"{episode_number}-{guest_name}-{role}.md"
    return safe_filename_part(filename)


def output_path(payload: dict[str, Any], summary: str) -> Path:
    return SUMMARY_DIR / build_summary_filename(str(payload["title"]), summary)


def load_transcript(episode_number: str) -> dict[str, Any]:
    with transcript_path(episode_number).open("r", encoding="utf-8") as file:
        return json.load(file)


def build_transcript_text(payload: dict[str, Any]) -> str:
    lines = []
    for segment in payload["segments"]:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = format_timestamp(float(segment.get("start", 0)))
        end = format_timestamp(float(segment.get("end", 0)))
        lines.append(f"[{start} - {end}] {text}")
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for line in text.splitlines():
        line_length = len(line)
        if current and current_length + 1 + line_length > max_chars:
            chunks.append("\n".join(current))
            current = [line]
            current_length = line_length
        else:
            current.append(line)
            current_length += line_length + (1 if current_length else 0)

    if current:
        chunks.append("\n".join(current))

    return chunks


def retry_call(
    func: Callable[[], T],
    max_attempts: int = RETRY_ATTEMPTS,
    sleep_seconds: int = RETRY_SLEEP_SECONDS,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as error:
            last_error = error
            if attempt == max_attempts:
                break
            print(f"api call failed, retrying {attempt}/{max_attempts}: {error}")
            time.sleep(sleep_seconds)
    raise last_error or RuntimeError("api call failed")


def call_deepseek(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> str:
    def request() -> Any:
        return client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

    response = retry_call(request)
    return response.choices[0].message.content or ""


def load_prompt(path: Path = SUMMARY_PROMPT_PATH) -> str:
    return path.read_text(encoding="utf-8")


def build_user_prompt(prompt_template: str, title: str, transcript_text: str) -> str:
    return f"""{prompt_template}

## 本次访谈标题
{title}

## 音频转录全文
{transcript_text}
"""


def build_chunk_note_prompt(title: str, chunk: str, index: int, total: int) -> str:
    return f"""下面是播客《{title}》转录文本的第 {index}/{total} 个分块。

请只输出这个分块的中间笔记，不要输出完整访谈总结报告。

中间笔记要求：
- 提取本分块出现的关键人物、机构、模型、技术、时间线和判断
- 合并重复口语，去掉语气词和无意义寒暄
- 如果嘉宾用具体案例、公司、产品、模型或个人经历支撑观点，记录案例和对应观点
- 标出本分块出现的重要术语，并给出一句话解释
- 不要使用一级标题，不要输出最终报告标题

分块转录文本：
{chunk}
"""


def summarize_transcript(payload: dict[str, Any], env_values: dict[str, str]) -> str:
    client = OpenAI(
        api_key=env_values["DEEPSEEK_API_KEY"],
        base_url=env_values["DEEPSEEK_BASE_URL"],
    )
    model = env_values["DEEPSEEK_MODEL"]
    transcript_text = build_transcript_text(payload)
    chunks = chunk_text(transcript_text)
    prompt_template = load_prompt()
    system_prompt = "严格遵循用户提供的外部提示词完成任务。"

    if len(chunks) == 1:
        user_prompt = build_user_prompt(
            prompt_template=prompt_template,
            title=str(payload["title"]),
            transcript_text=transcript_text,
        )
        return call_deepseek(client, model, system_prompt, user_prompt)

    notes = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"summarizing chunk {index}/{len(chunks)}")
        chunk_prompt = build_chunk_note_prompt(
            title=str(payload["title"]),
            chunk=chunk,
            index=index,
            total=len(chunks),
        )
        notes.append(call_deepseek(client, model, system_prompt, chunk_prompt))

    merged_text = "\n\n".join(notes)
    final_prompt = build_user_prompt(
        prompt_template=prompt_template,
        title=str(payload["title"]),
        transcript_text=merged_text,
    )
    return call_deepseek(client, model, system_prompt, final_prompt)


def write_summary(payload: dict[str, Any], summary: str) -> Path:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    path = output_path(payload, summary)
    with path.open("w", encoding="utf-8") as file:
        file.write(summary.strip() + "\n")
    return path


def main() -> int:
    episode_number = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EPISODE_NUMBER
    env_values = load_env_values(ENV_PATH.read_text(encoding="utf-8"))
    payload = load_transcript(episode_number)
    summary = summarize_transcript(payload, env_values)
    path = write_summary(payload, summary)
    print(f"summary: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
