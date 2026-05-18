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
# 2. 籌碼資料獲取模組 (FinMind + TWSE 雙重備援 + 模糊比對)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_institutional_data():
    debug_logs = []
    debug_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 開始向 FinMind 請求資料...")
    
    url = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")
    
    # 您的 API Token
    FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_date,
        "token": FINMIND_TOKEN
    }
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        debug_logs.append(f"FinMind HTTP 狀態碼: {res.status_code}")
        data = res.json()
        debug_logs.append(f"FinMind 回傳訊息 (msg): {data.get('msg')}")
        
        if data.get('msg') == 'success' and len(data.get('data', [])) > 0:
            df = pd.DataFrame(data['data'])
            debug_logs.append(f"FinMind 成功抓取到 {len(df)} 筆原始資料")
            
            # 【重要修正】使用「模糊比對」取代絕對相等，防止官方改名
            foreign_mask = df['name'].str.contains('外資', na=False) & ~df['name'].str.contains('自營商', na=False)
            foreign_df = df[foreign_mask].copy()
            
            if not foreign_df.empty:
                foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
                foreign_df['Foreign_Net'] = (foreign_df['buy'] - foreign_df['sell']) / 100000000
                
                latest_date = df['date'].max()
                latest_df = df[df['date'] == latest_date]
                debug_logs.append(f"FinMind 最新資料日期: {latest_date}")
                
                def get_net_buy(keyword, exclude=''):
                    mask = latest_df['name'].str.contains(keyword, na=False)
                    if exclude: mask = mask & ~latest_df['name'].str.contains(exclude, na=False)
                    sub_df = latest_df[mask]
                    if sub_df.empty: return 0.0
                    return (sub_df['buy'].sum() - sub_df['sell'].sum()) / 100000000

                latest_inst = {
                    'date': latest_date,
                    '外資': get_net_buy('外資', '自營商'),
                    '投信': get_net_buy('投信'),
                    '自營商': get_net_buy('自營商')
                }
                foreign_df.set_index('Date', inplace=True)
                debug_logs.append("✅ FinMind 資料解析成功！")
                return foreign_df[['Foreign_Net']], latest_inst, debug_logs
            else:
                debug_logs.append("⚠️ FinMind 資料中找不到包含『外資』關鍵字的項目。")
        else:
            debug_logs.append("⚠️ FinMind 回傳的資料陣列為空 (可能是太早抓取，官方尚未更新)。")
            
    except Exception as e:
        debug_logs.append(f"❌ FinMind 發生例外錯誤: {str(e)}")

    # ==========================================
    # 啟動 TWSE 備援機制
    # ==========================================
    debug_logs.append("🔄 啟動 TWSE OpenAPI 備援機制...")
    twse_url = "https://openapi.twse.com.tw/v1/fund/BFI82U"
    inst_data = {'date': '今日 (TWSE備援)', '外資': 0.0, '投信': 0.0, '自營商': 0.0}
    
    try:
        res_twse = requests.get(twse_url, timeout=10)
        debug_logs.append(f"TWSE HTTP 狀態碼: {res_twse.status_code}")
        if res_twse.status_code == 200:
            data_twse = res_twse.json()
            debug_logs.append(f"TWSE 回傳資料筆數: {len(data_twse)}")
            
            if len(data_twse) == 0:
                debug_logs.append("❌ TWSE 回傳空陣列！(今日籌碼尚未公布或為休假日)")
            else:
                for row in data_twse:
                    name = row.get('type', '')
                    net_buy_str = row.get('difference', '0').replace(',', '')
                    try: net_buy = int(net_buy_str)
                    except: net_buy = 0

                    if '外資' in name and '自營商' not in name:
                        inst_data['外資'] = round(net_buy / 100000000, 2)
                    elif '投信' in name:
                        inst_data['投信'] = round(net_buy / 100000000, 2)
                    elif '自營商' in name:
                        inst_data['自營商'] = round(net_buy / 100000000, 2)
                debug_logs.append("✅ TWSE 備援資料解析成功！")
    except Exception as e:
        debug_logs.append(f"❌ TWSE 發生例外錯誤: {str(e)}")

    return pd.DataFrame(), inst_data, debug_logs

# ==========================================
# 3. 策略引擎與多空打分
# ==========================================
def calculate_signals(data, has_foreign_history):
    data['MA60'] = data['TWII'].rolling(60).mean()
    data['SOX_MA20'] = data['SOX'].rolling(20).mean()
    data['TSMC_MA20'] = data['TSMC'].rolling(20).mean()
    
    if pd.isna(data['MA60'].iloc[-1]):
        return data, 0, 0, 0.0

    latest = data.iloc[-1]
    long_score, short_score = 0.0, 0.0
    z_score_val = 0.0
    
    if latest['TWII'] > latest['MA60']: long_score += 1.0
    elif latest['TWII'] < latest['MA60']: short_score += 1.2
        
    if latest['SOX'] > latest['SOX_MA20']: long_score += 1.8
    elif latest['SOX'] < latest['SOX_MA20']: short_score += 1.8
        
    if latest['TSMC'] > latest['TSMC_MA20']: long_score += 0.8
    elif latest['TSMC'] < latest['TSMC_MA20']: short_score += 0.5
        
    if has_foreign_history and 'Foreign_Net' in data.columns:
        data['Foreign_120MA'] = data['Foreign_Net'].rolling(120, min_periods=10).mean()
        data['Foreign_120STD'] = data['Foreign_Net'].rolling(120, min_periods=10).std().replace(0, np.nan)
        data['Foreign_Zscore'] = (data['Foreign_Net'] - data['Foreign_120MA']) / data['Foreign_120STD']
        
        z_score_val = data['Foreign_Zscore'].iloc[-1]
        if pd.notna(z_score_val) and data['Foreign_120STD'].iloc[-1] != 0:
            if z_score_val > 1.5: long_score += 1.5
            elif z_score_val < -1.5: short_score += 1.5
            
    return data, long_score, short_score, z_score_val

