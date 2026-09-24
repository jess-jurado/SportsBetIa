import datetime
import sqlite3
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.storage import get_connection, init_db
from scrapers.api_football_client import APIFootballClient
from engine.team_verifier import normalize_team_name, calculate_season_from_date
from engine.data_validator import validate_match_record, clean_and_normalize_match

DAILY_REQUEST_BUDGET = 20  # Límite seguro diario de peticiones para dejar 80 libres

def init_progress_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS ingestion_progress (
            league_key TEXT,
            season_param TEXT,
            status TEXT,
            last_run DATETIME,
            requests_used INTEGER,
            PRIMARY KEY (league_key, season_param)
        )
    ''')
    conn.commit()
    conn.close()

def run_gradual_ingestion():
    """
    Tarea de Ingesta Gradual Programada (Scheduled Job / Tarea en Segundo Plano).
    Consume hasta un máximo configurable (20 req/día) de la cuota diaria de API-Football
    para ir completando progresivamente los datos de Segunda, Serie B y MLS.
    La temporada real de cada partido se calcula dinámicamente desde su fecha con calculate_season_from_date.
    """
    init_progress_db()
    conn = get_connection()
    c = conn.cursor()

    client = APIFootballClient()

    targets = [
        ("soccer_spain_segunda", "2024"),
        ("soccer_italy_serie_b", "2024"),
        ("soccer_usa_mls", "2024"),
        ("soccer_spain_segunda", "2025"),
        ("soccer_italy_serie_b", "2025"),
        ("soccer_usa_mls", "2025")
    ]

    req_count = 0

    print("🚀 Iniciando tarea de Ingesta Gradual Programada (Tope diario: 20 req)...")

    for league_key, season_param in targets:
        if req_count >= DAILY_REQUEST_BUDGET:
            print("🛑 Límite diario de ingesta gradual alcanzado (20 peticiones). Guardando progreso.")
            break

        c.execute("SELECT status FROM ingestion_progress WHERE league_key=? AND season_param=?", (league_key, season_param))
        row = c.fetchone()

        if row and row[0] == "COMPLETED":
            continue

        print(f"📡 Ingesta Gradual: Procesando {league_key} (parámetro {season_param})...")
        payload = client.get_fixtures(league_key, season_param)
        req_count += 1

        if payload and "response" in payload:
            matches_list = payload["response"]
            inserted_count = 0

            for item in matches_list:
                try:
                    f_info = item.get("fixture", {})
                    t_info = item.get("teams", {})
                    g_info = item.get("goals", {})

                    date_str = f_info.get("date", "2026-08-16T20:00:00+00:00")
                    dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))

                    h = normalize_team_name(t_info.get("home", {}).get("name", ""))
                    a = normalize_team_name(t_info.get("away", {}).get("name", ""))
                    hs = g_info.get("home")
                    aws = g_info.get("away")

                    status_short = f_info.get("status", {}).get("short", "NS")
                    status = "FINISHED" if status_short in ["FT", "AET", "PEN"] else "SCHEDULED"

                    # Temporada Canónica basada estrictamente en la fecha real del partido
                    real_season = calculate_season_from_date(dt, league_key)

                    m_obj = {
                        "date": dt, "sport": "Football", "league": league_key, "season": real_season,
                        "home_team": h, "away_team": a, "home_score": hs, "away_score": aws,
                        "status": status, "source": "API-Football-Gradual"
                    }

                    if validate_match_record(m_obj):
                        cleaned = clean_and_normalize_match(m_obj)
                        match_id = f"GRAD_{real_season}_{league_key}_{f_info.get('id', inserted_count+1)}"
                        
                        c.execute("""
                            INSERT OR REPLACE INTO matches
                            (id, date, sport, league, season, home_team, away_team, home_score, away_score, status, winner)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (match_id, cleaned["date"], cleaned["sport"], cleaned["league"], cleaned["season"],
                              cleaned["home_team"], cleaned["away_team"], cleaned["home_score"], cleaned["away_score"],
                              cleaned["status"], cleaned["winner"]))
                        inserted_count += 1
                except Exception as ex:
                    pass

            c.execute("""
                INSERT OR REPLACE INTO ingestion_progress (league_key, season_param, status, last_run, requests_used)
                VALUES (?, ?, ?, ?, ?)
            """, (league_key, season_param, "COMPLETED", datetime.datetime.now().isoformat(), req_count))
            conn.commit()
            print(f"  ✅ Guardados {inserted_count} partidos en DB para {league_key} ({season_param}).")

    conn.close()
    print("✨ Tarea de Ingesta Gradual completada.")

if __name__ == "__main__":
    run_gradual_ingestion()
