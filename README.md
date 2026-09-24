# 期权组合跟踪与机会扫描系统

科创50ETF期权的持仓跟踪和机会扫描工具。

## 功能

### 1. 持仓跟踪（每日15:00自动更新）

- 每条腿的开仓价、当前价、变化幅度
- 浮动盈亏、接货成本、安全距离
- 盈利里程碑提示（1/3、1/2最大收益）
- 智能操作建议（基于7条原则）

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
    "has_etf": false
  }
}
```

**关键字段**：
- `targets.max_cost`：目标接货成本（当前1.65）
- `targets.has_etf`：是否持有ETF现货

### option_chain_latest.json

期权链数据，最近3个合约月的看涨/看跌期权实时价格（last/bid/ask/行权价/持仓量）。

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

## 更新日志

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
