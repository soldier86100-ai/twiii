import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="台指多因子戰情室 (強韌診斷版)")

# ==========================================
# 1. 資料獲取模組 (Yahoo Finance)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_market_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=250)
    
    tickers = {'TWII': '^TWII', 'SOX': '^SOX', 'TSMC': '2330.TW'}
    mkt_df = pd.DataFrame()
    
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty: continue

            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            if isinstance(df.columns, pd.MultiIndex):
                close_series = df['Close'][ticker].rename(name)
            else:
                close_series = df['Close'].rename(name)
            
            if mkt_df.empty:
                mkt_df = pd.DataFrame(close_series)
            else:
                mkt_df = mkt_df.join(close_series, how='outer')
        except Exception as e:
            pass

    return mkt_df.ffill().dropna()

# ==========================================
# 2. 籌碼資料獲取模組 (FinMind + TWSE 雙重備援)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_institutional_data():
    debug_logs = []
    debug_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 開始向 FinMind 請求資料...")
    
    url = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")
    
    FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_date,
        "token": FINMIND_TOKEN
    }
    
    # 偽裝成正常瀏覽器，避免被 API 防火牆阻擋
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        debug_logs.append(f"FinMind HTTP 狀態碼: {res.status_code}")
        data = res.json()
        debug_logs.append(f"FinMind 回傳訊息 (msg): {data.get('msg')}")
        
        if data.get('msg') == 'success' and len(data.get('data', [])) > 0:
            df = pd.DataFrame(data['data'])
            debug_logs.append(f"FinMind 成功抓取到 {len(df)} 筆原始資料")
            
            # 【關鍵修正】FinMind 已經將法人名稱全面改為英文，因此加入中英文雙重關鍵字比對
            foreign_mask = df['name'].str.contains('外資|Foreign_Investor', na=False, case=False)
            foreign_mask = foreign_mask & ~df['name'].str.contains('自營商|Dealer_Self', na=False, case=False)
            foreign_df = df[foreign_mask].copy()
            
            if not foreign_df.empty:
                foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
                foreign_df['Foreign_Net'] = (foreign_df['buy'] - foreign_df['sell']) / 100000000
                
                latest_date = df['date'].max()
                latest_df = df[df['date'] == latest_date]
                debug_logs.append(f"FinMind 最新資料日期: {latest_date}")
                
                def get_net_buy(keyword, exclude=''):
                    mask = latest_df['name'].str.contains(keyword, na=False, case=False)
                    if exclude: 
                        mask = mask & ~latest_df['name'].str.contains(exclude, na=False, case=False)
                    sub_df = latest_df[mask]
                    if sub_df.empty: return 0.0
                    return (sub_df['buy'].sum() - sub_df['sell'].sum()) / 100000000

                latest_inst = {
                    'date': latest_date,
                    '外資': get_net_buy('外資|Foreign_Investor', '自營商|Dealer_Self'),
                    '投信': get_net_buy('投信|Investment_Trust'),
                    '自營商': get_net_buy('自營商|Dealer', '外資|Foreign')
                }
                foreign_df.set_index('Date', inplace=True)
                debug_logs.append("✅ FinMind 資料解析成功！")
                return foreign_df[['Foreign_Net']], latest_inst, debug_logs
            else:
                debug_logs.append("⚠️ FinMind 資料中找不到包含外資或 Foreign_Investor 關鍵字的項目。")
        else:
            debug_logs.append("⚠️ FinMind 回傳的資料陣列為空。")
            
    except Exception as e:
        debug_logs.append(f"❌ FinMind 發生例外錯誤: {str(e)}")

    # ==========================================
    # TWSE 備援機制 (加入 JSON 解析防呆與瀏覽器偽裝)
    # ==========================================
    debug_logs.append("🔄 啟動 TWSE OpenAPI 備援機制...")
    twse_url = "https://openapi.twse.com.tw/v1/fund/BFI82U"
    inst_data = {'date': '今日 (TWSE備援)', '外資': 0.0, '投信': 0.0, '自營商': 0.0}
    
    try:
        twse_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res_twse = requests.get(twse_url, headers=twse_headers, timeout=10)
        debug_logs.append(f"TWSE HTTP 狀態碼: {res_twse.status_code}")
        
        if res_twse.status_code == 200:
            try:
                data_twse = res_twse.json()
                debug_logs.append(f"TWSE
