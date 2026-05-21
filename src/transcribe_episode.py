from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable


AUDIO_DIR = Path("data/audio")
TRANSCRIPT_DIR = Path("data/transcripts")
MODEL_SIZE = "small"
CLIP_TIMESTAMPS = "0,60"


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    whole_seconds = milliseconds // 1000
    milliseconds %= 1000
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def build_transcript_payload(
    title: str,
    audio_path: str,
    segments: Iterable[object],
    language: str,
) -> dict[str, object]:
    payload_segments = []
    for segment in segments:
        payload_segments.append(
            {
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": str(segment.text).strip(),
            }
        )

    return {
        "title": title,
        "audio_path": audio_path,
        "language": language,
        "segments": payload_segments,
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [f"# {payload['title']}", ""]
    for segment in payload["segments"]:
        start = format_timestamp(segment["start"])
        end = format_timestamp(segment["end"])
        lines.append(f"[{start} - {end}] {segment['text']}")
    return "\n".join(lines) + "\n"


def output_paths(model_size: str) -> tuple[Path, Path]:
    stem = f"128_faster_whisper_{model_size}_raw_transcript"
    return TRANSCRIPT_DIR / f"{stem}.json", TRANSCRIPT_DIR / f"{stem}.md"


def find_audio_file() -> Path:
    matches = sorted(AUDIO_DIR.glob("128*.m4a"))
    if not matches:
        raise FileNotFoundError("No episode 128 audio file found in data/audio")
    return matches[0]


def transcribe_audio(audio_path: Path) -> dict[str, object]:
    from faster_whisper import WhisperModel

    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(audio_path),
        language="zh",
        beam_size=5,
        vad_filter=True,
        clip_timestamps=CLIP_TIMESTAMPS,
    )
    return build_transcript_payload(
        title=audio_path.stem,
        audio_path=str(audio_path),
        segments=list(segments),
        language=info.language or "zh",
    )


def write_outputs(payload: dict[str, object]) -> tuple[Path, Path]:
    json_output, markdown_output = output_paths(MODEL_SIZE)
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    with json_output.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with markdown_output.open("w", encoding="utf-8") as file:
        file.write(render_markdown(payload))
    return json_output, markdown_output


def main() -> int:
    audio_path = find_audio_file()
    payload = transcribe_audio(audio_path)
    json_output, markdown_output = write_outputs(payload)
    print(f"segments: {len(payload['segments'])}")
    print(f"json: {json_output}")
    print(f"markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
