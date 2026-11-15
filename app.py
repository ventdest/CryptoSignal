import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Scanner Capitulation Crypto", layout="wide")

st.title("📊 Dashboard de Screening - Capitulation Crypto (Top 100 Crypto Pure)")
st.markdown("Analyse automatique des 100 vraies cryptomonnaies les plus liquides sur Binance.")

mode = st.radio(
    "Sélectionne l'horizon :",
    ["Court Terme (4H / Daily)", "Long Terme (Weekly / Monthly)"],
    horizontal=True
)

# Endpoint officiel alternatif pour éviter le blocage IP US (Erreur 451)
BASE_URL = "https://binance.vision"

EXCLUDED_KEYWORDS = [
    'UP', 'DOWN', 'BEAR', 'BULL',
    'USDC', 'FDUSD', 'TUSD', 'BUSD', 'USD1', 'USDE', 'RLUSD', 'DAI', 'EUR', 'GBP', 'AUD',
    'PAXG', 'XAU', 'XAG'
]

@st.cache_data(ttl=3600)
def get_top_symbols(limit=100):
    url = f"{BASE_URL}/ticker/24hr"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            usdt_pairs = [
                item for item in data
                if item['symbol'].endswith('USDT')
                and not any(ex in item['symbol'] for ex in EXCLUDED_KEYWORDS)
            ]
            usdt_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
            return [item['symbol'] for item in usdt_pairs[:limit]], None
        return None, f"Erreur HTTP {response.status_code} (Top 100) : {response.text}"
    except Exception as e:
        return None, f"Exception réseau (Top 100) : {str(e)}"

@st.cache_data(ttl=300)
def get_klines(symbol, interval, limit=1000):
    url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                for col in ['close', 'high', 'low', 'volume']:
                    df[col] = df[col].astype(float)
                return df, None
            return None, f"Données vides pour {symbol} ({interval})"
        return None, f"HTTP {response.status_code} sur {symbol} ({interval}) : {response.text}"
    except Exception as e:
        return None, f"Exception sur {symbol} ({interval}) : {str(e)}"

def compute_indicators(df, rsi_len=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/rsi_len, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/rsi_len, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss))
    
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma100'] = df['close'].rolling(100).mean()
    df['ma200'] = df['close'].rolling(200).mean()
    df['vol_sma20'] = df['volume'].rolling(20).mean()
    
    df['ath_365'] = df['high'].rolling(min_periods=1, window=365).max()
    df['ath_cycle'] = df['high'].max()
    return df

