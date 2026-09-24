import aiohttp
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    def __init__(self):
        # Lee la API de forma segura del archivo .env oculto
        self.api_key = os.getenv("ODDS_API_KEY", "")
        self.base_url = "https://api.the-odds-api.com/v4/sports"

    async def fetch_odds(self, sport: str, regions: str, markets: str):
        """Consulta en vivo la DB de the-odds-api y extrae N bookmakers por evento."""
        if not self.api_key or self.api_key == "your_api_key_here" or self.api_key.strip() == "":
            print("[X] ERROR SEGURIDAD: No has introducido una API Key en el archivo .env")
            await asyncio.sleep(2)
            return self._fallback_simulacion(), "Local"
            
        url = f"{self.base_url}/{sport}/odds/?apiKey={self.api_key}&regions={regions}&markets={markets}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=10) as response:
                    rem = response.headers.get('x-requests-remaining', 'Sin Dato')
                    
                    if response.status == 200:
                        data = await response.json()
                        return self.normalize_data(data), rem
                    elif response.status in [401, 429]:
                        return "LIMIT_REACHED", rem
                    else:
                        print(f"[API ERROR] Error Servidor {response.status}: {await response.text()}")
                        return self._fallback_simulacion(), rem
            except Exception as e:
                print(f"[API ERROR] Fallo conexión de red: {e}")
                return self._fallback_simulacion(), "Local Network"

    def normalize_data(self, raw_events: list) -> list:
        """
        Limpia, normaliza y empaqueta el arbol de la respuesta JSON complejo al formato lineal.
        Generando por evento una lista de las casas de apuestas analizadas.
        """
        normalized_events = []
        for event in raw_events:
            home = event.get('home_team', 'Equipo A')
            away = event.get('away_team', 'Equipo B')
            event_name = f"{home} vs {away}"
            market_odds = []
            
            # Recorrer todas las casas de apuestas indexadas (ej. Winamax, Bet365, DraftKings...)
            for bookie in event.get("bookmakers", []):
                source_name = bookie.get("title")
                markets_list = bookie.get("markets", [])
                
                # Buscamos el mercado configurado (generalmente Moneyline 'h2h')
                for market in markets_list:
                    if market.get("key") == "h2h":
                        outcomes = market.get("outcomes", [])
                        
                        # Extraemos precios garantizando orden logico: 0=Local, 1=Visitante, 2=Empate (si aplica)
                        odds = []
                        precio_local = next((o["price"] for o in outcomes if o["name"] == home), None)
                        precio_visitante = next((o["price"] for o in outcomes if o["name"] == away), None)
                        precio_empate = next((o["price"] for o in outcomes if o["name"].lower() == "draw"), None)
                        
                        if precio_local and precio_visitante:
                            odds = [precio_local, precio_visitante]
                            if precio_empate:
                                odds.append(precio_empate)
                            market_odds.append({"source": source_name, "odds": odds})
            
            # Solo guardamos el evento si hay cuotas de al menos dos o mas casas para comparar
            if len(market_odds) >= 2:
                normalized_events.append({
                    "event_name": event_name,
                    "market_odds": market_odds
                })
                
        return normalized_events

    def _fallback_simulacion(self):
        """Si falta el API Key, genera una estructura simulada robusta para que el frontend no bloquee."""
        import numpy as np
        odd1_a = round(np.random.uniform(2.0, 2.3), 2)
        odd2_a = round(np.random.uniform(1.6, 1.9), 2)
        
        odd1_b = round(np.random.uniform(2.0, 2.3), 2)
        odd2_b = round(np.random.uniform(1.6, 1.9), 2)
        
        return [{
            "event_name": "Esperando Token API... vs Simulacion",
            "market_odds": [
                {"source": "Bet365 (Simulado)", "odds": [odd1_a, odd2_a]},
                {"source": "Pinnacle (Simulado)", "odds": [odd1_b, odd2_b]}
            ]
        }]