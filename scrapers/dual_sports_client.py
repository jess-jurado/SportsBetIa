import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scrapers.football_data_client import FootballDataClient
from scrapers.api_football_client import APIFootballClient
from engine.team_verifier import normalize_team_name, calculate_season_from_date
from engine.data_validator import validate_match_record, clean_and_normalize_match, log_validation_error

# Tabla de asignación estricta de fuente por competición
LEAGUE_SOURCE_ROUTING = {
    "soccer_spain_la_liga": "football-data.org",
    "soccer_spain_segunda": "API-Football",
    "soccer_epl": "football-data.org",
    "soccer_england_championship": "football-data.org",
    "soccer_italy_serie_a": "football-data.org",
    "soccer_italy_serie_b": "API-Football",
    "soccer_germany_bundesliga": "football-data.org",
    "soccer_france_ligue_one": "football-data.org",
    "soccer_portugal_primeira_liga": "football-data.org",
    "soccer_usa_mls": "API-Football"
}

class DualSportsClient:
    """
    Capa de Normalización e Ingesta Dual.
    Canaliza cada competición a su fuente oficial asignada y traduce todas las respuestas
    a un modelo de datos interno único y homogéneo para toda la aplicación.
    La temporada de cada partido se calcula de forma Canónica e Inequívoca desde su fecha.
    """
    def __init__(self):
        self.fd_client = FootballDataClient()
        self.af_client = APIFootballClient()

    def get_source_for_league(self, league_key):
        return LEAGUE_SOURCE_ROUTING.get(league_key, "football-data.org")

    def fetch_normalized_standings(self, league_key, season="2026"):
        source = self.get_source_for_league(league_key)
        normalized_standings = []

        if source == "football-data.org":
            payload = self.fd_client.get_standings(league_key, season)
            if payload and "standings" in payload:
                for st in payload["standings"]:
                    if st.get("type") == "TOTAL":
                        for row in st.get("table", []):
                            t_name = normalize_team_name(row.get("team", {}).get("name", ""))
                            normalized_standings.append({
                                "team_name": t_name,
                                "league": league_key,
                                "season": season,
                                "sport": "Football",
                                "mp": row.get("playedGames", 0),
                                "w": row.get("won", 0),
                                "d": row.get("draw", 0),
                                "l": row.get("lost", 0),
                                "gs": row.get("goalsFor", 0),
                                "gc": row.get("goalsAgainst", 0),
                                "points": row.get("points", 0),
                                "rank": row.get("position", 0),
                                "source": "football-data.org"
                            })
        elif source == "API-Football":
            payload = self.af_client.get_standings(league_key, season)
            if payload and "response" in payload and len(payload["response"]) > 0:
                try:
                    standings_groups = payload["response"][0].get("league", {}).get("standings", [])
                    for group in standings_groups:
                        for row in group:
                            t_name = normalize_team_name(row.get("team", {}).get("name", ""))
                            all_stats = row.get("all", {})
                            normalized_standings.append({
                                "team_name": t_name,
                                "league": league_key,
                                "season": season,
                                "sport": "Football",
                                "mp": all_stats.get("played", 0),
                                "w": all_stats.get("win", 0),
                                "d": all_stats.get("draw", 0),
                                "l": all_stats.get("lose", 0),
                                "gs": all_stats.get("goals", {}).get("for", 0),
                                "gc": all_stats.get("goals", {}).get("against", 0),
                                "points": row.get("points", 0),
                                "rank": row.get("rank", 0),
                                "source": "API-Football"
                            })
                except Exception as ex:
                    log_validation_error(f"Error normalizando standings API-Football para {league_key}: {ex}")

        return normalized_standings

    def fetch_normalized_matches(self, league_key, season="2026"):
        source = self.get_source_for_league(league_key)
        normalized_matches = []

        if source == "football-data.org":
            payload = self.fd_client.get_matches(league_key, season)
            if payload and "matches" in payload:
                for item in payload["matches"]:
                    try:
                        date_str = item.get("utcDate", "2026-08-16T20:00:00Z")
                        dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        
                        h = normalize_team_name(item.get("homeTeam", {}).get("name", ""))
                        a = normalize_team_name(item.get("awayTeam", {}).get("name", ""))
                        
                        score_obj = item.get("score", {}).get("fullTime", {})
                        hs = score_obj.get("home")
                        aws = score_obj.get("away")

                        status_raw = item.get("status", "SCHEDULED")
                        status = "FINISHED" if status_raw in ["FINISHED", "AWARDED"] else "SCHEDULED"

                        # Derivar la temporada real desde la fecha del partido
                        real_season = calculate_season_from_date(dt, league_key)

                        m_obj = {
                            "date": dt,
                            "sport": "Football",
                            "league": league_key,
                            "season": real_season,
                            "home_team": h,
                            "away_team": a,
                            "home_score": hs,
                            "away_score": aws,
                            "status": status,
                            "source": "football-data.org"
                        }
                        if validate_match_record(m_obj):
                            cleaned = clean_and_normalize_match(m_obj)
                            cleaned["season"] = real_season
                            normalized_matches.append(cleaned)
                    except Exception as ex:
                        log_validation_error(f"Error normalizando partido football-data.org ({league_key}): {ex}")

        elif source == "API-Football":
            payload = self.af_client.get_fixtures(league_key, season)
            if payload and "response" in payload:
                for item in payload["response"]:
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

                        # Derivar la temporada real desde la fecha del partido
                        real_season = calculate_season_from_date(dt, league_key)

                        m_obj = {
                            "date": dt,
                            "sport": "Football",
                            "league": league_key,
                            "season": real_season,
                            "home_team": h,
                            "away_team": a,
                            "home_score": hs,
                            "away_score": aws,
                            "status": status,
                            "source": "API-Football"
                        }
                        if validate_match_record(m_obj):
                            cleaned = clean_and_normalize_match(m_obj)
                            cleaned["season"] = real_season
                            normalized_matches.append(cleaned)
                    except Exception as ex:
                        log_validation_error(f"Error normalizando fixture API-Football ({league_key}): {ex}")

        return normalized_matches
