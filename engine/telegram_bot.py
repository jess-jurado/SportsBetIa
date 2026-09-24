import os
import time
import requests
import re
from dotenv import load_dotenv

class TelegramNotifier:
    def __init__(self):
        load_dotenv(override=True)
        self.raw_token = os.getenv("TELEGRAM_TOKEN", "")
        self.token = self.raw_token.replace("..", ".").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        self._ensure_config()
        self._init_chat_id()

    def _ensure_config(self):
        env_path = ".env"
        lines = []
        has_token = False
        has_chat = False
        if os.path.exists(env_path):
            with open(env_path, "r") as f: lines = f.readlines()
        for l in lines:
            if l.startswith("TELEGRAM_TOKEN="): has_token = True
            if l.startswith("TELEGRAM_CHAT_ID="): has_chat = True
            
        with open(env_path, "w") as f:
            for l in lines: f.write(l)
            if not has_token: f.write(f"\nTELEGRAM_TOKEN={self.token}\n")
            if not has_chat: f.write("TELEGRAM_CHAT_ID=\n")

    def _update_env_chat(self, new_id):
        env_path = ".env"
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f: lines = f.readlines()
        with open(env_path, "w") as f:
            for l in lines:
                if l.startswith("TELEGRAM_CHAT_ID="):
                    f.write(f"TELEGRAM_CHAT_ID={new_id}\n")
                else:
                    f.write(l)

    def _init_chat_id(self):
        if self.chat_id and self.chat_id.strip() != "TU_ID_AQUI":
            return
            
        print("\n[TELEGRAM] 📡 Chat_ID de destino no configurado.")
        print(f"[TELEGRAM] 📡 Abre tu app Telegram y mándale el mensaje: /start al Bot Oficial.")
        print("[TELEGRAM] ⏳ Esperando señal de emparejamiento con servidor Telegram...")
        
        offset = 0
        while True:
            try:
                res = requests.get(f"{self.base_url}/getUpdates?offset={offset}", timeout=5)
                if res.status_code == 401:
                    print(f"\n[TELEGRAM] 🚨 ERROR CRITICO 401: El TELEGRAM_TOKEN provisto es INVÁLIDO o ha sido revocado. Entra en BotFather, genera uno nuevo y pégalo en Token en tu fichero .env")
                    time.sleep(10)
                    continue
                    
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok") and len(data.get("result", [])) > 0:
                        for item in data["result"]:
                            offset = item["update_id"] + 1
                            msg = item.get("message", {})
                            text = msg.get("text", "")
                            if "/start" in text:
                                self.chat_id = str(msg["chat"]["id"])
                                self._update_env_chat(self.chat_id)
                                print(f"[TELEGRAM] ✅ ¡Emparejado con éxito! Chat_ID detectado: {self.chat_id}")
                                
                                requests.post(f"{self.base_url}/sendMessage", json={
                                    "chat_id": self.chat_id,
                                    "text": "🤖 *BetIA Framework Enlazado*\nComandos Tácticos activados en tu Mac\\. Bienvenido a la caza de arbitrajes\\.",
                                    "parse_mode": "MarkdownV2"
                                })
                                return
            except Exception as e:
                pass
            time.sleep(3)

    def escape_markdown_v2(self, text):
        escape_chars = r"_*[]()~`>#+-=|{}.!"
        return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))

    def send_alert(self, event, league, margin, ai_prob, kelly_stake, best_odds_array, b_url):
        """
        Envía alerta dinámica N-way (2 o 3 patas).
        best_odds_array = [{"source": "Bet365", "odd": 2.15, "label": "Real Madrid"}, ...]
        """
        if not self.chat_id: return
        
        from engine.storage import log_telegram_alert
        
        total_stake_int = int(round(kelly_stake))
        if total_stake_int <= 0: total_stake_int = 10
        
        # Reparto estricto Inverso N-way con Smart Rounding
        n = len(best_odds_array)
        try:
            imps = [1.0 / item["odd"] for item in best_odds_array]
            total_imp = sum(imps)
            raw_stakes = [total_stake_int * (imp / total_imp) for imp in imps]
            
            # Smart Rounding: redondear todos menos el último, que absorbe la diferencia
            stakes = [int(round(s)) for s in raw_stakes[:-1]]
            stakes.append(total_stake_int - sum(stakes))
            
            # Protección contra negativos
            stakes = [max(0, s) for s in stakes]
        except:
            base = total_stake_int // n
            stakes = [base] * n
            stakes[-1] = total_stake_int - base * (n - 1)
        
        # Construir líneas dinámicas de ACCIONAR
        emojis_num = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        action_lines = []
        for i, item in enumerate(best_odds_array):
            emoji = emojis_num[i] if i < len(emojis_num) else f"{i+1}."
            src = self.escape_markdown_v2(item["source"])
            lbl = self.escape_markdown_v2(item["label"])
            odd = self.escape_markdown_v2(str(item["odd"]))
            st_i = stakes[i] if i < len(stakes) else 0
            action_lines.append(f"{emoji} {src}: Apostar {st_i}€ al {lbl} \\(@{odd}\\)")
        
        actions_block = "\n".join(action_lines)
        
        # Mapeo legible de liga
        league_map = {
            "soccer_epl": "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿",
            "soccer_spain_la_liga": "La Liga 🇪🇸",
            "soccer_italy_serie_a": "Serie A 🇮🇹",
            "soccer_germany_bundesliga": "Bundesliga 🇩🇪",
            "soccer_uefa_champs_league": "Champions League 🏆",
            "basketball_nba": "NBA 🏀",
            "tennis_atp": "ATP Tour 🎾"
        }
        league_display = league_map.get(league, league)
        
        msg = (
            f"🚨 *OPORTUNIDAD DETECTADA*\n"
            f"🏟️ {self.escape_markdown_v2(event)} \\| 🏆 {self.escape_markdown_v2(league_display)}\n"
            f"💰 Beneficio Neto: {self.escape_markdown_v2(str(margin))}\\%\n"
            f"\n"
            f"✅ *ACCIONAR:*\n"
            f"{actions_block}\n"
            f"\n"
            f"⚠️ _Stakes redondeados a {total_stake_int}€ en total_\n"
            f"🔗 [Acceso Directo]({b_url})"
        )
        
        try:
            requests.post(f"{self.base_url}/sendMessage", json={
                "chat_id": self.chat_id,
                "text": msg,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True
            }, timeout=5)
            print("📲 [TELEGRAM] Notificación Flash VIP enviada al Tracker móvil.")
            
            # Certificar en telemetría SQLite
            try:
                markets_dump = [{"src": o["source"], "lbl": o["label"], "odd": o["odd"], "stake": stakes[i]} for i, o in enumerate(best_odds_array)]
                log_telegram_alert(event, league_display, margin, total_stake_int, markets_dump)
            except: pass
            
        except Exception as e:
            print(f"[TELEGRAM] Fallo enviando alerta crítica: {e}")
