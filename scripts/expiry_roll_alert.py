#!/usr/bin/env python3
"""
到期决策提示: 亏损卖Put(到期≤10天且实值) roll vs 接货卖同价位Call 对比
=======================================================================
机制 (2026-11-21 与用户确认):
  针对到期日在10天以内的实值(亏损)卖出put, 每天对比两条路径的净权利金:
  A) roll:   买平当月同价put(付ask) + 卖出下月同价put(收bid), 两腿手续费
  B) 接货卖call: 到期按K接货 + 卖出下月同价位call(收bid), 一腿手续费,
     扣利息成本(接货比roll提前ΔT天垫出K×份数的现金, r=2%)
  按可成交价(bid/ask)计算, 不用last/中间价。

  平价关系(put-call parity)决定两者长期趋近打平:
    roll credit ≈ C(下月) − C(当月) − K·r·ΔT
  差值来自点差/skew/利息, 提示语引导关注真实差异项: 资金占用、点差、手续费。
  (2026-11-21 实盘验证: 科创50 1.55P roll credit 0.0150 vs 12月1.55C 0.0144,
   BSM平值IV模型严重低估深虚值call — skew使实际C远高于模型值, 必须用实盘报价)

数据源:
  - data/positions.json  (open的short_put)
  - data/option_chain{suffix}_latest.json  (fetch_chain_sina.py产出, 只读缓存)
  行情缓存非当日 → 静默退出(cron先跑fetch_chain_sina, 非交易日不写缓存)

用法: python3 scripts/expiry_roll_alert.py [--days 10]
输出: stdout 文本块(无触发仓位时静默), 由日报cron附带给用户
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
FEE_PER_LOT = 7.0     # 元/手/腿 (用户实盘成本参考)
RISK_FREE = 0.02      # 年化无风险利率(利息项)
ALERT_DAYS = 10       # 到期前N天开始提示
# underlying代码 → 行情缓存文件后缀 (与fetch_chain_sina.py UNDERLYINGS一致)
CHAIN_SUFFIX = {"588000": "", "510050": "_510050"}
MULT = 10000          # 合约单位


def load_chain(underlying):
    suffix = CHAIN_SUFFIX.get(underlying)
    if suffix is None:
        return None
    path = DATA_DIR / f"option_chain{suffix}_latest.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cache_is_today(chain):
    """行情缓存必须是当日(cron先fetch后跑本脚本); 否则视为非交易时段, 静默"""
    ts = chain.get("timestamp", "")
    return ts[:10] == date.today().isoformat()


def find_short_puts(positions, horizon_days):
    """open 的裸卖put, 到期≤horizon_days天。返回[(pos, days_left), ...]"""
    today = date.today()
    out = []
    for pos in positions:
        if pos.get("status") != "open" or pos.get("type") != "short_put":
            continue
        try:
            expiry = date.fromisoformat(pos["expiry"])
        except (KeyError, ValueError):
            continue
        days_left = (expiry - today).days
        if days_left < 0 or days_left > horizon_days:
            continue
        out.append((pos, days_left))
    return out


def fmt_money(x):
    return f"{'+' if x >= 0 else '-'}¥{abs(x):,.0f}"


def build_alert(pos, days_left, chain):
    """单个仓位的对比块。返回文本或None(数据不全时)"""
    underlying = pos["underlying"]
    name = pos.get("underlying_name", underlying)
    strike = str(float(pos["strike"]))          # 归一化key, 与缓存一致
    lots = pos.get("lots", 1)
    cur_expiry = pos["expiry"]

    contracts = chain.get("contracts", {})
    expiries = sorted(contracts.keys())
    if cur_expiry not in contracts:
        return None
    nxt_list = [e for e in expiries if e > cur_expiry]
    if not nxt_list:
        return None
    nxt_expiry = nxt_list[0]

    etf_price = chain.get("etf_price")
    cur_put = contracts[cur_expiry].get("puts", {}).get(strike)
    nxt_put = contracts[nxt_expiry].get("puts", {}).get(strike)
    nxt_call = contracts[nxt_expiry].get("calls", {}).get(strike)
    cur_call = contracts[cur_expiry].get("calls", {}).get(strike)
    if not cur_put or not nxt_put or not nxt_call:
        return None

    # 只提示实值(亏损)卖put
    if etf_price is None or float(strike) <= etf_price:
        return None

    d1 = date.fromisoformat(cur_expiry)
    d2 = date.fromisoformat(nxt_expiry)
    delta_days = (d2 - d1).days

    n = lots * MULT
    # ---- 路径A: roll (买平当月ask, 卖出下月bid, 两腿手续费) ----
    roll_per = nxt_put["bid"] - cur_put["ask"]
    roll_fee = 2 * lots * FEE_PER_LOT
    roll_net = roll_per * n - roll_fee

    # ---- 路径B: 到期接货 + 卖下月同价call (收bid, 一腿手续费, 扣利息) ----
    call_per = nxt_call["bid"]
    call_fee = lots * FEE_PER_LOT
    interest = float(strike) * n * RISK_FREE * delta_days / 365.0
    cc_net = call_per * n - call_fee - interest

    # ---- 平价核对: 理论roll credit = C下月 − C当月 − 利息 ----
    parity = None
    if cur_call and cur_call.get("ask", 0) > 0:
        parity = (nxt_call["bid"] - cur_call["ask"]) * n - interest

    diff = roll_net - cc_net
    if abs(diff) < 100:
        verdict = "≈打平(平价关系使然), 决策看资金占用与点差"
    elif diff > 0:
        verdict = f"roll 多收 {fmt_money(diff)}"
    else:
        verdict = f"接货卖call 多收 {fmt_money(-diff)}"

    assign_cash = float(strike) * n
    lines = [
        f"⏰ #{pos['id']} {name} 卖Put {strike} ×{lots}手 | 到期{cur_expiry}(剩{days_left}天) "
        f"ETF={etf_price} 实值{float(strike) - etf_price:.3f}",
        f"   A) roll至{nxt_expiry}: 买平当月@{cur_put['ask']:.4f} + 卖出@{nxt_put['bid']:.4f} "
        f"→ 净 {fmt_money(roll_net)} (含两腿手续费¥{roll_fee:.0f}) | 占保证金(估)",
        f"   B) 接货+卖{nxt_expiry} {strike}C@{nxt_call['bid']:.4f} → 净 {fmt_money(cc_net)} "
        f"(扣手续费¥{call_fee:.0f}、利息¥{interest:.0f}) | 需现金 {assign_cash:,.0f}元",
        f"   → {verdict}",
    ]
    if parity is not None:
        lines.append(f"   平价核对: 理论roll≈{fmt_money(parity)}, 实际偏差{fmt_money(roll_net - parity)}来自点差/skew")
    return "\n".join(lines)


def main():
    days = ALERT_DAYS
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    pos_path = DATA_DIR / "positions.json"
    if not pos_path.exists():
        return
    with open(pos_path, encoding="utf-8") as f:
        positions = json.load(f).get("positions", [])

    candidates = find_short_puts(positions, days)
    if not candidates:
        return

    blocks = []
    stale = False
    for pos, days_left in candidates:
        chain = load_chain(pos["underlying"])
        if not chain:
            continue
        if not cache_is_today(chain):
            stale = True
            continue
        blk = build_alert(pos, days_left, chain)
        if blk:
            blocks.append(blk)

    if stale and not blocks:
        return  # 非交易日/缓存过期: 静默
    if blocks:
        print(f"═══ 到期决策提示 (实值卖Put ≤{days}天: roll vs 接货卖call) ═══")
        print("\n\n".join(blocks))
        print("\n注: 按盘口bid/ask可成交价计算; 平价关系下两路径长期趋近打平,")
        print("    真正的差异在资金占用(保证金 vs 全额接货现金)、点差宽度与是否愿意持有正股。")


if __name__ == "__main__":
    main()
