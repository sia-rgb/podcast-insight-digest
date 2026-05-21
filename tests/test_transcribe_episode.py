import unittest
from types import SimpleNamespace

from src.transcribe_episode import build_transcript_payload, output_paths, render_markdown


class TranscribeEpisodeTest(unittest.TestCase):
    def test_build_transcript_payload_keeps_segment_timestamps_and_text(self):
        segments = [
            SimpleNamespace(start=1.2, end=3.4, text="  你好，欢迎收听。 "),
            SimpleNamespace(start=3.4, end=6.0, text="这是一次访谈。"),
        ]

        payload = build_transcript_payload(
            title="128. Manus决定出售前最后的访谈",
            audio_path="data/audio/test.m4a",
            segments=segments,
            language="zh",
        )

        self.assertEqual(payload["title"], "128. Manus决定出售前最后的访谈")
        self.assertEqual(payload["audio_path"], "data/audio/test.m4a")
        self.assertEqual(payload["language"], "zh")
        self.assertEqual(
            payload["segments"],
            [
                {"start": 1.2, "end": 3.4, "text": "你好，欢迎收听。"},
                {"start": 3.4, "end": 6.0, "text": "这是一次访谈。"},
            ],
        )

    def test_render_markdown_outputs_readable_timestamped_lines(self):
        payload = {
            "title": "128. Manus决定出售前最后的访谈",
            "segments": [
                {"start": 1.2, "end": 3.4, "text": "你好，欢迎收听。"},
            ],
        }

        markdown = render_markdown(payload)

        self.assertIn("# 128. Manus决定出售前最后的访谈", markdown)
        self.assertIn("[00:00:01.200 - 00:00:03.400] 你好，欢迎收听。", markdown)

    def test_output_paths_include_model_name(self):
        json_path, markdown_path = output_paths("small")

        self.assertEqual(str(json_path), "data\\transcripts\\128_faster_whisper_small_raw_transcript.json")
        self.assertEqual(str(markdown_path), "data\\transcripts\\128_faster_whisper_small_raw_transcript.md")


if __name__ == "__main__":
    unittest.main()
