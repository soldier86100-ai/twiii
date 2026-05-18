import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

st.set_page_config(layout="wide", page_title="台指多因子戰情室 (完整籌碼版)")

# ==========================================
# 1. 資料獲取模組 (Yahoo Finance + FinMind)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_finmind_historical():
    """使用 FinMind API 抓取大盤三大法人歷史資料 (過去250天) - 安全防呆版"""
    url = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.datetime.now() - datetime.timedelta(days=250)).strftime("%Y-%m-%d")
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_date
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        # 確保 API 回傳成功且真的有資料
        if data.get('msg') == 'success' and len(data.get('data', [])) > 0:
            df = pd.DataFrame(data['data'])
            
            if df.empty:
                return pd.DataFrame(), {}
            
            # 過濾外資資料
            foreign_df = df[df['name'] == '外資及陸資(不含外資自營商)'].copy()
            if foreign_df.empty:
                return pd.DataFrame(), {}

            foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
            
            # 計算淨買賣超 (單位轉為億元)
            foreign_df['Foreign_Net'] = (foreign_df['buy'] - foreign_df['sell']) / 100000000
            
            # 整理三大法人供面板顯示用 (取最新一日)
            latest_date = df['date'].max()
            latest_df = df[df['date'] == latest_date]
            
            # 【防呆函數】使用 sum() 取代 values[0]，即使沒有資料也會安全回傳 0.0
            def get_net_buy(name_filter):
                sub_df = latest_df[latest_df['name'] == name_filter]
                if sub_df.empty: 
                    return 0.0
                return (sub_df['buy'].sum() - sub_df['sell'].sum()) / 100000000

            latest_inst = {
                'date': latest_date,
                '外資': get_net_buy('外資及陸資(不含外資自營商)'),
                '投信': get_net_buy('投信'),
                '自營商': get_net_buy('自營商(自行買賣)')
            }
            
            foreign_df.set_index('Date', inplace=True)
            return foreign_df[['Foreign_Net']], latest_inst
            
    except Exception as e:
        st.error(f"FinMind API 串接發生例外錯誤: {e}")
        
    return pd.DataFrame(), {}

@st.cache_data(ttl=3600)
def fetch_finmind_historical():
    """使用 FinMind API 抓取大盤三大法人歷史資料 (過去250天)"""
    url = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.datetime.now() - datetime.timedelta(days=250)).strftime("%Y-%m-%d")
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_date
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        if data.get('msg') == 'success':
            df = pd.DataFrame(data['data'])
            
            # 過濾外資資料
            foreign_df = df[df['name'] == '外資及陸資(不含外資自營商)'].copy()
            foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
            
            # 計算淨買賣超 (單位轉為億元)
            foreign_df['Foreign_Net'] = (foreign_df['buy'] - foreign_df['sell']) / 100000000
            
            # 整理投信與自營商供面板顯示用 (取最新一日)
            latest_date = df['date'].max()
            latest_df = df[df['date'] == latest_date]
            
            latest_inst = {
                'date': latest_date,
                '外資': foreign_df.iloc[-1]['Foreign_Net'],
                '投信': (latest_df[latest_df['name'] == '投信']['buy'].values[0] - latest_df[latest_df['name'] == '投信']['sell'].values[0]) / 100000000 if not latest_df[latest_df['name'] == '投信'].empty else 0,
                '自營商': (latest_df[latest_df['name'] == '自營商(自行買賣)']['buy'].values[0] - latest_df[latest_df['name'] == '自營商(自行買賣)']['sell'].values[0]) / 100000000 if not latest_df[latest_df['name'] == '自營商(自行買賣)'].empty else 0
            }
            
            foreign_df.set_index('Date', inplace=True)
            return foreign_df[['Foreign_Net']], latest_inst
            
    except Exception as e:
        st.error(f"FinMind API 串接失敗: {e}")
        
    return pd.DataFrame(), {}

# ==========================================
# 2. 策略引擎與多空打分 (還原 v11 邏輯)
# ==========================================
def calculate_signals(mkt_df, foreign_df):
    # 將價格與外資籌碼依照日期對齊 (Outer Join)
    data = mkt_df.join(foreign_df, how='outer').ffill().dropna()
    
    # 價格技術指標
    data['MA60'] = data['TWII'].rolling(60).mean()
    data['SOX_MA20'] = data['SOX'].rolling(20).mean()
    data['TSMC_MA20'] = data['TSMC'].rolling(20).mean()
    
    # 籌碼技術指標 (外資 120 日 Z-score)
    data['Foreign_120MA'] = data['Foreign_Net'].rolling(120, min_periods=10).mean()
    data['Foreign_120STD'] = data['Foreign_Net'].rolling(120, min_periods=10).std().replace(0, np.nan)
    data['Foreign_Zscore'] = (data['Foreign_Net'] - data['Foreign_120MA']) / data['Foreign_120STD']
    
    if data.empty or pd.isna(data['MA60'].iloc[-1]):
        return data, 0, 0

    latest = data.iloc[-1]
    long_score, short_score = 0.0, 0.0
    
    # 因子 1: 大盤與季線
    if latest['TWII'] > latest['MA60']: long_score += 1.0
    elif latest['TWII'] < latest['MA60']: short_score += 1.2
        
    # 因子 2: 費城半導體動能
    if latest['SOX'] > latest['SOX_MA20']: long_score += 1.8
    elif latest['SOX'] < latest['SOX_MA20']: short_score += 1.8
        
    # 因子 3: 台積電現貨
    if latest['TSMC'] > latest['TSMC_MA20']: long_score += 0.8
    elif latest['TSMC'] < latest['TSMC_MA20']: short_score += 0.5
        
    # 因子 4: 外資動能 Z-score (還原 v11 核心邏輯)
    if latest['Foreign_Zscore'] > 1.5:
        long_score += 1.5
    elif latest['Foreign_Zscore'] < -1.5:
        short_score += 1.5
        
    return data, long_score, short_score

