"""
数据获取模块 - 从新浪/腾讯获取ETF行情
"""
import requests
import re
import json
from datetime import datetime

def fetch_etf_price_sina(symbol="sh588000"):
    """从新浪获取ETF价格"""
    url = f"https://hq.sinajs.cn/list={symbol}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'gbk'
        
        # 解析: var hq_str_sh588000="科创50ETF华夏,1.790,1.749,1.758,..."
        match = re.search(r'"([^"]+)"', response.text)
        if match:
            data = match.group(1).split(',')
            if len(data) >= 4:
                return {
                    'name': data[0],
                    'open': float(data[1]),
                    'yesterday_close': float(data[2]),
                    'current': float(data[3]),
                    'high': float(data[4]) if len(data) > 4 else float(data[3]),
                    'low': float(data[5]) if len(data) > 5 else float(data[3]),
                    'timestamp': datetime.now().isoformat()
                }
    except Exception as e:
        print(f"新浪数据获取失败: {e}")
    
    return None

def fetch_etf_price_tencent(symbol="sh588000"):
    """从腾讯获取ETF价格"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    
    try:
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        
        # 解析腾讯格式
        match = re.search(r'"([^"]+)"', response.text)
        if match:
            data = match.group(1).split('~')
            if len(data) >= 5:
                return {
                    'name': data[1],
                    'current': float(data[3]),
                    'yesterday_close': float(data[4]),
                    'open': float(data[5]) if len(data) > 5 else float(data[3]),
                    'high': float(data[33]) if len(data) > 33 else float(data[3]),
                    'low': float(data[34]) if len(data) > 34 else float(data[3]),
                    'timestamp': datetime.now().isoformat()
                }
    except Exception as e:
        print(f"腾讯数据获取失败: {e}")
    
    return None

def fetch_etf_price(symbol="sh588000"):
    """获取ETF价格，优先新浪，失败则用腾讯"""
    data = fetch_etf_price_sina(symbol)
    if data:
        return data
    
    data = fetch_etf_price_tencent(symbol)
    if data:
        return data
    
    return None

if __name__ == "__main__":
    # 测试
    price = fetch_etf_price()
    if price:
        print(json.dumps(price, ensure_ascii=False, indent=2))
    else:
        print("数据获取失败")
