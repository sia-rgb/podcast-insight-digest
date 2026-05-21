from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


ENV_PATH = Path(".env")
TRANSCRIPT_DIR = Path("data/transcripts")
SUMMARY_DIR = Path("data/summaries")
DEFAULT_EPISODE_NUMBER = "140"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
CHUNK_MAX_CHARS = 24000


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


def output_path(episode_number: str) -> Path:
    return SUMMARY_DIR / f"{episode_number}_summary.md"


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


def call_deepseek(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def summarize_chunk(client: OpenAI, model: str, chunk: str, index: int, total: int) -> str:
    system_prompt = (
        "你是中文播客内容分析助手。只基于给定转录文本提炼信息，"
        "不要编造，不要抒情，不要输出寒暄。"
    )
    user_prompt = f"""下面是长播客转录的第 {index}/{total} 个片段。

请输出这个片段的结构化中间笔记，要求：
- 保留关键人物、机构、模型、时间线和判断
- 如果嘉宾用具体案例、公司、产品、模型或个人经历支撑观点，必须记录案例和它对应的观点
- 合并重复口语，去掉语气词
- 按主题列要点
- 标出片段中出现的专业术语，并用一句话解释
- 不要写最终总结，不要写引言

转录片段：
{chunk}
"""
    return call_deepseek(client, model, system_prompt, user_prompt)


def build_final_prompt(title: str, notes: list[str]) -> str:
    joined_notes = "\n\n".join(
        f"## 片段 {index}\n{note}" for index, note in enumerate(notes, start=1)
    )
    return f"""请基于下面的分块中间笔记，为播客《{title}》生成最终结构化总结。

输出必须严格使用以下结构：

# {title}

## 一句话概括
用一句话说明这期播客聊了什么。

## 主题提炼
按核心观点分段，每段一个小标题。每段要求简洁、书面化、言之有物。
如果播客中有具体例子，请在对应观点下总结例子，说明例子支撑了什么判断。

## 核心观点
用要点列出最重要判断。每个观点下如有播客中的例子，增加“例子：...”。

## 专业术语简明备注
在正文中首次出现的专业术语，必须以“术语（简要解释）”形式处理。不要输出术语汇总表。

## 建议思考
面向一个想转入AI行业、正在准备面试的人，给出具体建议：
- 应该重点关注哪些技术方向
- 应该补哪些技能
- 应该准备哪些可展示的项目或经历
- 面试中应该如何表达对行业和岗位的理解

行文要求：
- 简洁清晰，不啰嗦不抒情
- 口语转书面，去掉语气词和废话
- 每段一个意思
- 正文中每个专业术语第一次出现时必须加括号解释，例如“Benchmark（基准测试）”
- 删除“术语汇总表”，不要输出任何术语表格
- 不要引用无意义寒暄
- 不要编造转录中没有的信息

分块中间笔记：
{joined_notes}
"""


def summarize_transcript(payload: dict[str, Any], env_values: dict[str, str]) -> str:
    client = OpenAI(
        api_key=env_values["DEEPSEEK_API_KEY"],
        base_url=env_values["DEEPSEEK_BASE_URL"],
    )
    model = env_values["DEEPSEEK_MODEL"]
    transcript_text = build_transcript_text(payload)
    chunks = chunk_text(transcript_text)

    notes = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"summarizing chunk {index}/{len(chunks)}")
        notes.append(summarize_chunk(client, model, chunk, index, len(chunks)))

    system_prompt = (
        "你是严谨的中文战略分析师，擅长把长访谈整理成结构化阅读文档。"
        "输出必须简洁、准确、书面化。"
    )
    final_prompt = build_final_prompt(str(payload["title"]), notes)
    return call_deepseek(client, model, system_prompt, final_prompt)


def write_summary(episode_number: str, summary: str) -> Path:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    path = output_path(episode_number)
    with path.open("w", encoding="utf-8") as file:
        file.write(summary.strip() + "\n")
    return path


def main() -> int:
    episode_number = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EPISODE_NUMBER
    env_values = load_env_values(ENV_PATH.read_text(encoding="utf-8"))
    payload = load_transcript(episode_number)
    summary = summarize_transcript(payload, env_values)
    path = write_summary(episode_number, summary)
    print(f"summary: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
