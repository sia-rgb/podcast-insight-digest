![Podcast Insight Digest](assets/banner.png)

## 一、项目概览

本项目用于将长时长中文播客访谈整理为结构化阅读文档，帮助用户快速获取访谈中的核心观点、关键案例和专业概念。

### 核心价值

本项目解决的问题是：长时长访谈信息密度高、收听成本高、关键观点分散，难以快速复用。

通过自动化流程，用户可以在不完整收听整期节目的情况下获得：

- 访谈主题概览
- 被访谈人基本介绍
- 核心观点、讨论主题与案例
- 关键术语解释
- 可直接阅读和存档的 Markdown 总结文档

### 输入

- 小宇宙播客 RSS URL
- 目标播客集数

当前默认 RSS：

```text
https://feed.xyzfm.space/dk4yh3pkpjp3
```

### 输出

- `summaries/{episode}-{guest}-{role}.md`：结构化访谈总结

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


## 二、快速启动

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 2. 配置环境变量

在 `.env` 中配置 TENCENTCLOUD 和 DEEPSEEK

### 3. 一键启动脚本

双击项目根目录下的：

```text
run_podcast_summary.bat
```

按提示输入要处理的播客集数，目前支持单集（例如140），也支持连续区间（例如130-140）。