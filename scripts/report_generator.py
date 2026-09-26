"""
期权组合跟踪报告生成器 - 使用真实期权价格
"""
import json
from datetime import datetime
from pathlib import Path

def calculate_pnl(position):
    """
    计算组合盈亏
    """
    legs = position['legs']
    long_leg = legs['long']
    short_leg = legs['short']
    
    # 开仓成本
    open_debit = long_leg['open_price'] - short_leg['open_price']
    open_value = open_debit * position['lots'] * position['contract_multiplier']
    
    # 当前价值
    current_long = long_leg['current_price']
    current_short = short_leg['current_price']
    current_spread = current_long - current_short
    current_value = current_spread * position['lots'] * position['contract_multiplier']
    
    # 盈亏
    pnl = current_value - open_value
    pnl_pct = (pnl / open_value) * 100 if open_value > 0 else 0
    
    # 接货成本（如果ETF在long_strike和short_strike之间到期）
    delivery_cost = position['long_strike'] + open_debit
    
    # 最大收益（如果ETF >= short_strike到期）
    max_spread_value = position['short_strike'] - position['long_strike']
    max_profit = (max_spread_value - open_debit) * position['lots'] * position['contract_multiplier']
    
    # 剩余天数
    expiry = datetime.strptime(position['expiry'], '%Y-%m-%d')
    today = datetime.now()
    days_to_expiry = (expiry - today).days
    
    # 盈亏平衡
    breakeven = position['long_strike'] + open_debit
    
    # 安全距离（距离盈亏平衡的百分比）
    etf_price = position['current_prices']['underlying']
    safety_margin = (etf_price - breakeven) / etf_price * 100
    
    # 年化收益率（基于当前浮盈）
    if days_to_expiry > 0 and open_value > 0:
        annualized_return = (pnl / open_value) * (365 / days_to_expiry) * 100
    else:
        annualized_return = 0
    
    # 盈利里程碑
    profit_milestones = []
    if max_profit > 0:
        profit_ratio = pnl / max_profit
        if profit_ratio >= 0.5:
            profit_milestones.append(f"✅ 已达最大盈利的50%以上（{profit_ratio*100:.0f}%）")
        elif profit_ratio >= 0.33:
            profit_milestones.append(f"✅ 已达最大盈利的33%以上（{profit_ratio*100:.0f}%）")
    
    # 状态判断
    if etf_price >= position['short_strike']:
        status = f"✅ 已达最大盈利区(ETF≥{position['short_strike']})"
    elif etf_price >= position['long_strike']:
        status = f"⚠️ 接货区({position['long_strike']}≤ETF<{position['short_strike']})"
    else:
        status = f"❌ 亏损区(ETF<{position['long_strike']})"
    
    return {
        'open_value': open_value,
        'current_value': current_value,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'delivery_cost': delivery_cost,
        'max_profit': max_profit,
        'days_to_expiry': days_to_expiry,
        'breakeven': breakeven,
        'safety_margin': safety_margin,
        'annualized_return': annualized_return,
        'profit_milestones': profit_milestones,
        'status': status
    }

def generate_suggestion(analysis, position):
    """生成操作建议"""
    days = analysis['days_to_expiry']
    pnl_pct = analysis['pnl_pct']
    safety_margin = analysis['safety_margin']
    max_profit = analysis['max_profit']
    pnl = analysis['pnl']
    etf_price = position['current_prices']['underlying']
    
    suggestions = []
    
    # 盈利里程碑建议
    if max_profit > 0:
        profit_ratio = pnl / max_profit
        if profit_ratio >= 0.5:
            if days <= 14:
                suggestions.append(f"🎯 已达最大盈利{profit_ratio*100:.0f}%，距到期仅{days}天，建议继续持有锁定收益")
            elif safety_margin >= 10:
                suggestions.append(f"🎯 已达最大盈利{profit_ratio*100:.0f}%，安全距离{safety_margin:.1f}%，建议继续持有")
            else:
                suggestions.append(f"🎯 已达最大盈利{profit_ratio*100:.0f}%，但安全距离仅{safety_margin:.1f}%，可考虑部分平仓锁定利润")
        elif profit_ratio >= 0.33:
            if days <= 7:
                suggestions.append(f"📈 已达最大盈利{profit_ratio*100:.0f}%，临近到期，建议持有至到期")
            elif safety_margin >= 15:
                suggestions.append(f"📈 已达最大盈利{profit_ratio*100:.0f}%，安全距离充足，建议继续持有")
            else:
                suggestions.append(f"📈 已达最大盈利{profit_ratio*100:.0f}%，可观察几日再决定")
    
    # 时间衰减提醒
    if days <= 7:
        suggestions.append(f"⏰ 距到期仅{days}天，时间价值衰减加速")
    elif days <= 14:
        suggestions.append(f"⏰ 距到期{days}天，关注ETF走势")
    
    # 安全距离提醒
    if safety_margin < 5 and safety_margin > 0:
        suggestions.append(f"⚠️ 安全距离仅{safety_margin:.1f}%，接近盈亏平衡点")
    elif safety_margin < 0:
        suggestions.append(f"❌ 已跌破盈亏平衡点{analysis['breakeven']:.4f}")
    
    # 亏损提醒
    if pnl_pct <= -10:
        suggestions.append(f"📉 浮亏{abs(pnl_pct):.1f}%，评估是否止损或调整策略")
    
    # 默认建议
    if not suggestions:
        if pnl_pct > 0:
            suggestions.append(f"📊 当前浮盈{pnl_pct:.1f}%，建议继续持有，定期跟踪")
        else:
            suggestions.append(f"📊 当前状态正常，建议继续持有，定期跟踪")
    
    return suggestions

