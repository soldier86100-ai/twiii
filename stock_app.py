import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="台指多因子戰情室 (V11版)")

# ==========================================
# 1. 資料獲取模組 (Yahoo + FinMind 獨立防呆抽取)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=250)
    
    # 1. 抓取 Yahoo Finance 價格與成交量 (改用 Ticker history 寫法提升穩定性)
    tickers = {
        'TWII': '^TWII', 'SOX': '^SOX', 'TSMC': '2330.TW',
        'TSM_ADR': 'TSM', 'ELEC': '0053.TW', 'FIN': '0055.TW'
    }
    
    mkt_df = pd.DataFrame()
    for name, ticker in tickers.items():
        try:
            tk = yf.Ticker(ticker)
            df = tk.history(start=start_date, end=end_date)
            
            if df.empty: 
                continue
                
            # 清除時區資訊以便後續對齊合併
            if df.index.tz is not None: 
                df.index = df.index.tz_localize(None)
            
            # 取出收盤價並重新命名
            close_series = df['Close'].rename(name)
            
            if mkt_df.empty:
                mkt_df = pd.DataFrame(close_series)
            else:
                mkt_df = mkt_df.join(close_series, how='outer')
                
            # 如果是台積電，額外抓取成交量
            if name == 'TSMC': 
                vol_series = df['Volume'].rename('TSMC_Vol')
                mkt_df = mkt_df.join(vol_series, how='outer')
                
        except Exception as e:
            # 單一標的抓取失敗先略過，交由後續防呆機制處理
            pass

    # 2. 抓取 FinMind 籌碼
    url = "https://api.finmindtrade.com/api/v4/data"
    FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"
    params = {"dataset": "TaiwanStockTotalInstitutionalInvestors", "start_date": start_date.strftime("%Y-%m-%d"), "token": FINMIND_TOKEN}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    foreign_df = pd.DataFrame()
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        data = res.json()
        if data.get('msg') == 'success' and len(data.get('data', [])) > 0:
            df_fm = pd.DataFrame(data['data'])
            f_mask = df_fm['name'].str.contains('外資|Foreign_Investor', case=False, na=False) & ~df_fm['name'].str.contains('自營商', case=False, na=False)
            foreign_df = df_fm[f_mask].copy()
            if not foreign_df.empty:
                foreign_df['Date'] = pd.to_datetime(foreign_df['date'])
                foreign_df['Foreign_Net'] = (foreign_df['buy'] - foreign_df['sell']) / 100000000
                foreign_df.set_index('Date', inplace=True)
    except Exception as e:
        pass

    if not foreign_df.empty:
        final_df = mkt_df.join(foreign_df[['Foreign_Net']], how='outer').ffill().dropna()
        has_foreign = True
    else:
        final_df = mkt_df.ffill().dropna()
        has_foreign = False
        
    return final_df, has_foreign