# ==========================================
# 3. 視覺化儀表板
# ==========================================
def main():
    st.title("📈 台指多因子量化戰情室 (完整籌碼 Z-score 版)")
    
    col_btn, col_time = st.columns([1, 4])
    with col_btn:
        if st.button("🔄 重新載入數據"):
            st.cache_data.clear()
            st.rerun()
    with col_time:
        st.write(f"系統最後更新時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner('正在從 Yahoo 與 FinMind 獲取長天期歷史數據...'):
        mkt_df = fetch_market_data()
        foreign_df, latest_inst = fetch_finmind_historical()
        
        if mkt_df.empty or foreign_df.empty:
            st.error("資料載入失敗，請檢查網路或 API 狀態！")
            return
            
        data, long_score, short_score = calculate_signals(mkt_df, foreign_df)
        
    # --- 區塊一：籌碼面 (FinMind 最新一日) ---
    st.header("一、 三大法人買賣超動向")
    st.caption(f"資料日期: {latest_inst.get('date', '未知')}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("外資及陸資 (億)", f"{latest_inst.get('外資', 0):.2f}", 
              "偏多" if latest_inst.get('外資', 0) > 0 else "偏空", 
              delta_color="normal" if latest_inst.get('外資', 0) > 0 else "inverse")
    c2.metric("投信 (億)", f"{latest_inst.get('投信', 0):.2f}")
    c3.metric("自營商 (億)", f"{latest_inst.get('自營商', 0):.2f}")
    
    # 新增 Z-score 監控面板
    z_score_val = data['Foreign_Zscore'].iloc[-1]
    z_color = "normal" if z_score_val > 1.5 else ("inverse" if z_score_val < -1.5 else "off")
    c4.metric("📊 外資動能 Z-Score", f"{z_score_val:.2f}", 
              "突破 1.5 觸發多方" if z_score_val > 1.5 else ("跌破 -1.5 觸發空方" if z_score_val < -1.5 else "常態區間"),
              delta_color=z_color)

    # --- 區塊二：模型訊號 ---
    st.header("二、 多空因子共振得分")
    LONG_ENTRY, SHORT_ENTRY = 4.0, 6.0
    
    if long_score >= LONG_ENTRY: signal = "🚨 偏多控盤 (Long)"
    elif short_score >= SHORT_ENTRY: signal = "⚠️ 偏空控盤 (Short)"
    else: signal = "⚖️ 震盪觀望 (Neutral)"

    m1, m2, m3 = st.columns(3)
    m1.metric("多頭總分", f"{long_score:.1f}", delta="進場門檻: 4.0", delta_color="normal")
    bias = ((data['TWII'].iloc[-1] / data['MA60'].iloc[-1]) - 1) * 100
    m2.metric("最新加權指數", f"{data['TWII'].iloc[-1]:.2f}", f"季線乖離: {bias:.2f}%")
    m3.metric("空頭總分", f"{short_score:.1f}", delta="-進場門檻: 6.0", delta_color="inverse")
    
    st.info(f"**模型綜合判定：** {signal}")

    # --- 區塊三：走勢圖表 ---
    st.header("三、 技術面與籌碼圖表")
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.5, 0.25, 0.25])
    
    # 子圖 1: 大盤與季線
    fig.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='silver', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['MA60'], name="季線 (60MA)", line=dict(color='orange', width=2, dash='dot')), row=1, col=1)
    
    # 子圖 2: 費半走勢
    fig.add_trace(go.Scatter(x=data.index, y=data['SOX'], name="費城半導體", line=dict(color='cyan', width=1.5)), row=2, col=1)
    
    # 子圖 3: 外資買賣超柱狀圖 (綠底紅字表示台灣習慣：紅漲綠跌)
    colors = ['#ef4444' if val > 0 else '#22c55e' for val in data['Foreign_Net']]
    fig.add_trace(go.Bar(x=data.index, y=data['Foreign_Net'], name="外資淨買賣(億)", marker_color=colors), row=3, col=1)
    
    fig.update_layout(height=800, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified", 
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
