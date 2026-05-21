PROJECT_PLAN.md

1. Project Goal
将长时长中文播客访谈自动整理为结构化 Word 文档，支持单集独立输出并保留原始 transcript 数据，便于快速阅读和知识管理。

2. Current State
Current Stage: MVP 3
Stage Status: Minimal Validation Passed
Last Updated: 2026-05-21
整体项目状态：MVP 3 已完成最小验证。已使用 DeepSeek 将第 140 集 raw transcript 总结为结构化 Markdown。

3. MVP Roadmap
MVP 1: RSS 解析与音频下载
Goal: 从 RSS 中解析 episode 列表，提取音频地址，并下载目标音频。
Input:
- 播客 RSS URL: https://feed.xyzfm.space/dk4yh3pkpjp3
Expected Output:
- episode metadata JSON / CSV
- 下载的音频文件（.m4a）
Core Difficulty:
- RSS 解析稳定性
- enclosure 音频地址提取
- 音频下载失败处理
- 文件命名安全处理
Acceptance Criteria:
- 成功解析至少 3 个 episode
- 每个 episode 至少包含 title / pub_date / audio_url
- 下载至少 1 个音频文件成功
Do Not Do Yet:
- 不做 ASR 转录
- 不做 Word 文档生成
- 不做前端开发

MVP 2: 音频转录为 raw transcript
Goal: 将本地音频文件转录为带时间戳的 raw transcript。
Input:
- 本地音频文件
Expected Output:
- raw transcript JSON
- raw transcript Markdown
Core Difficulty:
- 长音频转录稳定性
- 中文识别质量
- 时间戳 segment 输出
Acceptance Criteria:
- 成功转录至少一段音频
- 输出 JSON 中包含 segments
Do Not Do Yet:
- 不做 Word 文档生成

MVP 3: raw transcript 整理为 Word
Goal: 将 raw transcript 处理成结构化单集 Word 文档。
Input:
- raw transcript JSON
Expected Output:
- 每集独立 Word 文档
Core Difficulty:
- 长文本分块
- 按时间或主题提炼观点
- 合并、去重、归类、重排
Acceptance Criteria:
- 成功生成 Word 文档
- Word 使用标题样式，便于导航
Do Not Do Yet:
- 不处理其他音频或 RSS

4. Active MVP
Active MVP: MVP 3
Current Task: 第 140 集结构化总结 Markdown 已通过最小验证
Do Now:
- 等待用户确认是否生成 Word 文档
Do Not Do Yet:
- 不做多集批量总结

5. Update Policy
本文件不写详细调试日志，仅记录项目状态变化
且仅在有意义开发轮次结束时更新
有意义状态变化包括：
- MVP 状态变更
- 验收标准通过/失败
- 实现重要功能
- 发现阻塞
- 技术路线变化
- 输出或命令有实质变化
- 下一步任务变化
不为小改动、格式调整或临时调试更新此文件
详细开发日志放 DEV_LOG.md
