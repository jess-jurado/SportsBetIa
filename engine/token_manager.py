import requests
import time
import re
import os

class TokenManager:
    @staticmethod
    def _get_temp_email():
        try:
            res = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1")
            return res.json()[0]
        except:
            return None

    @staticmethod
    def _read_inbox(login, domain):
        try:
            res = requests.get(f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}")
            return res.json()
        except:
            return []

    @staticmethod
    def _read_message(login, domain, msg_id):
        try:
            res = requests.get(f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}")
            return res.json().get("body", "")
        except:
            return ""

    @staticmethod
    def renew_token():
        print("\n[🔑] Iniciando Protocolo de Emergencia: Generación de nueva Key API The Odds API...")
        email = TokenManager._get_temp_email()
        if not email:
            print("[🔑] TAREA FALLIDA: Servidor de Temp Mail bloqueado.")
            return False
            
        print(f"[🔑] [1] Email temporal generado OK: {email}")
        login, domain = email.split('@')
        
        print("[🔑] [2] Invocando robot HTTP hacia Muros The-Odds-API (Bypassing Cloudflare)...")
        try:
            register_url = "https://the-odds-api.com/api/v4/register"
            payload = {"email": email, "name": "BetIA System"}
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            
            # Request generico para desencadenar el correo de registro
            reg_req = requests.post(register_url, json=payload, headers=headers, timeout=8)
            
            # Si Cloudflare tumba el crawler o cambian el registro:
            if reg_req.status_code == 403 or reg_req.status_code == 404:
                 raise Exception("Muro de Seguridad antibot en The-Odds-Api activado (403_Forbidden/404).")
                 
        except Exception as e:
            print(f"[🔑] ¡BLOQUEO DETECTADO!: {e}")
            print("[🔑] API no pudo evadir Cloudflare/Registro. \n -> Auto-Aprobando Fallback Modo Web Playwright Directo.")
            return False

        print("[🔑] [3] Petición HTTP evadida. Escuchando Bandeja de Entrada Temporal 20 SEGUNDOS...")
        for _ in range(6):
            time.sleep(5)
            msgs = TokenManager._read_inbox(login, domain)
            if msgs:
                for m in msgs:
                    if "api" in m.get("subject", "").lower() or "odds" in m.get("subject", "").lower():
                        body = TokenManager._read_message(login, domain, m["id"])
                        keys = re.findall(r'[a-f0-9]{32}', body) # Hash MD5 tipico API KEY 32 chars
                        if keys:
                            new_key = keys[0]
                            print(f"[🔑] ¡RESURRECCIÓN! Nueva llave extraída del mail crudo: {new_key[:8]}************************")
                            TokenManager._update_env(new_key)
                            return True
        print("[🔑] Timeout Grave: El proveedor the-odds descartó nuestra solicitud en la sombra.")
        return False

    @staticmethod
    def _update_env(new_key):
        env_path = ".env"
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f: lines = f.readlines()
                
        with open(env_path, "w") as f:
            key_written = False
            for line in lines:
                if line.startswith("ODDS_API_KEY="):
                    f.write(f"ODDS_API_KEY={new_key}\n")
                    key_written = True
                else:
                    f.write(line)
            if not key_written:
                f.write(f"ODDS_API_KEY={new_key}\n")
                
