import asyncio
import pandas as pd
import numpy as np
import json
import datetime
import os
import time
import random

from engine.analytics import detect_arbitrage, calculate_kelly_stake
from engine.ml_model import train_hybrid_model, predict_value
from engine.token_manager import TokenManager
from engine.telegram_bot import TelegramNotifier
from scrapers.base_scraper import WebScraperFallback
from scrapers.market_scraper import APIClient
from engine.storage import init_db, save_scan_cycle, save_historical_signal, clean_old_records
from dotenv import load_dotenv

STATE_FILE = "state.json"
CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"
logs = []
tabla_recientes = []  
total_scanned_counter = 0

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    except Exception as e:
        return {"sports": [], "regions": "eu", "markets": "h2h", "countries": {}}

def get_active_settings(config):
    try:
        with open(SETTINGS_FILE, "r") as f:
            sett = json.load(f)
            c_name = sett.get("active_country", "España")
            s_name = sett.get("active_sport", "Todos")
            s_mode = sett.get("scraping_mode", "api")
            bankroll = float(sett.get("bankroll", 1000.0))
            if bankroll <= 0: bankroll = 1000.0
            tg_active = sett.get("telegram_alerts", True)
            allowed_bookies_raw = sett.get("allowed_bookies", [])
    except:
        c_name = "España"
        s_name = "Todos"
        s_mode = "api"
        bankroll = 1000.0
        tg_active = True
        allowed_bookies_raw = []
        
    c_data = config.get("countries", {}).get(c_name, {})
    
    if not allowed_bookies_raw:
        allowed_bookies_raw = c_data.get("bookmakers", ["bet365", "william hill", "bwin", "pinnacle"])
        
    allowed_bookies = [str(b).lower() for b in allowed_bookies_raw]
    return c_name, c_data.get("flag", "🇪🇸"), allowed_bookies, s_name, s_mode, bankroll, tg_active

def get_bookie_url(b_name):
    b = str(b_name).lower()
    if 'bet365' in b: return "https://www.bet365.com"
    elif 'pinnacle' in b: return "https://www.pinnacle.com"
    elif 'william hill' in b: return "https://sports.williamhill.com"
    elif 'bwin' in b: return "https://sports.bwin.com"
    elif '888' in b: return "https://www.888sport.com"
    elif 'betway' in b: return "https://www.betway.com"
    elif 'winamax' in b: return "https://www.winamax.es"
    elif 'luckia' in b: return "https://www.luckia.es"
    elif 'codere' in b: return "https://www.codere.es"
    else: return f"https://www.google.com/search?q={str(b_name).replace(' ', '+')}+sports+betting"

def update_state(status, margin=0.0, prob=0.0, stake=0.0, odds_a=None, odds_b=None, name_a="Bookie 1", name_b="Bookie 2", event="En Espera", log=None, debug_msg="Sistema Operativo", ai_samples=0, near_arbs=None, arb_timestamp=0, api_tokens=""):
    global logs
    global tabla_recientes
    global total_scanned_counter
    
    if log:
        is_duplicate = False
        if logs:
            last_msg = logs[-1].split("] ", 1)[-1]
            if last_msg == log:
                is_duplicate = True
                
        if not is_duplicate:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            formatted_log = f"[{timestamp}] {log}"
            logs.append(formatted_log)
            print(formatted_log)
        
    if odds_a is None: odds_a = [0, 0]
    if odds_b is None: odds_b = [0, 0]
    
    logs_to_save = logs[-20:]
    state = {
        "status": status, "last_margin": margin, "ai_probability": prob,
        "recommended_stake": stake, "market_a_odds": odds_a, "market_b_odds": odds_b,
        "name_a": name_a, "name_b": name_b, "event": event,
        "logs": logs_to_save,
        "total_scanned": total_scanned_counter,
        "tabla_recientes": tabla_recientes[-10:],
        "debug_msg": debug_msg,
        "ai_samples": ai_samples,
        "near_arbs": near_arbs[-10:] if near_arbs else [], 
        "arb_timestamp": arb_timestamp,
        "api_tokens_left": api_tokens,
        "last_sync_timestamp": time.time()
    }
    
    try:
        with open(STATE_FILE, "w") as f: json.dump(state, f)
    except: pass

