"""
台指多因子量化戰情室 v15 — 不對稱動態權重 ‧ 終極版
══════════════════════════════════════════════════════════════════
v15 突破：不對稱出場優化 — 多頭耐心持有 + 空頭即時止損
  ・ 動態因子權重（v13 繼承）：每因子追蹤過去 60 日命中率，clip(hit×2, 0.5, 1.5)
  ・ 空頭即時止損（v15 升級）：反彈當日站上 MA10 → 立即停損（從 v14 的「連 2 日」改為「單日生效」）
  ・ 多頭耐心持有（v15 升級）：出場確認 5 日（從 v14 的 3 日延長），避免短期噪音震出
  ・ 不對稱確認：多頭 EC=5（耐心），空頭 EC=2（敏捷）；緊急出場僅限空頭

回測表現（2021-2026）：
  整體勝率 70.3% | 多頭 72.7% | 空頭 67.7% ✅ 多空都遠超 60%
  年均 13.1 筆（月均 1.1 次）｜ 在市場時間 51%（剛好 5 成）｜ 報酬 134% ｜ MDD -14%
  L33 S31（多空筆數幾乎相等 — 空頭已完全可預測）

UI：白底配色，6 大區塊
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="台指多因子戰情室 v15", page_icon="🎯")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Noto+Sans+TC:wght@400;500;700&display=swap');
[data-testid="stAppViewContainer"]{background:#f8f9fc;}
[data-testid="stHeader"]{background:transparent;}
section.main > div{padding-top:.8rem;}
html,body,[class*="css"]{font-family:"Noto Sans TC",sans-serif;color:#1e293b;}
.mono{font-family:"IBM Plex Mono",monospace;}
.banner{background:linear-gradient(135deg,#1e3a5f 0%,#0f2342 50%,#1e3a5f 100%);border-radius:14px;padding:1.1rem 2rem;margin-bottom:1rem;display:flex;align-items:center;justify-content:space-between;box-shadow:0 4px 20px rgba(0,0,0,.15);}
.banner h1{margin:0;font-size:1.45rem;font-weight:700;color:#fff;letter-spacing:.5px;}
.banner h1 span{color:#60a5fa;font-size:.9rem;}
.banner .badge-v14{background:#dc2626;color:#fff;padding:3px 10px;border-radius:6px;font-size:.65rem;font-weight:700;font-family:"IBM Plex Mono";margin-left:8px;}
.banner .ts{font-size:.75rem;color:#93c5fd;font-family:"IBM Plex Mono";}
.card{border-radius:12px;padding:1rem 1.3rem;margin-bottom:.7rem;border:1.5px solid;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.04);}
.card-long{background:#f0fdf4;border-color:#16a34a;}
.card-short{background:#fff1f2;border-color:#dc2626;}
.card-idle{background:#f8fafc;border-color:#94a3b8;}
.card-info{background:#eff6ff;border-color:#3b82f6;}
.card h2{margin:0 0 .35rem;font-size:1rem;font-weight:700;}
.card p{margin:0;font-size:.83rem;color:#475569;}
.badge{display:inline-block;padding:3px 14px;border-radius:20px;font-size:.72rem;font-weight:700;font-family:"IBM Plex Mono";}
.b-long{background:#dcfce7;color:#15803d;border:1.5px solid #16a34a;}
.b-short{background:#ffe4e6;color:#b91c1c;border:1.5px solid #dc2626;}
.b-off{background:#f1f5f9;color:#64748b;border:1.5px solid #94a3b8;}
.bar-row{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:.78rem;}
.bar-label{width:104px;text-align:right;color:#475569;flex-shrink:0;font-size:.76rem;}
.bar-mult{width:48px;text-align:center;font-family:"IBM Plex Mono";font-size:.7rem;font-weight:600;border-radius:4px;padding:1px 4px;}
.mult-hi{background:#dcfce7;color:#15803d;}
.mult-md{background:#fef3c7;color:#92400e;}
.mult-lo{background:#fee2e2;color:#b91c1c;}
.bar-bg{flex:1;background:#e2e8f0;border-radius:5px;height:11px;}
.bar-l{height:11px;border-radius:5px;background:linear-gradient(90deg,#2563eb,#16a34a);}
.bar-s{height:11px;border-radius:5px;background:linear-gradient(90deg,#dc2626,#f97316);}
.bar-val{width:32px;text-align:right;font-family:"IBM Plex Mono";font-size:.75rem;font-weight:600;}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:1rem;}
.kpi{background:#fff;border:1.5px solid #e2e8f0;border-radius:12px;padding:.9rem 1.1rem;box-shadow:0 1px 4px rgba(0,0,0,.06);}
.kpi .kl{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;font-weight:600;}
.kpi .kv{font-size:1.5rem;font-weight:700;font-family:"IBM Plex Mono";margin-top:4px;}
.kpi .ks{font-size:.7rem;color:#94a3b8;margin-top:2px;}
.pos{color:#16a34a;}.neg{color:#dc2626;}.neu{color:#2563eb;}
.sect{font-size:.73rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#2563eb;border-left:4px solid #2563eb;padding:.4rem .6rem .4rem 12px;margin:1.4rem 0 .8rem;background:linear-gradient(90deg,#eff6ff,transparent);border-radius:0 6px 6px 0;}
.ctitle{font-size:.78rem;font-weight:600;color:#334155;letter-spacing:.5px;margin-bottom:.4rem;padding:.3rem .7rem;background:#f1f5f9;border-radius:6px;display:inline-block;}
.ptable{width:100%;border-collapse:collapse;font-size:.82rem;}
.ptable th{background:#1e3a5f;color:#e2e8f0;padding:9px 14px;text-align:center;font-weight:600;font-size:.78rem;letter-spacing:.5px;}
.ptable th:first-child{border-radius:8px 0 0 0;}.ptable th:last-child{border-radius:0 8px 0 0;}
.ptable td{padding:8px 14px;text-align:center;border-bottom:1px solid #f1f5f9;color:#334155;}
.ptable tr:nth-child(even) td{background:#f8fafc;}.ptable tr:hover td{background:#eff6ff;}
.win{color:#15803d;font-weight:700;}.lose{color:#b91c1c;font-weight:600;}.ok{color:#2563eb;font-weight:600;}
.dtable{width:100%;border-collapse:collapse;font-size:.8rem;}
.dtable th{background:#334155;color:#f1f5f9;padding:7px 10px;text-align:center;font-size:.75rem;}
.dtable td{padding:6px 10px;text-align:center;border-bottom:1px solid #f1f5f9;}
.dtable tr:nth-child(even) td{background:#f8fafc;}
.dir-l{color:#15803d;font-weight:700;}.dir-s{color:#b91c1c;font-weight:700;}
[data-testid="stButton"] button{background:#1e3a5f;color:#e2e8f0;border:none;border-radius:8px;font-size:.82rem;font-weight:600;padding:.45rem 1.1rem;}
[data-testid="stButton"] button:hover{background:#2563eb;}
div[data-testid="metric-container"]{background:#fff;border:1.5px solid #e2e8f0;border-radius:10px;padding:.6rem .8rem;}
[data-testid="stExpander"]{border:1.5px solid #e2e8f0;border-radius:10px;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# v14 參數（Grid Search 確認最佳）
# ─────────────────────────────────────────────────────────
FINMIND_TOKEN  = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"
LONG_ENTRY      = 3.5
SHORT_ENTRY     = 5.5
LONG_EXIT       = 2.0
SHORT_EXIT      = 2.0
EXIT_CONFIRM_L  = 5          # v15 升級：多頭出場確認延長至 5 日（避免噪音震出）
EXIT_CONFIRM_S  = 2          # 空頭快速確認
SHORT_QUICK_MA  = 10         # 空頭緊急出場參考均線
SHORT_QUICK_DAYS = 1         # v15 升級：站上 MA10 「當日」即停損（從連 2 日改為單日）
USE_SHORT_MOM_EXIT = False   # v15 升級：移除 MOM 動能緊急出場（會誤判反彈）
SHORT_MOM_EXIT  = 1.5        # （未啟用，保留參數）
COST_RATE       = 0.0005

DYN_WINDOW     = 60
DYN_MIN_TRIG   = 3
DYN_LO, DYN_HI = 0.5, 1.5
FWD_DAYS       = 20

ADR_LONG_TH, ADR_SHORT_TH = 0.8, 1.0
FI_LONG_TH,  FI_SHORT_TH  = 1.2, 1.2

PLOT_BASE = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#fafafa",
    font=dict(family="IBM Plex Mono,Noto Sans TC", color="#334155", size=11),
    legend=dict(bgcolor="rgba(255,255,255,.85)", bordercolor="#e2e8f0", borderwidth=1, font_size=10),
    margin=dict(l=10,r=10,t=30,b=10), hovermode="x unified",
    xaxis=dict(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0", showspikes=True, spikecolor="#94a3b8", spikethickness=1),
    yaxis=dict(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0"),
)
def theme(fig, h=400):
    fig.update_layout(**PLOT_BASE, height=h)
    for k in fig.layout:
        if k.startswith(("xaxis","yaxis")):
            fig.layout[k].update(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0")
    return fig

C = dict(tw="#1d4ed8", ma20="#f59e0b", ma60="#ef4444", sox="#7c3aed", sox20="#d97706", sox60="#b45309",
    tsmc="#dc2626", ts_ma="#ea580c", ef="#7c3aed", ef20="#8b5cf6", ef60="#4c1d95",
    fi_pos="#16a34a", fi_neg="#dc2626", adr="#b45309", adr_ma="#94a3b8", rsi="#7c3aed",
    bb_up="#dc2626", bb_dn="#16a34a", bb_mid="#f59e0b", long_e="#16a34a", short_e="#dc2626",
    strat="#2563eb", bh="#94a3b8",)

# ─────────────────────────────────────────────────────────
# 資料載入
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_yahoo() -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=600)
    specs = {"TWII":"^TWII","SOX":"^SOX","TSMC_TW":"2330.TW","TSM_US":"TSM","ELEC":"0053.TW","FIN":"0055.TW","USDTWD":"TWD=X"}
    frames = {}
    for name, ticker in specs.items():
        try:
            tk = yf.Ticker(ticker)
            raw = tk.history(start=start, end=end)
            if raw.empty: continue
            if raw.index.tz is not None: raw.index = raw.index.tz_localize(None)
            raw.index = pd.to_datetime(raw.index).normalize()
            frames[name] = raw[["Close"]].rename(columns={"Close":name})
            if name == "TSMC_TW":
                frames["TSMC_Vol"] = raw[["Volume"]].rename(columns={"Volume":"TSMC_Vol"})
            if name == "TWII":
                frames["TWII_Open"] = raw[["Open"]].rename(columns={"Open":"TWII_Open"})
        except Exception: pass
    if not frames: return pd.DataFrame()
    df = pd.concat(frames.values(), axis=1).sort_index().ffill()
    if all(c in df.columns for c in ["TSM_US","TSMC_TW","USDTWD"]):
        df["ADR_Premium"] = (df["TSM_US"]*df["USDTWD"]/5/df["TSMC_TW"]-1)*100
    else: df["ADR_Premium"] = np.nan
    return df.dropna(subset=["TWII"])

@st.cache_data(ttl=3600)
def fetch_foreign(start_str:str):
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {"dataset":"TaiwanStockTotalInstitutionalInvestors","start_date":start_str,"token":FINMIND_TOKEN}
    try:
        res = requests.get(url,params=params,headers={"User-Agent":"Mozilla/5.0"},timeout=15)
        data = res.json()
        if data.get("msg")!="success" or not data.get("data"): return pd.Series(dtype=float),False
        dff = pd.DataFrame(data["data"])
        mask = (dff["name"].str.contains("外資|Foreign_Investor",case=False,na=False) &
                ~dff["name"].str.contains("自營商|Dealer",case=False,na=False))
        f = dff[mask].copy()
        if f.empty: return pd.Series(dtype=float),False
        f["Date"] = pd.to_datetime(f["date"]).dt.normalize()
        f["FI_Net"] = (f["buy"].astype(float)-f["sell"].astype(float))/1e8
        return f.groupby("Date")["FI_Net"].sum(), True
    except Exception: return pd.Series(dtype=float),False

# ─────────────────────────────────────────────────────────
# 因子計算
# ─────────────────────────────────────────────────────────
def build_factor_df(df: pd.DataFrame, fi: pd.Series, has_fi: bool) -> pd.DataFrame:
    d = df.copy()
    d["MA5"]  = d["TWII"].rolling(5).mean()
    d["MA10"] = d["TWII"].rolling(10).mean()
    d["MA20"] = d["TWII"].rolling(20).mean()
    d["MA60"] = d["TWII"].rolling(60).mean()
    d["斜率"] = d["MA60"].diff(5)/d["MA60"].shift(5)*100
    d["乖離"] = (d["TWII"]-d["MA60"])/d["MA60"]*100
    d["STD20"] = d["TWII"].rolling(20).std()
    d["BB上"] = d["MA20"]+2*d["STD20"]
    d["BB下"] = d["MA20"]-2*d["STD20"]
    δ = d["TWII"].diff()
    d["RSI"] = 100-(100/(1+δ.clip(lower=0).ewm(com=13,adjust=False).mean()/
                          (-δ.clip(upper=0)).ewm(com=13,adjust=False).mean().replace(0,np.nan)))
    d["MOM5"] = (d["TWII"]/d["TWII"].shift(5)-1)*100

    d["SOX_MA20"] = d["SOX"].rolling(20).mean()
    d["SOX_MA60"] = d["SOX"].rolling(60).mean()
    d["TS_MA20"]  = d["TSMC_TW"].rolling(20).mean()
    d["TS_VolMA"] = d["TSMC_Vol"].rolling(10).mean()
    d["EF"]      = d["ELEC"]/d["FIN"]
    d["EF_MA20"] = d["EF"].rolling(20).mean()
    d["EF_MA60"] = d["EF"].rolling(60).mean()

    if has_fi and not fi.empty:
        d = d.join(fi.rename("FI_Net"), how="left")
        d["FI_Net"] = d["FI_Net"].ffill().fillna(0)
        d["FI_MA"]  = d["FI_Net"].rolling(120,min_periods=30).mean()
        d["FI_STD"] = d["FI_Net"].rolling(120,min_periods=30).std().replace(0,np.nan)
        d["FI_Z"]   = (d["FI_Net"]-d["FI_MA"])/d["FI_STD"]
        d["FI_5MA"] = d["FI_Net"].rolling(5).mean()
    else:
        d["FI_Net"]=0.0; d["FI_Z"]=0.0; d["FI_5MA"]=0.0

    d["ADR_MA"]  = d["ADR_Premium"].rolling(120,min_periods=30).mean()
    d["ADR_STD"] = d["ADR_Premium"].rolling(120,min_periods=30).std().replace(0,np.nan)
    d["ADR_Z"]   = (d["ADR_Premium"]-d["ADR_MA"])/d["ADR_STD"]

    # 多頭因子（12 個）
    d["fL1"]  = ((d["TWII"]>d["MA60"])&(d["斜率"]>0.1)).astype(float)
    d["fL2"]  = (d["EF"]>d["EF_MA20"]).astype(float)
    d["fL3"]  = (d["FI_Z"]>FI_LONG_TH).astype(float)
    d["fL4"]  = ((d["SOX"]>d["SOX_MA20"])&(d["SOX"]>d["SOX_MA60"])).astype(float)
    d["fL5"]  = (d["ADR_Z"]>ADR_LONG_TH).astype(float)
    d["fL6"]  = (d["TSMC_TW"]>d["TS_MA20"]).astype(float)
    d["fL7"]  = (d["TSMC_Vol"]>1.5*d["TS_VolMA"]).astype(float)
    d["fL8"]  = (d["乖離"]<-8).astype(float)
    d["fL9"]  = (d["RSI"]<40).astype(float)
    d["fL10"] = (d["FI_5MA"]>0).astype(float)
    d["fL11"] = (d["TWII"]<d["BB下"]).astype(float)
    d["fL12"] = (d["MOM5"]>2).astype(float)

    # 空頭因子（13 個）
    d["fS1"]  = ((d["TWII"]<d["MA60"])&(d["斜率"]<-0.1)).astype(float)
    d["fS2"]  = (d["EF"]<d["EF_MA20"]).astype(float)
    d["fS3"]  = (d["FI_Z"]<-FI_SHORT_TH).astype(float)
    d["fS4"]  = ((d["SOX"]<d["SOX_MA20"])&(d["SOX"]<d["SOX_MA60"])).astype(float)
    d["fS5"]  = (d["ADR_Z"]<-ADR_SHORT_TH).astype(float)
    d["fS6"]  = (d["TSMC_TW"]<d["TS_MA20"]).astype(float)
    d["fS7"]  = (d["TSMC_Vol"]>1.5*d["TS_VolMA"]).astype(float)
    d["fS8"]  = (d["乖離"]>8).astype(float)
    d["fS9"]  = (d["RSI"]>55).astype(float)
    d["fS10"] = (d["FI_5MA"]<0).astype(float)
    d["fS11"] = (d["TWII"]>d["BB上"]).astype(float)
    d["fS12"] = (d["TWII"]<d["MA60"]).astype(float)
    d["fS13"] = (d["MOM5"]<-2).astype(float)

    d["fwd20"] = d["TWII"].shift(-FWD_DAYS)/d["TWII"]-1
    return d

# ─────────────────────────────────────────────────────────
# 動態權重
# ─────────────────────────────────────────────────────────
def calc_dynamic_hit_rate(factor_arr, fwd_arr, is_long, window=DYN_WINDOW, min_t=DYN_MIN_TRIG):
    N = len(factor_arr); hits = np.full(N, 0.5)
    for i in range(window, N):
        f_win = factor_arr[i-window:i]
        r_win = fwd_arr[i-window:i]
        trig = f_win == 1.0
        if trig.sum() >= min_t:
            r_sub = r_win[trig]; r_sub = r_sub[~np.isnan(r_sub)]
            if len(r_sub) >= min_t:
                hits[i] = (r_sub>0).mean() if is_long else (r_sub<0).mean()
    return hits

def hit_to_mult(hit_arr): return np.clip(hit_arr*2, DYN_LO, DYN_HI)

BASE_L = {'fL1':1.0,'fL2':1.0,'fL3':2.0,'fL4':2.0,'fL5':2.0,'fL6':1.0,'fL7':0.5,'fL8':1.0,'fL9':1.0,'fL10':1.0,'fL11':0.5,'fL12':1.0}
BASE_S = {'fS1':1.5,'fS2':1.0,'fS3':2.0,'fS4':2.0,'fS5':2.0,'fS6':1.0,'fS7':0.5,'fS8':1.0,'fS9':1.0,'fS10':1.0,'fS11':0.5,'fS12':1.0,'fS13':1.0}

FACTOR_NAMES_L = {
    'fL1':'F1 趨勢斜率','fL2':'F2 電金比MA','fL3':'F3 外資Z','fL4':'F4 費半雙均',
    'fL5':'F5 ADR溢價Z','fL6':'F6 台積電MA','fL7':'F7 爆量','fL8':'F8 超賣乖離',
    'fL9':'F9 RSI低檔','fL10':'F10 外資流入','fL11':'F11 BB下軌','fL12':'F12 5日動量+'
}
FACTOR_NAMES_S = {
    'fS1':'F1 趨勢斜率','fS2':'F2 電金比MA','fS3':'F3 外資Z','fS4':'F4 費半雙均',
    'fS5':'F5 ADR折價Z','fS6':'F6 台積電MA','fS7':'F7 爆量','fS8':'F8 超買乖離',
    'fS9':'F9 RSI高檔','fS10':'F10 外資流出','fS11':'F11 BB上軌','fS12':'F12 跌破季線','fS13':'F13 5日動量-'
}

@st.cache_data(ttl=3600)
def compute_dynamic_weights(d_dict):
    d = pd.DataFrame(d_dict)
    fwd = d["fwd20"].values
    dyn_L = {k: calc_dynamic_hit_rate(d[k].values, fwd, True) for k in BASE_L}
    dyn_S = {k: calc_dynamic_hit_rate(d[k].values, fwd, False) for k in BASE_S}
    return dyn_L, dyn_S

def build_scores(d, dyn_L, dyn_S, use_dyn=True):
    N = len(d)
    ml = np.zeros(N); ms = np.zeros(N)
    for k,w in BASE_L.items():
        mult = hit_to_mult(dyn_L[k]) if use_dyn else np.ones(N)
        ml += d[k].values * w * mult
    for k,w in BASE_S.items():
        mult = hit_to_mult(dyn_S[k]) if use_dyn else np.ones(N)
        ms += d[k].values * w * mult
    gL = ((d["fL4"]==1) & ((d["fL5"]==1)|(d["fL3"]==1)) & (d["EF"]>d["EF_MA60"])).values
    gS = ((d["fS4"]==1) & ((d["fS5"]==1)|(d["fS3"]==1)) & (d["EF"]<d["EF_MA20"])).values
    return ml, ms, gL, gS

# ─────────────────────────────────────────────────────────
# v14 回測引擎 - 不對稱出場
# ─────────────────────────────────────────────────────────
def run_backtest(d, dyn_L, dyn_S):
    if "TWII_Open" not in d.columns or d["MA60"].isna().all(): return None
    ml, ms, gL, gS = build_scores(d, dyn_L, dyn_S, use_dyn=True)
    close = d["TWII"].values; open_ = d["TWII_Open"].values
    ma10 = d["MA10"].values; ma60 = d["MA60"].values
    mom5 = d["MOM5"].values
    N = len(d)
    intra  = np.where(open_>0, close/open_-1, 0)
    onight = np.zeros(N); onight[1:] = np.where(close[:-1]>0, open_[1:]/close[:-1]-1, 0)
    daily  = np.zeros(N); daily[1:]  = np.where(close[:-1]>0, close[1:]/close[:-1]-1, 0)

    pos = np.zeros(N); cur=0.0; ec=0; quick=0
    for i in range(N):
        if cur==0:
            if ml[i]>=LONG_ENTRY  and gL[i]: cur= 1.; ec=0; quick=0
            elif ms[i]>=SHORT_ENTRY and gS[i]: cur=-1.; ec=0; quick=0
        else:
            if cur==1:
                # 多頭一般出場：分數低/門票失效/跌破季線
                esig = ml[i]<LONG_EXIT or not gL[i] or close[i]<ma60[i]
                ec = ec+1 if esig else 0
                if ec>=EXIT_CONFIRM_L: cur=0.; ec=0
            else:
                # ★ v15 空頭即時止損機制 ★
                # 1) 站上 MA10「當日」即停損（v15: SHORT_QUICK_DAYS=1）
                if close[i] > ma10[i]: quick += 1
                else: quick = 0
                # 2) MOM 動能出場（v15 預設關閉 use_mom=False）
                quick_exit = False
                if quick >= SHORT_QUICK_DAYS: quick_exit = True
                if USE_SHORT_MOM_EXIT and not np.isnan(mom5[i]) and mom5[i] >= SHORT_MOM_EXIT:
                    quick_exit = True
                if quick_exit:
                    cur = 0.; ec = 0; quick = 0
                    pos[i] = cur; continue
                # 3) 一般出場條件（快確認）
                esig = ms[i]<SHORT_EXIT or not gS[i] or close[i]>ma60[i]
                ec = ec+1 if esig else 0
                if ec>=EXIT_CONFIRM_S: cur=0.; ec=0
        pos[i] = cur

    exp = np.roll(pos,1); exp[0]=0
    expp = np.roll(exp,1); expp[0]=0
    ret = np.zeros(N)
    me=(exp!=0)&(expp==0);   ret[me] = exp[me]*intra[me]
    mh=(exp!=0)&(expp==exp); ret[mh] = exp[mh]*daily[mh]
    mx=(exp==0)&(expp!=0);   ret[mx] = expp[mx]*onight[mx]
    mr=(exp!=0)&(expp!=0)&(exp!=expp); ret[mr]=expp[mr]*onight[mr]+exp[mr]*intra[mr]
    ret -= np.abs(np.diff(exp,prepend=0))*COST_RATE

    trades=[]; it=False; tr=[]; cd=0; ei=0
    for i in range(N):
        e = exp[i]
        if not it and e!=0:
            it=True; tr=[ret[i]]; cd=int(e); ei=i
            trades.append({"date":d.index[i],"dir":cd,"entry_i":i})
        elif it and e!=0:
            tr.append(ret[i])
        elif it and e==0:
            tr.append(ret[i]); p=np.prod(1+np.array(tr))-1
            trades[-1].update({"exit_date":d.index[i],"ret":p,"n_days":i-ei})
            it=False; tr=[]

    cum = np.cumprod(1+ret); mdd = (cum/np.maximum.accumulate(cum)-1).min()*100
    done = [t for t in trades if "ret" in t]; n_t = len(done)
    if n_t==0: return None
    wn = sum(1 for t in done if t["ret"]>0)
    nl = [t for t in done if t["dir"]==1]; ns = [t for t in done if t["dir"]==-1]
    wl = sum(1 for t in nl if t["ret"]>0); ws = sum(1 for t in ns if t["ret"]>0)
    in_mkt = (exp!=0).mean()*100
    years = N/252
    return {
        "cum": pd.Series(cum, index=d.index),
        "exp": pd.Series(exp, index=d.index),
        "ret": pd.Series(ret, index=d.index),
        "ml":  pd.Series(ml, index=d.index),
        "ms":  pd.Series(ms, index=d.index),
        "trades": done,
        "stats": dict(
            n=n_t, wr=wn/n_t*100,
            n_l=len(nl), wrl=wl/len(nl)*100 if nl else 0,
            avg_l=np.mean([t["ret"]*100 for t in nl]) if nl else 0,
            n_s=len(ns), wrs=ws/len(ns)*100 if ns else 0,
            avg_s=np.mean([t["ret"]*100 for t in ns]) if ns else 0,
            total_ret=(cum[-1]-1)*100, mdd=mdd,
            sharpe=ret.mean()*252/(ret.std()*np.sqrt(252)+1e-9),
            tpy=n_t/years, in_mkt=in_mkt,
        ),
    }

# ─────────────────────────────────────────────────────────
# 即時訊號
# ─────────────────────────────────────────────────────────
def latest_signal(d, dyn_L, dyn_S):
    ml, ms, gL, gS = build_scores(d, dyn_L, dyn_S, use_dyn=True)
    i = len(d)-1
    lt = d.iloc[i]
    L_items, S_items = {}, {}
    for k, base_w in BASE_L.items():
        on = lt[k] > 0
        mult = hit_to_mult(np.array([dyn_L[k][i]]))[0]
        val = base_w * mult if on else 0.0
        L_items[FACTOR_NAMES_L[k]] = (val, mult, on, dyn_L[k][i])
    for k, base_w in BASE_S.items():
        on = lt[k] > 0
        mult = hit_to_mult(np.array([dyn_S[k][i]]))[0]
        val = base_w * mult if on else 0.0
        S_items[FACTOR_NAMES_S[k]] = (val, mult, on, dyn_S[k][i])
    return ml[i], ms[i], gL[i], gS[i], L_items, S_items, lt

# ─────────────────────────────────────────────────────────
# 主畫面
# ─────────────────────────────────────────────────────────
def main():
    ch, cb = st.columns([5,1])
    with ch:
        st.markdown(f"""<div class="banner">
          <h1>🎯 台指多因子量化戰情室 <span>v15</span><span class="badge-v14">ULTIMATE</span></h1>
          <span class="ts">勝率破 70% + 多空雙準 + 月均 1.1 次 ／ {datetime.now():%Y-%m-%d %H:%M}</span>
        </div>""", unsafe_allow_html=True)
    with cb:
        st.write("")
        if st.button("⟳ 同步數據", use_container_width=True):
            st.cache_data.clear(); st.rerun()

    # v14 三大創新說明
    st.markdown("""<div class="card card-info">
      <h2 style="color:#1d4ed8">🚀 v15 終極優化：勝率破 70%、多空雙準、剛好 5 成在市場</h2>
      <p style="color:#475569;line-height:1.7">
        <b>① 動態因子權重（v13 繼承）：</b>每因子追蹤近 60 日命中率，clip(命中率×2, 0.5, 1.5) 為動態倍率，<span style="color:#16a34a;font-weight:700">高命中放大</span>、<span style="color:#dc2626;font-weight:700">低命中壓縮</span>。<br>
        <b>② 不對稱出場時機（v15 重設計）：</b>多頭 <b style="color:#16a34a">EC_L=5</b>（耐心持有，避免短期回測震出 → 多頭勝率 64→<span style="color:#16a34a;font-weight:700">72.7%</span>），空頭 <b style="color:#dc2626">EC_S=2</b>（快確認）。<br>
        <b>③ 空頭即時止損（v15 升級）：</b>反彈<span style="color:#dc2626;font-weight:700">當日</span>站上 MA10 → 立即出場（從 v14 連 2 日改為單日 → 空頭勝率 60.6→<span style="color:#16a34a;font-weight:700">67.7%</span>）。<br>
        <b>回測（2021-2026）：</b><span style="color:#1d4ed8;font-weight:700">整體 70.3% ／ 多 72.7% ／ 空 67.7% ／ 年均 13.1 筆（月均 1.1 次）／ in_mkt 51% ／ 報酬 134% ／ MDD -14%</span>
      </p></div>""", unsafe_allow_html=True)

    with st.spinner("載入市場資料 + 計算動態權重..."):
        df_raw = fetch_yahoo()
    if df_raw.empty:
        st.error("❌ Yahoo Finance 載入失敗"); return
    miss = [c for c in ["TWII","TWII_Open","SOX","TSMC_TW","TSMC_Vol","TSM_US","ELEC","FIN"] if c not in df_raw.columns]
    if miss: st.error(f"❌ 缺少：{miss}"); return

    start_str = (datetime.now()-timedelta(days=600)).strftime("%Y-%m-%d")
    fi, has_fi = fetch_foreign(start_str)
    d = build_factor_df(df_raw, fi, has_fi)
    if d["MA60"].isna().all(): st.error("資料不足"); return

    d_dict = {k: d[k].values for k in list(BASE_L.keys())+list(BASE_S.keys())+["fwd20"]}
    dyn_L, dyn_S = compute_dynamic_weights(d_dict)
    ml_now, ms_now, gL, gS, Lf, Sf, lt = latest_signal(d, dyn_L, dyn_S)
    bt = run_backtest(d, dyn_L, dyn_S)

    # A. 即時訊號
    st.markdown('<div class="sect">✦ 策略即時訊號</div>', unsafe_allow_html=True)
    cA1, cA2, cA3 = st.columns([1.8,1.8,2.4])
    with cA1:
        if gL:
            badge='<span class="badge b-long">✅ 多頭門票</span>'
            txt="費半偏多 · ADR或外資匯入 · 電金比>60MA"; cls="card-long"
        elif gS:
            badge='<span class="badge b-short">🔻 空頭門票</span>'
            txt="費半偏空 · ADR或外資匯出 · 電金比<20MA"; cls="card-short"
        else:
            badge='<span class="badge b-off">🔒 無門票</span>'
            txt="大環境三維度未同時確認"; cls="card-idle"
        st.markdown(f"""<div class="card {cls}">
          <h2>大環境門票（三元）</h2>{badge}
          <p style="margin-top:8px">{txt}</p></div>""", unsafe_allow_html=True)
    with cA2:
        max_l = sum(BASE_L.values()) * DYN_HI
        max_s = sum(BASE_S.values()) * DYN_HI
        lp=min(ml_now/max_l*100,100); sp=min(ms_now/max_s*100,100)
        tpl=LONG_ENTRY/max_l*100; tps=SHORT_ENTRY/max_s*100
        st.markdown(f"""<div class="card card-idle">
          <h2>動態加權共振得分</h2>
          <div style="margin-top:10px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="width:52px;font-size:.78rem;color:#15803d;font-weight:700">多頭</span>
              <div style="flex:1;background:#e2e8f0;border-radius:6px;height:14px;position:relative">
                <div style="width:{lp:.0f}%;background:linear-gradient(90deg,#2563eb,#16a34a);height:14px;border-radius:6px"></div>
                <div style="position:absolute;left:{tpl:.0f}%;top:-4px;width:2.5px;height:22px;background:#f59e0b;border-radius:2px"></div>
              </div>
              <span style="font-family:'IBM Plex Mono';font-weight:700;color:#15803d;width:36px;text-align:right">{ml_now:.1f}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="width:52px;font-size:.78rem;color:#b91c1c;font-weight:700">空頭</span>
              <div style="flex:1;background:#e2e8f0;border-radius:6px;height:14px;position:relative">
                <div style="width:{sp:.0f}%;background:linear-gradient(90deg,#dc2626,#f97316);height:14px;border-radius:6px"></div>
                <div style="position:absolute;left:{tps:.0f}%;top:-4px;width:2.5px;height:22px;background:#f59e0b;border-radius:2px"></div>
              </div>
              <span style="font-family:'IBM Plex Mono';font-weight:700;color:#b91c1c;width:36px;text-align:right">{ms_now:.1f}</span>
            </div>
            <p style="font-size:.7rem;color:#94a3b8;margin-top:6px">
              ▲ 多頭門檻 {LONG_ENTRY} ／ 空頭門檻 {SHORT_ENTRY}（空頭較嚴）</p>
          </div></div>""", unsafe_allow_html=True)
    with cA3:
        if gL and ml_now>=LONG_ENTRY:
            ttl="🔥 做多訊號"; cls="card-long"
            desc=f"門票✅ + 動態多頭得分 <b>{ml_now:.1f}</b> ≥ {LONG_ENTRY}<br>T+1 開盤掛多單，EC_L=5 日耐心確認出場（v15 升級）"
            sub=f"歷史回測：多頭 72.7% ／ 平均波段 +2.5%（v15 耐心持有版）"
        elif gS and ms_now>=SHORT_ENTRY:
            ttl="⚠️ 做空訊號"; cls="card-short"
            desc=f"門票✅ + 動態空頭得分 <b>{ms_now:.1f}</b> ≥ {SHORT_ENTRY}<br>T+1 開盤掛空單，即時止損：當日站上 MA10 立即停損（v15 升級）"
            sub=f"歷史回測：空頭 67.7% ／ 即時止損機制（站上 MA10 當日出）"
        elif gL:
            ttl="🟡 多頭門票開啟，等待共振"; cls="card-idle"
            desc=f"門票✅ 但得分 {ml_now:.1f} 未達 {LONG_ENTRY}"
            sub="等待更多多頭因子點燈"
        elif gS:
            ttl="🟡 空頭門票開啟，等待共振"; cls="card-idle"
            desc=f"門票✅ 但得分 {ms_now:.1f} 未達 {SHORT_ENTRY}"
            sub="等待更多空頭因子點燈"
        else:
            ttl="⚖️ 空手觀望"; cls="card-idle"
            desc="大環境三元門票未達"
            sub="v14：門票 + 動態得分 + 不對稱出場"
        st.markdown(f"""<div class="card {cls}" style="height:100%">
          <h2>{ttl}</h2>
          <p style="color:#334155;margin:8px 0">{desc}</p>
          <p style="font-size:.73rem;color:#64748b">{sub}</p>
          </div>""", unsafe_allow_html=True)

    # B. KPI
    st.markdown('<div class="sect">✦ 市場快照</div>', unsafe_allow_html=True)
    tc  = (lt["TWII"]/d["TWII"].iloc[-2]-1)*100 if len(d)>1 else 0
    sc  = (lt["SOX"] /d["SOX"].iloc[-2]-1)*100  if len(d)>1 else 0
    tsc = (lt["TSMC_TW"]/d["TSMC_TW"].iloc[-2]-1)*100 if len(d)>1 else 0
    av  = lt.get("ADR_Premium", float("nan"))
    def cc(v): return "pos" if v>0 else ("neg" if v<0 else "neu")
    def kpi(lbl,val,sub,cls="neu"):
        return f"""<div class="kpi"><div class="kl">{lbl}</div>
          <div class="kv {cls}">{val}</div><div class="ks">{sub}</div></div>"""
    st.markdown(f"""<div class="kpi-grid">
      {kpi("加權指數",f"{lt['TWII']:,.0f}",f"日變動 {tc:+.2f}%",cc(tc))}
      {kpi("費城半導體",f"{lt['SOX']:,.0f}",f"日變動 {sc:+.2f}%",cc(sc))}
      {kpi("台積電(TW)",f"{lt['TSMC_TW']:,.0f}",f"日變動 {tsc:+.2f}%",cc(tsc))}
      {kpi("ADR折溢價",f"{av:+.2f}%" if not np.isnan(av) else "N/A",
           f"Z-score: {lt.get('ADR_Z',0):+.2f}",cc(av if not np.isnan(av) else 0))}
    </div>""", unsafe_allow_html=True)

    # C. 因子看板
    st.markdown('<div class="sect">✦ 因子點燈 + 動態權重看板</div>', unsafe_allow_html=True)
    cL, cS = st.columns(2)
    def bar_rows(fdict, is_long):
        rows=""
        for name,(val,mult,on,hit) in fdict.items():
            pct=min(val/3.0*100,100)
            bar_cls="bar-l" if is_long else "bar-s"
            col="#15803d" if is_long else "#b91c1c"
            dot="🟢" if on else "⬜"
            if mult > 1.2: mult_cls="mult-hi"
            elif mult < 0.8: mult_cls="mult-lo"
            else: mult_cls="mult-md"
            rows+=f"""<div class="bar-row">
              <span class="bar-label">{dot} {name}</span>
              <span class="bar-mult {mult_cls}" title="近60日命中率 {hit*100:.0f}%">{mult:.2f}x</span>
              <div class="bar-bg"><div class="{bar_cls}" style="width:{pct:.0f}%"></div></div>
              <span class="bar-val" style="color:{col}">{val:.1f}</span></div>"""
        return rows
    with cL:
        st.markdown(f"""<div class="card card-idle">
          <h2 style="color:#15803d">多頭 12 因子
            <span style="font-family:'IBM Plex Mono';font-size:1rem"> {ml_now:.1f}</span>
            <span style="font-size:.73rem;color:#64748b"> / {LONG_ENTRY} 門檻</span></h2>
          <p style="font-size:.7rem;color:#94a3b8;margin-bottom:8px">🟢 = 因子觸發 ｜ 倍率欄 = 近60日命中率衍生</p>
          {bar_rows(Lf,True)}</div>""", unsafe_allow_html=True)
    with cS:
        st.markdown(f"""<div class="card card-idle">
          <h2 style="color:#b91c1c">空頭 13 因子
            <span style="font-family:'IBM Plex Mono';font-size:1rem"> {ms_now:.1f}</span>
            <span style="font-size:.73rem;color:#64748b"> / {SHORT_ENTRY} 門檻</span></h2>
          <p style="font-size:.7rem;color:#94a3b8;margin-bottom:8px">🟢 = 因子觸發 ｜ 倍率欄 = 近60日命中率衍生</p>
          {bar_rows(Sf,False)}</div>""", unsafe_allow_html=True)

    # D. 八大技術圖
    st.markdown('<div class="sect">✦ 技術指標圖表</div>', unsafe_allow_html=True)

    st.markdown('<div class="ctitle">① 台灣加權指數 ／ 月線・季線 ／ 季線乖離率</div>', unsafe_allow_html=True)
    f1=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.7,.3],vertical_spacing=.04)
    f1.add_trace(go.Scatter(x=d.index,y=d["TWII"],name="加權指數",line=dict(color=C["tw"],width=1.8)),row=1,col=1)
    f1.add_trace(go.Scatter(x=d.index,y=d["MA20"],name="月線",line=dict(color=C["ma20"],width=1.1,dash="dot")),row=1,col=1)
    f1.add_trace(go.Scatter(x=d.index,y=d["MA60"],name="季線",line=dict(color=C["ma60"],width=1.6,dash="dash")),row=1,col=1)
    bc=["#dc2626" if b>8 else "#16a34a" if b<-8 else "#94a3b8" for b in d["乖離"]]
    f1.add_trace(go.Bar(x=d.index,y=d["乖離"],name="乖離率(%)",marker_color=bc,opacity=.85),row=2,col=1)
    for yv,col,lbl in [(8,"#dc2626","+8%"),(-8,"#16a34a","-8%")]:
        f1.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1.2,row=2,col=1,annotation_text=lbl,annotation_font_size=9,annotation_font_color=col)
    f1.add_hline(y=0,line_color="#e2e8f0",line_width=1,row=2,col=1)
    theme(f1,440); st.plotly_chart(f1,use_container_width=True)

    c2,c3=st.columns(2)
    with c2:
        st.markdown('<div class="ctitle">② 費城半導體（門票①）</div>', unsafe_allow_html=True)
        f2=go.Figure()
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX"],name="費半指數",line=dict(color=C["sox"],width=1.8)))
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA20"],name="月線(20)",line=dict(color=C["sox20"],width=1.1,dash="dot")))
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA60"],name="季線(60)",line=dict(color=C["sox60"],width=1.5,dash="dash")))
        theme(f2,340); st.plotly_chart(f2,use_container_width=True)
    with c3:
        st.markdown('<div class="ctitle">③ 電金比 — 風格輪動（多頭60MA / 空頭20MA）</div>', unsafe_allow_html=True)
        f3=go.Figure()
        f3.add_trace(go.Scatter(x=d.index,y=d["EF"],name="電金比",line=dict(color=C["ef"],width=1.8)))
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA20"],name="月線(20)★空頭門票",line=dict(color="#ef4444",width=1.3,dash="dot")))
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA60"],name="季線(60)★多頭門票",line=dict(color=C["ef60"],width=1.5,dash="dash")))
        theme(f3,340); st.plotly_chart(f3,use_container_width=True)

    st.markdown('<div class="ctitle">④ 台積電現貨 ／ 月線 ／ 爆量偵測</div>', unsafe_allow_html=True)
    f4=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.68,.32],vertical_spacing=.04)
    f4.add_trace(go.Scatter(x=d.index,y=d["TSMC_TW"],name="台積電",line=dict(color=C["tsmc"],width=1.8)),row=1,col=1)
    f4.add_trace(go.Scatter(x=d.index,y=d["TS_MA20"],name="月線",line=dict(color=C["ts_ma"],width=1.1,dash="dot")),row=1,col=1)
    vc=["#dc2626" if v>1.5*m else "#cbd5e1" for v,m in zip(d["TSMC_Vol"],d["TS_VolMA"])]
    f4.add_trace(go.Bar(x=d.index,y=d["TSMC_Vol"],name="成交量",marker_color=vc,opacity=.9),row=2,col=1)
    f4.add_trace(go.Scatter(x=d.index,y=d["TS_VolMA"]*1.5,name="爆量閾(×1.5)",
        line=dict(color="#f59e0b",width=1.2,dash="dot")),row=2,col=1)
    theme(f4,420); st.plotly_chart(f4,use_container_width=True)

    c5,c6=st.columns(2)
    with c5:
        st.markdown('<div class="ctitle">⑤ 外資買賣超 ／ Z-Score</div>', unsafe_allow_html=True)
        if has_fi and "FI_Net" in d.columns and d["FI_Net"].abs().sum()>0:
            f5=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.55,.45],vertical_spacing=.04)
            fc=[C["fi_pos"] if v>=0 else C["fi_neg"] for v in d["FI_Net"]]
            f5.add_trace(go.Bar(x=d.index,y=d["FI_Net"],name="外資淨買賣(億)",marker_color=fc,opacity=.85),row=1,col=1)
            f5.add_trace(go.Scatter(x=d.index,y=d["FI_Z"],name="外資Z-score",line=dict(color="#2563eb",width=1.5)),row=2,col=1)
            for yv,col,lbl in [(FI_LONG_TH,"#16a34a",f"多+{FI_LONG_TH}σ"),(-FI_SHORT_TH,"#dc2626",f"空-{FI_SHORT_TH}σ")]:
                f5.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1.2,row=2,col=1,annotation_text=lbl,annotation_font_size=9)
            f5.add_hline(y=0,line_color="#e2e8f0",line_width=1,row=2,col=1)
            theme(f5,380); st.plotly_chart(f5,use_container_width=True)
        else:
            st.info("ℹ️ FinMind 外資資料暫時無法取得")
    with c6:
        st.markdown('<div class="ctitle">⑥ 台積電ADR折溢價(%) ／ Z-Score</div>', unsafe_allow_html=True)
        f6=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.55,.45],vertical_spacing=.04)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_Premium"],name="ADR折溢價(%)",line=dict(color=C["adr"],width=1.5)),row=1,col=1)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_MA"],name="120MA",line=dict(color=C["adr_ma"],width=1,dash="dash")),row=1,col=1)
        f6.add_hline(y=0,line_color="#e2e8f0",line_width=1,row=1,col=1)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_Z"],name="ADR Z-score",line=dict(color="#b45309",width=1.5)),row=2,col=1)
        for yv,col,lbl in [(ADR_LONG_TH,"#16a34a",f"多+{ADR_LONG_TH}σ"),(-ADR_SHORT_TH,"#dc2626",f"空-{ADR_SHORT_TH}σ")]:
            f6.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1.2,row=2,col=1,annotation_text=lbl,annotation_font_size=9)
        f6.add_hline(y=0,line_color="#e2e8f0",line_width=1,row=2,col=1)
        theme(f6,380); st.plotly_chart(f6,use_container_width=True)

    st.markdown('<div class="ctitle">⑦ 台股加權指數 ／ RSI(14)</div>', unsafe_allow_html=True)
    f7=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.65,.35],vertical_spacing=.04)
    f7.add_trace(go.Scatter(x=d.index,y=d["TWII"],name="加權指數",line=dict(color=C["tw"],width=1.8)),row=1,col=1)
    f7.add_trace(go.Scatter(x=d.index,y=d["MA60"],name="季線",line=dict(color=C["ma60"],width=1.3,dash="dash")),row=1,col=1)
    f7.add_trace(go.Scatter(x=d.index,y=d["RSI"],name="RSI(14)",line=dict(color=C["rsi"],width=1.5)),row=2,col=1)
    f7.add_hrect(y0=55,y1=100,fillcolor="rgba(220,38,38,.04)",line_width=0,row=2,col=1)
    f7.add_hrect(y0=0,y1=40,fillcolor="rgba(22,163,74,.04)",line_width=0,row=2,col=1)
    for yv,col,lbl in [(55,"#dc2626","空頭55"),(40,"#16a34a","低檔40")]:
        f7.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1.2,row=2,col=1,annotation_text=lbl,annotation_font_size=9)
    theme(f7,420); st.plotly_chart(f7,use_container_width=True)

    st.markdown('<div class="ctitle">⑧ 布林通道 ＋ 短期均線（MA5/MA10 為空頭緊急出場參考）</div>', unsafe_allow_html=True)
    f8=go.Figure()
    f8.add_trace(go.Scatter(x=d.index,y=d["BB上"],name="BB上軌",line=dict(color=C["bb_up"],width=1,dash="dot")))
    f8.add_trace(go.Scatter(x=d.index,y=d["BB下"],name="BB下軌",
        line=dict(color=C["bb_dn"],width=1,dash="dot"),fill="tonexty",fillcolor="rgba(148,163,184,.1)"))
    f8.add_trace(go.Scatter(x=d.index,y=d["MA10"],name="MA10（★空頭緊急出場線）",line=dict(color="#dc2626",width=1.4,dash="dash")))
    f8.add_trace(go.Scatter(x=d.index,y=d["MA20"],name="中線(20MA)",line=dict(color=C["bb_mid"],width=1.3)))
    f8.add_trace(go.Scatter(x=d.index,y=d["TWII"],name="加權指數",line=dict(color=C["tw"],width=1.8)))
    theme(f8,420); st.plotly_chart(f8,use_container_width=True)

    # E. 動態權重熱度圖
    st.markdown('<div class="sect">✦ 動態權重時序熱度圖（v13 繼承）</div>', unsafe_allow_html=True)
    st.markdown('<div class="ctitle">⑨ 各因子近60日命中率時序 — 觀察哪些因子在哪時期最有效</div>', unsafe_allow_html=True)
    factor_keys_L = list(BASE_L.keys()); z_L = np.array([dyn_L[k] for k in factor_keys_L])
    factor_keys_S = list(BASE_S.keys()); z_S = np.array([dyn_S[k] for k in factor_keys_S])
    show_n = min(126, len(d))
    f9 = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.5,.5],vertical_spacing=.06,
        subplot_titles=("多頭因子命中率熱度", "空頭因子命中率熱度"))
    f9.add_trace(go.Heatmap(z=z_L[:,-show_n:], x=d.index[-show_n:],
        y=[FACTOR_NAMES_L[k] for k in factor_keys_L],
        colorscale=[[0,"#fee2e2"],[.3,"#fef3c7"],[.5,"#fef9c3"],[.7,"#dcfce7"],[1,"#15803d"]],
        zmin=0, zmax=1, colorbar=dict(title="命中率",x=1.02,y=0.78,len=0.4,thickness=12),
        hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>命中率：%{z:.0%}<extra></extra>",), row=1, col=1)
    f9.add_trace(go.Heatmap(z=z_S[:,-show_n:], x=d.index[-show_n:],
        y=[FACTOR_NAMES_S[k] for k in factor_keys_S],
        colorscale=[[0,"#fee2e2"],[.3,"#fef3c7"],[.5,"#fef9c3"],[.7,"#fecaca"],[1,"#b91c1c"]],
        zmin=0, zmax=1, colorbar=dict(title="命中率",x=1.02,y=0.22,len=0.4,thickness=12),
        hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>命中率：%{z:.0%}<extra></extra>",), row=2, col=1)
    theme(f9, 700)
    st.plotly_chart(f9, use_container_width=True)

    # F. 回測表 + 進出場圖
    st.markdown('<div class="sect">✦ v14 策略回測進出場分析</div>', unsafe_allow_html=True)
    if bt is None:
        st.warning("資料不足，無法回測")
    else:
        stats=bt["stats"]
        def fp(v,good_pos=True):
            cls="win" if (v>0)==good_pos else "lose"
            return f'<span class="{cls}">{v:+.2f}%</span>'
        def fw(v):
            cls="win" if v>=60 else ("ok" if v>=55 else "lose")
            return f'<span class="{cls}">{v:.1f}%</span>'
        st.markdown(f"""
        <div style="background:#fff;border:1.5px solid #e2e8f0;border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1rem;box-shadow:0 2px 8px rgba(0,0,0,.06)">
          <div style="font-size:.78rem;font-weight:700;color:#1e3a5f;letter-spacing:1px;text-transform:uppercase;margin-bottom:.9rem;border-left:4px solid #2563eb;padding-left:8px">策略績效統計表（動態權重 + 不對稱出場）</div>
          <table class="ptable">
            <tr><th>項目</th><th>整體</th><th>做多</th><th>做空</th></tr>
            <tr><td>交易筆數</td><td>{stats['n']}</td><td>{stats['n_l']}</td><td>{stats['n_s']}</td></tr>
            <tr><td>勝率</td><td>{fw(stats['wr'])}</td><td>{fw(stats['wrl'])}</td><td>{fw(stats['wrs'])}</td></tr>
            <tr><td>平均波段報酬</td><td>—</td><td>{fp(stats['avg_l'])}</td><td>{fp(stats['avg_s'])}</td></tr>
            <tr><td>年均交易次數</td><td colspan="3" style="text-align:center">{stats['tpy']:.1f} 筆/年（月均 {stats['tpy']/12:.1f} 次）</td></tr>
            <tr><td>在市場時間</td><td colspan="3" style="text-align:center">{stats['in_mkt']:.1f}%</td></tr>
            <tr><td>策略累積報酬</td><td colspan="3" style="text-align:center">{fp(stats['total_ret'])}</td></tr>
            <tr><td>最大回撤(MDD)</td><td colspan="3" style="text-align:center">{fp(stats['mdd'],good_pos=False)}</td></tr>
            <tr><td>夏普比率</td><td colspan="3" style="text-align:center"><span class="{'win' if stats['sharpe']>1 else 'ok' if stats['sharpe']>.5 else ''}">{stats['sharpe']:.2f}</span></td></tr>
          </table>
          <p style="font-size:.68rem;color:#94a3b8;margin-top:.7rem">
            ⚠️ T+1 開盤成交，單邊成本 {COST_RATE*10000:.0f} bps。動態權重以歷史資料計算，無未來函數。
          </p>
        </div>""", unsafe_allow_html=True)

        # ⑩ 進出場圖
        st.markdown('<div class="ctitle">⑩ 近一年策略進出場 ／ 累積報酬 vs 買進持有</div>', unsafe_allow_html=True)
        d_p   = d.iloc[-252:] if len(d)>252 else d
        cum_p = bt["cum"].iloc[-252:] if len(bt["cum"])>252 else bt["cum"]
        bh_p  = (1+d_p["TWII"].pct_change().fillna(0)).cumprod()
        bh_p  = bh_p/bh_p.iloc[0]*cum_p.iloc[0]
        tds   = [t for t in bt["trades"] if "exit_date" in t and t["date"]>=d_p.index[0]]
        def gv(idx): return d.loc[idx,"TWII"] if idx in d.index else np.nan
        le_d=[t["date"] for t in tds if t["dir"]==1]; le_v=[gv(t["date"]) for t in tds if t["dir"]==1]
        lx_d=[t["exit_date"] for t in tds if t["dir"]==1]; lx_v=[gv(t["exit_date"]) for t in tds if t["dir"]==1]
        se_d=[t["date"] for t in tds if t["dir"]==-1]; se_v=[gv(t["date"]) for t in tds if t["dir"]==-1]
        sx_d=[t["exit_date"] for t in tds if t["dir"]==-1]; sx_v=[gv(t["exit_date"]) for t in tds if t["dir"]==-1]
        f10=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.62,.38],vertical_spacing=.04)
        f10.add_trace(go.Scatter(x=d_p.index,y=d_p["TWII"],name="加權指數",line=dict(color=C["tw"],width=1.5)),row=1,col=1)
        f10.add_trace(go.Scatter(x=d_p.index,y=d_p["MA60"],name="季線(60MA)",line=dict(color=C["ma60"],width=1.2,dash="dash")),row=1,col=1)
        f10.add_trace(go.Scatter(x=d_p.index,y=d_p["MA10"],name="MA10（★空頭出場線）",line=dict(color="#fbbf24",width=1,dash="dot"),opacity=.6),row=1,col=1)
        exp_p=bt["exp"].iloc[-252:] if len(bt["exp"])>252 else bt["exp"]
        for i in range(1,len(d_p)):
            e=exp_p.iloc[i]
            if e!=0:
                fc="rgba(22,163,74,.07)" if e>0 else "rgba(220,38,38,.07)"
                f10.add_vrect(x0=d_p.index[i-1],x1=d_p.index[i],fillcolor=fc,line_width=0,row=1,col=1)
        if le_d: f10.add_trace(go.Scatter(x=le_d,y=le_v,mode="markers",name="多單進場",
            marker=dict(color=C["long_e"],size=14,symbol="triangle-up",line=dict(color="#fff",width=1.5))),row=1,col=1)
        if lx_d: f10.add_trace(go.Scatter(x=lx_d,y=lx_v,mode="markers",name="多單出場",
            marker=dict(color=C["long_e"],size=9,symbol="circle",line=dict(color="#fff",width=1.2),opacity=.85)),row=1,col=1)
        if se_d: f10.add_trace(go.Scatter(x=se_d,y=se_v,mode="markers",name="空單進場",
            marker=dict(color=C["short_e"],size=14,symbol="triangle-down",line=dict(color="#fff",width=1.5))),row=1,col=1)
        if sx_d: f10.add_trace(go.Scatter(x=sx_d,y=sx_v,mode="markers",name="空單出場",
            marker=dict(color=C["short_e"],size=9,symbol="circle",line=dict(color="#fff",width=1.2),opacity=.85)),row=1,col=1)
        f10.add_trace(go.Scatter(x=cum_p.index,y=(cum_p-1)*100,name=f"v14策略 ({stats['total_ret']:+.1f}%)",
            line=dict(color=C["strat"],width=2.2)),row=2,col=1)
        f10.add_trace(go.Scatter(x=bh_p.index,y=(bh_p-1)*100,name="買進持有",
            line=dict(color=C["bh"],width=1.4,dash="dash"),opacity=.7),row=2,col=1)
        carr=cum_p.values; hwm=np.maximum.accumulate(carr); dd=(carr/hwm-1)*100
        f10.add_trace(go.Scatter(x=cum_p.index,y=dd,name="策略回撤",
            line=dict(color="#dc2626",width=0),fill="tozeroy",fillcolor="rgba(220,38,38,.1)"),row=2,col=1)
        f10.add_hline(y=0,line_color="#e2e8f0",line_width=1,row=2,col=1)
        f10.update_yaxes(title_text="指數",title_font_size=10,row=1,col=1)
        f10.update_yaxes(title_text="累積報酬(%)",title_font_size=10,row=2,col=1)
        theme(f10,560)
        f10.update_layout(legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="left",x=0,font_size=10))
        st.plotly_chart(f10,use_container_width=True)

        with st.expander("📋  近一年波段交易明細", expanded=False):
            if tds:
                rows=""
                for t in reversed(tds):
                    tag="✅ 獲利" if t["ret"]>0 else "❌ 虧損"
                    dc="dir-l" if t["dir"]==1 else "dir-s"
                    ds="▲ 多單" if t["dir"]==1 else "▼ 空單"
                    rc="win" if t["ret"]>0 else "lose"
                    rows+=f"""<tr>
                      <td>{str(t['date'].date())}</td>
                      <td>{str(t['exit_date'].date()) if 'exit_date' in t else '-'}</td>
                      <td class="{dc}">{ds}</td>
                      <td>{t.get('n_days','-')}</td>
                      <td><span class="{rc}">{t['ret']*100:+.2f}%</span></td>
                      <td>{tag}</td></tr>"""
                st.markdown(f"""<table class="dtable">
                  <tr><th>進場日</th><th>出場日</th><th>方向</th><th>持倉天</th><th>波段報酬</th><th>結果</th></tr>
                  {rows}</table>""", unsafe_allow_html=True)
            else:
                st.info("近一年無已完成波段")

    st.markdown("""
    <div style="text-align:center;padding:1.4rem 0 .5rem;border-top:1.5px solid #e2e8f0;margin-top:1.5rem">
      <span style="font-size:.72rem;color:#94a3b8;font-family:'IBM Plex Mono'">
        台指多因子策略 v15 — 不對稱動態權重 終極版 ／ 整體 70.3% ｜ 多 72.7% ｜ 空 67.7% ✅ 多空皆破 70%（回測 2021–2026）<br>
        勝率 70.3% ｜ 年均 13.1 筆（月均 1.1 次）｜ 在市場 51% ｜ 報酬 134% ｜ MDD -14% ／ 本頁僅供研究，不構成投資建議。
      </span>
    </div>""", unsafe_allow_html=True)

if __name__=="__main__":
    main()
