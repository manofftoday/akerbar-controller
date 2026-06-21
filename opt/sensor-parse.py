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

# Ciclo automático: encender 5 minutos y apagar 25 minutos (30 minutos totales)
TIEMPO_ENCENDIDO = 300
TIEMPO_APAGADO = 1500

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
    """Devuelve dict con última línea válida y reconecta si hay error"""
    if ser is None:
        return None, None

    try:
        if not ser.in_waiting:
            return None, ser

        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line or ":" not in line:
            return None, ser

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

        return (data if data else None), ser

    except Exception as e:
        print(f"[SERIAL ERROR] {e}")
        try:
            ser.close()
        except Exception:
            pass
        return None, None


print("==================================================")
print("  AKERBAR SYSTEM AUTOMATION - DAEMON CONTROLLER   ")
print("==================================================")


ser = None
last_usb_state = None
last_cycle_state = "OFF"
last_cycle_change = time.time()
cycle_mode = "AUTO"
next_cycle_change = last_cycle_change + TIEMPO_APAGADO
next_cycle_on = next_cycle_change

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
            cycle_mode = "MANUAL"
            next_cycle_change = None
            next_cycle_on = None

        elif manual_off:
            if last_usb_state != "OFF":
                print("[MANUAL] HUMIDIFICADOR OFF")
                controlar_usb(CMD_APAGAR)
                last_usb_state = "OFF"
            cycle_mode = "MANUAL"
            next_cycle_change = None
            next_cycle_on = None

        else:
            cycle_mode = "AUTO"
            # Ciclo automático: 5 minutos ON, 25 minutos OFF
            elapsed = time.time() - last_cycle_change

            if last_cycle_state == "ON":
                if elapsed >= TIEMPO_ENCENDIDO:
                    print("[AUTO] HUMIDIFICADOR OFF")
                    controlar_usb(CMD_APAGAR)
                    last_usb_state = "OFF"
                    last_cycle_state = "OFF"
                    last_cycle_change = time.time()
                    next_cycle_change = last_cycle_change + TIEMPO_APAGADO
                    next_cycle_on = next_cycle_change
                elif last_usb_state != "ON":
                    controlar_usb(CMD_ENCENDER)
                    last_usb_state = "ON"
                    next_cycle_change = last_cycle_change + TIEMPO_ENCENDIDO
                    next_cycle_on = next_cycle_change + TIEMPO_APAGADO

            else:
                if elapsed >= TIEMPO_APAGADO:
                    print("[AUTO] HUMIDIFICADOR ON")
                    controlar_usb(CMD_ENCENDER)
                    last_usb_state = "ON"
                    last_cycle_state = "ON"
                    last_cycle_change = time.time()
                    next_cycle_change = last_cycle_change + TIEMPO_ENCENDIDO
                    next_cycle_on = next_cycle_change + TIEMPO_APAGADO
                elif last_usb_state != "OFF":
                    controlar_usb(CMD_APAGAR)
                    last_usb_state = "OFF"
                    next_cycle_change = last_cycle_change + TIEMPO_APAGADO
                    next_cycle_on = next_cycle_change

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

        new_data, ser = leer_serial(ser)

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
            old["cycle_mode"] = cycle_mode
            old["cycle_state"] = last_cycle_state
            old["cycle_next_change"] = next_cycle_change
            old["cycle_next_on"] = next_cycle_on

            guardar_json_atomico(old)

        time.sleep(0.2)

    except Exception as e:
        print(f"[CRITICAL] {e}")
        try:
            if ser is not None:
                ser.close()
        except Exception:
            pass
        ser = None
        time.sleep(2)