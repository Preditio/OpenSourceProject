---
applyTo: "**"
---

# TrendRadar 项目维护指南 — Copilot Instructions

## 项目概述
TrendRadar 是一个自动化新闻监控系统，通过 GitHub Actions 定时抓取 RSS 新闻源和中文热榜，经 AI 智能筛选后发送邮件摘要。用户主要关注 **欧美 AI 监管政策与地缘政治** 方向。

## 关键架构

### 配置文件
- `config/config.yaml`：主配置，控制所有运行时行为
- `config/ai_interests.txt`：AI 兴趣描述文件，定义关注方向和排除规则
- `config/timeline.yaml`：时间调度配置（时段、频率、模式）
- `.github/workflows/crawler.yml`：GitHub Actions 定时任务

### 数据流
```
RSS feeds + 热榜平台 → 抓取器 → SQLite 数据库（永久保存）
→ AI 分类（min_score 过滤）→ 推送阶段（max_age_days 窗口过滤）→ 邮件通知
```

### 存储机制
- 数据库按日期分库：`output/news/{date}.db`（热榜）、`output/rss/{date}.db`（RSS）
- 所有抓取到的文章永久保留，不因 RSS feed 滚动更新而丢失
- `max_age_days` 仅控制推送展示窗口，不删除数据库数据
- 这是一个**滑动窗口**机制，永远展示"最近 N 天"的内容

## 当前配置状态

### 抓取频率
- cron: `0 0,8,16 * * *`（每 8 小时，北京时间 8:00/16:00/0:00）
- 抓取频率越高，21 天内积累的文章越完整（RSS feed 条目会滚动消失）

### RSS 源
- 已启用 ~20 个欧美主流媒体和政策机构源
- 大部分设置 `max_age_days: 30`
- 已禁用的源（确认不可用）：AP News、Reuters、The Times UK、IAPP
- EU Parliament Press 已替换为 European Commission Press Corner（原站被 WAF 拦截）
- 已添加：Yahoo News World、Congress.gov、Yahoo Finance

### AI 过滤
- `filter.method: "ai"`，使用 `openai/gpt-4o-mini` via GitHub Models
- `ai_filter.min_score: 0.65`（推送最低相关度阈值）
- `reclassify_threshold: 0`（强制全部重新分类，稳定后可改回 0.6）
- 兴趣排除规则：不要文物相关内容、不要标题党

### 推送展示
- `report.mode: "daily"`（每日全量汇总）
- `display.regions.hotlist: false`（热榜隐藏但继续抓取）
- `display.regions.rss: true`（RSS 正常展示）
- `region_order`：RSS 排在热点前面
- 邮件标题：`AI Regulation & Policy Tracker - MM/DD`

### 7 天签到机制
- 系统有 7 天自动过期机制，需定期运行 "Check In" workflow 续期
- 如果超过 7 天未签到，crawler workflow 会自动停止

## 常见操作

### 调整汇总天数（开会前）
修改 `config/config.yaml` 中 `rss.freshness_filter.max_age_days` 的值，commit + push，然后手动触发 "Get Hot News" workflow。
- 2 周会 → 14 天
- 3 周会 → 21 天
- 改完推送后可改回常用值

### 恢复热榜展示
将 `display.regions.hotlist` 改为 `true`

### 禁用/启用 RSS 源
在 `config/config.yaml` 的 `rss.feeds` 下，给对应源加 `enabled: false`

### AI 权限问题
GitHub Models 需要 PAT 有 `models` 权限。如果 AI 分析报 `AuthenticationError`，检查 PAT settings。

### Workflow 触发
```bash
gh workflow run "Get Hot News" -R Preditio/OpenSourceProject
```
需要 PAT 有 `workflow` scope，否则会 403（但 push 后 cron 会自动跑）。

## 关联项目
- Bi-weekly Assistant（同级目录 `../Bi-weekly_Assistant/`）：开会前一键触发抓取 + 生成简报的工具
  - `prepare-briefing.bat`：双击运行，输入天数自动完成 push → 触发 → 等待
  - 简报保存在 `../Bi-weekly_Assistant/Briefings/`

## 注意事项
- commit message 用中文描述改动内容
- 邮件通过 SMTP 发送，Outlook 个人邮箱不支持 basic auth，建议用 Gmail + App Password
- `freshness_filter.max_age_days` 的全局默认回退值是 3 天（代码硬编码），所以没有设置 `max_age_days` 的 feed 只会推送 3 天内文章
- 所有 feed 都应显式设置 `max_age_days`（当前科技媒体源如 MIT Tech Review、Wired 等缺少此配置）
