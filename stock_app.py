import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="台指多因子波段戰情室 v11")

# ==========================================
# 1. 資料獲取模組
# ==========================================
@st.cache_data(ttl=3600)  # 快取 1 小時避免重複抓取
def fetch_market_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=250) # 抓取足夠天數算 120MA
    
    # 透過 yfinance 抓取相關標的
    tickers = {
        '大盤': '^TWII',
        '費半': '^SOX',
        '台積電': '2330.TW',
        '台積電ADR': 'TSM'
    }
    
    raw_data = {}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            raw_data[name] = df['Close'].values.flatten()
            if name == '大盤':
                dates = df.index
        except Exception as e:
            st.error(f"抓取 {name} 失敗: {e}")

    # 合併為單一 DataFrame
    mkt_df = pd.DataFrame({
        'Date': dates,
        'TWII': raw_data.get('大盤', []),
        'SOX': raw_data.get('費半', []),
        'TSMC': raw_data.get('台積電', []),
        'TSM_ADR': raw_data.get('台積電ADR', [])
    }).set_index('Date').ffill().dropna()
    
    return mkt_df

@st.cache_data(ttl=3600)
def fetch_institutional_data():
    # 使用 FinMind API 抓取三大法人買賣超 (範例)
    # 實戰建議申請 Token 放進 requests header
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        if data['msg'] == 'success':
            df = pd.DataFrame(data['data'])
            # 篩選外資並加總
            foreign_df = df[df['name'] == '外資及陸資(不含外資自營商)'].copy()
            foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
            foreign_df.set_index('Date', inplace=True)
            return foreign_df['buy'] - foreign_df['sell']
    except Exception as e:
        st.warning("FinMind API 呼叫失敗，暫不計入籌碼因子。")
        return pd.Series()
    return pd.Series()

# ==========================================
# 2. 策略引擎與多空打分
# ==========================================
def calculate_signals(df):
    data = df.copy()
    
    # 算術指標
    data['MA60'] = data['TWII'].rolling(60).mean()
    data['SOX_MA20'] = data['SOX'].rolling(20).mean()
    data['TSMC_MA20'] = data['TSMC'].rolling(20).mean()
    
    # 取最新一天資料
    latest = data.iloc[-1]
    
    # 初始化分數 (根據 v11 權重設定)
    long_score, short_score = 0.0, 0.0
    
    # 因子 1: 大盤與季線
    if latest['TWII'] > latest['MA60']:
        long_score += 1.0
    elif latest['TWII'] < latest['MA60']:
        short_score += 1.2
        
    # 因子 4: 費城半導體
    if latest['SOX'] > latest['SOX_MA20']:
        long_score += 1.8
    elif latest['SOX'] < latest['SOX_MA20']:
        short_score += 1.8
        
    # 因子 6: 台積電現貨
    if latest['TSMC'] > latest['TSMC_MA20']:
        long_score += 0.8
    elif latest['TSMC'] < latest['TSMC_MA20']:
        short_score += 0.5
        
    return data, long_score, short_score

# ==========================================
# 3. Streamlit 介面佈局
# ==========================================
def main():
    st.title("📈 台指多因子量化戰情室 v11 (多空平衡版)")
    st.write(f"系統更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    if st.button("🔄 重新載入數據"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner('正在載入數據並計算多因子模型...'):
        df = fetch_market_data()
        foreign_net_buy = fetch_institutional_data()
        
        if df.empty:
            st.error("市場資料載入失敗！")
            return
            
        data, long_score, short_score = calculate_signals(df)
        
    # --- 戰略儀表板 ---
    st.header("一、 模型總分與波段訊號")
    
    LONG_ENTRY = 4.0
    SHORT_ENTRY = 6.0
    
    if long_score >= LONG_ENTRY:
        signal = "🚨 偏多控盤 (Long)"
        color = "normal" 
    elif short_score >= SHORT_ENTRY:
        signal = "⚠️ 偏空控盤 (Short)"
        color = "inverse"
    else:
        signal = "⚖️ 震盪觀望 (Neutral)"
        color = "off"

    col1, col2, col3 = st.columns(3)
    col1.metric("多頭得分 (Long Score)", f"{long_score:.1f}", delta="門檻: 4.0", delta_color="normal")
    col2.metric("最新加權指數", f"{data['TWII'].iloc[-1]:.2f}", f"季線: {data['MA60'].iloc[-1]:.2f}")
    col3.metric("空頭得分 (Short Score)", f"{short_score:.1f}", delta="-門檻: 6.0", delta_color="inverse")
    
    st.info(f"**當前模型判定狀態：** {signal}")

    # --- Plotly 視覺化圖表 ---
    st.header("二、 價格結構與技術指標")
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1, row_heights=[0.7, 0.3])
    
    # 子圖 1: 台灣加權指數與均線
    fig.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='white', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['MA60'], name="季線 (60MA)", line=dict(color='orange', width=2, dash='dot')), row=1, col=1)
    
    # 子圖 2: 費半走勢對比
    fig.add_trace(go.Scatter(x=data.index, y=data['SOX'], name="費城半導體", line=dict(color='cyan', width=1.5)), row=2, col=1)
    
    fig.update_layout(height=600, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0),
                      hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
