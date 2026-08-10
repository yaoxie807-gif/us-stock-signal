# 美股信号云端

GitHub Actions 云端扫描 S&P 500，发现符合规则的买入信号后通过 Telegram 推送限价、止损、股数和风险金额。

## 启动/运行

- 云端自动运行：GitHub Actions `美股信号扫描`
- 手动测试：Actions 页面 `Run workflow`，`mode=selftest`
- 本地测试：`python scan.py --dry-run`
- 推送通道：只用 Telegram，不使用 ntfy

## 交接

先读同目录 `README.md`。本项目是当前唯一应保留的 S&P 500 纯信号扫描器；
`D:\炒股工具\股票AI-IBKR脚本\signal_scan.py` 是同源本地版，正常情况下不要同时启用，避免重复推送。
