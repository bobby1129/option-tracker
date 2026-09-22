"""
从新浪财经抓取科创50ETF期权实时行情
"""
import json
import re
import requests
from datetime import datetime

def fetch_etf_price():
    """获取ETF当前价格"""
    url = "https://hq.sinajs.cn/list=sh588000"
    headers = {"Referer": "https://finance.sina.com.cn"}
    resp = requests.get(url, headers=headers, timeout=5)
    resp.encoding = 'gbk'
    match = re.search(r'"([^"]+)"', resp.text)
    if match:
        fields = match.group(1).split(',')
        return float(fields[3])  # 当前价
    return None

def fetch_option_chain_via_browser():
    """
    通过浏览器JS执行抓取期权数据
    这个方法由外部调用（hermes browser_console）
    """
    pass

def parse_option_table(strikes_data, call_data):
    """
    解析期权T型报价数据
    strikes_data: [(行权价, 看涨最新价, 看涨买价, 看涨卖价, 持仓量), ...]
    """
    result = {}
    for row in strikes_data:
        strike = row[0]
        result[strike] = {
            'strike': strike,
            'last': row[1],
            'bid': row[2],
            'ask': row[3],
            'volume': row[4] if len(row) > 4 else None
        }
    return result

def build_option_snapshot(etf_price, oct_calls, dec_calls, timestamp=None):
    """
    构建完整的期权快照
    oct_calls / dec_calls: {strike: {last, bid, ask, ...}}
    """
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        'timestamp': timestamp,
        'etf_price': etf_price,
        'oct_expiry': '2026-10-28',
        'dec_expiry': '2026-12-23',
        'oct_calls': oct_calls,
        'dec_calls': dec_calls
    }

def get_option_price(snapshot, expiry_key, strike, price_type='last'):
    """
    从快照中获取指定期权的价格
    price_type: 'last'(最新价), 'bid'(买价), 'ask'(卖价), 'mid'(中间价)
    """
    calls = snapshot.get(f'{expiry_key}_calls', {})
    opt = calls.get(strike)
    if not opt:
        return None
    
    if price_type == 'mid':
        return (opt['bid'] + opt['ask']) / 2
    return opt.get(price_type)

if __name__ == '__main__':
    price = fetch_etf_price()
    print(f"ETF当前价: {price}")
