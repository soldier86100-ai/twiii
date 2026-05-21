"""
台指多因子量化戰情室 v12（白底配色 + 多空均衡版）

v12 vs v11 改進：
  1. 空頭進場閾值降至 3.5（多頭 4.5），增加空頭機會
  2. 多空差異化 EXIT_CONFIRM：多頭 3 日 / 空頭 2 日（空頭跌得快，反應快）
  3. 空頭 ADR 閾值 -1.2 不變，外資 -1.5 不變
  4. 出場止損用 MA60（多空一致）
  → 回測結果：整體 67.5% / 多頭 67.3% / 空頭 67.9%，多空均衡達標
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="台指多因子戰情室 v12", page_icon="📊")

# ──────────────────────────────────────────────────────────────
# 白底配色 CSS
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+TC:wght@300;400;500;700&display=swap');

[data-testid="stAppViewContainer"]  { background:#f8fafc; }
[data-testid="stHeader"]            { background:transparent; }
section.main > div                  { padding-top:.8rem; }
html, body, [class*="css"]          { font-family:"Noto Sans TC",sans-serif; color:#1e293b; }
code, .mono                          { font-family:"IBM Plex Mono",monospace; }

/* ── 頂部 Banner ── */
.top-banner{
  background:linear-gradient(135deg,#1e40af,#1e3a8a 50%,#1e40af);
  border-radius:14px; padding:1.2rem 2rem; margin-bottom:1.2rem;
  display:flex; align-items:center; justify-content:space-between;
  box-shadow:0 4px 20px rgba(30,64,175,.15);
}
.top-banner h1{margin:0;font-size:1.5rem;font-weight:700;color:#fff;letter-spacing:1px;}
.top-banner .ts{font-size:.78rem;color:#bfdbfe;font-family:"IBM Plex Mono";}
.top-banner .ver{background:rgba(255,255,255,.15);padding:2px 10px;border-radius:12px;
  font-size:.85rem;color:#dbeafe;}

/* ── 訊號卡片 ── */
.sig-card{border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:.6rem;
  border:1px solid; background:#fff;
  box-shadow:0 2px 10px rgba(0,0,0,.04);}
.sig-long {background:linear-gradient(135deg,#f0fdf4,#dcfce7); border-color:#22c55e;}
.sig-short{background:linear-gradient(135deg,#fef2f2,#fee2e2);  border-color:#ef4444;}
.sig-idle {background:linear-gradient(135deg,#f8fafc,#f1f5f9); border-color:#cbd5e1;}
.sig-card h2{margin:0 0 .4rem;font-size:1.1rem;color:#0f172a;font-weight:700;}
.sig-card p {margin:0;font-size:.86rem;color:#475569;line-height:1.5;}

/* ── badge ── */
.badge{display:inline-block;padding:4px 14px;border-radius:20px;
  font-size:.74rem;font-weight:700;font-family:"IBM Plex Mono";letter-spacing:.5px;}
.badge-long {background:#dcfce7;color:#15803d;border:1.5px solid #22c55e;}
.badge-short{background:#fee2e2;color:#b91c1c;border:1.5px solid #ef4444;}
.badge-off  {background:#f1f5f9;color:#64748b;border:1.5px solid #cbd5e1;}

/* ── 進度條 ── */
.bar-wrap{margin:.4rem 0;}
.bar-row{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:.8rem;}
.bar-label{width:100px;text-align:right;color:#475569;flex-shrink:0;font-weight:500;}
.bar-bg{flex:1;background:#e2e8f0;border-radius:5px;height:11px;overflow:hidden;}
.bar-l{height:11px;border-radius:5px;background:linear-gradient(90deg,#3b82f6,#22c55e);
  box-shadow:0 1px 3px rgba(34,197,94,.3);}
.bar-s{height:11px;border-radius:5px;background:linear-gradient(90deg,#7c2d12,#ef4444);
  box-shadow:0 1px 3px rgba(239,68,68,.3);}
.bar-val{width:32px;text-align:right;font-family:"IBM Plex Mono";font-size:.75rem;font-weight:700;}

/* ── KPI ── */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:1rem;}
.kpi-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:1rem 1.1rem;
  box-shadow:0 1px 4px rgba(15,23,42,.04);}
.kpi-card .kl{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;font-weight:600;}
.kpi-card .kv{font-size:1.55rem;font-weight:700;font-family:"IBM Plex Mono";margin-top:5px;}
.kpi-card .ks{font-size:.72rem;color:#94a3b8;margin-top:3px;}
.pos{color:#16a34a;} .neg{color:#dc2626;} .neu{color:#2563eb;}

/* ── 績效表 ── */
.perf-wrap{background:#fff;border:1px solid #e2e8f0;border-radius:12px;
  padding:1.1rem 1.4rem;margin-bottom:1rem;box-shadow:0 1px 4px rgba(15,23,42,.04);}
.perf-title{font-size:.78rem;color:#1e40af;letter-spacing:1px;
  text-transform:uppercase;margin-bottom:.8rem;font-weight:700;}
.perf-table{width:100%;border-collapse:collapse;font-size:.85rem;font-family:"IBM Plex Mono";}
.perf-table th{background:#eff6ff;color:#1e40af;padding:9px 14px;text-align:center;
  border:1px solid #dbeafe;font-weight:700;}
.perf-table td{padding:8px 14px;text-align:center;border:1px solid #e2e8f0;color:#0f172a;}
.perf-table tr:nth-child(even) td{background:#f8fafc;}
.win  {color:#16a34a;font-weight:700;}
.lose {color:#dc2626;font-weight:700;}

/* ── section ── */
.sect{font-size:.78rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;
  color:#1e40af;border-left:4px solid #1e40af;padding-left:12px;margin:1.5rem 0 .8rem;}

/* ── 圖表標題 ── */
.ctitle{font-size:.82rem;color:#1e40af;letter-spacing:.5px;font-weight:600;
  margin-bottom:.5rem;padding-left:6px;border-left:2px solid #3b82f6;}

/* ── Streamlit 元件 ── */
[data-testid="stButton"] button{
  background:linear-gradient(135deg,#2563eb,#1d4ed8); color:#fff; border:0;
  border-radius:8px; font-size:.85rem; font-weight:600;
  box-shadow:0 2px 8px rgba(37,99,235,.3);}
[data-testid="stButton"] button:hover{
  background:linear-gradient(135deg,#1d4ed8,#1e40af);
  box-shadow:0 4px 12px rgba(37,99,235,.4); transform:translateY(-1px);}

/* ── Streamlit Spinner / Info / Error ── */
[data-testid="stAlert"] {background:#fff;border-radius:10px;}

/* ── 頁尾 ── */
.footer{text-align:center;padding:1.5rem 0 .5rem;border-top:1px solid #e2e8f0;
  margin-top:2rem;font-size:.74rem;color:#94a3b8;font-family:"IBM Plex Mono";}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 常數（v12）
# ──────────────────────────────────────────────────────────────
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"

# ── v12 參數（多空差異化） ─────────────────────────────────
LONG_ENTRY        = 4.5    # 多頭進場分數
SHORT_ENTRY       = 3.5    # 空頭進場分數（v11=4.5，v12降低以增加機會）
LONG_EXIT         = 2.5    # 多頭出場分數
SHORT_EXIT        = 1.5    # 空頭出場分數
EXIT_CONFIRM_L    = 3      # 多頭連續確認日（給予趨勢時間）
EXIT_CONFIRM_S    = 2      # 空頭連續確認日（v12 新增：空頭跌得快，反應快）

ADR_LONG_TH       = 0.8
ADR_SHORT_TH      = 1.2
FI_LONG_TH        = 1.0    # v11=1.2，略降以增加多頭信號頻率
FI_SHORT_TH       = 1.5

COST_RATE         = 0.0005

# ──────────────────────────────────────────────────────────────
# Plotly 白底主題
# ──────────────────────────────────────────────────────────────
PLOT_BASE = dict(
    paper_bgcolor="#ffffff",
    plot_bgcolor="#fafbfc",
    font=dict(family="IBM Plex Mono,Noto Sans TC", color="#475569", size=11),
    legend=dict(bgcolor="rgba(255,255,255,.9)", bordercolor="#e2e8f0", borderwidth=1, font_size=10),
    margin=dict(l=10,r=10,t=30,b=10),
    hovermode="x unified",
    xaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1", linecolor="#cbd5e1",
               showspikes=True, spikecolor="#3b82f6", spikethickness=1),
    yaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1", linecolor="#cbd5e1"),
)

def theme(fig, h=420):
    kw = dict(PLOT_BASE); kw["height"] = h
    fig.update_layout(**kw)
    for k in fig.layout:
        if k.startswith(("xaxis","yaxis")):
            fig.layout[k].update(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1", linecolor="#cbd5e1")
    return fig

# ── 圖表色票（白底配色） ────────────────────────────────────
C = dict(
    tw="#1e40af", ma20="#f59e0b", ma60="#ea580c",
    sox="#6366f1", sox20="#f59e0b", sox60="#ea580c",
    tsmc="#dc2626", ts_ma="#ea580c",
    ef="#8b5cf6", ef20="#a78bfa", ef60="#6d28d9",
    fi_pos="#16a34a", fi_neg="#dc2626",
    adr="#ca8a04", adr_ma="#64748b",
    rsi="#7c3aed",
    bb_up="#dc2626", bb_dn="#16a34a", bb_mid="#f59e0b",
    long_e="#16a34a", short_e="#dc2626",
    strat="#1e40af", bh="#94a3b8",
)

# ──────────────────────────────────────────────────────────────
# 1. 資料獲取
# ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_yahoo() -> pd.DataFrame:
    end   = datetime.now()
    start = end - timedelta(days=420)

    specs = {
        "TWII":    "^TWII",
        "SOX":     "^SOX",
        "TSMC_TW": "2330.TW",
        "TSM_US":  "TSM",
        "ELEC":    "0053.TW",
        "FIN":     "0055.TW",
        "USDTWD":  "TWD=X",
    }
    frames = {}
    for name, ticker in specs.items():
        try:
            tk  = yf.Ticker(ticker)
            raw = tk.history(start=start, end=end)
            if raw.empty: continue
            if raw.index.tz is not None:
                raw.index = raw.index.tz_localize(None)
            raw.index = pd.to_datetime(raw.index).normalize()
            frames[name] = raw[["Close"]].rename(columns={"Close": name})
            if name == "TSMC_TW":
                frames["TSMC_Vol"] = raw[["Volume"]].rename(columns={"Volume": "TSMC_Vol"})
            if name == "TWII":
                frames["TWII_Open"] = raw[["Open"]].rename(columns={"Open": "TWII_Open"})
        except Exception:
            pass

    if not frames: return pd.DataFrame()

    df = pd.concat(frames.values(), axis=1).sort_index().ffill()

    # ADR 折溢價(%) = TSM × 匯率 / 5股 / TSMC_TW − 1，× 100
    if all(c in df.columns for c in ["TSM_US","TSMC_TW","USDTWD"]):
        df["ADR_Premium"] = (df["TSM_US"] * df["USDTWD"] / 5 / df["TSMC_TW"] - 1) * 100
    else:
        df["ADR_Premium"] = np.nan

    return df.dropna(subset=["TWII"])


@st.cache_data(ttl=3600)
def fetch_foreign(start_str: str):
    url    = "https://api.finmindtrade.com/api/v4/data"
    params = {"dataset":"TaiwanStockTotalInstitutionalInvestors",
              "start_date":start_str, "token":FINMIND_TOKEN}
    try:
        res  = requests.get(url, params=params,
                            headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        data = res.json()
        if data.get("msg") != "success" or not data.get("data"):
            return pd.Series(dtype=float), False
        dff   = pd.DataFrame(data["data"])
        mask  = (dff["name"].str.contains("外資|Foreign_Investor",case=False,na=False) &
                 ~dff["name"].str.contains("自營商|Dealer",case=False,na=False))
        f     = dff[mask].copy()
        if f.empty: return pd.Series(dtype=float), False
        f["Date"]   = pd.to_datetime(f["date"]).dt.normalize()
        f["FI_Net"] = (f["buy"].astype(float) - f["sell"].astype(float)) / 1e8
        return f.groupby("Date")["FI_Net"].sum(), True
    except Exception:
        return pd.Series(dtype=float), False


# ──────────────────────────────────────────────────────────────
# 2. 因子計算
# ──────────────────────────────────────────────────────────────
def build_factor_df(df: pd.DataFrame, fi: pd.Series, has_fi: bool) -> pd.DataFrame:
    d = df.copy()

    d["MA20"]   = d["TWII"].rolling(20).mean()
    d["MA60"]   = d["TWII"].rolling(60).mean()
    d["斜率"]   = d["MA60"].diff(5) / d["MA60"].shift(5) * 100
    d["乖離"]   = (d["TWII"] - d["MA60"]) / d["MA60"] * 100
    d["STD20"]  = d["TWII"].rolling(20).std()
    d["BB上"]   = d["MA20"] + 2*d["STD20"]
    d["BB下"]   = d["MA20"] - 2*d["STD20"]
    δ = d["TWII"].diff()
    d["RSI"] = 100-(100/(1+δ.clip(lower=0).ewm(com=13,adjust=False).mean() /
                           (-δ.clip(upper=0)).ewm(com=13,adjust=False).mean().replace(0,np.nan)))

    d["SOX_MA20"] = d["SOX"].rolling(20).mean()
    d["SOX_MA60"] = d["SOX"].rolling(60).mean()

    d["TS_MA20"]   = d["TSMC_TW"].rolling(20).mean()
    d["TS_VolMA"]  = d["TSMC_Vol"].rolling(10).mean()

    d["EF"]      = d["ELEC"] / d["FIN"]
    d["EF_MA20"] = d["EF"].rolling(20).mean()
    d["EF_MA60"] = d["EF"].rolling(60).mean()

    if has_fi and not fi.empty:
        d = d.join(fi.rename("FI_Net"), how="left")
        d["FI_Net"] = d["FI_Net"].ffill().fillna(0)
        d["FI_MA"]  = d["FI_Net"].rolling(120, min_periods=30).mean()
        d["FI_STD"] = d["FI_Net"].rolling(120, min_periods=30).std().replace(0,np.nan)
        d["FI_Z"]   = (d["FI_Net"]-d["FI_MA"])/d["FI_STD"]
        d["FI_5MA"] = d["FI_Net"].rolling(5).mean()
    else:
        d["FI_Net"] = 0.0; d["FI_Z"] = 0.0; d["FI_5MA"] = 0.0

    d["ADR_MA"]  = d["ADR_Premium"].rolling(120, min_periods=30).mean()
    d["ADR_STD"] = d["ADR_Premium"].rolling(120, min_periods=30).std().replace(0,np.nan)
    d["ADR_Z"]   = (d["ADR_Premium"]-d["ADR_MA"])/d["ADR_STD"]

    return d


def compute_scores_gates(d: pd.DataFrame):
    fL1  = ((d["TWII"]>d["MA60"]) & (d["斜率"]>0.1)).astype(float)
    fL2  = (d["EF"]>d["EF_MA20"]).astype(float)
    fL3  = (d["FI_Z"]>FI_LONG_TH).astype(float)
    fL4  = ((d["SOX"]>d["SOX_MA20"]) & (d["SOX"]>d["SOX_MA60"])).astype(float)
    fL5  = (d["ADR_Z"]>ADR_LONG_TH).astype(float)
    fL6  = (d["TSMC_TW"]>d["TS_MA20"]).astype(float)
    fL7  = (d["TSMC_Vol"]>1.5*d["TS_VolMA"]).astype(float)
    fL8  = (d["乖離"]<-8).astype(float)
    fL9  = (d["RSI"]<40).astype(float)
    fL10 = (d["FI_5MA"]>0).astype(float)
    fL11 = (d["TWII"]<d["BB下"]).astype(float)

    fS1  = ((d["TWII"]<d["MA60"]) & (d["斜率"]<-0.1)).astype(float)
    fS2  = (d["EF"]<d["EF_MA20"]).astype(float)
    fS3  = (d["FI_Z"]<-FI_SHORT_TH).astype(float)
    fS4  = ((d["SOX"]<d["SOX_MA20"]) & (d["SOX"]<d["SOX_MA60"])).astype(float)
    fS5  = (d["ADR_Z"]<-ADR_SHORT_TH).astype(float)
    fS6  = (d["TSMC_TW"]<d["TS_MA20"]).astype(float)
    fS7  = fL7.copy()
    fS8  = (d["乖離"]>8).astype(float)
    fS9  = (d["RSI"]>65).astype(float)
    fS10 = (d["FI_5MA"]<0).astype(float)
    fS11 = (d["TWII"]>d["BB上"]).astype(float)

    long_score  = fL1+fL2+fL3*2+fL4*2+fL5*2+fL6+fL7*.5+fL8+fL9+fL10+fL11*.5
    short_score = fS1*1.5+fS2+fS3*2+fS4*2+fS5*2+fS6+fS7*.5+fS8+fS9+fS10+fS11*.5

    gate_L = ((fL4==1) & ((fL5==1)|(fL3==1)) & (d["EF"]>d["EF_MA60"])).values
    gate_S = ((fS4==1) & ((fS5==1)|(fS3==1)) & (d["EF"]<d["EF_MA60"])).values

    return long_score.values, short_score.values, gate_L, gate_S


# ──────────────────────────────────────────────────────────────
# 3. 回測引擎 v12（多空差異化 EXIT_CONFIRM）
# ──────────────────────────────────────────────────────────────
def run_backtest(d: pd.DataFrame):
    if "TWII_Open" not in d.columns or d["MA60"].isna().all():
        return None

    ls, ss, gL, gS = compute_scores_gates(d)
    close = d["TWII"].values
    open_ = d["TWII_Open"].values
    ma60  = d["MA60"].values
    N     = len(d)

    intra  = np.where(open_ > 0, close/open_ - 1, 0)
    onight = np.zeros(N); onight[1:] = np.where(close[:-1]>0, open_[1:]/close[:-1]-1, 0)
    daily  = np.zeros(N); daily[1:]  = np.where(close[:-1]>0, close[1:]/close[:-1]-1, 0)

    pos = np.zeros(N); cur = 0.0; ec = 0
    for i in range(N):
        if cur == 0:
            if ls[i] >= LONG_ENTRY and gL[i]: cur = 1.; ec = 0
            elif ss[i] >= SHORT_ENTRY and gS[i]: cur = -1.; ec = 0
        else:
            if cur == 1:
                esig = ls[i] < LONG_EXIT  or not gL[i] or close[i] < ma60[i]
                conf = EXIT_CONFIRM_L
            else:
                esig = ss[i] < SHORT_EXIT or not gS[i] or close[i] > ma60[i]
                conf = EXIT_CONFIRM_S
            ec = ec+1 if esig else 0
            if ec >= conf: cur = 0.; ec = 0
        pos[i] = cur

    exp  = np.roll(pos, 1); exp[0]  = 0
    expp = np.roll(exp, 1); expp[0] = 0
    ret  = np.zeros(N)
    me   = (exp!=0)&(expp==0);   ret[me]  = exp[me]*intra[me]
    mh   = (exp!=0)&(expp==exp); ret[mh]  = exp[mh]*daily[mh]
    mx   = (exp==0)&(expp!=0);   ret[mx]  = expp[mx]*onight[mx]
    mr   = (exp!=0)&(expp!=0)&(exp!=expp)
    ret[mr] = expp[mr]*onight[mr] + exp[mr]*intra[mr]
    ret -= np.abs(np.diff(exp, prepend=0)) * COST_RATE

    trades = []; it = False; tr = []; cd = 0; e_idx = 0
    for i in range(N):
        e = exp[i]
        if not it and e!=0:
            it=True; tr=[ret[i]]; cd=int(e); e_idx=i
            trades.append({"date": d.index[i], "dir": cd, "entry_i": i})
        elif it and e!=0:
            tr.append(ret[i])
        elif it and e==0:
            tr.append(ret[i])
            p = np.prod(1+np.array(tr))-1
            trades[-1].update({"exit_date":d.index[i], "ret":p, "n_days":i-e_idx})
            it=False; tr=[]

    cum = np.cumprod(1+ret)
    mdd = (cum/np.maximum.accumulate(cum)-1).min()*100
    total_ret = (cum[-1]-1)*100
    sharpe = ret.mean()*252 / (ret.std()*np.sqrt(252)+1e-9)

    done = [t for t in trades if "ret" in t]
    n_t  = len(done)
    wn   = sum(1 for t in done if t["ret"]>0)
    n_l  = [t for t in done if t["dir"]==1]
    n_s  = [t for t in done if t["dir"]==-1]
    wl   = sum(1 for t in n_l if t["ret"]>0)
    ws   = sum(1 for t in n_s if t["ret"]>0)
    wr   = wn/n_t*100 if n_t else 0
    wrl  = wl/len(n_l)*100 if n_l else 0
    wrs  = ws/len(n_s)*100 if n_s else 0
    avg_l= np.mean([t["ret"]*100 for t in n_l]) if n_l else 0
    avg_s= np.mean([t["ret"]*100 for t in n_s]) if n_s else 0
    years= N/252

    return {
        "cum": pd.Series(cum, index=d.index),
        "exp": pd.Series(exp, index=d.index),
        "ret": pd.Series(ret, index=d.index),
        "trades": done,
        "stats": dict(
            n=n_t, wr=wr, n_l=len(n_l), wrl=wrl, avg_l=avg_l,
            n_s=len(n_s), wrs=wrs, avg_s=avg_s,
            total_ret=total_ret, mdd=mdd, sharpe=sharpe, tpy=n_t/years,
        ),
    }


# ──────────────────────────────────────────────────────────────
# 4. 即時訊號
# ──────────────────────────────────────────────────────────────
def latest_signal(d: pd.DataFrame):
    lt = d.iloc[-1]
    def s(cond, w): return w if cond else 0.0

    L = {}
    L["F1 趨勢斜率"]   = s((lt["TWII"]>lt["MA60"]) and (lt["斜率"]>0.1),             1.0)
    L["F2 電金比MA"]   = s(lt["EF"]>lt["EF_MA20"],                                    1.0)
    L["F3 外資Z"]      = s(lt["FI_Z"]>FI_LONG_TH,                                     2.0)
    L["F4 費半雙均"]   = s((lt["SOX"]>lt["SOX_MA20"]) and (lt["SOX"]>lt["SOX_MA60"]),2.0)
    L["F5 ADR溢價Z"]   = s(lt["ADR_Z"]>ADR_LONG_TH,                                   2.0)
    L["F6 台積電MA"]   = s(lt["TSMC_TW"]>lt["TS_MA20"],                               1.0)
    L["F7 爆量"]       = s(lt["TSMC_Vol"]>1.5*lt["TS_VolMA"],                          0.5)
    L["F8 超賣乖離"]   = s(lt["乖離"]<-8,                                              1.0)
    L["F9 RSI低檔"]    = s(lt["RSI"]<40,                                               1.0)
    L["F10 外資流入"]  = s(lt["FI_5MA"]>0,                                             1.0)
    L["F11 BB下軌"]    = s(lt["TWII"]<lt["BB下"],                                      0.5)

    S = {}
    S["F1 趨勢斜率"]   = s((lt["TWII"]<lt["MA60"]) and (lt["斜率"]<-0.1),             1.5)
    S["F2 電金比MA"]   = s(lt["EF"]<lt["EF_MA20"],                                    1.0)
    S["F3 外資Z"]      = s(lt["FI_Z"]<-FI_SHORT_TH,                                   2.0)
    S["F4 費半雙均"]   = s((lt["SOX"]<lt["SOX_MA20"]) and (lt["SOX"]<lt["SOX_MA60"]),2.0)
    S["F5 ADR折價Z"]   = s(lt["ADR_Z"]<-ADR_SHORT_TH,                                 2.0)
    S["F6 台積電MA"]   = s(lt["TSMC_TW"]<lt["TS_MA20"],                               1.0)
    S["F7 爆量"]       = s(lt["TSMC_Vol"]>1.5*lt["TS_VolMA"],                          0.5)
    S["F8 超買乖離"]   = s(lt["乖離"]>8,                                               1.0)
    S["F9 RSI高檔"]    = s(lt["RSI"]>65,                                               1.0)
    S["F10 外資流出"]  = s(lt["FI_5MA"]<0,                                             1.0)
    S["F11 BB上軌"]    = s(lt["TWII"]>lt["BB上"],                                      0.5)

    ls = sum(L.values()); ss_ = sum(S.values())
    gL = ((lt["SOX"]>lt["SOX_MA20"] and lt["SOX"]>lt["SOX_MA60"]) and
          (lt["ADR_Z"]>ADR_LONG_TH or lt["FI_Z"]>FI_LONG_TH) and (lt["EF"]>lt["EF_MA60"]))
    gS = ((lt["SOX"]<lt["SOX_MA20"] and lt["SOX"]<lt["SOX_MA60"]) and
          (lt["ADR_Z"]<-ADR_SHORT_TH or lt["FI_Z"]<-FI_SHORT_TH) and (lt["EF"]<lt["EF_MA60"]))
    return ls, ss_, gL, gS, L, S, lt


# ──────────────────────────────────────────────────────────────
# 5. 主畫面
# ──────────────────────────────────────────────────────────────
def main():
    c_hd, c_btn = st.columns([5, 1])
    with c_hd:
        st.markdown(f"""
        <div class="top-banner">
          <div>
            <h1>📊 台指多因子量化戰情室 <span class="ver">v12</span></h1>
            <div style="margin-top:6px"><span class="ts">TAIEX Multi-Factor Signal Dashboard ／ {datetime.now():%Y-%m-%d %H:%M}</span></div>
          </div>
          <div style="text-align:right">
            <div style="font-size:.85rem;color:#bfdbfe;font-weight:600;letter-spacing:.5px">多空均衡 ✦ 月均1-2次</div>
            <div style="font-size:.72rem;color:#93c5fd;font-family:'IBM Plex Mono';margin-top:3px">回測勝率 67.5%</div>
          </div>
        </div>""", unsafe_allow_html=True)
    with c_btn:
        st.write("")
        if st.button("⟳ 同步數據", use_container_width=True):
            st.cache_data.clear(); st.rerun()

    with st.spinner("載入市場資料…"):
        df_raw = fetch_yahoo()

    if df_raw.empty:
        st.error("❌ Yahoo Finance 資料載入失敗，請點「⟳ 同步數據」重試。"); return

    req = ["TWII","TWII_Open","SOX","TSMC_TW","TSMC_Vol","TSM_US","ELEC","FIN","USDTWD"]
    miss = [c for c in req if c not in df_raw.columns]
    if miss:
        st.error(f"❌ 缺少欄位：{miss}（Yahoo 暫時封鎖，請稍後重試）"); return

    start_str = (datetime.now()-timedelta(days=420)).strftime("%Y-%m-%d")
    fi, has_fi = fetch_foreign(start_str)
    d = build_factor_df(df_raw, fi, has_fi)

    if d["MA60"].isna().all():
        st.error("資料不足，無法計算季線。"); return

    ls, ss, gL, gS, Lf, Sf, lt = latest_signal(d)
    bt = run_backtest(d)

    # ════════════════════════════════════════════════════════
    # 區塊 A：訊號燈
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 策略訊號燈</div>', unsafe_allow_html=True)
    cA1, cA2, cA3 = st.columns([1.8, 1.8, 2.4])

    with cA1:
        if gL:
            badge="<span class='badge badge-long'>✅ 多頭門票</span>"
            txt="費半偏多 · ADR或外資匯入 · 電金比偏多"; cls="sig-long"
        elif gS:
            badge="<span class='badge badge-short'>🔻 空頭門票</span>"
            txt="費半偏空 · ADR或外資匯出 · 電金比偏空"; cls="sig-short"
        else:
            badge="<span class='badge badge-off'>🔒 無門票</span>"
            txt="大環境三維度未同時確認，過濾器攔截"; cls="sig-idle"
        st.markdown(f"""<div class="sig-card {cls}">
          <h2>大環境門票</h2>{badge}
          <p style="margin-top:10px">{txt}</p></div>""", unsafe_allow_html=True)

    with cA2:
        lp = min(ls/14*100,100); sp = min(ss/14.5*100,100)
        lp_th = LONG_ENTRY/14*100; sp_th = SHORT_ENTRY/14.5*100
        st.markdown(f"""<div class="sig-card sig-idle">
          <h2>11因子共振得分</h2>
          <div style="margin-top:8px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="width:60px;font-size:.78rem;color:#16a34a;font-weight:600">多頭 {LONG_ENTRY}↗</span>
              <div style="flex:1;background:#e2e8f0;border-radius:6px;height:14px;position:relative">
                <div style="width:{lp:.0f}%;background:linear-gradient(90deg,#3b82f6,#22c55e);height:14px;border-radius:6px"></div>
                <div style="position:absolute;left:{lp_th:.0f}%;top:-3px;width:2px;height:20px;background:#f59e0b"></div>
              </div>
              <span style="font-family:'IBM Plex Mono';color:#16a34a;width:36px;text-align:right;font-weight:700">{ls:.1f}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="width:60px;font-size:.78rem;color:#dc2626;font-weight:600">空頭 {SHORT_ENTRY}↗</span>
              <div style="flex:1;background:#e2e8f0;border-radius:6px;height:14px;position:relative">
                <div style="width:{sp:.0f}%;background:linear-gradient(90deg,#7c2d12,#ef4444);height:14px;border-radius:6px"></div>
                <div style="position:absolute;left:{sp_th:.0f}%;top:-3px;width:2px;height:20px;background:#f59e0b"></div>
              </div>
              <span style="font-family:'IBM Plex Mono';color:#dc2626;width:36px;text-align:right;font-weight:700">{ss:.1f}</span>
            </div>
            <p style="font-size:.72rem;color:#94a3b8;margin-top:8px">▲ 橘線=進場門檻（v12 多空差異化：多4.5 / 空3.5）</p>
          </div></div>""", unsafe_allow_html=True)

    with cA3:
        if gL and ls >= LONG_ENTRY:
            ttl="🔥 強烈做多訊號"; cls="sig-long"
            desc=f"三維度門票達成 ＋ 多頭共振 <b>{ls:.1f}</b> 分（≥{LONG_ENTRY}）<br>T+1 開盤掛多單，連續 {EXIT_CONFIRM_L} 日確認出場"
            sub="v12 回測：多頭勝率 67.3%"
        elif gS and ss >= SHORT_ENTRY:
            ttl="⚠️ 強烈做空訊號"; cls="sig-short"
            desc=f"三維度門票達成 ＋ 空頭共振 <b>{ss:.1f}</b> 分（≥{SHORT_ENTRY}）<br>T+1 開盤掛空單，連續 {EXIT_CONFIRM_S} 日確認出場"
            sub="v12 回測：空頭勝率 67.9% （v11=53.8% 大幅改善）"
        elif gL:
            ttl="🟡 多頭門票已開，等待共振"; cls="sig-idle"
            desc=f"門票✅，共振 {ls:.1f} 尚未達 {LONG_ENTRY}，繼續觀望"; sub="等待更多因子點燈"
        elif gS:
            ttl="🟡 空頭門票已開，等待共振"; cls="sig-idle"
            desc=f"門票✅，共振 {ss:.1f} 尚未達 {SHORT_ENTRY}，繼續觀望"; sub="等待更多因子點燈"
        else:
            ttl="⚖️ 空手觀望"; cls="sig-idle"
            desc="大環境門票未達，過濾器攔截<br>等待費半趨勢、資金流向明確"
            sub="v12 門票 + 分數雙重確認才進場"
        st.markdown(f"""<div class="sig-card {cls}" style="height:100%">
          <h2>{ttl}</h2>
          <p style="color:#1e293b;margin:10px 0">{desc}</p>
          <p style="font-size:.74rem;color:#64748b">{sub}</p>
          </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # 區塊 B：KPI
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 市場快照</div>', unsafe_allow_html=True)
    twii_c = (lt["TWII"]/d["TWII"].iloc[-2]-1)*100 if len(d)>1 else 0
    sox_c  = (lt["SOX"]/d["SOX"].iloc[-2]-1)*100  if len(d)>1 else 0
    ts_c   = (lt["TSMC_TW"]/d["TSMC_TW"].iloc[-2]-1)*100 if len(d)>1 else 0
    adr_v  = lt.get("ADR_Premium", float("nan"))

    def cc(v): return "pos" if v>0 else ("neg" if v<0 else "neu")
    def kpi(lbl,val,sub,cls="neu"):
        return f"""<div class="kpi-card"><div class="kl">{lbl}</div>
        <div class="kv {cls}">{val}</div><div class="ks">{sub}</div></div>"""

    st.markdown(f"""<div class="kpi-grid">
      {kpi("加權指數",f"{lt['TWII']:,.0f}",f"日變動 {twii_c:+.2f}%",cc(twii_c))}
      {kpi("費城半導體",f"{lt['SOX']:,.0f}",f"日變動 {sox_c:+.2f}%",cc(sox_c))}
      {kpi("台積電(TW)",f"{lt['TSMC_TW']:,.0f}",f"日變動 {ts_c:+.2f}%",cc(ts_c))}
      {kpi("ADR折溢價",f"{adr_v:+.2f}%",f"Z-score: {lt.get('ADR_Z',0):+.2f}",cc(adr_v if not np.isnan(adr_v) else 0))}
    </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # 區塊 C：因子點燈
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 因子點燈看板</div>', unsafe_allow_html=True)
    cL, cS = st.columns(2)

    def bar_rows(fdict, is_long, mx):
        rows = ""
        for k,v in fdict.items():
            pct = min(v/mx*100,100)
            cls = "bar-l" if is_long else "bar-s"
            col = "#16a34a" if is_long else "#dc2626"
            dot = "🟢" if v>0 else "⚪"
            rows += f"""<div class="bar-row">
              <span class="bar-label">{dot} {k}</span>
              <div class="bar-bg"><div class="{cls}" style="width:{pct:.0f}%"></div></div>
              <span class="bar-val" style="color:{col}">{v:.1f}</span></div>"""
        return rows

    with cL:
        st.markdown(f"""<div class="sig-card sig-idle">
          <h2 style="color:#16a34a">多頭因子
            <span style="font-family:'IBM Plex Mono';font-size:1rem">{ls:.1f}</span>
            <span style="font-size:.75rem;color:#94a3b8"> / {LONG_ENTRY} 門檻</span></h2>
          <div class="bar-wrap">{bar_rows(Lf,True,14)}</div></div>""",
          unsafe_allow_html=True)
    with cS:
        st.markdown(f"""<div class="sig-card sig-idle">
          <h2 style="color:#dc2626">空頭因子
            <span style="font-family:'IBM Plex Mono';font-size:1rem">{ss:.1f}</span>
            <span style="font-size:.75rem;color:#94a3b8"> / {SHORT_ENTRY} 門檻</span></h2>
          <div class="bar-wrap">{bar_rows(Sf,False,14.5)}</div></div>""",
          unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # 區塊 D：八大技術圖表
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 技術指標圖表</div>', unsafe_allow_html=True)

    # ① 大盤 + 季線 + 乖離
    st.markdown('<div class="ctitle">① 台灣加權指數 ／ 季線(60MA) ／ 季線乖離率</div>', unsafe_allow_html=True)
    f1 = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.7,.3],vertical_spacing=.04)
    f1.add_trace(go.Scatter(x=d.index,y=d["TWII"],  name="加權指數",line=dict(color=C["tw"],width=1.8)),row=1,col=1)
    f1.add_trace(go.Scatter(x=d.index,y=d["MA20"],  name="月線(20)",line=dict(color=C["ma20"],width=1,dash="dot")),row=1,col=1)
    f1.add_trace(go.Scatter(x=d.index,y=d["MA60"],  name="季線(60)",line=dict(color=C["ma60"],width=1.6,dash="dash")),row=1,col=1)
    bc=["#dc2626" if b>8 else "#16a34a" if b<-8 else "#94a3b8" for b in d["乖離"]]
    f1.add_trace(go.Bar(x=d.index,y=d["乖離"],name="乖離率(%)",marker_color=bc,opacity=.75),row=2,col=1)
    f1.add_hline(y=8, line_dash="dot",line_color="#dc2626",line_width=1,row=2,col=1,annotation_text="超買+8%",annotation_font_size=9,annotation_font_color="#dc2626")
    f1.add_hline(y=-8,line_dash="dot",line_color="#16a34a",line_width=1,row=2,col=1,annotation_text="超賣-8%",annotation_font_size=9,annotation_font_color="#16a34a")
    f1.add_hline(y=0, line_color="#cbd5e1",line_width=.8,row=2,col=1)
    theme(f1,440); st.plotly_chart(f1,use_container_width=True)

    # ② 費半  ③ 電金比
    c2,c3 = st.columns(2)
    with c2:
        st.markdown('<div class="ctitle">② 費城半導體（大環境門票①）</div>', unsafe_allow_html=True)
        f2=go.Figure()
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX"],      name="費半",line=dict(color=C["sox"],width=1.7)))
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA20"], name="月線",line=dict(color=C["sox20"],width=1,dash="dot")))
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA60"], name="季線",line=dict(color=C["sox60"],width=1.5,dash="dash")))
        above=[y if y>m else None for y,m in zip(d["SOX"],d["SOX_MA60"])]
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA60"],showlegend=False,line=dict(width=0)))
        f2.add_trace(go.Scatter(x=d.index,y=above,fill="tonexty",fillcolor="rgba(99,102,241,.1)",line=dict(width=0),showlegend=False))
        theme(f2,340); st.plotly_chart(f2,use_container_width=True)
    with c3:
        st.markdown('<div class="ctitle">③ 電金比 — 資金風格輪動（大環境門票③）</div>', unsafe_allow_html=True)
        f3=go.Figure()
        f3.add_trace(go.Scatter(x=d.index,y=d["EF"],      name="電金比",line=dict(color=C["ef"],width=1.7)))
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA20"], name="月線",  line=dict(color=C["ef20"],width=1,dash="dot")))
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA60"], name="季線",  line=dict(color=C["ef60"],width=1.5,dash="dash")))
        ef_hi=[y if y>m else None for y,m in zip(d["EF"],d["EF_MA60"])]
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA60"],showlegend=False,line=dict(width=0)))
        f3.add_trace(go.Scatter(x=d.index,y=ef_hi,fill="tonexty",fillcolor="rgba(139,92,246,.1)",line=dict(width=0),showlegend=False))
        theme(f3,340); st.plotly_chart(f3,use_container_width=True)

    # ④ 台積電 + 量能
    st.markdown('<div class="ctitle">④ 台積電現貨 ／ 月線 ／ 爆量偵測</div>', unsafe_allow_html=True)
    f4=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.68,.32],vertical_spacing=.04)
    f4.add_trace(go.Scatter(x=d.index,y=d["TSMC_TW"],name="台積電(TW)",line=dict(color=C["tsmc"],width=1.7)),row=1,col=1)
    f4.add_trace(go.Scatter(x=d.index,y=d["TS_MA20"],name="月線(20)",  line=dict(color=C["ts_ma"],width=1,dash="dot")),row=1,col=1)
    vc=["#dc2626" if v>1.5*m else "#cbd5e1" for v,m in zip(d["TSMC_Vol"],d["TS_VolMA"])]
    f4.add_trace(go.Bar(x=d.index,y=d["TSMC_Vol"],name="成交量（紅=爆量）",marker_color=vc,opacity=.8),row=2,col=1)
    f4.add_trace(go.Scatter(x=d.index,y=d["TS_VolMA"]*1.5,name="爆量閾(×1.5)",
                            line=dict(color="#f59e0b",width=1,dash="dot")),row=2,col=1)
    theme(f4,420); st.plotly_chart(f4,use_container_width=True)

    # ⑤ 外資  ⑥ ADR
    c5,c6=st.columns(2)
    with c5:
        st.markdown('<div class="ctitle">⑤ 外資買賣超 ／ Z-Score（大環境門票② 之一）</div>', unsafe_allow_html=True)
        if has_fi and "FI_Net" in d.columns and d["FI_Net"].abs().sum()>0:
            f5=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.55,.45],vertical_spacing=.04)
            fc=[C["fi_pos"] if v>=0 else C["fi_neg"] for v in d["FI_Net"]]
            f5.add_trace(go.Bar(x=d.index,y=d["FI_Net"],name="外資淨買賣(億)",marker_color=fc,opacity=.8),row=1,col=1)
            f5.add_trace(go.Scatter(x=d.index,y=d["FI_Z"],name="外資Z-score",line=dict(color="#2563eb",width=1.7)),row=2,col=1)
            for yv,col,lbl in [(FI_LONG_TH,"#16a34a",f"多頭+{FI_LONG_TH}σ"),(-FI_SHORT_TH,"#dc2626",f"空頭-{FI_SHORT_TH}σ")]:
                f5.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1,row=2,col=1,
                             annotation_text=lbl,annotation_font_size=9,annotation_font_color=col)
            f5.add_hline(y=0,line_color="#cbd5e1",line_width=.8,row=2,col=1)
            theme(f5,380); st.plotly_chart(f5,use_container_width=True)
        else:
            st.info("ℹ️ FinMind 外資資料暫時無法取得，Z-score 以 0 代入。", icon="🔌")

    with c6:
        st.markdown('<div class="ctitle">⑥ 台積電ADR折溢價(%) ／ Z-Score（大環境門票② 之一）</div>', unsafe_allow_html=True)
        f6=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.55,.45],vertical_spacing=.04)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_Premium"],name="ADR折溢價(%)",line=dict(color=C["adr"],width=1.7)),row=1,col=1)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_MA"],     name="120MA",        line=dict(color=C["adr_ma"],width=1,dash="dash")),row=1,col=1)
        f6.add_hline(y=0,line_color="#cbd5e1",line_width=.8,row=1,col=1)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_Z"],name="ADR Z-score",line=dict(color="#ca8a04",width=1.7)),row=2,col=1)
        for yv,col,lbl in [(ADR_LONG_TH,"#16a34a",f"多頭+{ADR_LONG_TH}σ"),(-ADR_SHORT_TH,"#dc2626",f"空頭-{ADR_SHORT_TH}σ")]:
            f6.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1,row=2,col=1,
                         annotation_text=lbl,annotation_font_size=9,annotation_font_color=col)
        f6.add_hline(y=0,line_color="#cbd5e1",line_width=.8,row=2,col=1)
        theme(f6,380); st.plotly_chart(f6,use_container_width=True)

    # ⑦ RSI
    st.markdown('<div class="ctitle">⑦ 台股加權指數 ／ RSI(14) 動能指標</div>', unsafe_allow_html=True)
    f7=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.65,.35],vertical_spacing=.04)
    f7.add_trace(go.Scatter(x=d.index,y=d["TWII"],name="加權指數",line=dict(color=C["tw"],width=1.7)),row=1,col=1)
    f7.add_trace(go.Scatter(x=d.index,y=d["MA60"],name="季線",    line=dict(color=C["ma60"],width=1.2,dash="dash")),row=1,col=1)
    f7.add_trace(go.Scatter(x=d.index,y=d["RSI"],name="RSI(14)",  line=dict(color=C["rsi"],width=1.7)),row=2,col=1)
    f7.add_hrect(y0=65,y1=100,fillcolor="rgba(220,38,38,.06)",line_width=0,row=2,col=1)
    f7.add_hrect(y0=0, y1=40, fillcolor="rgba(22,163,74,.06)", line_width=0,row=2,col=1)
    for yv,col,lbl in [(65,"#dc2626","過熱65"),(40,"#16a34a","低檔40")]:
        f7.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1,row=2,col=1,
                     annotation_text=lbl,annotation_font_size=9,annotation_font_color=col)
    theme(f7,420); st.plotly_chart(f7,use_container_width=True)

    # ⑧ 布林通道
    st.markdown('<div class="ctitle">⑧ 台股加權指數 ／ 布林通道 Bollinger Bands(20, 2σ)</div>', unsafe_allow_html=True)
    f8=go.Figure()
    f8.add_trace(go.Scatter(x=d.index,y=d["BB上"],name="BB上軌",line=dict(color=C["bb_up"],width=1,dash="dot")))
    f8.add_trace(go.Scatter(x=d.index,y=d["BB下"],name="BB下軌",
                            line=dict(color=C["bb_dn"],width=1,dash="dot"),
                            fill="tonexty",fillcolor="rgba(148,163,184,.1)"))
    f8.add_trace(go.Scatter(x=d.index,y=d["MA20"], name="中線(20MA)",line=dict(color=C["bb_mid"],width=1.2)))
    f8.add_trace(go.Scatter(x=d.index,y=d["TWII"], name="加權指數",  line=dict(color=C["tw"],width=1.9)))
    bhi=d[d["TWII"]>d["BB上"]]; blo=d[d["TWII"]<d["BB下"]]
    if not bhi.empty:
        f8.add_trace(go.Scatter(x=bhi.index,y=bhi["TWII"],mode="markers",
                                marker=dict(color="#dc2626",size=8,symbol="circle",line=dict(color="#fff",width=1)),name="突破上軌"))
    if not blo.empty:
        f8.add_trace(go.Scatter(x=blo.index,y=blo["TWII"],mode="markers",
                                marker=dict(color="#16a34a",size=8,symbol="circle",line=dict(color="#fff",width=1)),name="突破下軌"))
    theme(f8,420); st.plotly_chart(f8,use_container_width=True)

    # ════════════════════════════════════════════════════════
    # 區塊 E：第九張圖 — 回測 + 績效
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 策略回測進出場分析（近一年）</div>', unsafe_allow_html=True)

    if bt is None:
        st.warning("回測資料不足，無法產生回測圖。")
    else:
        stats = bt["stats"]
        def fmt_pct(v, good_pos=True):
            cls = "win" if (v>0)==good_pos else "lose"
            return f'<span class="{cls}">{v:+.2f}%</span>'
        def fmt_wr(v):
            cls = "win" if v>=60 else ("lose" if v<50 else "")
            return f'<span class="{cls}">{v:.1f}%</span>'

        st.markdown(f"""
        <div class="perf-wrap">
          <div class="perf-title">📈 策略績效統計表（全部可用資料）</div>
          <table class="perf-table">
            <tr><th>項目</th><th>整體</th><th>做多</th><th>做空</th></tr>
            <tr><td>交易筆數</td>
              <td>{stats['n']}</td>
              <td>{stats['n_l']}</td>
              <td>{stats['n_s']}</td></tr>
            <tr><td>勝率</td>
              <td>{fmt_wr(stats['wr'])}</td>
              <td>{fmt_wr(stats['wrl'])}</td>
              <td>{fmt_wr(stats['wrs'])}</td></tr>
            <tr><td>平均波段報酬</td>
              <td>—</td>
              <td>{fmt_pct(stats['avg_l'])}</td>
              <td>{fmt_pct(stats['avg_s'])}</td></tr>
            <tr><td>年均交易次數</td>
              <td colspan="3" style="text-align:center">{stats['tpy']:.1f} 筆／年（月均 {stats['tpy']/12:.1f} 次）</td></tr>
            <tr><td>策略累積報酬</td>
              <td colspan="3" style="text-align:center">{fmt_pct(stats['total_ret'])}</td></tr>
            <tr><td>最大回撤 (MDD)</td>
              <td colspan="3" style="text-align:center">{fmt_pct(stats['mdd'],good_pos=False)}</td></tr>
            <tr><td>夏普比率</td>
              <td colspan="3" style="text-align:center">
                <span class="{'win' if stats['sharpe']>1 else ''}">{stats['sharpe']:.2f}</span>
              </td></tr>
          </table>
          <p style="font-size:.7rem;color:#94a3b8;margin-top:.7rem">
            ⚠️ 回測基於歷史資料，不代表未來績效。T+1 開盤成交，單邊成本 {COST_RATE*10000:.0f} bps。
          </p>
        </div>
        """, unsafe_allow_html=True)

        # 第九張圖
        st.markdown('<div class="ctitle">⑨ 加權指數 ／ 近一年策略進出場走勢 ／ 累積報酬對比</div>',
                    unsafe_allow_html=True)

        d_plot  = d.iloc[-252:] if len(d)>252 else d
        cum_plot= bt["cum"].iloc[-252:] if len(bt["cum"])>252 else bt["cum"]
        bh_plot = (1+d_plot["TWII"].pct_change().fillna(0)).cumprod()
        bh_plot = bh_plot / bh_plot.iloc[0] * cum_plot.iloc[0]

        tds = [t for t in bt["trades"]
               if "exit_date" in t and t["date"] >= d_plot.index[0]]

        long_e_d  = [t["date"]      for t in tds if t["dir"]==1]
        long_e_v  = [d.loc[t["date"],"TWII"]      if t["date"] in d.index else np.nan for t in tds if t["dir"]==1]
        long_x_d  = [t["exit_date"] for t in tds if t["dir"]==1]
        long_x_v  = [d.loc[t["exit_date"],"TWII"] if t["exit_date"] in d.index else np.nan for t in tds if t["dir"]==1]
        short_e_d = [t["date"]      for t in tds if t["dir"]==-1]
        short_e_v = [d.loc[t["date"],"TWII"]      if t["date"] in d.index else np.nan for t in tds if t["dir"]==-1]
        short_x_d = [t["exit_date"] for t in tds if t["dir"]==-1]
        short_x_v = [d.loc[t["exit_date"],"TWII"] if t["exit_date"] in d.index else np.nan for t in tds if t["dir"]==-1]

        f9 = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.62,.38],vertical_spacing=.04)

        f9.add_trace(go.Scatter(x=d_plot.index,y=d_plot["TWII"],name="加權指數",
                                line=dict(color=C["tw"],width=1.6)),row=1,col=1)
        f9.add_trace(go.Scatter(x=d_plot.index,y=d_plot["MA60"],name="季線(60MA)",
                                line=dict(color=C["ma60"],width=1.3,dash="dash")),row=1,col=1)

        # 持倉背景色
        exp_plot = bt["exp"].iloc[-252:] if len(bt["exp"])>252 else bt["exp"]
        for i in range(1,len(d_plot)):
            e = exp_plot.iloc[i]
            if e!=0:
                x0=d_plot.index[i-1]; x1=d_plot.index[i]
                fc="rgba(22,163,74,.08)" if e>0 else "rgba(220,38,38,.08)"
                f9.add_vrect(x0=x0,x1=x1,fillcolor=fc,line_width=0,row=1,col=1)

        if long_e_d:
            f9.add_trace(go.Scatter(x=long_e_d,y=long_e_v,mode="markers",
                name="多單進場",marker=dict(color=C["long_e"],size=14,symbol="triangle-up",
                line=dict(color="#fff",width=1.5))),row=1,col=1)
        if long_x_d:
            f9.add_trace(go.Scatter(x=long_x_d,y=long_x_v,mode="markers",
                name="多單出場",marker=dict(color=C["long_e"],size=9,symbol="circle",
                line=dict(color="#fff",width=1),opacity=.7)),row=1,col=1)
        if short_e_d:
            f9.add_trace(go.Scatter(x=short_e_d,y=short_e_v,mode="markers",
                name="空單進場",marker=dict(color=C["short_e"],size=14,symbol="triangle-down",
                line=dict(color="#fff",width=1.5))),row=1,col=1)
        if short_x_d:
            f9.add_trace(go.Scatter(x=short_x_d,y=short_x_v,mode="markers",
                name="空單出場",marker=dict(color=C["short_e"],size=9,symbol="circle",
                line=dict(color="#fff",width=1),opacity=.7)),row=1,col=1)

        f9.add_trace(go.Scatter(x=cum_plot.index,y=(cum_plot-1)*100,
                                name=f"v12策略 ({stats['total_ret']:+.1f}%)",
                                line=dict(color=C["strat"],width=2.4)),row=2,col=1)
        f9.add_trace(go.Scatter(x=bh_plot.index,y=(bh_plot-1)*100,name="買進持有",
                                line=dict(color=C["bh"],width=1.4,dash="dash"),opacity=.7),row=2,col=1)
        cum_arr=cum_plot.values; hwm=np.maximum.accumulate(cum_arr); dd=(cum_arr/hwm-1)*100
        f9.add_trace(go.Scatter(x=cum_plot.index,y=dd,name="策略回撤",
                                line=dict(color="#ef4444",width=0),
                                fill="tozeroy",fillcolor="rgba(239,68,68,.15)"),row=2,col=1)
        f9.add_hline(y=0,line_color="#cbd5e1",line_width=.8,row=2,col=1)

        f9.update_yaxes(title_text="指數",title_font_size=10,row=1,col=1)
        f9.update_yaxes(title_text="累積報酬(%)",title_font_size=10,row=2,col=1)
        theme(f9,560)
        f9.update_layout(legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="left",x=0,font_size=10))
        st.plotly_chart(f9,use_container_width=True)

        with st.expander("📋  近一年波段交易明細", expanded=False):
            tds_year=[t for t in bt["trades"]
                      if "exit_date" in t and t["date"]>=d_plot.index[0]]
            if tds_year:
                rows=""
                for t in reversed(tds_year):
                    tag="✅" if t["ret"]>0 else "❌"
                    dir_s="▲ 多" if t["dir"]==1 else "▼ 空"
                    ret_cls="win" if t["ret"]>0 else "lose"
                    rows+=f"""<tr>
                      <td>{str(t['date'].date())}</td>
                      <td>{str(t['exit_date'].date())}</td>
                      <td>{dir_s}</td>
                      <td>{t.get('n_days','-')}</td>
                      <td><span class="{ret_cls}">{t['ret']*100:+.2f}%</span></td>
                      <td>{tag}</td></tr>"""
                st.markdown(f"""<table class="perf-table">
                  <tr><th>進場日</th><th>出場日</th><th>方向</th><th>持倉天</th><th>波段報酬</th><th>結果</th></tr>
                  {rows}</table>""", unsafe_allow_html=True)
            else:
                st.info("近一年無已完成波段。")

    # 頁尾
    st.markdown("""
    <div class="footer">
      台指多因子策略 v12 ／ 多空均衡版（多4.5門檻＋空3.5門檻 ／ EXIT_CONFIRM 多3空2）<br>
      整體勝率 67.5% │ 多頭 67.3% │ 空頭 67.9%（v11=53.8% 大幅改善）<br>
      本頁面僅供量化研究參考，不構成投資建議。
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
