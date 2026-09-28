#!/usr/bin/env python3
"""
从各标的的期权链缓存读取最新合约价格，更新 positions.json 中的 current_price 和 ETF 价格。
支持多标的（按 position.underlying 匹配链文件）与 bull_call_spread / short_put 两种持仓类型。
依赖: fetch_chain_sina.py 已先运行(确保 latest.json 是最新数据)。

链文件命名约定（与 fetch_chain_sina.py UNDERLYINGS 一致）:
  588000 → data/option_chain_latest.json（历史原名, scanner等下游依赖）
  其他   → data/option_chain_{code}_latest.json
"""
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'
POSITIONS_FILE = DATA_DIR / 'positions.json'


def chain_file_for(underlying):
    if underlying == '588000':
        return DATA_DIR / 'option_chain_latest.json'
    return DATA_DIR / f'option_chain_{underlying}_latest.json'


def mid_price(quote):
    """bid/ask 中间价作为当前价(比 last 更稳定), 无效时退回 last"""
    bid, ask = quote.get('bid', 0), quote.get('ask', 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return quote.get('last', 0)


def main():
    with open(POSITIONS_FILE) as f:
        positions_data = json.load(f)

    # 按标的加载链数据（懒加载 + 缓存）
    chains = {}
    updated = 0
    for pos in positions_data['positions']:
        if pos['status'] != 'open':
            continue
        underlying = pos['underlying']
        if underlying not in chains:
            cf = chain_file_for(underlying)
            if not cf.exists():
                print(f"❌ {cf.name} 不存在，请先运行 fetch_chain_sina.py")
                sys.exit(1)
            with open(cf) as f:
                chain = json.load(f)
            if not chain.get('contracts'):
                print(f"❌ {underlying} 期权链数据为空，请先运行 fetch_chain_sina.py")
                sys.exit(1)
            chains[underlying] = chain
            print(f"✅ {underlying} 期权链: ETF={chain['etf_price']}, 时间={chain['timestamp']}")
        chain = chains[underlying]

        expiry = pos['expiry']
        if expiry not in chain['contracts']:
            print(f"  ⚠️ 组合#{pos['id']}: 到期日 {expiry} 不在 {underlying} 期权链中，跳过")
            continue
        node = chain['contracts'][expiry]
        calls = node.get('calls', {})
        puts = node.get('puts', {})

        if pos['type'] == 'bull_call_spread':
            long_strike = str(pos['long_strike'])
            short_strike = str(pos['short_strike'])
            if long_strike in calls:
                p = mid_price(calls[long_strike])
                pos['legs']['long']['current_price'] = round(p, 4)
                print(f"  组合#{pos['id']} long call@{long_strike}: {p:.4f}")
            else:
                print(f"  ⚠️ 组合#{pos['id']}: call@{long_strike} 不在链中")
            if short_strike in calls:
                p = mid_price(calls[short_strike])
                pos['legs']['short']['current_price'] = round(p, 4)
                print(f"  组合#{pos['id']} short call@{short_strike}: {p:.4f}")
            else:
                print(f"  ⚠️ 组合#{pos['id']}: call@{short_strike} 不在链中")
        elif pos['type'] == 'short_put':
            strike = str(pos['strike'])
            if strike in puts:
                p = mid_price(puts[strike])
                pos['legs']['short']['current_price'] = round(p, 4)
                print(f"  组合#{pos['id']} short put@{strike}: {p:.4f}")
            else:
                print(f"  ⚠️ 组合#{pos['id']}: put@{strike} 不在链中")
        else:
            print(f"  ⚠️ 组合#{pos['id']}: 未知类型 {pos['type']}，跳过")
            continue

        pos['current_prices']['underlying'] = chain['etf_price']
        pos['current_prices']['update_time'] = chain['timestamp']
        updated += 1

    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 已更新 {updated} 个持仓的当前价格")


if __name__ == '__main__':
    main()
