import json
import time
import os

STATE_FILE = "/usr/share/akerbar-controller/akerbar_state.json"

# =====================================================================
# CONFIGURACIÓN DE CALIBRACIÓN REAL (Sensor Capacitivo V2.0)
# =====================================================================
# Ajusta estos valores tras hacer pruebas al aire libre y en barro:
RAW_SECO = 850.0  # Valor analógico típico cuando el sensor está al aire (0%)
RAW_AGUA = 280.0  # Valor analógico típico sumergido en agua/barro (100%)

def calcular_porcentaje_y_status(valor_analogico):
    """
    Mapeo REAL para Sensor Capacitivo V2.0:
    A mayor valor RAW -> Más seco.
    A menor valor RAW -> Más húmedo.
    """
    # Protecciones contra cables sueltos o cortos antes de calcular
    if valor_analogico >= 1020:
        return 0, "\033[91m[ DESCONECTADO / AIR ]\033[0m"
    if valor_analogico <= 10:
        return 100, "\033[91m[ ERROR / CORTO EN GND ]\033[0m"

    # Fórmula de porcentaje inverso para sensores capacitivos
    porcentaje = ((RAW_SECO - valor_analogico) / (RAW_SECO - RAW_AGUA)) * 100
    porcentaje = max(0, min(100, int(porcentaje)))

    # Tramos de valoración corregidos según la física real del hardware
    # Colores ANSI: 91=Rojo, 93=Amarillo, 92=Verde, 94=Azul, 95=Magenta (Negrilla=\033[1m)
    if valor_analogico >= 750:
        status = "\033[91m[ SECO -> Riego requerido ]\033[0m"
    elif valor_analogico >= 600:
        status = "\033[93m[ REGULAR -> Riego requerido ]\033[0m"
    elif valor_analogico >= 450:
        status = "\033[92m[ OPTIMO -> Riego innecesario ]\033[0m"
    elif valor_analogico >= 320:
        status = "\033[94m[ MOJADO -> Riego innecesario ]\033[0m"
    else:
        status = "\033[95m\033[1m[ SATURADO -> Peligro ]\033[0m"

    return porcentaje, status

def render_display():
    # 1. Comprobar existencia de la base de datos JSON
    if not os.path.exists(STATE_FILE):
        os.system('clear')
        print("==================================================")
        print("       AKERBAR MONITOR - TTY LIVE DISPLAY        ")
        print("==================================================")
        print(f"\n[ALERTA] No existe el archivo de estado en la ruta:")
        print(f"         {STATE_FILE}")
        print("         (Asegúrate de que el daemon controlador esté corriendo)\n")
        print("==================================================")
        return

    # 2. Intentar leer el JSON capturando excepciones de sistema
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("[DEBUG DISPLAY] El archivo JSON contiene datos corruptos. Esperando reconstrucción atómica...")
        return
    except IOError as e:
        print(f"[DEBUG DISPLAY] Error de lectura/permisos en el JSON: {e}")
        print("Prueba a lanzar el script con 'sudo' si es necesario.")
        return 

    # 3. Calcular tiempo de consistencia de datos
    ahora = time.time()
    minutos_transcurridos = int((ahora - data.get("timestamp", ahora)) // 60)

    # Estilos ANSI básicos
    VERDE = "\033[92m"
    ROJO = "\033[91m"
    AMARILLO = "\033[93m"
    RESET = "\033[0m"
    NEGRILLA = "\033[1m"

    # Línea dinámica de estado del HUB USB / Humidificador
    if data.get("fan_status") == "ON":
        status_line = f"{VERDE}{NEGRILLA}[ ON ]  (SOPLANDO Y LEYENDO){RESET}"
    else:
        status_line = f"{ROJO}[ OFF ] (REPOSO - ELECTRÓLISIS BLINDADA){RESET}"

    # 4. Recuperar métricas RAW directas
    raw_soil1 = data.get("SOIL1", 1023.0)
    raw_soil2 = data.get("SOIL2", 1023.0)
    raw_soil3 = data.get("SOIL3", 1023.0)
    temp  = data.get("TEMP", 0.0)
    hum   = data.get("HUM", 0.0)

    # 5. Calcular porcentajes y valoraciones dinámicas
    p_soil1, status_soil1 = calcular_porcentaje_y_status(raw_soil1)
    p_soil2, status_soil2 = calcular_porcentaje_y_status(raw_soil2)
    p_soil3, status_soil3 = calcular_porcentaje_y_status(raw_soil3)

    # 6. Renderizar interfaz por consola (TTY)
    os.system('clear')
    print("==================================================")
    print(f"       {NEGRILLA}AKERBAR MONITOR - SALVIA DIVINORUM{RESET}        ")
    print("==================================================")
    print(f"SISTEMA USB : {status_line}\n")
    
    print(f"{NEGRILLA}[SUELO]{RESET}")
    print(f"  - Maceta 1 (RAW: {int(raw_soil1):4}): {p_soil1:3}% Humedad  -> {status_soil1}")
    print(f"  - Maceta 2 (RAW: {int(raw_soil2):4}): {p_soil2:3}% Humedad  -> {status_soil2}")
    print(f"  - Maceta 3 (RAW: {int(raw_soil3):4}): {p_soil3:3}% Humedad  -> {status_soil3}")
    
    print(f"\n{NEGRILLA}[AMBIENTE]{RESET}")
    print(f"  - Temperatura : {temp:.2f} °C")
    print(f"  - Humedad Aire: {hum:.2f} %\n")
    print("--------------------------------------------------")
    
    # Alerta visual si el servicio de fondo lleva más de 22 minutos colgado
    if minutos_transcurridos > 22:
        print(f"{AMARILLO}Última actualización: hace {minutos_transcurridos} min (REVISAR SISTEMA){RESET}")
    else:
        print(f"Lectura tomada hace: {minutos_transcurridos} minutos.")
    print("==================================================")

# =====================================================================
# BUCLE PRINCIPAL DE REFRESCO PARA LA TERMINAL
# =====================================================================
if __name__ == "__main__":
    try:
        while True:
            render_display()
            time.sleep(2)  # Frecuencia de muestreo visual en tu TTY
    except KeyboardInterrupt:
        print("\nMonitor TTY cerrado de forma limpia.")