import urllib.request
import json
import sqlite3
import datetime
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.storage import get_connection, init_db

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

# Mapeo oficial de competiciones asignadas a football-data.org
FD_COMPETITION_MAP = {
    "soccer_spain_la_liga": {"code": "PD", "name": "La Liga EA Sports", "country": "Spain"},
    "soccer_epl": {"code": "PL", "name": "Premier League", "country": "England"},
    "soccer_england_championship": {"code": "ELC", "name": "Championship", "country": "England"},
    "soccer_germany_bundesliga": {"code": "BL1", "name": "Bundesliga", "country": "Germany"},
    "soccer_italy_serie_a": {"code": "SA", "name": "Serie A", "country": "Italy"},
    "soccer_france_ligue_one": {"code": "FL1", "name": "Ligue 1", "country": "France"},
    "soccer_portugal_primeira_liga": {"code": "PPD", "name": "Primeira Liga", "country": "Portugal"}
}

# Throttling global: Máximo 10 peticiones por minuto (6 segundos entre peticiones desatendidas)
LAST_REQUEST_TIMES = []

def load_env():
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v.strip()

def parse_season_year(season_str):
    """Mapea dinámicamente cualquier identificador de temporada al año numérico de inicio de la API."""
    s = str(season_str)
    if "2026" in s:
        return "2026"
    elif "2025" in s:
        return "2025"
    elif "2024" in s:
        return "2024"
    return "2026"

class FootballDataClient:
    def __init__(self, token=None):
        load_env()
        self.token = token or os.getenv("FOOTBALLDATA_TOKEN") or ""

    def _throttle(self):
        """Aplica límites estrictos de ritmo: máximo 10 peticiones/minuto."""
        now = time.time()
        while LAST_REQUEST_TIMES and now - LAST_REQUEST_TIMES[0] > 60:
            LAST_REQUEST_TIMES.pop(0)

        if len(LAST_REQUEST_TIMES) >= 10:
            sleep_time = 60 - (now - LAST_REQUEST_TIMES[0]) + 0.5
            if sleep_time > 0:
                print(f"⏳ Throttle football-data.org: Esperando {sleep_time:.1f}s para no exceder 10 req/min...")
                time.sleep(sleep_time)

        LAST_REQUEST_TIMES.append(time.time())

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
                # Datos de temporadas pasadas (2024, 2025) no expiran en caché
                if "season=2024" in params_str or "season=2025" in params_str or (datetime.datetime.now() - fetched_at).total_seconds() < ttl_hours * 3600:
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
        
        cached = self._get_cache(endpoint, params_str)
        if cached:
            return cached

        if not self.token:
            print("⚠️ football-data.org: Token no disponible en entorno.")
            return None

        self._throttle()

        url = f"{FOOTBALL_DATA_BASE}/{endpoint}"
        if params_str:
            url += f"?{params_str}"

        headers = {
            "X-Auth-Token": self.token,
            "User-Agent": "BetAI/3.0"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    self._set_cache(endpoint, params_str, data)
                    return data
        except Exception as e:
            print(f"⚠️ Error consultando football-data.org ({url}): {e}")
        return None

    def get_standings(self, league_key, season="2026"):
        info = FD_COMPETITION_MAP.get(league_key)
        if not info:
            return None
        code = info["code"]
        year = parse_season_year(season)
        endpoint = f"competitions/{code}/standings"
        return self.fetch_api(endpoint, {"season": year})

    def get_matches(self, league_key, season="2026"):
        info = FD_COMPETITION_MAP.get(league_key)
        if not info:
            return None
        code = info["code"]
        year = parse_season_year(season)
        endpoint = f"competitions/{code}/matches"
        return self.fetch_api(endpoint, {"season": year})
