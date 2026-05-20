"""
台指多因子量化戰情室 v11  —  Streamlit 完整版
修正項目：
  1. ADR 折溢價(%) 正確計算：(TSM_US × 匯率 / 5 / TSMC_TW − 1) × 100
  2. 外資 Z-score 單位一致（Z-score 本身不受單位影響，圖標改為億元）
  3. yfinance Ticker.history() 統一寫法，移除多餘 MultiIndex 處理
  4. 新增第九張圖：近一年回測進出場走勢 + 績效統計表
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ──────────────────────────────────────────────────────────────
# 頁面設定
# ──────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="台指多因子戰情室 v11", page_icon="📊")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+TC:wght@300;400;700&display=swap');

[data-testid="stAppViewContainer"]  { background:#0a0e1a; }
[data-testid="stHeader"]            { background:transparent; }
section.main > div                  { padding-top:.8rem; }
html,body,[class*="css"]            { font-family:"Noto Sans TC",sans-serif; color:#c8d6e8; }
code,.mono                          { font-family:"IBM Plex Mono",monospace; }

/* ── 頂部 banner ── */
.top-banner{
  background:linear-gradient(135deg,#0d1f3c,#0a1628 50%,#0d1f3c);
  border:1px solid #1e3a5f; border-radius:12px;
  padding:1.1rem 2rem; margin-bottom:1.2rem;
  display:flex; align-items:center; justify-content:space-between;
}
.top-banner h1{margin:0;font-size:1.45rem;font-weight:700;color:#e2eeff;
  text-shadow:0 0 20px rgba(59,130,246,.4);letter-spacing:1px;}
.top-banner .ts{font-size:.78rem;color:#4a6fa5;font-family:"IBM Plex Mono";}

/* ── 訊號卡片 ── */
.sig-card{border-radius:12px;padding:1rem 1.3rem;border:1px solid;margin-bottom:.6rem;}
.sig-long {background:rgba(34,197,94,.08); border-color:#22c55e;}
.sig-short{background:rgba(239,68,68,.08);  border-color:#ef4444;}
.sig-idle {background:rgba(59,130,246,.06); border-color:#2a4a7f;}
.sig-card h2{margin:0 0 .3rem;font-size:1.05rem;}
.sig-card p {margin:0;font-size:.85rem;color:#8899bb;}

/* ── badge ── */
.badge{display:inline-block;padding:3px 12px;border-radius:20px;
  font-size:.72rem;font-weight:600;font-family:"IBM Plex Mono";}
.badge-long {background:#14532d;color:#4ade80;border:1px solid #22c55e;}
.badge-short{background:#4c0519;color:#f87171;border:1px solid #ef4444;}
.badge-off  {background:#1e293b;color:#64748b;border:1px solid #334155;}

/* ── 進度條 ── */
.bar-wrap{margin:.35rem 0;}
.bar-row{display:flex;align-items:center;gap:8px;margin:3px 0;font-size:.78rem;}
.bar-label{width:96px;text-align:right;color:#8899bb;flex-shrink:0;}
.bar-bg{flex:1;background:#1a2540;border-radius:4px;height:10px;}
.bar-l{height:10px;border-radius:4px;background:linear-gradient(90deg,#1d4ed8,#22c55e);}
.bar-s{height:10px;border-radius:4px;background:linear-gradient(90deg,#7c2020,#ef4444);}
.bar-val{width:30px;text-align:right;font-family:"IBM Plex Mono";font-size:.73rem;}

/* ── KPI ── */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:1rem;}
.kpi-card{background:#0d1424;border:1px solid #1e3356;border-radius:10px;padding:.85rem 1rem;}
.kpi-card .kl{font-size:.7rem;color:#4a6fa5;text-transform:uppercase;letter-spacing:.5px;}
.kpi-card .kv{font-size:1.45rem;font-weight:700;font-family:"IBM Plex Mono";margin-top:3px;}
.kpi-card .ks{font-size:.7rem;color:#4a6fa5;margin-top:2px;}
.pos{color:#22c55e;} .neg{color:#ef4444;} .neu{color:#93c5fd;}

/* ── 績效表格 ── */
.perf-table{width:100%;border-collapse:collapse;font-size:.82rem;font-family:"IBM Plex Mono";}
.perf-table th{background:#0d1f3c;color:#7ea8d8;padding:7px 12px;text-align:center;
  border:1px solid #1e3356;font-weight:600;}
.perf-table td{padding:6px 12px;text-align:center;border:1px solid #1a2540;color:#c8d6e8;}
.perf-table tr:nth-child(even) td{background:rgba(13,31,60,.4);}
.win  {color:#22c55e;font-weight:600;}
.lose {color:#ef4444;}

/* ── section title ── */
.sect{font-size:.75rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;
  color:#3b82f6;border-left:3px solid #3b82f6;padding-left:10px;margin:1.4rem 0 .7rem;}

/* ── 圖表標題 ── */
.ctitle{font-size:.78rem;color:#7ea8d8;letter-spacing:1px;text-transform:uppercase;margin-bottom:.4rem;}

/* streamlit 元件覆蓋 */
[data-testid="stButton"] button{
  background:#0d2d5e;border:1px solid #2563eb;color:#93c5fd;
  border-radius:8px;font-size:.8rem;}
[data-testid="stButton"] button:hover{background:#1d4ed8;color:#fff;}
div[data-testid="metric-container"]{
  background:#0d1424;border:1px solid #1e3356;border-radius:10px;padding:.6rem .8rem;}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 常數
# ──────────────────────────────────────────────────────────────
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoia3VvODYwMSIsImVtYWlsIjoic29sZGllcjg2MTAwQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9._5JgdrkR3h3ogK7zaxW1t7R4UxB0rbR-_aZUm3z0HLQ"
ENTRY_THRESH  = 4.5
EXIT_CONFIRM  = 3
COST_RATE     = 0.0005
PLOT_H_TALL   = 440
PLOT_H_MED    = 380
PLOT_H_SM     = 340

PLOT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(13,20,36,.6)",
    font=dict(family="IBM Plex Mono,Noto Sans TC", color="#8899bb", size=11),
    legend=dict(bgcolor="rgba(0,0,0,0)", font_size=10),
    margin=dict(l=10,r=10,t=30,b=10),
    hovermode="x unified",
    xaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540",
               showspikes=True, spikecolor="#3b82f6", spikethickness=1),
    yaxis=dict(gridcolor="#1a2540", zerolinecolor="#1a2540"),
)

def theme(fig, h=PLOT_H_TALL):
    kw = dict(PLOT_BASE); kw["height"] = h
    fig.update_layout(**kw)
    for k in fig.layout:
        if k.startswith(("xaxis","yaxis")):
            fig.layout[k].update(gridcolor="#1a2540", zerolinecolor="#253555")
    return fig

C = dict(
    tw="#7dd3fc", ma20="#f59e0b", ma60="#f97316",
    sox="#818cf8", sox20="#fbbf24", sox60="#f97316",
    tsmc="#fb7185", ts_ma="#f97316",
    ef="#c084fc", ef20="#a78bfa", ef60="#6d28d9",
    fi_pos="#22c55e", fi_neg="#ef4444",
    adr="#facc15", adr_ma="#94a3b8",
    rsi="#a78bfa",
    bb_up="#ef4444", bb_dn="#22c55e", bb_mid="#f59e0b",
    long_e="#22c55e", short_e="#ef4444",
    strat="#38bdf8", bh="#64748b",
)

# ──────────────────────────────────────────────────────────────
# 1. 資料獲取
# ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_yahoo() -> pd.DataFrame:
    end   = datetime.now()
    start = end - timedelta(days=420)   # 多抓確保120MA樣本充足

    specs = {
        "TWII":    "^TWII",
        "TWII_O":  "^TWII",   # 開盤價（用同一ticker）
        "SOX":     "^SOX",
        "TSMC_TW": "2330.TW",
        "TSM_US":  "TSM",
        "ELEC":    "0053.TW",
        "FIN":     "0055.TW",
        "USDTWD":  "TWD=X",
    }

    frames = {}
    for name, ticker in specs.items():
        if name == "TWII_O":
            continue   # 從 TWII 的 Open 欄拿
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

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames.values(), axis=1).sort_index().ffill()

    # ── ADR 折溢價(%) 正確計算 ──────────────────────────────
    # 公式：TSM_US（美元）× 匯率（TWD/USD）÷ 5股 ÷ TSMC本地價 − 1，×100
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
        # 原始單位為元，÷1e8 = 億元（Z-score 不受單位影響，圖表顯示億元）
        f["FI_Net"] = (f["buy"].astype(float) - f["sell"].astype(float)) / 1e8
        return f.groupby("Date")["FI_Net"].sum(), True
    except Exception:
        return pd.Series(dtype=float), False


# ──────────────────────────────────────────────────────────────
# 2. 因子計算（全序列，供即時看板 + 回測共用）
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


def compute_scores_gates(d: pd.DataFrame) -> tuple:
    """對整個 DataFrame 逐行計算得分與門票（供回測使用）"""
    n = len(d)

    # ── 因子序列 ──
    fL1  = ((d["TWII"]>d["MA60"]) & (d["斜率"]>0.1)).astype(float)
    fL2  = (d["EF"]>d["EF_MA20"]).astype(float)
    fL3  = (d["FI_Z"]>1.2).astype(float)
    fL4  = ((d["SOX"]>d["SOX_MA20"]) & (d["SOX"]>d["SOX_MA60"])).astype(float)
    fL5  = (d["ADR_Z"]>0.8).astype(float)
    fL6  = (d["TSMC_TW"]>d["TS_MA20"]).astype(float)
    fL7  = (d["TSMC_Vol"]>1.5*d["TS_VolMA"]).astype(float)
    fL8  = (d["乖離"]<-8).astype(float)
    fL9  = (d["RSI"]<40).astype(float)
    fL10 = (d["FI_5MA"]>0).astype(float)
    fL11 = (d["TWII"]<d["BB下"]).astype(float)

    fS1  = ((d["TWII"]<d["MA60"]) & (d["斜率"]<-0.1)).astype(float)
    fS2  = (d["EF"]<d["EF_MA20"]).astype(float)
    fS3  = (d["FI_Z"]<-1.5).astype(float)
    fS4  = ((d["SOX"]<d["SOX_MA20"]) & (d["SOX"]<d["SOX_MA60"])).astype(float)
    fS5  = (d["ADR_Z"]<-1.2).astype(float)
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
# 3. 回測引擎（完整 v11 狀態機，T+1 開盤）
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
    onight = np.zeros(N)
    onight[1:] = np.where(close[:-1]>0, open_[1:]/close[:-1]-1, 0)
    daily  = np.zeros(N)
    daily[1:] = np.where(close[:-1]>0, close[1:]/close[:-1]-1, 0)

    pos = np.zeros(N); cur = 0.0; ec = 0
    for i in range(N):
        if cur == 0:
            if ls[i] >= ENTRY_THRESH and gL[i]: cur = 1.
            elif ss[i] >= ENTRY_THRESH and gS[i]: cur = -1.
        else:
            if cur == 1:  esig = ls[i]<2.5 or not gL[i] or close[i]<ma60[i]
            else:         esig = ss[i]<2.5 or not gS[i] or close[i]>ma60[i]
            ec = ec+1 if esig else 0
            if ec >= EXIT_CONFIRM: cur = 0.; ec = 0
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

    # ── 波段統計 ──
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
# 4. 即時訊號（最新一天）
# ──────────────────────────────────────────────────────────────
def latest_signal(d: pd.DataFrame):
    lt = d.iloc[-1]
    def s(cond, w): return w if cond else 0.0

    L = {}
    L["F1 趨勢斜率"]   = s((lt["TWII"]>lt["MA60"]) and (lt["斜率"]>0.1),             1.0)
    L["F2 電金比MA"]   = s(lt["EF"]>lt["EF_MA20"],                                    1.0)
    L["F3 外資Z"]      = s(lt["FI_Z"]>1.2,                                            2.0)
    L["F4 費半雙均"]   = s((lt["SOX"]>lt["SOX_MA20"]) and (lt["SOX"]>lt["SOX_MA60"]),2.0)
    L["F5 ADR溢價Z"]   = s(lt["ADR_Z"]>0.8,                                           2.0)
    L["F6 台積電MA"]   = s(lt["TSMC_TW"]>lt["TS_MA20"],                               1.0)
    L["F7 爆量"]       = s(lt["TSMC_Vol"]>1.5*lt["TS_VolMA"],                          0.5)
    L["F8 超賣乖離"]   = s(lt["乖離"]<-8,                                              1.0)
    L["F9 RSI低檔"]    = s(lt["RSI"]<40,                                               1.0)
    L["F10 外資流入"]  = s(lt["FI_5MA"]>0,                                             1.0)
    L["F11 BB下軌"]    = s(lt["TWII"]<lt["BB下"],                                      0.5)

    S = {}
    S["F1 趨勢斜率"]   = s((lt["TWII"]<lt["MA60"]) and (lt["斜率"]<-0.1),             1.5)
    S["F2 電金比MA"]   = s(lt["EF"]<lt["EF_MA20"],                                    1.0)
    S["F3 外資Z"]      = s(lt["FI_Z"]<-1.5,                                           2.0)
    S["F4 費半雙均"]   = s((lt["SOX"]<lt["SOX_MA20"]) and (lt["SOX"]<lt["SOX_MA60"]),2.0)
    S["F5 ADR折價Z"]   = s(lt["ADR_Z"]<-1.2,                                          2.0)
    S["F6 台積電MA"]   = s(lt["TSMC_TW"]<lt["TS_MA20"],                               1.0)
    S["F7 爆量"]       = s(lt["TSMC_Vol"]>1.5*lt["TS_VolMA"],                          0.5)
    S["F8 超買乖離"]   = s(lt["乖離"]>8,                                               1.0)
    S["F9 RSI高檔"]    = s(lt["RSI"]>65,                                               1.0)
    S["F10 外資流出"]  = s(lt["FI_5MA"]<0,                                             1.0)
    S["F11 BB上軌"]    = s(lt["TWII"]>lt["BB上"],                                      0.5)

    ls = sum(L.values()); ss = sum(S.values())
    gL = ((lt["SOX"]>lt["SOX_MA20"] and lt["SOX"]>lt["SOX_MA60"]) and
          (lt["ADR_Z"]>0.8 or lt["FI_Z"]>1.2) and (lt["EF"]>lt["EF_MA60"]))
    gS = ((lt["SOX"]<lt["SOX_MA20"] and lt["SOX"]<lt["SOX_MA60"]) and
          (lt["ADR_Z"]<-1.2 or lt["FI_Z"]<-1.5) and (lt["EF"]<lt["EF_MA60"]))
    return ls, ss, gL, gS, L, S, lt


# ──────────────────────────────────────────────────────────────
# 5. 主畫面
# ──────────────────────────────────────────────────────────────
def main():
    # ── Banner ───────────────────────────────────────────────
    c_hd, c_btn = st.columns([5,1])
    with c_hd:
        st.markdown(f"""
        <div class="top-banner">
          <h1>📊 台指多因子量化戰情室 <span style="color:#3b82f6;font-size:.9rem">v11</span></h1>
          <span class="ts">TAIEX Multi-Factor Signal Dashboard ／ {datetime.now():%Y-%m-%d %H:%M}</span>
        </div>""", unsafe_allow_html=True)
    with c_btn:
        st.write("")
        if st.button("⟳ 同步數據", use_container_width=True):
            st.cache_data.clear(); st.rerun()

    # ── 資料載入 ──────────────────────────────────────────────
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
    # 區塊A：訊號燈
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 策略訊號燈</div>', unsafe_allow_html=True)
    cA1, cA2, cA3 = st.columns([1.8,1.8,2.4])

    # 門票
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
          <p style="margin-top:8px">{txt}</p></div>""", unsafe_allow_html=True)

    # 得分進度條
    with cA2:
        lp = min(ls/14*100,100); sp = min(ss/14.5*100,100); tp = ENTRY_THRESH/14*100
        st.markdown(f"""<div class="sig-card sig-idle">
          <h2>11因子共振得分</h2>
          <div style="margin-top:8px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
              <span style="width:48px;font-size:.78rem;color:#22c55e">多頭</span>
              <div style="flex:1;background:#1a2540;border-radius:6px;height:13px;position:relative">
                <div style="width:{lp:.0f}%;background:linear-gradient(90deg,#1d4ed8,#22c55e);height:13px;border-radius:6px"></div>
                <div style="position:absolute;left:{tp:.0f}%;top:-4px;width:2px;height:21px;background:#f59e0b"></div>
              </div>
              <span style="font-family:'IBM Plex Mono';color:#22c55e;width:34px;text-align:right">{ls:.1f}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="width:48px;font-size:.78rem;color:#ef4444">空頭</span>
              <div style="flex:1;background:#1a2540;border-radius:6px;height:13px;position:relative">
                <div style="width:{sp:.0f}%;background:linear-gradient(90deg,#7c2020,#ef4444);height:13px;border-radius:6px"></div>
                <div style="position:absolute;left:{tp:.0f}%;top:-4px;width:2px;height:21px;background:#f59e0b"></div>
              </div>
              <span style="font-family:'IBM Plex Mono';color:#ef4444;width:34px;text-align:right">{ss:.1f}</span>
            </div>
            <p style="font-size:.7rem;color:#4a6fa5;margin-top:6px">▲ 橘線 = 進場門檻 {ENTRY_THRESH}分（滿分 14 分）</p>
          </div></div>""", unsafe_allow_html=True)

    # 綜合裁決
    with cA3:
        if gL and ls >= ENTRY_THRESH:
            ttl="🔥 強烈做多訊號"; cls="sig-long"
            desc=f"三維度門票達成 ＋ 多頭共振 <b>{ls:.1f}</b> 分，超越門檻<br>T+1 開盤掛多單，EXIT_CONFIRM=3 日確認出場"
            sub="歷史回測：整體 65.8% ｜ 多頭 65.4%"
        elif gS and ss >= ENTRY_THRESH:
            ttl="⚠️ 強烈做空訊號"; cls="sig-short"
            desc=f"三維度門票達成 ＋ 空頭共振 <b>{ss:.1f}</b> 分，超越門檻<br>T+1 開盤掛空單，EXIT_CONFIRM=3 日確認出場"
            sub="歷史回測：整體 65.8% ｜ 空頭 66.7%"
        elif gL:
            ttl="🟡 多頭門票已開，等待共振"; cls="sig-idle"
            desc=f"門票✅，但共振得分 {ls:.1f} 尚未達 {ENTRY_THRESH}，繼續觀望"
            sub="等待更多因子點燈"
        elif gS:
            ttl="🟡 空頭門票已開，等待共振"; cls="sig-idle"
            desc=f"門票✅，但共振得分 {ss:.1f} 尚未達 {ENTRY_THRESH}，繼續觀望"
            sub="等待更多因子點燈"
        else:
            ttl="⚖️ 空手觀望"; cls="sig-idle"
            desc="大環境三維度門票未達，過濾器攔截<br>等待費半趨勢、資金流向明確"
            sub="v11 門票 + 分數雙重確認才進場"
        st.markdown(f"""<div class="sig-card {cls}" style="height:100%">
          <h2>{ttl}</h2>
          <p style="color:#c8d6e8;margin:8px 0">{desc}</p>
          <p style="font-size:.73rem;color:#4a6fa5">{sub}</p>
          </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # 區塊B：KPI 快覽
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
    # 區塊C：因子點燈看板
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 因子點燈看板</div>', unsafe_allow_html=True)
    cL, cS = st.columns(2)

    def bar_rows(fdict, is_long, mx):
        rows = ""
        for k,v in fdict.items():
            pct = min(v/mx*100,100)
            cls = "bar-l" if is_long else "bar-s"
            col = "#22c55e" if is_long else "#ef4444"
            dot = "🟢" if v>0 else "⬜"
            rows += f"""<div class="bar-row">
              <span class="bar-label">{dot} {k}</span>
              <div class="bar-bg"><div class="{cls}" style="width:{pct:.0f}%"></div></div>
              <span class="bar-val" style="color:{col}">{v:.1f}</span></div>"""
        return rows

    with cL:
        st.markdown(f"""<div class="sig-card sig-idle">
          <h2 style="color:#22c55e">多頭因子
            <span style="font-family:'IBM Plex Mono';font-size:1rem">{ls:.1f}</span>
            <span style="font-size:.75rem;color:#4a6fa5"> / {ENTRY_THRESH} 門檻</span></h2>
          <div class="bar-wrap">{bar_rows(Lf,True,14)}</div></div>""",
          unsafe_allow_html=True)
    with cS:
        st.markdown(f"""<div class="sig-card sig-idle">
          <h2 style="color:#ef4444">空頭因子
            <span style="font-family:'IBM Plex Mono';font-size:1rem">{ss:.1f}</span>
            <span style="font-size:.75rem;color:#4a6fa5"> / {ENTRY_THRESH} 門檻</span></h2>
          <div class="bar-wrap">{bar_rows(Sf,False,14.5)}</div></div>""",
          unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # 區塊D：八大技術圖表
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 技術指標圖表</div>', unsafe_allow_html=True)

    # ① 大盤 + 季線 + 乖離
    st.markdown('<div class="ctitle">① 台灣加權指數 ／ 季線(60MA) ／ 季線乖離率</div>', unsafe_allow_html=True)
    f1 = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.7,.3],vertical_spacing=.04)
    f1.add_trace(go.Scatter(x=d.index,y=d["TWII"],  name="加權指數",line=dict(color=C["tw"],width=1.5)),row=1,col=1)
    f1.add_trace(go.Scatter(x=d.index,y=d["MA20"],  name="月線(20)",line=dict(color=C["ma20"],width=1,dash="dot")),row=1,col=1)
    f1.add_trace(go.Scatter(x=d.index,y=d["MA60"],  name="季線(60)",line=dict(color=C["ma60"],width=1.6,dash="dash")),row=1,col=1)
    bc=["#ef4444" if b>8 else "#22c55e" if b<-8 else "#334466" for b in d["乖離"]]
    f1.add_trace(go.Bar(x=d.index,y=d["乖離"],name="乖離率(%)",marker_color=bc,opacity=.85),row=2,col=1)
    f1.add_hline(y=8, line_dash="dot",line_color="#ef4444",line_width=1,row=2,col=1,annotation_text="超買+8%",annotation_font_size=9)
    f1.add_hline(y=-8,line_dash="dot",line_color="#22c55e",line_width=1,row=2,col=1,annotation_text="超賣-8%",annotation_font_size=9)
    f1.add_hline(y=0, line_color="#334466",line_width=.8,row=2,col=1)
    theme(f1,PLOT_H_TALL); st.plotly_chart(f1,use_container_width=True)

    # ② 費半  ③ 電金比（並排）
    c2,c3 = st.columns(2)
    with c2:
        st.markdown('<div class="ctitle">② 費城半導體（大環境門票①）</div>', unsafe_allow_html=True)
        f2=go.Figure()
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX"],      name="費半",line=dict(color=C["sox"],width=1.5)))
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA20"], name="月線",line=dict(color=C["sox20"],width=1,dash="dot")))
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA60"], name="季線",line=dict(color=C["sox60"],width=1.5,dash="dash")))
        above=[y if y>m else None for y,m in zip(d["SOX"],d["SOX_MA60"])]
        f2.add_trace(go.Scatter(x=d.index,y=d["SOX_MA60"],showlegend=False,line=dict(width=0)))
        f2.add_trace(go.Scatter(x=d.index,y=above,fill="tonexty",fillcolor="rgba(129,140,248,.12)",line=dict(width=0),showlegend=False))
        theme(f2,PLOT_H_SM); st.plotly_chart(f2,use_container_width=True)
    with c3:
        st.markdown('<div class="ctitle">③ 電金比 — 資金風格輪動（大環境門票③）</div>', unsafe_allow_html=True)
        f3=go.Figure()
        f3.add_trace(go.Scatter(x=d.index,y=d["EF"],      name="電金比",line=dict(color=C["ef"],width=1.5)))
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA20"], name="月線",  line=dict(color=C["ef20"],width=1,dash="dot")))
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA60"], name="季線",  line=dict(color=C["ef60"],width=1.5,dash="dash")))
        ef_hi=[y if y>m else None for y,m in zip(d["EF"],d["EF_MA60"])]
        f3.add_trace(go.Scatter(x=d.index,y=d["EF_MA60"],showlegend=False,line=dict(width=0)))
        f3.add_trace(go.Scatter(x=d.index,y=ef_hi,fill="tonexty",fillcolor="rgba(192,132,252,.1)",line=dict(width=0),showlegend=False))
        theme(f3,PLOT_H_SM); st.plotly_chart(f3,use_container_width=True)

    # ④ 台積電 + 量能
    st.markdown('<div class="ctitle">④ 台積電現貨 ／ 月線 ／ 爆量偵測</div>', unsafe_allow_html=True)
    f4=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.68,.32],vertical_spacing=.04)
    f4.add_trace(go.Scatter(x=d.index,y=d["TSMC_TW"],name="台積電(TW)",line=dict(color=C["tsmc"],width=1.5)),row=1,col=1)
    f4.add_trace(go.Scatter(x=d.index,y=d["TS_MA20"],name="月線(20)",  line=dict(color=C["ts_ma"],width=1,dash="dot")),row=1,col=1)
    vc=["#ef4444" if v>1.5*m else "#2a4060" for v,m in zip(d["TSMC_Vol"],d["TS_VolMA"])]
    f4.add_trace(go.Bar(x=d.index,y=d["TSMC_Vol"],name="成交量（紅=爆量）",marker_color=vc,opacity=.9),row=2,col=1)
    f4.add_trace(go.Scatter(x=d.index,y=d["TS_VolMA"]*1.5,name="爆量閾(×1.5)",
                            line=dict(color="#f59e0b",width=1,dash="dot")),row=2,col=1)
    theme(f4,420); st.plotly_chart(f4,use_container_width=True)

    # ⑤ 外資  ⑥ ADR（並排）
    c5,c6=st.columns(2)
    with c5:
        st.markdown('<div class="ctitle">⑤ 外資買賣超 ／ Z-Score（大環境門票② 之一）</div>', unsafe_allow_html=True)
        if has_fi and "FI_Net" in d.columns and d["FI_Net"].abs().sum()>0:
            f5=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.55,.45],vertical_spacing=.04)
            fc=[C["fi_pos"] if v>=0 else C["fi_neg"] for v in d["FI_Net"]]
            f5.add_trace(go.Bar(x=d.index,y=d["FI_Net"],name="外資淨買賣(億)",marker_color=fc,opacity=.85),row=1,col=1)
            f5.add_trace(go.Scatter(x=d.index,y=d["FI_Z"],name="外資Z-score",line=dict(color="#60a5fa",width=1.5)),row=2,col=1)
            for yv,col,lbl in [(1.2,"#22c55e","多頭+1.2σ"),(-1.5,"#ef4444","空頭-1.5σ")]:
                f5.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1,row=2,col=1,
                             annotation_text=lbl,annotation_font_size=9)
            f5.add_hline(y=0,line_color="#334466",line_width=.8,row=2,col=1)
            theme(f5,PLOT_H_MED); st.plotly_chart(f5,use_container_width=True)
        else:
            st.info("ℹ️ FinMind 外資資料暫時無法取得，Z-score 以 0 代入。", icon="🔌")

    with c6:
        st.markdown('<div class="ctitle">⑥ 台積電ADR折溢價(%) ／ Z-Score（大環境門票② 之一）</div>', unsafe_allow_html=True)
        f6=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.55,.45],vertical_spacing=.04)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_Premium"],name="ADR折溢價(%)",line=dict(color=C["adr"],width=1.5)),row=1,col=1)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_MA"],     name="120MA",        line=dict(color=C["adr_ma"],width=1,dash="dash")),row=1,col=1)
        f6.add_hline(y=0,line_color="#334466",line_width=.8,row=1,col=1)
        f6.add_trace(go.Scatter(x=d.index,y=d["ADR_Z"],name="ADR Z-score",line=dict(color="#fbbf24",width=1.5)),row=2,col=1)
        for yv,col,lbl in [(0.8,"#22c55e","多頭+0.8σ"),(-1.2,"#ef4444","空頭-1.2σ")]:
            f6.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1,row=2,col=1,
                         annotation_text=lbl,annotation_font_size=9)
        f6.add_hline(y=0,line_color="#334466",line_width=.8,row=2,col=1)
        theme(f6,PLOT_H_MED); st.plotly_chart(f6,use_container_width=True)

    # ⑦ RSI
    st.markdown('<div class="ctitle">⑦ 台股加權指數 ／ RSI(14) 動能指標</div>', unsafe_allow_html=True)
    f7=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.65,.35],vertical_spacing=.04)
    f7.add_trace(go.Scatter(x=d.index,y=d["TWII"],name="加權指數",line=dict(color=C["tw"],width=1.5)),row=1,col=1)
    f7.add_trace(go.Scatter(x=d.index,y=d["MA60"],name="季線",    line=dict(color=C["ma60"],width=1.2,dash="dash")),row=1,col=1)
    f7.add_trace(go.Scatter(x=d.index,y=d["RSI"],name="RSI(14)",  line=dict(color=C["rsi"],width=1.5)),row=2,col=1)
    f7.add_hrect(y0=65,y1=100,fillcolor="rgba(239,68,68,.06)",line_width=0,row=2,col=1)
    f7.add_hrect(y0=0, y1=40, fillcolor="rgba(34,197,94,.06)", line_width=0,row=2,col=1)
    for yv,col,lbl in [(65,"#ef4444","過熱65"),(40,"#22c55e","低檔40")]:
        f7.add_hline(y=yv,line_dash="dot",line_color=col,line_width=1,row=2,col=1,
                     annotation_text=lbl,annotation_font_size=9)
    theme(f7,420); st.plotly_chart(f7,use_container_width=True)

    # ⑧ 布林通道
    st.markdown('<div class="ctitle">⑧ 台股加權指數 ／ 布林通道 Bollinger Bands(20, 2σ)</div>', unsafe_allow_html=True)
    f8=go.Figure()
    f8.add_trace(go.Scatter(x=d.index,y=d["BB上"],name="BB上軌",line=dict(color=C["bb_up"],width=1,dash="dot")))
    f8.add_trace(go.Scatter(x=d.index,y=d["BB下"],name="BB下軌",
                            line=dict(color=C["bb_dn"],width=1,dash="dot"),
                            fill="tonexty",fillcolor="rgba(100,100,120,.08)"))
    f8.add_trace(go.Scatter(x=d.index,y=d["MA20"], name="中線(20MA)",line=dict(color=C["bb_mid"],width=1.2)))
    f8.add_trace(go.Scatter(x=d.index,y=d["TWII"], name="加權指數",  line=dict(color=C["tw"],width=1.8)))
    bhi=d[d["TWII"]>d["BB上"]]; blo=d[d["TWII"]<d["BB下"]]
    if not bhi.empty:
        f8.add_trace(go.Scatter(x=bhi.index,y=bhi["TWII"],mode="markers",
                                marker=dict(color="#ef4444",size=7,symbol="circle"),name="突破上軌"))
    if not blo.empty:
        f8.add_trace(go.Scatter(x=blo.index,y=blo["TWII"],mode="markers",
                                marker=dict(color="#22c55e",size=7,symbol="circle"),name="突破下軌"))
    theme(f8,420); st.plotly_chart(f8,use_container_width=True)

    # ════════════════════════════════════════════════════════
    # 區塊E：回測圖 + 績效統計（新增第九張圖）
    # ════════════════════════════════════════════════════════
    st.markdown('<div class="sect">✦ 策略回測進出場分析（近一年）</div>', unsafe_allow_html=True)

    if bt is None:
        st.warning("回測資料不足（需要開盤價與足夠歷史），無法產生回測圖。")
    else:
        stats = bt["stats"]

        # ── 績效統計表（HTML表格） ─────────────────────────
        def fmt_pct(v, good_pos=True):
            cls = "win" if (v>0)==good_pos else "lose"
            return f'<span class="{cls}">{v:+.2f}%</span>'
        def fmt_wr(v):
            cls = "win" if v>=60 else ("lose" if v<50 else "")
            return f'<span class="{cls}">{v:.1f}%</span>'

        st.markdown(f"""
        <div style="background:#0d1424;border:1px solid #1e3356;border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:1rem">
          <div style="font-size:.78rem;color:#7ea8d8;letter-spacing:1px;text-transform:uppercase;margin-bottom:.8rem">策略績效統計表（全部可用資料）</div>
          <table class="perf-table">
            <tr>
              <th>項目</th><th>整體</th><th>做多</th><th>做空</th>
            </tr>
            <tr>
              <td>交易筆數</td>
              <td>{stats['n']}</td>
              <td>{stats['n_l']}</td>
              <td>{stats['n_s']}</td>
            </tr>
            <tr>
              <td>勝率</td>
              <td>{fmt_wr(stats['wr'])}</td>
              <td>{fmt_wr(stats['wrl'])}</td>
              <td>{fmt_wr(stats['wrs'])}</td>
            </tr>
            <tr>
              <td>平均波段報酬</td>
              <td>—</td>
              <td>{fmt_pct(stats['avg_l'])}</td>
              <td>{fmt_pct(stats['avg_s'])}</td>
            </tr>
            <tr>
              <td>年均交易次數</td>
              <td colspan="3" style="text-align:center">{stats['tpy']:.1f} 筆／年（月均 {stats['tpy']/12:.1f} 次）</td>
            </tr>
            <tr>
              <td>策略累積報酬</td>
              <td colspan="3" style="text-align:center">{fmt_pct(stats['total_ret'])}</td>
            </tr>
            <tr>
              <td>最大回撤 (MDD)</td>
              <td colspan="3" style="text-align:center">{fmt_pct(stats['mdd'],good_pos=False)}</td>
            </tr>
            <tr>
              <td>夏普比率</td>
              <td colspan="3" style="text-align:center">
                <span class="{'win' if stats['sharpe']>1 else ''}">{stats['sharpe']:.2f}</span>
              </td>
            </tr>
          </table>
          <p style="font-size:.68rem;color:#2a4a7f;margin-top:.6rem">
            ⚠️ 回測基於歷史資料，不代表未來績效。T+1 開盤成交，單邊成本 {COST_RATE*10000:.0f} bps。
          </p>
        </div>
        """, unsafe_allow_html=True)

        # ── 第九張圖：進出場走勢圖 ────────────────────────
        st.markdown('<div class="ctitle">⑨ 加權指數 ／ 近一年策略進出場走勢 ／ 累積報酬對比</div>',
                    unsafe_allow_html=True)

        # 取最近252交易日顯示
        d_plot  = d.iloc[-252:] if len(d)>252 else d
        cum_plot= bt["cum"].iloc[-252:] if len(bt["cum"])>252 else bt["cum"]
        bh_plot = ((1+d_plot["TWII"].pct_change().fillna(0)).cumprod())
        # 對齊買進持有基準到策略起始點
        bh_plot = bh_plot / bh_plot.iloc[0] * cum_plot.iloc[0]

        # 近一年的進出場
        tds = [t for t in bt["trades"]
               if "exit_date" in t and t["date"] >= d_plot.index[0]]
        long_e_dates  = [t["date"]      for t in tds if t["dir"]==1]
        long_e_vals   = [d.loc[t["date"],"TWII"]      if t["date"] in d.index else np.nan for t in tds if t["dir"]==1]
        long_x_dates  = [t["exit_date"] for t in tds if t["dir"]==1]
        long_x_vals   = [d.loc[t["exit_date"],"TWII"] if t["exit_date"] in d.index else np.nan for t in tds if t["dir"]==1]
        short_e_dates = [t["date"]      for t in tds if t["dir"]==-1]
        short_e_vals  = [d.loc[t["date"],"TWII"]      if t["date"] in d.index else np.nan for t in tds if t["dir"]==-1]
        short_x_dates = [t["exit_date"] for t in tds if t["dir"]==-1]
        short_x_vals  = [d.loc[t["exit_date"],"TWII"] if t["exit_date"] in d.index else np.nan for t in tds if t["dir"]==-1]

        f9 = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.62, 0.38], vertical_spacing=0.04,
            subplot_titles=["", ""]
        )

        # 走勢
        f9.add_trace(go.Scatter(x=d_plot.index,y=d_plot["TWII"],name="加權指數",
                                line=dict(color=C["tw"],width=1.4),opacity=.85),row=1,col=1)
        f9.add_trace(go.Scatter(x=d_plot.index,y=d_plot["MA60"],name="季線(60MA)",
                                line=dict(color=C["ma60"],width=1.3,dash="dash")),row=1,col=1)

        # 持倉背景色
        exp_plot = bt["exp"].iloc[-252:] if len(bt["exp"])>252 else bt["exp"]
        for i in range(1,len(d_plot)):
            e = exp_plot.iloc[i]
            if e!=0:
                x0=d_plot.index[i-1]; x1=d_plot.index[i]
                fc="rgba(34,197,94,.07)" if e>0 else "rgba(239,68,68,.07)"
                f9.add_vrect(x0=x0,x1=x1,fillcolor=fc,line_width=0,row=1,col=1)

        # 進出場標記
        if long_e_dates:
            f9.add_trace(go.Scatter(x=long_e_dates,y=long_e_vals,mode="markers",
                name="多單進場",marker=dict(color=C["long_e"],size=13,symbol="triangle-up",
                line=dict(color="#fff",width=1.2))),row=1,col=1)
        if long_x_dates:
            f9.add_trace(go.Scatter(x=long_x_dates,y=long_x_vals,mode="markers",
                name="多單出場",marker=dict(color=C["long_e"],size=9,symbol="circle",
                line=dict(color="#fff",width=1),opacity=.8)),row=1,col=1)
        if short_e_dates:
            f9.add_trace(go.Scatter(x=short_e_dates,y=short_e_vals,mode="markers",
                name="空單進場",marker=dict(color=C["short_e"],size=13,symbol="triangle-down",
                line=dict(color="#fff",width=1.2))),row=1,col=1)
        if short_x_dates:
            f9.add_trace(go.Scatter(x=short_x_dates,y=short_x_vals,mode="markers",
                name="空單出場",marker=dict(color=C["short_e"],size=9,symbol="circle",
                line=dict(color="#fff",width=1),opacity=.8)),row=1,col=1)

        # 累積報酬
        f9.add_trace(go.Scatter(x=cum_plot.index,y=(cum_plot-1)*100,name=f"v11策略 ({stats['total_ret']:+.1f}%)",
                                line=dict(color=C["strat"],width=2.2)),row=2,col=1)
        f9.add_trace(go.Scatter(x=bh_plot.index,y=(bh_plot-1)*100,name="買進持有",
                                line=dict(color=C["bh"],width=1.4,dash="dash"),opacity=.7),row=2,col=1)
        # 回撤陰影
        cum_arr=cum_plot.values; hwm=np.maximum.accumulate(cum_arr)
        dd=(cum_arr/hwm-1)*100
        f9.add_trace(go.Scatter(x=cum_plot.index,y=dd,name="策略回撤",
                                line=dict(color="#ef4444",width=0),
                                fill="tozeroy",fillcolor="rgba(239,68,68,.12)"),row=2,col=1)
        f9.add_hline(y=0,line_color="#334466",line_width=.8,row=2,col=1)

        f9.update_yaxes(title_text="指數",      title_font_size=10,row=1,col=1)
        f9.update_yaxes(title_text="累積報酬(%)",title_font_size=10,row=2,col=1)
        theme(f9, 560)
        # 圖例放上方
        f9.update_layout(legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="left",x=0,font_size=10))
        st.plotly_chart(f9,use_container_width=True)

        # ── 交易明細摺疊 ──────────────────────────────────
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

    # ── 頁尾 ─────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:1.5rem 0 .5rem;border-top:1px solid #1e3356;margin-top:1.5rem">
      <span style="font-size:.72rem;color:#2a4a7f;font-family:'IBM Plex Mono'">
        台指多因子策略 v11 ／ Grid Search 34,992 組最佳化 ／ 整體勝率 65.8%（回測 2021–2026）<br>
        本頁面僅供量化研究參考，不構成投資建議。
      </span>
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
