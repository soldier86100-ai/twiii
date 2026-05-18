import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="台指多因子戰情室 (直覺圖表版)")

# ==========================================
# 1. 資料獲取模組 (Yahoo + FinMind 獨立防呆抽取)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=250)
    
    # 1. 抓取 Yahoo Finance 價格與成交量
    tickers = {
        'TWII': '^TWII', 'SOX': '^SOX', 'TSMC': '2330.TW',
        'TSM_ADR': 'TSM', 'ELEC': '0053.TW', 'FIN': '0055.TW'
    }
    
    mkt_df = pd.DataFrame()
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty: continue
            if df.index.tz is not None: df.index = df.index.tz_localize(None)
            
            if isinstance(df.columns, pd.MultiIndex):
                close_series = df['Close'][ticker].rename(name)
                if name == 'TSMC': vol_series = df['Volume'][ticker].rename('TSMC_Vol')
            else:
                close_series = df['Close'].rename(name)
                if name == 'TSMC': vol_series = df['Volume'].rename('TSMC_Vol')
            
            mkt_df = pd.DataFrame(close_series) if mkt_df.empty else mkt_df.join(close_series, how='outer')
            if name == 'TSMC': mkt_df = mkt_df.join(vol_series, how='outer')
        except Exception:
            pass

    # 2. 抓取 FinMind 籌碼
    url = "https://api.finmindtrade.com/api/v4/data"
    FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"
    params = {"dataset": "TaiwanStockTotalInstitutionalInvestors", "start_date": start_date.strftime("%Y-%m-%d"), "token": FINMIND_TOKEN}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    inst_snapshot = {'date': '資料異常', '外資': 0.0, '投信': 0.0, '自營商': 0.0}
    foreign_df = pd.DataFrame()
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        data = res.json()
        if data.get('msg') == 'success' and len(data.get('data', [])) > 0:
            df_fm = pd.DataFrame(data['data'])
            
            # 獨立抓取各法人最新一筆 (解決時間差導致的 0.00 問題)
            def get_latest_net(kw, ex=''):
                m = df_fm['name'].str.contains(kw, case=False, na=False)
                if ex: m = m & ~df_fm['name'].str.contains(ex, case=False, na=False)
                sub_df = df_fm[m].sort_values('date')
                if sub_df.empty: return 0.0, 'N/A'
                return (sub_df['buy'].iloc[-1] - sub_df['sell'].iloc[-1]) / 100000000, sub_df['date'].iloc[-1]

            f_net, f_date = get_latest_net('外資|Foreign_Investor', '自營商')
            t_net, _ = get_latest_net('投信|Investment_Trust')
            d_net, _ = get_latest_net('自營商|Dealer', '外資|Foreign')
            
            inst_snapshot = {'date': f_date, '外資': f_net, '投信': t_net, '自營商': d_net}

            # 建立外資歷史序列供 Z-score 使用
            f_mask = df_fm['name'].str.contains('外資|Foreign_Investor', case=False, na=False) & ~df_fm['name'].str.contains('自營商', case=False, na=False)
            foreign_df = df_fm[f_mask].copy()
            if not foreign_df.empty:
                foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
                foreign_df['Foreign_Net'] = (foreign_df['buy'] - foreign_df['sell']) / 100000000
                foreign_df.set_index('Date', inplace=True)
    except Exception as e:
        st.warning("籌碼 API 連線異常，暫時略過籌碼因子。")

    if not foreign_df.empty:
        final_df = mkt_df.join(foreign_df[['Foreign_Net']], how='outer').ffill().dropna()
    else:
        final_df = mkt_df.ffill().dropna()
        
    return final_df, inst_snapshot

