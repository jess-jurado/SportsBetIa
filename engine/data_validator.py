import datetime
import re
import os
from engine.team_verifier import normalize_team_name

# Validador de esquemas y registros deportivos multiorigen (11 Competiciones Oficiales)
SUPPORTED_SPORTS = {"Football", "Basketball"}
SUPPORTED_LEAGUES = {
    "soccer_spain_la_liga": "Fútbol - La Liga EA Sports",
    "soccer_spain_segunda": "Fútbol - La Liga Hypermotion",
    "soccer_epl": "Fútbol - Premier League",
    "soccer_england_championship": "Fútbol - Championship",
    "soccer_italy_serie_a": "Fútbol - Serie A",
    "soccer_italy_serie_b": "Fútbol - Serie B",
    "soccer_germany_bundesliga": "Fútbol - Bundesliga",
    "soccer_germany_bundesliga2": "Fútbol - 2. Bundesliga",
    "soccer_france_ligue_one": "Fútbol - Ligue 1",
    "soccer_portugal_primeira_liga": "Fútbol - Primeira Liga",
    "soccer_usa_mls": "Fútbol - MLS",
    "basketball_nba": "Baloncesto - NBA"
}

LOG_FILE = "api_validation.log"

def log_validation_error(message: str):
    """Registra errores de validación de respuestas de API para auditoría."""
    timestamp = datetime.datetime.now().isoformat()
    entry = f"[{timestamp}] [VALIDATION_ERROR] {message}\n"
    print(f"⚠️ {entry.strip()}")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def validate_match_record(match: dict) -> bool:
    """
    Valida la integridad de un registro de partido antes de insertarlo en la DB:
    - Comprueba que tenga equipos distintos y normalizados.
    - Comprueba que tenga deporte y liga validos.
    - Comprueba que los marcadores sean enteros validos o None.
    """
    if not isinstance(match, dict):
        log_validation_error("Registro de partido no es un diccionario válido.")
        return False

    home = normalize_team_name(match.get("home_team", ""))
    away = normalize_team_name(match.get("away_team", ""))

    if not home or not away or home == away:
        log_validation_error(f"Equipos inválidos o idénticos: home='{home}', away='{away}'.")
        return False

    sport = match.get("sport", "Football")
    if sport not in SUPPORTED_SPORTS:
        log_validation_error(f"Deporte no soportado: '{sport}'.")
        return False

    league = match.get("league", "")
    if league not in SUPPORTED_LEAGUES:
        log_validation_error(f"Liga no soportada: '{league}'.")
        return False

    hs = match.get("home_score")
    aws = match.get("away_score")

    if hs is not None and (not isinstance(hs, int) or hs < 0):
        log_validation_error(f"Goles locales inválidos: {hs} para {home} vs {away}.")
        return False

    if aws is not None and (not isinstance(aws, int) or aws < 0):
        log_validation_error(f"Goles visitantes inválidos: {aws} para {home} vs {away}.")
        return False

    return True

def clean_and_normalize_match(match: dict) -> dict:
    """Limpia y normaliza un registro de partido valido."""
    cleaned = match.copy()
    cleaned["home_team"] = normalize_team_name(match["home_team"])
    cleaned["away_team"] = normalize_team_name(match["away_team"])
    
    hs = match.get("home_score")
    aws = match.get("away_score")
    
    if hs is not None and aws is not None:
        cleaned["status"] = "FINISHED"
        cleaned["winner"] = "HOME" if hs > aws else ("AWAY" if aws > hs else "DRAW")
    else:
        cleaned["status"] = "SCHEDULED"
        cleaned["winner"] = None
        
    return cleaned
