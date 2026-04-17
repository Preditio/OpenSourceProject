---
mode: agent
description: "一键触发 TrendRadar 抓取并准备 Briefing"
---

用户说"生成X天的briefing"或"X天briefing"时，从指令中提取天数，然后自动执行以下步骤：

## Step 1: 修改 max_age_days
编辑 `D:\Github_Projects\OpenSourceProject\config\config.yaml`，将 `freshness_filter` 下的 `max_age_days` 改为用户指定的天数。

## Step 2: Git push
在终端执行：
```
git -C "D:\Github_Projects\OpenSourceProject" add config/config.yaml
git -C "D:\Github_Projects\OpenSourceProject" commit -m "Briefing: max_age_days -> {天数}"
git -C "D:\Github_Projects\OpenSourceProject" push
```

## Step 3: 触发 GitHub Actions
```
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
gh workflow run "Get Hot News" -R Preditio/OpenSourceProject
```
如果 403 失败，告诉用户 push 已完成，cron 会在下一个周期自动运行，或手动去 GitHub 触发。

## Step 4: 等待完成
轮询 workflow 运行状态，直到成功：
```
gh run list -R Preditio/OpenSourceProject -w "Get Hot News" --limit 1 --json databaseId,status,conclusion
```
每 15 秒检查一次，最多等 10 分钟。

## Step 5: 完成提示
运行成功后告诉用户：
- 邮件已发送到 davidcuiczc@gmail.com
- 现在去 M365 Copilot 说"今日briefing"即可生成简报
- 简报会保存到 `D:\GithubProjects\Bi-weekly_Assistant\Briefings\`
