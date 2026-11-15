import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Scanner Capitulation Crypto", layout="wide")

st.title("🚀 Dashboard de Screening - Capitulation Crypto (Top 200 Binance)")
st.markdown("Analyse automatique des cryptomonnaies les plus liquides sur le marché Spot Binance.")

# Mots-clés et tokens spécifiques à exclure pour éviter les faux positifs
EXCLUDED_KEYWORDS = [
    'UP', 'DOWN', 'BEAR', 'BULL',
    'USDC', 'FDUSD', 'TUSD', 'BUSD', 'USDE', 'DAI', 'EUR', 'GBP', 'AUD', 'USD1', 'RLUSD',
    'PAXG', 'XAU', 'XAG', 'AUTO', 'BLZ'
]

# Sidebar pour les filtres
st.sidebar.header("⚙️ Paramètres du Scan")
min_volume_usdt = st.sidebar.number_input(
    "Volume 24h min (en USDT)", 
    min_value=0, 
    value=5_000_000, 
    step=1_000_000, 
    format="%d"
)

@st.cache_data(ttl=3600)
def get_all_binance_pairs():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            usdt_pairs = []
            for item in data:
                symbol = item['symbol']
                if symbol.endswith('USDT'):
                    base_symbol = symbol.replace('USDT', '')
                    if not any(excluded == base_symbol or excluded in symbol for excluded in EXCLUDED_KEYWORDS):
                        usdt_pairs.append(item)
            usdt_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
            return usdt_pairs
    except Exception as e:
        st.error(f"Erreur de connexion à l'API Binance : {e}")
    return []

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
    except:
        pass
    return None

