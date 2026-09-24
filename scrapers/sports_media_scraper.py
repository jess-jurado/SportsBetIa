import urllib.request
import json
import xml.etree.ElementTree as ET
import re
from engine.team_verifier import normalize_team_name

# Rascador e Ingestor de Prensa Deportiva Oficial (Diario AS / Marca / Feeds Oficiales)
AS_PRIMERA_RSS = "https://as.com/rss/futbol/primera.xml"
AS_SEGUNDA_RSS = "https://as.com/rss/futbol/segunda.xml"

def fetch_feed(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"⚠️ Error consultando boletín deportivo {url}: {e}")
        return ""

def parse_as_sports_press():
    """
    Extrae titulares de noticias deportivas oficiales, marcadores reportados y resúmenes de jornadas.
    """
    print("📰 Consultando boletines oficiales de prensa deportiva (Diario AS / Marca)...")
    content_p = fetch_feed(AS_PRIMERA_RSS)
    content_s = fetch_feed(AS_SEGUNDA_RSS)

    extracted_items = []
    
    for content in [content_p, content_s]:
        if not content:
            continue
        try:
            root = ET.fromstring(content)
            for item in root.findall('.//item'):
                title = item.find('title')
                desc = item.find('description')
                t_txt = title.text if title is not None and title.text else ""
                d_txt = desc.text if desc is not None and desc.text else ""
                
                # Buscar patron de partido/resultado ej: Real Madrid 2 - 1 Betis
                score_match = re.search(r'([A-Za-z\s]+)\s+(\d+)\s*-\s*(\d+)\s+([A-Za-z\s]+)', t_txt)
                if score_match:
                    h_team = normalize_team_name(score_match.group(1))
                    hs = int(score_match.group(2))
                    aws = int(score_match.group(3))
                    a_team = normalize_team_name(score_match.group(4))
                    
                    extracted_items.append({
                        "home_team": h_team,
                        "away_team": a_team,
                        "home_score": hs,
                        "away_score": aws,
                        "headline": t_txt,
                        "source": "Diario_AS"
                    })
        except Exception as e:
            print(f"⚠️ Error parseando XML de prensa: {e}")

    print(f"✅ Extraídos {len(extracted_items)} titulares y marcadores verificados por prensa deportiva.")
    return extracted_items

if __name__ == "__main__":
    items = parse_as_sports_press()
    print("Muestra de prensa deportiva:", items[:3])
