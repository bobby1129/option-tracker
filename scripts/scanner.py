#!/usr/bin/env python3
"""
机会扫描器 - 读取期权链数据，扫描符合条件的开仓机会
"""
import json
from datetime import datetime
from pathlib import Path

def load_data():
    data_dir = Path(__file__).parent.parent / 'data'
    chains = {}
    with open(data_dir / 'option_chain_latest.json') as f:
        chains['588000'] = json.load(f)
    p50 = data_dir / 'option_chain_510050_latest.json'
    if p50.exists():
        with open(p50) as f:
            chains['510050'] = json.load(f)
    with open(data_dir / 'positions.json') as f:
        config_data = json.load(f)
    return chains, config_data

def scan_bull_call_spreads(chain, target_cost, min_annual, max_time_value=0.01, min_days=10):
    """扫描牛市价差机会
    max_time_value: 买腿允许的最大时间价值（每份），深实值call按平价关系必有
    正时间价值（=同行权价put的时间价值），硬要求≤内在价值在真实盘口下永远不通过。
    时间价值会在租金公式中被自动扣除（租金=卖腿权利金-买腿时间价值），太大则年化不达标。
    """
    etf_price = chain['etf_price']
    opportunities = []
    
    for expiry, contract in chain['contracts'].items():
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        days = (expiry_date - datetime.now()).days
        if days <= min_days:
            continue
        
        calls = contract['calls']
        strikes = sorted([float(s) for s in calls.keys()])
        
        for i, long_s in enumerate(strikes):
            for short_s in strikes[i+1:]:
                long_data = calls[str(long_s)]
                short_data = calls[str(short_s)]
                # 盘口价：买腿用ask、卖腿用bid（真实成交方向），无盘口退回last
                long_price = long_data.get('ask') or long_data.get('last')
                short_price = short_data.get('bid') or short_data.get('last')
                
                if long_price is None or short_price is None:
                    continue
                
                # 买入腿必须深度实值且时间价值≤容差（时间价值在租金中自动扣除）
                intrinsic = etf_price - long_s
                if intrinsic <= 0:
                    continue  # 虚值，跳过
                time_value = long_price - intrinsic
                if time_value < 0 or time_value > max_time_value:
                    continue  # 负时间价值=盘口异常；超容差=不够"深"实值
                
                # 卖出腿必须虚值（大于现价），从最大收益出发
                if short_s <= etf_price:
                    continue
                
                net_debit = long_price - short_price
                if net_debit <= 0:
                    continue
                
                delivery_cost = long_s + net_debit
                if delivery_cost >= target_cost:
                    continue
                
                # 租金 = 卖腿权利金 - 买腿时间价值 = 现价 - 接货成本
                # （ETF到期横盘不动也能赚到的钱，不含方向钱）
                rent = etf_price - delivery_cost
                if rent <= 0:
                    continue
                
                max_profit = (short_s - long_s) - net_debit
                if max_profit <= 0:
                    continue
                
                # 年化只按租金算（分母=净权利金支出）；最大收益含宽度方向钱，单独展示
                annual = (rent / net_debit) * (365 / days) * 100
                if annual < min_annual:
                    continue
                
                opportunities.append({
                    'strategy': '牛市价差',
                    'expiry': expiry,
                    'days': days,
                    'long_strike': long_s,
                    'short_strike': short_s,
                    'long_price': long_price,
                    'short_price': short_price,
                    'intrinsic': intrinsic,
                    'time_value': long_price - intrinsic,
                    'net_debit': net_debit,
                    'delivery_cost': delivery_cost,
                    'rent': rent,
                    'max_profit': max_profit,
                    'annual': annual,
                    'capital': net_debit * 10000
                })
    
    return opportunities

def scan_sell_puts(chain, target_cost, min_annual, min_days=10):
    """扫描卖put机会"""
    etf_price = chain['etf_price']
    opportunities = []
    
    for expiry, contract in chain['contracts'].items():
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        days = (expiry_date - datetime.now()).days
        if days <= min_days:
            continue
        
        puts = contract['puts']
        
        for strike_str, put_data in puts.items():
            strike = float(strike_str)
            put_price = put_data['last']
            
            if put_price is None or put_price <= 0:
                continue
            
            # 卖出腿必须虚值（行权价 < 现价）
            if strike >= etf_price:
                continue
            
            delivery_cost = strike - put_price
            if delivery_cost >= target_cost:
                continue
            
            # 资金占用 = ETF价格 × 15% × 10000
            capital = etf_price * 0.15 * 10000
            # 年化 = (权利金收入 / 资金占用) × 365/天数
            income = put_price * 10000
            annual = (income / capital) * (365 / days) * 100
            
            if annual < min_annual:
                continue
            
            opportunities.append({
                'strategy': '卖put',
                'expiry': expiry,
                'days': days,
                'strike': strike,
                'put_price': put_price,
                'delivery_cost': delivery_cost,
                'annual': annual,
                'capital': capital,
                'income': income
            })
    
    return opportunities

