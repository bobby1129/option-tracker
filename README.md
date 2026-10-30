# 期权组合跟踪与机会扫描系统

科创50ETF期权的持仓跟踪和机会扫描工具。

## 功能

### 1. 持仓跟踪（每日15:00自动更新）

- 每条腿的开仓价、当前价、变化幅度
- 浮动盈亏、接货成本、安全距离
- 盈利里程碑提示（1/3、1/2最大收益）
- 智能操作建议（基于7条原则）
- **盈亏三口径汇总**：①权利金盈亏（期权腿已实现+浮动）②接货后盈亏（正股浮动）③总体盈亏（见下方配置说明）
- **接货额度提示**：按到期日汇总"若接货需准备的现金"（K1×组数×10000），额度上限人工判断

**报告路径**：`reports/latest.html`

### 2. 机会扫描（每小时扫描一次）

扫描三种策略的开仓机会：

#### 牛市价差
- 买入腿：深度实值，**时间价值 ≤ max_tv_spread 容差**（positions.json，默认0.01/份）。旧硬过滤"last≤内在价值"在真实盘口下永远不通过——深实值call按平价关系必有正时间价值（=同行权价put的时间价值），2026-10-21早盘扫出的11个机会全是陈旧last伪影
- 报价用盘口：**买腿ask、卖腿bid**（真实成交方向），无盘口退回last（对应skill Pitfall 15，杜绝陈旧last）
- 卖出腿：虚值（行权价 > 现价）
- **租金（横盘收益）与最大收益分开（2026-10-21）**：
  - 租金 = 现价 − 接货成本 = 卖腿权利金 − 买腿时间价值（ETF到期不动也能赚的钱）
  - 最大收益 = (K2−K1) − 净支出（含涨到K2才拿满的方向钱，单独展示）
  - **年化门槛只按租金算**：年化 = 租金 ÷ 净支出 × 365/天数 ≥ 100%
  - 旧算法用最大收益÷买腿价格算年化，宽价差（如1.2/1.95）方向钱被折成2000%+假年化（2026-10-21早盘实际发生的bug）
- 接货成本 < 目标价

#### 卖Put
- 虚值Put（行权价 < 现价）
- 年化收益 ≥ 100%
- 接货成本 < 目标价

#### 卖Covered Call
- 正股持仓**按批次独立扫描**（2026-10-30用户要求）：`targets.cc_holdings`（老仓）+ `stock_holdings` 每笔接货/买入各自为一个批次，同标的也不合并——确保每一笔被行权都单独赚钱
- 每批次的行权价红线 = 该批次 `cc_breakeven`（盈亏平衡）：
  - 行权接货批次 = 行权价 − 已收权利金（如 s4 = 1.45−0.0366 = 1.4134）
  - 市价买入批次 = 买入价 + 摊入对应期权组合净盈亏/股数（如 s1 = 1.422 + 组合#1净亏25440/100000股 = 1.6764，用户确认"一开始为组合的按组合盈亏看"）
  - 缺省退回 `cost`
- 只扫**虚值/平值** call（行权价 ≥ ETF现价；实值部分不是租金且锁亏正股）
- **报价用 bid**（真实成交方向），无bid退回last
- 年化收益 ≥ 15%，年化 = bid权利金 ÷ ETF现价 × 365/剩余天数
- 机会卡片显示所属批次、批次盈亏平衡、可卖手数与权利金总收入
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
- `targets.max_cost`：目标接货成本（当前1.45，2026-10-09从1.65下调）
- `targets.min_annual_spread`：价差/卖put年化门槛（%，当前100）
- `targets.min_annual_cc`：covered call年化门槛（%，当前15）
- `targets.min_scan_days`：机会扫描剩余天数过滤（当前10）——剩余天数 ≤ 此值的到期月整体跳过（临近到期年化虚高，2026-10-30新增）
- `targets.max_tv_spread`：价差买腿最大时间价值容差（每份，当前0.01；时间价值在租金中自动扣除）
- `targets.cc_holdings`：正股持仓表（covered call扫描用），按标的代码分组：

```json
"cc_holdings": {
  "510050": {"name": "50ETF", "shares": 30000, "cost": 3.03, "open_date": "2026-03-15"}
}
```

可卖手数 = shares ÷ 10000（向下取整）。有持仓的标的才会进入 covered call 扫描；`has_etf` 字段已废弃（scanner 改读 `cc_holdings`）。