# ==========================================
# 2. 核心因子引擎 (V11 邏輯: 11因子 + 門票機制)
# ==========================================
def calculate_v11_signals(df, has_foreign):
    data = df.copy()
    
    # ── 1. 大盤趨勢與布林通道 ──
    data['台指_20MA'] = data['TWII'].rolling(20).mean()
    data['台指_60MA'] = data['TWII'].rolling(60).mean()
    data['台指_季線斜率'] = data['台指_60MA'].diff(5) / data['台指_60MA'].shift(5) * 100
    data['台指_乖離率'] = (data['TWII'] - data['台指_60MA']) / data['台指_60MA'] * 100
    
    data['BB_STD20'] = data['TWII'].rolling(20).std()
    data['BB_上軌'] = data['台指_20MA'] + 2 * data['BB_STD20']
    data['BB_下軌'] = data['台指_20MA'] - 2 * data['BB_STD20']
    
    # 計算 RSI 14
    delta = data['TWII'].diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    data['台指_RSI14'] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    
    # ── 2. 費半 ──
    data['費半_20MA'] = data['SOX'].rolling(20).mean()
    data['費半_60MA'] = data['SOX'].rolling(60).mean()
    
    # ── 3. 台積電 ──
    data['台積電_20MA'] = data['TSMC'].rolling(20).mean()
    data['台積電量_10MA'] = data['TSMC_Vol'].rolling(10).mean()
    
    # ── 4. 電金比 ──
    data['電金比'] = data['ELEC'] / data['FIN']
    data['電金比_20MA'] = data['電金比'].rolling(20).mean()
    data['電金比_60MA'] = data['電金比'].rolling(60).mean()  # V11 門票用
    
    # ── 5. 外資 Z-score 與動能 ──
    if has_foreign and 'Foreign_Net' in data.columns:
        data['外資_120MA'] = data['Foreign_Net'].rolling(120, min_periods=10).mean()
        data['外資_120STD'] = data['Foreign_Net'].rolling(120, min_periods=10).std().replace(0, np.nan)
        data['外資_Zscore'] = (data['Foreign_Net'] - data['外資_120MA']) / data['外資_120STD']
        data['外資_5MA'] = data['Foreign_Net'].rolling(5).mean()
    else:
        data['Foreign_Net'] = 0.0
        data['外資_Zscore'] = 0.0
        data['外資_5MA'] = 0.0
        
    # ── 6. ADR Z-score ──
    data['ADR_120MA'] = data['TSM_ADR'].rolling(120, min_periods=10).mean()
    data['ADR_120STD'] = data['TSM_ADR'].rolling(120, min_periods=10).std().replace(0, np.nan)
    data['ADR_Zscore'] = (data['TSM_ADR'] - data['ADR_120MA']) / data['ADR_120STD']
    
    if data.empty or pd.isna(data['台指_60MA'].iloc[-1]): 
        return data, False, False, 0.0, 0.0

    latest = data.iloc[-1]
    
    # ── V11 門票機制 ──
    gate_long = (
        (latest['SOX'] > latest['費半_20MA'] and latest['SOX'] > latest['費半_60MA']) and 
        (latest['ADR_Zscore'] > 0.8 or latest['外資_Zscore'] > 1.2) and 
        (latest['電金比'] > latest['電金比_60MA'])
    )
    
    gate_short = (
        (latest['SOX'] < latest['費半_20MA'] and latest['SOX'] < latest['費半_60MA']) and 
        (latest['ADR_Zscore'] < -1.2 or latest['外資_Zscore'] < -1.5) and 
        (latest['電金比'] < latest['電金比_60MA'])
    )

    # ── V11 打分邏輯 (均等配分) ──
    # 多頭得分
    f1_l = 1.0 if (latest['TWII'] > latest['台指_60MA']) and (latest['台指_季線斜率'] > 0.1) else 0.0
    f2_l = 1.0 if latest['電金比'] > latest['電金比_20MA'] else 0.0
    f3_l = 2.0 if latest['外資_Zscore'] > 1.2 else 0.0
    f4_l = 2.0 if (latest['SOX'] > latest['費半_20MA']) and (latest['SOX'] > latest['費半_60MA']) else 0.0
    f5_l = 2.0 if latest['ADR_Zscore'] > 0.8 else 0.0
    f6_l = 1.0 if latest['TSMC'] > latest['台積電_20MA'] else 0.0
    f7_l = 0.5 if latest['TSMC_Vol'] > 1.5 * latest['台積電量_10MA'] else 0.0
    f8_l = 1.0 if latest['台指_乖離率'] < -8 else 0.0
    f9_l = 1.0 if latest['台指_RSI14'] < 40 else 0.0
    f10_l = 1.0 if latest['外資_5MA'] > 0 else 0.0
    f11_l = 0.5 if latest['TWII'] < latest['BB_下軌'] else 0.0

    # 空頭得分 (注意空頭的閾值更嚴格，且趨勢權重較高)
    f1_s = 1.5 if (latest['TWII'] < latest['台指_60MA']) and (latest['台指_季線斜率'] < -0.1) else 0.0
    f2_s = 1.0 if latest['電金比'] < latest['電金比_20MA'] else 0.0
    f3_s = 2.0 if latest['外資_Zscore'] < -1.5 else 0.0
    f4_s = 2.0 if (latest['SOX'] < latest['費半_20MA']) and (latest['SOX'] < latest['費半_60MA']) else 0.0
    f5_s = 2.0 if latest['ADR_Zscore'] < -1.2 else 0.0
    f6_s = 1.0 if latest['TSMC'] < latest['台積電_20MA'] else 0.0
    f7_s = 0.5 if latest['TSMC_Vol'] > 1.5 * latest['台積電量_10MA'] else 0.0
    f8_s = 1.0 if latest['台指_乖離率'] > 8 else 0.0
    f9_s = 1.0 if latest['台指_RSI14'] > 65 else 0.0
    f10_s = 1.0 if latest['外資_5MA'] < 0 else 0.0
    f11_s = 0.5 if latest['TWII'] > latest['BB_上軌'] else 0.0

    long_score = f1_l + f2_l + f3_l + f4_l + f5_l + f6_l + f7_l + f8_l + f9_l + f10_l + f11_l
    short_score = f1_s + f2_s + f3_s + f4_s + f5_s + f6_s + f7_s + f8_s + f9_s + f10_s + f11_s
    
    return data, gate_long, gate_short, long_score, short_score

