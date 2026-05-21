# Podcast Insight Digest

## 一、项目概览

Podcast Insight Digest 用于将长时长中文播客访谈整理为结构化阅读文档，帮助用户快速获取访谈中的核心观点、关键案例和专业概念。

### 使用场景

- 长访谈播客快速阅读
- AI 行业访谈内容归档
- 从音频节目中提取观点、案例和术语
- 为后续知识管理、内部分享或深度阅读准备结构化材料

### 核心价值

本项目解决的问题是：长时长访谈信息密度高、收听成本高、关键观点分散，难以快速复用。

通过自动化流程，用户可以在不完整收听整期节目的情况下获得：

- 访谈主题概览
- 被访谈人基本介绍
- 核心观点、讨论主题与案例
- 关键术语解释
- 可直接阅读和存档的 Markdown 总结文档

### 输入

- 播客 RSS URL
- 目标播客集数

当前默认 RSS：

```text
https://feed.xyzfm.space/dk4yh3pkpjp3
```

### 输出

- `data/episodes.json`：播客 episode metadata
- `data/transcripts/{episode}_tencent_asr_raw_transcript.json`：腾讯云 ASR 原始转录 JSON
- `data/transcripts/{episode}_tencent_asr_raw_transcript.md`：带时间戳的 raw transcript Markdown
- `summaries/{episode}-{guest}-{role}.md`：结构化访谈总结

示例：

```text
summaries/140-姚顺宇-Google科学家.md
```

### 整体技术链路

```text
RSS 解析
→ 提取 episode title / pub_date / audio_url
→ 腾讯云 ASR 直接识别 audio_url
→ 生成 raw transcript JSON / Markdown
→ 读取 prompts/interview_summary_prompt.md
→ DeepSeek 总结
→ 输出结构化 Markdown
```

当前主链路脚本：

```text
src/fetch_episodes.py
src/tencent_asr_episode.py
src/summarize_transcript.py
```

## 二、快速启动

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 2. 配置环境变量

在 `.env` 中配置：

```text
TENCENTCLOUD_SECRET_ID=...
TENCENTCLOUD_SECRET_KEY=...
TENCENTCLOUD_REGION=ap-shanghai

DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=...
```

`DEEPSEEK_BASE_URL` 可选；未配置时默认使用：

```text
https://api.deepseek.com
```

### 3. 解析 RSS

```powershell
python src\fetch_episodes.py
```

输出：

```text
data\episodes.json
```

### 4. 转录指定集数

例如转录第 140 集：

```powershell
python src\tencent_asr_episode.py 140
```

输出：

```text
data\transcripts\140_tencent_asr_raw_transcript.json
data\transcripts\140_tencent_asr_raw_transcript.md
```

### 5. 生成访谈总结

```powershell
python src\summarize_transcript.py 140
```

输出：

```text
summaries\140-姚顺宇-Google科学家.md
```

### 6. 运行测试

```powershell
python -m unittest discover -s tests
```