async def main():
    global tabla_recientes
    global total_scanned_counter
    init_db()
    clean_old_records()
    near_arbs_memoria = []
    
    update_state("Inicializando", log="=== KERNEL DE PRODUCCIÓN SOBERANA ACTIVADO ===")
    
    print("\n[+] Sincronizando Módulos de Telecomunicaciones...")
    # Bucle Bloqueante si no hay Chat ID (Espera el /start del Usuario por Telegram)
    notifier = TelegramNotifier()
    
    update_state("Escaneando SQLite...", log="[1] Cargando histórico SQLite...")
    ml_agent, ai_samples = train_hybrid_model()
    update_state("Modelo Activo", ai_samples=ai_samples, log=f"   -> [ML] Engine compilado con {ai_samples} registros.")
    
    config = load_config()
    sports = config.get("sports", ["soccer_epl"])
    regions = config.get("regions", "eu")
    markets = config.get("markets", "h2h")
    
    scraper = APIClient()
    web_scraper = WebScraperFallback()

    last_training_thousand = total_scanned_counter // 1000

    while True:
        c_name, c_flag, allowed_bookies, s_name, s_mode, bankroll, tg_active = get_active_settings(config)
        update_state("Analizando Entorno", ai_samples=ai_samples, log=f"[2] Mode: {s_mode.upper()} | Bankroll Activo: ${bankroll} | Extracción: {c_name} {c_flag}")
        
        current_thousand = total_scanned_counter // 1000
        if current_thousand > last_training_thousand and total_scanned_counter > 0:
            last_training_thousand = current_thousand
            up_msg = f"[+] Actualización Continua IA: Engranando XGBoost y SQLite con {total_scanned_counter} registros..."
            print(f"\n{up_msg}")
            update_state("Auto-Train IA", log=up_msg)
            ml_agent, ai_samples = train_hybrid_model()
        
        for sport in sports:
            if s_name != "Todos" and sport != s_name: continue
            
            update_state(f"Query: {sport}", ai_samples=ai_samples, near_arbs=near_arbs_memoria, log=f" -> Búsqueda: {sport}...")
            try:
                tokens_ui_str = "WEB Scraping"
                res = []
                
                if s_mode == "api":
                    res, rem = await scraper.fetch_odds(sport, regions, markets)
                    tokens_ui_str = str(rem)
                    
                    if res == "LIMIT_REACHED":
                        update_state(f"Agotamiento Tokens", debug_msg="Límite the-odds (401). Renovando Key...", ai_samples=ai_samples, api_tokens="0")
                        success = TokenManager.renew_token()
                        
                        if success:
                            load_dotenv(override=True)
                            scraper.api_key = os.getenv("ODDS_API_KEY", "")
                            res, rem = await scraper.fetch_odds(sport, regions, markets)
                            tokens_ui_str = str(rem)
                        else:
                            with open(SETTINGS_FILE, "r+") as f:
                                stg = json.load(f)
                                stg["scraping_mode"] = "web"
                                f.seek(0)
                                json.dump(stg, f)
                                f.truncate()
                            s_mode = "web"
                            update_state("Fallback Web", debug_msg="Cambiando a Chromium Invisible...", ai_samples=ai_samples, api_tokens="ILIMITADO")
                
                if s_mode == "web" or res == "LIMIT_REACHED":
                    tokens_ui_str = "Web Proxy ∞"
                    res = await web_scraper.fetch_odds_web(sport, allowed_bookies)
                    
                eventos_activos = res
                
                if not eventos_activos or eventos_activos == "LIMIT_REACHED":
                    update_state(f"Nulo: {sport}", debug_msg=f"⚠️ Sin información para {sport}.", ai_samples=ai_samples, near_arbs=near_arbs_memoria, api_tokens=tokens_ui_str)
                    continue
                    
                total_scanned_counter += len(eventos_activos)
                
                for evento in eventos_activos:
                    event_name = evento["event_name"]
                    mercados_evento = []
                    
                    for m in evento["market_odds"]:
                        s_name_book = m["source"].lower()
                        if any(b.lower() in s_name_book for b in allowed_bookies):
                            mercados_evento.append(m)
                            
                    if len(mercados_evento) < 2:
                        continue 
                        
                    m1 = mercados_evento[0]
                    m2 = mercados_evento[1]
                    
                    oportunidad = detect_arbitrage(mercados_evento)
                    margin = oportunidad.get("margin_percentage", 0)
                    
                    o_a1 = m1["odds"][0] if len(m1["odds"]) > 0 else 0
                    o_a2 = m1["odds"][1] if len(m1["odds"]) > 1 else 0
                    o_b1 = m2["odds"][0] if len(m2["odds"]) > 0 else 0
                    o_b2 = m2["odds"][1] if len(m2["odds"]) > 1 else 0
                    
                    current_event_features = pd.DataFrame(
                        [[o_a1, o_a2, o_b1, o_b2, margin]], 
                        columns=['odd_a_1', 'odd_a_2', 'odd_b_1', 'odd_b_2', 'margin']
                    )
                    probabilidad_x = predict_value(ml_agent, current_event_features)
                    
                    # Extraer nombres de equipos del evento
                    clean_ev = event_name
                    for ch in ["⚽", "🎾", "🏀", "[Web]"]:
                        clean_ev = clean_ev.replace(ch, "")
                    clean_ev = clean_ev.strip()
                    if " vs " in clean_ev:
                        ev_parts = clean_ev.split(" vs ", 1)
                    elif " v " in clean_ev:
                        ev_parts = clean_ev.split(" v ", 1)
                    elif " - " in clean_ev:
                        ev_parts = clean_ev.split(" - ", 1)
                    else:
                        ev_parts = [clean_ev, "Rival"]
                    team_home = ev_parts[0].strip()
                    team_away = ev_parts[1].strip() if len(ev_parts) > 1 else "Rival"
                    
                    # Determinar si es fútbol (3-way)
                    is_football = 'soccer' in sport

                    mejor_casa = oportunidad["best_odds"][0]["source"] if oportunidad.get("arbitrage_found") else m1["source"]
                    mejor_cuota = oportunidad["best_odds"][0]["odd"] if oportunidad.get("arbitrage_found") else max(m1["odds"])
                    
                    tabla_recientes.append({
                        "Evento": event_name,
                        "Mejor Mercado": mejor_casa,
                        "Max. Cuota": f"{mejor_cuota:.2f}",
                        "Arbitraje": f"{margin:.2f}%" if oportunidad.get("arbitrage_found") else "No"
                    })
                    
                    save_scan_cycle(mercados_evento, oportunidad.get("arbitrage_found", False), margin, event_name, sport)
                    
                    if oportunidad.get("arbitrage_found"):
                        ts = time.time()
                        update_state(f"¡Arbitraje!", margin=margin, prob=probabilidad_x, odds_a=m1["odds"], odds_b=m2["odds"], name_a=m1["source"], name_b=m2["source"], event=f"{c_flag} {event_name}", debug_msg="Matriz Válida", ai_samples=ai_samples, near_arbs=near_arbs_memoria, arb_timestamp=ts, api_tokens=tokens_ui_str, log=f"[!!!] DISCREPANCIA DETECTADA: {event_name}")
                        
                        if margin > 1.0:
                            os.system(f"osascript -e 'display notification \"¡{margin:.2f}% detectado en {event_name}!\" with title \"BetIA - Arbitraje Superior\"'")
                            
                        best_market_odd = oportunidad["best_odds"][0]["odd"]
                        best_source = oportunidad["best_odds"][0]["source"]
                        
                        kelly = calculate_kelly_stake(probabilidad_x, best_market_odd, float(bankroll), 0.25)
                        k_s = kelly.get("recommended_stake_amount", 0)
                        
                        if margin > 0.5 and k_s <= 0:
                            k_s = bankroll * 0.02
                        k_s = int(round(k_s))
                        
                        save_historical_signal(f"{c_flag} {event_name} [{best_source}]", probabilidad_x, k_s, best_market_odd, kelly.get("edge_found", False))
                        
                        # ALERTA DE ORO (Arbitraje) — Filtro anti-sospechosos
                        if margin > 1.2 and margin <= 15.0 and tg_active:
                            # Construir best_odds_array con etiquetas de resultado
                            best_odds_raw = oportunidad.get("best_odds", [])
                            
                            # Recuperar outcome_labels desde los mercados originales
                            all_labels = m1.get("outcome_labels", [team_home, team_away] if not is_football else [team_home, "Empate", team_away])
                            
                            # Si es fútbol 3-way, verificar que tenemos las 3 patas
                            if is_football and len(best_odds_raw) < 3:
                                pass  # No enviar alerta incompleta de 3-way
                            else:
                                best_odds_array = []
                                for item in best_odds_raw:
                                    idx = item["outcome_index"]
                                    label = all_labels[idx] if idx < len(all_labels) else f"Resultado {idx+1}"
                                    best_odds_array.append({
                                        "source": item["source"],
                                        "odd": item["odd"],
                                        "label": label
                                    })
                                
                                notifier.send_alert(
                                    f"[Arb] {event_name}", sport, round(margin, 2), round(probabilidad_x*100, 2), 
                                    k_s, best_odds_array, get_bookie_url(best_source)
                                )
                        
                        await asyncio.sleep(2.0)
                    else:
                        if margin < 0 and margin >= -15.0 and probabilidad_x > 0.55:
                            near_arbs_memoria.append({
                                "Partido": f"{c_flag} {event_name}",
                                "Edge Predicho": f"{probabilidad_x * 100:.2f}%",
                                "Margen Gap": f"{margin:.2f}%",
                                "Target": m1['source']
                            })
                            update_state("Near-Arb!", margin=margin, prob=probabilidad_x, odds_a=m1["odds"], odds_b=m2["odds"], name_a=m1["source"], name_b=m2["source"], event=f"{c_flag} {event_name}", debug_msg=f"Value Bet Rastreada ({probabilidad_x * 100:.1f}%)", ai_samples=ai_samples, near_arbs=near_arbs_memoria, api_tokens=tokens_ui_str)
                            
                            # ALERTA DE ORO (IA Value Bet Severa)
                            if probabilidad_x > 0.75 and tg_active:
                                 kell_val = calculate_kelly_stake(probabilidad_x, max(m1["odds"]), float(bankroll), 0.25)
                                 sv = kell_val.get("recommended_stake_amount", 0)
                                 if sv <= 0: sv = bankroll * 0.015
                                 sv = int(round(sv))
                                 
                                 all_labels_vb = m1.get("outcome_labels", [team_home, team_away])
                                 # Value bet: apostar al resultado con mayor cuota
                                 max_odd_idx = m1["odds"].index(max(m1["odds"]))
                                 vb_label = all_labels_vb[max_odd_idx] if max_odd_idx < len(all_labels_vb) else team_home
                                 
                                 vb_array = [{"source": m1["source"], "odd": max(m1["odds"]), "label": vb_label}]
                                 notifier.send_alert(
                                     f"[ValueBet] {event_name}", sport, round(margin, 2), round(probabilidad_x*100, 2), 
                                     sv, vb_array, get_bookie_url(m1['source'])
                                 )
                                 
                            await asyncio.sleep(0.05)
                        else:
                            update_state("Escaneando", odds_a=m1["odds"], odds_b=m2["odds"], name_a=m1["source"], name_b=m2["source"], event=f"{c_flag} {event_name}", debug_msg="Volatilidad estática.", ai_samples=ai_samples, near_arbs=near_arbs_memoria, api_tokens=tokens_ui_str)
                            await asyncio.sleep(0.01) 
                
            except Exception as e:
                # Simplificación radical de logs de error para mayor limpieza
                err_msg = str(e).split('\n')[0]
                if "Target page, context or browser has been closed" in err_msg or "CancelledError" in err_msg:
                    pass # Evitar ruido durante el cierre
                else:
                    print(f"⚠️  Error detectado en {sport}: {err_msg[:60]}...")
                    update_state("Reintentando", debug_msg=f"Error Red: {err_msg[:40]}", ai_samples=ai_samples, near_arbs=near_arbs_memoria, api_tokens=tokens_ui_str)
            
        human_delay = random.uniform(12, 28)
        update_state(f"Pausa ({c_flag})", ai_samples=ai_samples, near_arbs=near_arbs_memoria, log=f"=== Ciclo {c_flag} OK. Enfriando motor {human_delay:.0f}s ===", api_tokens=tokens_ui_str)
        await asyncio.sleep(human_delay)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n" + "="*50)
        print("🛑 Deteniendo BetIA de forma segura...")
        print("🔌 Cerrando conexiones y liberando recursos...")
        # No hace falta cerrar DB explícitamente porque storage usa conexiones locales por función
        print("✅ Sistema apagado correctamente. ¡Hasta pronto!")
        print("="*50 + "\n")
    except Exception as e:
        print(f"\n❌ Error fatal inesperado: {e}")
