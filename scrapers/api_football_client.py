import urllib.request
import json
import sqlite3
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.storage import get_connection, init_db
from engine.data_validator import log_validation_error

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

# Competiciones exclusivas reservadas a API-Football (Segunda España, Serie B Italia, MLS EEUU)
API_FOOTBALL_LEAGUE_MAP = {
    "soccer_spain_segunda": {"id": 141, "name": "La Liga Hypermotion", "country": "Spain"},
    "soccer_italy_serie_b": {"id": 136, "name": "Serie B", "country": "Italy"},
    "soccer_usa_mls": {"id": 253, "name": "Major League Soccer", "country": "USA"}
}

def load_env():
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v.strip()

def init_cache_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS api_cache (
            endpoint TEXT,
            params TEXT,
            response_json TEXT,
            fetched_at DATETIME,
            PRIMARY KEY (endpoint, params)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS resolved_league_ids (
            league_key TEXT PRIMARY KEY,
            api_id INTEGER,
            league_name TEXT,
            country TEXT,
            resolved_at DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def parse_season_year_af(season_str):
    s = str(season_str)
    if "2026" in s:
        return "2026"
    elif "2025" in s:
        return "2025"
    elif "2024" in s:
        return "2024"
    return "2026"

class APIFootballClient:
    def __init__(self, api_key=None):
        load_env()
        self.api_key = api_key or os.getenv("APIFOOTBALL_KEY") or os.getenv("API_FOOTBALL_KEY") or ""
        init_cache_db()

    def _get_cache(self, endpoint, params_str, ttl_hours=12):
        conn = get_connection()
        c = conn.cursor()
        c.execute('SELECT response_json, fetched_at FROM api_cache WHERE endpoint = ? AND params = ?', (endpoint, params_str))
        row = c.fetchone()
        conn.close()
        
        if row:
            resp_json, fetched_at_str = row
            try:
                fetched_at = datetime.datetime.fromisoformat(fetched_at_str)
                if "season=2024" in params_str or (datetime.datetime.now() - fetched_at).total_seconds() < ttl_hours * 3600:
                    return json.loads(resp_json)
            except Exception:
                pass
        return None

    def _set_cache(self, endpoint, params_str, data):
        conn = get_connection()
        c = conn.cursor()
        now_str = datetime.datetime.now().isoformat()
        c.execute('''
            INSERT OR REPLACE INTO api_cache (endpoint, params, response_json, fetched_at)
            VALUES (?, ?, ?, ?)
        ''', (endpoint, params_str, json.dumps(data), now_str))
        conn.commit()
        conn.close()

    def fetch_api(self, endpoint, params_dict=None):
        params_dict = params_dict or {}
        params_str = "&".join(f"{k}={v}" for k, v in sorted(params_dict.items()))
        
        cached_data = self._get_cache(endpoint, params_str)
        if cached_data:
            return cached_data

        if not self.api_key:
            print(f"⚠️ API-Football: Clave APIFOOTBALL_KEY no disponible en entorno.")
            return None

        url = f"{API_FOOTBALL_BASE}/{endpoint}?{params_str}"
        headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": self.api_key,
            "x-apisports-key": self.api_key,
            "User-Agent": "BetAI/3.0"
        }
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data and "errors" in data and data["errors"]:
                        err_msg = str(data["errors"])
                        if "plan" in err_msg.lower():
                            log_validation_error(f"API-Football Plan Restriction for {endpoint}?{params_str}: {err_msg}")
                    if data:
                        self._set_cache(endpoint, params_str, data)
                        return data
        except Exception as e:
            print(f"⚠️ Error conectando con API-Football ({url}): {e}")
            
        return None

    def resolve_league_id(self, league_key):
        conn = get_connection()
        c = conn.cursor()
        c.execute('SELECT api_id FROM resolved_league_ids WHERE league_key = ?', (league_key,))
        row = c.fetchone()
        if row:
            conn.close()
            return row[0]

        info = API_FOOTBALL_LEAGUE_MAP.get(league_key)
        if not info:
            conn.close()
            return None

        data = self.fetch_api("leagues", {"name": info["name"], "country": info["country"]})
        resolved_id = info["id"]
        
        if data and "response" in data and len(data["response"]) > 0:
            try:
                resolved_id = data["response"][0]["league"]["id"]
            except Exception:
                pass

        c.execute('''
            INSERT OR REPLACE INTO resolved_league_ids (league_key, api_id, league_name, country, resolved_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (league_key, resolved_id, info["name"], info["country"], datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()

        return resolved_id

    def get_standings(self, league_key, season="2026"):
        league_id = self.resolve_league_id(league_key)
        if not league_id:
            return None

        year = parse_season_year_af(season)
        return self.fetch_api("standings", {"league": league_id, "season": year})

    def get_fixtures(self, league_key, season="2026"):
        league_id = self.resolve_league_id(league_key)
        if not league_id:
            return None

        year = parse_season_year_af(season)
        return self.fetch_api("fixtures", {"league": league_id, "season": year})
