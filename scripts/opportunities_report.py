"""
机会扫描报告生成器
生成HTML格式的机会扫描报告
"""
from datetime import datetime
from pathlib import Path

def generate_opportunities_report(opportunities, config, etf_price, timestamp):
    """
    生成机会扫描HTML报告
    opportunities: 扫描结果列表
    config: 扫描配置
    etf_price: ETF当前价格
    timestamp: 扫描时间
    """
    
    # 按策略类型分组
    spreads = [o for o in opportunities if o['strategy'] == '牛市价差']
    puts = [o for o in opportunities if o['strategy'] == '卖put']
    ccs = [o for o in opportunities if o['strategy'] == '卖covered call']
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>期权机会扫描报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        .header {{
            text-align: center;
            padding: 30px 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,215,0,0.2);
        }}
        .header h1 {{
            font-size: 28px;
            background: linear-gradient(90deg, #ffd700, #ffed4e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .header .subtitle {{
            color: #aaa;
            font-size: 14px;
        }}
        .header .etf-price {{
            font-size: 42px;
            font-weight: bold;
            color: #ffd700;
            margin: 15px 0;
        }}
        .header .update-time {{
            color: #888;
            font-size: 12px;
        }}
        
        .config-box {{
            background: rgba(255,255,255,0.06);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 13px;
        }}
        .config-box .config-item {{
            display: inline-block;
            margin-right: 30px;
            color: #aaa;
        }}
        .config-box .config-value {{
            color: #ffd700;
            font-weight: 600;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .summary-card {{
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .summary-card .label {{
            color: #aaa;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .summary-card .value {{
            font-size: 24px;
            font-weight: bold;
            color: #4ade80;
        }}
        
        .strategy-section {{
            background: rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,215,0,0.15);
        }}
        .strategy-section h2 {{
            color: #ffd700;
            font-size: 20px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .strategy-section h2 .badge {{
            background: rgba(255,215,0,0.2);
            color: #ffd700;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
        }}
        
        .opportunity-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .opportunity-table th {{
            background: rgba(255,215,0,0.1);
            color: #ffd700;
            padding: 10px;
            text-align: left;
            font-weight: 600;
        }}
        .opportunity-table td {{
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .opportunity-table tr:hover {{
            background: rgba(255,255,255,0.05);
        }}
        .opportunity-table .highlight {{
            color: #4ade80;
            font-weight: 600;
        }}
        
        .no-opportunity {{
            text-align: center;
            padding: 40px;
            color: #888;
            font-size: 14px;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 期权机会扫描报告</h1>
            <div class="subtitle">科创50ETF (588000) · 机会扫描</div>
            <div class="etf-price">¥{etf_price:.3f}</div>
            <div class="update-time">扫描时间: {timestamp}</div>
        </div>
        
        <div class="config-box">
            <span class="config-item">目标接货成本: <span class="config-value">¥{config['target_delivery_cost']:.2f}</span></span>
            <span class="config-item">牛市价差门槛: <span class="config-value">{config['min_annual_spread']}%</span></span>
            <span class="config-item">卖put门槛: <span class="config-value">{config['min_annual_put']}%</span></span>
            <span class="config-item">covered call门槛: <span class="config-value">{config['min_annual_cc']}%</span></span>
            <span class="config-item">持仓状态: <span class="config-value">{'有货' if config['has_etf'] else '无货'}</span></span>
        </div>
        
        <div class="summary-grid">
            <div class="summary-card">
                <div class="label">牛市价差机会</div>
                <div class="value">{len(spreads)}</div>
            </div>
            <div class="summary-card">
                <div class="label">卖put机会</div>
                <div class="value">{len(puts)}</div>
            </div>
            <div class="summary-card">
                <div class="label">卖covered call机会</div>
                <div class="value">{len(ccs)}</div>
            </div>
        </div>
"""
    
    # 牛市价差
    html += """
        <div class="strategy-section">
            <h2>
                牛市价差
                <span class="badge">接货成本 &lt; ¥{:.2f}</span>
                <span class="badge">年化 ≥ {}%</span>
            </h2>
""".format(config['target_delivery_cost'], config['min_annual_spread'])
    
    if spreads:
        html += """
            <table class="opportunity-table">
                <thead>
                    <tr>
                        <th>到期日</th>
                        <th>剩余天数</th>
                        <th>买入行权价</th>
                        <th>卖出行权价</th>
                        <th>买入价</th>
                        <th>卖出价</th>
                        <th>净支出</th>
                        <th>接货成本</th>
                        <th>最大收益</th>
                        <th>年化收益</th>
                    </tr>
                </thead>
                <tbody>
"""
        for o in spreads:
            html += f"""
                    <tr>
                        <td>{o['expiry']}</td>
                        <td>{o['expiry_days']}天</td>
                        <td>{o['long_strike']:.2f}</td>
                        <td>{o['short_strike']:.2f}</td>
                        <td>{o['long_price']:.4f}</td>
                        <td>{o['short_price']:.4f}</td>
                        <td>{o['net_debit']:.4f}</td>
                        <td class="highlight">{o['delivery_cost']:.4f}</td>
                        <td>{o['max_profit']:.4f}</td>
                        <td class="highlight">{o['annualized']:.1f}%</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="no-opportunity">暂无符合条件的牛市价差机会</div>
"""
    html += """
        </div>
"""
    
    # 卖put
    html += """
        <div class="strategy-section">
            <h2>
                卖put
                <span class="badge">接货成本 &lt; ¥{:.2f}</span>
                <span class="badge">年化 ≥ {}%</span>
            </h2>
""".format(config['target_delivery_cost'], config['min_annual_put'])
    
    if puts:
        html += """
            <table class="opportunity-table">
                <thead>
                    <tr>
                        <th>到期日</th>
                        <th>剩余天数</th>
                        <th>行权价</th>
                        <th>权利金</th>
                        <th>接货成本</th>
                        <th>资金占用</th>
                        <th>年化收益</th>
                    </tr>
                </thead>
                <tbody>
"""
        for o in puts:
            html += f"""
                    <tr>
                        <td>{o['expiry']}</td>
                        <td>{o['expiry_days']}天</td>
                        <td>{o['strike']:.2f}</td>
                        <td>{o['put_price']:.4f}</td>
                        <td class="highlight">{o['delivery_cost']:.4f}</td>
                        <td>¥{o['capital_required']:,.0f}</td>
                        <td class="highlight">{o['annualized']:.1f}%</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="no-opportunity">暂无符合条件的卖put机会</div>
"""
    html += """
        </div>
"""
    
    # 卖covered call
    html += """
        <div class="strategy-section">
            <h2>
                卖covered call
                <span class="badge">年化 ≥ {}%</span>
            </h2>
""".format(config['min_annual_cc'])
    
    if not config['has_etf']:
        html += """
            <div class="no-opportunity">当前无持仓，无法卖covered call</div>
"""
    elif ccs:
        html += """
            <table class="opportunity-table">
                <thead>
                    <tr>
                        <th>到期日</th>
                        <th>剩余天数</th>
                        <th>行权价</th>
                        <th>权利金</th>
                        <th>持仓成本</th>
                        <th>资金占用</th>
                        <th>年化收益</th>
                    </tr>
                </thead>
                <tbody>
"""
        for o in ccs:
            html += f"""
                    <tr>
                        <td>{o['expiry']}</td>
                        <td>{o['expiry_days']}天</td>
                        <td>{o['strike']:.2f}</td>
                        <td>{o['call_price']:.4f}</td>
                        <td>{o['holding_cost']:.4f}</td>
                        <td>¥{o['capital_required']:,.0f}</td>
                        <td class="highlight">{o['annualized']:.1f}%</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="no-opportunity">暂无符合条件的卖covered call机会</div>
"""
    html += """
        </div>
"""
    
    html += f"""
        <div class="footer">
            数据源: 新浪财经 · 扫描时间: {timestamp}
        </div>
    </div>
</body>
</html>
"""
    return html

def save_opportunities_report(html_content, output_dir="reports"):
    """保存机会扫描报告"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 保存最新报告
    latest_path = output_path / "opportunities_latest.html"
    with open(latest_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # 保存带时间戳的报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_path = output_path / f"opportunities_{timestamp}.html"
    with open(timestamped_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return str(latest_path)

if __name__ == '__main__':
    # 测试
    print("机会扫描报告生成器模块加载成功")
