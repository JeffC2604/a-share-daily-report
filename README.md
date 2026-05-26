# A 股日报助手

这是一个轻量的 A 股数据日报工具，用于抓取指数、板块和基金估值数据，并生成 Markdown 与 HTML 日报。

它只做数据抓取、数据整理和轻量观察，不构成投资建议，不做买卖推荐，也不生成个股推荐。

## v0.4.0 已完成

当前版本：`v0.4.0`

v0.4.0 增加了 GitHub Actions 和 GitHub Pages 云端部署支持。项目可以在本地通过 `python main.py` 生成日报，也可以在 GitHub Actions 中每天自动生成 HTML 日报并发布到 GitHub Pages。

本版本不包含个股推荐，不包含投资建议，不输出买卖建议。

## 当前功能

- 通过 `config.json` 配置报告日期、基金代码、指数展示列表和输出目录。
- 抓取指数数据。
- 抓取行业板块数据。
- 抓取概念板块数据。
- 抓取基金估值数据。
- 生成 Markdown 日报到 `output` 目录。
- 同时生成 HTML 日报到 `output` 目录。
- 东方财富主指数接口失败时不中断程序，会自动尝试备用指数接口。
- 主接口和备用接口都失败时，可读取本地 `fallback_data.json`。
- 数据源失败会写入日报的数据缺失提示。
- 生成轻量市场观察，只判断数据完整性、指数整体状态、基金估值波动和板块热度。
- 生成自动候选观察池，只用于整理当天值得继续观察的标的。
- 生成日报前会执行禁用词风险扫描。
- 支持 GitHub Actions 自动运行。
- 支持 GitHub Pages 发布 HTML 日报。

## 板块热度模块

板块热度模块位于 `sector_sources.py`。

当前抓取：

- 行业板块涨跌幅
- 概念板块涨跌幅
- 成交额
- 资金热度
- 上涨家数
- 下跌家数
- 领涨标的
- 领涨幅

日报中会新增：

- `板块热度观察`
- `板块数据表`

板块热度观察只做数据层面的强弱和热度描述，不做买卖建议，不做个股推荐。

## 自动候选观察池

自动候选观察池位于 `candidate_pool.py`。

它基于当前指数数据和板块热度数据，先筛选相对活跃的板块，再从板块成分股中整理出候选观察列表。

候选观察池字段包括：

- 股票代码
- 股票名称
- 市场类型
- 所属板块
- 最新价
- 涨跌幅
- 成交额
- 换手率
- 入选原因
- 风险提示
- 置信度

候选观察池不是荐股池。它只输出“候选观察”“强于板块”“跟随板块”“波动较大”“需要观察持续性”“不适合追高”“数据不完整，置信度降低”等观察类措辞。

市场类型提示只用于风险提醒。例如科创板、创业板标的可能涉及交易权限和更高波动风险。该提示不是投资建议，也不是买卖依据。

候选池为空时，日报仍会正常生成，并显示数据不完整或置信度降低。

## 配置 config.json

可以通过 `config.json` 调整日报对象，不需要改代码。

默认配置示例：

```json
{
  "report_date": "auto",
  "funds": ["018816"],
  "indexes": [
    { "code": "000001", "name": "上证指数" },
    { "code": "399001", "name": "深证成指" },
    { "code": "399006", "name": "创业板指" },
    { "code": "000300", "name": "沪深300" },
    { "code": "000688", "name": "科创50" }
  ],
  "output_dir": "output"
}
```

说明：

- `report_date`: 写 `"auto"` 时使用当天日期。
- `funds`: 基金代码列表，支持多个，例如 `["018816", "000001"]`。
- `indexes`: 日报里展示的指数列表。
- `output_dir`: 日报输出目录。

如果 `config.json` 不存在，运行 `main.py` 时会自动创建默认配置。

## 运行

在项目目录下运行：

```powershell
python main.py
```

如果 Python 不在系统 PATH 中，可以使用完整路径：

```powershell
& "C:\Users\Jeff\AppData\Local\Programs\Python\Python314\python.exe" main.py
```

运行后会生成：

- `output/daily_report_YYYY-MM-DD.md`
- `output/daily_report_YYYY-MM-DD.html`
- `public/daily_report_YYYY-MM-DD.html`
- `public/index.html`

