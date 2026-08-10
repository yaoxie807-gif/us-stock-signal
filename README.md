# 美股信号云端

在 **GitHub Actions 云端**每5分钟自动扫描 S&P 500，符合规则就发 **ntfy 手机推送**：
买入标的、限价、止损、建议股数和风险金额。

这是当前唯一应保留的 S&P 500 纯信号扫描器。`D:\炒股工具\股票AI-IBKR脚本` 里的
`signal_scan.py` 是同源本地版，规则相同，但会造成重复提醒；正常情况下应停用它的
Windows 定时任务 `美股信号-5分钟`。

- 数据：yfinance（免费，约延迟 15 分钟）
- 策略：筛当日“在动的票”(gap≥3% + 相对量) → 按 `rules.json` 过滤 → 出信号
- 去重：同一只票当天首次触发才发，不重复刷屏（记录在 `state/`，自动提交回仓库）
- 交易：不碰 IBKR、不下单，收到后自己去券商手动下单

---

## 部署步骤（一次性）

### 1. 建仓库并推代码
在 GitHub 网页 **New repository** 建一个空仓库（名字随意，比如 `us-stock-signal`）。
然后在本文件夹执行（把 URL 换成你的仓库地址）：

```bash
git remote add origin https://github.com/你的用户名/us-stock-signal.git
git branch -M main
git push -u origin main
```

（本地已经 `git init` 并提交好了，直接 push 即可。）

### 2. 填 ntfy 密钥（Secrets）
仓库页 **Settings → Secrets and variables → Actions → New repository secret**，加一个：

| Name | Value |
|---|---|
| `NTFY_TOPIC` | 你的 ntfy topic 名称 |

如果你想用完整 URL，也可以不用 `NTFY_TOPIC`，改加：

| Name | Value |
|---|---|
| `NOTIFY_URL` | 例如 `https://ntfy.sh/你的topic` |

Telegram 仍然保留为可选备份。需要时再加：

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram 机器人 token |
| `TELEGRAM_CHAT_ID` | Telegram chat id |

（可选）**Variables** 里可设 `PORTFOLIO_VALUE_USD` / `MAX_TRADE_SIZE_USD` / `MAX_RISK_PER_TRADE_PCT`，
不设就用默认 `25000 / 2500 / 1%`（只影响信号里给的“股数”）。

### 3. 测试
仓库页 **Actions → 美股信号扫描 → Run workflow**，`mode` 选 `selftest` 手动跑一次，
看手机是否收到 ntfy 测试推送、日志有没有报错。
（美股休市时它会“非入场时段，跳过”，属正常。）

---

## ⚠️ 关于 GitHub 免费额度（重要，决定用公开还是私有仓库）

GitHub Actions 免费额度：**公开仓库无限量；私有仓库每月 2000 分钟**。
本任务每5分钟跑一次，私有仓库大概率**会超**这 2000 分钟。三选一：

1. **用公开仓库**（推荐）：额度无限。代码里没有任何密钥（token 在 Secrets），公开无安全风险。
2. **用私有仓库 + 降频**：把 `.github/workflows/scan.yml` 里的 `*/5` 改成 `*/15`（每15分钟），基本能压进免费额度。
3. **私有 + 每5分钟**：会用超，超出部分按 GitHub 计费。

## 其它须知
- **数据不精确**：yfinance 免费源约延迟15分钟；下单前请在券商核对**实时价**。
- **GitHub 定时不准时**：Actions 定时是“尽力而为”，常延迟几分钟，属正常。
- 本项目**只发信号、不下单**，一切交易由你手动决定并执行。
- 如果修改规则或推送逻辑，要 `git commit` + `git push`，否则云端仍跑旧代码。

## 本地测试
```bash
pip install -r requirements.txt
python scan.py --dry-run     # 只打印，不发手机推送
```
