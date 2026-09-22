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

期权链数据，包含10月和12月合约的看涨/看跌期权价格。

**数据来源**：新浪财经期权T型报价（通过浏览器抓取）

## 使用方法

### 生成持仓报告

```bash
cd /home/cat/projects/option-tracker
python3 scripts/report_generator.py
```

### 扫描机会

```bash
python3 scripts/scanner.py
```

### 更新期权数据

1. 用浏览器访问：https://stock.finance.sina.com.cn/option/quotes.html
2. 选择"ETF期权" → "科创50"
3. 切换到目标月份（10月、12月）
4. 用JavaScript提取数据：

```javascript
(() => {
    const tables = document.querySelectorAll('table');
    const result = {calls: [], puts: [], strikes: []};

    if (tables[0]) {
        const rows = tables[0].querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 6) {
                result.calls.push({
                    bid: parseFloat(cells[1].textContent),
                    last: parseFloat(cells[2].textContent),
                    ask: parseFloat(cells[3].textContent),
                    oi: cells[5].textContent.trim()
                });
            }
        });
    }

    if (tables[1]) {
        const rows = tables[1].querySelectorAll('tr');
        rows.forEach(row => {
            const cell = row.querySelector('td');
            if (cell) result.strikes.push(parseFloat(cell.textContent));
        });
    }

    if (tables[2]) {
        const rows = tables[2].querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 6) {
                result.puts.push({
                    bid: parseFloat(cells[1].textContent),
                    last: parseFloat(cells[2].textContent),
                    ask: parseFloat(cells[3].textContent),
                    oi: cells[5].textContent.trim()
                });
            }
        });
    }

    return JSON.stringify(result);
})()
```

5. 将结果保存到 `data/option_chain_latest.json`

## 自动化任务

### Cron任务

1. **持仓日报**（每个交易日15:00）
   - 任务ID：`52da0bfa2a5c`
   - 生成持仓报告并发送摘要

2. **机会扫描**（每小时）
   - 待实现

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
│   ├── report_generator.py         # 持仓报告生成器
│   ├── scanner.py                  # 机会扫描器
│   ├── data_fetcher.py             # ETF价格获取
│   └── option_pricing.py           # 期权定价（Black-Scholes）
└── README.md
```

## 更新日志

### 2026-09-23

- ✅ 持仓跟踪系统：每条腿明细、安全距离、盈利里程碑、智能建议
- ✅ 机会扫描系统：牛市价差、卖put、卖covered call
- ✅ 筛选逻辑：买入腿深度实值、卖出腿虚值、年化≥100%
- ✅ 目标接货成本：1.65
- ✅ 卡片式展示（替代宽表格）