# ==========================================
# 2. 核心因子引擎 (計算 8 大因子)
# ==========================================
def calculate_v11_signals(df):
    data = df.copy()
    
    data['台指_60MA'] = data['TWII'].rolling(60).mean()
    data['台指_季線斜率'] = data['台指_60MA'].diff(5) / data['台指_60MA'].shift(5) * 100
    data['台指_乖離率'] = (data['TWII'] - data['台指_60MA']) / data['台指_60MA'] * 100
    
    data['電金比'] = data['ELEC'] / data['FIN']
    data['電金比_20MA'] = data['電金比'].rolling(20).mean()
    
    if 'Foreign_Net' in data.columns:
        data['外資_120MA'] = data['Foreign_Net'].rolling(120, min_periods=10).mean()
        data['外資_120STD'] = data['Foreign_Net'].rolling(120, min_periods=10).std().replace(0, np.nan)
        data['外資_Zscore'] = (data['Foreign_Net'] - data['外資_120MA']) / data['外資_120STD']
    else:
        data['外資_Zscore'] = 0.0
    
    data['費半_20MA'] = data['SOX'].rolling(20).mean()
    data['費半_60MA'] = data['SOX'].rolling(60).mean()
    
    data['ADR_120MA'] = data['TSM_ADR'].rolling(120, min_periods=10).mean()
    data['ADR_120STD'] = data['TSM_ADR'].rolling(120, min_periods=10).std().replace(0, np.nan)
    data['ADR_Zscore'] = (data['TSM_ADR'] - data['ADR_120MA']) / data['ADR_120STD']
    
    data['台積電_20MA'] = data['TSMC'].rolling(20).mean()
    data['台積電量_10MA'] = data['TSMC_Vol'].rolling(10).mean()
    
    if data.empty or pd.isna(data['台指_60MA'].iloc[-1]): return data, 0.0, 0.0

    latest = data.iloc[-1]
    
    # 打分邏輯
    f1_l = 1.0 if (latest['TWII'] > latest['台指_60MA']) and (latest['台指_季線斜率'] > 0.1) else 0.0
    f2_l = 0.8 if latest['電金比'] > latest['電金比_20MA'] else 0.0
    f3_l = 1.5 if latest['外資_Zscore'] > 1.5 else 0.0
    f4_l = 1.8 if (latest['SOX'] > latest['費半_20MA']) and (latest['SOX'] > latest['費半_60MA']) else 0.0
    f5_l = 4.0 if latest['ADR_Zscore'] > 1.0 else 0.0
    f6_l = 0.8 if latest['TSMC'] > latest['台積電_20MA'] else 0.0
    f7_l = 0.5 if latest['TSMC_Vol'] > 1.5 * latest['台積電量_10MA'] else 0.0
    f8_l = 0.8 if latest['台指_乖離率'] < -8 else 0.0

    f1_s = 1.2 if (latest['TWII'] < latest['台指_60MA']) and (latest['台指_季線斜率'] < -0.1) else 0.0
    f2_s = 0.5 if latest['電金比'] < latest['電金比_20MA'] else 0.0
    f3_s = 1.5 if latest['外資_Zscore'] < -1.5 else 0.0
    f4_s = 1.8 if (latest['SOX'] < latest['費半_20MA']) and (latest['SOX'] < latest['費半_60MA']) else 0.0
    f5_s = 4.0 if latest['ADR_Zscore'] < -1.0 else 0.0
    f6_s = 0.5 if latest['TSMC'] < latest['台積電_20MA'] else 0.0
    f8_s = 0.8 if latest['台指_乖離率'] > 8 else 0.0

    long_score = f1_l + f2_l + f3_l + f4_l + f5_l + f6_l + f7_l + f8_l
    short_score = f1_s + f2_s + f3_s + f4_s + f5_s + f6_s + f8_s
    
    return data, long_score, short_score

