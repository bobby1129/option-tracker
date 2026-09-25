#!/usr/bin/env python3
"""
新浪期权链实时抓取 (纯requests, 无需Playwright)
替代 fetch_option_data.py 的浏览器方案 — 旧方案解析页面失败(返回nan)且会把坏数据写入latest.json

接口链 (2026-09-24 实测验证):
1. 合约月份探测: 逐月查 OP_UP_588000{YYMM} 是否非空(有合约代码即有合约, 权威)
   到期日 = 到期月第四个周三(本地计算, 实测与新浪接口100%吻合), 排除已过期月
   ⚠️ 不用 getRemainderDay 探测月份: 对某些月flaky返回None(2026-11漏掉), 且不排除过期月
   ⚠️ cate命名: "科创50"=588000华夏, "科创板50"=588080易方达, 别搞混
2. 合约代码列表: https://hq.sinajs.cn/list=OP_UP_588000{YYMM},OP_DOWN_588000{YYMM}
   (OP_UP=calls, OP_DOWN=puts; short = ETF_CODE + YYMM, 无需带字母C)
3. 合约实时行情: https://hq.sinajs.cn/list=CON_OP_xxx,CON_OP_yyy,...
4. ETF现价: https://hq.sinajs.cn/list=sh588000 (idx3=现价)

CON_OP_ 字段布局 (逗号分隔, 已在2026-09-24打印验证):
  [0]买量 [1]买价 [2]最新价 [3]卖价 [4]卖量 [5]持仓量 [6]涨跌幅% [7]行权价
  [8]昨收 [9]开盘 [10]涨停 [11]跌停
  [12..31]卖五档+买五档(价量交替) [32]行情时间 [33]主力标识 ...
输出格式与旧 option_chain_latest.json 完全兼容:
  {etf_price, timestamp, contracts: {expiry: {calls: {strike: {last,bid,ask}}, puts: {...}}}}
"""
import json
import re
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import requests

HEADERS = {"Referer": "https://stock.finance.sina.com.cn/option/quotes.html"}
HQ = "https://hq.sinajs.cn/list="
ETF_SYMBOL = "sh588000"
ETF_CODE = "588000"
N_MONTHS = 3  # 只看最近3个合约期 (用户规则)


def sina_hq(symbols):
    """批量拉新浪行情, 返回 {symbol: [字段...]}"""
    url = HQ + ",".join(symbols)
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.encoding = "gbk"
    out = {}
    for m in re.finditer(r'var hq_str_(\w+)="([^"]*)";', resp.text):
        sym, data = m.group(1), m.group(2)
        if data:
            out[sym] = data.split(",")
    return out


def fourth_wednesday(y, m):
    """上交所ETF期权到期日 = 到期月第四个周三
    2026-09/10/11/12 实测计算值与新浪接口返回100%吻合"""
    d = date(y, m, 1)
    while d.weekday() != 2:  # 2 = 周三
        d += timedelta(days=1)
    return d + timedelta(days=21)


def month_has_contracts(short):
    """探测某月是否有合约: OP_UP_{short} 非空即有(权威来源, 有合约代码就是真有合约)"""
    lst = sina_hq([f"OP_UP_{short}"])
    return bool(lst.get(f"OP_UP_{short}"))


def get_expiry_months():
    """枚举未来月份, 探测最近 N_MONTHS 个有效合约月
    返回 [(ym, expiry, short), ...]  short = 合约代码前缀(588000+YYMM)

    ⚠️ 弃用 getRemainderDay 接口探测月份: 实测对某些月flaky返回None(2026-11返回None但实际有9个合约),
       且不排除已过期月(2026-09-23已过期仍返回)。改用 OP_UP 合约列表探测(权威) + 本地算第四个周三到期日。
    ⚠️ 不能用 getStockName 的 cateList/contractMonth zip配对 — 实测两列表长度不等(6vs5)会错配。
    """
    months = []
    today = date.today()
    now = datetime.now()
    for i in range(12):  # 探测未来12个月(合约月可能不连续, 中间有空档如2701/2702)
        y = now.year + (now.month - 1 + i) // 12
        m = (now.month - 1 + i) % 12 + 1
        expiry = fourth_wednesday(y, m)
        if expiry < today:  # 排除已过期月份
            continue
        short = f"{ETF_CODE}{str(y)[2:]}{m:02d}"  # 588000 + 2610
        if month_has_contracts(short):
            months.append((f"{y}-{m:02d}", expiry.isoformat(), short))
        if len(months) >= N_MONTHS:
            break
    return months


