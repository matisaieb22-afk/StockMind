# -*- coding: utf-8 -*-
"""
StockMind Terminal v2 - Full Paper Trading and Market Intelligence Platform
"""
import json
import asyncio
import os
import io
import base64
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf
from nicegui import ui, run

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd(), 'stockmind_data.json')

def save_state():
    """Persist all user state to disk."""
    try:
        data = {
            'watchlist': WATCHLIST,
            'profile': profile,
            'settings': settings,
            'account': account,
            'state_ticker': state.get('ticker', 'AAPL'),
            'state_period': state.get('period', '3mo'),
            'state_chart_type': state.get('chart_type', 'candles'),
            'chat_log': chat_log[-50:],  # keep last 50 messages
        }
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print('Save error:', e)

def load_state():
    """Load persisted user state from disk, returning defaults if file doesn't exist."""
    try:
        if not os.path.exists(SAVE_FILE):
            return None
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('Load error:', e)
        return None

def reset_to_defaults():
    """Clear all saved state and reset to factory defaults."""
    try:
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
    except Exception:
        pass

import httpx

GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'llama-3.3-70b-versatile'

ai_state = {'enabled': False, 'key': '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', 'last_error': ''}

def init_ai_client(validate=False):
    if not ai_state['key']:
        ai_state['enabled'] = False
        ai_state['last_error'] = 'No API key provided.'
        return False
    if validate:
        try:
            r = httpx.post(
                GROQ_API_URL,
                headers={'Authorization': 'Bearer {}'.format(ai_state['key']), 'Content-Type': 'application/json'},
                json={'model': GROQ_MODEL, 'max_tokens': 8, 'messages': [{'role': 'user', 'content': 'hi'}]},
                timeout=10
            )
            if r.status_code != 200:
                ai_state['enabled'] = False
                ai_state['last_error'] = 'HTTP {}: {}'.format(r.status_code, r.text[:200])
                return False
        except Exception as e:
            ai_state['enabled'] = False
            ai_state['last_error'] = str(e)
            return False
    ai_state['enabled'] = True
    ai_state['last_error'] = ''
    return True

init_ai_client(validate=False)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    PDF_OK = True
except Exception:
    PDF_OK = False

WATCHLIST = ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'AMZN', 'META', 'GOOGL', 'AMD', 'NFLX', 'JPM']

profile = {'username': 'Trader', 'avatar': '\U0001F600', 'joined': datetime.now().strftime('%d %b %Y'), 'theme': 'green'}

settings = {
    'accent': '#10b981', 'chart_style': 'candles', 'show_ma20': True,
    'show_ma50': True, 'show_ema12': False, 'show_volume': True,
    'compact_mode': False, 'right_panel': True,
}

THEMES = {
    'green':  {'name': 'Terminal Green', 'accent': '#10b981', 'bg': '#080c0a', 'bg1': '#0b100d', 'bg2': '#0f1610', 'bg3': '#132018', 'border': '#1a3020', 'text': '#a8d4ba', 'text2': '#7a9986', 'text3': '#5a7a68'},
    'blue':   {'name': 'Ocean Blue',    'accent': '#3b82f6', 'bg': '#070a0f', 'bg1': '#0a0e15', 'bg2': '#0e131c', 'bg3': '#141b28', 'border': '#1c2a3a', 'text': '#a9c4e0', 'text2': '#7d97b3', 'text3': '#5c7287'},
    'purple': {'name': 'Deep Purple',   'accent': '#8b5cf6', 'bg': '#0a080f', 'bg1': '#0d0b14', 'bg2': '#12101c', 'bg3': '#191527', 'border': '#251f38', 'text': '#c0b3e0', 'text2': '#9485b3', 'text3': '#706589'},
    'orange': {'name': 'Amber Fire',    'accent': '#f97316', 'bg': '#0f0a08', 'bg1': '#140d0a', 'bg2': '#1c130e', 'bg3': '#271a13', 'border': '#3a2519', 'text': '#e0c2a8', 'text2': '#b3937d', 'text3': '#896f5c'},
}

account = {'cash': 10000.00, 'start_cash': 10000.00, 'positions': {}, 'history': []}
alerts = {}
chat_log = [{'role': 'ai', 'text': "Hey! I'm Max, your trading buddy. You've got $10,000 to practice with — zero risk, real market data. Ask me about any stock, what to watch out for, or whether a trade makes sense. What are you looking at today?"}]
state = {'ticker': 'AAPL', 'period': '3mo', 'interval': None, 'chart_type': 'candles', 'view': 'chart'}
explorer_filters = {'sector': 'All', 'index': 'All', 'movement': 'All', 'search': ''}
refs = {}
global_funcs = {}
_cache = {}

# ── Load persisted state ──────────────────────────────────────────────────────
_saved = load_state()
if _saved:
    if 'watchlist' in _saved:
        WATCHLIST.clear(); WATCHLIST.extend(_saved['watchlist'])
    if 'profile' in _saved:
        profile.update(_saved['profile'])
    if 'settings' in _saved:
        settings.update(_saved['settings'])
    if 'account' in _saved:
        account.update(_saved['account'])
    if 'state_ticker' in _saved:
        state['ticker'] = _saved['state_ticker']
    if 'state_period' in _saved:
        state['period'] = _saved['state_period']
    if 'state_chart_type' in _saved:
        state['chart_type'] = _saved['state_chart_type']
    if 'chat_log' in _saved and len(_saved['chat_log']) > 1:
        chat_log.clear(); chat_log.extend(_saved['chat_log'])

def fetch(ticker, period='3mo', need_info=True, interval=None):
    if interval is None:
        # Daily-bar periods default to daily candles; short periods need intraday intervals
        # or Yahoo returns almost no data (e.g. period='1d' + interval='1d' = 1 candle).
        interval = {
            '1d': '5m', '5d': '15m', '1mo': '1h',
        }.get(period, '1d')
    key = f'{ticker}_{period}_{interval}_{need_info}'
    if key in _cache:
        ts, h, i = _cache[key]
        if (datetime.now() - ts).seconds < 60:
            return h, i
    try:
        t = yf.Ticker(ticker)
        h = t.history(period=period, interval=interval)
        i = t.info if need_info else {}
        _cache[key] = (datetime.now(), h, i)
        return h, i
    except Exception:
        return pd.DataFrame(), {}

def fetch_news(ticker):
    try:
        t = yf.Ticker(ticker)
        raw = t.news
        if not raw:
            return []
        out = []
        for item in raw[:10]:
            # Newer yfinance versions nest article data under 'content'
            content = item.get('content', item)
            title = content.get('title') or item.get('title', '')
            link = ''
            if isinstance(content.get('clickThroughUrl'), dict):
                link = content.get('clickThroughUrl', {}).get('url', '')
            elif isinstance(content.get('canonicalUrl'), dict):
                link = content.get('canonicalUrl', {}).get('url', '')
            link = link or item.get('link', '') or '#'
            publisher = ''
            if isinstance(content.get('provider'), dict):
                publisher = content.get('provider', {}).get('displayName', '')
            publisher = publisher or item.get('publisher', '')
            pub_time = content.get('pubDate') or item.get('providerPublishTime', '')
            if title:
                out.append({'title': title, 'link': link, 'publisher': publisher, 'pub_time_raw': pub_time})
        return out
    except Exception:
        return []

MARKET_UNIVERSE = [
    {'symbol': 'AAPL', 'name': 'Apple', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'ABBV', 'name': 'AbbVie', 'sector': 'Healthcare', 'index': 'S&P 500'},
    {'symbol': 'ABNB', 'name': 'Airbnb', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'ADBE', 'name': 'Adobe', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'AMD', 'name': 'AMD', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'AMZN', 'name': 'Amazon', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'AXP', 'name': 'American Express', 'sector': 'Financials', 'index': 'S&P 500'},
    {'symbol': 'BA', 'name': 'Boeing', 'sector': 'Industrials', 'index': 'S&P 500'},
    {'symbol': 'BAC', 'name': 'Bank of America', 'sector': 'Financials', 'index': 'S&P 500'},
    {'symbol': 'BKNG', 'name': 'Booking Holdings', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'sector': 'Crypto', 'index': 'Crypto'},
    {'symbol': 'CAT', 'name': 'Caterpillar', 'sector': 'Industrials', 'index': 'S&P 500'},
    {'symbol': 'COST', 'name': 'Costco', 'sector': 'Consumer Staples', 'index': 'S&P 500'},
    {'symbol': 'CRM', 'name': 'Salesforce', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'CVX', 'name': 'Chevron', 'sector': 'Energy', 'index': 'S&P 500'},
    {'symbol': 'DIA', 'name': 'SPDR Dow Jones ETF', 'sector': 'ETF', 'index': 'ETF'},
    {'symbol': 'DIS', 'name': 'Disney', 'sector': 'Communication Services', 'index': 'S&P 500'},
    {'symbol': 'ETH-USD', 'name': 'Ethereum', 'sector': 'Crypto', 'index': 'Crypto'},
    {'symbol': 'F', 'name': 'Ford Motor', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'GE', 'name': 'General Electric', 'sector': 'Industrials', 'index': 'S&P 500'},
    {'symbol': 'GM', 'name': 'General Motors', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'GOOGL', 'name': 'Alphabet', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'GS', 'name': 'Goldman Sachs', 'sector': 'Financials', 'index': 'S&P 500'},
    {'symbol': 'HD', 'name': 'Home Depot', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'IBM', 'name': 'IBM', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'INTC', 'name': 'Intel', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'IWM', 'name': 'Russell 2000 ETF', 'sector': 'ETF', 'index': 'ETF'},
    {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'sector': 'Healthcare', 'index': 'S&P 500'},
    {'symbol': 'JPM', 'name': 'JPMorgan Chase', 'sector': 'Financials', 'index': 'S&P 500'},
    {'symbol': 'KO', 'name': 'Coca-Cola', 'sector': 'Consumer Staples', 'index': 'S&P 500'},
    {'symbol': 'LLY', 'name': 'Eli Lilly', 'sector': 'Healthcare', 'index': 'S&P 500'},
    {'symbol': 'LOW', 'name': "Lowe's", 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'MA', 'name': 'Mastercard', 'sector': 'Financials', 'index': 'S&P 500'},
    {'symbol': 'MCD', 'name': "McDonald's", 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'META', 'name': 'Meta Platforms', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'MSFT', 'name': 'Microsoft', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'NEE', 'name': 'NextEra Energy', 'sector': 'Utilities', 'index': 'S&P 500'},
    {'symbol': 'NFLX', 'name': 'Netflix', 'sector': 'Communication Services', 'index': 'S&P 500'},
    {'symbol': 'NKE', 'name': 'Nike', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'NVDA', 'name': 'Nvidia', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'ORCL', 'name': 'Oracle', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'PEP', 'name': 'PepsiCo', 'sector': 'Consumer Staples', 'index': 'S&P 500'},
    {'symbol': 'PFE', 'name': 'Pfizer', 'sector': 'Healthcare', 'index': 'S&P 500'},
    {'symbol': 'PG', 'name': 'Procter & Gamble', 'sector': 'Consumer Staples', 'index': 'S&P 500'},
    {'symbol': 'PLD', 'name': 'Prologis', 'sector': 'Real Estate', 'index': 'S&P 500'},
    {'symbol': 'PYPL', 'name': 'PayPal', 'sector': 'Financials', 'index': 'S&P 500'},
    {'symbol': 'QCOM', 'name': 'Qualcomm', 'sector': 'Technology', 'index': 'S&P 500'},
    {'symbol': 'QQQ', 'name': 'Invesco QQQ (Nasdaq 100)', 'sector': 'ETF', 'index': 'ETF'},
    {'symbol': 'SBUX', 'name': 'Starbucks', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF', 'sector': 'ETF', 'index': 'ETF'},
    {'symbol': 'T', 'name': 'AT&T', 'sector': 'Communication Services', 'index': 'S&P 500'},
    {'symbol': 'TGT', 'name': 'Target', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'TSLA', 'name': 'Tesla', 'sector': 'Consumer Discretionary', 'index': 'S&P 500'},
    {'symbol': 'UNH', 'name': 'UnitedHealth', 'sector': 'Healthcare', 'index': 'S&P 500'},
    {'symbol': 'UPS', 'name': 'United Parcel Service', 'sector': 'Industrials', 'index': 'S&P 500'},
    {'symbol': 'V', 'name': 'Visa', 'sector': 'Financials', 'index': 'S&P 500'},
    {'symbol': 'VZ', 'name': 'Verizon', 'sector': 'Communication Services', 'index': 'S&P 500'},
    {'symbol': 'WMT', 'name': 'Walmart', 'sector': 'Consumer Staples', 'index': 'S&P 500'},
    {'symbol': 'XOM', 'name': 'Exxon Mobil', 'sector': 'Energy', 'index': 'S&P 500'},
]

_search_cache = {}

def local_prefix_search(query):
    """Instant local search across the curated universe — matches symbol prefix or name substring."""
    q = query.strip().upper()
    if not q:
        return []
    out = []
    for item in MARKET_UNIVERSE:
        if item['symbol'].upper().startswith(q) or item['name'].upper().startswith(q.upper()):
            out.append({'symbol': item['symbol'], 'name': item['name']})
    # also catch substring matches (lower priority, appended after prefix matches)
    seen = {r['symbol'] for r in out}
    for item in MARKET_UNIVERSE:
        if item['symbol'] in seen:
            continue
        if q.lower() in item['name'].lower():
            out.append({'symbol': item['symbol'], 'name': item['name']})
            seen.add(item['symbol'])
    return out[:8]

def search_symbols(query):
    query = query.strip()
    if not query or len(query) < 1:
        return []
    if query in _search_cache:
        return _search_cache[query]

    local_results = local_prefix_search(query)

    try:
        s = yf.Search(query, max_results=8, news_count=0, include_research=False, enable_fuzzy_query=True)
        remote_results = []
        for q in s.quotes:
            sym = q.get('symbol', '')
            name = q.get('shortname') or q.get('longname') or ''
            if sym:
                remote_results.append({'symbol': sym, 'name': name})
    except Exception:
        remote_results = []

    seen = set()
    combined = []
    for r in local_results + remote_results:
        if r['symbol'] not in seen:
            seen.add(r['symbol'])
            combined.append(r)

    combined = combined[:10]
    _search_cache[query] = combined
    return combined

def calc_rsi(c, n=14):
    d = c.diff()
    g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean()
    return round(float((100 - 100 / (1 + g / l)).iloc[-1]), 1)

def calc_macd(c):
    e12 = c.ewm(span=12).mean()
    e26 = c.ewm(span=26).mean()
    m = e12 - e26
    sig = m.ewm(span=9).mean()
    hist = m - sig
    return round(float(m.iloc[-1]), 2), round(float(sig.iloc[-1]), 2), float(hist.iloc[-1]) > 0

def calc_bb(c, n=20):
    ma = c.rolling(n).mean()
    std = c.rolling(n).std()
    u = float((ma + 2 * std).iloc[-1])
    l = float((ma - 2 * std).iloc[-1])
    p = float(c.iloc[-1])
    pct = round((p - l) / (u - l) * 100, 1) if u != l else 50.0
    return round(u, 2), round(l, 2), pct

def calc_atr(h, n=14):
    hh, ll, cc = h['High'], h['Low'], h['Close']
    tr = pd.concat([hh - ll, (hh - cc.shift()).abs(), (ll - cc.shift()).abs()], axis=1).max(axis=1)
    return round(float(tr.rolling(n).mean().iloc[-1]), 2)

def sma(c, n):
    return c.rolling(n).mean()

def ema(c, n):
    return c.ewm(span=n).mean()

def fmt_cap(n):
    if not n:
        return 'N/A'
    n = float(n)
    if n >= 1e12:
        return '${:.2f}T'.format(n/1e12)
    if n >= 1e9:
        return '${:.2f}B'.format(n/1e9)
    if n >= 1e6:
        return '${:.2f}M'.format(n/1e6)
    return '${:,.0f}'.format(n)

def fmt_vol(n):
    if n >= 1e9:
        return '{:.2f}B'.format(n/1e9)
    if n >= 1e6:
        return '{:.1f}M'.format(n/1e6)
    if n >= 1e3:
        return '{:.0f}K'.format(n/1e3)
    return str(int(n))

def to_candles(h):
    out = []
    for ts, r in h.iterrows():
        out.append({
            'time': int(pd.Timestamp(ts).timestamp()),
            'open': round(float(r['Open']), 2),
            'high': round(float(r['High']), 2),
            'low': round(float(r['Low']), 2),
            'close': round(float(r['Close']), 2),
        })
    return out

def to_line(h):
    return [{'time': int(pd.Timestamp(ts).timestamp()), 'value': round(float(v), 2)} for ts, v in h['Close'].items()]

def to_vol(h):
    out = []
    for ts, r in h.iterrows():
        up = float(r['Close']) >= float(r['Open'])
        out.append({'time': int(pd.Timestamp(ts).timestamp()), 'value': int(r['Volume']), 'color': '#10b98120' if up else '#ef444420'})
    return out

def to_sma(h, n):
    s = sma(h['Close'], n).dropna()
    return [{'time': int(pd.Timestamp(ts).timestamp()), 'value': round(float(v), 2)} for ts, v in s.items()]

def to_ema(h, n):
    s = ema(h['Close'], n).dropna()
    return [{'time': int(pd.Timestamp(ts).timestamp()), 'value': round(float(v), 2)} for ts, v in s.items()]

def get_price(ticker):
    h, _ = fetch(ticker, '1d', need_info=False)
    if h.empty:
        return None
    return round(float(h['Close'].iloc[-1]), 2)

def buy_stock(ticker, shares, price=None):
    if price is None:
        price = get_price(ticker)
    if price is None:
        return False, 'Could not get price'
    try:
        shares = float(shares)
    except Exception:
        return False, 'Invalid share amount'
    if shares <= 0:
        return False, 'Enter a positive number of shares'
    cost = round(price * shares, 2)
    if cost > account['cash']:
        return False, 'Insufficient funds. Need ${:.2f}, have ${:.2f}'.format(cost, account['cash'])
    account['cash'] = round(account['cash'] - cost, 2)
    if ticker in account['positions']:
        pos = account['positions'][ticker]
        total_shares = pos['shares'] + shares
        avg = round((pos['avg_cost'] * pos['shares'] + price * shares) / total_shares, 2)
        account['positions'][ticker] = {'shares': total_shares, 'avg_cost': avg, 'buy_date': pos['buy_date']}
    else:
        account['positions'][ticker] = {'shares': shares, 'avg_cost': price, 'buy_date': datetime.now().strftime('%d %b %Y %H:%M')}
    account['history'].append({'type': 'BUY', 'ticker': ticker, 'shares': shares, 'price': price, 'total': cost, 'date': datetime.now().strftime('%d %b %Y %H:%M'), 'cash_after': account['cash']})
    save_state()
    return True, 'Bought {} {} @ ${:.2f} for ${:.2f}'.format(shares, ticker, price, cost)

def sell_stock(ticker, shares, price=None):
    if ticker not in account['positions']:
        return False, 'You do not own {}'.format(ticker)
    if price is None:
        price = get_price(ticker)
    if price is None:
        return False, 'Could not get price'
    try:
        shares = float(shares)
    except Exception:
        return False, 'Invalid share amount'
    pos = account['positions'][ticker]
    if shares > pos['shares']:
        return False, 'Only own {} shares of {}'.format(pos['shares'], ticker)
    proceeds = round(price * shares, 2)
    gl = round((price - pos['avg_cost']) * shares, 2)
    gl_pct = round((price - pos['avg_cost']) / pos['avg_cost'] * 100, 2)
    account['cash'] = round(account['cash'] + proceeds, 2)
    if shares == pos['shares']:
        del account['positions'][ticker]
    else:
        account['positions'][ticker]['shares'] = round(pos['shares'] - shares, 4)
    account['history'].append({'type': 'SELL', 'ticker': ticker, 'shares': shares, 'price': price, 'total': proceeds, 'gl': gl, 'gl_pct': gl_pct, 'date': datetime.now().strftime('%d %b %Y %H:%M'), 'cash_after': account['cash']})
    save_state()
    return True, 'Sold {} {} @ ${:.2f}  P&L: ${:+.2f} ({:+.1f}%)'.format(shares, ticker, price, gl, gl_pct)

def portfolio_value():
    val = account['cash']
    for ticker, pos in account['positions'].items():
        p = get_price(ticker) or pos['avg_cost']
        val += p * pos['shares']
    return round(val, 2)

def get_perf_stats():
    sells = [t for t in account['history'] if t['type'] == 'SELL']
    if not sells:
        return {}
    gls = [t['gl'] for t in sells]
    wins = [g for g in gls if g > 0]
    losses = [g for g in gls if g < 0]
    total_gl = round(sum(gls), 2)
    return {
        'total_trades': len(sells), 'wins': len(wins), 'losses': len(losses),
        'win_rate': round(len(wins) / len(sells) * 100, 1) if sells else 0,
        'total_gl': total_gl, 'best_trade': max(gls) if gls else 0,
        'worst_trade': min(gls) if gls else 0, 'avg_gl': round(sum(gls) / len(gls), 2) if gls else 0,
        'total_return': round((portfolio_value() - account['start_cash']) / account['start_cash'] * 100, 2),
    }

def build_context():
    h, info = fetch(state['ticker'], state['period'])
    c = h['Close'] if not h.empty else pd.Series([0])
    price = round(float(c.iloc[-1]), 2) if not h.empty else 0
    pv = portfolio_value()
    pos_summary = ', '.join(['{} ({} shares, avg ${})'.format(s, v['shares'], v['avg_cost']) for s, v in account['positions'].items()]) or 'nothing yet'
    stats = get_perf_stats()
    rsi_val = calc_rsi(c) if not h.empty else None
    rsi_text = '{} ({})'.format(rsi_val, 'overbought' if rsi_val and rsi_val > 70 else 'oversold' if rsi_val and rsi_val < 30 else 'neutral') if rsi_val else 'N/A'
    pe = info.get('trailingPE')
    sector = info.get('sector', 'N/A')
    name = info.get('longName', state['ticker'])

    return """You are Max, a sharp and friendly trading buddy inside StockMind Terminal — a paper trading app. You talk like a smart friend who knows markets well, not like a textbook. Be direct, conversational, and genuinely helpful. Use plain English. The odd bit of enthusiasm is fine.

RIGHT NOW the user is looking at: {name} ({ticker}) trading at ${price}
Sector: {sector} | P/E: {pe} | RSI: {rsi}
Their portfolio is worth ${pv:,.2f} with {return_pct:+.2f}% total return
Positions: {positions}
Win rate: {win_rate:.0f}% across {trades} completed trades

Your job:
- Answer their question naturally and helpfully
- If they ask about the stock they're viewing, use what you know about it
- Point out anything genuinely interesting or worth watching (good or bad)
- If something looks risky, say so plainly — don't sugarcoat
- Keep it conversational — no bullet-point walls unless it genuinely helps
- This is paper trading practice, so be encouraging but honest
- Never give a generic non-answer. Always have a real take.
- If you don't know something specific, say so and give your best read instead""".format(
        name=name, ticker=state['ticker'], price=price,
        sector=sector, pe='{:.1f}x'.format(pe) if pe else 'N/A', rsi=rsi_text,
        pv=pv, return_pct=stats.get('total_return', 0),
        positions=pos_summary, win_rate=stats.get('win_rate', 0),
        trades=stats.get('total_trades', 0)
    )

async def ai_respond(user_msg):
    if not ai_state['enabled']:
        return 'AI is not connected. Go to Settings, paste your Groq API key and click Connect.'
    try:
        ctx = build_context()
        msgs = [{'role': 'system', 'content': ctx}]
        for m in chat_log[-8:]:
            if m['role'] == 'user':
                msgs.append({'role': 'user', 'content': m['text']})
            elif m['role'] == 'ai' and m['text'] != '...':
                msgs.append({'role': 'assistant', 'content': m['text']})
        msgs.append({'role': 'user', 'content': user_msg})
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                GROQ_API_URL,
                headers={'Authorization': 'Bearer {}'.format(ai_state['key']), 'Content-Type': 'application/json'},
                json={'model': GROQ_MODEL, 'max_tokens': 500, 'messages': msgs}
            )
        if r.status_code != 200:
            return 'AI error: HTTP {} - {}'.format(r.status_code, r.text[:200])
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        return 'AI error: {}. Check your Groq API key in Settings.'.format(e)

