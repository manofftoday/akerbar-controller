import subprocess
import serial
import json
import time
import os

STATE_FILE = "/usr/share/akerbar-controller/akerbar_state.json"
PORT = "/dev/ttyACM0"
BAUD = 115200

FLAG_ON  = "/usr/share/akerbar-controller/humidificador_on"
FLAG_OFF = "/usr/share/akerbar-controller/humidificador_off"

TIEMPO_APAGADO = 900
TIEMPO_ENCENDIDO = 300

CMD_ENCENDER = ["sudo", "uhubctl", "-l", "1-1", "-p", "2", "-a", "1"]
CMD_APAGAR   = ["sudo", "uhubctl", "-l", "1-1", "-p", "2", "-a", "0"]


def controlar_usb(cmd):
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[ERROR USB] {e}")


def guardar_json_atomico(data):
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        print(f"[ERROR FILE] {e}")


def leer_serial(ser):
    """Devuelve dict con última línea válida"""
    if ser is None or not ser.in_waiting:
        return None

    try:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line or ":" not in line:
            return None

        print(f"[RAW] {line}")

        data = {}
        for p in line.split(","):
            if ":" not in p:
                continue
            k, v = p.split(":", 1)
            try:
                data[k.strip()] = float(v.strip())
            except ValueError:
                pass

        return data if data else None

    except Exception as e:
        print(f"[SERIAL ERROR] {e}")
        return None


print("==================================================")
print("  AKERBAR SYSTEM AUTOMATION - DAEMON CONTROLLER   ")
print("==================================================")


ser = None
last_usb_state = None

while True:
    try:

        # ----------------------------
        # MODO MANUAL (solo actuador)
        # ----------------------------
        manual_on = os.path.exists(FLAG_ON)
        manual_off = os.path.exists(FLAG_OFF)

        if manual_on:
            if last_usb_state != "ON":
                print("[MANUAL] HUMIDIFICADOR ON")
                controlar_usb(CMD_ENCENDER)
                last_usb_state = "ON"

        elif manual_off:
            if last_usb_state != "OFF":
                print("[MANUAL] HUMIDIFICADOR OFF")
                controlar_usb(CMD_APAGAR)
                last_usb_state = "OFF"

        # ----------------------------
        # LECTURA SERIAL (SIEMPRE)
        # ----------------------------
        if ser is None:
            try:
                ser = serial.Serial(PORT, BAUD, timeout=1)
                print("[SERIAL] Conectado")
            except Exception as e:
                print(f"[SERIAL] Error conexión: {e}")
                time.sleep(1)
                continue

        new_data = leer_serial(ser)

        if new_data:

            old = {}
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r") as f:
                        old = json.load(f)
                except:
                    old = {}

            old.update(new_data)
            old["timestamp"] = time.time()
            old["fan_status"] = last_usb_state or "UNKNOWN"

            guardar_json_atomico(old)

        time.sleep(0.2)

    except Exception as e:
        print(f"[CRITICAL] {e}")
        time.sleep(2)