def fetch_chain(verify=False):
    etf = sina_hq([ETF_SYMBOL])
    if ETF_SYMBOL not in etf:
        raise RuntimeError("ETF行情获取失败")
    etf_price = float(etf[ETF_SYMBOL][3])
    f = etf[ETF_SYMBOL]
    # 尾部为 ...,2026-09-24,11:30:00,00,(空串) → [-4]=日期 [-3]=时间
    quote_time = f"{f[-4]} {f[-3]}"

    months = get_expiry_months()  # [(ym, expiry, short), ...]
    contracts = {}
    for ym, expiry, short in months:
        lst = sina_hq([f"OP_UP_{short}", f"OP_DOWN_{short}"])
        calls = [c for c in lst.get(f"OP_UP_{short}", []) if c]
        puts = [c for c in lst.get(f"OP_DOWN_{short}", []) if c]
        if not calls or not puts:
            print(f"  ⚠️ {ym}: 合约列表为空, 跳过")
            continue
        quotes = sina_hq(calls + puts)
        node = {"calls": {}, "puts": {}}
        for sym, side in [(s, "calls") for s in calls] + [(s, "puts") for s in puts]:
            f = quotes.get(sym)
            if not f or len(f) < 33:
                continue
            strike = str(float(f[7]))  # 归一化: '1.4000'→'1.4' (与scanner的key格式一致)
            node[side][strike] = {
                "last": float(f[2]), "bid": float(f[1]), "ask": float(f[3]),
                "prev_close": float(f[8]), "volume_oi": int(f[5]),
                "symbol": sym, "quote_time": f[32],
            }
        contracts[expiry] = node
        if verify:
            print(f"  {expiry}: {len(node['calls'])}个call, {len(node['puts'])}个put")
            s0 = list(node["calls"].keys())[0]
            print(f"    样本 call@{s0}: {json.dumps(node['calls'][s0], ensure_ascii=False)}")

    return {
        "etf_price": etf_price,
        "timestamp": quote_time,
        "contracts": contracts,
    }


def is_trading_day():
    """交易日检查：周末直接否；工作日对比新浪上证指数行情日期与今天。
    节假日休市时新浪返回的仍是上一交易日日期 → 判定非交易日。
    行情接口异常时保守放行（宁可抓旧数据也不误杀正常交易日）。"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False, '周末休市'
    try:
        q = sina_hq(['sh000001']).get('sh000001')
        if not q or len(q) < 31:
            raise ValueError('新浪行情字段缺失')
        quote_date = q[30]  # YYYY-MM-DD
        today = now.strftime('%Y-%m-%d')
        if quote_date == today:
            return True, f'交易日（行情日期 {quote_date}）'
        return False, f'非交易日：行情日期为 {quote_date}，今天是 {today}（节假日休市）'
    except Exception as e:
        return True, f'⚠ 行情接口异常({e})，保守放行按交易日处理'


def main():
    verify = "--verify" in sys.argv
    ok, reason = is_trading_day()
    if not ok:
        print(f"NON_TRADING_DAY: {reason}")
        sys.exit(0)
    print("抓取新浪期权链 (科创50ETF 588000)...")
    data = fetch_chain(verify=verify)
    if not data["contracts"]:
        print("❌ 合约数据为空, 拒绝写入latest (保护旧数据)")
        sys.exit(1)

    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in [data_dir / f"option_chain_{ts}.json", data_dir / "option_chain_latest.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    n = sum(len(c["calls"]) + len(c["puts"]) for c in data["contracts"].values())
    print(f"✅ ETF={data['etf_price']} 行情时间={data['timestamp']} "
          f"月份={list(data['contracts'].keys())} 合约数={n}")
    print(f"已写入 data/option_chain_latest.json")


if __name__ == "__main__":
    main()
