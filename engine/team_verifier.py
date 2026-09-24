import re
import datetime

# Mapa de normalización canónica de nombres de equipos de fútbol a nivel internacional
CANONICAL_TEAM_MAP = {
    # España - Primera
    "girona": "Girona FC", "girona fc": "Girona FC",
    "mallorca": "RCD Mallorca", "rcd mallorca": "RCD Mallorca",
    "valencia": "Valencia CF", "valencia cf": "Valencia CF",
    "real madrid": "Real Madrid", "real madrid c.f.": "Real Madrid",
    "atletico madrid": "Atlético de Madrid", "atlético de madrid": "Atlético de Madrid",
    "athletic bilbao": "Athletic Club", "athletic club": "Athletic Club",
    "barcelona": "FC Barcelona", "fc barcelona": "FC Barcelona",
    "real betis": "Real Betis", "betis": "Real Betis",
    "real sociedad": "Real Sociedad", "celta vigo": "RC Celta", "rc celta": "RC Celta",
    "rayo vallecano": "Rayo Vallecano", "villarreal": "Villarreal CF", "villarreal cf": "Villarreal CF",
    "osasuna": "CA Osasuna", "ca osasuna": "CA Osasuna",
    "alaves": "Deportivo Alavés", "deportivo alavés": "Deportivo Alavés",
    "getafe": "Getafe CF", "getafe cf": "Getafe CF",
    "espanyol": "RCD Espanyol", "rcd espanyol": "RCD Espanyol",
    "sevilla": "Sevilla FC", "sevilla fc": "Sevilla FC",
    "real valladolid": "Real Valladolid", "valladolid": "Real Valladolid",
    "cd leganes": "CD Leganés", "cd leganés": "CD Leganés",
    "malaga": "Málaga CF", "málaga cf": "Málaga CF", "málaga": "Málaga CF",
    "deportivo la coruna": "Deportivo La Coruña", "deportivo la coruña": "Deportivo La Coruña",
    "racing santander": "Racing de Santander", "racing de santander": "Racing de Santander",
    "levante": "Levante UD", "levante ud": "Levante UD",

    # Inglaterra
    "arsenal": "Arsenal", "aston villa": "Aston Villa", "chelsea": "Chelsea",
    "everton": "Everton", "liverpool": "Liverpool", "manchester city": "Manchester City",
    "man city": "Manchester City", "manchester united": "Manchester United",
    "man utd": "Manchester United", "newcastle": "Newcastle United",
    "tottenham": "Tottenham Hotspur", "brighton": "Brighton & Hove Albion",
    "west ham": "West Ham United", "wolverhampton": "Wolverhampton Wanderers",
    "brentford": "Brentford", "fulham": "Fulham", "bournemouth": "AFC Bournemouth",
    "crystal palace": "Crystal Palace", "nottingham forest": "Nottingham Forest",
    "leicester": "Leicester City", "ipswich": "Ipswich Town", "southampton": "Southampton",

    # Italia
    "inter": "Inter Milan", "inter milan": "Inter Milan", "milan": "AC Milan", "ac milan": "AC Milan",
    "juventus": "Juventus", "napoli": "Napoli", "roma": "AS Roma", "lazio": "SS Lazio",
    "atala": "Atalanta", "atalanta": "Atalanta", "fiorentina": "Fiorentina", "bologna": "Bologna",
    "torino": "Torino", "udinese": "Udinese", "genoa": "Genoa", "cagliari": "Cagliari",
    "parma": "Parma", "como": "Como", "verona": "Hellas Verona", "empoli": "Empoli",

    # Alemania
    "bayern munich": "Bayern Munich", "bayern münchen": "Bayern Munich",
    "dortmund": "Borussia Dortmund", "borussia dortmund": "Borussia Dortmund",
    "leverkusen": "Bayer Leverkusen", "bayer leverkusen": "Bayer Leverkusen",
    "rb leipzig": "RB Leipzig", "leipzig": "RB Leipzig", "eintracht frankfurt": "Eintracht Frankfurt",
    "vfb stuttgart": "VfB Stuttgart", "stuttgart": "VfB Stuttgart", "wolfsburg": "VfL Wolfsburg",

    # Francia
    "paris saint germain": "Paris Saint-Germain", "psg": "Paris Saint-Germain",
    "marseille": "Olympique de Marseille", "om": "Olympique de Marseille",
    "monaco": "AS Monaco", "lyon": "Olympique Lyonnais", "lille": "LOSC Lille",

    # Portugal
    "benfica": "SL Benfica", "sporting cp": "Sporting CP", "porto": "FC Porto", "braga": "SC Braga",

    # USA MLS
    "inter miami": "Inter Miami CF", "la galaxy": "LA Galaxy", "lafc": "Los Angeles FC",
    "seattle sounders": "Seattle Sounders FC", "columbus crew": "Columbus Crew"
}

def normalize_team_name(name: str) -> str:
    """Normaliza cualquier nombre de equipo devolviendo su forma canónica oficial."""
    if not name:
        return name
    raw = name.strip().lower()
    raw_clean = re.sub(r'\s+', ' ', raw)
    return CANONICAL_TEAM_MAP.get(raw_clean, name.strip())

def calculate_season_from_date(dt: datetime.datetime, league_key: str = "") -> str:
    """
    Función CANÓNICA y ÚNICA fuente de verdad para etiquetar la temporada real de un partido basándose en su fecha:
    - Para MLS (soccer_usa_mls): Año natural continuo (ej. Oct 2024 -> '2024').
    - Para Fútbol Europeo:
      - Meses Agosto (8) a Diciembre (12): Pertenece a la temporada que arranca ese año (ej. Oct 2025 -> '2025-26').
      - Meses Enero (1) a Julio (7): Pertenece a la temporada que empezó el año anterior (ej. Mar 2026 -> '2025-26', May 2025 -> '2024-25').
    """
    if isinstance(dt, str):
        try:
            dt = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return "2024-25"

    if not isinstance(dt, (datetime.datetime, datetime.date)):
        return "2024-25"

    if "mls" in str(league_key).lower():
        return str(dt.year)

    if dt.month >= 8:
        start_year = dt.year
        end_year_short = str(dt.year + 1)[-2:]
        return f"{start_year}-{end_year_short}"
    else:
        start_year = dt.year - 1
        end_year_short = str(dt.year)[-2:]
        return f"{start_year}-{end_year_short}"
