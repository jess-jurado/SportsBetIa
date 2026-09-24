import sqlite3
import datetime
import os
import pandas as pd

DB_PATH = "bet_data.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Tabla masiva para todos los escaneos
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            target_a TEXT,
            odd_a_1 REAL,
            odd_a_2 REAL,
            target_b TEXT,
            odd_b_1 REAL,
            odd_b_2 REAL,
            arbitrage_found BOOLEAN,
            margin REAL
        )
    ''')
    
    # EXPERIMENTAL MIGRATION (Inyeccion sin perdidas para BD existente)
    try:
        c.execute('ALTER TABLE scan_cycles ADD COLUMN event_name TEXT')
        c.execute('ALTER TABLE scan_cycles ADD COLUMN sport TEXT')
    except sqlite3.OperationalError:
        pass # La estructura ya esta consolidada.
    
    # 2. Tabla selectiva para las senales IA 
    c.execute('''
        CREATE TABLE IF NOT EXISTS historical_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            source_match TEXT,
            ai_probability REAL,
            kelly_stake REAL,
            odds_selected REAL,
            is_valid_edge BOOLEAN
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS telegram_alerts_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            event_name TEXT,
            league TEXT,
            margin REAL,
            total_stake REAL,
            markets_dump TEXT
        )
    ''')
    # 4. Tablas para Analítica Avanzada e Inteligencia Deportiva
    c.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY,
            date DATETIME,
            sport TEXT,
            league TEXT,
            season TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT,
            winner TEXT
        )
    ''')
    try:
        c.execute('ALTER TABLE matches ADD COLUMN season TEXT')
    except sqlite3.OperationalError:
        pass
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookmaker_odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            bookmaker TEXT,
            timestamp DATETIME,
            odd_home REAL,
            odd_draw REAL,
            odd_away REAL,
            implied_prob_home REAL,
            implied_prob_draw REAL,
            implied_prob_away REAL,
            overround REAL,
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS team_stats (
            team_name TEXT,
            sport TEXT,
            league TEXT,
            season TEXT,
            matches_played INTEGER,
            wins INTEGER,
            draws INTEGER,
            losses INTEGER,
            goals_scored INTEGER,
            goals_conceded INTEGER,
            form_score REAL,
            elo_rating REAL,
            PRIMARY KEY (team_name, league, season)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS ml_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            timestamp DATETIME,
            predicted_outcome TEXT,
            prob_home REAL,
            prob_draw REAL,
            prob_away REAL,
            value_edge REAL,
            actual_outcome TEXT,
            is_correct BOOLEAN
        )
    ''')
    conn.commit()
    conn.close()

def clean_old_records():
    """Auditoria y limpieza: Borra excesos mayores a 7 dias para evitar memory-bloating."""
    conn = get_connection()
    c = conn.cursor()
    past_date = datetime.datetime.now() - datetime.timedelta(days=7)
    c.execute('DELETE FROM scan_cycles WHERE timestamp < ?', (past_date,))
    c.execute('DELETE FROM historical_signals WHERE timestamp < ?', (past_date,))
    c.execute('DELETE FROM telegram_alerts_log WHERE timestamp < ?', (past_date,))
    conn.commit()
    conn.close()

def save_scan_cycle(data, arbitrage_found, margin, event_name="Unknown", sport="Unknown"):
    """Guarda un registro general del cruce interceptado."""
    if not data or len(data) < 2:
        return
        
    conn = get_connection()
    c = conn.cursor()
    
    t_a = data[0].get("source", "Unknown")
    o_a = data[0].get("odds", [0, 0])
    
    t_b = data[1].get("source", "Unknown")
    o_b = data[1].get("odds", [0, 0])

    c.execute('''
        INSERT INTO scan_cycles 
        (timestamp, target_a, odd_a_1, odd_a_2, target_b, odd_b_1, odd_b_2, arbitrage_found, margin, event_name, sport)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.datetime.now(), t_a, o_a[0], o_a[1], t_b, o_b[0], o_b[1], arbitrage_found, margin, event_name, sport))
    
    conn.commit()
    conn.close()

