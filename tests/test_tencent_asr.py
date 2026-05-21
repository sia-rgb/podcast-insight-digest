import unittest

from src.tencent_asr_episode import (
    build_transcript_payload,
    find_episode,
    load_env_values,
    render_markdown,
)


class TencentAsrEpisodeTest(unittest.TestCase):
    def test_load_env_values_reads_required_keys(self):
        values = load_env_values(
            "TENCENTCLOUD_SECRET_ID=id\n"
            "TENCENTCLOUD_SECRET_KEY=key\n"
            "TENCENTCLOUD_REGION=ap-shanghai\n"
        )

        self.assertEqual(values["TENCENTCLOUD_SECRET_ID"], "id")
        self.assertEqual(values["TENCENTCLOUD_SECRET_KEY"], "key")
        self.assertEqual(values["TENCENTCLOUD_REGION"], "ap-shanghai")

    def test_find_episode_matches_title_prefix(self):
        episode = find_episode(
            [
                {"title": "127. other", "audio_url": "https://example.com/127.m4a"},
                {"title": "128. Manus决定出售前最后的访谈：啊", "audio_url": "https://example.com/128.m4a"},
            ],
            "128. Manus决定出售前最后的访谈",
        )

        self.assertEqual(episode["audio_url"], "https://example.com/128.m4a")

    def test_build_transcript_payload_uses_result_detail_segments(self):
        raw_task = {
            "TaskId": 123,
            "StatusStr": "success",
            "Result": "你好，欢迎收听。",
            "ResultDetail": [
                {"StartMs": 0, "EndMs": 1200, "FinalSentence": "你好。"},
                {"StartMs": 1200, "EndMs": 2400, "FinalSentence": "欢迎收听。"},
            ],
        }

        payload = build_transcript_payload(
            title="128. Manus决定出售前最后的访谈",
            audio_url="https://example.com/128.m4a",
            task=raw_task,
        )

        self.assertEqual(payload["task_id"], 123)
        self.assertEqual(
            payload["segments"],
            [
                {"start": 0.0, "end": 1.2, "text": "你好。"},
                {"start": 1.2, "end": 2.4, "text": "欢迎收听。"},
            ],
        )

    def test_render_markdown_outputs_timestamped_segments(self):
        payload = {
            "title": "128. Manus决定出售前最后的访谈",
            "segments": [{"start": 0.0, "end": 1.2, "text": "你好。"}],
        }

        markdown = render_markdown(payload)

        self.assertIn("# 128. Manus决定出售前最后的访谈", markdown)
        self.assertIn("[00:00:00.000 - 00:00:01.200] 你好。", markdown)


if __name__ == "__main__":
    unittest.main()
