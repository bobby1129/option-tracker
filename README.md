# 期权组合跟踪与机会扫描系统

科创50ETF期权的持仓跟踪和机会扫描工具。

## 功能

### 1. 持仓跟踪（每日15:00自动更新）

- 每条腿的开仓价、当前价、变化幅度
- 浮动盈亏、接货成本、安全距离
- 盈利里程碑提示（1/3、1/2最大收益）
- 智能操作建议（基于7条原则）
- **接货额度提示**：按到期日汇总"若接货需准备的现金"（K1×组数×10000），额度上限人工判断

**报告路径**：`reports/latest.html`

### 2. 机会扫描（每小时扫描一次）

扫描三种策略的开仓机会：

#### 牛市价差
- 买入腿：深度实值（价格 ≤ 内在价值，无时间价值）
- 卖出腿：虚值（行权价 > 现价）
- 年化收益 ≥ 100%（基于买权支出计算）
- 接货成本 < 目标价

#### 卖Put
- 虚值Put（行权价 < 现价）
- 年化收益 ≥ 100%
- 接货成本 < 目标价

#### 卖Covered Call
- 需要持有ETF现货
- 年化收益 ≥ 15%

年化门槛与接货成本红线均从 `positions.json` 的 `targets` 读取（单位：年化%，见下方配置说明），scanner 不再硬编码。

**报告路径**：`reports/opportunities.html`

## 配置

### positions.json

```json
{
  "positions": [
    {
      "id": 1,
      "underlying": "588000",
      "type": "bull_call_spread",
      "expiry": "2026-10-28",
      "long_strike": 1.45,
      "short_strike": 1.75,
      "lots": 10,
      "legs": {
        "long": {
          "strike": 1.45,
          "direction": "buy",
          "open_price": 0.3011,
          "current_price": 0.3093
        },
        "short": {
          "strike": 1.75,
          "direction": "sell",
          "open_price": 0.0739,
          "current_price": 0.0767
        }
      },
      "current_prices": {
        "underlying": 1.758,
        "update_time": "2026-09-23 15:00:00"
      }
    }
  ],
  "targets": {
    "max_cost": 1.65,
    "min_annual_spread": 100,
    "min_annual_cc": 15,
    "has_etf": false
  }
}
```

**关键字段**：
- `targets.max_cost`：目标接货成本（当前1.65）
- `targets.min_annual_spread`：价差/卖put年化门槛（%，当前100）
- `targets.min_annual_cc`：covered call年化门槛（%，当前15）
- `targets.has_etf`：是否持有ETF现货

**卖出Put（short_put）持仓结构**（单腿，无 long 腿）：

```json
{
  "id": 3,
  "underlying": "588000",
  "type": "short_put",
  "expiry": "2026-11-25",
  "strike": 1.55,
  "lots": 5,
  "contract_multiplier": 10000,
  "open_date": "2026-09-28",
  "status": "open",
  "legs": {
    "short": {"strike": 1.55, "option_type": "put", "direction": "sell", "open_price": 0.0532, "current_price": 0.054}
  }
}
```

卖put口径：盈亏 = 权利金收入 - 当前平仓成本；资金占用 = ETF×15%×乘数×手数（与scanner一致）；接货成本 = 盈亏平衡 = 行权价 - 权利金；接货需备现金 = 行权价×手数×乘数。

### option_chain_latest.json

期权链数据，最近3个合约月的看涨/看跌期权实时价格（last/bid/ask/行权价/持仓量）。

**多标的**：588000（科创50ETF）→ `option_chain_latest.json`（历史原名，scanner依赖）；510050（上证50ETF）→ `option_chain_510050_latest.json`。标的清单在 `fetch_chain_sina.py` 的 `UNDERLYINGS` 配置。

**数据来源**：新浪财经期权T型报价接口（`fetch_chain_sina.py` 纯 requests 抓取，见"更新期权数据"）

## 使用方法

### 生成持仓报告

```bash
cd /home/cat/projects/option-tracker
python3 scripts/report_generator.py
```

### 更新期权数据

