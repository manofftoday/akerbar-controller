#!/usr/bin/env python3
import json
import os
import sys
import time

FLAG_DIR = "/usr/share/akerbar-controller"
STATE_FILE = os.path.join(FLAG_DIR, "akerbar_state.json")
FLAG_ON = os.path.join(FLAG_DIR, "humidificador_on")
FLAG_OFF = os.path.join(FLAG_DIR, "humidificador_off")

RAW_SECO = 850.0
RAW_AGUA = 280.0


def ensure_flag_dir():
    os.makedirs(FLAG_DIR, exist_ok=True)


def calcular_porcentaje_y_status(valor_analogico):
    if valor_analogico >= 1020:
        return 0, "DESCONECTADO"
    if valor_analogico <= 10:
        return 100, "ERROR / CORTO EN GND"

    porcentaje = ((RAW_SECO - valor_analogico) / (RAW_SECO - RAW_AGUA)) * 100
    porcentaje = max(0, min(100, int(porcentaje)))

    if valor_analogico >= 750:
        return porcentaje, "SECO"
    if valor_analogico >= 600:
        return porcentaje, "REGULAR"
    if valor_analogico >= 450:
        return porcentaje, "OPTIMO"
    if valor_analogico >= 320:
        return porcentaje, "MOJADO"
    return porcentaje, "SATURADO"


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def write_flag(path):
    ensure_flag_dir()
    try:
        with open(path, "w") as f:
            f.write("1")
        return True
    except Exception as exc:
        print(f"Error escribiendo {path}: {exc}")
        return False


def remove_flag(path):
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception as exc:
        print(f"Error borrando {path}: {exc}")
        return False


def show_status():
    data = load_state()
    if data is None:
        print("No se encuentra el estado. Asegúrate de que el daemon esté corriendo.")
        return

    now = time.time()
    timestamp = data.get("timestamp", now)
    age = int((now - timestamp) // 60)
    fan_status = data.get("fan_status", "UNKNOWN")
    cycle_mode = data.get("cycle_mode", "UNKNOWN")
    cycle_state = data.get("cycle_state", fan_status)
    next_on = data.get("cycle_next_on")
    next_change = data.get("cycle_next_change")

    print("=== AKERBAR STATUS ===")
    print(f"Modo: {cycle_mode}")
    print(f"Estado actual: {cycle_state}")
    if cycle_mode == "AUTO" and next_on is not None:
        remaining = int(max(0, next_on - now))
        m = remaining // 60
        s = remaining % 60
        print(f"Siguiente encendido en: {m}m {s}s")
    elif cycle_mode == "AUTO" and next_change is not None:
        remaining = int(max(0, next_change - now))
        m = remaining // 60
        s = remaining % 60
        print(f"Siguiente cambio en: {m}m {s}s")
    print(f"Última lectura hace: {age} min")
    print("")

    print("-- Sensores --")
    for sensor in ["SOIL1", "SOIL2", "SOIL3"]:
        raw = data.get(sensor, 0.0)
        pct, status = calcular_porcentaje_y_status(raw)
        print(f"{sensor}: RAW={int(raw)} {pct}% {status}")

    temp = data.get("TEMP", 0.0)
    hum = data.get("HUM", 0.0)
    print(f"Temperatura: {temp:.2f} °C")
    print(f"Humedad aire: {hum:.2f} %")


def do_on():
    ensure_flag_dir()
    remove_flag(FLAG_OFF)
    if write_flag(FLAG_ON):
        print("Modo MANUAL ON activado.")


def do_off():
    ensure_flag_dir()
    remove_flag(FLAG_ON)
    if write_flag(FLAG_OFF):
        print("Modo MANUAL OFF activado.")


def do_auto():
    ensure_flag_dir()
    remove_flag(FLAG_ON)
    remove_flag(FLAG_OFF)
    print("Modo AUTO activado.")


def show_help():
    print("Uso: akerbar-control [comando]")
    print("comandos:")
    print("  status   Mostrar datos del estado y el ciclo")
    print("  on       Forzar humidificador ON manual")
    print("  off      Forzar humidificador OFF manual")
    print("  auto     Volver al ciclo automático")
    print("  help     Mostrar esta ayuda")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_status()
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd in ["status", "s"]:
        show_status()
    elif cmd == "on":
        do_on()
    elif cmd == "off":
        do_off()
    elif cmd == "auto":
        do_auto()
    else:
        show_help()