# ==========================================
# 4. 視覺化儀表板
# ==========================================
def main():
    st.title("📈 台指多因子量化戰情室 (強韌診斷版)")
    
    col_btn, col_time = st.columns([1, 4])
    with col_btn:
        if st.button("🔄 重新載入數據"):
            st.cache_data.clear()
            st.rerun()
    with col_time:
        st.write(f"系統最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner('正在獲取市場與籌碼數據...'):
        mkt_df = fetch_market_data()
        foreign_df, latest_inst, debug_logs = fetch_institutional_data()
        
        # 顯示 API 診斷報告
        with st.expander("🛠️ API 連線診斷報告 (點擊展開查看背後運作狀態)"):
            for log in debug_logs:
                if "❌" in log or "⚠️" in log:
                    st.error(log)
                elif "✅" in log:
                    st.success(log)
                else:
                    st.write(log)

        if mkt_df.empty:
            st.error("🚨 Yahoo Finance 價格數據嚴重載入失敗，無法執行運算。")
            return
            
        has_foreign_history = not foreign_df.empty
        
        if has_foreign_history:
            data = mkt_df.join(foreign_df, how='outer').ffill().dropna()
        else:
            data = mkt_df.copy()
            st.warning("⚠️ 由於上述診斷報告中的原因，系統目前僅能啟動無歷史資料的備援模式。")
            
        data, long_score, short_score, z_score_val = calculate_signals(data, has_foreign_history)
        
    st.header("一、 三大法人買賣超動向")
    st.caption(f"資料日期: {latest_inst.get('date', '未知')}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("外資及陸資 (億)", f"{latest_inst.get('外資', 0):.2f}", 
              "偏多" if latest_inst.get('外資', 0) > 0 else "偏空", 
              delta_color="normal" if latest_inst.get('外資', 0) > 0 else "inverse")
    c2.metric("投信 (億)", f"{latest_inst.get('投信', 0):.2f}")
    c3.metric("自營商 (億)", f"{latest_inst.get('自營商', 0):.2f}")
    
    if has_foreign_history:
        z_color = "normal" if z_score_val > 1.5 else ("inverse" if z_score_val < -1.5 else "off")
        c4.metric("📊 外資動能 Z-Score", f"{z_score_val:.2f}", 
                  "突破 1.5" if z_score_val > 1.5 else ("跌破 -1.5" if z_score_val < -1.5 else "常態區間"),
                  delta_color=z_color)
    else:
        c4.metric("📊 外資動能 Z-Score", "無法計算", "缺乏長天期資料", delta_color="off")

    st.header("二、 多空因子共振得分")
    LONG_ENTRY, SHORT_ENTRY = 4.0, 6.0
    
    if long_score >= LONG_ENTRY: signal = "🚨 偏多控盤 (Long)"
    elif short_score >= SHORT_ENTRY: signal = "⚠️ 偏空控盤 (Short)"
    else: signal = "⚖️ 震盪觀望 (Neutral)"

    m1, m2, m3 = st.columns(3)
    score_note = "" if has_foreign_history else " (未計入籌碼)"
    m1.metric(f"多頭總分{score_note}", f"{long_score:.1f}", delta="進場門檻: 4.0", delta_color="normal")
    
    bias = 0.0
    if not data.empty and not pd.isna(data['MA60'].iloc[-1]) and data['MA60'].iloc[-1] != 0:
        bias = ((data['TWII'].iloc[-1] / data['MA60'].iloc[-1]) - 1) * 100
        
    m2.metric("最新加權指數", f"{data['TWII'].iloc[-1]:.2f}", f"季線乖離: {bias:.2f}%")
    m3.metric(f"空頭總分{score_note}", f"{short_score:.1f}", delta="-進場門檻: 6.0", delta_color="inverse")
    st.info(f"**模型綜合判定：** {signal}")

    st.header("三、 技術面與籌碼圖表")
    rows = 3 if has_foreign_history else 2
    row_heights = [0.5, 0.25, 0.25] if has_foreign_history else [0.7, 0.3]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=row_heights)
    
    if 'TWII' in data.columns and 'MA60' in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='silver', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['MA60'], name="季線 (60MA)", line=dict(color='orange', width=2, dash='dot')), row=1, col=1)
    
    if 'SOX' in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data['SOX'], name="費城半導體", line=dict(color='cyan', width=1.5)), row=2, col=1)
    
    if has_foreign_history and 'Foreign_Net' in data.columns:
        colors = ['#ef4444' if val > 0 else '#22c55e' for val in data['Foreign_Net']]
        fig.add_trace(go.Bar(x=data.index, y=data['Foreign_Net'], name="外資淨買賣(億)", marker_color=colors), row=3, col=1)
    
    fig.update_layout(height=800 if has_foreign_history else 600, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified", 
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