```bash
python3 scripts/fetch_chain_sina.py           # 抓实时期权链 → data/option_chain_latest.json
python3 scripts/fetch_chain_sina.py --verify  # 带字段验证输出
```

纯 requests 实现，无需浏览器。接口链（2026-09-24 实测验证）：
1. 合约月份探测：逐月查 `hq.sinajs.cn/list=OP_UP_588000{YYMM}` 是否非空（有合约代码即有合约，权威）；到期日=到期月第四个周三（本地计算，实测与新浪接口100%吻合）；排除已过期月
   ⚠️ 不用 `getRemainderDay` 探测月份——实测对某些月 flaky 返回 None（曾漏掉 2026-11），且不排除过期月（曾混入已过期的 09-23）
   ⚠️ cate 命名陷阱："科创50"=588000 华夏，"科创板50"=588080 易方达，勿混
2. `hq.sinajs.cn/list=OP_UP_588000{YYMM},OP_DOWN_588000{YYMM}` → 该月合约代码列表（OP_UP=calls，OP_DOWN=puts）
3. `hq.sinajs.cn/list=CON_OP_xxx,...` → 逐合约实时行情（bid/last/ask/行权价/持仓量）
4. `hq.sinajs.cn/list=sh588000` → ETF 现价

保护机制：合约为空时拒绝写入 latest.json（防止坏数据覆盖）。
ℹ️ 旧的 Playwright 页面解析方案（`fetch_option_data.py` / `fetch_option_simple.py`）已失效并删除（返回 nan 且会写坏 latest），统一改用本脚本。
⚠️ `scanner.py` 只读缓存文件不抓数据，**扫描前必须先跑 fetch_chain_sina.py**。

⚠️ `fetch_chain_sina.py` 入口自带交易日检查：周末/节假日休市时打印 `NON_TRADING_DAY: <原因>` 并以退出码0结束（不写缓存）。cron任务见此输出应回复 `[SILENT]` 完全静默，不发任何消息。

### 扫描机会

```bash
python3 scripts/fetch_chain_sina.py && python3 scripts/scanner.py
```

## 自动化任务

### Cron任务

1. **持仓日报**（每个交易日15:00）
   - 任务ID：`52da0bfa2a5c`
   - 生成持仓报告并发送摘要

2. **机会扫描-早盘**（每个交易日9:40）
   - 任务ID：`56caf7207b93`
   - 先 `fetch_chain_sina.py` 抓实时期权链，再 `scanner.py` 扫描，发送Top5摘要

3. **机会扫描-午盘**（每个交易日14:00）
   - 任务ID：`effeda3bccc8`
   - 同上

所有任务已固定模型 qwen3.7-plus（custom provider），全局模型切换不会导致跳过。

## 操作建议原则

### 持仓跟踪（7条原则）

1. 盈利进度 > 时间进度，收益 ≥ 1/3 → **可止盈**
2. 盈利进度 > 时间进度，收益 ≥ 1/2 → **建议止盈**
3. 时间 > 10天，收益 < 1/3 → **继续持有**
4. 时间 ≤ 10天，安全距离 > 10% → **持有到期**
5. 时间 ≤ 10天，盈利，安全距离5-10% → **密切关注准备平仓**
6. 时间 ≤ 10天，盈利，安全距离 < 5% → **建议平仓**
7. 时间 ≤ 10天，亏损 → **准备亏损接货**

**关键定义**：
- 盈利进度 = 当前浮盈 / 最大收益
- 时间进度 = 已过天数 / 总天数
- 安全距离 = (ETF价格 - 盈亏平衡) / ETF价格

### 机会扫描原则

1. 只做牛市价差、卖put、卖covered call三种
2. 绝不裸卖call，尽可能不单买权
3. 目标接货成本 < 1.65（可调整）
4. 只看最近3个合约期
5. 年化门槛：价差/卖put ≥ 100%，covered call ≥ 15%
6. 按年化从高到低排序

## 文件结构

