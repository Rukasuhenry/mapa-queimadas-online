# app.py
import os
import sys
import streamlit as st
from datetime import date, datetime
import streamlit.components.v1 as components
import matplotlib.pyplot as plt

# Garante que o diretório atual esteja no path
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from mapa_com_correlacao_v4 import main

st.set_page_config(page_title="Mapa de Queimadas V4", layout="wide")
st.title("🔍 Mapa de Queimadas – V4 🗺️")

# Definição das estações
station_coords = {
    "bauru": (-22.3146, -49.0629),
    "campinas-v.união": (-23.1884, -47.8970),
    "carapicuíba": (-23.4970, -46.8340),
    "cerqueira-césar": (-23.5432, -46.6621),
    "cid.universitária-usp-ipen": (-23.5594, -46.7346),
    "congonhas": (-23.6264, -46.6562),
    "cubatão-vale-do mogi": (-23.8714, -46.4208),
    "cubatão-vila-parisi": (-23.8700, -46.4280),
    "guaratinguetá": (-22.7994, -45.2146),
    "guarulhos-paço-municipal": (-23.4510, -46.5330),
    "guarulhos-pimentas": (-23.4970, -46.3580),
    "ibirapuera": (-23.5870, -46.6610),
    "interlagos": (-23.7050, -46.7100),
    "itaim-paulista": (-23.5020, -46.4740),
    "itaquera": (-23.5340, -46.4600),
    "jundiaí": (-23.1850, -46.8970),
    "limeira": (-23.1850, -47.4850),
    "marg.tietê-ponte-dos remédios": (-23.5070, -46.6330),
    "mauá": (-23.6540, -46.4640),
    "mooca": (-23.5570, -46.5980),
    "nossa-senhora do ó": (-23.4920, -46.5980),
    "osasco": (-23.5320, -46.7910),
    "parelheiros": (-23.7740, -46.7720),
    "parque-d.pedro ii": (-23.5500, -46.6330),
    "paulínia": (-23.1880, -46.5370),
    "paulínia-sul": (-23.2120, -46.5510),
    "perus": (-23.4870, -46.7220),
    "pinheiros": (-23.5630, -46.6870),
    "piracicaba": (-23.2090, -47.6480),
    "presidente-prudente": (-22.1200, -51.3960),
    "ribeirão-preto": (-21.1770, -47.8100),
    "rio-claro-jd.guanabara": (-22.4090, -47.5480),
    "s.bernardo-centro": (-23.6760, -46.5640),
    "s.josé-campos-jd.satélite": (-23.1890, -45.9000),
    "santa-gertrudes": (-23.1020, -47.5340),
    "santana": (-23.4980, -46.6280),
    "santo-amaro": (-23.6240, -46.6980),
    "santos": (-23.1896, -46.8130),
    "santos-ponta-da praia": (-23.9730, -46.3370),
    "são-josé do rio preto": (-20.8180, -49.3790),
    "taboão-da serra": (-23.6260, -46.7530),
    "taubaté": (-23.0465, -45.5639)
}

# Formulário de parâmetros
with st.form(key='params_form'):
    station = st.selectbox("Estação", list(station_coords.keys()))
    col1, col2, col3 = st.columns(3)
    with col1:
        start_date = st.date_input("Data início", value=date(2024,7,1))
    with col2:
        end_date = st.date_input("Data fim",   value=date(2024,8,30))
    with col3:
        radius_km = st.number_input("Raio (km)", min_value=10, max_value=1000, value=150, step=10)
    submit = st.form_submit_button("▶️ Gerar")

if submit:
    # Converte datas
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt   = datetime.combine(end_date,   datetime.max.time())
    lat, lon = station_coords[station]

    st.header(f"📍 {station.title()} | {start_date} → {end_date} | Raio: {radius_km} km")

    # Spinner durante processamento
    with st.spinner('🔄 Carregando dados e gerando visualizações...'):
        mapa, lags_df, df_merge = main(lat, lon, radius_km, station, start_dt, end_dt)
    st.success('✅ Carregamento concluído!')

    # Mapa Interativo
    st.subheader("🌐 Mapa Interativo")
    map_html = mapa.get_root().render()
    components.html(map_html, width=1300, height=600)

    # Gráficos lado a lado
    st.subheader("📈 Gráficos de Correlação e Scatter")
    col1, col2 = st.columns(2)
    with col1:
        fig1, ax1 = plt.subplots(figsize=(6,4))
        ax1.plot(lags_df['Lag'], lags_df['Correlation'], marker='o', linestyle='-')
        ax1.set_title("Correlação vs Defasagem (Lag ≥ 0)")
        ax1.set_xlabel("Dias de Defasagem")
        ax1.set_ylabel("r de Pearson")
        ax1.grid(True)
        st.pyplot(fig1)
    with col2:
        fig2, ax2 = plt.subplots(figsize=(6,4))
        ax2.scatter(df_merge['num_queimadas'], df_merge['pm25'])
        ax2.set_title("Scatter Queimadas vs PM2.5")
        ax2.set_xlabel("Número de Queimadas")
        ax2.set_ylabel("PM2.5 (µg/m³)")
        ax2.grid(True)
        st.pyplot(fig2)

    # Tabela e download CSV
    with st.expander("🔍 Tabela de Correlações"):
        st.dataframe(lags_df, use_container_width=True)
        csv = lags_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Baixar CSV", data=csv, file_name="correlacao_lags.csv")
