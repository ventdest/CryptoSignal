import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Scanner Capitulation Crypto", layout="wide")

st.title("📊 Dashboard de Screening - Capitulation Crypto (Top 100 Crypto Pure)")
st.markdown("Analyse automatique des 100 vraies cryptomonnaies les plus liquides sur Binance.")

# Sélecteur entre Court Terme et Long Terme
mode = st.radio("Sélectionne l'horizon :", ["Court Terme (4H / Daily)", "Long Terme (Weekly / Monthly)"], horizontal=True)

# Liste de stablecoins et d'actifs non-crypto à filtrer
EXCLUDED_KEYWORDS = [
    'UP', 'DOWN', 'BEAR', 'BULL',  # Tokens à effet de levier
    'USDC', 'FDUSD', 'TUSD', 'BUSD', 'USD1', 'USDE', 'RLUSD', 'DAI', 'EUR', 'GBP', 'AUD', # Stablecoins / Fx
    'PAXG', 'XAU', 'XAG' # Or / Métaux tokenisés
]

# Fonction pour récupérer dynamiquement le Top 100 des paires USDT réelles
@st.cache_data(ttl=3600)
def get_top_symbols(limit=100):
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            usdt_pairs = []
            for item in data:
                symbol = item['symbol']
                # Doit se terminer par USDT
                if symbol.endswith('USDT'):
                    base_asset = symbol[:-4] # Ex: BTC, ETH
                    # Vérifier qu'aucun mot-clé exclu n'est présent
                    if not any(excluded in symbol for excluded in EXCLUDED_KEYWORDS):
                        usdt_pairs.append(item)
            
            # Trier par volume d'échange décroissant
            usdt_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
            symbols = [item['symbol'] for item in usdt_pairs[:limit]]
            return symbols
    except:
        pass
    # Liste de secours au cas où l'API est indisponible
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT", "AKTUSDT", "ARBUSDT", "AXLUSDT", "SUIUSDT", "DOGEUSDT", "MANTAUSDT", "ONDOUSDT", "OPUSDT", "PENDLEUSDT", "PYTHUSDT", "RENDERUSDT", "STXUSDT", "TIAUSDT", "WUSDT", "WIFUSDT"]

# Fonction mise en cache pour récupérer les bougies
@st.cache_data(ttl=300)
def get_klines(symbol, interval, limit=1000):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['volume'] = df['volume'].astype(float)
                return df
    except Exception as e:
        pass
    return None

# Calcul des indicateurs techniques de base
def compute_indicators(df, rsi_len=14):
    df['rsi'] = 100 - (100 / (1 + df['close'].diff().clip(lower=0).ewm(alpha=1/rsi_len, adjust=False).mean() / 
                              (-df['close'].diff().clip(upper=0).ewm(alpha=1/rsi_len, adjust=False).mean())))
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma100'] = df['close'].rolling(100).mean()
    df['ma200'] = df['close'].rolling(200).mean()
    df['vol_sma20'] = df['volume'].rolling(20).mean()
    
    df['ath_365'] = df['high'].rolling(min_periods=1, window=365).max()
    df['ath_cycle'] = df['high'].max()
    
    return df

