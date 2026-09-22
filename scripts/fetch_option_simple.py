#!/usr/bin/env python3
"""
使用requests抓取新浪期权数据
"""
import requests
import re
import json
from datetime import datetime
from pathlib import Path

def fetch_option_data_simple():
    """
    简单方式：直接从页面提取期权数据
    """
    # 科创50ETF期权页面
    url = "https://stock.finance.sina.com.cn/option/quotes.html"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    print(f"访问: {url}")
    resp = requests.get(url, headers=headers, timeout=10)
    resp.encoding = 'gb2312'
    
    # 提取ETF价格
    etf_price_match = re.search(r'price["\s:]+([\d.]+)', resp.text)
    etf_price = float(etf_price_match.group(1)) if etf_price_match else None
    print(f"ETF价格: {etf_price}")
    
    # 提取期权合约数据
    # 新浪期权数据通常在JavaScript变量中
    # 例如: var callData = [...]; var putData = [...];
    
    # 查找看涨期权数据
    call_data = []
    call_match = re.search(r'var\s+callData\s*=\s*(\[.*?\]);', resp.text, re.DOTALL)
    if call_match:
        try:
            call_data = json.loads(call_match.group(1))
            print(f"看涨期权数据: {len(call_data)} 条")
        except:
            print("解析看涨期权数据失败")
    
    # 查找看跌期权数据
    put_data = []
    put_match = re.search(r'var\s+putData\s*=\s*(\[.*?\]);', resp.text, re.DOTALL)
    if put_match:
        try:
            put_data = json.loads(put_match.group(1))
            print(f"看跌期权数据: {len(put_data)} 条")
        except:
            print("解析看跌期权数据失败")
    
    return {
        'etf_price': etf_price,
        'timestamp': datetime.now().isoformat(),
        'calls': call_data,
        'puts': put_data
    }

def fetch_option_via_api():
    """
    尝试通过API获取期权数据
    """
    # 新浪期权API（可能需要特定参数）
    api_url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/OptionService.getOptionData"
    
    params = {
        'type': 'etf',
        'product': '588000',
        'exchange': 'sh'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://stock.finance.sina.com.cn/'
    }
    
    print(f"访问API: {api_url}")
    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=10)
        data = resp.json()
        print(f"API响应: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
        return data
    except Exception as e:
        print(f"API请求失败: {e}")
        return None

def manual_input_mode():
    """
    手动输入模式：用户输入期权价格
    """
    print("\n=== 手动输入期权数据 ===")
    print("请输入当前ETF价格:")
    etf_price = float(input())
    
    print("\n请输入到期月份 (如: 2026-10):")
    expiry = input()
    
    print("\n请输入行权价和对应的期权价格")
    print("格式: 行权价,看涨买价,看涨卖价,看跌买价,看跌卖价")
    print("输入 'done' 结束")
    
    calls = {}
    puts = {}
    
    while True:
        line = input("> ").strip()
        if line.lower() == 'done':
            break
        
        parts = line.split(',')
        if len(parts) >= 5:
            try:
                strike = float(parts[0])
                call_bid = float(parts[1])
                call_ask = float(parts[2])
                put_bid = float(parts[3])
                put_ask = float(parts[4])
                
                calls[strike] = {
                    'bid': call_bid,
                    'ask': call_ask,
                    'last': (call_bid + call_ask) / 2
                }
                
                puts[strike] = {
                    'bid': put_bid,
                    'ask': put_ask,
                    'last': (put_bid + put_ask) / 2
                }
                
                print(f"  已添加: 行权价 {strike}")
            except ValueError:
                print("  格式错误，请重新输入")
    
    return {
        'etf_price': etf_price,
        'timestamp': datetime.now().isoformat(),
        'contracts': {
            expiry: {
                'calls': calls,
                'puts': puts
            }
        }
    }

def main():
    """主函数"""
    print("=== 期权数据获取工具 ===\n")
    
    # 尝试自动获取
    print("1. 尝试自动获取...")
    data = fetch_option_data_simple()
    
    if data['etf_price'] and (data['calls'] or data['puts']):
        print("\n✓ 成功获取期权数据")
    else:
        print("\n✗ 自动获取失败，切换到手动输入模式")
        data = manual_input_mode()
    
    # 保存数据
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"option_chain_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 数据已保存到: {output_file}")
    
    # 同时保存latest
    latest_file = output_dir / "option_chain_latest.json"
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 最新数据: {latest_file}")
    
    return data

if __name__ == '__main__':
    main()
