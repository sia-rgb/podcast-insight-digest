# Podcast Insight Digest

1. Project Goal
本项目用于将长时长中文播客访谈自动整理为结构化 Word 文档，方便快速获取访谈核心观点和专业术语。

2. Project Value
通过本项目，用户无需完整收听长时间访谈即可获取：
- 核心观点
- 关键概念解释
- AI 领域术语表
- 重要判断和分析
提升信息吸收效率，并便于知识管理。

3. Input
- 播客的RSS URL

4. Output
- 每集播客生成一个独立 Word 文档

5. Core Pipeline
RSS→ 音频下载 → ASR 转录 raw transcript → 文本分块与观点提炼 → 单集 Word 文档生成