```
option-tracker/
├── data/
│   ├── positions.json              # 持仓配置
│   └── option_chain_latest.json    # 期权链数据
├── reports/
│   ├── latest.html                 # 持仓报告
│   └── opportunities.html          # 机会扫描报告
├── scripts/
│   ├── fetch_chain_sina.py           # 实时期权链抓取（新浪T型报价接口, 纯requests）★cron/扫描入口
│   ├── report_generator.py         # 持仓报告生成器（cron 15:00）
│   ├── scanner.py                  # 机会扫描器（只读data缓存, 扫描前先跑fetch_chain_sina.py; 内联生成opportunities.html）
│   └── option_pricing.py           # 期权定价Black-Scholes库（功能完整, 当前未被其它脚本引用, 独有能力保留）
└── README.md
```

## 交易框架备忘（Agent必读）

- **提交红线（2026-09-28确立）**：git 只提交代码/文档改动（scripts/、README.md），**实际持仓与行情数据永不提交**（data/positions.json、option_chain_*.json、reports/*.html 留本地）。用户忘了提醒时，Agent 须主动提醒并只 add 代码文件。
- 两轴框架"收租+接货"：年化门槛（价差/卖put ≥100%，cc ≥15%）与接货成本红线（1.65）均在 `positions.json` 的 `targets` 配置，scanner 不硬编码。额度上限人工判断，报告按到期日提示接货额度。
- IV regime 择时：上涨行情→牛市价差（call权利金厚，涨幅只封顶不亏 Vega）；下跌后→卖put（IV高 + 接货成本达标）。同一档 call 比 put 贵常是行权价网格错位，等距校正后 put skew 正常。
- cron 链路：`fetch_chain_sina.py`（纯 requests 抓新浪期权链，OP_UP 逐月探测合约，去掉 C 后缀）→ `scanner.py`（只读缓存）；非交易日返回 `[SILENT]`。
- 实盘券商为华泰；数据对标以华泰为准，HV 用 60 日窗口；ETF 期权交易成本约 7 元/手。
- 持仓数据：`data/positions.json`。

## 更新日志

### 2026-09-30

- ✅ 组合#1（科创50ETF 10-28 1.45/1.75价差）卖出腿 1750C 以 0.0265 买入平仓（开仓0.0739，已实现盈利 +¥4,740），组合转为**单腿买Call**状态，等待回补
- ✅ 持仓结构新增"卖出腿已平"支持：`legs.short.status="closed"` + `close_price` + `close_date`；`plan` 字段记录回补计划（1750C ≥0.04~0.05 再卖出，做T目标再收~2350）
- ✅ **回补监控 `rewatch` 字段**：`{"strike": "1.75", "option_type": "call", "triggers": [0.04, 0.05]}`。update_positions.py 每次刷新被监控合约现价；report_generator.py 在 HTML 建议区和终端摘要输出监控状态，现价 ≥ 最低触发线时显示"🚨已触发"。触发线/合约可配，其他组合也可挂 rewatch
- ✅ 新增组合#5：科创50ETF 2026-10-28 卖Put 1.6×5手 @0.053（接货成本1.547）
- ✅ `update_positions.py`：closed 卖腿跳过链价更新
- ✅ `report_generator.py`：卖腿已平时——盈亏=含已实现（卖腿按平仓价锁定）；盈亏平衡/接货成本抬升平仓支出（1.45+0.2272+0.0265=1.7037）；最大收益显示"上不封顶(单腿)"；卡片/接货额度标签显示"单腿买Call(卖腿已平)"；建议区提示回补计划与theta风险

### 2026-09-28

- ✅ 报告显示持仓周期：每条持仓根据 `open_date` 计算"已持N天"（HTML角标+终端摘要），便于判断持仓时长和未来复盘
- ✅ 卡片角标统一：所有组合（价差/卖put）均显示 标的·策略·到期日·剩余天数·手数·已持天数
- ✅ 新增"理论最大收租收益率"指标：最大收益/占用资金（价差=净支出，卖put=保证金），并按总持仓周期年化（`max_return_pct` / `max_annual_return`），HTML+终端摘要均有
- ✅ 持仓跟踪支持 `short_put`（卖出Put单腿）类型：新增组合#3（科创50ETF 2026-11-25 卖Put 1.55×5手 @0.0532）、组合#4（50ETF 2026-10-28 卖Put 2.9×5手 @0.0255，9/24开仓）
- ✅ **多标的支持**：`fetch_chain_sina.py` 增加 UNDERLYINGS 配置（588000科创50ETF + 510050上证50ETF），588000 输出保持 `option_chain_latest.json` 原名（scanner等下游依赖），其他标的输出 `option_chain_{code}_latest.json`
- ✅ `update_positions.py` 重写：按 position.underlying 匹配链文件，支持 bull_call_spread / short_put 两种类型（此前只支持价差且直接取 long_strike/short_strike 会对卖put崩溃）
- `report_generator.py` 按 type 分发计算：卖put盈亏 = 权利金收入 - 当前平仓成本；资金占用与scanner口径一致（ETF×15%×乘数×手数）；接货成本=盈亏平衡=行权价-权利金
- 接货额度提示（HTML+终端摘要）纳入卖put：需备现金 = 行权价×手数×10000；持仓标签带标的名
- 报告头部改为多标的行情行（按 underlying 分组各取最新价），不再硬编码 positions[0]

### 2026-09-27

- 🐛 修复年化门槛失效bug：`positions.json` 里 `min_annual_return: 0.05` 是死配置（scanner从未读取），且 scanner 硬编码100/100/15与main()传入的30不一致，导致报告标题错误显示"≥30%"。现统一从 `targets.min_annual_spread`(100) / `targets.min_annual_cc`(15) 读取，删除死配置
- ✅ 持仓报告新增"接货额度提示"：按到期日汇总行权接货所需现金（K1×组数×10000），HTML与终端摘要均有，额度上限人工判断
- 📝 README同步：targets新字段、接货额度功能说明

### 2026-09-24（清理）

- 🗑️ 删除4个失效脚本：`fetch_option_data.py` / `fetch_option_simple.py`（Playwright页面解析, 返回nan且写坏缓存）、`option_fetcher.py` / `option_data_fetcher.py`（期权抓取函数是空壳pass/return None, 未实现）
- 🗑️ 删除2个零引用重复实现：`opportunities_report.py`（宽表格版报告, scanner内联的卡片版符合用户偏好且已在用）、`data_fetcher.py`（ETF价抓取, fetch_chain_sina.py已自含）
- ✅ 保留 `option_pricing.py`（Black-Scholes/Greeks, 项目独有能力, 无重复）
- 🐛 修复月份探测bug：弃用flaky的getRemainderDay（曾漏掉2026-11月、混入已过期的09-23），改用OP_UP合约列表逐月探测（权威）+ 本地计算第四个周三到期日 + 排除已过期月。连跑3次结果一致
- 抓取统一为 `fetch_chain_sina.py`

### 2026-09-24

- ✅ 修复扫描用过期数据的bug：`scanner.py` 只读 `option_chain_latest.json` 缓存，此前 cron 只跑 scanner，导致每天扫的都是旧行情（9/24 发现缓存是 9/23 15:00 的）
- ✅ 新增 `fetch_chain_sina.py`：纯 requests 实时抓取新浪期权链（合约月份探测→合约代码列表→逐合约行情），输出兼容旧格式；旧 Playwright 方案 `fetch_option_data.py` 已失效弃用
- ✅ 两个扫描 cron（早盘9:40/午盘14:00）prompt 更新为"先抓取再扫描"
- ✅ 全部 cron 任务固定模型 qwen3.7-plus，避免全局模型漂移触发跳过

### 2026-09-23

- ✅ 持仓跟踪系统：每条腿明细、安全距离、盈利里程碑、智能建议
- ✅ 机会扫描系统：牛市价差、卖put、卖covered call
- ✅ 筛选逻辑：买入腿深度实值、卖出腿虚值、年化≥100%
- ✅ 目标接货成本：1.65
- ✅ 卡片式展示（替代宽表格）