if st.button("Lancer le Scan Dynamique du Top 100 🚀"):
    symbols, top_error = get_top_symbols(100)
    
    if top_error:
        st.warning(f"⚠️ Liste dynamique indisponible ({top_error}). Utilisation de la liste de secours.")
        symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT", "AKTUSDT", "ARBUSDT",
            "AXLUSDT", "MANTAUSDT", "ONDOUSDT", "OPUSDT", "PENDLEUSDT", "PYTHUSDT",
            "RENDERUSDT", "STXUSDT", "TIAUSDT", "WUSDT", "WIFUSDT"
        ]
    
    results = []
    errors_log = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(symbols)
    is_short_term = "Court Terme" in mode
    
    for i, symbol in enumerate(symbols):
        status_text.text(f"Analyse en cours ({i+1}/{total}) : {symbol}...")
        progress_bar.progress((i + 1) / total)
        
        try:
            tf_fast, tf_slow = ("4h", "1d") if is_short_term else ("1d", "1w")
            df_fast, err_fast = get_klines(symbol, tf_fast)
            df_slow, err_slow = get_klines(symbol, tf_slow)
            
            if err_fast:
                errors_log.append(err_fast)
            if err_slow:
                errors_log.append(err_slow)
                
            if df_fast is not None and len(df_fast) > 200 and df_slow is not None and len(df_slow) > 50:
                df_fast = compute_indicators(df_fast)
                df_slow = compute_indicators(df_slow)
                
                cf = df_fast.iloc[-1]
                cs = df_slow.iloc[-1]
                
                if is_short_term:
                    c1 = cs['close'] <= cs['ath_365'] * 0.5
                    c2 = cf['rsi'] < 35
                    c3 = cf['close'] < cf['ma50'] and cf['close'] < cf['ma100']
                    c4 = cf['close'] < cf['ma200']
                    c5 = cs['rsi'] < 40
                    c6 = cs['close'] < cs['ma20'] and cs['close'] < cs['ma50']
                    c7 = (cf['low'] < df_fast['low'].iloc[-20:-5].min()) and (cf['rsi'] > df_fast['rsi'].iloc[-20:-5].min())
                    c8 = (cs['low'] < df_slow['low'].iloc[-20:-5].min()) and (cs['rsi'] > df_slow['rsi'].iloc[-20:-5].min())
                    c9 = cf['volume'] > (2.5 * cf['vol_sma20'])
                    
                    score = sum([c1, c2, c3, c4, c5, c6, c7, c8, c9])
                    results.append({
                        "Actif": symbol,
                        "Prix": cf['close'],
                        "Score /9": f"{score}/9",
                        "C1 (ATH 365j -50%)": "✅" if c1 else "❌",
                        "C2 (RSI 4H <35)": f"{round(cf['rsi'], 1)} {'✅' if c2 else '❌'}",
                        "C3 (Sous MA50/100 4H)": "✅" if c3 else "❌",
                        "C4 (Sous MA200 4H)": "✅" if c4 else "❌",
                        "C5 (RSI Daily <40)": f"{round(cs['rsi'], 1)} {'✅' if c5 else '❌'}",
                        "C6 (Sous MA20/50 D)": "✅" if c6 else "❌",
                        "C7 (Div 4H)": "✅" if c7 else "❌",
                        "C8 (Div Daily)": "✅" if c8 else "❌",
                        "C9 (Vol Cap 4H)": "🔥 Oui" if c9 else "❌",
                    })
                else:
                    c1 = cs['close'] <= cs['ath_cycle'] * 0.5
                    c2 = cf['rsi'] < 30
                    c3 = cf['close'] < cf['ma100']
                    c4 = cf['close'] < cf['ma200']
                    c5 = cs['rsi'] < 40
                    c6 = cs['close'] < cs['ma50']
                    c7 = (cf['low'] < df_fast['low'].iloc[-30:-5].min()) and (cf['rsi'] > df_fast['rsi'].iloc[-30:-5].min())
                    c8 = (cs['low'] < df_slow['low'].iloc[-10:-2].min()) and (cs['rsi'] > df_slow['rsi'].iloc[-10:-2].min())
                    c9 = cf['volume'] > (3.0 * cf['vol_sma20'])
                    
                    score = sum([c1, c2, c3, c4, c5, c6, c7, c8, c9])
                    results.append({
                        "Actif": symbol,
                        "Prix": cf['close'],
                        "Score /9": f"{score}/9",
                        "C1 (ATH Cycle -50%)": "✅" if c1 else "❌",
                        "C2 (RSI Daily <30)": f"{round(cf['rsi'], 1)} {'✅' if c2 else '❌'}",
                        "C3 (Sous MA100 D)": "✅" if c3 else "❌",
                        "C4 (Sous MA200 D)": "✅" if c4 else "❌",
                        "C5 (RSI Weekly <40)": f"{round(cs['rsi'], 1)} {'✅' if c5 else '❌'}",
                        "C6 (Sous MA50 W)": "✅" if c6 else "❌",
                        "C7 (Div Daily)": "✅" if c7 else "❌",
                        "C8 (Div Weekly)": "✅" if c8 else "❌",
                        "C9 (Vol Cap D)": "🔥 Oui" if c9 else "❌",
                    })
        except Exception as e:
            errors_log.append(f"Erreur de calcul sur {symbol} : {str(e)}")

    status_text.empty()
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Score /9", ascending=False)
        st.success(f"Scan terminé ! {len(df_res)} actifs analysés.")
        st.dataframe(df_res, use_container_width=True)
    else:
        st.error("Impossible de récupérer les données pour le moment.")
        if errors_log:
            with st.expander("🔍 Détails des erreurs rencontrées", expanded=True):
                for err in errors_log[:10]:
                    st.code(err)
