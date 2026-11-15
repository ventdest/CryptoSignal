import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Scanner Capitulation Crypto", layout="wide")

st.title("📊 Dashboard de Screening - Capitulation Crypto (Top 100 Crypto Pure)")
st.markdown("Analyse automatique des cryptomonnaies les plus liquides (données marché Coinbase).")

mode = st.radio(
    "Sélectionne l'horizon :",
    ["Court Terme (6H / Daily)", "Long Terme (Weekly / Monthly)"],
    horizontal=True
)

BASE_URL = "https://coinbase.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

EXCLUDED_KEYWORDS = [
    'USDC', 'FDUSD', 'TUSD', 'BUSD', 'USD1', 'USDE', 'RLUSD', 'DAI', 'EUR', 'GBP', 'AUD', 'PYUSD', 'GUSD', 'PAX',
    'PAXG', 'XAU', 'XAG', 'XAUT', 'WBTC', 'WETH', 'CBETH', 'STETH'
]

@st.cache_data(ttl=3600)
def get_top_symbols(limit=80):
    try:
        # Récupère toutes les paires disponibles sur Coinbase
        res_prod = requests.get(f"{BASE_URL}/products", headers=HEADERS, timeout=10)
        if res_prod.status_code != 200:
            return None, f"Erreur HTTP {res_prod.status_code} sur /products"
        
        products = res_prod.json()
        valid_pairs = []
        for p in products:
            # Coinbase utilise USD ou USDT (USD est le plus liquide sur Coinbase)
            if p.get('quote_currency') == 'USD' and p.get('status') == 'online' and not p.get('trading_disabled'):
                base = p.get('base_currency', '')
                if base not in EXCLUDED_KEYWORDS:
                    valid_pairs.append(p['id'])  # Format : BTC-USD

        # Récupère les stats 24h pour trier par volume
        res_stats = requests.get(f"{BASE_URL}/products/stats", headers=HEADERS, timeout=10)
        if res_stats.status_code == 200:
            stats_data = res_stats.json()
            ranked = []
            for pair_id in valid_pairs:
                if pair_id in stats_data:
                    s = stats_data[pair_id].get('stats_24hour', {})
                    vol_usd = float(s.get('volume', 0)) * float(s.get('last', 0))
                    ranked.append((pair_id, vol_usd))
            ranked.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in ranked[:limit]], None
        
        return valid_pairs[:limit], None
    except Exception as e:
        return None, f"Exception réseau (Top 100) : {str(e)}"

@st.cache_data(ttl=300)
def get_klines(product_id, granularity):
    # Coinbase utilise la granularité en secondes : 21600 (6H), 86400 (1D)
    # Limite max par appel : 300 bougies
    url = f"{BASE_URL}/products/{product_id}/candles?granularity={granularity}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                # Coinbase renvoie [timestamp, low, high, open, close, volume] du plus récent au plus ancien
                data = data[::-1]
                df = pd.DataFrame(data, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
                for col in ['close', 'high', 'low', 'volume']:
                    df[col] = df[col].astype(float)
                return df, None
            return None, f"Données vides pour {product_id}"
        return None, f"HTTP {response.status_code} sur {product_id} : {response.text[:100]}"
    except Exception as e:
        return None, f"Exception sur {product_id} : {str(e)}"

def resample_weekly(df_daily):
    df = df_daily.copy()
    df['date'] = pd.to_datetime(df['timestamp'], unit='s')
    df.set_index('date', inplace=True)
    df_w = df.resample('W').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    return df_w

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

if st.button("Lancer le Scan Dynamique 🚀"):
    symbols, top_error = get_top_symbols(60)
    
    if top_error:
        st.warning(f"⚠️ Liste dynamique indisponible ({top_error}). Utilisation de la liste de secours.")
        symbols = [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
            "DOGE-USD", "AVAX-USD", "LINK-USD", "SUI-USD", "ARB-USD",
            "ONDO-USD", "OP-USD", "RENDER-USD", "STX-USD", "TIA-USD", "WIF-USD"
        ]
    
    results = []
    errors_log = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(symbols)
    is_short_term = "Court Terme" in mode
    
    for i, symbol in enumerate(symbols):
        clean_name = symbol.replace("-USD", "")
        status_text.text(f"Analyse en cours ({i+1}/{total}) : {clean_name}...")
        progress_bar.progress((i + 1) / total)
        
        # Respecte la limite de requêtes par seconde de Coinbase (10 req/s max)
        time.sleep(0.15)
        
        try:
            if is_short_term:
                df_fast, err_fast = get_klines(symbol, 21600)  # 6H (4H n'existe pas nativement sur Coinbase)
                df_slow, err_slow = get_klines(symbol, 86400)  # 1D
            else:
                df_fast, err_fast = get_klines(symbol, 86400)  # 1D
                err_slow = None
                df_slow = resample_weekly(df_fast) if df_fast is not None else None
            
            if err_fast:
                errors_log.append(err_fast)
            if err_slow:
                errors_log.append(err_slow)
                
            if df_fast is not None and len(df_fast) > 200 and df_slow is not None and len(df_slow) > 30:
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
                        "Actif": clean_name,
                        "Prix ($)": cf['close'],
                        "Score /9": f"{score}/9",
                        "C1 (ATH 300j -50%)": "✅" if c1 else "❌",
                        "C2 (RSI 6H <35)": f"{round(cf['rsi'], 1)} {'✅' if c2 else '❌'}",
                        "C3 (Sous MA50/100 6H)": "✅" if c3 else "❌",
                        "C4 (Sous MA200 6H)": "✅" if c4 else "❌",
                        "C5 (RSI Daily <40)": f"{round(cs['rsi'], 1)} {'✅' if c5 else '❌'}",
                        "C6 (Sous MA20/50 D)": "✅" if c6 else "❌",
                        "C7 (Div 6H)": "✅" if c7 else "❌",
                        "C8 (Div Daily)": "✅" if c8 else "❌",
                        "C9 (Vol Cap 6H)": "🔥 Oui" if c9 else "❌",
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
                        "Actif": clean_name,
                        "Prix ($)": cf['close'],
                        "Score /9": f"{score}/9",
                        "C1 (ATH 300j -50%)": "✅" if c1 else "❌",
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
            errors_log.append(f"Erreur de calcul sur {clean_name} : {str(e)}")

    status_text.empty()
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Score /9", ascending=False)
        st.success(f"Scan terminé ! {len(df_res)} actifs analysés.")
        st.dataframe(df_res, use_container_width=True)
    else:
        st.error("Impossible de récupérer les données pour le moment.")