def scan_covered_calls(chain, min_annual, holding, min_days=10):
    """扫描卖covered call机会(单批次独立扫描, 不与其他批次合并)
    holding: {"shares": 30000, "cost": 3.03, "cc_breakeven": 2.8745, ...} 正股持仓批次
    硬红线: 行权价 ≥ cc_breakeven(该批次盈亏平衡) — 被行权也确保这笔赚钱(用户2026-10-30要求);
    cc_breakeven 缺省退回 cost。盈亏平衡口径: 接货价-已收权利金; 市价买入批次摊入对应组合净盈亏
    """
    if not holding or not chain:
        return []
    etf_price = chain['etf_price']
    max_lots = int(holding.get('shares', 0)) // 10000
    if max_lots <= 0:
        return []

    breakeven = holding.get('cc_breakeven') or holding.get('cost')
    opportunities = []

    for expiry, contract in chain['contracts'].items():
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        days = (expiry_date - datetime.now()).days
        if days <= min_days:
            continue

        calls = contract['calls']

        for strike_str, call_data in calls.items():
            strike = float(strike_str)
            # 卖出腿用bid(真实成交方向), 无bid退回last
            call_price = call_data.get('bid') or call_data.get('last')

            if call_price is None or call_price <= 0:
                continue

            # 只卖虚值/平值 call: 行权价低于现价的部分是内在价值, 不是租金,
            # 且会立即锁定正股市价亏损
            if strike < etf_price:
                continue

            # 硬红线: 行权价 ≥ 该批次盈亏平衡 — 被行权这笔也锁定赚钱
            if breakeven and strike < breakeven:
                continue

            # 资金占用 = ETF价格 × 10000 (每手, 正股已持有)
            capital = etf_price * 10000
            income = call_price * 10000
            annual = (income / capital) * (365 / days) * 100

            if annual < min_annual:
                continue

            opportunities.append({
                'strategy': '卖covered call',
                'expiry': expiry,
                'days': days,
                'strike': strike,
                'call_price': call_price,
                'annual': annual,
                'capital': capital,
                'income': income,
                'max_lots': max_lots,
                'total_income': income * max_lots,
                'etf_cost': holding.get('cost'),
                'breakeven': breakeven,
                'batch': holding.get('batch_label', ''),
            })

    return opportunities

