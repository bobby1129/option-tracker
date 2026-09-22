#!/usr/bin/env python3
"""
使用Playwright抓取新浪期权数据
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

async def fetch_option_chain(etf_code="588000", expiry_month=None):
    """
    抓取新浪期权链数据
    
    Args:
        etf_code: ETF代码，默认588000（科创50ETF）
        expiry_month: 到期月份，格式如"2026-10"，None表示获取所有月份
    
    Returns:
        dict: 期权链数据
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # 访问新浪期权页面
        url = f"https://stock.finance.sina.com.cn/option/quotes.html"
        print(f"访问: {url}")
        await page.goto(url, wait_until='networkidle')
        
        # 等待页面加载
        await page.wait_for_timeout(2000)
        
        # 选择ETF类型
        try:
            await page.click('text=ETF期权')
            await page.wait_for_timeout(1000)
        except:
            pass
        
        # 选择具体ETF
        try:
            await page.click(f'text={etf_code}')
            await page.wait_for_timeout(1000)
        except:
            pass
        
        # 获取当前ETF价格
        etf_price = await page.evaluate('''() => {
            const priceElement = document.querySelector('.price');
            return priceElement ? parseFloat(priceElement.textContent) : null;
        }''')
        
        print(f"ETF价格: {etf_price}")
        
        # 获取所有到期月份
        months = await page.evaluate('''() => {
            const monthElements = document.querySelectorAll('.month-item');
            return Array.from(monthElements).map(el => ({
                text: el.textContent.trim(),
                value: el.getAttribute('data-value') || el.textContent.trim()
            }));
        }''')
        
        print(f"可用月份: {months}")
        
        # 如果指定了月份，只抓取该月份
        if expiry_month:
            months = [m for m in months if expiry_month in m['text']]
        
        all_data = {}
        
        # 抓取每个月份的期权链
        for month in months[:3]:  # 只抓取前3个月
            month_text = month['text']
            print(f"\n抓取月份: {month_text}")
            
            try:
                # 点击月份
                await page.click(f'text={month_text}')
                await page.wait_for_timeout(2000)
                
                # 抓取看涨期权数据
                call_data = await page.evaluate('''() => {
                    const calls = [];
                    const rows = document.querySelectorAll('.call-table tbody tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 8) {
                            calls.push({
                                strike: parseFloat(cells[0].textContent),
                                last: parseFloat(cells[1].textContent) || 0,
                                bid: parseFloat(cells[2].textContent) || 0,
                                ask: parseFloat(cells[3].textContent) || 0,
                                volume: parseInt(cells[4].textContent) || 0,
                                openInterest: parseInt(cells[5].textContent) || 0
                            });
                        }
                    });
                    return calls;
                }''')
                
                # 抓取看跌期权数据
                put_data = await page.evaluate('''() => {
                    const puts = [];
                    const rows = document.querySelectorAll('.put-table tbody tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 8) {
                            puts.push({
                                strike: parseFloat(cells[0].textContent),
                                last: parseFloat(cells[1].textContent) || 0,
                                bid: parseFloat(cells[2].textContent) || 0,
                                ask: parseFloat(cells[3].textContent) || 0,
                                volume: parseInt(cells[4].textContent) || 0,
                                openInterest: parseInt(cells[5].textContent) || 0
                            });
                        }
                    });
                    return puts;
                }''')
                
                all_data[month_text] = {
                    'calls': call_data,
                    'puts': put_data
                }
                
                print(f"  看涨期权: {len(call_data)} 个")
                print(f"  看跌期权: {len(put_data)} 个")
                
            except Exception as e:
                print(f"  抓取失败: {e}")
        
        await browser.close()
        
        return {
            'etf_price': etf_price,
            'timestamp': datetime.now().isoformat(),
            'contracts': all_data
        }

async def main():
    """主函数"""
    print("开始抓取期权数据...")
    
    data = await fetch_option_chain("588000")
    
    # 保存到文件
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"option_chain_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n数据已保存到: {output_file}")
    
    # 同时保存一份latest
    latest_file = output_dir / "option_chain_latest.json"
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"最新数据: {latest_file}")
    
    return data

if __name__ == '__main__':
    asyncio.run(main())