## 查看报告

日报会生成到 `output` 目录，文件名格式：

```text
daily_report_YYYY-MM-DD.md
daily_report_YYYY-MM-DD.html
```

例如：

```text
output/daily_report_2026-05-25.md
output/daily_report_2026-05-25.html
```

Markdown 可以用 VS Code、Typora 或任意 Markdown 阅读器打开。HTML 可以直接用浏览器打开，表格更适合查看。

## 云端部署：GitHub Actions + GitHub Pages

v0.4.0 新增 `.github/workflows/daily_report.yml`。

工作流会：

1. 使用 `ubuntu-latest`
2. checkout 当前仓库
3. setup-python，使用 Python 3.11
4. 执行 `pip install -r requirements.txt`
5. 执行 `python main.py`
6. 保留 `output` 目录中的 Markdown 和 HTML 日报
7. 上传 `output` 作为 artifact
8. 将 `public` 目录发布到 GitHub Pages

### 开启 GitHub Pages

在 GitHub 仓库中：

1. 打开 `Settings`
2. 进入 `Pages`
3. 在 `Build and deployment` 中选择 `GitHub Actions`
4. 保存后运行 `Daily A Share Report` workflow

部署完成后，`public/index.html` 会成为 GitHub Pages 首页。

### 定时运行时间

GitHub Actions 的 `schedule` 使用 UTC 时间。

当前 workflow 使用：

```yaml
cron: "30 8 * * 1-5"
```

这表示 UTC 工作日 08:30 运行。换算成本地时间时，需要按所在时区自行转换。

### 手动触发

workflow 支持 `workflow_dispatch`。

手动运行方式：

1. 打开 GitHub 仓库的 `Actions`
2. 选择 `Daily A Share Report`
3. 点击 `Run workflow`

### output / artifact / Pages 的区别

- `output`: 程序运行时生成的本地日报目录，包含 Markdown 和 HTML。
- `artifact`: GitHub Actions 保存的运行产物，可在 workflow run 页面下载。
- `public`: 用于 GitHub Pages 发布的目录，包含日期 HTML 和 `index.html`。
- `public/index.html`: GitHub Pages 访问时默认打开的最新日报。

## 常见问题

### 东方财富接口返回 502

这是接口或网络侧的临时失败。程序不会中断，会自动重试 3 次；如果仍失败，会尝试备用指数接口，并在日报中标记东方财富指数接口失败。

### 出现 ReadTimeout

表示请求在 `timeout=10` 秒内没有完成。程序会自动重试；如果最终失败，会记录失败原因，不会影响其他数据源继续运行。

### requests 未安装

安装依赖：

```powershell
python -m pip install requests
```

如果使用完整 Python 路径：

```powershell
& "C:\Users\Jeff\AppData\Local\Programs\Python\Python314\python.exe" -m pip install requests
```

### Python 命令不识别

可能是 Python 没有加入 PATH，或者命中了 WindowsApps 的占位 alias。

可以用真实 Python 路径运行：

```powershell
& "C:\Users\Jeff\AppData\Local\Programs\Python\Python314\python.exe" main.py
```

## 风险说明

- 本项目只做数据抓取、整理和轻量观察，不构成投资建议。
- 本项目不做买卖推荐，不推荐个股。
- 数据源可能延迟、失败或返回异常。
- 基金估值通常是盘中估算，不等同于最终净值。
- 板块热度数据只说明当时数据表现，不代表后续走势。
- 候选观察池只用于观察整理，不代表后续走势。
- 使用报告前，应先查看数据源状态和数据缺失提示。
## v0.4.2 说明

v0.4.2 增加了板块数据质量校验。GitHub Actions 云端运行时，东方财富板块接口可能受云端网络环境影响，出现 HTTP 502、字段缺失，或只返回板块名称但核心字段为 0 / `-` 的情况。

当板块数据不完整时，系统会：
- 在数据源状态中标记原始接口、备用接口和数据质量。
- 将板块表作为“名称参考”处理，不把缺失字段伪装成正常数据。
- 在板块观察中提示“板块接口返回不完整，无法形成有效板块强弱判断”。
- 不生成候选观察池，并说明“候选池未生成：板块核心字段缺失，无法筛选”。

候选观察池不是荐股池；板块数据质量不达标时不会生成候选池。