def generate_report(spreads, puts, ccs, chain, config):
    """生成HTML报告"""
    etf_price = chain['etf_price']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
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
        .header .subtitle {{ color: #aaa; font-size: 14px; }}
        .header .etf-price {{
            font-size: 42px;
            font-weight: bold;
            color: #ffd700;
            margin: 15px 0;
        }}
        .header .update-time {{ color: #888; font-size: 12px; }}
        
        .config-box {{
            background: rgba(255,255,255,0.06);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 13px;
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .config-item {{ color: #aaa; }}
        .config-value {{ color: #ffd700; font-weight: 600; }}
        
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
        .summary-card .label {{ color: #aaa; font-size: 12px; margin-bottom: 8px; }}
        .summary-card .value {{ font-size: 24px; font-weight: bold; color: #4ade80; }}
        
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
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: rgba(255,215,0,0.1);
            color: #ffd700;
            padding: 10px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .highlight {{ color: #4ade80; font-weight: 600; }}
        
        .no-opportunity {{
            text-align: center;
            padding: 40px;
            color: #888;
        }}
        
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .card {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 215, 0, 0.3);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .card-header {{
            background: rgba(255, 215, 0, 0.1);
            padding: 10px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .card-title {{
            color: #ffd700;
            font-weight: 600;
            font-size: 14px;
        }}
        
        .card-badge {{
            background: #4ade80;
            color: #000;
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 13px;
        }}
        
        .card-body {{
            padding: 15px;
        }}
        
        .card-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        .card-row:last-child {{
            border-bottom: none;
        }}
        
        .card-label {{
            color: #888;
            font-size: 13px;
        }}
        
        .card-value {{
            color: #e0e0e0;
            font-weight: 500;
            font-size: 13px;
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
            <div class="subtitle">科创50ETF (588000)</div>
            <div class="etf-price">¥{etf_price:.3f}</div>
            <div class="update-time">扫描时间: {timestamp}</div>
        </div>
        
        <div class="config-box">
            <div class="config-item">目标接货成本: <span class="config-value">¥{config['target_delivery_cost']:.2f}</span></div>
            <div class="config-item">价差/卖put门槛: <span class="config-value">≥{config['min_annual_spread']}%</span></div>
            <div class="config-item">covered call门槛: <span class="config-value">≥{config['min_annual_cc']}%</span></div>
            <div class="config-item">剩余天数过滤: <span class="config-value">≤{config.get('min_scan_days', 10)}天忽略(年化虚高)</span></div>
            <div class="config-item">持仓状态: <span class="config-value">{'有货' if config['has_etf'] else '无货'}</span></div>
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
    html += f"""
        <div class="strategy-section">
            <h2>📈 牛市价差（接货成本 &lt; ¥{config['target_delivery_cost']:.2f}，年化 ≥ {config['min_annual_spread']}%）</h2>
"""
    if spreads:
        html += '<div class="cards-grid">'
        for o in spreads:
            html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="card-title">{o['expiry']}（{o['days']}天）</span>
                    <span class="card-badge">{o['annual']:.1f}%</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">买入腿</span>
                        <span class="card-value">{o['long_strike']:.2f} @ {o['long_price']:.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">卖出腿</span>
                        <span class="card-value">{o['short_strike']:.2f} @ {o['short_price']:.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">净支出</span>
                        <span class="card-value">{o['net_debit']:.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">接货成本</span>
                        <span class="card-value highlight">¥{o['delivery_cost']:.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">租金(横盘收益)</span>
                        <span class="card-value">{o['rent']:.4f}/张</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">最大收益(含方向钱)</span>
                        <span class="card-value">¥{o['max_profit']:.4f}/张</span>
                    </div>
                </div>
            </div>
"""
        html += '</div>'
    else:
        html += """
            <div class="no-opportunity">暂无符合条件的牛市价差机会</div>
"""
    html += """
        </div>
"""
    
    # 卖put
    html += f"""
        <div class="strategy-section">
            <h2>📉 卖put（接货成本 &lt; ¥{config['target_delivery_cost']:.2f}，年化 ≥ {config['min_annual_spread']}%）</h2>
"""
    if puts:
        html += '<div class="cards-grid">'
        for o in puts:
            html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="card-title">{o['expiry']}（{o['days']}天）</span>
                    <span class="card-badge">{o['annual']:.1f}%</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">行权价</span>
                        <span class="card-value">{o['strike']:.2f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">权利金</span>
                        <span class="card-value">{o['put_price']:.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">接货成本</span>
                        <span class="card-value highlight">¥{o['delivery_cost']:.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">资金占用</span>
                        <span class="card-value">¥{o['capital']:,.0f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">权利金收入</span>
                        <span class="card-value">¥{o['income']:,.0f}</span>
                    </div>
                </div>
            </div>
"""
        html += '</div>'
    else:
        html += """
            <div class="no-opportunity">暂无符合条件的卖put机会</div>
"""
    html += """
        </div>
"""
    
    # 卖covered call
    html += f"""
        <div class="strategy-section">
            <h2>📊 卖covered call（年化 ≥ {config['min_annual_cc']}%）</h2>
"""
    cc_batches = config.get('cc_batches', [])
    if not cc_batches:
        html += """
            <div class="no-opportunity">当前无正股持仓，无法卖covered call</div>
"""
    else:
        batch_desc = '<br>'.join(
            f"{b['batch_label']} · 可卖{b['shares']//10000}手 · 行权价红线≥{b.get('cc_breakeven', b.get('cost'))}"
            for b in cc_batches
        )
        html += f"""
            <div class="no-opportunity" style="color:#aaa;">正股持仓（按批次独立扫描）：<br>{batch_desc}</div>
"""
    if ccs:
        html += '<div class="cards-grid">'
        for o in ccs:
            html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="card-title">{o.get('underlying_name','')} {o['expiry']}（{o['days']}天）</span>
                    <span class="card-badge">{o['annual']:.1f}%</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">持仓批次</span>
                        <span class="card-value">{o.get('batch','')}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">行权价</span>
                        <span class="card-value">{o['strike']:.2f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">批次盈亏平衡</span>
                        <span class="card-value">{o.get('breakeven'):.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">权利金(bid)</span>
                        <span class="card-value">{o['call_price']:.4f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">可卖手数</span>
                        <span class="card-value">{o['max_lots']}手</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">权利金总收入</span>
                        <span class="card-value highlight">¥{o['total_income']:,.0f}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">每手资金占用</span>
                        <span class="card-value">¥{o['capital']:,.0f}</span>
                    </div>
                </div>
            </div>
"""
        html += '</div>'
    elif cc_batches:
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

def main():
    chains, config_data = load_data()
    chain = chains.get('588000')  # 价差/卖put 仍只扫科创50

    # 扫描配置 (门槛从positions.json targets读取, 单位: 年化%)
    target_cost = config_data['targets']['max_cost']
    min_annual_spread = config_data['targets'].get('min_annual_spread', 100)
    min_annual_cc = config_data['targets'].get('min_annual_cc', 15)
    max_tv_spread = config_data['targets'].get('max_tv_spread', 0.01)
    # 剩余天数过滤: 到期日太近的合约年化虚高(权利金/极少天数), 直接忽略(2026-10-30用户要求)
    min_days = config_data['targets'].get('min_scan_days', 10)
    cc_holdings = config_data['targets'].get('cc_holdings', {})

    # 构建covered call扫描批次: 同标的也按批次分开扫, 各批用自己的盈亏平衡做行权价红线
    # (cc_holdings老仓 + stock_holdings每笔接货/买入, 2026-10-30用户要求)
    cc_batches = []
    for code, h in cc_holdings.items():
        cc_batches.append({
            'underlying': code, 'name': h.get('name', code),
            'shares': h.get('shares', 0), 'cost': h.get('cost'),
            'cc_breakeven': h.get('cc_breakeven', h.get('cost')),
            'batch_label': f"{h.get('name', code)} 老仓{h.get('shares',0):,}股(成本{h.get('cost')})",
        })
    for h in config_data.get('stock_holdings', []):
        if int(h.get('shares', 0)) // 10000 <= 0:
            continue
        src = '行权接货' if h.get('source') == 'exercise' else '市价买入'
        cc_batches.append({
            'underlying': h['underlying'], 'name': h.get('underlying_name', h['underlying']),
            'shares': h['shares'], 'cost': h.get('cost'),
            'cc_breakeven': h.get('cc_breakeven', h.get('cost')),
            'batch_label': f"{h.get('underlying_name','')} {src}{h['shares']:,}股({h.get('open_date','')} 平衡{h.get('cc_breakeven', h.get('cost'))})",
        })

    config = {
        'target_delivery_cost': target_cost,
        'min_annual_spread': min_annual_spread,
        'min_annual_put': min_annual_spread,
        'min_annual_cc': min_annual_cc,
        'min_scan_days': min_days,
        'has_etf': bool(cc_batches),
        'cc_holdings': cc_holdings,
        'cc_batches': cc_batches,
    }

    # 扫描三种策略
    spreads = scan_bull_call_spreads(chain, target_cost, min_annual_spread, max_tv_spread, min_days)
    puts = scan_sell_puts(chain, target_cost, min_annual_spread, min_days)
    ccs = []
    for batch in cc_batches:
        opts = scan_covered_calls(chains.get(batch['underlying']), min_annual_cc, batch, min_days)
        for o in opts:
            o['underlying'] = batch['underlying']
            o['underlying_name'] = batch['name']
        ccs.extend(opts)

    # 按年化排序
    spreads.sort(key=lambda x: x['annual'], reverse=True)
    puts.sort(key=lambda x: x['annual'], reverse=True)
    ccs.sort(key=lambda x: x['annual'], reverse=True)

    # 生成报告
    html = generate_report(spreads, puts, ccs, chain, config)

    # 保存报告
    reports_dir = Path(__file__).parent.parent / 'reports'
    reports_dir.mkdir(exist_ok=True)

    with open(reports_dir / 'opportunities.html', 'w', encoding='utf-8') as f:
        f.write(html)

    # 打印摘要
    print(f"ETF价格: {chain['etf_price']}")
    print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标接货成本: < ¥{target_cost}")
    print(f"牛市价差机会: {len(spreads)} 个")
    print(f"卖put机会: {len(puts)} 个")
    print(f"卖covered call机会: {len(ccs)} 个")
    print()

    if spreads:
        print("Top 5 牛市价差:")
        for o in spreads[:5]:
            print(f"  {o['expiry']} {o['long_strike']}/{o['short_strike']} "
                  f"净支出={o['net_debit']:.4f} 接货={o['delivery_cost']:.4f} "
                  f"租金={o['rent']:.4f} 年化={o['annual']:.1f}% "
                  f"最大收益={o['max_profit']:.4f}/张")

    if puts:
        print("\nTop 5 卖put:")
        for o in puts[:5]:
            print(f"  {o['expiry']} 行权价={o['strike']:.2f} "
                  f"权利金={o['put_price']:.4f} 接货={o['delivery_cost']:.4f} "
                  f"年化={o['annual']:.1f}%")

    if ccs:
        print("\nTop 5 卖covered call:")
        for o in ccs[:5]:
            print(f"  [{o.get('batch','')}] {o['expiry']} 行权价={o['strike']:.2f} "
                  f"权利金={o['call_price']:.4f} 年化={o['annual']:.1f}% "
                  f"(最多{o['max_lots']}手, 总收入¥{o['total_income']:,.0f})")

    print(f"\n报告已保存: {reports_dir / 'opportunities.html'}")

if __name__ == '__main__':
    main()
