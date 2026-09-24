#!/usr/bin/env python3
"""
新浪期权链实时抓取 (纯requests, 无需Playwright)
替代 fetch_option_data.py 的浏览器方案 — 旧方案解析页面失败(返回nan)且会把坏数据写入latest.json

接口链 (2026-09-24 实测验证):
1. 合约月份列表: StockOptionService.getRemainderDay?cate=科创50&date=YYYY-MM → expireDay
   (cateList里"科创50"=588000华夏, "科创板50"=588080易方达, 别搞混)
2. 合约代码列表: https://hq.sinajs.cn/list=OP_UP_588000{YYMM},OP_DOWN_588000{YYMM}
   ⚠️ cateId要去掉字母C: 588000C2610 → 5880002610
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
from datetime import datetime
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


def get_expiry_months():
    """枚举未来月份, 用 getRemainderDay 探测哪些月份有588000合约
    ⚠️ 不能用 getStockName 的 cateList/contractMonth zip配对 — 实测两列表长度不等(6vs5)会错配"""
    months = []
    now = datetime.now()
    for i in range(10):  # 探测未来10个月
        y = now.year + (now.month - 1 + i) // 12
        m = (now.month - 1 + i) % 12 + 1
        ym = f"{y}-{m:02d}"
        try:
            r = requests.get(
                "https://stock.finance.sina.com.cn/futures/api/openapi.php/"
                f"StockOptionService.getRemainderDay?exchange=null&cate=科创50&date={ym}&dpc=1",
                headers=HEADERS, timeout=10)
            d = r.json()["result"]["data"]
            if d.get("expireDay") and d.get("stockId") == ETF_CODE:
                months.append(ym)
        except Exception:
            continue
    return months


def month_to_expiry(ym):
    """2026-10 → 2026-10-28 (第四个周三; 用 getRemainderDay 实测接口拿准确到期日)"""
    r = requests.get(
        "https://stock.finance.sina.com.cn/futures/api/openapi.php/"
        f"StockOptionService.getRemainderDay?exchange=null&cate=科创50&date={ym}&dpc=1",
        headers=HEADERS, timeout=10)
    d = r.json()["result"]["data"]
    return d["expireDay"], d["cateId"]


def fetch_chain(verify=False):
    etf = sina_hq([ETF_SYMBOL])
    if ETF_SYMBOL not in etf:
        raise RuntimeError("ETF行情获取失败")
    etf_price = float(etf[ETF_SYMBOL][3])
    f = etf[ETF_SYMBOL]
    # 尾部为 ...,2026-09-24,11:30:00,00,(空串) → [-4]=日期 [-3]=时间
    quote_time = f"{f[-4]} {f[-3]}"

    months = get_expiry_months()[:N_MONTHS]
    contracts = {}
    for ym in months:
        expiry, cate_id = month_to_expiry(ym)
        if not expiry:
            continue
        short = cate_id.replace("C", "")  # 588000C2610 → 5880002610
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


def main():
    verify = "--verify" in sys.argv
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
