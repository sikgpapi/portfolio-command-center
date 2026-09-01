
import os, sqlite3
from datetime import datetime, date, timedelta
import requests, pandas as pd, streamlit as st

st.set_page_config(page_title="Portfolio Command Center", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-left: 1rem; padding-right: 1rem;}
[data-testid="stMetricValue"] {font-size: 1.55rem;}
@media (max-width: 700px) {
  .block-container {padding: .7rem .65rem 1.5rem;}
  h1 {font-size: 1.65rem !important;}
  h2 {font-size: 1.25rem !important;}
  h3 {font-size: 1.05rem !important;}
  [data-testid="stMetricValue"] {font-size: 1.2rem;}
}
</style>
""", unsafe_allow_html=True)

DB = "portfolio.db"
API_BASE = "https://bharatstockapi.com"
API_KEY = os.getenv("BHARATSTOCK_API_KEY", "")
if not API_KEY:
    try:
        API_KEY = st.secrets.get("BHARATSTOCK_API_KEY", "")
    except Exception:
        API_KEY = ""

DEFAULTS = [
    # name, symbol, qty, avg cost, add low, add high, breakout, max weight %
    ("Motilal-NASDAQ 100","MON100",2509,266.99,300,315,335,12),
    ("Adani Ports & SEZ","ADANIPORTS",72,1429.09,1575,1610,1750,12),
    ("Adani Green Energy","ADANIGREEN",90,1350.40,1050,1150,1450,15),
    ("Laurus Labs","LAURUSLABS",46,1450.72,1800,1850,1950,12),
    ("Modi's Navnirman","MODIS",225,353.49,300,325,380,12),
    ("Eternal (Zomato)","ETERNAL",254,269.20,280,300,360,15),
    ("GOLDCASE","GOLDCASE",3388,23.55,23,24.50,25.50,15),
    ("360 ONE WAM","360ONE",68,1087.87,1140,1170,1280,12),
    ("Triveni Turbine","TRITURBINE",130,523.87,555,570,620,12),
    ("Hitachi Energy India","POWERINDIA",2,31252.50,29500,31000,35000,10),
    ("Polycab India","POLYCAB",7,9384.14,8850,9000,9500,12),
    ("GE Vernova T&D India","GVT&D",13,4781.93,4000,4200,4700,10),
    ("Metropolis Healthcare","METROPOLIS",91,551.15,525,550,620,12),
    ("VA Tech Wabag","WABAG",24,2077.00,1900,2000,2200,12),
]
def db():
    c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS holdings(
        id INTEGER PRIMARY KEY, name TEXT, symbol TEXT, qty REAL, avg REAL,
        zone_low REAL, zone_high REAL, breakout REAL, trim_pct REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots(
        ts TEXT, symbol TEXT, price REAL, change_pct REAL)""")
    c.commit()
    return c

def seed():
    c=db()
    if c.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]==0:
        c.executemany("INSERT INTO holdings(name,symbol,qty,avg,zone_low,zone_high,breakout,trim_pct) VALUES(?,?,?,?,?,?,?,?)", DEFAULTS)
        c.commit()
    c.close()

def load():
    c=db()
    x=pd.read_sql_query("SELECT * FROM holdings ORDER BY id",c)
    c.close()
    return x

def save(df):
    c=db()
    c.execute("DELETE FROM holdings")
    c.executemany("""INSERT INTO holdings(name,symbol,qty,avg,zone_low,zone_high,breakout,trim_pct)
                     VALUES(?,?,?,?,?,?,?,?)""",
                  df[["name","symbol","qty","avg","zone_low","zone_high","breakout","trim_pct"]].itertuples(index=False,name=None))
    c.commit(); c.close()

def api(path, params=None):
    if not API_KEY: return None, "BHARATSTOCK_API_KEY is not set"
    try:
        r=requests.get(API_BASE+path,headers={"X-API-Key":API_KEY},params=params or {},timeout=15)
        if r.status_code != 200: return None, f"{r.status_code}: {r.text[:200]}"
        return r.json(),None
    except Exception as e: return None,str(e)