**持仓状态机**（position.status，2026-10-28起）：
- `open`：正常持仓，按链上市价估值
- `pending_delivery`：义务仓到期实值、行权通知未到，腿写 `settlement_price`（put作废=0），报告挂"⏳待行权交割"角标；E+1交割确认后转 `exercised`
- `exercised`：义务仓被行权、交割完成（2026-10-30起）。权利金全额落袋锁定（口径①按 settlement_price=0 计已实现），同时写入 stock_holdings（source=exercise）+ trades.json `exercised` 流水，报告挂"✅已行权交割"角标；update_positions.py 不再刷新其腿价
- `expired`：权利仓到期归零，`settlement_price: 0.0`，挂"🔚到期归零"角标，同时记 trades.json `expired_worthless` 流水

**正股持仓 stock_holdings**（positions.json 顶层数组，2026-10-28新增）：
```json
"stock_holdings": [
  {"id": "s1", "underlying": "588000", "underlying_name": "科创50ETF",
   "shares": 100000, "cost": 1.422, "open_date": "2026-10-19",
   "source": "market_buy", "current_price": 1.354, "note": "..."}
]
```
source: `market_buy`（市价买入）| `exercise`（行权接货）。update_positions.py 每次用链中ETF价刷新 current_price。

**cc_breakeven 字段**（covered call扫描用行权价红线，2026-10-30新增）：每笔正股持仓各自的盈亏平衡，卖CC时行权价必须 ≥ 此值（被行权这笔也单独赚钱）。行权接货 = 行权价−已收权利金；市价买入且为配合期权组合而买的 = 买入价+组合净盈亏摊薄（s1 = 1.422 + 25440/100000 = 1.6764，组合#1口径含卖腿做T+4670）。cc_holdings 老仓同样加此字段（缺省=cost）。

**盈亏三口径汇总**（report_generator.py `calculate_portfolio_summary`，HTML区块+终端摘要）：
1. ① 权利金盈亏 = 全部期权腿现金流（已实现+浮动，含手续费；到期腿按结算价锁定）
2. ② 接货后盈亏 = 正股（市价买入+预期/已行权接货）(现价−接货价)×股数；行权接货成本=**行权价**（权利金已在①计入，不重复），净成本(行权价−权利金)列仅参考
3. ③ 总体盈亏 = ①+②

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

**历史快照留档**：每次抓取除写 latest 外，同时写一份带时间戳的快照（`option_chain_{code}_YYYYMMDD_HHMMSS.json`）。快照=当时盘口完整记录（bid/ask/last/持仓量），用于事后复盘（IV regime验证、成交价合理性、滑点分析——行情API可查历史价但查不到历史盘口）。**保留不删**（2026-10-09用户决定）；无任何脚本读取，纯本地存档，.gitignore排除永不提交。

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
3. 目标接货成本 < 1.45（可调整，2026-10-09从1.65下调）
4. 只看最近3个合约期
5. 年化门槛：价差/卖put ≥ 100%，covered call ≥ 15%
6. 按年化从高到低排序
7. **剩余天数 ≤ 10 天的到期月整体忽略**（2026-10-30新增）：临近到期合约权利金除以极少天数会得出虚高年化（如到期周"年化2000%"伪机会）。阈值配置在 `targets.min_scan_days`（当前10），三种策略统一生效，报告头部展示过滤条件

## 文件结构