def generate_html_report(positions_data):
    """生成HTML报告"""
    timestamp = positions_data['positions'][0]['current_prices']['update_time']
    etf_price = positions_data['positions'][0]['current_prices']['underlying']
    
    # 计算每个组合的盈亏
    analyses = []
    total_open = 0
    total_current = 0
    total_pnl = 0
    
    for pos in positions_data['positions']:
        if pos['status'] == 'open':
            analysis = calculate_pnl(pos)
            analysis['position'] = pos
            analyses.append(analysis)
            total_open += analysis['open_value']
            total_current += analysis['current_value']
            total_pnl += analysis['pnl']
    
    # 按到期日汇总接货额度 (行权买入正股所需现金, 不含已付权利金)
    # 价差: S到期落在[K1,K2)时行权K1腿接货, 需 K1×lots×multiplier
    delivery_by_expiry = {}
    for a in analyses:
        pos = a['position']
        if pos['type'] == 'bull_call_spread':
            cash_needed = pos['long_strike'] * pos['lots'] * pos['contract_multiplier']
            entry = delivery_by_expiry.setdefault(pos['expiry'], {'cash': 0, 'positions': []})
            entry['cash'] += cash_needed
            entry['positions'].append(f"{pos['long_strike']}/{pos['short_strike']}×{pos['lots']}组")
    
    delivery_rows = ""
    delivery_total = 0
    for expiry in sorted(delivery_by_expiry):
        e = delivery_by_expiry[expiry]
        delivery_total += e['cash']
        delivery_rows += f"""
            <tr>
                <td>{expiry}</td>
                <td>{', '.join(e['positions'])}</td>
                <td class="highlight">¥{e['cash']:,.0f}</td>
            </tr>"""
    if delivery_rows:
        delivery_rows += f"""
            <tr>
                <td><b>合计</b></td>
                <td></td>
                <td class="highlight"><b>¥{delivery_total:,.0f}</b></td>
            </tr>"""
    
    # 生成HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>期权组合跟踪报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        
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
        }}
        .summary-card .value.profit {{ color: #4ade80; }}
        .summary-card .value.loss {{ color: #f87171; }}
        .summary-card .value.neutral {{ color: #fbbf24; }}
        
        .position-card {{
            background: rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,215,0,0.15);
        }}
        .position-card h2 {{
            color: #ffd700;
            font-size: 20px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .position-card h2 .badge {{
            background: rgba(255,215,0,0.2);
            color: #ffd700;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
        }}
        
        .legs-section {{
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        .legs-section h3 {{
            color: #aaa;
            font-size: 14px;
            margin-bottom: 12px;
        }}
        .legs-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .legs-table th {{
            background: rgba(255,215,0,0.1);
            color: #ffd700;
            padding: 10px;
            text-align: left;
            font-weight: 600;
        }}
        .legs-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .legs-table .direction-buy {{ color: #4ade80; }}
        .legs-table .direction-sell {{ color: #f87171; }}
        .legs-table .price-change {{ font-size: 11px; margin-left: 5px; }}
        .legs-table .price-up {{ color: #4ade80; }}
        .legs-table .price-down {{ color: #f87171; }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }}
        .metric {{
            background: rgba(0,0,0,0.3);
            padding: 12px;
            border-radius: 8px;
        }}
        .metric .label {{
            color: #888;
            font-size: 11px;
            margin-bottom: 4px;
        }}
        .metric .value {{
            font-size: 16px;
            font-weight: 600;
        }}
        
        .milestones {{
            background: rgba(74,222,128,0.1);
            border: 1px solid rgba(74,222,128,0.3);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 15px;
        }}
        .milestones .milestone-item {{
            color: #4ade80;
            font-size: 13px;
            margin-bottom: 4px;
        }}
        .milestones .milestone-item:last-child {{
            margin-bottom: 0;
        }}
        
        .suggestions {{
            background: rgba(251,191,36,0.1);
            border: 1px solid rgba(251,191,36,0.3);
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }}
        .suggestions h4 {{
            color: #fbbf24;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .suggestions .suggestion-item {{
            font-size: 13px;
            margin-bottom: 6px;
            color: #e0e0e0;
        }}
        .suggestions .suggestion-item:last-child {{
            margin-bottom: 0;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 12px;
        }}

        .delivery-section {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 20px;
        }}
        .delivery-section h3 {{
            font-size: 15px;
            color: #e0e0e0;
            margin-bottom: 12px;
        }}
        .delivery-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .delivery-table th {{
            text-align: left;
            color: #aaa;
            font-weight: normal;
            padding: 6px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .delivery-table td {{
            padding: 8px 10px;
            color: #e0e0e0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .delivery-table .highlight {{
            color: #fbbf24;
            font-weight: bold;
        }}
        .delivery-note {{
            margin-top: 10px;
            font-size: 12px;
            color: #888;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏠 期权组合跟踪报告</h1>
            <div class="subtitle">科创50ETF (588000) · 牛市看涨价差</div>
            <div class="etf-price">¥{etf_price:.3f}</div>
            <div class="update-time">更新时间: {timestamp}</div>
        </div>
        
        <div class="summary-grid">
            <div class="summary-card">
                <div class="label">总投入</div>
                <div class="value neutral">¥{total_open:,.0f}</div>
            </div>
            <div class="summary-card">
                <div class="label">当前价值</div>
                <div class="value neutral">¥{total_current:,.0f}</div>
            </div>
            <div class="summary-card">
                <div class="label">浮动盈亏</div>
                <div class="value {'profit' if total_pnl >= 0 else 'loss'}">
                    {'+' if total_pnl >= 0 else ''}¥{total_pnl:,.0f}
                </div>
            </div>
        </div>

        <div class="delivery-section">
            <h3>💰 接货额度提示（按到期日，行权买入正股所需现金）</h3>
            <table class="delivery-table">
                <thead>
                    <tr><th>到期日</th><th>持仓</th><th>需备现金</th></tr>
                </thead>
                <tbody>{delivery_rows}
                </tbody>
            </table>
            <div class="delivery-note">额度上限由人工判断，此处仅提示各到期日若被指派/主动行权接货所需准备的现金</div>
        </div>
"""
    
    for a in analyses:
        pos = a['position']
        pnl_class = 'profit' if a['pnl'] >= 0 else 'loss'
        
        # 生成建议
        suggestions = generate_suggestion(a, pos)
        
        # 计算每条腿的价格变化
        long_leg = pos['legs']['long']
        short_leg = pos['legs']['short']
        long_change = ((long_leg['current_price'] - long_leg['open_price']) / long_leg['open_price']) * 100
        short_change = ((short_leg['current_price'] - short_leg['open_price']) / short_leg['open_price']) * 100
        
        html += f"""
        <div class="position-card">
            <h2>
                组合 #{pos['id']}
                <span class="badge">{pos['long_strike']}/{pos['short_strike']} 价差</span>
                <span class="badge">剩{a['days_to_expiry']}天</span>
            </h2>
            
            <div class="legs-section">
                <h3>持仓明细</h3>
                <table class="legs-table">
                    <thead>
                        <tr>
                            <th>方向</th>
                            <th>行权价</th>
                            <th>开仓价</th>
                            <th>当前价</th>
                            <th>变化</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="direction-buy">买入</td>
                            <td>{long_leg['strike']:.2f}</td>
                            <td>{long_leg['open_price']:.4f}</td>
                            <td>{long_leg['current_price']:.4f}</td>
                            <td>
                                <span class="price-change {'price-up' if long_change >= 0 else 'price-down'}">
                                    {'+' if long_change >= 0 else ''}{long_change:.1f}%
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <td class="direction-sell">卖出</td>
                            <td>{short_leg['strike']:.2f}</td>
                            <td>{short_leg['open_price']:.4f}</td>
                            <td>{short_leg['current_price']:.4f}</td>
                            <td>
                                <span class="price-change {'price-up' if short_change >= 0 else 'price-down'}">
                                    {'+' if short_change >= 0 else ''}{short_change:.1f}%
                                </span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="metrics-grid">
                <div class="metric">
                    <div class="label">开仓净支出</div>
                    <div class="value">¥{a['open_value']:,.0f}</div>
                </div>
                <div class="metric">
                    <div class="label">当前价值</div>
                    <div class="value">¥{a['current_value']:,.0f}</div>
                </div>
                <div class="metric">
                    <div class="label">浮动盈亏</div>
                    <div class="value {pnl_class}">{'+' if a['pnl'] >= 0 else ''}¥{a['pnl']:,.0f} ({a['pnl_pct']:+.1f}%)</div>
                </div>
                <div class="metric">
                    <div class="label">接货成本</div>
                    <div class="value">¥{a['delivery_cost']:.4f}</div>
                </div>
                <div class="metric">
                    <div class="label">盈亏平衡</div>
                    <div class="value">¥{a['breakeven']:.4f}</div>
                </div>
                <div class="metric">
                    <div class="label">安全距离</div>
                    <div class="value {'profit' if a['safety_margin'] >= 5 else 'loss' if a['safety_margin'] < 0 else 'neutral'}">{a['safety_margin']:+.1f}%</div>
                </div>
                <div class="metric">
                    <div class="label">最大收益</div>
                    <div class="value profit">¥{a['max_profit']:,.0f}</div>
                </div>
                <div class="metric">
                    <div class="label">年化收益率</div>
                    <div class="value {pnl_class}">{a['annualized_return']:+.1f}%</div>
                </div>
            </div>
"""
        
        # 盈利里程碑
        if a['profit_milestones']:
            html += """
            <div class="milestones">
"""
            for milestone in a['profit_milestones']:
                html += f"""                <div class="milestone-item">{milestone}</div>
"""
            html += """            </div>
"""
        
        # 操作建议
        html += f"""
            <div class="suggestions">
                <h4>💡 操作建议</h4>
"""
        for suggestion in suggestions:
            html += f"""                <div class="suggestion-item">{suggestion}</div>
"""
        html += """            </div>
        </div>
"""
    
    html += f"""
        <div class="footer">
            数据源: 新浪财经 · 更新时间: {timestamp}
        </div>
    </div>
</body>
</html>
"""
    return html

def run_analysis():
    """运行分析并生成报告"""
    # 加载持仓数据
    data_dir = Path(__file__).parent.parent / 'data'
    with open(data_dir / 'positions.json', 'r') as f:
        positions_data = json.load(f)
    
    # 生成HTML报告
    html = generate_html_report(positions_data)
    
    # 保存报告
    reports_dir = Path(__file__).parent.parent / 'reports'
    reports_dir.mkdir(exist_ok=True)
    
    report_path = reports_dir / 'latest.html'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    # 打印摘要
    etf_price = positions_data['positions'][0]['current_prices']['underlying']
    print(f"ETF价格: {etf_price}")
    print(f"报告已生成: {report_path}")
    print()
    
    total_pnl = 0
    for pos in positions_data['positions']:
        if pos['status'] == 'open':
            analysis = calculate_pnl(pos)
            print(f"组合#{pos['id']} ({pos['long_strike']}/{pos['short_strike']}, 剩{analysis['days_to_expiry']}天):")
            print(f"  开仓: ¥{analysis['open_value']:,.0f}, 当前: ¥{analysis['current_value']:,.0f}")
            print(f"  浮盈: {'+' if analysis['pnl'] >= 0 else ''}¥{analysis['pnl']:,.0f} ({analysis['pnl_pct']:+.1f}%)")
            print(f"  接货成本: {analysis['delivery_cost']:.4f}, 盈亏平衡: {analysis['breakeven']:.4f}")
            print(f"  安全距离: {analysis['safety_margin']:+.1f}%, 年化: {analysis['annualized_return']:+.1f}%")
            print(f"  状态: {analysis['status']}")
            if analysis['profit_milestones']:
                for m in analysis['profit_milestones']:
                    print(f"  {m}")
            print()
            total_pnl += analysis['pnl']
    
    print(f"总浮盈: {'+' if total_pnl >= 0 else ''}¥{total_pnl:,.0f}")
    
    # 接货额度提示 (按到期日)
    delivery_by_expiry = {}
    for pos in positions_data['positions']:
        if pos['status'] == 'open' and pos['type'] == 'bull_call_spread':
            cash = pos['long_strike'] * pos['lots'] * pos['contract_multiplier']
            entry = delivery_by_expiry.setdefault(pos['expiry'], {'cash': 0, 'positions': []})
            entry['cash'] += cash
            entry['positions'].append(f"{pos['long_strike']}/{pos['short_strike']}×{pos['lots']}组")
    if delivery_by_expiry:
        print()
        print("💰 接货额度提示 (行权买入正股所需现金, 上限人工判断):")
        total_cash = 0
        for expiry in sorted(delivery_by_expiry):
            e = delivery_by_expiry[expiry]
            total_cash += e['cash']
            print(f"  {expiry}: ¥{e['cash']:,.0f}  ({', '.join(e['positions'])})")
        print(f"  合计: ¥{total_cash:,.0f}")
    
    return str(report_path)

if __name__ == "__main__":
    run_analysis()