def compute_indicators(df, rsi_len=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/rsi_len, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/rsi_len, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma100'] = df['close'].rolling(100).mean()
    df['ma200'] = df['close'].rolling(200).mean()
    df['vol_sma20'] = df['volume'].rolling(20).mean()
    
    df['ath_365'] = df['high'].rolling(min_periods=1, window=365).max()
    df['ath_cycle'] = df['high'].max()
    
    return df

def run_screener_engine(symbols_list, volumes_dict):
    mode = st.radio(
        "Sélectionne l'horizon de screening :", 
        ["Court Terme (4H / Daily)", "Moyen Terme (Daily / Weekly)", "Long Terme (Daily / Weekly)"], 
        horizontal=True
    )

    if st.button("Lancer le Scan Automatique 🚀", type="primary"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(symbols_list)
        
        if total == 0:
            st.warning("Aucun actif trouvé avec ces critères.")
            return

        for i, symbol in enumerate(symbols_list):
            status_text.text(f"Analyse ({i+1}/{total}) : {symbol}...")
            
            try:
                if "Court Terme" in mode:
                    df_fast = get_klines(symbol, "4h")
                    df_slow = get_klines(symbol, "1d")
                elif "Moyen Terme" in mode:
                    df_fast = get_klines(symbol, "1d")
                    df_slow = get_klines(symbol, "1w")
                else: 
                    df_fast = get_klines(symbol, "1d")
                    df_slow = get_klines(symbol, "1w")

                if df_fast is not None and len(df_fast) > 200 and df_slow is not None and len(df_slow) > 50:
                    df_fast = compute_indicators(df_fast)
                    df_slow = compute_indicators(df_slow)
                    
                    curr_fast = df_fast.iloc[-1]
                    curr_slow = df_slow.iloc[-1]
                    
                    if curr_fast['close'] <= 0:
                        continue

                    tv_link = f"https://www.tradingview.com/symbols/search/?q={symbol}"
                    
                    # Formatage du volume 24h
                    raw_vol = volumes_dict.get(symbol, 0)
                    if raw_vol >= 1e9:
                        vol_fmt = f"${raw_vol / 1e9:,.2f}B"
                    elif raw_vol >= 1e6:
                        vol_fmt = f"${raw_vol / 1e6:,.2f}M"
                    else:
                        vol_fmt = f"${raw_vol:,.0f}"

                    if "Court Terme" in mode:
                        c1 = curr_slow['close'] <= curr_slow['ath_cycle'] * 0.5                  
                        c2 = curr_fast['rsi'] < 35                                                
                        c3 = curr_fast['close'] < curr_fast['ma50'] and curr_fast['close'] < curr_fast['ma100'] 
                        c4 = curr_fast['close'] < curr_fast['ma200']                            
                        c5 = curr_slow['rsi'] < 40                                                
                        c6 = curr_slow['close'] < curr_fast['ma20'] and curr_slow['close'] < curr_fast['ma50'] 
                        c7 = (curr_fast['low'] < df_fast['low'].iloc[-20:-5].min()) and (curr_fast['rsi'] > df_fast['rsi'].iloc[-20:-5].min()) 
                        c8 = (curr_slow['low'] < df_slow['low'].iloc[-20:-5].min()) and (curr_slow['rsi'] > df_slow['rsi'].iloc[-20:-5].min()) 
                        c9 = curr_fast['volume'] > (2.5 * curr_fast['vol_sma20'])                
                        
                        score = sum([c1, c2, c3, c4, c5, c6, c7, c8, c9])
                        price_fmt = f"${curr_fast['close']:,.4f}" if curr_fast['close'] < 1 else f"${curr_fast['close']:,.2f}"
                        
                        results.append({
                            "Actif": symbol,
                            "TradingView": tv_link,
                            "Prix": price_fmt,
                            "Volume 24h": vol_fmt,
                            "Score /9": f"{score}/9",
                            "C1 (ATH Cycle -50%)": "✅" if c1 else "❌",
                            "C2 (RSI 4H <35)": f"{curr_fast['rsi']:.1f} " + ("✅" if c2 else "❌"),
                            "C3 (Sous MA50/100 4H)": "✅" if c3 else "❌",
                            "C4 (Sous MA200 4H)": "✅" if c4 else "❌",
                            "C5 (RSI Daily <40)": f"{curr_slow['rsi']:.1f} " + ("✅" if c5 else "❌"),
                            "C6 (Sous MA20/50 D)": "✅" if c6 else "❌",
                            "C7 (Div 4H)": "✅" if c7 else "❌",
                            "C8 (Div Daily)": "✅" if c8 else "❌",
                            "C9 (Vol Cap 4H)": "🔥 Oui" if c9 else "❌",
                        })

                    elif "Moyen Terme" in mode:
                        c1 = curr_fast['rsi'] < 40                                                
                        c2 = curr_fast['close'] < curr_fast['ma50']                               
                        c3 = curr_fast['close'] < curr_fast['ma100']                              
                        c4 = curr_fast['close'] < curr_fast['ma200']                              
                        c5 = curr_slow['close'] < curr_slow['ma50']                               
                        c6 = curr_slow['close'] < curr_slow['ma100']                              
                        c7 = curr_slow['rsi'] < 40                                                
                        c8 = (curr_fast['low'] < df_fast['low'].iloc[-30:-5].min()) and (curr_fast['rsi'] > df_fast['rsi'].iloc[-30:-5].min()) 
                        
                        score = sum([c1, c2, c3, c4, c5, c6, c7, c8])
                        price_fmt = f"${curr_fast['close']:,.4f}" if curr_fast['close'] < 1 else f"${curr_fast['close']:,.2f}"

                        results.append({
                            "Actif": symbol,
                            "TradingView": tv_link,
                            "Prix": price_fmt,
                            "Volume 24h": vol_fmt,
                            "Score /8": f"{score}/8",
                            "C1 (RSI Daily <40)": f"{curr_fast['rsi']:.1f} " + ("✅" if c1 else "❌"),
                            "C2 (Prix < MA50 D)": "✅" if c2 else "❌",
                            "C3 (Prix < MA100 D)": "✅" if c3 else "❌",
                            "C4 (Prix < MA200 D)": "✅" if c4 else "❌",
                            "C5 (Prix < MA50 W)": "✅" if c5 else "❌",
                            "C6 (Prix < MA100 W)": "✅" if c6 else "❌",
                            "C7 (RSI Weekly <40)": f"{curr_slow['rsi']:.1f} " + ("✅" if c7 else "❌"),
                            "C8 (Div Daily)": "✅" if c8 else "❌",
                        })

                    else: 
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
                        price_fmt = f"${curr_fast['close']:,.4f}" if curr_fast['close'] < 1 else f"${curr_fast['close']:,.2f}"

                        results.append({
                            "Actif": symbol,
                            "TradingView": tv_link,
                            "Prix": price_fmt,
                            "Volume 24h": vol_fmt,
                            "Score /9": f"{score}/9",
                            "C1 (ATH Cycle -50%)": "✅" if c1 else "❌",
                            "C2 (RSI Daily <30)": f"{curr_fast['rsi']:.1f} " + ("✅" if c2 else "❌"),
                            "C3 (Sous MA100 D)": "✅" if c3 else "❌",
                            "C4 (Sous MA200 D)": "✅" if c4 else "❌",
                            "C5 (RSI Weekly <40)": f"{curr_slow['rsi']:.1f} " + ("✅" if c5 else "❌"),
                            "C6 (Sous MA50 W)": "✅" if c6 else "❌",
                            "C7 (Div Daily)": "✅" if c7 else "❌",
                            "C8 (Div Weekly)": "✅" if c8 else "❌",
                            "C9 (Vol Cap Daily)": "🔥 Oui" if c9 else "❌",
                        })
            except Exception:
                pass
                
            progress_bar.progress((i + 1) / total)
            
        status_text.empty()
        progress_bar.empty()
        
        if results:
            res_df = pd.DataFrame(results)
            score_col = [col for col in res_df.columns if "Score" in col][0]
            res_df = res_df.sort_values(by=score_col, key=lambda x: x.str.split('/').str[0].astype(int), ascending=False)
            
            st.success("Scan terminé avec succès !")
            st.dataframe(
                res_df,
                use_container_width=True,
                column_config={
                    "TradingView": st.column_config.LinkColumn(
                        "Graphique TradingView",
                        help="Cliquez pour ouvrir la recherche TradingView de la paire",
                        display_text="📈 Ouvrir TV"
                    )
                }
            )
            
            csv_data = res_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger les résultats en CSV",
                data=csv_data,
                file_name="capitulation_crypto_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("Aucun résultat correspondant ou données indisponibles pour ces actifs.")

# Chargement et filtrage rigoureux
with st.spinner("Récupération des données propres depuis l'API Binance..."):
    all_pairs = get_all_binance_pairs()

# Création d'un dictionnaire pour associer chaque symbole à son volume 24h
volumes_dict = {p['symbol']: float(p['quoteVolume']) for p in all_pairs}

crypto_pairs = [
    p for p in all_pairs 
    if float(p['quoteVolume']) >= min_volume_usdt
]
top_200_cryptos = [p['symbol'] for p in crypto_pairs[:200]]

st.sidebar.success(f"Actifs filtrés et analysés : {len(top_200_cryptos)}")

run_screener_engine(top_200_cryptos, volumes_dict)