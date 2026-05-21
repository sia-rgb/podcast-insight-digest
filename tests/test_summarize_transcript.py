import unittest

from src.summarize_transcript import (
    build_final_prompt,
    build_transcript_text,
    chunk_text,
    load_env_values,
    output_path,
)


class SummarizeTranscriptTest(unittest.TestCase):
    def test_load_env_values_uses_default_deepseek_base_url(self):
        values = load_env_values(
            "DEEPSEEK_API_KEY=key\n"
            "DEEPSEEK_MODEL=deepseek-chat\n"
        )

        self.assertEqual(values["DEEPSEEK_API_KEY"], "key")
        self.assertEqual(values["DEEPSEEK_MODEL"], "deepseek-chat")
        self.assertEqual(values["DEEPSEEK_BASE_URL"], "https://api.deepseek.com")

    def test_build_transcript_text_keeps_timestamps_and_text(self):
        payload = {
            "segments": [
                {"start": 1.2, "end": 3.4, "text": "你好。"},
                {"start": 3.4, "end": 5.6, "text": "欢迎收听。"},
            ]
        }

        text = build_transcript_text(payload)

        self.assertIn("[00:00:01.200 - 00:00:03.400] 你好。", text)
        self.assertIn("[00:00:03.400 - 00:00:05.600] 欢迎收听。", text)

    def test_chunk_text_splits_on_line_boundaries(self):
        text = "第一行\n第二行\n第三行"

        chunks = chunk_text(text, max_chars=8)

        self.assertEqual(chunks, ["第一行\n第二行", "第三行"])

    def test_output_path_uses_episode_number(self):
        self.assertEqual(str(output_path("140")), "data\\summaries\\140_summary.md")

    def test_final_prompt_uses_updated_summary_structure(self):
        prompt = build_final_prompt("标题", ["中间笔记"])

        self.assertIn("## 一句话概括", prompt)
        self.assertIn("## 主题提炼", prompt)
        self.assertIn("## 核心观点", prompt)
        self.assertIn("## 专业术语简明备注", prompt)
        self.assertIn("## 建议思考", prompt)
        self.assertNotIn("## 术语汇总表", prompt)
        self.assertIn("如果播客中有具体例子", prompt)


if __name__ == "__main__":
    unittest.main()
