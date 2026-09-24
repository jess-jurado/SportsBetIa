import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import time
import os
import datetime
import asyncio

from engine.storage import (
    init_db, get_matches_df, get_odds_drift_df, 
    get_team_stats_df, get_ml_performance_df, get_team_matches_df, get_connection
)
from engine.ml_model import train_hybrid_model
from engine.analytics import calculate_overround_margin, calculate_fair_probabilities, calculate_market_dispersion
from engine.data_generator import generate_benchmark_dataset

# 1. Asegurar base de datos inicializada
init_db()

# Verificar si la base de datos tiene datos o necesita inicializacion benchmark
df_init_check = get_matches_df(limit=5)
if df_init_check.empty:
    generate_benchmark_dataset()

# Configuracion de pagina Streamlit
st.set_page_config(
    page_title="BetAI Data Hub - Sports Analytics Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo Personalizado Dark Pro Showcase & Responsive Tuning
st.markdown("""
<style>
    .stApp, [data-testid="stAppViewContainer"], .main .block-container { background-color: #05070A !important; }
    section[data-testid="stSidebar"] { background-color: #0B0E14 !important; border-right: 1px solid #1F2937; }
    
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    }
    div[data-testid="stMetricLabel"] p { font-size: 0.85rem !important; color: #94A3B8 !important; font-weight: 600 !important; }
    div[data-testid="stMetricValue"] { font-size: 1.9rem !important; font-weight: 800 !important; color: #38BDF8 !important; }
    
    .stButton>button {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: 1px solid #0EA5E9 !important;
        background: #0284C7 !important;
        color: #FFFFFF !important;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        background: #0369A1 !important;
        border-color: #38BDF8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #1E293B; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #94A3B8;
        border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: #38BDF8 !important;
        background-color: #0F172A !important;
        border-bottom: 2px solid #38BDF8 !important;
    }
    
    h1, h2, h3, h4, h5 { color: #F8FAFC !important; font-family: 'Inter', sans-serif; }
    p, span, label { color: #CBD5E1 !important; }

    /* Estilos de cursor de mano y eliminación del parpadeo de texto en desplegables */
    div[data-baseweb="select"], div[data-baseweb="select"] * {
        cursor: pointer !important;
    }
    div[data-baseweb="select"] input {
        cursor: pointer !important;
        caret-color: transparent !important;
    }
    div[data-testid="stSelectbox"] div[role="combobox"] {
        cursor: pointer !important;
    }

    /* Adaptación 100% Responsive para móviles y tablets */
    @media (max-width: 768px) {
        .main .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
        div[data-testid="stMetricLabel"] p { font-size: 0.75rem !important; }
        .stTabs [data-baseweb="tab"] { padding: 6px 10px !important; font-size: 0.8rem !important; }
    }
</style>
""", unsafe_allow_html=True)

LEAGUE_LABELS = {
    "Todos": "🌍 Todas las Ligas",
    "soccer_spain_la_liga": "🇪🇸 España - La Liga EA Sports (football-data.org)",
    "soccer_spain_segunda": "🇪🇸 España - La Liga Hypermotion (API-Football)",
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra - Premier League (football-data.org)",
    "soccer_england_championship": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra - Championship (football-data.org)",
    "soccer_italy_serie_a": "🇮🇹 Italia - Serie A (football-data.org)",
    "soccer_italy_serie_b": "🇮🇹 Italia - Serie B (API-Football)",
    "soccer_germany_bundesliga": "🇩🇪 Alemania - Bundesliga (football-data.org)",
    "soccer_france_ligue_one": "🇫🇷 Francia - Ligue 1 (football-data.org)",
    "soccer_portugal_primeira_liga": "🇵🇹 Portugal - Primeira Liga (football-data.org)",
    "soccer_usa_mls": "🇺🇸 EE. UU. - Major League Soccer (API-Football)"
}

STATUS_TRANSLATIONS = {
    "SCHEDULED": "Programado",
    "FINISHED": "Finalizado",
    "TIMED": "Programado",
    "IN_PLAY": "En Juego",
    "PAUSED": "Descanso",
    "POSTPONED": "Aplazado",
    "SUSPENDED": "Suspendido",
    "CANCELLED": "Cancelado"
}

FEATURE_NAMES_MAP = {
    "odd_home": "Cuota Victoria Local",
    "odd_draw": "Cuota Empate",
    "odd_away": "Cuota Victoria Visitante",
    "overround": "Margen Comercial (Overround %)",
    "elo_diff": "Diferencia Rating Elo",
    "form_diff": "Diferencia de Forma Reciente",
    "implied_prob_home": "Probabilidad Implícita Local"
}

# ═══ SIDEBAR CONTROL ═══
st.sidebar.image("https://img.icons8.com/fluency/96/analytics.png", width=64)
st.sidebar.markdown("## ⚡ BetAI Analytics Hub")
st.sidebar.caption("Plataforma de Inteligencia Predictiva y Analítica Deportiva")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎛️ Filtros de Control")

from engine.storage import get_available_seasons_for_league

selected_league_key = st.sidebar.selectbox(
    "Seleccionar Liga",
    options=list(LEAGUE_LABELS.keys()),
    format_func=lambda x: LEAGUE_LABELS[x]
)

# Consulta dinámica de temporadas reales indexadas para la liga seleccionada
available_seasons = sorted(get_available_seasons_for_league(selected_league_key), reverse=True)

# Si la liga tiene temporada 2026-27 disponible en la API (football-data.org) pero aún no se ha ingerido, agregarla a las opciones prioritarias
if selected_league_key in ["soccer_spain_la_liga", "soccer_epl", "soccer_england_championship", "soccer_italy_serie_a", "soccer_germany_bundesliga", "soccer_france_ligue_one"]:
    if "2026-27" not in available_seasons:
        available_seasons.insert(0, "2026-27")

SEASON_FRIENDLY_LABELS = {
    "2026-27": "⚽ Temporada 2026-27 (En Curso)",
    "2025-26": "📜 Temporada 2025-26 (Reciente)",
    "2024-25": "📜 Temporada 2024-25 (Histórico)",
    "2024": "📜 Temporada 2024 (MLS)"
}

if not available_seasons:
    selected_season_key = None
    st.sidebar.warning("⚠️ No hay temporadas con datos indexados para esta liga.")
else:
    options_season = available_seasons + (["Todas"] if len(available_seasons) > 1 else [])
    selected_season_key = st.sidebar.selectbox(
        "Seleccionar Temporada Disponible",
        options=options_season,
        index=0,
        format_func=lambda s: SEASON_FRIENDLY_LABELS.get(s, f"📅 Temporada {s}" if s != "Todas" else "🌍 Todas las Temporadas")
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<div style='font-size:0.75rem; color:#64748B; text-align:center;'>BetAI Data Hub v3.0<br>© 2026 Jesus G.Jurado</div>",
    unsafe_allow_html=True
)

# Cargar Datos Clave
df_matches = get_matches_df(league=selected_league_key if selected_league_key != "Todos" else None, season=selected_season_key)
df_teams = get_team_stats_df(league=selected_league_key if selected_league_key != "Todos" else None, season=selected_season_key)

# Header Principal & Cabecera Visible de Contexto
st.markdown(f"# 📊 BetAI Sports Analytics Platform")
st.caption("Motor agnóstico de analítica deportiva impulsado por extracción dinámica de proveedores de datos externos.")

# Cabecera Fija de Contexto del Dashboard
league_label = LEAGUE_LABELS.get(selected_league_key, selected_league_key)

if selected_season_key == "2026-27":
    season_badge = "<span style='background:#065F46; color:#34D399; padding:5px 14px; border-radius:14px; font-weight:800; font-size:0.9rem;'>⚽ 2026-27 · En curso</span>"
elif selected_season_key == "2025-26":
    season_badge = "<span style='background:#1E293B; color:#94A3B8; padding:5px 14px; border-radius:14px; font-weight:700; font-size:0.9rem;'>📜 2025-26 · Histórico Reciente</span>"
elif selected_season_key == "2024-25":
    season_badge = "<span style='background:#1E293B; color:#94A3B8; padding:5px 14px; border-radius:14px; font-weight:700; font-size:0.9rem;'>📜 2024-25 · Histórico</span>"
elif selected_season_key == "2024":
    season_badge = "<span style='background:#1E293B; color:#94A3B8; padding:5px 14px; border-radius:14px; font-weight:700; font-size:0.9rem;'>📜 2024 · MLS</span>"
elif selected_season_key == "Todas":
    season_badge = "<span style='background:#0F172A; color:#38BDF8; padding:5px 14px; border-radius:14px; font-weight:700; font-size:0.9rem;'>🌍 Todas las Temporadas</span>"
else:
    season_badge = f"<span style='background:#1E293B; color:#94A3B8; padding:5px 14px; border-radius:14px; font-weight:700; font-size:0.9rem;'>📅 Temporada {selected_season_key}</span>"

provider_notice = ""
if selected_league_key in ["soccer_spain_segunda", "soccer_italy_serie_b", "soccer_usa_mls"] and selected_season_key in ["2026-27", "2026"]:
    provider_notice = "<div style='font-size:0.85rem; background:#451A03; color:#FDBA74; padding:8px 14px; border-radius:8px; margin-top:10px; border:1px solid #78350F;'>⚠️ Datos en curso no disponibles (Plan Gratuito API-Football). Mostrando histórico disponible.</div>"
elif selected_league_key == "soccer_portugal_primeira_liga":
    provider_notice = "<div style='font-size:0.85rem; background:#451A03; color:#FDBA74; padding:8px 14px; border-radius:8px; margin-top:10px; border:1px solid #78350F;'>⚠️ Liga no disponible en el plan gratuito de la fuente de datos.</div>"

header_html = f"""
<div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); padding: 20px 24px; border-radius: 12px; border: 1px solid #334155; margin-top: 10px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        <div style="font-size: 1.4rem; font-weight: 800; color: #F8FAFC;">
            {league_label}
        </div>
        <div>
            {season_badge}
        </div>
    </div>
    {provider_notice}
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

# ═══ TAB CONTROL ═══
tab_overview, tab_drift, tab_teams, tab_ml = st.tabs([
    "🌐 Executive Overview", 
    "📈 Market Drift & Odds", 
    "⚽ Team & Match Explorer", 
    "🧠 ML Predictive Intelligence"
])

# ---------------------------------------------------------
# TAB 1: EXECUTIVE OVERVIEW
# ---------------------------------------------------------
with tab_overview:
    st.markdown("### 📈 Indicadores Clave del Sistema (KPIs)")
    
    total_matches = len(df_matches)
    finished_matches = len(df_matches[df_matches['status'] == 'FINISHED']) if not df_matches.empty else 0
    avg_overround = round(df_matches['avg_overround'].mean(), 2) if not df_matches.empty and 'avg_overround' in df_matches.columns else 4.2
    
    # Entrenar ML rápido para métricas
    _, _, ml_metrics, _ = train_hybrid_model()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🏟️ Partidos Indexados", f"{total_matches:,}", delta=f"{finished_matches} Finalizados")
    kpi2.metric("📊 Margen Comercial Medio", f"{avg_overround}%", delta="Overround Vig")
    kpi3.metric("🎯 Precisión Modelo (XGBoost)", f"{ml_metrics['accuracy']*100:.1f}%", delta=f"AUC: {ml_metrics['roc_auc']}")
    kpi4.metric("⚡ Muestras Analizadas", f"{ml_metrics['sample_count']:,}", delta="Live SQLite Pipeline")

    st.markdown("---")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("##### 🏦 Margen Comercial Medio (Vig %) por Casa de Apuestas")
        df_drift = get_odds_drift_df(limit=1000)
        if not df_drift.empty:
            vig_by_bookie = df_drift.groupby('bookmaker')['overround'].mean().reset_index()
            fig_vig = px.bar(
                vig_by_bookie, 
                x='bookmaker', 
                y='overround',
                labels={'bookmaker': 'Casa de Apuestas', 'overround': 'Margen (%)'},
                color='overround',
                color_continuous_scale='Blues'
            )
            fig_vig.update_layout(template="plotly_dark", height=320, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_vig, use_container_width=True)
        else:
            st.info("Cargando datos de casas de apuestas...")

    with col_chart2:
        st.markdown("##### 🏆 Distribución de Partidos por Liga")
        if not df_matches.empty:
            league_counts = df_matches['league'].map(lambda x: LEAGUE_LABELS.get(x, x)).value_counts().reset_index()
            league_counts.columns = ['Liga', 'Partidos']
            fig_pie = px.pie(
                league_counts, 
                names='Liga', 
                values='Partidos', 
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Darkmint
            )
            fig_pie.update_layout(template="plotly_dark", height=320, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("##### 📋 Partidos Recientes Indexados")
    if not df_matches.empty:
        display_df = df_matches[['date', 'league', 'home_team', 'away_team', 'status', 'avg_odd_home', 'avg_odd_draw', 'avg_odd_away', 'avg_overround']].copy()
        display_df['league'] = display_df['league'].map(lambda x: LEAGUE_LABELS.get(x, x))
        display_df['status'] = display_df['status'].map(lambda x: STATUS_TRANSLATIONS.get(str(x).upper(), str(x)))
        display_df.columns = ['Fecha', 'Liga', 'Local', 'Visitante', 'Estado', 'Cuota Local', 'Cuota Empate', 'Cuota Visitante', 'Margen (%)']
        st.dataframe(display_df.head(15), use_container_width=True, height=260)

# ---------------------------------------------------------
# TAB 2: MARKET DRIFT & ODDS VISUALIZER
# ---------------------------------------------------------
with tab_drift:
    st.markdown("### 📈 Variación Temporal de Cuotas (Odds Drift & Dispersión)")
    st.caption("Visualiza cómo oscilan las cuotas entre diferentes casas de apuestas antes del evento.")
    
    if not df_matches.empty:
        match_options = {
            f"{row['home_team']} vs {row['away_team']} ({str(row['date'])[:10]})": row['id']
            for _, row in df_matches.iterrows()
        }
        selected_match_label = st.selectbox("Seleccionar Partido para Análisis de Mercado", list(match_options.keys()))
        selected_match_id = match_options[selected_match_label]
        
        df_match_drift = get_odds_drift_df(match_id=selected_match_id)
        
        if not df_match_drift.empty:
            col_d1, col_d2 = st.columns([2, 1])
            
            with col_d1:
                st.markdown("##### ⏱️ Evolución Temporal de Cuota Local por Casa de Apuestas")
                fig_line = px.line(
                    df_match_drift, 
                    x='timestamp', 
                    y='odd_home', 
                    color='bookmaker',
                    markers=True,
                    labels={'timestamp': 'Fecha/Hora Snapshot', 'odd_home': 'Cuota Equipo Local', 'bookmaker': 'Casa'},
                    title="Evolución Cuota Victoria Local"
                )
                fig_line.update_layout(template="plotly_dark", height=380, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_line, use_container_width=True)

            with col_d2:
                st.markdown("##### 📦 Dispersión de Cuotas entre Casas")
                df_box_data = df_match_drift.rename(columns={
                    'odd_home': 'Cuota Local',
                    'odd_draw': 'Cuota Empate',
                    'odd_away': 'Cuota Visitante'
                })
                fig_box = px.box(
                    df_box_data, 
                    y=['Cuota Local', 'Cuota Empate', 'Cuota Visitante'],
                    labels={'variable': 'Mercado', 'value': 'Cuota Decimal'},
                    title="Rango y Cuartiles de Mercado"
                )
                fig_box.update_layout(template="plotly_dark", height=380, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_box, use_container_width=True)

            st.markdown("##### 🔍 Desglose Completo por Casa de Apuestas")
            df_drift_disp = df_match_drift[['timestamp', 'bookmaker', 'odd_home', 'odd_draw', 'odd_away', 'implied_prob_home', 'overround']].copy()
            df_drift_disp.columns = ['Fecha/Hora', 'Casa de Apuestas', 'Cuota Local', 'Cuota Empate', 'Cuota Visitante', 'Prob. Local', 'Margen (%)']
            st.dataframe(df_drift_disp, use_container_width=True)
        else:
            st.warning("No hay registros de cuotas temporales para este partido.")
    else:
        st.info("No hay partidos disponibles para la liga seleccionada.")

# ---------------------------------------------------------
# TAB 3: TEAM & MATCH EXPLORER
# ---------------------------------------------------------
with tab_teams:
    st.markdown("### ⚽ Explorador Estadístico de Equipos & Ratings")
    
    if not df_teams.empty:
        df_teams_clean = df_teams.drop_duplicates(subset=['team_name']).copy()
        col_t1, col_t2 = st.columns([1, 2])
        
        with col_t1:
            st.markdown("##### 🏆 Ranking Elo Rating de Equipos")
            fig_elo = px.bar(
                df_teams_clean.sort_values(by="elo_rating", ascending=True), 
                y='team_name', 
                x='elo_rating', 
                orientation='h',
                color='elo_rating',
                color_continuous_scale='Tealgrn',
                labels={'team_name': 'Equipo', 'elo_rating': 'Elo Rating'}
            )
            fig_elo.update_layout(template="plotly_dark", height=450, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_elo, use_container_width=True)

        with col_t2:
            st.markdown("##### 🔍 Ficha de Rendimiento por Equipo")
            selected_team = st.selectbox("Seleccionar Equipo", sorted(df_teams_clean['team_name'].unique()))
            team_row = df_teams_clean[df_teams_clean['team_name'] == selected_team].iloc[0]
            
            tm1, tm2, tm3, tm4, tm5 = st.columns(5)
            tm1.metric("⭐ Rating Elo", f"{team_row['elo_rating']:.1f}")
            tm2.metric("🔥 Score Forma", f"{team_row['form_score']*100:.0f}%")
            tm3.metric("⚽ Goles A Favor", f"{team_row['goals_scored']}")
            tm4.metric("🛡️ Goles En Contra", f"{team_row['goals_conceded']}")
            gd = team_row['goals_scored'] - team_row['goals_conceded']
            tm5.metric("📊 Dif. Goles", f"{'+' if gd > 0 else ''}{gd}")
            
            st.markdown(f"###### 🏟️ Partidos y Resultados Oficiales de {selected_team}")
            team_matches = get_team_matches_df(selected_team, season=selected_season_key)
            if not team_matches.empty:
                team_matches['date_fmt'] = team_matches['date'].astype(str).str[:10]
                team_matches['marcador'] = team_matches.apply(
                    lambda r: f"{int(r['home_score'])} - {int(r['away_score'])}" if pd.notnull(r['home_score']) and pd.notnull(r['away_score']) else "Pendiente", 
                    axis=1
                )
                team_matches['total_goles'] = team_matches.apply(
                    lambda r: int(r['home_score'] + r['away_score']) if pd.notnull(r['home_score']) and pd.notnull(r['away_score']) else "-",
                    axis=1
                )
                team_matches['ganador_txt'] = team_matches['winner'].map({
                    'HOME': 'LOCAL', 'AWAY': 'VISITANTE', 'DRAW': 'EMPATE'
                }).fillna('PENDIENTE')
                
                df_finished = team_matches[team_matches['status'] == 'FINISHED'].copy()
                df_scheduled = team_matches[team_matches['status'] == 'SCHEDULED'].copy()
                
                st.markdown("##### 🏆 Partidos Finalizados con Marcadores Reales")
                if not df_finished.empty:
                    df_disp_finished = df_finished[['date_fmt', 'home_team', 'away_team', 'marcador', 'total_goles', 'ganador_txt']].copy()
                    df_disp_finished.columns = ['Fecha', 'Equipo Local', 'Equipo Visitante', 'Marcador Exacto', 'Total Goles', 'Ganador']
                    st.dataframe(df_disp_finished, use_container_width=True)
                else:
                    st.info("No hay partidos finalizados aún en esta temporada.")

                if not df_scheduled.empty:
                    with st.expander("📅 Próximos Partidos Programados"):
                        df_disp_scheduled = df_scheduled[['date_fmt', 'home_team', 'away_team']].copy()
                        df_disp_scheduled.columns = ['Fecha Programada', 'Equipo Local', 'Equipo Visitante']
                        st.dataframe(df_disp_scheduled, use_container_width=True)
            else:
                st.info(f"No hay partidos registrados para {selected_team} en la temporada seleccionada.")

# ---------------------------------------------------------
# TAB 4: ML PREDICTIVE INTELLIGENCE
# ---------------------------------------------------------
with tab_ml:
    st.markdown("### 🧠 Inteligencia Predictiva Machine Learning (XGBoost)")
    st.caption("Evaluación del modelo de IA entrenado para predecir probabilidades de resultado frente al mercado.")
    
    model, sample_count, metrics, feature_imp = train_hybrid_model()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🎯 Accuracy Score", f"{metrics['accuracy']*100:.2f}%")
    m2.metric("📈 ROC-AUC Score", f"{metrics['roc_auc']:.4f}")
    m3.metric("📉 Log Loss Metric", f"{metrics['log_loss']:.4f}")
    m4.metric("📦 Datos Entrenados", f"{metrics['sample_count']} Muestras")
    
    st.markdown("---")
    
    col_ml1, col_ml2 = st.columns(2)
    
    with col_ml1:
        st.markdown("##### 📊 Importancia de Variables en el Modelo (Feature Importance)")
        feature_imp_display = feature_imp.copy()
        feature_imp_display['Feature'] = feature_imp_display['Feature'].map(lambda x: FEATURE_NAMES_MAP.get(x, x))
        
        fig_feat = px.bar(
            feature_imp_display, 
            x='Importance', 
            y='Feature', 
            orientation='h',
            color='Importance',
            color_continuous_scale='Viridis',
            labels={'Importance': 'Importancia Relativa', 'Feature': 'Variable Explicativa'}
        )
        fig_feat.update_layout(template="plotly_dark", height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_feat, use_container_width=True)

    with col_ml2:
        st.markdown("##### 🎯 Calibración: Probabilidad IA vs Cuota Implícita")
        df_ml_perf = get_ml_performance_df()
        if not df_ml_perf.empty and 'prob_home' in df_ml_perf.columns:
            df_scatter_data = df_ml_perf.copy()
            df_scatter_data['Resultado IA'] = df_scatter_data['is_correct'].map({
                1: 'Predicción Acertada', 
                0: 'Predicción Fallada', 
                True: 'Predicción Acertada', 
                False: 'Predicción Fallada'
            }).fillna('En Proceso')

            fig_scatter = px.scatter(
                df_scatter_data, 
                x='prob_home', 
                y='value_edge',
                color='Resultado IA',
                hover_data=['home_team', 'away_team'],
                labels={'prob_home': 'Probabilidad Victoria Local (IA)', 'value_edge': 'Ventaja de Valor (Edge %)', 'Resultado IA': 'Resultado'},
                title="Distribución de Ventaja de Valor (Value Edge %)"
            )
            fig_scatter.update_layout(template="plotly_dark", height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("##### 📋 Predicciones de IA Recientes Registradas")
    df_ml_perf = get_ml_performance_df()
    if not df_ml_perf.empty:
        df_ml_disp = df_ml_perf[['date', 'home_team', 'away_team', 'predicted_outcome', 'prob_home', 'prob_draw', 'prob_away', 'value_edge', 'actual_outcome', 'is_correct']].copy()
        df_ml_disp['is_correct'] = df_ml_disp['is_correct'].map({1: '✓ Acertada', 0: '✗ Fallada', True: '✓ Acertada', False: '✗ Fallada'}).fillna('En Proceso')
        df_ml_disp.columns = ['Fecha', 'Local', 'Visitante', 'Predicción IA', 'Prob Local', 'Prob Empate', 'Prob Visitante', 'Ventaja (%)', 'Resultado Real', 'Estado IA']
        st.dataframe(df_ml_disp.head(15), use_container_width=True)
