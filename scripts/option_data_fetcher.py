"""
期权数据获取模块
从新浪财经获取ETF期权链数据
"""
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
        return float(fields[3])
    return None

def fetch_option_chain_html(etf_code="588000", expiry_month=None):
    """
    获取期权链HTML页面
    返回: HTML内容字符串
    """
    # 新浪财经期权链URL格式
    # 例如: https://stock.finance.sina.com.cn/futures/api/openapi.php/OptionService.getOptionData?type=futures&product=588000&exchange=sh&pinzhong=588000
    
    # 实际上新浪的期权数据需要通过页面抓取
    # 这里返回None，实际使用时需要通过浏览器获取
    return None

def parse_option_chain_from_browser_data(page_data):
    """
    从浏览器获取的页面数据解析期权链
    page_data格式: {
        'calls': [{'strike': 1.45, 'last': 0.30, 'bid': 0.29, 'ask': 0.31}, ...],
        'puts': [{'strike': 1.45, 'last': 0.05, 'bid': 0.04, 'ask': 0.06}, ...],
        'expiry': '2026-10-28'
    }
    """
    calls = {}
    puts = {}
    
    for call in page_data.get('calls', []):
        strike = call['strike']
        calls[strike] = {
            'last': call.get('last'),
            'bid': call.get('bid'),
            'ask': call.get('ask')
        }
    
    for put in page_data.get('puts', []):
        strike = put['strike']
        puts[strike] = {
            'last': put.get('last'),
            'bid': put.get('bid'),
            'ask': put.get('ask')
        }
    
    return {
        'expiry': page_data.get('expiry'),
        'calls': calls,
        'puts': puts
    }

def get_full_option_data(etf_price, contracts_data):
    """
    构建完整的期权数据
    contracts_data: list of {expiry, calls, puts}
    """
    return {
        'etf_price': etf_price,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'contracts': {
            c['expiry']: {
                'calls': c['calls'],
                'puts': c['puts']
            }
            for c in contracts_data
        }
    }

if __name__ == '__main__':
    # 测试
    price = fetch_etf_price()
    print(f"ETF价格: {price}")