def save_historical_signal(source_match, prob, stake, odd, edge):
    """Graba el dictamen de Kelly y de la IA en la seccion historica maestra."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO historical_signals 
        (timestamp, source_match, ai_probability, kelly_stake, odds_selected, is_valid_edge)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (datetime.datetime.now(), source_match, prob, stake, odd, edge))
    
    conn.commit()
    conn.close()

def get_recent_signals(limit=50):
    """Recupera la tabla cruzada de senales para visualizar en Streamlit."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM historical_signals ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    cols = [description[0] for description in c.description]
    conn.close()
    return cols, rows

def get_analytics_data():
    """Genera matrices Pandas para construir Graficos en Dashoard y CLI."""
    conn = get_connection()
    
    # 1. Top 5 Ultimas 24H
    top_5 = pd.read_sql_query('''
        SELECT sport AS Liga, event_name AS Evento, MAX(margin) AS Margen 
        FROM scan_cycles 
        WHERE arbitrage_found = 1 AND timestamp >= datetime('now', '-1 day') AND sport IS NOT NULL
        GROUP BY event_name, sport
        ORDER BY Margen DESC 
        LIMIT 5
    ''', conn)
    
    # 2. Resumen Volumen x Deporte
    by_sport = pd.read_sql_query('''
        SELECT sport, COUNT(*) as count 
        FROM scan_cycles 
        WHERE arbitrage_found = 1 AND sport IS NOT NULL AND sport != 'Unknown'
        GROUP BY sport
    ''', conn)
    
    # 3. Heatmap Horario
    hourly = pd.read_sql_query('''
        SELECT strftime('%H', timestamp) as hora, AVG(margin) as avg_margin 
        FROM scan_cycles 
        WHERE arbitrage_found = 1
        GROUP BY hora
        ORDER BY hora
    ''', conn)
    
    conn.close()
    return top_5, by_sport, hourly

def log_telegram_alert(event_name, league, margin, total_stake, markets_dump):
    """Guarda un registro de un mensaje Telegram enviado exitosamente."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO telegram_alerts_log 
        (timestamp, event_name, league, margin, total_stake, markets_dump)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (datetime.datetime.now(), event_name, league, margin, total_stake, str(markets_dump)))
    conn.commit()
    conn.close()

def get_telegram_logs(limit=20):
    """Devuelve las ultimas N alertas enviadas a Telegram."""
    conn = get_connection()
    df = pd.read_sql_query('''
        SELECT timestamp AS Fecha, event_name AS Evento, league AS Liga, margin AS Margen, total_stake AS Stake, markets_dump AS Desglose
        FROM telegram_alerts_log
        ORDER BY timestamp DESC
        LIMIT ?
    ''', conn, params=(limit,))
    conn.close()
    return df

def save_active_bet(alert_id, event_name, league, stake, margin, event_date):
    """Persiste una apuesta ejecutada en SQLite."""
    conn = get_connection()
    c = conn.cursor()
    roi = round(margin, 2) if margin else 0
    try:
        c.execute('''
            INSERT OR IGNORE INTO active_bets (executed_at, alert_id, event_name, league, stake, margin, event_date, roi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.datetime.now(), alert_id, event_name, league, stake, margin, event_date, roi))
        conn.commit()
    except: pass
    conn.close()

def get_active_bets():
    """Recupera todas las apuestas ejecutadas."""
    conn = get_connection()
    try:
        df = pd.read_sql_query('''
            SELECT executed_at AS "Fecha Ejecución", event_name AS Evento, league AS Liga, 
                   stake AS "Inversión (€)", margin AS "Margen (%)", event_date AS "Fecha Evento", roi AS "ROI (%)"
            FROM active_bets ORDER BY executed_at DESC
        ''', conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def bet_exists(alert_id):
    """Verifica si una apuesta ya fue ejecutada (idempotencia)."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT COUNT(*) FROM active_bets WHERE alert_id = ?', (alert_id,))
        count = c.fetchone()[0]
    except:
        count = 0
    conn.close()
    return count > 0

