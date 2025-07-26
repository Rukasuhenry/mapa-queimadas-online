# mapa_com_correlacao_v4.py
import os
import math
import datetime
import logging
import pandas as pd
import numpy as np
from pymongo import MongoClient
import folium
from folium.plugins import HeatMap
from branca.element import MacroElement
from jinja2 import Template
import matplotlib.pyplot as plt
from scipy.stats import pearsonr

#  Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Diretórios
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# MongoDB
MONGO_URI = os.getenv(
    "MONGO_URI_PRIMARY",
    "mongodb+srv://lhms:lhms123@clusterlhms.vpuaqlo.mongodb.net/qualidade_ar?retryWrites=true&w=majority"
)
TIMEOUT_MS = 5000  # ms

def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=TIMEOUT_MS)
    client.admin.command('ping')
    return client['qualidade_ar']

def detect_date_field(coll_name: str) -> str:
    db = get_db(); doc = db[coll_name].find_one()
    for k,v in doc.items():
        if isinstance(v, datetime.datetime):
            return k
    raise KeyError(f"Nenhum campo datetime em '{coll_name}'")

def carregar_dados_aqicn_mongo(station, start_date, end_date):
    db=get_db(); coll=db['air_quality']
    date_field=detect_date_field('air_quality')
    pipeline=[
        {"$match":{date_field:{"$gte":start_date,"$lte":end_date}}},
        {"$match":{"Estação":station}},
        {"$addFields":{"data":{"$dateToString":{"date":f"${date_field}","format":"%Y-%m-%d"}}}},
        {"$project":{"_id":0,"data":1,"pm25":"$ pm25"}},
        {"$sort":{"data":1}}
    ]
    df=pd.DataFrame(list(coll.aggregate(pipeline)))
    df['pm25']=pd.to_numeric(df['pm25'],errors='coerce')
    df['data']=pd.to_datetime(df['data'],errors='coerce').dt.date
    df.dropna(subset=['data','pm25'],inplace=True)
    logger.info(f"AQICN: {len(df)} registros após limpeza")
    return df

def carregar_dados_queimadas_raw(lat,lon,radius_km,start_date,end_date):
    db=get_db(); coll=db['focos_incendio']
    date_field=detect_date_field('focos_incendio')
    dlat=radius_km/111.32; dlon=radius_km/(111.32*math.cos(math.radians(lat)))
    pipeline=[
        {"$match":{date_field:{"$gte":start_date,"$lte":end_date}}},
        {"$match":{
            "latitude":{"$gte":lat-dlat,"$lte":lat+dlat},
            "longitude":{"$gte":lon-dlon,"$lte":lon+dlon}
        }},
        {"$addFields":{"data":{"$dateToString":{"date":f"${date_field}","format":"%Y-%m-%d"}}}},
        {"$project":{"_id":0,"latitude":1,"longitude":1,"data":1}}
    ]
    df=pd.DataFrame(list(coll.aggregate(pipeline)))
    df['data']=pd.to_datetime(df['data'],errors='coerce').dt.date
    
    def hav(lat1,lon1,lat2,lon2):
        R=6371.0
        φ1,φ2 = map(math.radians,(lat1,lat2))
        Δφ = math.radians(lat2-lat1)
        Δλ = math.radians(lon2-lon1)
        a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    df['distancia']=df.apply(lambda r: hav(lat,lon,r['latitude'],r['longitude']),axis=1)
    df=df[df['distancia']<=radius_km]
    df['num_queimadas']=1
    logger.info(f"Queimadas raw: {len(df)} registros dentro de {radius_km} km")
    return df

def agregar_dados_queimadas(df_raw):
    df=df_raw.groupby('data',as_index=False)['num_queimadas'].sum()
    logger.info(f"Queimadas agregadas: {len(df)} dias")
    return df

def compute_lagged_correlation(df, lag_range=5):
    results=[]
    for lag in range(0, lag_range+1):
        x=df['num_queimadas']
        y=df['pm25'].shift(lag)
        valid=(~x.isna()) & (~y.isna())
        if valid.sum()>2:
            r,_=pearsonr(x[valid], y[valid])
            results.append((lag, r))
    return pd.DataFrame(results, columns=['Lag','Correlation']).sort_values('Lag')

def gerar_mapa(lat,lon,df_raw,correlacao_pm25,media_pm25):
    m=folium.Map([lat,lon],zoom_start=6,control_scale=True)
    data_heat=list(zip(df_raw['latitude'],df_raw['longitude'],df_raw['num_queimadas']))
    HeatMap(data_heat,radius=20,max_zoom=10).add_to(m)
    popup=(f"<strong>Local</strong><br>Lat:{lat},Lon:{lon}<br>"
           f"PM2.5 méd:{media_pm25:.2f}")
    folium.Marker([lat,lon],popup=popup,
                  icon=folium.Icon(color='red')).add_to(m)
    top100 = (
        df_raw.groupby(['latitude','longitude'],as_index=False)
              .agg(num_queimadas=('num_queimadas','sum'),
                   distancia=('distancia','mean'))
              .nlargest(100,'num_queimadas')
    )
    for _,r in top100.iterrows():
        folium.Marker([r['latitude'],r['longitude']],
            popup=f"Queimadas:{r['num_queimadas']}<br>Dist:{r['distancia']:.2f}km",
            icon=folium.Icon(color='orange',icon='fire',prefix='fa')
        ).add_to(m)
    legend=Template("""
    {% macro html(this,kwargs) %}
    <div style="position:fixed;top:10px;left:10px;
                background:white;padding:8px;box-shadow:2px 2px 8px rgba(0,0,0,0.3);">
        🔥 HeatMap &nbsp;&nbsp;📍 Centro&nbsp;&nbsp;◉ Top100
    </div>
    {% endmacro %}
    """)
    macro=MacroElement(); macro._template=legend
    m.get_root().add_child(macro)
    return m

def main(lat,lon,radius_km,station,start_date,end_date):
    df_aq = carregar_dados_aqicn_mongo(station,start_date,end_date)
    df_raw = carregar_dados_queimadas_raw(lat,lon,radius_km,start_date,end_date)
    df_q  = agregar_dados_queimadas(df_raw)
    df_merge = pd.merge(df_aq,df_q,on='data')
    media = df_merge['pm25'].mean()
    corr  = df_merge['pm25'].corr(df_merge['num_queimadas'])

    # Detrending
    df_merge['pm25_detrended']         = df_merge['pm25'] - df_merge['pm25'].rolling(3,center=True).mean()
    df_merge['num_queimadas_detrended']= df_merge['num_queimadas'] - df_merge['num_queimadas'].rolling(3,center=True).mean()
    df_det = df_merge[['data','pm25_detrended','num_queimadas_detrended']].dropna()
    df_det.columns = ['data','pm25','num_queimadas']

    # Correlação lag ≥ 0
    lags_df = compute_lagged_correlation(df_det, lag_range=5)

    # Gera mapa
    mapa = gerar_mapa(lat,lon,df_raw,corr,media)

    # Retorna objetos para o App
    return mapa, lags_df, df_merge