# Build startup theme CSS from saved profile
_startup_theme = THEMES.get(profile.get('theme', 'green'), THEMES['green'])
STARTUP_THEME_CSS = '<style>:root {' + ' '.join(
    '--{}: {};'.format(k, v) for k, v in _startup_theme.items() if k != 'name'
) + ' --green: {};'.format(_startup_theme['accent']) + '}</style>'

CHART_JS = """
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
var PIE = {chart: null};
function smPieRender(labels, values, colors) {
    function tryRender() {
        var el = document.getElementById('portfolio-pie');
        if (!el || !window.Chart) { setTimeout(tryRender, 150); return; }
        if (PIE.chart) { try { PIE.chart.destroy(); } catch(e) {} PIE.chart = null; }
        PIE.chart = new Chart(el, {
            type: 'doughnut',
            data: { labels: labels, datasets: [{ data: values, backgroundColor: colors, borderColor: '#0b100d', borderWidth: 2, hoverOffset: 10 }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { animateRotate: true, duration: 700 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#132018', titleColor: '#e8f0eb', bodyColor: '#8ab89a',
                        borderColor: '#1a3020', borderWidth: 1, padding: 10,
                        callbacks: { label: function(ctx) {
                            var total = ctx.dataset.data.reduce(function(a,b){return a+b;}, 0);
                            var pct = total ? (ctx.raw / total * 100).toFixed(1) : 0;
                            return ' ' + ctx.label + ': $' + ctx.raw.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '  (' + pct + '%)';
                        }}
                    }
                },
                cutout: '62%',
            }
        });
    }
    tryRender();
}
var BAR = {chart: null};
function smBarRender(labels, values, colors) {
    function tryRender() {
        var el = document.getElementById('portfolio-bar');
        if (!el || !window.Chart) { setTimeout(tryRender, 150); return; }
        if (BAR.chart) { try { BAR.chart.destroy(); } catch(e) {} BAR.chart = null; }
        BAR.chart = new Chart(el, {
            type: 'bar',
            data: { labels: labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 4, maxBarThickness: 36 }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 600 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#132018', titleColor: '#e8f0eb', bodyColor: '#8ab89a',
                        borderColor: '#1a3020', borderWidth: 1, padding: 10,
                        callbacks: { label: function(ctx) {
                            var v = ctx.raw;
                            return (v >= 0 ? ' +$' : ' -$') + Math.abs(v).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                        }}
                    }
                },
                scales: {
                    x: { grid: { color: '#1a3020' }, ticks: { color: '#7a9986', font: {family: 'IBM Plex Mono', size: 10} } },
                    y: { grid: { color: '#1a3020' }, ticks: { color: '#7a9986', font: {family: 'IBM Plex Mono', size: 10} } }
                }
            }
        });
    }
    tryRender();
}
</script>
<script>
var SM = {chart:null, cs:null, ls:null, ma20:null, ma50:null, ema12:null, vol:null};
function smCssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return v ? v.trim() : fallback;
}
function smInit() {
    var el = document.getElementById('sm-chart');
    if (!el || !window.LightweightCharts) { setTimeout(smInit, 150); return; }
    if (el.clientWidth < 10 || el.clientHeight < 10) { setTimeout(smInit, 150); return; }
    if (SM.chart) { try { SM.chart.remove(); } catch(e) {} SM.chart = null; }
    var bg = smCssVar('--bg', '#080c0a');
    var border = smCssVar('--border', '#1a3020');
    var textC = smCssVar('--text2', '#7a9986');
    var accent = smCssVar('--accent', '#10b981');
    SM.chart = LightweightCharts.createChart(el, {
        width: el.clientWidth, height: el.clientHeight,
        layout: { background: {color:bg}, textColor:textC },
        grid: { vertLines: {color:border}, horzLines: {color:border} },
        crosshair: { mode: 1, vertLine: {color:accent+'44', labelBackgroundColor:border}, horzLine: {color:accent+'44', labelBackgroundColor:border} },
        rightPriceScale: { borderColor:border, textColor:textC },
        timeScale: { borderColor:border, textColor:textC, timeVisible:true, secondsVisible:false },
        handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
        handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true },
    });
    SM.cs = SM.chart.addCandlestickSeries({ upColor:'#10b981', downColor:'#ef4444', borderUpColor:'#10b981', borderDownColor:'#ef4444', wickUpColor:'#10b981', wickDownColor:'#ef4444' });
    SM.ls = SM.chart.addLineSeries({ color:accent, lineWidth:2, visible:true });
    SM.ma20 = SM.chart.addLineSeries({ color:'#f59e0b', lineWidth:1, title:'MA20' });
    SM.ma50 = SM.chart.addLineSeries({ color:'#6366f1', lineWidth:1, lineStyle:1, title:'MA50' });
    SM.ema12 = SM.chart.addLineSeries({ color:'#ec4899', lineWidth:1, lineStyle:2, title:'EMA12', visible:false });
    SM.vol = SM.chart.addHistogramSeries({ priceFormat:{type:'volume'}, priceScaleId:'vol', scaleMargins:{top:0.82, bottom:0} });
    function doResize() {
        if (SM.chart && el.clientWidth > 0 && el.clientHeight > 0) {
            SM.chart.applyOptions({width: el.clientWidth, height: el.clientHeight});
        }
    }
    new ResizeObserver(doResize).observe(el);
    setTimeout(doResize, 100);
    setTimeout(doResize, 400);
    setTimeout(doResize, 900);

    el.onwheel = function(ev) {
        if (!ev.ctrlKey && !ev.metaKey) return; // plain scroll: let it bubble to the page
        ev.preventDefault();
        smZoom(ev.deltaY < 0 ? 0.85 : 1.18);
    };
}
function smZoom(factor) {
    if (!SM.chart) return;
    var ts = SM.chart.timeScale();
    var range = ts.getVisibleLogicalRange();
    if (!range) return;
    var span = range.to - range.from;
    var newSpan = Math.max(span * factor, 3); // don't zoom in past ~3 bars
    var center = range.from + span / 2;
    ts.setVisibleLogicalRange({ from: center - newSpan / 2, to: center + newSpan / 2 });
}
function smZoomReset() {
    if (!SM.chart) return;
    SM.chart.timeScale().fitContent();
}
function smUpdate(candles, line, ma20, ma50, ema12, vol, ct, vis) {
    if (!SM.chart) { setTimeout(function(){ smUpdate(candles, line, ma20, ma50, ema12, vol, ct, vis); }, 200); return; }
    var isC = (ct === 'candles');
    SM.cs.setData(isC ? candles : []);
    SM.cs.applyOptions({visible: isC});
    SM.ls.setData(!isC ? line : []);
    SM.ls.applyOptions({visible: !isC});
    SM.ma20.setData(ma20);
    SM.ma50.setData(ma50);
    SM.ema12.setData(ema12);
    SM.vol.setData(vol);
    // Re-apply visibility from Python settings every time — reinit resets to defaults otherwise
    if (vis) {
        SM.ma20.applyOptions({visible: !!vis.ma20});
        SM.ma50.applyOptions({visible: !!vis.ma50});
        SM.ema12.applyOptions({visible: !!vis.ema12});
    }
    SM.chart.timeScale().fitContent();
    SM.lastBar = candles.length ? Object.assign({}, candles[candles.length - 1]) : null;
    SM.lastLinePoint = line.length ? Object.assign({}, line[line.length - 1]) : null;
}
function smUpdateLastPrice(price) {
    if (!SM.chart || !SM.cs) return;
    if (SM.lastBar) {
        SM.lastBar.high = Math.max(SM.lastBar.high, price);
        SM.lastBar.low = Math.min(SM.lastBar.low, price);
        SM.lastBar.close = price;
        try { SM.cs.update(SM.lastBar); } catch (e) {}
    }
    if (SM.lastLinePoint && SM.ls) {
        SM.lastLinePoint.value = price;
        try { SM.ls.update(SM.lastLinePoint); } catch (e) {}
    }
}
function smToggle(name, v) {
    if (name === 'ma20' && SM.ma20) SM.ma20.applyOptions({visible: v});
    if (name === 'ma50' && SM.ma50) SM.ma50.applyOptions({visible: v});
    if (name === 'ema12' && SM.ema12) SM.ema12.applyOptions({visible: v});
}
function smSetType(t) {
    if (!SM.cs) return;
    var isC = (t === 'candles');
    SM.cs.applyOptions({visible: isC});
    SM.ls.applyOptions({visible: !isC});
}
function smAddLine(price, label, color) {
    if (!SM.cs) return;
    SM.cs.createPriceLine({price: price, color: color || '#f59e0b', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: label || ''});
}
function smFlashPulse() {
    var el = document.getElementById('live-pulse-dot');
    if (!el) return;
    el.style.transition = 'none';
    el.style.transform = 'scale(1.8)';
    el.style.opacity = '1';
    requestAnimationFrame(function() {
        el.style.transition = 'transform 0.4s ease, opacity 0.4s ease';
        el.style.transform = 'scale(1)';
    });
}
document.addEventListener('DOMContentLoaded', smInit);
window.smInit = smInit;
window.smReinit = smInit;
window.smUpdateLastPrice = smUpdateLastPrice;
window.smFlashPulse = smFlashPulse;
window.smZoom = smZoom;
window.smZoomReset = smZoomReset;
var HIST = {chart: null};
function smHistRender(labels, values) {
    function tryRender() {
        var el = document.getElementById('portfolio-hist');
        if (!el || !window.Chart) { setTimeout(tryRender, 200); return; }
        if (HIST.chart) { try { HIST.chart.destroy(); } catch(e) {} HIST.chart = null; }
        var grad = el.getContext('2d').createLinearGradient(0, 0, 0, el.offsetHeight || 200);
        grad.addColorStop(0, 'rgba(99,102,241,0.3)');
        grad.addColorStop(1, 'rgba(99,102,241,0.0)');
        HIST.chart = new Chart(el, {
            type: 'line',
            data: { labels: labels, datasets: [{
                data: values, borderColor: '#6366f1', borderWidth: 2.5,
                backgroundColor: grad, fill: true,
                pointRadius: 0, pointHoverRadius: 4, tension: 0.3
            }]},
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 600 },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#0d1f12', titleColor: '#a0c4a8', bodyColor: '#e8f0eb',
                        borderColor: '#1a3020', borderWidth: 1, padding: 10,
                        callbacks: {
                            label: function(ctx) {
                                return ' $' + ctx.raw.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                            }
                        }
                    }
                },
                scales: {
                    x: { grid: { color: '#1a2420' }, ticks: { color: '#4a6a54', font: {size:9, family:'IBM Plex Mono'}, maxTicksLimit: 8 } },
                    y: { grid: { color: '#1a2420' }, ticks: { color: '#4a6a54', font: {size:9, family:'IBM Plex Mono'},
                        callback: function(v) { return '$' + (v >= 1000 ? (v/1000).toFixed(1)+'k' : v); }
                    }}
                }
            }
        });
    }
    tryRender();
}
</script>
"""

CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.11.0/dist/tabler-icons.min.css"/>
<style>
:root {
  --bg:#080c0a; --bg1:#0b100d; --bg2:#0f1610; --bg3:#132018;
  --border:#1a3020; --text:#a8d4ba; --text2:#7a9986; --text3:#5a7a68;
  --green:#10b981; --red:#ef4444; --amber:#f59e0b; --indigo:#6366f1; --pink:#ec4899;
  --white:#e8f0eb; --mono:'IBM Plex Mono',monospace; --sans:'Inter',sans-serif;
  --accent:#10b981;
}
*, *::before, *::after { box-sizing: border-box; }
html, body { margin:0; padding:0; width:100%; height:100%; background:var(--bg); font-family:var(--sans); overflow:hidden; color:var(--text); }
.nicegui-content { padding:0!important; width:100vw; height:100vh; overflow:hidden; }
.q-btn { text-transform:none!important; letter-spacing:0!important; }
.q-field__control { background:transparent!important; min-height:30px!important; }
.q-field__native { color:var(--white)!important; font-size:12px!important; font-family:var(--sans)!important; padding:0!important; }
.q-field__native::placeholder { color:var(--text3)!important; }
.q-field--outlined .q-field__control:before { border-color:var(--border)!important; border-radius:5px!important; }
.q-field--outlined.q-field--focused .q-field__control:before { border-color:var(--accent)!important; border-width:1px!important; }
.q-field__marginal { color:var(--text2)!important; height:30px!important; }
.q-scrollarea__content { width:100%!important; }
.q-tooltip { font-family:var(--sans)!important; font-size:11px!important; background:#1a3020!important; color:var(--text)!important; border:1px solid var(--border)!important; }
.q-table { background:transparent!important; }
.q-table th { color:var(--text3)!important; font-family:var(--mono)!important; font-size:9px!important; letter-spacing:1px!important; background:var(--bg2)!important; border-color:var(--border)!important; }
.q-table td { color:var(--text)!important; font-family:var(--mono)!important; font-size:11px!important; border-color:var(--bg3)!important; }
.q-table tr:hover td { background:var(--bg2)!important; }
.q-checkbox__label { color:var(--text)!important; font-size:11px!important; font-family:var(--mono)!important; }
.q-select .q-field__native { color:var(--white)!important; }
html { scrollbar-width: thin; scrollbar-color: var(--text3) var(--bg1); }
::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-track { background:var(--bg1); }
::-webkit-scrollbar-thumb { background:var(--text3); border-radius:4px; border:2px solid var(--bg1); }
::-webkit-scrollbar-thumb:hover { background:var(--text2); }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes fadeIn { from{opacity:0;transform:translateY(3px)} to{opacity:1;transform:none} }
@keyframes scan { 0%{top:-2%} 100%{top:102%} }
.scanline { position:fixed; top:0; left:0; width:100%; height:1px; background:linear-gradient(transparent, rgba(16,185,129,.06), transparent); animation: scan 8s linear infinite; pointer-events:none; z-index:9999; }
.live-dot { width:6px; height:6px; border-radius:50%; background:var(--accent); animation:pulse 2s infinite; flex-shrink:0; }
.sec-label { font-size:9px; letter-spacing:1.5px; text-transform:uppercase; color:var(--text3); font-family:var(--mono); }
.s-item { width:38px; height:38px; border-radius:7px; display:flex; align-items:center; justify-content:center; cursor:pointer; transition:background .1s; }
.s-item:hover { background:var(--bg3); }
.s-item.active { background:var(--bg3); border:1px solid var(--border); }
.w-row { display:flex; justify-content:space-between; align-items:center; padding:5px 8px; border-radius:5px; cursor:pointer; transition:background .1s; border:1px solid transparent; }
.w-row:hover { background:var(--bg2); border-color:var(--border); }
.ind-card { flex:1; background:var(--bg2); border:1px solid var(--border); border-radius:6px; padding:9px 11px; display:flex; flex-direction:column; gap:2px; min-width:100px; }
.chat-bubble { border-radius:8px; padding:9px 12px; font-size:12px; line-height:1.6; flex:1; word-break:break-word; animation:fadeIn .2s ease; }
.chat-bubble.ai { background:var(--bg2); border:1px solid var(--border); color:var(--text); }
.chat-bubble.user { background:var(--bg3); border:1px solid #1a4a2a; color:var(--white); }
.pill { padding:3px 9px; border-radius:4px; font-size:11px; cursor:pointer; font-family:var(--mono); border:1px solid var(--border); color:var(--text2); background:transparent; transition:all .12s; }
.pill:hover { color:var(--text); background:var(--bg2); }
.pill.active { color:var(--accent); background:var(--bg3); border-color:var(--accent); }
.top-stat { display:flex; flex-direction:column; gap:1px; padding:0 10px; border-right:1px solid var(--border); }
.top-stat:last-child { border-right:none; }
.view-btn { padding:4px 12px; border-radius:4px; font-size:11px; cursor:pointer; color:var(--text2); background:transparent; border:none; font-family:var(--sans); display:flex; align-items:center; gap:5px; transition:all .12s; white-space:nowrap; }
.view-btn:hover { color:var(--text); background:var(--bg2); }
.view-btn.active { color:var(--accent); background:var(--bg3); }
.card { background:var(--bg2); border:1px solid var(--border); border-radius:6px; padding:14px; }
.trade-row { display:flex; justify-content:space-between; align-items:center; padding:7px 10px; background:var(--bg2); border:1px solid var(--border); border-radius:5px; margin-bottom:4px; cursor:pointer; transition:border-color .1s; }
.trade-row:hover { border-color:var(--accent); }
.news-card { background:var(--bg2); border:1px solid var(--border); border-radius:6px; padding:10px 12px; margin-bottom:6px; cursor:pointer; transition:border-color .1s; }
.news-card:hover { border-color:var(--accent); }
</style>
"""

ui.add_head_html(CSS)
ui.add_head_html(STARTUP_THEME_CSS)
ui.add_body_html(CHART_JS)
ui.add_body_html('<div class="scanline"></div>')

def D(s='', c=''):
    el = ui.element('div')
    if s:
        el.style(s)
    if c:
        el.classes(c)
    return el

def R(s=''):
    return D('display:flex;align-items:center;' + s)

def C(s=''):
    return D('display:flex;flex-direction:column;' + s)

def L(t, s='', c=''):
    el = ui.label(t)
    if s:
        el.style(s)
    if c:
        el.classes(c)
    return el

def ICO(cls, s='', sz=16):
    return ui.label('').classes('ti ' + cls).style('font-size:{}px;{}'.format(sz, s))

def PILL(t, active=False, on_click=None):
    return ui.button(t, on_click=on_click).classes('pill' + (' active' if active else ''))

def safe_set(key, text, style=None):
    if key in refs:
        refs[key].set_text(str(text))
        if style:
            refs[key].style(style)

def load_stock(ticker, period=None):
    ticker = ticker.strip().upper().replace(' ', '')
    if not ticker:
        return
    if period:
        state['period'] = period
    state['ticker'] = ticker
    h, info = fetch(ticker, state['period'], interval=state.get('interval'))
    if h.empty:
        if state.get('interval'):
            ui.notify('No data for {} at {} interval over {} - try a shorter period'.format(ticker, state['interval'], state['period']), type='negative', position='top-right', timeout=4000)
        else:
            ui.notify('No data: {}'.format(ticker), type='negative', position='top-right')
        return

    c = h['Close']
    price = round(float(c.iloc[-1]), 2)
    prev = round(float(c.iloc[-2]), 2)
    chg = round(price - prev, 2)
    pct = round(chg / prev * 100, 2) if prev else 0

    up = chg >= 0
    col = 'var(--green)' if up else 'var(--red)'
    arr = 'UP' if up else 'DOWN'

    _rsi = calc_rsi(c)
    m_val, sig, bull = calc_macd(c)
    bb_u, bb_l, bpct = calc_bb(c)
    lv, av = int(h['Volume'].iloc[-1]), int(h['Volume'].mean())
    vpct = round((lv - av) / av * 100, 1) if av else 0
    _atr = calc_atr(h)
    h52 = round(float(h['High'].max()), 2)
    l52 = round(float(h['Low'].min()), 2)
    day_high = round(float(h['High'].iloc[-1]), 2)
    day_low = round(float(h['Low'].iloc[-1]), 2)
    daily_returns = c.pct_change().dropna()
    volatility_pct = round(float(daily_returns.std() * 100), 2) if len(daily_returns) > 1 else 0
    if volatility_pct < 1.5:
        vol_label = 'Low'
        vol_color = 'var(--green)'
    elif volatility_pct < 3:
        vol_label = 'Moderate'
        vol_color = 'var(--amber)'
    else:
        vol_label = 'High'
        vol_color = 'var(--red)'
    name = info.get('longName', ticker)
    exch = info.get('exchange', '')
    sector = info.get('sector', '')
    cap = fmt_cap(info.get('marketCap'))
    pe = info.get('trailingPE')
    div = info.get('dividendYield')
    beta = info.get('beta')
    eps = info.get('trailingEps')

    safe_set('hdr_name', name)
    safe_set('hdr_ticker', '{} | {} | {}'.format(ticker, exch, sector))
    safe_set('hdr_price', '${:,.2f}'.format(price))
    safe_set('hdr_chg', '{} ${:.2f}  ({:.2f}%)'.format(arr, abs(chg), abs(pct)), 'font-size:12px;color:{};font-family:var(--mono);'.format(col))

    # Dashboard: clean human-readable stats
    safe_set('ind_range_v', '${:.2f} - ${:.2f}'.format(day_low, day_high))
    safe_set('ind_range_s', "Today's low to high")
    safe_set('ind_cap_v', cap)
    safe_set('ind_cap_s', '{} sector'.format(sector) if sector else 'Total company value')
    safe_set('ind_vol_v', '{}%'.format(volatility_pct), 'font-family:var(--mono);font-size:16px;font-weight:600;color:{};'.format(vol_color))
    safe_set('ind_vol_s', '{} risk - daily swing'.format(vol_label))
    safe_set('ind_eps_v', '${:.2f}'.format(eps) if eps else 'N/A')
    safe_set('ind_eps_s', 'Profit per share')
    mc = 'var(--green)' if bull else 'var(--red)'
    safe_set('ind_macd_v', 'Bullish' if bull else 'Bearish', 'font-family:var(--mono);font-size:16px;font-weight:600;color:{};'.format(mc))
    safe_set('ind_macd_s', 'Price momentum direction')
    rsi_col = 'var(--green)' if 30 < _rsi < 70 else ('var(--red)' if _rsi >= 70 else 'var(--amber)')
    rsi_label = 'Balanced' if 30 < _rsi < 70 else ('Overbought' if _rsi >= 70 else 'Oversold')
    safe_set('ind_rsi_v', rsi_label, 'font-family:var(--mono);font-size:16px;font-weight:600;color:{};'.format(rsi_col))
    safe_set('ind_rsi_s', 'Buying/selling pressure')

    # Full chart view: technical indicators (separate ref keys)
    safe_set('ind_rsi_v2', str(_rsi), 'font-family:var(--mono);font-size:17px;font-weight:600;color:{};'.format(rsi_col))
    safe_set('ind_rsi_s2', 'Neutral' if 30 < _rsi < 70 else ('Overbought' if _rsi >= 70 else 'Oversold'))
    safe_set('ind_macd_v2', 'Bullish' if bull else 'Bearish', 'font-family:var(--mono);font-size:17px;font-weight:600;color:{};'.format(mc))
    safe_set('ind_macd_s2', 'MACD {:+.2f}  Sig {:.2f}'.format(m_val, sig))
    bc = 'var(--green)' if bpct > 50 else 'var(--red)'
    safe_set('ind_bb_v', '{:.0f}%'.format(bpct), 'font-family:var(--mono);font-size:17px;font-weight:600;color:{};'.format(bc))
    safe_set('ind_bb_s', '${:.0f} to ${:.0f}'.format(bb_l, bb_u))
    vc2 = 'var(--green)' if vpct >= 0 else 'var(--red)'
    safe_set('ind_vold_v', '{:+.1f}%'.format(vpct), 'font-family:var(--mono);font-size:17px;font-weight:600;color:{};'.format(vc2))
    safe_set('ind_vold_s', '{} vs {} avg'.format(fmt_vol(lv), fmt_vol(av)))
    safe_set('ind_atr_v', '${}'.format(_atr))
    safe_set('ind_atr_s', 'Daily range avg')

    safe_set('ai_sub', '{} | {} | {}'.format(ticker, state['period'], datetime.now().strftime('%H:%M')))
    safe_set('trade_ticker', ticker)
    safe_set('trade_price', '${:,.2f}'.format(price))
    safe_set('acct_pv', '${:,.2f}'.format(portfolio_value()))

    vis = {'ma20': settings['show_ma20'], 'ma50': settings['show_ma50'], 'ema12': settings['show_ema12']}
    chart_js_call = 'smUpdate({}, {}, {}, {}, {}, {}, "{}", {})'.format(
        json.dumps(to_candles(h)), json.dumps(to_line(h)),
        json.dumps(to_sma(h, 20)), json.dumps(to_sma(h, 50)), json.dumps(to_ema(h, 12)),
        json.dumps(to_vol(h)), state['chart_type'], json.dumps(vis)
    )
    state['last_chart_js'] = chart_js_call
    state['last_chart_ticker'] = ticker
    ui.run_javascript('window.smReinit ? window.smReinit() : null;')
    ui.run_javascript(chart_js_call)

    for sym in WATCHLIST:
        if sym == ticker:
            safe_set('wp_{}'.format(sym), '${:,.2f}'.format(price))
            safe_set('wc_{}'.format(sym), '{:+.2f}%'.format(pct), 'font-size:9px;color:{};font-family:var(--mono);'.format(col))

    if ticker in alerts:
        al = alerts[ticker]
        if al.get('above') and price >= al['above']:
            ui.notify('Alert: {} hit ${} - above ${}'.format(ticker, price, al['above']), type='warning', timeout=6000)
        if al.get('below') and price <= al['below']:
            ui.notify('Alert: {} hit ${} - below ${}'.format(ticker, price, al['below']), type='warning', timeout=6000)

    if state['view'] != 'chart' and 'content_area' in refs:
        rebuild_view()

    ui.timer(1.0, refresh_live_price, once=True)

    ui.notify('{} ${:,.2f} {} {:.2f}%'.format(ticker, price, arr, abs(pct)), type='positive' if up else 'negative', position='top-right', timeout=1800)

def render_chat():
    if 'chat_col' not in refs:
        return
    refs['chat_col'].clear()
    with refs['chat_col']:
        for msg in chat_log:
            is_ai = msg['role'] == 'ai'
            ico = 'ti-terminal-2' if is_ai else 'ti-user'
            av_bg = 'var(--bg3)' if is_ai else '#1a4a2a'
            ic = 'var(--accent)' if is_ai else 'var(--white)'
            cls = 'ai' if is_ai else 'user'
            with D('display:flex;align-items:flex-start;gap:7px;width:100%;'):
                with D('width:22px;height:22px;min-width:22px;flex-shrink:0;background:{};border-radius:5px;border:1px solid var(--border);display:flex;align-items:center;justify-content:center;margin-top:1px;'.format(av_bg)):
                    ICO(ico, 'font-size:11px;color:{};'.format(ic))
                L(msg['text']).classes('chat-bubble {}'.format(cls))

async def send_msg():
    if 'chat_in' not in refs:
        return
    val = refs['chat_in'].value.strip()
    if not val:
        return
    chat_log.append({'role': 'user', 'text': val})
    refs['chat_in'].value = ''
    chat_log.append({'role': 'ai', 'text': '...'})
    render_chat()
    resp = await ai_respond(val)
    chat_log[-1]['text'] = resp
    render_chat()

def build_chart_view(c):
    c.clear()
    with c:
        with R('justify-content:space-between;align-items:flex-start;margin-bottom:8px;'):
            with C('gap:2px;'):
                refs['hdr_name'] = L('Apple Inc.', 'font-size:15px;font-weight:600;color:var(--white);')
                refs['hdr_ticker'] = L('AAPL | NASDAQ | Technology', 'font-size:10px;color:var(--text2);font-family:var(--mono);')
            with R('gap:12px;align-items:center;'):
                with C('align-items:flex-end;gap:2px;'):
                    with R('gap:5px;align-items:center;'):
                        refs['live_pulse'] = D('width:6px;height:6px;border-radius:50%;background:var(--green);').classes('live-dot')
                        refs['live_pulse'].props('id="live-pulse-dot"')
                        refs['hdr_price'] = L('$--', 'font-family:var(--mono);font-size:24px;font-weight:600;color:var(--white);')
                    refs['hdr_chg'] = L('--', 'font-size:12px;color:var(--green);font-family:var(--mono);')
                with R('gap:6px;align-items:center;'):
                    trade_qty = ui.input(value='1', placeholder='qty').props('outlined dense').style('width:52px;font-family:var(--mono);font-size:11px;')
                    def quick_buy():
                        ok, msg = buy_stock(state['ticker'], trade_qty.value or 1)
                        ui.notify(msg, type='positive' if ok else 'negative')
                    def quick_sell():
                        ok, msg = sell_stock(state['ticker'], trade_qty.value or 1)
                        ui.notify(msg, type='positive' if ok else 'negative')
                    ui.button('BUY', on_click=quick_buy).style(
                        'background:#10b98122;border:1px solid #10b98155;color:var(--green);'
                        'border-radius:6px;font-family:var(--mono);font-weight:700;font-size:11px;padding:5px 14px;')
                    ui.button('SELL', on_click=quick_sell).style(
                        'background:#ef444422;border:1px solid #ef444455;color:var(--red);'
                        'border-radius:6px;font-family:var(--mono);font-weight:700;font-size:11px;padding:5px 14px;')

        PERIOD_DAYS = {'1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180, '1y': 365, '5y': 1825}
        INTERVAL_MAX_DAYS = {'1m': 7, '5m': 60, '15m': 60, '30m': 60, '1h': 730, '1d': 100000}

        def clamp_period_for_interval(period, interval):
            """If the chosen period exceeds what the interval supports, shrink it to the largest valid period."""
            if interval is None:
                return period
            max_days = INTERVAL_MAX_DAYS.get(interval, 100000)
            if PERIOD_DAYS.get(period, 0) <= max_days:
                return period
            # find the largest period that still fits within this interval's max lookback
            valid = [p for p, d in PERIOD_DAYS.items() if d <= max_days]
            if not valid:
                return period
            return max(valid, key=lambda p: PERIOD_DAYS[p])

        with R('justify-content:space-between;margin-bottom:6px;flex-wrap:wrap;gap:6px;'):
            with R('gap:3px;flex-wrap:wrap;'):
                for lbl2, pv in [('1D', '1d'), ('5D', '5d'), ('1M', '1mo'), ('3M', '3mo'), ('6M', '6mo'), ('1Y', '1y'), ('5Y', '5y')]:
                    def pick_period(e, p=pv):
                        # Keep the current interval if still valid for this period, otherwise clear it
                        # so fetch() falls back to its own sensible default for the new window.
                        cur_interval = state.get('interval')
                        if cur_interval and PERIOD_DAYS.get(p, 0) > INTERVAL_MAX_DAYS.get(cur_interval, 100000):
                            state['interval'] = None
                        ui.timer(0.05, lambda: load_stock(state['ticker'], p), once=True)
                    PILL(lbl2, state['period'] == pv, on_click=pick_period)
            with R('gap:5px;align-items:center;flex-wrap:wrap;'):
                for iname, icol, ilbl in [('ma20', 'var(--amber)', 'MA20'), ('ma50', 'var(--indigo)', 'MA50'), ('ema12', 'var(--pink)', 'EMA12')]:
                    def make_toggle(n):
                        def toggle(e):
                            settings['show_' + n] = e.value
                            ui.run_javascript('smToggle("{}", {})'.format(n, str(e.value).lower()))
                            save_state()
                        return toggle
                    ui.checkbox(ilbl, value=settings['show_' + iname], on_change=make_toggle(iname)).style('color:{};'.format(icol))
                D('width:1px;height:14px;background:var(--border);')
                for ct in ['Candles', 'Line']:
                    PILL(ct, state['chart_type'] == ct.lower(), on_click=lambda e, c2=ct: (state.update({'chart_type': c2.lower()}), ui.run_javascript('smSetType("{}")'.format(c2.lower()))))

        with R('gap:3px;flex-wrap:wrap;margin-bottom:8px;align-items:center;'):
            L('CANDLE', '').classes('sec-label').style('margin-right:2px;')
            for ilbl3, iv in [('1m', '1m'), ('5m', '5m'), ('15m', '15m'), ('30m', '30m'), ('1H', '1h'), ('1D', '1d')]:
                def pick_interval(e, v=iv):
                    # Keep the user's current time window (period) - only shrink it if this
                    # interval genuinely cannot support that much history.
                    state['interval'] = v
                    safe_period = clamp_period_for_interval(state['period'], v)
                    ui.timer(0.05, lambda: load_stock(state['ticker'], safe_period), once=True)
                PILL(ilbl3, state['interval'] == iv, on_click=pick_interval)

        with D('height:340px;background:var(--bg);border:1px solid var(--border);border-radius:6px;overflow:hidden;position:relative;'):
            ui.element('div').props('id="sm-chart"').style('width:100%;height:100%;')
            with R('position:absolute;top:8px;left:10px;z-index:10;gap:5px;'):
                D('').classes('live-dot')
                L('LIVE', 'font-family:var(--mono);font-size:9px;color:var(--accent);letter-spacing:1px;')
            with R('position:absolute;top:8px;right:10px;z-index:10;gap:4px;'):
                with D('width:24px;height:24px;border-radius:5px;background:var(--bg2);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;').on('click', lambda e: ui.run_javascript('window.smZoom && window.smZoom(0.8)')).tooltip('Zoom in'):
                    ICO('ti-zoom-in', 'color:var(--text2);', 13)
                with D('width:24px;height:24px;border-radius:5px;background:var(--bg2);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;').on('click', lambda e: ui.run_javascript('window.smZoom && window.smZoom(1.25)')).tooltip('Zoom out'):
                    ICO('ti-zoom-out', 'color:var(--text2);', 13)
                with D('width:24px;height:24px;border-radius:5px;background:var(--bg2);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;').on('click', lambda e: ui.run_javascript('window.smZoomReset && window.smZoomReset()')).tooltip('Reset zoom'):
                    ICO('ti-zoom-reset', 'color:var(--text2);', 13)
        ui.timer(0.15, lambda: ui.run_javascript('window.smInit && window.smInit();'), once=True)
        if state.get('last_chart_js') and state.get('last_chart_ticker') == state.get('ticker'):
            ui.timer(0.35, lambda: ui.run_javascript(state['last_chart_js']), once=True)
        else:
            ui.timer(0.1, lambda: load_stock(state['ticker'], state['period']), once=True)

        with R('gap:6px;margin-top:8px;flex-wrap:wrap;align-items:center;'):
            L('DRAW', '').classes('sec-label')
            ann_p = ui.input(placeholder='Price').props('outlined dense').style('width:90px;')
            ann_l = ui.input(placeholder='Label').props('outlined dense').style('width:100px;')
            for col_name, hex_c in [('Support', '#10b981'), ('Resist', '#ef4444'), ('Target', '#f59e0b'), ('Custom', '#6366f1')]:
                ui.button(col_name, on_click=lambda e, h=hex_c, p=ann_p, lb=ann_l: ui.run_javascript('smAddLine({}, "{}", "{}")'.format(float(p.value) if p.value else 0, lb.value, h))).classes('pill').style('color:{};border-color:{}33;font-size:10px;'.format(hex_c, hex_c))

        L('TODAY AT A GLANCE', '').classes('sec-label').style('margin-top:10px;margin-bottom:6px;')
        with R('gap:8px;flex-wrap:wrap;'):
            for lbl3, vk, sk, dv, ds, col_s in [
                ("Day's Range", 'ind_range_v', 'ind_range_s', '--', 'Low to High today', 'var(--white)'),
                ('Market Cap', 'ind_cap_v', 'ind_cap_s', '--', 'Total company value', 'var(--white)'),
                ('Volatility', 'ind_vol_v', 'ind_vol_s', '--', 'Price swing risk', 'var(--amber)'),
                ('Earnings/Share', 'ind_eps_v', 'ind_eps_s', '--', 'Profit per share', 'var(--white)'),
                ('Trend', 'ind_macd_v', 'ind_macd_s', '--', '--', 'var(--green)'),
                ('Momentum', 'ind_rsi_v', 'ind_rsi_s', '--', '--', 'var(--green)'),
            ]:
                with D('').classes('ind-card'):
                    L(lbl3, 'font-size:8px;color:var(--text3);font-family:var(--mono);letter-spacing:.8px;margin-bottom:3px;')
                    refs[vk] = L(dv, 'font-family:var(--mono);font-size:16px;font-weight:600;color:{};'.format(col_s))
                    refs[sk] = L(ds, 'font-size:10px;color:var(--text2);margin-top:1px;')

        L('TECHNICAL INDICATORS', '').classes('sec-label').style('margin-top:10px;margin-bottom:6px;')
        with R('gap:6px;flex-wrap:wrap;'):
            for lbl3, vk, sk, dv, ds, col_s in [
                ('RSI 14', 'ind_rsi_v2', 'ind_rsi_s2', '--', '--', 'var(--green)'),
                ('MACD', 'ind_macd_v2', 'ind_macd_s2', '--', '--', 'var(--green)'),
                ('BOLL %B', 'ind_bb_v', 'ind_bb_s', '--', '--', 'var(--amber)'),
                ('VOL DELTA', 'ind_vold_v', 'ind_vold_s', '--', '--', 'var(--indigo)'),
                ('ATR', 'ind_atr_v', 'ind_atr_s', '--', '--', 'var(--pink)'),
            ]:
                with D('').classes('ind-card'):
                    L(lbl3, 'font-size:8px;color:var(--text3);font-family:var(--mono);letter-spacing:.8px;margin-bottom:3px;')
                    refs[vk] = L(dv, 'font-family:var(--mono);font-size:17px;font-weight:600;color:{};'.format(col_s))
                    refs[sk] = L(ds, 'font-size:10px;color:var(--text2);font-family:var(--mono);margin-top:1px;')


def fetch_holdings_batch(symbols):
    """Fetch price + basic info for holdings using fast quote endpoint."""
    import concurrent.futures

    def _one(sym):
        try:
            q = fetch_quote_fast(sym, cache_seconds=30)
            price = q.get('price') if q else None
            # get name/sector from fast_info only — avoid the slow t.info call entirely
            try:
                t = get_ticker_obj(sym)
                t._fast_info = None
                fi = t.fast_info
                name = getattr(fi, 'name', None) or sym
                # sector not in fast_info — use a lightweight history call for sector only
                sector = 'Other'
            except Exception:
                name = sym
                sector = 'Other'
            return {'price': price, 'name': name, 'sector': sector}
        except Exception:
            return {'price': None, 'name': sym, 'sector': 'Other'}

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_one, sym): sym for sym in symbols}
        for fut in concurrent.futures.as_completed(futures, timeout=15):
            sym = futures[fut]
            try:
                results[sym] = fut.result()
            except Exception:
                results[sym] = {'price': None, 'name': sym, 'sector': 'Other'}
    return results


def build_portfolio_view(c):
    c.clear()
    with c:
        pv = portfolio_value()
        gl = round(pv - account['start_cash'], 2)
        gl_pct = round(gl / account['start_cash'] * 100, 2)
        gl_col = 'var(--green)' if gl >= 0 else 'var(--red)'
        stats = get_perf_stats()
        n_pos = len(account['positions'])
        best = max(account['positions'].items(), key=lambda x: (fetch_quote_fast(x[0]) or {}).get('price', x[1]['avg_cost']), default=(None, None)) if account['positions'] else (None, None)
        best_sym = best[0] or '--'
        best_pos = account['positions'].get(best_sym)
        best_pct = round((((fetch_quote_fast(best_sym) or {}).get('price') or best_pos['avg_cost']) - best_pos['avg_cost']) / best_pos['avg_cost'] * 100, 2) if best_pos else 0

        # ── 4 stat cards ──────────────────────────────────────────────────────
        ICONS = ['ti-wallet', 'ti-trending-up', 'ti-chart-pie', 'ti-star']
        ICON_COLS = ['#6366f1', 'var(--green)' if gl >= 0 else 'var(--red)', '#f59e0b', '#ec4899']
        cards = [
            ('Portfolio Value', '${:,.2f}'.format(pv), '${:+,.2f}  ({:+.1f}%)'.format(gl, gl_pct), gl_col),
            ('Day Change', '${:+,.2f}'.format(gl), '{:+.2f}%'.format(gl_pct), gl_col),
            ('Total Positions', str(n_pos), '{} completed trades'.format(stats.get('total_trades', 0)), 'var(--text3)'),
            ('Best Performer', best_sym, '{:+.2f}%'.format(best_pct), 'var(--green)' if best_pct >= 0 else 'var(--red)'),
        ]
        with R('gap:10px;margin-bottom:16px;flex-wrap:wrap;'):
            for (lbl, val, sub, scol), ico, icol in zip(cards, ICONS, ICON_COLS):
                with D('flex:1;min-width:160px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:16px 18px;position:relative;overflow:hidden;'):
                    with R('justify-content:space-between;align-items:flex-start;margin-bottom:10px;'):
                        L(lbl, 'font-size:11px;color:var(--text2);font-family:var(--mono);letter-spacing:.5px;')
                        with D('width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;background:{}22;'.format(icol)):
                            ICO(ico, 'font-size:16px;color:{};'.format(icol))
                    L(val, 'font-size:22px;font-weight:700;color:var(--white);font-family:var(--mono);margin-bottom:4px;')
                    with R('gap:5px;align-items:center;'):
                        D('width:6px;height:6px;border-radius:50%;background:{};'.format(scol))
                        L(sub, 'font-size:10px;color:{};font-family:var(--mono);'.format(scol))

        # ── Trade ticket (collapsible feel — compact row) ─────────────────────
        with D('background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:16px;'):
            with R('gap:6px;margin-bottom:10px;align-items:center;flex-wrap:wrap;'):
                L('QUICK TRADE', '').classes('sec-label')
                refs['trade_ticker'] = L(state['ticker'], 'font-size:13px;font-weight:600;color:var(--white);font-family:var(--mono);')
                refs['trade_price'] = L('$--', 'font-size:13px;color:var(--accent);font-family:var(--mono);')
                D('flex:1;')
                def reset_account():
                    account['cash'] = account['start_cash']
                    account['positions'].clear()
                    account['history'].clear()
                    ui.notify('Account reset', type='info')
                    build_portfolio_view(c)
                ui.button('Reset', on_click=reset_account).style('font-size:9px;color:var(--red);background:transparent;border:1px solid #ef444433;border-radius:4px;padding:2px 8px;')
            with R('gap:8px;align-items:flex-end;flex-wrap:wrap;'):
                shares_in = ui.input(placeholder='Shares').props('outlined dense').style('width:120px;')
                with R('gap:3px;flex-wrap:wrap;align-items:center;'):
                    for amt in ['1', '5', '10', '50']:
                        ui.button(amt, on_click=lambda e, a=amt: setattr(shares_in, 'value', a)).classes('pill').style('font-size:9px;padding:1px 6px;')
                    h_tmp, _ = fetch(state['ticker'], '1d', need_info=False)
                    curr_p = round(float(h_tmp['Close'].iloc[-1]), 2) if not h_tmp.empty else 1
                    for da in [100, 500, 1000]:
                        sc = round(da / curr_p, 4)
                        ui.button('${}'.format(da), on_click=lambda e, s=sc: setattr(shares_in, 'value', str(s))).classes('pill').style('font-size:9px;padding:1px 6px;color:var(--amber);')
                def do_buy():
                    ok, msg = buy_stock(state['ticker'], shares_in.value or 1)
                    ui.notify(msg, type='positive' if ok else 'negative')
                    if ok: shares_in.value = ''; build_portfolio_view(c)
                def do_sell():
                    ok, msg = sell_stock(state['ticker'], shares_in.value or 1)
                    ui.notify(msg, type='positive' if ok else 'negative')
                    if ok: shares_in.value = ''; build_portfolio_view(c)
                ui.button('BUY', on_click=do_buy).style('background:#10b98122;border:1px solid #10b98150;color:var(--green);border-radius:6px;font-family:var(--mono);font-weight:700;font-size:13px;padding:7px 20px;')
                ui.button('SELL', on_click=do_sell).style('background:#ef444422;border:1px solid #ef444450;color:var(--red);border-radius:6px;font-family:var(--mono);font-weight:700;font-size:13px;padding:7px 20px;')

        if not account['positions']:
            with D('background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:40px;text-align:center;'):
                ICO('ti-chart-pie-2', 'color:var(--text3);font-size:40px;')
                L('No positions yet', 'font-size:14px;color:var(--text);margin-top:12px;margin-bottom:6px;font-weight:500;')
                L('Search a stock and use the trade panel above to open your first position.', 'font-size:11px;color:var(--text3);')
            return

        body_ref = D('display:flex;flex-direction:column;gap:14px;width:100%;')
        with body_ref:
            L('Loading portfolio...', 'font-size:11px;color:var(--text3);')

        async def load_body():
            symbols = list(account['positions'].keys())
            try:
                quotes = await run.io_bound(fetch_holdings_batch, symbols)
            except Exception:
                quotes = {}

            holdings = []
            total_val = 0
            sector_totals = {}
            for sym, pos in account['positions'].items():
                q = quotes.get(sym) or {}
                curr = q.get('price') or pos['avg_cost']
                name_p = q.get('name', sym)
                sector_p = q.get('sector', 'Other')
                val = round(curr * pos['shares'], 2)
                gl_p = round((curr - pos['avg_cost']) * pos['shares'], 2)
                gl_pct_p = round((curr - pos['avg_cost']) / pos['avg_cost'] * 100, 2) if pos['avg_cost'] else 0
                holdings.append({'sym': sym, 'name': name_p, 'sector': sector_p, 'shares': pos['shares'],
                                  'avg': pos['avg_cost'], 'curr': curr, 'val': val, 'gl': gl_p, 'gl_pct': gl_pct_p})
                total_val += val
                sector_totals[sector_p] = sector_totals.get(sector_p, 0) + val

            holdings.sort(key=lambda x: x['val'], reverse=True)
            palette = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#3b82f6', '#f97316', '#8b5cf6', '#14b8a6', '#06b6d4', '#84cc16']

            # Build portfolio history from trade log
            hist_labels, hist_values = [], []
            running = account['start_cash']
            if account['history']:
                for trade in sorted(account['history'], key=lambda x: x.get('date', '')):
                    hist_labels.append(trade.get('date', '')[:10])
                    cost = trade['shares'] * trade['price']
                    if trade['action'] == 'BUY':
                        running -= cost
                    else:
                        running += cost
                    hist_values.append(round(running + total_val, 2))
            if not hist_labels:
                hist_labels = ['Start', 'Now']
                hist_values = [account['start_cash'], round(total_val + account['cash'], 2)]

            body_ref.clear()
            with body_ref:
                # ── Main row: history chart + donut ───────────────────────────
                with R('gap:12px;align-items:stretch;flex-wrap:wrap;margin-bottom:12px;'):

                    # Portfolio history chart
                    with D('flex:2;min-width:300px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:18px;'):
                        with R('justify-content:space-between;align-items:center;margin-bottom:14px;'):
                            with C('gap:2px;'):
                                L('Portfolio History', 'font-size:13px;font-weight:600;color:var(--white);')
                                L('Simulated value over trade history', 'font-size:9px;color:var(--text3);font-family:var(--mono);')
                            with R('gap:3px;align-items:center;'):
                                D('width:8px;height:8px;border-radius:50%;background:#6366f1;')
                                L('Total Value', 'font-size:9px;color:var(--text2);font-family:var(--mono);')
                        with D('height:180px;'):
                            ui.element('canvas').props('id="portfolio-hist"').style('width:100%;height:180px;')

                    # Donut chart
                    with D('flex:1;min-width:240px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:18px;'):
                        L('Portfolio Composition', 'font-size:13px;font-weight:600;color:var(--white);margin-bottom:14px;')
                        with R('gap:16px;align-items:center;'):
                            with D('width:150px;height:150px;position:relative;flex-shrink:0;'):
                                ui.element('canvas').props('id="portfolio-pie"').style('width:150px;height:150px;')
                                with C('position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);align-items:center;pointer-events:none;'):
                                    L('${:,.0f}'.format(pv), 'font-size:13px;font-weight:700;color:var(--white);font-family:var(--mono);')
                                    L('total', 'font-size:8px;color:var(--text3);font-family:var(--mono);')
                            with C('gap:5px;flex:1;'):
                                for i, hd in enumerate(holdings[:6]):
                                    pct = (hd['val'] / total_val * 100) if total_val else 0
                                    with R('justify-content:space-between;align-items:center;'):
                                        with R('gap:6px;align-items:center;'):
                                            D('width:8px;height:8px;border-radius:2px;background:{};flex-shrink:0;'.format(palette[i % len(palette)]))
                                            L(hd['sym'], 'font-size:10px;color:var(--white);font-family:var(--mono);font-weight:500;')
                                        L('{:.1f}%'.format(pct), 'font-size:10px;color:var(--text2);font-family:var(--mono);')

                # ── Holdings table ─────────────────────────────────────────────
                with D('background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;'):
                    with R('padding:14px 16px;border-bottom:1px solid var(--border);align-items:center;gap:8px;'):
                        L('Holdings', 'font-size:13px;font-weight:600;color:var(--white);')
                        with D('background:var(--bg3);border-radius:5px;padding:2px 8px;'):
                            L('{} positions'.format(len(holdings)), 'font-size:9px;color:var(--text2);font-family:var(--mono);')
                    # table header
                    with R('padding:8px 16px;background:var(--bg3);'):
                        for hdr, w in [('ASSET', 'flex:2;'), ('SHARES', 'flex:1;'), ('AVG COST', 'flex:1;'), ('CURRENT', 'flex:1;'), ('VALUE', 'flex:1;'), ('P&L', 'flex:1;')]:
                            L(hdr, 'font-size:8px;color:var(--text3);font-family:var(--mono);letter-spacing:.8px;{}'.format(w))
                    for hd in holdings:
                        pc = 'var(--green)' if hd['gl'] >= 0 else 'var(--red)'
                        with D('border-bottom:1px solid var(--border);').on('click', lambda e, s=hd['sym']: ui.timer(0.05, lambda: load_stock(s), once=True)):
                            with R('padding:12px 16px;align-items:center;').classes('trade-row').style('border-radius:0;margin:0;'):
                                with R('gap:8px;align-items:center;flex:2;'):
                                    D('width:10px;height:10px;border-radius:3px;background:{};flex-shrink:0;'.format(palette[holdings.index(hd) % len(palette)]))
                                    with C('gap:1px;'):
                                        L(hd['sym'], 'font-size:12px;font-weight:600;color:var(--white);font-family:var(--mono);')
                                        L(hd['name'][:20], 'font-size:9px;color:var(--text3);')
                                L(str(hd['shares']), 'font-size:11px;color:var(--white);font-family:var(--mono);flex:1;')
                                L('${:.2f}'.format(hd['avg']), 'font-size:11px;color:var(--text2);font-family:var(--mono);flex:1;')
                                L('${:.2f}'.format(hd['curr']), 'font-size:11px;color:var(--white);font-family:var(--mono);flex:1;')
                                L('${:,.2f}'.format(hd['val']), 'font-size:11px;font-weight:500;color:var(--white);font-family:var(--mono);flex:1;')
                                with C('gap:1px;flex:1;'):
                                    L('{:+.2f}%'.format(hd['gl_pct']), 'font-size:11px;font-weight:600;color:{};font-family:var(--mono);'.format(pc))
                                    L('${:+,.2f}'.format(hd['gl']), 'font-size:9px;color:{};font-family:var(--mono);'.format(pc))

            pie_labels = [hd['sym'] for hd in holdings]
            pie_values = [hd['val'] for hd in holdings]
            pie_colors = [palette[i % len(palette)] for i in range(len(holdings))]
            if account['cash'] > 0:
                pie_labels.append('Cash')
                pie_values.append(account['cash'])
                pie_colors.append('#2a2a3a')
            ui.timer(0.15, lambda: ui.run_javascript('smPieRender({},{},{})'.format(json.dumps(pie_labels), json.dumps(pie_values), json.dumps(pie_colors))), once=True)
            ui.timer(0.15, lambda: ui.run_javascript('smHistRender({},{})'.format(json.dumps(hist_labels), json.dumps(hist_values))), once=True)

        ui.timer(0.05, load_body, once=True)


def build_history_view(c):
    c.clear()
    with c:
        stats = get_perf_stats()
        pv = portfolio_value()
        total_ret = round((pv - account['start_cash']) / account['start_cash'] * 100, 2)
        ret_col = 'var(--green)' if total_ret >= 0 else 'var(--red)'

        L('Trading Performance', 'font-size:15px;font-weight:600;color:var(--white);margin-bottom:10px;')

        with R('gap:8px;margin-bottom:12px;flex-wrap:wrap;'):
            for lbl_t, val_t, col_t in [
                ('TOTAL RETURN', '{:+.2f}%'.format(total_ret), ret_col),
                ('WIN RATE', '{:.1f}%'.format(stats.get('win_rate', 0)), 'var(--green)' if stats.get('win_rate', 0) >= 50 else 'var(--red)'),
                ('TRADES', str(stats.get('total_trades', 0)), 'var(--white)'),
                ('WINS / LOSSES', '{} / {}'.format(stats.get('wins', 0), stats.get('losses', 0)), 'var(--text)'),
                ('BEST TRADE', '+${:.2f}'.format(stats.get('best_trade', 0)), 'var(--green)'),
                ('WORST TRADE', '${:.2f}'.format(stats.get('worst_trade', 0)), 'var(--red)'),
                ('AVG P&L', '${:+.2f}'.format(stats.get('avg_gl', 0)), 'var(--accent)'),
            ]:
                with D('flex:1;min-width:100px;background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:10px 12px;'):
                    L(lbl_t, 'font-size:8px;color:var(--text3);font-family:var(--mono);letter-spacing:.8px;margin-bottom:4px;')
                    L(val_t, 'font-size:13px;font-weight:600;color:{};font-family:var(--mono);'.format(col_t))

        if stats.get('total_trades', 0):
            wp = int(stats.get('win_rate', 0))
            with D('background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:12px;margin-bottom:12px;'):
                with R('justify-content:space-between;margin-bottom:6px;'):
                    L('SIGNAL ACCURACY', '').classes('sec-label')
                    L('{} wins / {} losses'.format(stats['wins'], stats['losses']), 'font-size:10px;color:var(--text2);font-family:var(--mono);')
                D('height:6px;border-radius:3px;background:linear-gradient(90deg,var(--green) {}%,var(--red) {}%);'.format(wp, wp))

        with D('background:var(--bg2);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:6px;padding:12px;margin-bottom:12px;'):
            with R('gap:6px;margin-bottom:6px;'):
                ICO('ti-robot', 'font-size:13px;color:var(--accent);')
                L('AI COACHING TIP', 'font-size:9px;color:var(--accent);font-family:var(--mono);letter-spacing:1px;')
            if not stats.get('total_trades'):
                tip = 'Start by buying a stock you know. Try $100 in AAPL or NVDA and watch how indicators affect price.'
            elif stats.get('win_rate', 0) >= 60:
                tip = 'Great win rate of {:.1f}%! Consider increasing position sizes slightly. Track which indicators you relied on most for winners.'.format(stats['win_rate'])
            elif stats.get('win_rate', 0) >= 40:
                tip = 'Balanced performance at {:.1f}% wins. Review your losing trades - did you ignore RSI signals? Set stop-losses to protect gains.'.format(stats['win_rate'])
            else:
                tip = 'Win rate at {:.1f}% - focus on quality over quantity. Wait for RSI below 40 and MACD bullish crossover before buying.'.format(stats['win_rate'])
            L(tip, 'font-size:11px;color:var(--text);line-height:1.6;')

        L('TRADE HISTORY', '').classes('sec-label').style('margin-bottom:6px;')
        if not account['history']:
            L('No trades yet. Go to the Trade tab and make your first trade!', 'font-size:11px;color:var(--text3);font-family:var(--mono);')
        else:
            rows = []
            for t in reversed(account['history']):
                gl_str = '${:+.2f}'.format(t.get('gl', 0)) if 'gl' in t else '--'
                gl_pct_str = '{:+.1f}%'.format(t.get('gl_pct', 0)) if 'gl_pct' in t else '--'
                rows.append({'date': t['date'], 'type': t['type'], 'ticker': t['ticker'], 'shares': str(t['shares']), 'price': '${:.2f}'.format(t['price']), 'total': '${:,.2f}'.format(t['total']), 'gl': gl_str, 'gl_pct': gl_pct_str})
            cols = [
                {'name': 'date', 'label': 'DATE', 'field': 'date', 'align': 'left'},
                {'name': 'type', 'label': 'TYPE', 'field': 'type'},
                {'name': 'ticker', 'label': 'TICKER', 'field': 'ticker'},
                {'name': 'shares', 'label': 'SHARES', 'field': 'shares'},
                {'name': 'price', 'label': 'PRICE', 'field': 'price'},
                {'name': 'total', 'label': 'TOTAL', 'field': 'total'},
                {'name': 'gl', 'label': 'P&L', 'field': 'gl'},
                {'name': 'gl_pct', 'label': 'P&L%', 'field': 'gl_pct'},
            ]
            ui.table(columns=cols, rows=rows, row_key='date').style('font-family:var(--mono);font-size:11px;background:transparent;color:var(--text);width:100%;')

            def export_history():
                df = pd.DataFrame(account['history'])
                csv = df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                ui.run_javascript('var a=document.createElement("a");a.href="data:text/csv;base64,' + b64 + '";a.download="trade_history.csv";a.click();')
            ui.button('Export History CSV', on_click=export_history).classes('pill').style('margin-top:8px;color:var(--accent);border-color:var(--accent)33;font-size:11px;')

def is_us_market_open():
    now_utc = datetime.utcnow()
    et_hour = (now_utc.hour - 5) % 24
    weekday = now_utc.weekday()
    if weekday >= 5:
        return False
    return 9 <= et_hour < 16

_explorer_cache = {}
_live_price_cache = {}

_ticker_objects = {}

def get_ticker_obj(symbol):
    if symbol not in _ticker_objects:
        _ticker_objects[symbol] = yf.Ticker(symbol)
    return _ticker_objects[symbol]

def fetch_quote_fast(symbol, cache_seconds=45):
    cache_store = _explorer_cache if cache_seconds >= 45 else _live_price_cache
    if symbol in cache_store:
        ts, data = cache_store[symbol]
        if (datetime.now() - ts).seconds < cache_seconds:
            return data
    try:
        t = get_ticker_obj(symbol)
        t._fast_info = None  # force a fresh FastInfo - it permanently caches last_price after first read
        fi = t.fast_info
        price = fi.get('lastPrice')
        prev = fi.get('previousClose') or fi.get('regularMarketPreviousClose')
        if price is None:
            return None
        chg_pct = round((price - prev) / prev * 100, 2) if prev else 0
        data = {'price': round(float(price), 2), 'chg_pct': chg_pct, 'cap': None}
        cache_store[symbol] = (datetime.now(), data)
        return data
    except Exception:
        return None

def quick_add_to_watchlist(sym):
    sym = sym.strip().upper()
    if not sym:
        return
    if sym in WATCHLIST:
        ui.notify('{} is already in your watchlist'.format(sym), type='info')
        return
    WATCHLIST.append(sym)
    if 'render_watchlist' in global_funcs:
        global_funcs['render_watchlist']()
    save_state()
    ui.notify('Added {} to watchlist'.format(sym), type='positive')


def fetch_quotes_batch(symbols):
    """Fetch multiple quotes concurrently using a thread pool - runs off the main event loop."""
    import concurrent.futures
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_quote_fast, sym): sym for sym in symbols}
        for fut in concurrent.futures.as_completed(futures, timeout=20):
            sym = futures[fut]
            try:
                results[sym] = fut.result()
            except Exception:
                results[sym] = None
    return results


def build_explorer_view(c):
    c.clear()
    with c:
        market_open = is_us_market_open()
        with R('justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px;'):
            with C('gap:2px;'):
                L('Market Explorer', 'font-size:15px;font-weight:600;color:var(--white);')
                L('Browse stocks, ETFs, and crypto by sector or index', 'font-size:10px;color:var(--text2);font-family:var(--mono);')
            with R('gap:6px;align-items:center;'):
                dot_color = 'var(--green)' if market_open else 'var(--red)'
                D('width:6px;height:6px;border-radius:50%;background:{};'.format(dot_color))
                L('US Market {}'.format('Open' if market_open else 'Closed'), 'font-size:10px;color:{};font-family:var(--mono);'.format(dot_color))

        sectors = ['All'] + sorted(set(s['sector'] for s in MARKET_UNIVERSE))
        indexes = ['All'] + sorted(set(s['index'] for s in MARKET_UNIVERSE))

        with C('gap:8px;width:100%;'):
            with D('background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px 12px 6px;margin-bottom:10px;'):
                with R('gap:10px;flex-wrap:wrap;align-items:flex-start;'):
                    sector_sel = ui.select(sectors, value=explorer_filters['sector'], label='Sector').props('outlined dense').style('width:170px;')
                    index_sel = ui.select(indexes, value=explorer_filters['index'], label='Index / Type').props('outlined dense').style('width:150px;')
                    status_sel = ui.select(['All', 'Gainers', 'Losers'], value=explorer_filters['movement'], label='Movement').props('outlined dense').style('width:120px;')
                    name_search = ui.input(value=explorer_filters['search'], placeholder='Search name or symbol...').props('outlined dense').style('width:200px;')

            grid_ref = D('display:grid;grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));gap:8px;width:100%;')
            explorer_state = {'token': 0}

            def open_stock(sym):
                state['ticker'] = sym.strip().upper()
                state['last_chart_js'] = None
                switch_view('chart')

            def render_cards(cards_data):
                grid_ref.clear()
                with grid_ref:
                    if not cards_data:
                        L('No matches. Try different filters.', 'font-size:11px;color:var(--text3);grid-column:1/-1;')
                    for item, q in cards_data:
                        up = q['chg_pct'] >= 0
                        chg_color = 'var(--green)' if up else 'var(--red)'
                        with D('background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px;cursor:pointer;position:relative;').on(
                            'click', lambda e, s=item['symbol']: open_stock(s)
                        ).classes('trade-row'):
                            with D('position:absolute;top:8px;right:8px;width:18px;height:18px;border-radius:4px;background:var(--bg3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:5;').on(
                                'click', lambda e, s=item['symbol']: quick_add_to_watchlist(s),
                                js_handler='(event) => { event.stopPropagation(); emit(event); }'
                            ).tooltip('Add to watchlist'):
                                ICO('ti-plus', 'color:var(--accent);', 11)
                            with R('justify-content:space-between;align-items:flex-start;margin-bottom:6px;padding-right:20px;'):
                                with C('gap:1px;'):
                                    L(item['symbol'], 'font-size:13px;font-weight:600;color:var(--white);font-family:var(--mono);')
                                    L(item['name'][:22], 'font-size:9px;color:var(--text2);')
                                L(item['sector'][:12], 'font-size:8px;color:var(--text3);font-family:var(--mono);background:var(--bg3);padding:2px 5px;border-radius:3px;')
                            with R('justify-content:space-between;align-items:baseline;'):
                                L('${:,.2f}'.format(q['price']), 'font-size:14px;font-weight:600;color:var(--white);font-family:var(--mono);')
                                L('{:+.2f}%'.format(q['chg_pct']), 'font-size:11px;color:{};font-family:var(--mono);'.format(chg_color))

            async def render_grid():
                explorer_state['token'] += 1
                my_token = explorer_state['token']

                explorer_filters['sector'] = sector_sel.value
                explorer_filters['index'] = index_sel.value
                explorer_filters['movement'] = status_sel.value
                explorer_filters['search'] = name_search.value or ''

                items = MARKET_UNIVERSE
                if sector_sel.value != 'All':
                    items = [s for s in items if s['sector'] == sector_sel.value]
                if index_sel.value != 'All':
                    items = [s for s in items if s['index'] == index_sel.value]
                if name_search.value:
                    q_text = name_search.value.lower()
                    items = [s for s in items if q_text in s['name'].lower() or q_text in s['symbol'].lower()]

                grid_ref.clear()
                with grid_ref:
                    L('Loading live prices...', 'font-size:11px;color:var(--text3);grid-column:1/-1;')

                symbols = [s['symbol'] for s in items]
                try:
                    quotes = await run.io_bound(fetch_quotes_batch, symbols)
                except Exception:
                    quotes = {}

                if my_token != explorer_state['token']:
                    return  # filters changed again while we were fetching - discard stale results

                cards_data = []
                for item in items:
                    q = quotes.get(item['symbol'])
                    if q is None:
                        continue
                    if status_sel.value == 'Gainers' and q['chg_pct'] <= 0:
                        continue
                    if status_sel.value == 'Losers' and q['chg_pct'] >= 0:
                        continue
                    cards_data.append((item, q))

                render_cards(cards_data)

            def trigger_render():
                asyncio.create_task(render_grid())

            sector_sel.on('update:model-value', lambda e: trigger_render())
            index_sel.on('update:model-value', lambda e: trigger_render())
            status_sel.on('update:model-value', lambda e: trigger_render())
            name_search.on('update:model-value', lambda e: trigger_render())

        ui.timer(0.05, render_grid, once=True)


def build_report_view(c):
    c.clear()
    with c:
        h, info = fetch(state['ticker'], state['period'])
        if h.empty:
            L('No data. Search a stock first.', 'color:var(--text2);')
            return
        close = h['Close']
        price = round(float(close.iloc[-1]), 2)
        chg = round((price - float(close.iloc[0])) / float(close.iloc[0]) * 100, 2)
        _rsi = calc_rsi(close)
        m_val, sig_v, bull = calc_macd(close)
        bb_u, bb_l, bpct = calc_bb(close)
        lv, av = int(h['Volume'].iloc[-1]), int(h['Volume'].mean())
        vpct = round((lv - av) / av * 100, 1) if av else 0
        _atr = calc_atr(h)
        h52 = round(float(h['High'].max()), 2)
        l52 = round(float(h['Low'].min()), 2)
        sma20v = round(float(sma(close, 20).iloc[-1]), 2)
        sma50v = round(float(sma(close, 50).iloc[-1]), 2)
        ema12v = round(float(ema(close, 12).iloc[-1]), 2)
        name = info.get('longName', state['ticker'])

        bull_sigs = []
        bear_sigs = []
        if _rsi < 30:
            bull_sigs.append('RSI oversold at {} - potential reversal opportunity'.format(_rsi))
        if _rsi > 70:
            bear_sigs.append('RSI overbought at {} - watch for pullback'.format(_rsi))
        if 30 <= _rsi <= 70:
            bull_sigs.append('RSI healthy at {} - momentum intact'.format(_rsi))
        if bull:
            bull_sigs.append('MACD bullish crossover ({:+.2f} vs signal {:.2f})'.format(m_val, sig_v))
        else:
            bear_sigs.append('MACD bearish ({:+.2f} below signal {:.2f})'.format(m_val, sig_v))
        if bpct > 80:
            bear_sigs.append('Near upper Bollinger Band ({:.0f}%B) - overbought risk'.format(bpct))
        if bpct < 20:
            bull_sigs.append('Near lower Bollinger Band ({:.0f}%B) - oversold opportunity'.format(bpct))
        if price > sma20v:
            bull_sigs.append('Above SMA20 ${} - short-term uptrend'.format(sma20v))
        else:
            bear_sigs.append('Below SMA20 ${} - short-term weakness'.format(sma20v))
        if price > sma50v:
            bull_sigs.append('Above SMA50 ${} - medium-term strength'.format(sma50v))
        else:
            bear_sigs.append('Below SMA50 ${} - medium-term caution'.format(sma50v))
        if vpct > 20:
            bull_sigs.append('Volume {:+.1f}% above average - strong institutional activity'.format(vpct))
        if vpct < -20:
            bear_sigs.append('Volume {:.1f}% below average - weak conviction'.format(vpct))
        if price >= h52 * 0.95:
            bear_sigs.append('Near 52-week high ${} - limited near-term upside'.format(h52))
        if price <= l52 * 1.08:
            bull_sigs.append('Near 52-week low ${} - historically discounted'.format(l52))

        total = len(bull_sigs) + len(bear_sigs)
        bp = int(len(bull_sigs) / total * 100) if total else 50
        ov = 'BULLISH' if bp >= 60 else ('BEARISH' if bp <= 40 else 'NEUTRAL')
        ov_col = 'var(--green)' if ov == 'BULLISH' else ('var(--red)' if ov == 'BEARISH' else 'var(--amber)')

        with R('justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;'):
            with C('gap:2px;'):
                L(name, 'font-size:14px;font-weight:600;color:var(--white);')
                L('Report - {}'.format(datetime.now().strftime('%d %b %Y %H:%M')), 'font-size:10px;color:var(--text2);font-family:var(--mono);')
            with R('gap:6px;'):
                if PDF_OK:
                    ui.button('Download PDF', on_click=lambda: gen_pdf(name, state['ticker'], price, chg, _rsi, m_val, sig_v, bull, bb_u, bb_l, bpct, sma20v, sma50v, vpct, _atr, bull_sigs, bear_sigs, ov, info)).classes('pill').style('color:var(--amber);border-color:var(--amber)33;')

        with R('background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:14px;margin-bottom:8px;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;'):
            with C('gap:3px;'):
                L('OVERALL SIGNAL', '').classes('sec-label')
                L(ov, 'font-size:20px;font-weight:600;color:{};font-family:var(--mono);'.format(ov_col))
                L('{}% bullish / {}% bearish'.format(bp, 100 - bp), 'font-size:10px;color:var(--text2);font-family:var(--mono);')
                D('height:5px;border-radius:3px;background:linear-gradient(90deg,var(--green) {}%,var(--red) {}%);margin-top:4px;width:160px;'.format(bp, bp))
            with C('align-items:flex-end;gap:3px;'):
                L('${:,.2f}'.format(price), 'font-size:20px;font-weight:600;color:var(--white);font-family:var(--mono);')
                col_ch = 'var(--green)' if chg >= 0 else 'var(--red)'
                L('{:+.2f}% over {}'.format(chg, state['period']), 'font-size:11px;color:{};font-family:var(--mono);'.format(col_ch))

        # Plain-English quick take
        quick_take = '{} is trading at ${:,.2f}, {} over the {} period. '.format(name, price, '{:+.1f}%'.format(chg), state['period'])
        if ov == 'BULLISH':
            quick_take += 'Most signals point upward right now, suggesting positive momentum.'
        elif ov == 'BEARISH':
            quick_take += 'Most signals point downward right now, suggesting caution.'
        else:
            quick_take += 'Signals are mixed, suggesting a wait-and-see approach.'

        with D('').classes('card').style('margin-bottom:8px;'):
            L('QUICK TAKE', '').classes('sec-label').style('margin-bottom:6px;')
            L(quick_take, 'font-size:12px;color:var(--text);line-height:1.6;')

        with R('gap:8px;align-items:flex-start;flex-wrap:wrap;'):
            with C('flex:1;min-width:200px;gap:6px;'):
                with D('').classes('card'):
                    L('PRICE SNAPSHOT', '').classes('sec-label').style('margin-bottom:6px;')
                    for met, val in [
                        ("Today's range", '${:.2f} - ${:.2f}'.format(round(float(h['Low'].iloc[-1]), 2), round(float(h['High'].iloc[-1]), 2))),
                        ('52-week range', '${} - ${}'.format(l52, h52)),
                        ('20-day average', '${}'.format(sma20v)),
                        ('50-day average', '${}'.format(sma50v)),
                        ('Volume today', fmt_vol(lv)),
                        ('Average volume', fmt_vol(av)),
                    ]:
                        with R('justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--bg3);'):
                            L(met, 'font-size:11px;color:var(--text2);')
                            L(val, 'font-size:11px;color:var(--white);font-family:var(--mono);font-weight:500;')

                with D('').classes('card'):
                    L('COMPANY BASICS', '').classes('sec-label').style('margin-bottom:6px;')
                    eps_val = info.get('trailingEps')
                    pe_val = info.get('trailingPE')
                    beta_val = info.get('beta')
                    div_val = info.get('dividendYield')
                    for met, val in [
                        ('Market cap', fmt_cap(info.get('marketCap'))),
                        ('Sector', info.get('sector', 'N/A')),
                        ('P/E ratio', '{:.1f}x'.format(pe_val) if pe_val else 'N/A'),
                        ('Earnings per share', '${:.2f}'.format(eps_val) if eps_val else 'N/A'),
                        ('Dividend yield', '{:.2f}%'.format(div_val * 100) if div_val else 'N/A'),
                        ('Beta (volatility vs market)', '{:.2f}'.format(beta_val) if beta_val else 'N/A'),
                    ]:
                        with R('justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--bg3);'):
                            L(met, 'font-size:11px;color:var(--text2);')
                            L(str(val), 'font-size:11px;color:var(--white);font-family:var(--mono);font-weight:500;')

            with C('flex:2;min-width:260px;gap:6px;'):
                with D('').classes('card'):
                    L('BULLISH SIGNALS', '').classes('sec-label').style('margin-bottom:6px;')
                    for sig in bull_sigs:
                        with R('gap:7px;padding:4px 0;border-bottom:1px solid var(--bg3);'):
                            D('width:4px;height:4px;border-radius:50%;background:var(--green);flex-shrink:0;margin-top:3px;')
                            L(sig, 'font-size:11px;color:var(--text);line-height:1.4;')
                    if not bull_sigs:
                        L('No bullish signals.', 'font-size:11px;color:var(--text3);')
                with D('').classes('card'):
                    L('BEARISH SIGNALS', '').classes('sec-label').style('margin-bottom:6px;')
                    for sig in bear_sigs:
                        with R('gap:7px;padding:4px 0;border-bottom:1px solid var(--bg3);'):
                            D('width:4px;height:4px;border-radius:50%;background:var(--red);flex-shrink:0;margin-top:3px;')
                            L(sig, 'font-size:11px;color:var(--text);line-height:1.4;')
                    if not bear_sigs:
                        L('No bearish signals.', 'font-size:11px;color:var(--text3);')
                if info.get('longBusinessSummary'):
                    with D('').classes('card'):
                        L('ABOUT', '').classes('sec-label').style('margin-bottom:6px;')
                        L(info['longBusinessSummary'][:500] + '...', 'font-size:11px;color:var(--text);line-height:1.6;')

def build_news_view(c):
    c.clear()
    with c:
        L('Market News and Alerts', 'font-size:15px;font-weight:600;color:var(--white);margin-bottom:10px;')

        with D('').classes('card').style('margin-bottom:12px;'):
            L('PRICE ALERTS', '').classes('sec-label').style('margin-bottom:8px;')
            with R('gap:6px;margin-bottom:8px;flex-wrap:wrap;'):
                al_sym = ui.input(placeholder='Ticker').props('outlined dense').style('width:90px;')
                al_ab = ui.input(placeholder='Alert above $').props('outlined dense').style('width:120px;')
                al_bl = ui.input(placeholder='Alert below $').props('outlined dense').style('width:120px;')

                def set_alert():
                    sym = al_sym.value.strip().upper()
                    if not sym:
                        return
                    alerts[sym] = {'above': float(al_ab.value) if al_ab.value else None, 'below': float(al_bl.value) if al_bl.value else None}
                    al_sym.value = al_ab.value = al_bl.value = ''
                    build_news_view(c)
                ui.button('Set', on_click=set_alert).classes('pill active').style('font-size:11px;')
            if alerts:
                for sym, al in list(alerts.items()):
                    with R('gap:8px;background:var(--bg3);border:1px solid var(--border);border-radius:5px;padding:5px 10px;margin-bottom:3px;'):
                        L(sym, 'font-size:12px;font-weight:600;color:var(--white);font-family:var(--mono);width:60px;')
                        if al.get('above'):
                            L('Above ${:.2f}'.format(al['above']), 'font-size:11px;color:var(--green);font-family:var(--mono);flex:1;')
                        if al.get('below'):
                            L('Below ${:.2f}'.format(al['below']), 'font-size:11px;color:var(--red);font-family:var(--mono);flex:1;')
                        ui.button('x', on_click=lambda e, s=sym: (alerts.pop(s, None), build_news_view(c))).style('background:transparent;color:var(--text3);font-size:13px;padding:0 4px;min-width:0;')

        tickers_to_watch = [state['ticker']] + list(account['positions'].keys()) + list(alerts.keys())
        seen = set()
        news_items = []
        for sym in list(dict.fromkeys(tickers_to_watch))[:5]:
            for n in fetch_news(sym):
                t = n.get('title', '')
                if t and t not in seen:
                    seen.add(t)
                    time_str = ''
                    raw_t = n.get('pub_time_raw', '')
                    try:
                        if isinstance(raw_t, (int, float)) and raw_t:
                            time_str = datetime.fromtimestamp(raw_t).strftime('%d %b %H:%M')
                        elif isinstance(raw_t, str) and raw_t:
                            time_str = raw_t[:16].replace('T', ' ')
                    except Exception:
                        time_str = ''
                    news_items.append({'sym': sym, 'title': t, 'link': n.get('link', '#'), 'publisher': n.get('publisher', ''), 'time': time_str})

        L('LATEST NEWS', '').classes('sec-label').style('margin-bottom:8px;')
        if not news_items:
            with D('').classes('card').style('text-align:center;padding:20px;'):
                L('No news available right now.', 'font-size:11px;color:var(--text2);margin-bottom:4px;')
                L('Load a stock, add a position, or set an alert - news loads for tracked tickers.', 'font-size:10px;color:var(--text3);')
        for n in news_items[:20]:
            with D('').classes('news-card').on('click', lambda e, url=n['link']: ui.run_javascript('window.open("' + url + '", "_blank")') if url and url != '#' else None):
                with R('justify-content:space-between;margin-bottom:4px;'):
                    L(n['sym'], 'font-size:9px;color:var(--accent);font-family:var(--mono);letter-spacing:1px;background:var(--bg3);padding:1px 5px;border-radius:3px;')
                    L(n['time'], 'font-size:9px;color:var(--text3);font-family:var(--mono);')
                L(n['title'], 'font-size:11px;color:var(--white);line-height:1.4;margin-bottom:3px;')
                L(n['publisher'], 'font-size:9px;color:var(--text2);')

def build_settings_view(c):
    c.clear()
    with c:
        with R('justify-content:space-between;align-items:center;margin-bottom:12px;'):
            L('Settings', 'font-size:15px;font-weight:600;color:var(--white);')
            def reset_all():
                reset_to_defaults()
                ui.notify('All settings, portfolio and watchlist reset to defaults. Restart the app to apply.', type='warning', timeout=6000)
            ui.button('Reset to Defaults', on_click=reset_all).style(
                'font-size:10px;color:var(--red);background:transparent;border:1px solid #ef444444;'
                'border-radius:5px;padding:4px 10px;font-family:var(--mono);'
            )

        with D('').classes('card').style('margin-bottom:12px;'):
            L('AI ADVISOR — GROQ', '').classes('sec-label').style('margin-bottom:8px;')
            status_color = 'var(--green)' if ai_state['enabled'] else 'var(--amber)'
            L('Status: {}'.format('Connected (Llama 3.3 70B)' if ai_state['enabled'] else 'Not connected'), 'font-size:12px;color:{};font-family:var(--mono);margin-bottom:8px;'.format(status_color))
            if not ai_state['enabled'] and ai_state['last_error']:
                L('Last error: {}'.format(ai_state['last_error'][:150]), 'font-size:9px;color:var(--red);font-family:var(--mono);margin-bottom:8px;')
            with R('gap:6px;flex-wrap:wrap;align-items:center;'):
                key_in = ui.input(placeholder='gsk_...', password=True, password_toggle_button=True).props('outlined dense').style('width:280px;')
                if ai_state['key']:
                    key_in.value = ai_state['key']

                async def connect_ai():
                    ai_state['key'] = key_in.value.strip()
                    ui.notify('Connecting...', type='info', timeout=2000)
                    ok = await run.io_bound(init_ai_client, True)
                    if ok:
                        ui.notify('AI connected successfully!', type='positive')
                    else:
                        ui.notify('Connection failed: {}'.format(ai_state['last_error'][:200]), type='negative', timeout=8000)
                    if 'ai_status_badge' in refs:
                        refs['ai_status_badge'].set_text('ONLINE' if ai_state['enabled'] else 'OFFLINE')
                        refs['ai_status_badge'].style('font-size:8px;font-family:var(--mono);padding:1px 5px;border-radius:3px;{}'.format('color:var(--green);background:#10b98114;border:1px solid #10b98130;' if ai_state['enabled'] else 'color:var(--amber);background:#f59e0b14;border:1px solid #f59e0b30;'))
                    if 'ai_offline_hint' in refs:
                        refs['ai_offline_hint'].style('display:{};'.format('none' if ai_state['enabled'] else 'block'))
                    build_settings_view(c)

                ui.button('Connect', on_click=connect_ai).classes('pill active')
            L('Free API key at console.groq.com — no credit card required.', 'font-size:9px;color:var(--text3);font-family:var(--mono);margin-top:6px;')

        with R('gap:12px;align-items:flex-start;flex-wrap:wrap;'):
            with C('flex:1;min-width:200px;gap:8px;'):
                with D('').classes('card'):
                    L('THEME', '').classes('sec-label').style('margin-bottom:10px;')
                    with R('gap:8px;flex-wrap:wrap;'):
                        def apply_theme(theme_id, th):
                            profile['theme'] = theme_id
                            settings['accent'] = th['accent']
                            js_vars = ';'.join(
                                'document.documentElement.style.setProperty("--{}", "{}")'.format(k, v)
                                for k, v in th.items() if k != 'name'
                            )
                            js_vars += ';document.documentElement.style.setProperty("--green", "{}")'.format(th['accent'])
                            ui.run_javascript(js_vars)
                            save_state()
                            ui.notify('Theme changed to {}'.format(th['name']), type='positive')
                            build_settings_view(c)
                            rebuild_view()

                        for theme_id, th in THEMES.items():
                            is_sel = profile['theme'] == theme_id
                            with D('display:flex;flex-direction:column;align-items:center;gap:4px;cursor:pointer;').on(
                                'click', lambda e, tid=theme_id, t=th: apply_theme(tid, t)
                            ):
                                D('width:36px;height:36px;border-radius:50%;background:{};border:3px solid {};cursor:pointer;'.format(th['accent'], 'var(--white)' if is_sel else 'transparent'))
                                L(th['name'], 'font-size:9px;color:var(--text2);font-family:var(--mono);')

                with D('').classes('card'):
                    L('CHART DEFAULTS', '').classes('sec-label').style('margin-bottom:10px;')
                    def make_setting_toggle(k):
                        def toggle(e):
                            settings[k] = e.value
                        return toggle
                    for key, lbl in [('show_ma20', 'Show MA20 by default'), ('show_ma50', 'Show MA50 by default'), ('show_ema12', 'Show EMA12 by default'), ('show_volume', 'Show Volume bars')]:
                        ui.checkbox(lbl, value=settings[key], on_change=make_setting_toggle(key)).style('margin-bottom:4px;')
                    L('DEFAULT CHART TYPE', '').classes('sec-label').style('margin-top:10px;margin-bottom:6px;')
                    with R('gap:6px;'):
                        for ct in ['Candles', 'Line']:
                            PILL(ct, settings['chart_style'] == ct.lower(), on_click=lambda e, t=ct: (settings.update({'chart_style': t.lower()}), state.update({'chart_type': t.lower()})))

            with C('flex:1;min-width:200px;gap:8px;'):
                with D('').classes('card'):
                    L('DISPLAY', '').classes('sec-label').style('margin-bottom:10px;')
                    def toggle_compact(e):
                        settings['compact_mode'] = e.value
                    def toggle_right_panel(e):
                        settings['right_panel'] = e.value
                    ui.checkbox('Compact mode (smaller spacing)', value=settings.get('compact_mode', False), on_change=toggle_compact)
                    ui.checkbox('Show right panel', value=settings.get('right_panel', True), on_change=toggle_right_panel)

                with D('').classes('card'):
                    L('STARTING CAPITAL', '').classes('sec-label').style('margin-bottom:8px;')
                    L('Current: ${:,.0f}'.format(account['start_cash']), 'font-size:12px;color:var(--text);font-family:var(--mono);margin-bottom:8px;')
                    with R('gap:6px;flex-wrap:wrap;'):
                        for amt in [5000, 10000, 25000, 50000, 100000]:
                            ui.button('${}K'.format(amt // 1000), on_click=lambda e, a=amt: (account.update({'start_cash': a, 'cash': a}), account['positions'].clear(), account['history'].clear(), safe_set('acct_pv', '${:,.2f}'.format(portfolio_value())), ui.notify('Account reset to ${:,}'.format(a), type='info'), build_settings_view(c))).classes('pill').style('font-size:11px;')
                    L('Note: changing this resets your trading account.', 'font-size:9px;color:var(--text3);font-family:var(--mono);margin-top:6px;')

def build_profile_view(c):
    c.clear()
    with c:
        pv = portfolio_value()
        gl = round(pv - account['start_cash'], 2)
        gl_pct = round(gl / account['start_cash'] * 100, 2)
        stats = get_perf_stats()

        L('Profile', 'font-size:15px;font-weight:600;color:var(--white);margin-bottom:12px;')
        with R('gap:16px;align-items:flex-start;flex-wrap:wrap;'):
            with C('flex:1;min-width:200px;gap:8px;'):
                with D('').classes('card').style('text-align:center;'):
                    refs['profile_avatar_big'] = L(profile['avatar'], 'font-size:48px;margin-bottom:8px;')
                    username_in = ui.input(value=profile['username']).props('outlined dense').style('text-align:center;margin-bottom:8px;')
                    username_in.on('blur', lambda e: profile.update({'username': username_in.value}))
                    L('Member since {}'.format(profile['joined']), 'font-size:10px;color:var(--text3);font-family:var(--mono);')
                    L('CHOOSE AVATAR', '').classes('sec-label').style('margin:12px 0 8px;')
                    AVATARS = ['\U0001F600', '\U0001F60E', '\U0001F913', '\U0001F920', '\U0001F9D9',
                               '\U0001F916', '\U0001F47D', '\U0001F431', '\U0001F436', '\U0001F98A',
                               '\U0001F985', '\U0001F989', '\U0001F438', '\U0001F42F', '\U0001F984',
                               '\U0001F995']

                    def pick_avatar(a):
                        profile.update({'avatar': a})
                        refs['profile_avatar_big'].set_text(a)
                        if 'sidebar_avatar' in refs:
                            refs['sidebar_avatar'].set_text(a)
                        build_profile_view(c)

                    with R('gap:6px;flex-wrap:wrap;justify-content:center;'):
                        for av in AVATARS:
                            sel = profile['avatar'] == av
                            with D('width:38px;height:38px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:20px;cursor:pointer;background:var(--bg3);border:2px solid {};'.format('var(--accent)' if sel else 'transparent')).on('click', lambda e, a=av: pick_avatar(a)):
                                L(av, 'font-size:20px;')

            with C('flex:2;min-width:260px;gap:8px;'):
                with D('').classes('card'):
                    L('TRADING STATS', '').classes('sec-label').style('margin-bottom:10px;')
                    gl_col = 'var(--green)' if gl >= 0 else 'var(--red)'
                    for lbl_s, val_s, col_s in [
                        ('Portfolio Value', '${:,.2f}'.format(pv), 'var(--white)'),
                        ('Total P&L', '${:+,.2f}  ({:+.2f}%)'.format(gl, gl_pct), gl_col),
                        ('Started With', '${:,.2f}'.format(account['start_cash']), 'var(--text2)'),
                        ('Completed Trades', str(stats.get('total_trades', 0)), 'var(--white)'),
                        ('Win Rate', '{:.1f}%'.format(stats.get('win_rate', 0)), 'var(--green)' if stats.get('win_rate', 0) >= 50 else 'var(--red)'),
                        ('Best Trade', '+${:.2f}'.format(stats.get('best_trade', 0)), 'var(--green)'),
                        ('Worst Trade', '${:.2f}'.format(stats.get('worst_trade', 0)), 'var(--red)'),
                        ('Open Positions', str(len(account['positions'])), 'var(--white)'),
                    ]:
                        with R('justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bg3);'):
                            L(lbl_s, 'font-size:11px;color:var(--text2);')
                            L(val_s, 'font-size:11px;font-weight:500;color:{};font-family:var(--mono);'.format(col_s))

                with D('').classes('card'):
                    L('TRADER BADGE', '').classes('sec-label').style('margin-bottom:8px;')
                    n_trades = stats.get('total_trades', 0)
                    wr = stats.get('win_rate', 0)
                    if n_trades == 0:
                        badge, bdesc = 'SEEDLING', 'Make your first trade to start your journey'
                    elif n_trades < 5:
                        badge, bdesc = 'BEGINNER', 'Getting started. Keep trading to level up'
                    elif wr >= 70:
                        badge, bdesc = 'EXPERT TRADER', '{:.0f}% win rate - outstanding!'.format(wr)
                    elif wr >= 55:
                        badge, bdesc = 'SKILLED TRADER', '{:.0f}% win rate - above average'.format(wr)
                    elif wr >= 40:
                        badge, bdesc = 'ACTIVE TRADER', 'Balanced performance. Keep refining your strategy'
                    else:
                        badge, bdesc = 'LEARNING', 'Study the indicators. Use the AI advisor for tips'
                    L(badge, 'font-size:18px;font-weight:600;color:var(--accent);font-family:var(--mono);margin-bottom:6px;')
                    L(bdesc, 'font-size:11px;color:var(--text);line-height:1.5;')

VIEWS = {
    'chart': build_chart_view, 'portfolio': build_portfolio_view,
    'explorer': build_explorer_view, 'history': build_history_view,
    'report': build_report_view, 'news': build_news_view,
    'settings': build_settings_view, 'profile': build_profile_view,
}

def switch_view(v):
    state['view'] = v
    for vid in VIEWS:
        if 'nav_' + vid in refs:
            if v == vid:
                refs['nav_' + vid].classes(add='active')
            else:
                refs['nav_' + vid].classes(remove='active')
    sb_map = {'chart': 'sb_chart', 'history': 'sb_history', 'news': 'sb_news', 'settings': 'sb_settings'}
    for vid, key in sb_map.items():
        if key in refs:
            if v == vid:
                refs[key].classes(add='active')
            else:
                refs[key].classes(remove='active')
    if 'content_area' in refs:
        VIEWS[v](refs['content_area'])

def rebuild_view():
    if 'content_area' in refs:
        VIEWS[state['view']](refs['content_area'])

def gen_pdf(name, ticker, price, chg, rsi_v, m_val, sig_v, bull, bb_u, bb_l, bpct, sma20, sma50, vpct, atr, bull_s, bear_s, overall, info):
    if not PDF_OK:
        ui.notify('pip install reportlab', type='warning')
        return
    try:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
        styles = getSampleStyleSheet()
        GRN = rl_colors.HexColor('#10b981')
        RED = rl_colors.HexColor('#ef4444')
        AMB = rl_colors.HexColor('#f59e0b')
        WHT = rl_colors.HexColor('#e8f0eb')
        GRY = rl_colors.HexColor('#4a6b55')
        BG2 = rl_colors.HexColor('#0f1610')

        def T(name_, color, fs, fn='Helvetica', b=False):
            return ParagraphStyle(name_, parent=styles['Normal'], textColor=color, fontSize=fs, fontName=fn + ('-Bold' if b else ''))

        story = []
        story.append(Paragraph('STOCKMIND TERMINAL - ' + ticker, T('t', WHT, 18, 'Courier', True)))
        story.append(Paragraph(name, T('s', GRY, 11)))
        story.append(Paragraph('Report generated {} - {}'.format(datetime.now().strftime('%d %B %Y %H:%M'), profile['username']), T('d', GRY, 9)))
        story.append(HRFlowable(width='100%', color=AMB, thickness=1, spaceAfter=10))
        story.append(Paragraph('PRICE SUMMARY', T('h', AMB, 11, 'Courier', True)))
        td = [['Metric', 'Value', 'Metric', 'Value'],
              ['Current Price', '${:,.2f}'.format(price), 'Period Change', '{:+.2f}%'.format(chg)],
              ['SMA 20', '${}'.format(sma20), 'SMA 50', '${}'.format(sma50)],
              ['52W High', '${:.2f}'.format(float(info.get('fiftyTwoWeekHigh', 0))), '52W Low', '${:.2f}'.format(float(info.get('fiftyTwoWeekLow', 0)))],
              ['Market Cap', fmt_cap(info.get('marketCap')), 'ATR', '${}'.format(atr)]]
        t = Table(td, colWidths=[4.5 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#132018')),
            ('TEXTCOLOR', (0, 0), (-1, 0), AMB),
            ('TEXTCOLOR', (0, 1), (-1, -1), WHT),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (-1, -1), 'Courier'),
            ('GRID', (0, 0), (-1, -1), .5, rl_colors.HexColor('#1a3020')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.HexColor('#080c0a'), BG2]),
        ]))
        story.append(t)
        story.append(Spacer(1, .3 * cm))
        ov_col = GRN if overall == 'BULLISH' else (RED if overall == 'BEARISH' else AMB)
        story.append(Paragraph('OVERALL SIGNAL', T('h2', AMB, 11, 'Courier', True)))
        story.append(Paragraph('<b>' + overall + '</b>', T('ov', ov_col, 16, 'Courier', True)))
        story.append(Paragraph('BULLISH SIGNALS', T('h3', GRN, 10, 'Courier', True)))
        for s in bull_s:
            story.append(Paragraph('- ' + s, T('b', GRY, 9)))
        story.append(Spacer(1, .2 * cm))
        story.append(Paragraph('BEARISH SIGNALS', T('h4', RED, 10, 'Courier', True)))
        for s in bear_s:
            story.append(Paragraph('- ' + s, T('b2', GRY, 9)))
        story.append(Spacer(1, .5 * cm))
        story.append(HRFlowable(width='100%', color=rl_colors.HexColor('#1a3020'), thickness=.5))
        story.append(Paragraph('This report is for educational purposes only. Not financial advice.', T('d2', GRY, 8)))
        doc.build(story)
        b64 = base64.b64encode(buf.getvalue()).decode()
        fname = '{}_StockMind_{}.pdf'.format(ticker, datetime.now().strftime('%Y%m%d'))
        ui.run_javascript('var a=document.createElement("a");a.href="data:application/pdf;base64,' + b64 + '";a.download="' + fname + '";a.click();')
        ui.notify('PDF downloaded: ' + fname, type='positive')
    except Exception as ex:
        ui.notify('PDF error: {}'.format(ex), type='negative')

refresh_debug = {'last_price': {}}

async def refresh_live_price():
    """Lightweight periodic refresh - updates the price/change display and the chart's current candle."""
    if state['view'] != 'chart':
        return
    ticker = state['ticker']
    try:
        q = await run.io_bound(fetch_quote_fast, ticker, 1)
    except Exception:
        return
    if not q or not q.get('price'):
        return
    if state['ticker'] != ticker or state['view'] != 'chart':
        return  # stock or view changed mid-fetch - discard stale result

    price = q['price']
    pct = q.get('chg_pct', 0)
    last_seen = refresh_debug['last_price'].get(ticker)
    if last_seen == price:
        return  # no change - skip the DOM/chart writes entirely
    refresh_debug['last_price'][ticker] = price

    up = pct >= 0
    col = 'var(--green)' if up else 'var(--red)'
    arr = 'UP' if up else 'DOWN'
    prev = price / (1 + pct / 100) if pct != -100 else price
    chg = round(price - prev, 2)
    safe_set('hdr_price', '${:,.2f}'.format(price))
    safe_set('hdr_chg', '{} ${:.2f}  ({:.2f}%)'.format(arr, abs(chg), abs(pct)), 'font-size:12px;color:{};font-family:var(--mono);'.format(col))
    ui.run_javascript('window.smUpdateLastPrice && window.smUpdateLastPrice({}); window.smFlashPulse && window.smFlashPulse();'.format(price))
    for sym in WATCHLIST:
        if sym == ticker:
            safe_set('wp_{}'.format(sym), '${:,.2f}'.format(price))
            safe_set('wc_{}'.format(sym), '{:+.2f}%'.format(pct), 'font-size:9px;color:{};font-family:var(--mono);'.format(col))


with D('display:flex;width:100vw;height:100vh;min-height:0;overflow:hidden;background:var(--bg);'):
    ui.timer(1.5, lambda: load_stock(state['ticker']), once=True)
    ui.timer(1.5, refresh_live_price)
    ui.timer(30.0, save_state)  # autosave every 30 seconds

    with C('width:52px;min-width:52px;height:100vh;background:var(--bg1);border-right:1px solid var(--border);align-items:center;padding:10px 0;gap:3px;'):
        with D('width:34px;height:34px;border-radius:7px;margin-bottom:12px;background:var(--bg3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;'):
            ICO('ti-chart-candle', 'color:var(--accent);', 18)

        def sb(ico, tip, active=False, on_click=None):
            el = D('').classes('s-item' + (' active' if active else '')).tooltip(tip)
            if on_click:
                el.on('click', on_click)
            with el:
                ICO(ico, 'font-size:17px;color:{};'.format('var(--accent)' if active else 'var(--text2)'))
            return el

        refs['sb_chart'] = sb('ti-layout-dashboard', 'Dashboard', True, on_click=lambda e: switch_view('chart'))
        refs['sb_history'] = sb('ti-history', 'Trade History', on_click=lambda e: switch_view('history'))
        refs['sb_news'] = sb('ti-news', 'News & Alerts', on_click=lambda e: switch_view('news'))
        D('width:26px;height:1px;background:var(--border);margin:4px 0;')
        refs['sb_settings'] = sb('ti-settings', 'Settings', on_click=lambda e: switch_view('settings'))
        sb('ti-info-circle', 'About StockMind Terminal - paper trading and AI market analysis', on_click=lambda e: ui.notify('StockMind Terminal v2 - Paper trading simulator with AI advisor. Not real financial advice.', type='info', timeout=4000))
        D('flex:1;')
        with D('width:30px;height:30px;border-radius:50%;background:var(--bg3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:16px;').on('click', lambda e: switch_view('profile')).tooltip('Profile'):
            refs['sidebar_avatar'] = L(profile['avatar'], 'font-size:16px;')

    with C('flex:1;min-width:0;min-height:0;height:100vh;overflow:hidden;'):

        with R('height:46px;min-height:46px;width:100%;background:var(--bg1);border-bottom:1px solid var(--border);padding:0 12px;gap:6px;overflow:hidden;'):
            with R('gap:5px;'):
                D('').classes('live-dot')
                L('STOCKMIND', 'font-family:var(--mono);font-size:12px;font-weight:600;color:var(--white);letter-spacing:1px;')
                L('TERMINAL', 'font-family:var(--mono);font-size:9px;color:var(--accent);letter-spacing:2px;')
            D('width:1px;height:20px;background:var(--border);margin:0 6px;')

            NAV_ITEMS = [('Portfolio', 'portfolio', 'ti-briefcase'), ('Explorer', 'explorer', 'ti-table'), ('Report', 'report', 'ti-file-analytics')]
            for lbl_n, vid, ico_n in NAV_ITEMS:
                btn = ui.button(lbl_n, on_click=lambda e, v=vid: switch_view(v)).classes('view-btn' + (' active' if vid == 'chart' else ''))
                refs['nav_' + vid] = btn

            D('flex:1;')
            with D('position:relative;') as search_wrap:
                search = ui.input(placeholder='Ticker or company name - try "apple" or AAPL').props('outlined dense').style('width:260px;')
                search.on('keydown.enter', lambda: (ui.timer(0.05, lambda: load_stock(search.value), once=True), hide_suggestions()))
                search_wrap.props('id="search-wrap-anchor"')
                suggest_box = D('position:fixed;width:280px;background:var(--bg2);border:1px solid var(--border);border-radius:6px;z-index:9999;max-height:280px;overflow-y:auto;display:none;box-shadow:0 8px 24px rgba(0,0,0,0.6);')
                suggest_box.props('id="search-suggest-box"')
                search_state = {'pending_query': '', 'timer_active': False}

                def position_suggestions():
                    ui.run_javascript(
                        'var a = document.getElementById("search-wrap-anchor");'
                        'var b = document.getElementById("search-suggest-box");'
                        'if (a && b) {'
                        '  var r = a.getBoundingClientRect();'
                        '  b.style.top = (r.bottom + 4) + "px";'
                        '  b.style.left = r.left + "px";'
                        '}'
                    )

                def hide_suggestions():
                    suggest_box.style('display:none;')

                def render_results(query, results):
                    # Ignore stale results if the input has changed since the request was made
                    if search.value.strip() != query:
                        return
                    suggest_box.clear()
                    if not results:
                        hide_suggestions()
                        return
                    suggest_box.style('display:block;')
                    position_suggestions()
                    with suggest_box:
                        for r in results:
                            sym = r['symbol']
                            nm = r['name']

                            def pick_result(s=sym):
                                setattr(search, 'value', '')
                                hide_suggestions()
                                ui.timer(0.05, lambda: load_stock(s), once=True)

                            with D('padding:8px 10px;cursor:pointer;border-bottom:1px solid var(--bg3);display:flex;justify-content:space-between;align-items:center;').on(
                                'click', lambda e, fn=pick_result: fn()
                            ).style('transition:background .1s;'):
                                with R('gap:6px;'):
                                    L(sym, 'font-size:12px;font-weight:600;color:var(--white);font-family:var(--mono);')
                                L(nm[:30], 'font-size:10px;color:var(--text2);')

                async def do_search(query):
                    try:
                        results = await run.io_bound(search_symbols, query)
                    except Exception:
                        results = []
                    render_results(query, results)

                def on_input_change():
                    q = search.value.strip()
                    if not q:
                        hide_suggestions()
                        return
                    search_state['pending_query'] = q
                    # Show instant local matches immediately, no network wait
                    instant = local_prefix_search(q)
                    render_results(q, instant)
                    asyncio.create_task(debounced_search(q))

                async def debounced_search(q):
                    await asyncio.sleep(0.35)
                    if search_state['pending_query'] == q and search.value.strip() == q:
                        await do_search(q)

                search.on('update:model-value', lambda e: on_input_change())
                search.on('blur', lambda e: ui.timer(0.2, hide_suggestions, once=True))

            with D('background:var(--bg3);border:1px solid var(--border);border-radius:5px;padding:4px 10px;display:flex;align-items:center;gap:4px;cursor:pointer;').on('click', lambda e: (ui.timer(0.05, lambda: load_stock(search.value), once=True) if search.value else None, hide_suggestions())):
                ICO('ti-search', 'color:var(--accent);', 12)
                L('Go', 'font-size:11px;color:var(--accent);font-family:var(--mono);')

            with R('gap:6px;margin-left:8px;background:var(--bg3);border:1px solid var(--border);border-radius:5px;padding:3px 10px;cursor:pointer;').on('click', lambda e: switch_view('portfolio')):
                ICO('ti-wallet', 'color:var(--accent);', 12)
                refs['acct_pv'] = L('${:,.2f}'.format(portfolio_value()), 'font-size:11px;color:var(--white);font-family:var(--mono);font-weight:500;')

        with R('flex:1;min-height:0;overflow:hidden;align-items:stretch;'):

            with C('flex:1;min-width:0;min-height:0;padding:12px;gap:0;overflow-y:auto;align-self:stretch;'):
                refs['content_area'] = D('display:flex;flex-direction:column;gap:8px;width:100%;')
                with refs['content_area']:
                    build_chart_view(refs['content_area'])

            with C('width:360px;min-width:360px;min-height:0;border-left:1px solid var(--border);height:100%;overflow:hidden;align-self:stretch;'):

                with C('flex:1;min-height:0;padding:10px;gap:7px;overflow:hidden;'):
                    with R('gap:5px;align-items:center;'):
                        D('').classes('live-dot')
                        L('AI ADVISOR', 'font-size:9px;color:var(--accent);font-family:var(--mono);letter-spacing:1.5px;')
                        refs['ai_status_badge'] = L(
                            'ONLINE' if ai_state['enabled'] else 'OFFLINE',
                            'font-size:8px;font-family:var(--mono);padding:1px 5px;border-radius:3px;{}'.format(
                                'color:var(--green);background:#10b98114;border:1px solid #10b98130;' if ai_state['enabled'] else 'color:var(--amber);background:#f59e0b14;border:1px solid #f59e0b30;'
                            )
                        )
                    refs['ai_sub'] = L('Ready', 'font-size:9px;color:var(--text3);font-family:var(--mono);')

                    with ui.scroll_area().style('flex:1;min-height:0;height:1px;'):
                        refs['chat_col'] = C('gap:7px;width:100%;padding-right:3px;')
                        with refs['chat_col']:
                            for msg in chat_log:
                                is_ai = msg['role'] == 'ai'
                                ico = 'ti-terminal-2' if is_ai else 'ti-user'
                                av_bg = 'var(--bg3)' if is_ai else '#1a4a2a'
                                ic = 'var(--accent)' if is_ai else 'var(--white)'
                                cls = 'ai' if is_ai else 'user'
                                with D('display:flex;align-items:flex-start;gap:7px;width:100%;'):
                                    with D('width:22px;height:22px;min-width:22px;flex-shrink:0;background:{};border-radius:5px;border:1px solid var(--border);display:flex;align-items:center;justify-content:center;margin-top:1px;'.format(av_bg)):
                                        ICO(ico, 'font-size:11px;color:{};'.format(ic))
                                    L(msg['text']).classes('chat-bubble {}'.format(cls))

                    refs['ai_offline_hint'] = D('').style('display:{};'.format('none' if ai_state['enabled'] else 'block'))
                    with refs['ai_offline_hint']:
                        with D('font-size:9px;color:var(--text3);font-family:var(--mono);background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:6px;line-height:1.6;cursor:pointer;').on('click', lambda e: switch_view('settings')):
                            L('AI not connected. Go to Settings and paste your free Groq API key.', 'font-size:9px;color:var(--text3);')

                    SUGGESTED_PROMPTS = [
                        'Is {} a good buy right now?'.format(state['ticker']),
                        'What are the risks with {}?'.format(state['ticker']),
                        'Explain the RSI for {}?'.format(state['ticker']),
                        'How is my portfolio doing?',
                        'What sectors look strong right now?',
                        'Should I take profits?',
                    ]
                    with D('display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px;'):
                        for prompt in SUGGESTED_PROMPTS:
                            async def send_prompt(e, p=prompt):
                                if 'chat_in' not in refs:
                                    return
                                refs['chat_in'].value = p
                                await send_msg()
                            ui.button(prompt, on_click=send_prompt).style(
                                'font-size:9px;padding:2px 8px;border-radius:12px;border:1px solid var(--border);'
                                'background:var(--bg2);color:var(--text2);font-family:var(--sans);'
                                'cursor:pointer;white-space:normal;text-align:left;height:auto;'
                            )

                    with R('gap:5px;align-items:center;'):
                        refs['chat_in'] = ui.input(placeholder='Ask Max anything about markets...').props('outlined dense').style('flex:1;min-width:0;')
                        refs['chat_in'].on('keydown.enter', send_msg)
                        with ui.button(on_click=send_msg).style('background:var(--bg3);border:1px solid var(--border);border-radius:5px;width:30px;height:30px;min-width:30px;padding:0;'):
                            ICO('ti-send', 'color:var(--accent);', 12)

                with C('border-top:1px solid var(--border);padding:8px 10px;gap:1px;max-height:300px;overflow-y:auto;'):
                    with R('justify-content:space-between;margin-bottom:5px;'):
                        L('WATCHLIST', '').classes('sec-label')
                        refs['watchlist_count'] = L('{} sym'.format(len(WATCHLIST)), 'font-size:9px;color:var(--text3);font-family:var(--mono);')

                    refs['watchlist_rows'] = C('gap:1px;width:100%;')

                    def render_watchlist():
                        refs['watchlist_rows'].clear()
                        refs['watchlist_count'].set_text('{} sym'.format(len(WATCHLIST)))
                        with refs['watchlist_rows']:
                            for sym in WATCHLIST:
                                with D('').classes('w-row'):
                                    with R('gap:5px;cursor:pointer;flex:1;').on('click', lambda e, s=sym: ui.timer(0.05, lambda: load_stock(s), once=True)):
                                        D('width:5px;height:5px;border-radius:50%;background:var(--text3);flex-shrink:0;')
                                        L(sym, 'font-size:11px;font-weight:600;color:var(--white);font-family:var(--mono);')
                                    with R('gap:6px;align-items:center;'):
                                        with C('align-items:flex-end;gap:0;'):
                                            refs['wp_' + sym] = L('--', 'font-size:10px;color:var(--text);font-family:var(--mono);')
                                            refs['wc_' + sym] = L('--', 'font-size:9px;color:var(--text3);font-family:var(--mono);')
                                        ui.button('x', on_click=lambda e, s=sym: remove_from_watchlist(s)).style(
                                            'background:transparent;color:var(--text3);font-size:12px;padding:0 3px;min-width:0;height:auto;'
                                        )

                    global_funcs['render_watchlist'] = render_watchlist

                    def remove_from_watchlist(sym):
                        if sym in WATCHLIST:
                            WATCHLIST.remove(sym)
                        render_watchlist()
                        save_state()

                    def add_to_watchlist():
                        sym = watch_add_in.value.strip().upper()
                        if not sym:
                            return
                        if sym in WATCHLIST:
                            ui.notify('{} is already in your watchlist'.format(sym), type='info')
                            watch_add_in.value = ''
                            return
                        WATCHLIST.append(sym)
                        watch_add_in.value = ''
                        render_watchlist()
                        ui.timer(0.05, lambda s=sym: load_stock(s), once=True)

                    render_watchlist()

                    with R('gap:4px;margin-top:6px;align-items:center;'):
                        watch_add_in = ui.input(placeholder='Add ticker...').props('outlined dense').style('flex:1;min-width:0;')
                        watch_add_in.on('keydown.enter', add_to_watchlist)
                        ui.button('+', on_click=add_to_watchlist).style(
                            'background:var(--bg3);border:1px solid var(--border);color:var(--accent);'
                            'border-radius:5px;width:28px;height:28px;min-width:28px;padding:0;font-size:14px;'
                        )



if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='StockMind Terminal', favicon='\U0001F4C8', dark=True, port=8080, show=True, reload=False)