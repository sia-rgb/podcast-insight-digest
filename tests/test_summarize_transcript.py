import unittest
from unittest.mock import Mock

from src.summarize_transcript import (
    build_transcript_text,
    chunk_text,
    build_summary_filename,
    build_chunk_note_prompt,
    build_user_prompt,
    extract_guest_role_from_summary,
    load_env_values,
    output_path,
    retry_call,
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

    def test_extract_guest_role_from_summary_uses_basic_intro_section(self):
        summary = """# 访谈总结报告

## 一、访谈主题概览

## 二、被访谈人基本介绍

1. **姓名/职业身份**：苏煜，俄亥俄州立大学计算机系教授，New Cognition创始人。
2. **教育背景**：原文未明确提及。

## 三、核心观点、讨论主题与案例
"""

        guest, role = extract_guest_role_from_summary(summary)

        self.assertEqual(guest, "苏煜")
        self.assertEqual(role, "俄亥俄州立大学计算机系教授")

    def test_extract_guest_role_from_summary_removes_host_and_uses_current_role(self):
        summary = """# 访谈总结报告

## 二、被访谈人基本介绍

1. **访谈人姓名/职业身份**：苏煜（嘉宾）、小俊（主持人）。苏煜现任俄亥俄州立大学计算机教授，同时为AI创业公司New Cognition创始人，2025年斯隆研究奖得主。
"""

        guest, role = extract_guest_role_from_summary(summary)

        self.assertEqual(guest, "苏煜")
        self.assertEqual(role, "俄亥俄州立大学计算机教授")

    def test_build_summary_filename_uses_episode_and_summary_guest_role(self):
        title = "139. 【Agent的综述】和苏煜聊Agent技术史、OpenClaw Moment、边界的消弭和社会的辐射"
        summary = """# 访谈总结报告

## 二、被访谈人基本介绍

1. **姓名/职业身份**：苏煜，俄亥俄州立大学计算机系教授，New Cognition创始人。
"""

        filename = build_summary_filename(title, summary)

        self.assertEqual(filename, "139-苏煜-俄亥俄州立大学计算机系教授.md")

    def test_output_path_uses_episode_guest_and_role(self):
        payload = {
            "title": "139. 【Agent的综述】和苏煜聊Agent技术史、OpenClaw Moment、边界的消弭和社会的辐射"
        }
        summary = """# 访谈总结报告

## 二、被访谈人基本介绍

1. **姓名/职业身份**：苏煜，俄亥俄州立大学计算机系教授，New Cognition创始人。
"""

        self.assertEqual(str(output_path(payload, summary)), "summaries\\139-苏煜-俄亥俄州立大学计算机系教授.md")

    def test_build_user_prompt_uses_external_prompt_and_transcript(self):
        prompt = build_user_prompt(
            prompt_template="外部提示词",
            title="标题",
            transcript_text="转录文本",
        )

        self.assertIn("外部提示词", prompt)
        self.assertIn("标题", prompt)
        self.assertIn("转录文本", prompt)

    def test_build_chunk_note_prompt_does_not_request_final_report(self):
        prompt = build_chunk_note_prompt(
            title="标题",
            chunk="分块文本",
            index=1,
            total=2,
        )

        self.assertIn("中间笔记", prompt)
        self.assertIn("不要输出完整访谈总结报告", prompt)
        self.assertNotIn("访谈总结报告", prompt.replace("不要输出完整访谈总结报告", ""))

    def test_retry_call_retries_once_after_connection_error(self):
        calls = Mock(side_effect=[RuntimeError("connection"), "ok"])

        result = retry_call(calls, max_attempts=2, sleep_seconds=0)

        self.assertEqual(result, "ok")
        self.assertEqual(calls.call_count, 2)


if __name__ == "__main__":
    unittest.main()