if st.button("Lancer le Scan Dynamique du Top 100 🚀"):
    symbols = get_top_symbols(100)
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(symbols)
    
    for i, symbol in enumerate(symbols):
        status_text.text(f"Analyse en cours ({i+1}/{total}) : {symbol}...")
        
        try:
            if "Court Terme" in mode:
                df_fast = get_klines(symbol, "4h")
                df_slow = get_klines(symbol, "1d")
                
                if df_fast is not None and len(df_fast) > 200 and df_slow is not None and len(df_slow) > 50:
                    df_fast = compute_indicators(df_fast)
                    df_slow = compute_indicators(df_slow)
                    
                    curr_fast = df_fast.iloc[-1]
                    curr_slow = df_slow.iloc[-1]
                    
                    c1 = curr_slow['close'] <= curr_slow['ath_365'] * 0.5                  
                    c2 = curr_fast['rsi'] < 35                                              
                    c3 = curr_fast['close'] < curr_fast['ma50'] and curr_fast['close'] < curr_fast['ma100'] 
                    c4 = curr_fast['close'] < curr_fast['ma200']                            
                    c5 = curr_slow['rsi'] < 40                                              
                    c6 = curr_slow['close'] < curr_slow['ma20'] and curr_slow['close'] < curr_slow['ma50'] 
                    c7 = (curr_fast['low'] < df_fast['low'].iloc[-20:-5].min()) and (curr_fast['rsi'] > df_fast['rsi'].iloc[-20:-5].min()) 
                    c8 = (curr_slow['low'] < df_slow['low'].iloc[-20:-5].min()) and (curr_slow['rsi'] > df_slow['rsi'].iloc[-20:-5].min()) 
                    c9 = curr_fast['volume'] > (2.5 * curr_fast['vol_sma20'])               
                    
                    score = sum([c1, c2, c3, c4, c5, c6, c7, c8, c9])
                    
                    results.append({
                        "Actif": symbol,
                        "Prix": curr_fast['close'],
                        "Score /9": f"{score}/9",
                        "C1 (ATH 365j -50%)": "✅" if c1 else "❌",
                        "C2 (RSI 4H <35)": f"{round(curr_fast['rsi'], 1)} {'✅' if c2 else '❌'}",
                        "C3 (Sous MA50/100 4H)": "✅" if c3 else "❌",
                        "C4 (Sous MA200 4H)": "✅" if c4 else "❌",
                        "C5 (RSI Daily <40)": f"{round(curr_slow['rsi'], 1)} {'✅' if c5 else '❌'}",
                        "C6 (Sous MA20/50 D)": "✅" if c6 else "❌",
                        "C7 (Div 4H)": "✅" if c7 else "❌",
                        "C8 (Div Daily)": "✅" if c8 else "❌",
                        "C9 (Vol Cap 4H)": "🔥 Oui" if c9 else "❌",
                    })
            else:
                df_fast = get_klines(symbol, "1d")
                df_slow = get_klines(symbol, "1w")
                
                if df_fast is not None and len(df_fast) > 200 and df_slow is not None and len(df_slow) > 50:
                    df_fast = compute_indicators(df_fast)
                    df_slow = compute_indicators(df_slow)
                    
                    curr_fast = df_fast.iloc[-1]
                    curr_slow = df_slow.iloc[-1]
                    
                    c1 = curr_slow['close'] <= curr_slow['ath_cycle'] * 0.5                
                    c2 = curr_fast['rsi'] < 30                                              
                    c3 = curr_fast['close'] < curr_fast['ma100']                            
                    c4 = curr_fast['close'] < curr_fast['ma200']                            
                    c5 = curr_slow['rsi'] < 40                                              
                    c6 = curr_slow['close'] < curr_slow['ma50']                             
                    c7 = (curr_fast['low'] < df_fast['low'].iloc[-30:-5].min()) and (curr_fast['rsi'] > df_fast['rsi'].iloc[-30:-5].min()) 
                    c8 = (curr_slow['low'] < df_slow['low'].iloc[-10:-2].min()) and (curr_slow['rsi'] > df_slow['rsi'].iloc[-10:-2].min()) 
                    c9 = curr_fast['volume'] > (3.0 * curr_fast['vol_sma20'])               
                    
                    score = sum([c1, c2, c3, c4, c5, c6, c7, c8, c9])
                    
                    results.append({
                        "Actif": symbol,
                        "Prix": curr_fast['close'],
                        "Score /9": f"{score}/9",
                        "C1 (ATH Cycle -50%)": "✅" if c1 else "❌",
                        "C2 (RSI Daily <30)": f"{round(curr_fast['rsi'], 1)} {'✅' if c2 else '❌'}",
                        "C3 (Sous MA100 D)": "✅" if c3 else "❌",
                        "C4 (Sous MA200 D)": "✅" if c4 else "❌",
                        "C5 (RSI Weekly <40)": f"{round(curr_slow['rsi'], 1)} {'✅' if c5 else '❌'}",
                        "C6 (Sous MA50 W)": "✅" if c6 else "❌",
                        "C7 (Div Daily)": "✅" if c7 else "❌",
                        "C8 (Div Weekly)": "✅" if c8 else "❌",
                        "C9 (Vol Cap Daily)": "🔥 Oui" if c9 else "❌",
                    })
        except Exception as e:
            pass
            
        progress_bar.progress((i + 1) / total)
        
    status_text.empty()
    progress_bar.empty()
    
    if results:
        res_df = pd.DataFrame(results)
        res_df = res_df.sort_values(by="Score /9", ascending=False)
        st.success("Scan dynamique du Top 100 terminé avec succès !")
        st.dataframe(res_df, use_container_width=True)
    else:
        st.error("Impossible de récupérer les données pour le moment.")