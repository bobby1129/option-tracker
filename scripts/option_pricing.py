"""
期权定价模块 - Black-Scholes模型
"""
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta

def black_scholes_call(S, K, T, r, sigma):
    """
    Black-Scholes看涨期权定价
    
    Args:
        S: 标的资产当前价格
        K: 行权价
        T: 到期时间（年）
        r: 无风险利率
        sigma: 波动率
    
    Returns:
        期权价格
    """
    if T <= 0:
        return max(0, S - K)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return call_price

def black_scholes_greeks(S, K, T, r, sigma):
    """
    计算期权Greeks
    
    Returns:
        dict: {'delta': float, 'gamma': float, 'theta': float, 'vega': float, 'rho': float}
    """
    if T <= 0:
        intrinsic = max(0, S - K)
        return {
            'delta': 1.0 if intrinsic > 0 else 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - 
             r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
    vega = S * norm.pdf(d1) * np.sqrt(T) / 100
    rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
    
    return {
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega,
        'rho': rho
    }

def estimate_historical_volatility(prices, window=30):
    """
    估算历史波动率
    
    Args:
        prices: 价格序列
        window: 窗口大小（天）
    
    Returns:
        年化波动率
    """
    if len(prices) < window:
        return 0.30  # 默认30%
    
    returns = np.diff(np.log(prices[-window:]))
    daily_vol = np.std(returns)
    annual_vol = daily_vol * np.sqrt(252)
    return annual_vol

def days_to_expiry(expiry_date):
    """计算到期天数"""
    today = datetime.now().date()
    expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
    return (expiry - today).days

def years_to_expiry(expiry_date):
    """计算到期年数"""
    days = days_to_expiry(expiry_date)
    return max(0, days / 365.0)