def quotes(symbols):
    """Batch quotes, with a single-ticker fallback for symbols the batch endpoint cannot resolve."""
    syms=[s for s in symbols if s]
    if not syms: return {},None
    data,err=api("/v1/stocks/quotes",{"symbols":",".join(syms)})
    if err:return {},err

    out={}
    unresolved=[]
    for x in data if isinstance(data,list) else data.get("data",[]):
        if x.get("found"):
            out[x["symbol"]]=x
        else:
            unresolved.append(x.get("symbol"))

    # Some ETFs/listed products can occasionally miss the batch quote feed.
    # Fall back to the single-stock endpoint before declaring the symbol unresolved.
    for symbol in unresolved:
        if not symbol:
            continue
        one, one_err = api(f"/v1/stocks/{symbol}")
        if not one_err and one:
            lp = one.get("latest_price", {})
            if lp.get("close") is not None:
                prev = lp.get("prev_close")
                chg = ((lp["close"]/prev)-1)*100 if prev else 0.0
                out[symbol]={"symbol":symbol,"close":lp["close"],"change_pct":chg,"found":True}
                continue

        # GOLDCASE is a valid NSE/BSE ETF symbol, but BharatStock may not
        # expose it in its quote endpoints. Use a market-data fallback.
        if symbol == "GOLDCASE":
            fallback = goldcase_fallback()
            if fallback:
                out[symbol] = fallback

    return out,None

