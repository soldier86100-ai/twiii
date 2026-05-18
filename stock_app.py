import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="台指多因子量化戰情室 v11 完全體")

# ==========================================
# 1. 資料獲取模組 (Yahoo Finance 6大標的 + FinMind外資)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_all_data():
    """抓取完整8大因子所需的全部市場與籌碼歷史資料"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=250)
    
    # 價格面 6 大核心標的
    tickers = {
        'TWII': '^TWII',       # 大盤
        'SOX': '^SOX',         # 費城半導體
        'TSMC': '2330.TW',     # 台積電現貨
        'TSM_ADR': 'TSM',       # 台積電ADR
        'ELEC': '0053.TW',     # 電子指數代用 (元大電子)
        'FIN': '0055.TW'       # 金融指數代用 (元大金融)
    }
    
    mkt_df = pd.DataFrame()
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty: continue

            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            # 處理新版 yfinance MultiIndex 與 提取成交量
            if isinstance(df.columns, pd.MultiIndex):
                close_series = df['Close'][ticker].rename(name)
                if name == 'TSMC':
                    vol_series = df['Volume'][ticker].rename('TSMC_Vol')
            else:
                close_series = df['Close'].rename(name)
                if name == 'TSMC':
                    vol_series = df['Volume'].rename('TSMC_Vol')
            
            if mkt_df.empty:
                mkt_df = pd.DataFrame(close_series)
            else:
                mkt_df = mkt_df.join(close_series, how='outer')
                
            if name == 'TSMC':
                mkt_df = mkt_df.join(vol_series, how='outer')
        except Exception as e:
            st.warning(f"抓取 {name} 失敗: {e}")

    # 串接 FinMind 外資籌碼
    url = "https://api.finmindtrade.com/api/v4/data"
    FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "token": FINMIND_TOKEN
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        data = res.json()
        if data.get('msg') == 'success' and len(data.get('data', [])) > 0:
            df_fm = pd.DataFrame(data['data'])
            foreign_df = df_fm[df_fm['name'].str.contains('外資|Foreign_Investor', na=False, case=False) & ~df_fm['name'].str.contains('自營商', na=False)].copy()
            
            foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
            foreign_df['Foreign_Net'] = (foreign_df['buy'] - foreign_df['sell']) / 100000000
            
            # 法人面板快照
            latest_date = df_fm['date'].max()
            latest_df = df_fm[df_fm['date'] == latest_date]
            def get_net_buy(kw, ex=''):
                m = latest_df['name'].str.contains(kw, na=False, case=False)
                if ex: m = m & ~latest_df['name'].str.contains(ex, na=False, case=False)
                return (latest_df[m]['buy'].sum() - latest_df[m]['sell'].sum()) / 100000000

            inst_snapshot = {'date': latest_date, '外資': get_net_buy('外資', '自營商'), '投信': get_net_buy('投信'), '自營商': get_net_buy('自營商')}
            
            foreign_df.set_index('Date', inplace=True)
            final_df = mkt_df.join(foreign_df[['Foreign_Net']], how='outer').ffill().dropna()
            return final_df, inst_snapshot
    except Exception as e:
        st.error(f"籌碼模組載入失敗: {e}")
        
    return mkt_df.ffill().dropna(), {}

# ==========================================
# 2. v11 完整八大因子打分引擎
# ==========================================
def calculate_v11_signals(df):
    data = df.copy()
    
    # 1. 大盤與季線指標
    data['台指_60MA'] = data['TWII'].rolling(60).mean()
    data['台指_季線斜率'] = data['台指_60MA'].diff(5) / data['台指_60MA'].shift(5) * 100
    data['台指_乖離率'] = (data['TWII'] - data['台指_60MA']) / data['台指_60MA'] * 100
    
    # 2. 電金比
    data['電金比'] = data['ELEC'] / data['FIN']
    data['電金比_20MA'] = data['電金比'].rolling(20).mean()
    
    # 3. 外資 Z-score
    data['外資_120MA'] = data['Foreign_Net'].rolling(120, min_periods=10).mean()
    data['外資_120STD'] = data['Foreign_Net'].rolling(120, min_periods=10).std().replace(0, np.nan)
    data['外資_Zscore'] = (data['Foreign_Net'] - data['外資_120MA']) / data['外資_120STD']
    
    # 4. 費半均線
    data['費半_20MA'] = data['SOX'].rolling(20).mean()
    data['費半_60MA'] = data['SOX'].rolling(60).mean()
    
    # 5. ADR Z-score
    data['ADR_120MA'] = data['TSM_ADR'].rolling(120, min_periods=10).mean()
    data['ADR_120STD'] = data['TSM_ADR'].rolling(120, min_periods=10).std().replace(0, np.nan)
    data['ADR_Zscore'] = (data['TSM_ADR'] - data['ADR_120MA']) / data['ADR_120STD']
    
    # 6 & 7. 台積電均線與量
    data['台積電_20MA'] = data['TSMC'].rolling(20).mean()
    data['台積電量_10MA'] = data['TSMC_Vol'].rolling(10).mean()
    
    if data.empty or pd.isna(data['台指_60MA'].iloc[-1]):
        return data, 0.0, 0.0, {}

    latest = data.iloc[-1]
    
    # --- 八大核心因子共振評估 ---
    f1_long = 1.0 if (latest['TWII'] > latest['台指_60MA']) and (latest['台指_季線斜率'] > 0.1) else 0.0
    f2_long = 0.8 if latest['電金比'] > latest['電金比_20MA'] else 0.0
    f3_long = 1.5 if latest['外資_Zscore'] > 1.5 else 0.0
    f4_long = 1.8 if (latest['SOX'] > latest['費半_20MA']) and (latest['SOX'] > latest['費半_60MA']) else 0.0
    f5_long = 4.0 if latest['ADR_Zscore'] > 1.0 else 0.0
    f6_long = 0.8 if latest['TSMC'] > latest['台積電_20MA'] else 0.0
    f7_long = 0.5 if latest['TSMC_Vol'] > 1.5 * latest['台積電量_10MA'] else 0.0
    f8_long = 0.8 if latest['台指_乖離率'] < -8 else 0.0

    f1_short = 1.2 if (latest['TWII'] < latest['台指_60MA']) and (latest['台指_季線斜率'] < -0.1) else 0.0
    f2_short = 0.5 if latest['電金比'] < latest['電金比_20MA'] else 0.0
    f3_short = 1.5 if latest['外資_Zscore'] < -1.5 else 0.0
    f4_short = 1.8 if (latest['SOX'] < latest['費半_20MA']) and (latest['SOX'] < latest['費半_60MA']) else 0.0
    f5_short = 4.0 if latest['ADR_Zscore'] < -1.0 else 0.0
    f6_short = 0.5 if latest['TSMC'] < latest['台積電_20MA'] else 0.0
    f8_short = 0.8 if latest['台指_乖離率'] > 8 else 0.0

    long_score = f1_long + f2_long + f3_long + f4_long + f5_long + f6_long + f7_long + f8_long
    short_score = f1_short + f2_short + f3_short + f4_short + f5_short + f6_short + f8_short

    factor_details = {
        '多頭': [f1_long, f2_long, f3_long, f4_long, f5_long, f6_long, f7_long, f8_long],
        '空頭': [f1_short, f2_short, f3_short, f4_short, f5_short, f6_short, f8_short]
    }
    
    return data, long_score, short_score, factor_details

# ==========================================
# 3. 儀表板畫面呈現
# ==========================================
def main():
    st.title("📊 台指多因子波段量化戰情室 v11 (八大因子完全體)")
    st.write(f"系統最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if st.button("🔄 重新同步全市場數據"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner('正在同步大盤、費半、台積電、ADR、電金比及歷史籌碼中...'):
        data, inst_snapshot = fetch_all_data()
        if data.empty or '台指_60MA' not in calculate_v11_signals(data)[0].columns:
            data, long_score, short_score, factor_details = calculate_v11_signals(data)
        else:
            data, long_score, short_score, factor_details = calculate_v11_signals(data)

    # --- 區塊一：籌碼現況 ---
    st.header("一、 最新三大法人買賣超")
    st.caption(f"籌碼發布日期: {inst_snapshot.get('date', '同步中')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("外資現貨 (億)", f"{inst_snapshot.get('外資', 0):.2f}")
    c2.metric("投信現貨 (億)", f"{inst_snapshot.get('投信', 0):.2f}")
    c3.metric("自營商現貨 (億)", f"{inst_snapshot.get('自營商', 0):.2f}")
    c4.metric("外資動能 Z-Score", f"{data['外資_Zscore'].iloc[-1]:.2f}")

    # --- 區塊二：決策燈號 ---
    st.header("二、 v11 策略決策總分")
    LONG_ENTRY, SHORT_ENTRY = 4.0, 6.0
    
    if long_score >= LONG_ENTRY: signal = "🚨 多頭觸發進場 (LONG ENTRY)"
    elif short_score >= SHORT_ENTRY: signal = "⚠️ 空頭觸發進場 (SHORT ENTRY)"
    else: signal = "⚖️ 趨勢不明，空手觀望 (NEUTRAL)"

    m1, m2, m3 = st.columns(3)
    m1.metric("多頭共振總分", f"{long_score:.1f}", f"進場門檻: {LONG_ENTRY}")
    m2.metric("最新加權指數", f"{data['TWII'].iloc[-1]:.2f}", f"季線乖離: {data['台指_乖離率'].iloc[-1]:.2f}%")
    m3.metric("空頭共振總分", f"{short_score:.1f}", f"進場門檻: {SHORT_ENTRY}")
    st.info(f"**模型完全體綜合判定：** {signal}")

    # --- 區塊三：因子明細展開 ---
    with st.expander("🔍 點擊查看當下各因子得分明細 (權重對照表)"):
        col_l, col_s = st.columns(2)
        with col_l:
            st.subheader("多頭因子明細")
            labels_l = ["F1 大盤站上季線且斜率翻揚", "F2 電子指數強於金融指數", "F3 外資極端買超 (Z>1.5)", "F4 費半多頭排列", "F5 台積電ADR強勢溢價", "F6 台積電站上月線", "F7 台積電成交量暴量", "F8 大盤超跌嚴重乖離"]
            for label, score in zip(labels_l, factor_details.get('多頭', [])):
                st.write(f"{'✅' if score > 0 else '❌'} {label} : 得 {score} 分")
        with col_s:
            st.subheader("空頭因子明細")
            labels_s = ["F1 大盤跌破季線且斜率下彎", "F2 金融指數強於電子指數", "F3 外資極端賣超 (Z<-1.5)", "F4 費半空頭排列", "F5 台積電ADR弱勢折價", "F6 台積電跌破月線", "F8 大盤超買高檔乖離"]
            for label, score in zip(labels_s, factor_details.get('空頭', [])):
                st.write(f"{'✅' if score > 0 else '❌'} {label} : 得 {score} 分")

    # --- 區塊四：高階視覺化圖表 ---
    st.header("三、 技術與籌碼綜合圖表")
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.5, 0.25, 0.25])
    fig.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='silver', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['台指_60MA'], name="季線 (60MA)", line=dict(color='orange', width=2, dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['SOX'], name="費城半導體", line=dict(color='cyan', width=1.5)), row=2, col=1)
    colors = ['#ef4444' if val > 0 else '#22c55e' for val in data['Foreign_Net']]
    fig.add_trace(go.Bar(x=data.index, y=data['Foreign_Net'], name="外資淨買賣(億)", marker_color=colors), row=3, col=1)
    fig.update_layout(height=800, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
