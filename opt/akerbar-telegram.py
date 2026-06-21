import subprocess
import requests
import json
import time
import os

# =====================================================================
# CONFIGURACIÓN DE SEGURIDAD Y LLAVES
# =====================================================================
TOKEN = ""
USUARIO_AUTORIZADO = "" 

FLAG_DIR = "/usr/share/akerbar-controller"
STATE_FILE = os.path.join(FLAG_DIR, "akerbar_state.json")
FLAG_ON  = os.path.join(FLAG_DIR, "humidificador_on")
FLAG_OFF = os.path.join(FLAG_DIR, "humidificador_off")

URL = f"https://api.telegram.org/bot{TOKEN}/"

# Constantes de calibración del sensor capacitivo V2.0
RAW_SECO = 850.0
RAW_AGUA = 280.0


def ensure_flag_dir():
    os.makedirs(FLAG_DIR, exist_ok=True)

def calcular_porcentaje_y_status(valor_analogico):
    if valor_analogico >= 1020:
        return 0, "❌ DESCONECTADO"
    if valor_analogico <= 10:
        return 100, "⚠️ CORTO EN GND"

    porcentaje = ((RAW_SECO - valor_analogico) / (RAW_SECO - RAW_AGUA)) * 100
    porcentaje = max(0, min(100, int(porcentaje)))

    if valor_analogico >= 750:
        status = "🔴 Dry soil; time to water"
    elif valor_analogico >= 600:
        status = "🟡 Soil is moderately moist"
    elif valor_analogico >= 450:
        status = "🟢 Soil is moist; no need to water"
    elif valor_analogico >= 320:
        status = "🔵 Soil is quite wet"
    else:
        status = "🟣 *Soil is saturated; no more watering required*"

    return porcentaje, status

def enviar_mensaje(chat_id, texto):
    try:
        requests.post(URL + "sendMessage", json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"[TELEGRAM ERROR] No se pudo enviar mensaje: {e}")

def generar_reporte_status():
    if not os.path.exists(STATE_FILE):
        return "⚠️ *Akerbar:* No se encuentra el archivo de estado `akerbar_state.json` todavía."

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        return f"❌ *Akerbar:* Error al leer la base de datos de los sensores: {e}"

    ahora = time.time()
    minutos = int((ahora - data.get("timestamp", ahora)) // 60)

    if data.get("fan_status") == "ON":
        sys_status = "⚡ *ON* (Soplando y Leyendo)"
    else:
        sys_status = "💤 *OFF* (Reposo - Electrólisis Blindada)"

    raw1 = data.get("SOIL1", 1023.0)
    raw2 = data.get("SOIL2", 1023.0)
    raw3 = data.get("SOIL3", 1023.0)
    temp = data.get("TEMP", 0.0)
    hum_aire = data.get("HUM", 0.0)

    p1, txt1 = calcular_porcentaje_y_status(raw1)
    p2, txt2 = calcular_porcentaje_y_status(raw2)
    p3, txt3 = calcular_porcentaje_y_status(raw3)

    reporte = (
        "🌿 *AKERBAR STATUS REPORT*\n"
        "============================\n"
        f"🖥️ *Sistema USB:* {sys_status}\n\n"
        "🪵 *[HUMEDAD DE SUELO]*\n"
        f"  - *Maceta 1:* {p1}% (RAW: {int(raw1)})\n"
        f"    └ {txt1}\n"
        f"  - *Maceta 2:* {p2}% (RAW: {int(raw2)})\n"
        f"    └ {txt2}\n"
        f"  - *Maceta 3:* {p3}% (RAW: {int(raw3)})\n"
        f"    └ {txt3}\n\n"
        "🌤️ *[AMBIENTE]*\n"
        f"  - *Temperatura:* {temp:.2f} °C\n"
        f"  - *Humedad Aire:* {hum_aire:.2f} %\n"
        "============================\n"
    )

    if minutos > 22:
        reporte += f"⚠️ *¡Atención!* Datos desactualizados hace {minutos} min."
    else:
        reporte += f"⏱️ Lectura de hace {minutos} minutos."

    return reporte

def procesar_comandos():
    print(f"[TELEGRAM] Servidor activo. Usuario protegido: {USUARIO_AUTORIZADO}")
    offset = 0
    
    while True:
        try:
            response = requests.get(URL + "getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
            data = response.json()
            
            if "result" in data:
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" not in update or "text" not in update["message"]:
                        continue
                        
                    chat_id = update["message"]["chat"]["id"]
                    
                    # -------------------------------------------------------------
                    # CONTROL DE ACCESO PRIVADO
                    # -------------------------------------------------------------
                    if chat_id != USUARIO_AUTORIZADO:
                        print(f"[ALERTA SEGURIDAD] Intento de acceso de ID no autorizado: {chat_id}")
                        enviar_mensaje(chat_id, "🔒 *Acceso Denegado.* Este sistema de automatización es privado.")
                        continue
                    # -------------------------------------------------------------
                    
                    text = update["message"]["text"].strip().lower()
                    
                    if text == "/status":
                        status_report = generar_reporte_status()
                        enviar_mensaje(chat_id, status_report)

                    elif text == "/on":
                        ensure_flag_dir()
                        if os.path.exists(FLAG_OFF):
                            os.remove(FLAG_OFF)
                        with open(FLAG_ON, "w") as f:
                            f.write("1")
                        enviar_mensaje(chat_id, "🚀 *Akerbar: MODO MANUAL ON*\nEl HUB USB y el humidificador se han forzado a encendido continuo.")
                        
                    elif text == "/off":
                        ensure_flag_dir()
                        if os.path.exists(FLAG_ON):
                            os.remove(FLAG_ON)
                        with open(FLAG_OFF, "w") as f:
                            f.write("1")
                        enviar_mensaje(chat_id, "🛑 *Akerbar: MODO MANUAL OFF*\nEl sistema USB se ha cortado y queda apagado indefinidamente.")
                        
                    elif text == "/auto":
                        ensure_flag_dir()
                        if os.path.exists(FLAG_ON):
                            os.remove(FLAG_ON)
                        if os.path.exists(FLAG_OFF):
                            os.remove(FLAG_OFF)
                        enviar_mensaje(chat_id, "🔄 *Akerbar: MODO AUTOMÁTICO*\nRestablecido el ciclo normal.")
                        
                    elif text in ["/start", "/help"]:
                        menu = (
                            "🌿 *Panel de Control Akerbar*\n\n"
                            "Comandos disponibles:\n"
                            "/status - Ver telemetría en tiempo real 📊\n"
                            "/on - Forzar encendido continuo 🚀\n"
                            "/off - Forzar apagado completo 🛑\n"
                            "/auto - Volver al ciclo automático 🔄"
                        )
                        enviar_mensaje(chat_id, menu)

        except requests.exceptions.RequestException:
            time.sleep(5)
        except Exception as e:
            print(f"[TELEGRAM CRITICAL] Fallo en bucle: {e}")
            time.sleep(5)

if __name__ == "__main__":
    procesar_comandos()