# ==========================================
# 3. 畫面呈現與 8 大圖表繪製
# ==========================================
def main():
    st.title("📊 台指多因子量化戰情室 (V11 均衡多空勝率版)")
    
    col_btn, col_time = st.columns([1, 4])
    with col_btn:
        if st.button("🔄 重新同步數據"):
            st.cache_data.clear()
            st.rerun()
    with col_time:
        st.write(f"最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner('正在計算 V11 因子與生成圖表...'):
        data, has_foreign = fetch_all_data()
        
        # --- 🛡️ 新增防呆檢查：避免 KeyError ---
        if data.empty:
            st.error("❌ 市場資料完全載入失敗！請檢查伺服器網路連線。")
            return
            
        # 檢查必備的 Yahoo 欄位是否都有成功抓到
        required_cols = ['TWII', 'SOX', 'TSMC', 'TSMC_Vol', 'ELEC', 'FIN', 'TSM_ADR']
        missing_cols = [col for col in required_cols if col not in data.columns]
        
        if missing_cols:
            st.error(f"❌ Yahoo Finance 暫時連線失敗，缺少以下資料：{', '.join(missing_cols)}")
            st.warning("💡 解決建議：請點擊左上角「🔄 重新同步數據」。(這通常是因為 Yahoo 暫時阻擋了伺服器 IP)")
            return
        # --------------------------------------

        # 確認資料齊全後，才進入計算
        data, gate_long, gate_short, long_score, short_score = calculate_v11_signals(data, has_foreign)

    # ------------------------------------------
    # 區塊一：開頭直球對決 (V11 雙重認證)
    # ------------------------------------------
    ENTRY_THRESH = 4.5
    
    st.markdown("### 🎯 策略當下訊號")
    col_gate, col_score = st.columns(2)
    
    with col_gate:
        st.markdown("#### 🎫 大環境門票狀態")
        if gate_long:
            st.success("✅ **取得【做多門票】** (費半偏多 + 資金匯入 + 電金比偏多)")
        elif gate_short:
            st.error("🚨 **取得【做空門票】** (費半偏空 + 資金匯出 + 電金比偏空)")
        else:
            st.info("🔒 **無門票** (大環境未形成共識，濾網阻擋進場)")

    with col_score:
        st.markdown("#### 💯 11因子共振得分")
        st.write(f"🟢 **多頭得分:** {long_score:.1f} / 4.5 門檻")
        st.write(f"🔴 **空頭得分:** {short_score:.1f} / 4.5 門檻")

    # 綜合判斷
    if gate_long and long_score >= ENTRY_THRESH:
        st.success(f"🔥 **【強烈看多】大環境門票達成 且 因子共振達標！觸發做多訊號！**")
    elif gate_short and short_score >= ENTRY_THRESH:
        st.error(f"⚠️ **【強烈看空】大環境門票達成 且 因子共振達標！觸發做空訊號！**")
    else:
        st.warning("⚖️ **【維持空手觀望】未同時滿足門票與 4.5 分門檻，避免假突破。**")

    st.markdown("---")

    # ------------------------------------------
    # 區塊二：八大獨立圖表展示
    # ------------------------------------------
    
    # 1. 台股大盤 vs 季線還有乖離率
    st.subheader("1. 台股大盤與季線乖離率")
    fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig1.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='silver')), row=1, col=1)
    fig1.add_trace(go.Scatter(x=data.index, y=data['台指_60MA'], name="季線(60MA)", line=dict(color='orange', dash='dash')), row=1, col=1)
    bias_colors = ['#ef4444' if b > 8 else ('#22c55e' if b < -8 else '#555555') for b in data['台指_乖離率']]
    fig1.add_trace(go.Bar(x=data.index, y=data['台指_乖離率'], name="季線乖離率(%)", marker_color=bias_colors), row=2, col=1)
    fig1.add_hline(y=8, line_dash="dot", line_color="red", row=2, col=1, annotation_text="超買 (>8%)")
    fig1.add_hline(y=-8, line_dash="dot", line_color="green", row=2, col=1, annotation_text="超賣 (<-8%)")
    fig1.update_layout(height=450, margin=dict(t=10, b=10), hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

    colA, colB = st.columns(2)
    with colA:
        # 2. 費城半導體 及費半月線及季線
        st.subheader("2. 費城半導體 (大環境門票1)")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=data.index, y=data['SOX'], name="費半指數", line=dict(color='cyan')))
        fig2.add_trace(go.Scatter(x=data.index, y=data['費半_20MA'], name="月線(20MA)", line=dict(color='yellow', dash='dot')))
        fig2.add_trace(go.Scatter(x=data.index, y=data['費半_60MA'], name="季線(60MA)", line=dict(color='orange', dash='dash')))
        fig2.update_layout(height=350, margin=dict(t=10, b=10), hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)

    with colB:
        # 3. 電金比，電金比月線與季線
        st.subheader("3. 資金輪動：電金比 (大環境門票3)")
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=data.index, y=data['電金比'], name="電金比", line=dict(color='magenta')))
        fig4.add_trace(go.Scatter(x=data.index, y=data['電金比_20MA'], name="月線(20MA)", line=dict(color='purple', dash='dot')))
        fig4.add_trace(go.Scatter(x=data.index, y=data['電金比_60MA'], name="季線(60MA)", line=dict(color='gray', dash='dash')))
        fig4.update_layout(height=350, margin=dict(t=10, b=10), hovermode="x unified")
        st.plotly_chart(fig4, use_container_width=True)

    # 4. 台積電走勢 及台積電月線、台積電量能(爆量翻紅)
    st.subheader("4. 台積電價格與爆量偵測")
    fig3 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig3.add_trace(go.Scatter(x=data.index, y=data['TSMC'], name="台積電現貨", line=dict(color='red')), row=1, col=1)
    fig3.add_trace(go.Scatter(x=data.index, y=data['台積電_20MA'], name="月線(20MA)", line=dict(color='orange', dash='dot')), row=1, col=1)
    vol_colors = ['#ef4444' if v > 1.5 * m else '#555555' for v, m in zip(data['TSMC_Vol'], data['台積電量_10MA'])]
    fig3.add_trace(go.Bar(x=data.index, y=data['TSMC_Vol'], name="成交量 (紅柱為爆量)", marker_color=vol_colors), row=2, col=1)
    fig3.update_layout(height=450, margin=dict(t=10, b=10), hovermode="x unified")
    st.plotly_chart(fig3, use_container_width=True)

    colC, colD = st.columns(2)
    with colC:
        # 5. 外資買賣超 vs外資Z分數 (V11: 1.2 / -1.5)
        st.subheader("5. 外資買賣超與 Z-Score")
        if has_foreign:
            fig5 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.05)
            f_colors = ['#ef4444' if val > 0 else '#22c55e' for val in data['Foreign_Net']]
            fig5.add_trace(go.Bar(x=data.index, y=data['Foreign_Net'], name="外資淨買賣(億)", marker_color=f_colors), row=1, col=1)
            fig5.add_trace(go.Scatter(x=data.index, y=data['外資_Zscore'], name="外資 Z-score", line=dict(color='#3b82f6')), row=2, col=1)
            fig5.add_hline(y=1.2, line_dash="dot", line_color="red", row=2, col=1, annotation_text="多頭 (+1.2)")
            fig5.add_hline(y=-1.5, line_dash="dot", line_color="green", row=2, col=1, annotation_text="空頭 (-1.5)")
            fig5.update_layout(height=400, margin=dict(t=10, b=10), hovermode="x unified")
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.warning("⚠️ 無法獲取 FinMind 外資歷史資料。")

    with colD:
        # 6. 台積電ADR、台積電ADRZ分數 (V11: 0.8 / -1.2)
        st.subheader("6. 台積電 ADR 與 Z-Score")
        fig6 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.05)
        fig6.add_trace(go.Scatter(x=data.index, y=data['TSM_ADR'], name="台積電 ADR", line=dict(color='lightblue')), row=1, col=1)
        fig6.add_trace(go.Scatter(x=data.index, y=data['ADR_120MA'], name="半年線(120MA)", line=dict(color='gray', dash='dash')), row=1, col=1)
        fig6.add_trace(go.Scatter(x=data.index, y=data['ADR_Zscore'], name="ADR Z-score", line=dict(color='#eab308')), row=2, col=1)
        fig6.add_hline(y=0.8, line_dash="dot", line_color="red", row=2, col=1, annotation_text="多頭 (+0.8)")
        fig6.add_hline(y=-1.2, line_dash="dot", line_color="green", row=2, col=1, annotation_text="空頭 (-1.2)")
        fig6.update_layout(height=400, margin=dict(t=10, b=10), hovermode="x unified")
        st.plotly_chart(fig6, use_container_width=True)

    # 7. 新增圖表：台指與 RSI
    st.subheader("7. 台股大盤與 RSI 動能指標")
    fig7 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig7.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='silver')), row=1, col=1)
    fig7.add_trace(go.Scatter(x=data.index, y=data['台指_RSI14'], name="RSI (14)", line=dict(color='#8b5cf6')), row=2, col=1)
    fig7.add_hline(y=65, line_dash="dot", line_color="red", row=2, col=1, annotation_text="過熱區 (>65)")
    fig7.add_hline(y=40, line_dash="dot", line_color="green", row=2, col=1, annotation_text="低檔區 (<40)")
    fig7.update_layout(height=450, margin=dict(t=10, b=10), hovermode="x unified")
    st.plotly_chart(fig7, use_container_width=True)

    # 8. 新增圖表：台指與布林通道
    st.subheader("8. 台股大盤與 布林通道 (Bollinger Bands)")
    fig8 = go.Figure()
    fig8.add_trace(go.Scatter(x=data.index, y=data['TWII'], name="加權指數", line=dict(color='silver')))
    # 布林上軌
    fig8.add_trace(go.Scatter(x=data.index, y=data['BB_上軌'], name="BB 上軌", line=dict(color='rgba(239, 68, 68, 0.5)', dash='dot')))
    # 中線(20MA)
    fig8.add_trace(go.Scatter(x=data.index, y=data['台指_20MA'], name="月線 (20MA)", line=dict(color='rgba(255, 165, 0, 0.8)')))
    # 布林下軌，並使用 fill='tonexty' 畫出通道陰影
    fig8.add_trace(go.Scatter(x=data.index, y=data['BB_下軌'], name="BB 下軌", line=dict(color='rgba(34, 197, 94, 0.5)', dash='dot'), fill='tonexty', fillcolor='rgba(128, 128, 128, 0.1)'))
    fig8.update_layout(height=450, margin=dict(t=10, b=10), hovermode="x unified")
    st.plotly_chart(fig8, use_container_width=True)

if __name__ == "__main__":
    main()