def goldcase_fallback():
    """Fallback quote for GOLDCASE using Yahoo Finance's public chart endpoint.
    This is only used when BharatStock cannot resolve the ETF."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GOLDCASE.NS"
        r = requests.get(url, params={"range":"5d","interval":"1d"}, timeout=10,
                         headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        closes = [x for x in closes if x is not None]
        if not closes:
            return None
        price = float(closes[-1])
        prev = float(closes[-2]) if len(closes) > 1 else None
        chg = ((price / prev) - 1) * 100 if prev else 0.0
        return {"symbol":"GOLDCASE","close":price,"change_pct":chg,"found":True}
    except Exception:
        return None

def tech(symbol):
    data,err=api(f"/v1/stocks/{symbol}/technical-indicators",
                 {"sma_period":20,"ema_period":20,"rsi_period":14})
    if err:return {}
    rows=data if isinstance(data,list) else data.get("data",[])
    return rows[-1] if rows else {}

def ratios(symbol):
    data,err=api(f"/v1/stocks/{symbol}/ratios")
    return data if data and not err else {}

def decide(r, t, rat):
    p=r.price
    if not p: return "HOLD","No live price."
    if r.change_pct >= 5 and p > r.zone_high:
        return "HOLD","Sharp move above the accumulation zone — don't chase."
    if r.zone_low <= p <= r.zone_high:
        return "ADD",f"Price is inside ₹{r.zone_low:,.0f}–₹{r.zone_high:,.0f} accumulation zone."
    if p >= r.breakout and t:
        rv=t.get("rsi")
        sma=t.get("sma")
        if (rv is None or rv < 70) and (sma is None or p > sma):
            return "ADD",f"Breakout above ₹{r.breakout:,.0f} with trend confirmation."
    if r.qty > 0 and r.weight >= r.trim_pct:
        return "TRIM",f"Position is {r.weight:.1f}% of portfolio, above the {r.trim_pct:.0f}% cap."
    # valuation warning is informational, not an automatic sell
    pe=rat.get("pe_ratio")
    if pe and pe > 100 and r.qty > 0:
        return "HOLD",f"Very rich valuation (P/E {pe:.0f}); hold, but do not add unless price reaches the planned zone."
    return "HOLD","No actionable trigger."

seed()

st.title("📈 Portfolio Command Center")
st.caption("Daily investment tracker • disciplined ADD / HOLD / TRIM signals")
st.caption("14 holdings loaded from your verified portfolio snapshot. Prices below refresh from the configured market-data source.")

df=load()

with st.sidebar:
    st.header("Settings")
    if API_KEY:
        st.success("BharatStock API connected")
    else:
        st.warning("API key not configured")
    st.write("Set `BHARATSTOCK_API_KEY` in your environment. Never hard-code it.")
    if st.button("Refresh live data"):
        st.rerun()

tab_dash, tab_port, tab_history = st.tabs(["Dashboard","Portfolio & Rules","History"])

with tab_port:
    st.subheader("Portfolio & strategy inputs")
    st.caption("Verified from your latest holdings screenshots. Average costs are back-calculated from the displayed current price, total P&L and return %. Review before using the signals.")
    st.caption("Edit quantities, average costs and trigger levels. These rules are yours; the app does not invent trades.")
    edited=st.data_editor(
        df,use_container_width=True,num_rows="fixed",hide_index=True,
        column_config={
            "id":None,
            "name":st.column_config.TextColumn("Holding"),
            "symbol":st.column_config.TextColumn("NSE symbol"),
            "qty":st.column_config.NumberColumn("Shares",min_value=0),
            "avg":st.column_config.NumberColumn("Avg cost",min_value=0,format="₹%.2f"),
            "zone_low":st.column_config.NumberColumn("Add low",min_value=0,format="₹%.2f"),
            "zone_high":st.column_config.NumberColumn("Add high",min_value=0,format="₹%.2f"),
            "breakout":st.column_config.NumberColumn("Breakout",min_value=0,format="₹%.2f"),
            "trim_pct":st.column_config.NumberColumn("Max weight",min_value=1,max_value=100,format="%.0f%%"),
        },
        disabled=["id"]
    )
    if st.button("Save portfolio"):
        save(edited); st.success("Saved locally in portfolio.db"); st.rerun()
    st.download_button("Export CSV",edited.to_csv(index=False),"portfolio.csv","text/csv")

with tab_dash:
    q,err=quotes(df.symbol.tolist())
    if err:
        st.error(f"Live quotes unavailable: {err}")
        df["price"]=0.0; df["change_pct"]=0.0
    else:
        df["price"]=df.symbol.map(lambda s:q.get(s,{}).get("close",0.0))
        df["change_pct"]=df.symbol.map(lambda s:q.get(s,{}).get("change_pct",0.0))
        missing=df[(df.symbol!="") & (df.price==0)]
        if len(missing): st.warning("Still unresolved after fallback: "+", ".join(missing.symbol.tolist())+". Check the symbol in Portfolio & Rules.")

    df["value"]=df.qty*df.price
    total=df.value.sum()
    df["weight"]=df.value/total*100 if total else 0
    df["pnl"]=(df.price-df.avg)*df.qty
    df["pnl_pct"]=((df.price/df.avg)-1)*100
    df.loc[df.avg<=0,"pnl_pct"]=0

    actions=[]; reasons=[]; pes=[]
    for r in df.itertuples():
        t=tech(r.symbol) if r.symbol and r.price else {}
        rat=ratios(r.symbol) if r.symbol and r.price else {}
        action,reason=decide(r,t,rat)
        actions.append(action); reasons.append(reason); pes.append(rat.get("pe_ratio"))
    df["action"]=actions; df["reason"]=reasons; df["pe"]=pes

    a,b,c,d=st.columns(4)
    a.metric("Portfolio value",f"₹{total:,.0f}")
    a2=(df.qty*df.avg).sum()
    b.metric("Invested",f"₹{a2:,.0f}")
    c.metric("Unrealised P&L",f"₹{df.pnl.sum():,.0f}")
    d.metric("Positions",int((df.qty>0).sum()))

    actionable=df[df.action!="HOLD"]
    st.subheader("⚡ Today's decisions")
    if len(actionable):
        st.dataframe(actionable[["name","price","change_pct","avg","action","reason"]],use_container_width=True,hide_index=True)
    else:
        st.success("No meaningful changes. HOLD.")

    st.subheader("Portfolio")
    st.dataframe(df[["name","symbol","qty","price","avg","pnl","pnl_pct","weight","pe","action"]],use_container_width=True,hide_index=True)

    # Save one daily snapshot per symbol.
    if not err:
        c=db()
        now=datetime.now().isoformat(timespec="seconds")
        c.executemany("INSERT INTO snapshots VALUES(?,?,?,?)",
                      [(now,r.symbol,float(r.price),float(r.change_pct)) for r in df.itertuples() if r.symbol and r.price])
        c.commit(); c.close()

with tab_history:
    c=db()
    hist=pd.read_sql_query("SELECT * FROM snapshots ORDER BY ts DESC LIMIT 5000",c)
    c.close()
    if hist.empty:
        st.info("History will appear after the first successful live refresh.")
    else:
        st.dataframe(hist,use_container_width=True,hide_index=True)
        st.download_button("Export price history",hist.to_csv(index=False),"price_history.csv","text/csv")

st.divider()
st.caption("Decision-support only. The app never places trades. ADD/HOLD/TRIM is generated from the trigger rules you define.")
