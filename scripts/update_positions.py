#!/usr/bin/env python3
"""
从 option_chain_latest.json 读取最新合约价格，更新 positions.json 中的 current_price 和 ETF 价格。
依赖: fetch_chain_sina.py 已先运行(确保 latest.json 是最新数据)。
"""
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'
POSITIONS_FILE = DATA_DIR / 'positions.json'
CHAIN_FILE = DATA_DIR / 'option_chain_latest.json'


def main():
    if not CHAIN_FILE.exists():
        print("❌ option_chain_latest.json 不存在，请先运行 fetch_chain_sina.py")
        sys.exit(1)

    with open(CHAIN_FILE) as f:
        chain = json.load(f)

    if not chain.get('contracts'):
        print("❌ 期权链数据为空，请先运行 fetch_chain_sina.py")
        sys.exit(1)

    etf_price = chain['etf_price']
    timestamp = chain['timestamp']
    contracts = chain['contracts']  # {expiry: {calls: {strike: {...}}, puts: {...}}}

    print(f"✅ 期权链数据: ETF={etf_price}, 时间={timestamp}")

    with open(POSITIONS_FILE) as f:
        positions_data = json.load(f)

    updated = 0
    for pos in positions_data['positions']:
        if pos['status'] != 'open':
            continue

        expiry = pos['expiry']
        long_strike = str(pos['long_strike'])
        short_strike = str(pos['short_strike'])

        if expiry not in contracts:
            print(f"  ⚠️ 组合#{pos['id']}: 到期日 {expiry} 不在期权链中，跳过")
            continue

        calls = contracts[expiry].get('calls', {})

        # 更新 long leg (买入的call)
        if long_strike in calls:
            long_data = calls[long_strike]
            # 用 bid/ask 中间价作为当前价(比 last 更稳定)
            long_price = (long_data['bid'] + long_data['ask']) / 2 if long_data['bid'] > 0 and long_data['ask'] > 0 else long_data['last']
            pos['legs']['long']['current_price'] = round(long_price, 4)
            print(f"  组合#{pos['id']} long@{long_strike}: {long_price:.4f} (bid={long_data['bid']}, ask={long_data['ask']})")

        # 更新 short leg (卖出的call)
        if short_strike in calls:
            short_data = calls[short_strike]
            short_price = (short_data['bid'] + short_data['ask']) / 2 if short_data['bid'] > 0 and short_data['ask'] > 0 else short_data['last']
            pos['legs']['short']['current_price'] = round(short_price, 4)
            print(f"  组合#{pos['id']} short@{short_strike}: {short_price:.4f} (bid={short_data['bid']}, ask={short_data['ask']})")

        # 更新 ETF 价格和时间
        pos['current_prices']['underlying'] = etf_price
        pos['current_prices']['update_time'] = timestamp
        updated += 1

    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 已更新 {updated} 个持仓的当前价格")
    print(f"   ETF: {etf_price}, 时间: {timestamp}")


if __name__ == '__main__':
    main()