# ==========================================
# 3. 畫面呈現與圖表繪製
# ==========================================
def main():
    st.title("📊 台指多因子量化戰情室")
    
    col_btn, col_time = st.columns([1, 4])
    with col_btn:
        if st.button("🔄 重新同步數據"):
            st.cache_data.clear()
            st.rerun()
    with col_time:
        st.write(f"系統最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner('正在計算八大因子與生成圖表...'):
        data, inst_snapshot = fetch_all_data()
        data, long_score, short_score = calculate_v11_signals(data)

    # ------------------------------------------
    # 區塊一：開頭直球對決 (訊號情境判斷)
    # ------------------------------------------
    LONG_ENTRY, SHORT_ENTRY = 4.0, 6.0
    
    if long_score >= LONG_ENTRY:
        st.success(f"🔥 **【偏多情境】觸發做多訊號！** (多方總分: {long_score:.1f} / 空方總分: {short_score:.1f})")
    elif short_score >= SHORT_ENTRY:
        st.error(f"⚠️ **【偏空情境】觸發做空訊號！** (空方總分: {short_score:.1f} / 多方總分: {long_score:.1f})")
    else:
        st.info(f"⚖️ **【震盪整理】維持空手觀望。** (多方總分: {long_score:.1f} / 空方總分: {short_score:.1f})")

    st.markdown("---")

    # 法人現況小儀表板
    st.caption(f"籌碼發布日期: {inst_snapshot.get('date', '未知')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("外資現貨 (億)", f"{inst_snapshot.get('外資', 0):.2f}")
    c2.metric("投信現貨 (億)", f"{inst_snapshot.get('投信', 0):.2f}")
    c3.metric("自營商現貨 (億)", f"{inst_snapshot.get('自營商', 0):.2f}")
    z_score = data['外資_Zscore'].iloc[-1] if not data.empty and '外資_Zscore' in data else 0.0
    c4.metric("外資動能 Z-Score", f"{z_score:.2f}")

    st.markdown("---")

    # ------------------------------------------
    # 區塊二：八大因子圖表整併
    # ------------------------------------------
    st.header("📈 核心因子視覺化圖表")

    if data.empty:
        st.error("資料不足，無法繪製圖表。")
        return

    # [圖表 1] 大盤結構 (F1 季線 + F8 乖離率)
    st.subheader("① 大盤結構與乖離 (因子 1, 8)")
    fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig1.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='white')), row=1, col=1)
    fig1.add_trace(go.Scatter(x=data.index, y=data['台指_60MA'], name="季線(60MA)", line=dict(color='orange', dash='dash')), row=1, col=1)
    
    bias_colors = ['red' if b > 8 else ('green' if b < -8 else 'gray') for b in data['台指_乖離率']]
    fig1.add_trace(go.Bar(x=data.index, y=data['台指_乖離率'], name="季線乖離率(%)", marker_color=bias_colors), row=2, col=1)
    fig1.add_hline(y=8, line_dash="dot", line_color="red", row=2, col=1)
    fig1.add_hline(y=-8, line_dash="dot", line_color="green", row=2, col=1)
    fig1.update_layout(height=450, margin=dict(t=30, b=10), hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

    # [圖表 2] 半導體雙星 (F4 費半 + F6 台積電 + F7 台積電爆量)
    st.subheader("② 半導體雙星動能 (因子 4, 6, 7)")
    fig2 = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.4, 0.4, 0.2], vertical_spacing=0.05)
    fig2.add_trace(go.Scatter(x=data.index, y=data['SOX'], name="費半指數", line=dict(color='cyan')), row=1, col=1)
    fig2.add_trace(go.Scatter(x=data.index, y=data['費半_20MA'], name="費半20MA", line=dict(color='yellow', dash='dot')), row=1, col=1)
    
    fig2.add_trace(go.Scatter(x=data.index, y=data['TSMC'], name="台積電現貨", line=dict(color='red')), row=2, col=1)
    fig2.add_trace(go.Scatter(x=data.index, y=data['台積電_20MA'], name="台積電20MA", line=dict(color='orange', dash='dot')), row=2, col=1)
    
    vol_colors = ['#ef4444' if v > 1.5 * m else '#555555' for v, m in zip(data['TSMC_Vol'], data['台積電量_10MA'])]
    fig2.add_trace(go.Bar(x=data.index, y=data['TSMC_Vol'], name="台積電成交量", marker_color=vol_colors), row=3, col=1)
    fig2.update_layout(height=600, margin=dict(t=30, b=10), hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

    # [圖表 3] 資金與籌碼流向 (F2 電金比 + F3 外資Z + F5 ADR_Z)
    st.subheader("③ 資金與籌碼流向 (因子 2, 3, 5)")
    fig3 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5], vertical_spacing=0.08)
    fig3.add_trace(go.Scatter(x=data.index, y=data['電金比'], name="電金比", line=dict(color='magenta')), row=1, col=1)
    fig3.add_trace(go.Scatter(x=data.index, y=data['電金比_20MA'], name="電金比20MA", line=dict(color='purple', dash='dot')), row=1, col=1)
    
    fig3.add_trace(go.Scatter(x=data.index, y=data['外資_Zscore'], name="外資 Z-score", line=dict(color='#22c55e')), row=2, col=1)
    fig3.add_trace(go.Scatter(x=data.index, y=data['ADR_Zscore'], name="ADR Z-score", line=dict(color='#3b82f6')), row=2, col=1)
    fig3.add_hline(y=1.5, line_dash="dot", line_color="red", row=2, col=1)
    fig3.add_hline(y=-1.5, line_dash="dot", line_color="green", row=2, col=1)
    fig3.update_layout(height=500, margin=dict(t=30, b=10), hovermode="x unified")
    st.plotly_chart(fig3, use_container_width=True)

if __name__ == "__main__":
    main()