```
option-tracker/
├── data/
│   ├── positions.json              # 持仓配置
│   ├── trades.json                 # 历史平仓流水(实际交易数据, 不提交git)
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

- **提交红线（2026-09-28确立）**：git 只提交代码/文档改动（scripts/、README.md），**实际持仓与行情数据永不提交**（data/positions.json、data/trades.json、option_chain_*.json、reports/*.html 留本地）。用户忘了提醒时，Agent 须主动提醒并只 add 代码文件。
- 两轴框架"收租+接货"：年化门槛（价差/卖put ≥100%，cc ≥15%）与接货成本红线（1.45，2026-10-09从1.65下调）均在 `positions.json` 的 `targets` 配置，scanner 不硬编码。额度上限人工判断，报告按到期日提示接货额度。
- IV regime 择时：上涨行情→牛市价差（call权利金厚，涨幅只封顶不亏 Vega）；下跌后→卖put（IV高 + 接货成本达标）。同一档 call 比 put 贵常是行权价网格错位，等距校正后 put skew 正常。
- cron 链路：`fetch_chain_sina.py`（纯 requests 抓新浪期权链，OP_UP 逐月探测合约，去掉 C 后缀）→ `scanner.py`（只读缓存）；非交易日返回 `[SILENT]`。
- 实盘券商为华泰；数据对标以华泰为准，HV 用 60 日窗口；ETF 期权交易成本约 7 元/手。
- 持仓数据：`data/positions.json`。

## 更新日志

### 2026-10-30（新持仓 + 扫描剩余天数过滤）

- ✅ 新增组合#7/#8：科创50ETF 2026-11-25 卖Put 1.1，#7 5手@0.0085（10-29）、#8 5手@0.0233（10-30）；接货成本1.0915/1.0767
- ✅ **机会扫描新增剩余天数过滤**（用户要求"到期日在10天以内可以忽略，年化会比较虚高"）：三种策略扫描函数统一加 `min_days` 参数，剩余天数 ≤ `targets.min_scan_days`（当前10）的到期月整体跳过；报告头部显示过滤条件。10-30实测：当前最近月11-25剩26天不受影响，进入11月中旬后自动生效

### 2026-10-30（三笔义务仓行权交割确认）

- ✅ 组合#4（50ETF 2.9P×5手）、#5（科创50 1.6P×5手）、#6（科创50 1.45P×5手）10-28到期被行权，10-29 E+1交割完成，状态 `pending_delivery` → **`exercised`**（新状态：权利金锁定+挂"✅已行权交割"角标，update_positions.py 跳过刷新）
- ✅ stock_holdings 新增 s2/s3/s4：50ETF 50,000股@2.9、科创50ETF 50,000股@1.6、科创50ETF 50,000股@1.45（source=exercise，open_date=2026-10-29）；科创50ETF正股合计200,000股
- ✅ trades.json 新增 trade_id 4/5/6（action=exercised）：权利金落袋 +1,275 / +2,650 / +1,830，累计6笔已实现 -11,125（含#1买腿归零-30,110）
- ✅ report_generator.py：三口径汇总/卡片/终端摘要全面支持 `exercised` 状态；接货明细按 source 区分"行权接货"与"市价买入"
- ✅ **covered call扫描改为按批次独立**（用户要求"同标的也分开扫，确保每一笔都能赚钱"）：cc_holdings老仓 + stock_holdings每笔各为一个批次，行权价红线用各批次 `cc_breakeven`（新字段）；s1按组合#1整体口径摊入卖腿做T+4,670 → 盈亏平衡1.6764（用户确认"一开始为组合的按组合盈亏看"）；行权批次 2.8745/1.547/1.4134；卡片/终端摘要显示批次标签。10-30实测：仅s4批次扫出2个机会（12月/11月 1.45C，年化16.9%/15.9%），其余批次红线高属正常

### 2026-10-28（到期日结算 + 盈亏三口径）

- ✅ **持仓状态机新增 `expired` / `pending_delivery`**：到期归零的权利仓（如组合#1 买腿1.45C，ETF收1.354<1.45虚值归零，权利金-30,110计入 trades.json trade_id=3）；到期实值待行权的义务仓（#4 50ETF 2.9P、#5 科创50 1.6P、#6 科创50 1.45P，E+1交割确认后转正式接货）。腿上加 `settlement_price` 字段（归零=0），calculate_pnl/卡片/摘要均按结算价估值并挂角标
- ✅ **新增正股持仓 `stock_holdings`**（positions.json 顶层数组）：`{id, underlying, underlying_name, shares, cost, open_date, source, current_price, note}`。首笔=科创50ETF 100,000股@1.422（2026-10-19市价买入，变相接货对应#1买腿）。update_positions.py 每次刷新其 current_price
- ✅ **报告新增"📊 盈亏三口径汇总"**（HTML区块+终端摘要，report_generator.py `calculate_portfolio_summary`）：
  - ① 权利金盈亏 = 全部期权腿现金流（已实现+浮动，含平仓手续费7元/手；到期腿按结算价锁定）
  - ② 接货后盈亏 = 正股持仓（市价买入+预期/已行权接货）(现价−接货价)×股数；**行权接货成本用行权价**，权利金已在口径①计入不重复；净成本(行权价−权利金)列仅作参考
  - ③ 总体盈亏 = ①+②
- ✅ 接货额度提示只统计 `open` 持仓（待行权组合已进接货明细，不再重复占额度）
- ✅ ~~待办：明日(10-29)交割单出来后，把 #4/#5/#6 从 `pending_delivery` 转正式接货~~（已于2026-10-30完成，见上）

### 2026-10-21

- 🐛 **修复牛市价差假年化bug（用户发现"不可能有那么高的年化"）**：旧算法 `年化 = 最大收益/买腿价格 × 365/天数`，把宽价差（如1.2/1.95，K2=现价+36%）的方向钱折成年化，早盘扫出2327%假机会。修复后**租金与最大收益分开**：租金 = 现价 − 接货成本（横盘也赚的钱），年化 = 租金/净支出 × 365/天数；最大收益含方向钱单独展示。用当日9:40归档数据回放验证：11个假机会 → 4个真实机会（1.2/1.45档年化411.9%租金口径）
- ✅ **深实值过滤改用盘口价+时间价值容差**：买腿ask/卖腿bid（无盘口退回last）；过滤条件从"last≤内在价值"（真实盘口下永远不通过，深实值call按平价关系必有正时间价值=同行权价put时间价值）改为"0 ≤ ask−内在价值 ≤ max_tv_spread"（positions.json可配，默认0.01/份）。时间价值在租金公式中自动扣除，过大则年化不达标

### 2026-10-15

- ✅ 组合#2（科创50ETF 12-23 1.3/1.8价差）卖出腿 1800C 以 0.0187 买入平仓（开仓0.105，已实现净盈利 +¥8,560），组合转为**单腿买Call 1.3C**状态
- ✅ 交易流水录入 trade_id=2；历史战绩累计2笔、已实现+¥13,230、胜率100%

### 2026-10-09

- 🎯 covered call 硬红线（用户要求）：**行权价必须 ≥ 正股成本**，被行权也锁定正收益，绝不卖"行权即亏"的位置。当前50ETF成本3.03，最近合规档位3.1（各月年化均<5%，未达15%门槛 → 扫描0机会，属正常，等波动率/价格上来）
- ✅ **.gitignore 全面落实提交红线**：显式排除 `data/positions.json`、`data/trades.json`、全部 `option_chain_*.json`（含latest与历史快照）、`reports/*`；并将历史上误跟踪的4个数据文件 `git rm --cached` 移出仓库（本地文件保留）。此后数据文件物理上不可能被误提交
- 📝 期权链历史快照约定入README：带时间戳快照为盘口留档（复盘用），保留不删、无脚本读取、永不提交
- ✅ 新增组合#6：科创50ETF 2026-10-28 卖Put 1.45×5手 @0.0366（接货成本1.4134）
- 🎯 目标接货成本红线 `targets.max_cost` 从 1.65 下调至 **1.45**（scanner/报告标题自动跟随）
- ✅ **covered call 扫描启用**：新增 `targets.cc_holdings` 正股持仓配置（50ETF 30000股 成本3.03，约2026-03-15买入，录入时已持208天）；scanner 按持仓标的多链扫描，只卖虚值/平值call、报价用bid、显示可卖手数与总收入；`has_etf` 字段废弃
- 🎯 covered call 硬红线（用户要求）：**行权价必须 ≥ 正股成本**，被行权也锁定正收益，绝不卖"行权即亏"的位置。当前50ETF成本3.03，最近合规档位3.1（各月年化均<5%，未达15%门槛 → 扫描0机会，属正常，等波动率/价格上来）

### 2026-09-30

- ✅ **历史战绩跟踪**：新增 `data/trades.json` 交易流水账（每笔平仓一条：trade_id/date/position_id/action/strike/open_price/close_price/lots/pnl_gross/cost/pnl_net/note；成本按 `cost_per_lot`=7元/手）。报告新增"📜 历史战绩"区块（HTML卡片+终端摘要）：累计平仓笔数、累计已实现盈亏、胜率、平均单笔、最大单笔盈/亏、按标的分组小计、最近5笔明细。只记已实现盈亏，与浮动盈亏口径分离
- ✅ 首笔录入：组合#1 价差卖腿 1750C 0.0739→0.0265 ×10手，毛盈+4740，扣成本70，净+4670
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