def get_total_invested():
    """Suma total de stakes en active_bets para recalcular bankroll."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT COALESCE(SUM(stake), 0) FROM active_bets')
        total = c.fetchone()[0]
    except:
        total = 0
    conn.close()
    return total

def get_matches_df(league=None, sport=None, season=None, limit=400):
    """Recupera listado de partidos con cuotas agregadas y filtro de temporada."""
    conn = get_connection()
    query = """
        SELECT m.id, m.date, m.sport, m.league, m.season, m.home_team, m.away_team, 
               m.home_score, m.away_score, m.status, m.winner,
               AVG(b.odd_home) as avg_odd_home, AVG(b.odd_draw) as avg_odd_draw, AVG(b.odd_away) as avg_odd_away,
               MIN(b.odd_home) as min_odd_home, MAX(b.odd_home) as max_odd_home,
               AVG(b.overround) as avg_overround
        FROM matches m
        LEFT JOIN bookmaker_odds b ON m.id = b.match_id
        WHERE 1=1
    """
    params = []
    if league and league != "Todos":
        query += " AND m.league = ?"
        params.append(league)
    if sport and sport != "Todos":
        query += " AND m.sport = ?"
        params.append(sport)
    if season and season != "Todas":
        query += " AND m.season = ?"
        params.append(season)
    query += " GROUP BY m.id ORDER BY m.date DESC LIMIT ?"
    params.append(limit)
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def get_odds_drift_df(match_id=None, limit=500):
    """Recupera la serie temporal de variaciones de cuotas por casas de apuestas."""
    conn = get_connection()
    query = """
        SELECT b.id, b.match_id, b.bookmaker, b.timestamp, 
               b.odd_home, b.odd_draw, b.odd_away, 
               b.implied_prob_home, b.implied_prob_draw, b.implied_prob_away, b.overround,
               m.home_team, m.away_team, m.league
        FROM bookmaker_odds b
        JOIN matches m ON b.match_id = m.id
        WHERE 1=1
    """
    params = []
    if match_id:
        query += " AND b.match_id = ?"
        params.append(match_id)
    query += " ORDER BY b.timestamp ASC LIMIT ?"
    params.append(limit)
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def get_team_stats_df(league=None, season=None):
    """Recupera la tabla de clasificacion/metricas de equipos filtrada por liga y temporada."""
    conn = get_connection()
    query = "SELECT * FROM team_stats WHERE 1=1"
    params = []
    if league and league != "Todos":
        query += " AND league = ?"
        params.append(league)
    if season and season != "Todas":
        query += " AND season = ?"
        params.append(season)
    query += " ORDER BY elo_rating DESC"
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def get_ml_performance_df():
    """Recupera metricas de rendimiento del modelo predictivo."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("""
            SELECT p.*, m.home_team, m.away_team, m.league, m.date
            FROM ml_predictions p
            JOIN matches m ON p.match_id = m.id
            ORDER BY p.timestamp DESC
        """, conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def get_team_matches_df(team_name, season=None):
    """Recupera todos los partidos de un equipo especifico ordenando partidos finalizados con marcadores primero."""
    conn = get_connection()
    query = """
        SELECT id, date, sport, league, season, home_team, away_team, 
               home_score, away_score, status, winner
        FROM matches
        WHERE (home_team = ? OR away_team = ?)
    """
    params = [team_name, team_name]
    if season and season != "Todas":
        query += " AND season = ?"
        params.append(season)
    query += " ORDER BY CASE WHEN status = 'FINISHED' THEN 0 ELSE 1 END, date DESC"
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def get_available_seasons_for_league(league=None):
    """Recupera las temporadas reales que existen en la base de datos para una liga especifica."""
    conn = get_connection()
    c = conn.cursor()
    if league and league != "Todos":
        c.execute("SELECT DISTINCT season FROM matches WHERE league = ? UNION SELECT DISTINCT season FROM team_stats WHERE league = ? ORDER BY 1 DESC", (league, league))
    else:
        c.execute("SELECT DISTINCT season FROM matches UNION SELECT DISTINCT season FROM team_stats ORDER BY 1 DESC")
    seasons = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    return seasons


