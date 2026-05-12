import obd
import time
import os
import json
import argparse
import socketio
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Nivel de log mínimo para mantener la terminal limpia
obd.logger.setLevel(obd.logging.CRITICAL)

# ─── Socket.IO Client ─────────────────────────────────────────────────────────
sio = socketio.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=2)

ws_connected = False

@sio.event
def connect():
    global ws_connected
    ws_connected = True
    print("🔗 Conectado al backend via WebSocket")

@sio.event
def disconnect():
    global ws_connected
    ws_connected = False
    print("❌ Desconectado del backend")

@sio.on('*')
def catch_all(event, data):
    pass  # Silently handle server events

# ─── Helpers ───────────────────────────────────────────────────────────────────
def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def parse_value(response):
    """Extract a numeric value from an OBD response."""
    if response.is_null():
        return None, True
    val = response.value
    # pint Quantity objects have a .magnitude attribute
    if hasattr(val, 'magnitude'):
        return float(val.magnitude), False
    try:
        return float(val), False
    except (TypeError, ValueError):
        return None, False

def build_sensor_entry(name, cmd, response):
    """Build a sensor dict for the WebSocket payload."""
    value, is_null = parse_value(response)
    # Derive unit from pint or command
    unit = ""
    if not response.is_null() and hasattr(response.value, 'units'):
        unit = str(response.value.units)
    elif hasattr(cmd, 'unit'):
        unit = str(cmd.unit) if cmd.unit else ""
    
    return {
        "pid": cmd.pid if hasattr(cmd, 'pid') else "",
        "name": name,
        "value": value,
        "unit": unit,
        "isNull": is_null,
    }

# ─── Main Diagnostic Loop ─────────────────────────────────────────────────────
def obtener_diagnostico(ws_url: str, serial_port: str, baudrate: int):
    # Conexión OBD
    conn = obd.OBD(serial_port, baudrate=baudrate, fast=False, timeout=30)

    if not conn.is_connected():
        print("❌ Error de conexión. Verifica el adaptador y el encendido.")
        return

    protocol_name = conn.protocol_name()

    # Conectar al backend via WebSocket
    try:
        sio.connect(ws_url, wait_timeout=10, transports=['websocket'],
                    auth=None, headers={},
                    socketio_path='socket.io')
        # Iniciar sesión de diagnóstico
        sio.emit('start-session', {'protocol': protocol_name})
    except Exception as e:
        print(f"⚠️ No se pudo conectar al backend: {e}")
        print("   Continuando en modo local (solo terminal)")

    # Lista de sensores
    sensores = [
        ("RPM del Motor", obd.commands.RPM),
        ("Velocidad", obd.commands.SPEED),
        ("Voltaje del Adaptador", obd.commands.ELM_VOLTAGE),
        ("Temperatura Refrigerante", obd.commands.COOLANT_TEMP),
        ("Carga del Motor", obd.commands.ENGINE_LOAD),
        ("Posición del Acelerador", obd.commands.THROTTLE_POS),
        ("Presión Manifold (MAP)", obd.commands.INTAKE_PRESSURE),
        ("Flujo de Aire (MAF)", obd.commands.MAF),
        ("Temperatura Aire Admisión", obd.commands.INTAKE_TEMP),
        ("Nivel de Combustible", obd.commands.FUEL_LEVEL),
        ("Presión Rampa Combustible", obd.commands.FUEL_RAIL_PRESSURE_DIRECT),
        ("Avance del Encendido", obd.commands.TIMING_ADVANCE),
        ("Estatus de Luz MIL", obd.commands.STATUS),
    ]

    try:
        while True:
            timestamp = time.strftime('%H:%M:%S') + f".{int(time.time() * 1000) % 1000:03d}"
            sensor_entries = []
            mil_status = False

            # ── Terminal output ──
            limpiar_pantalla()
            print(f"--- REPORTE DE SISTEMA OBD-II | Protocolo: {protocol_name} ---")
            print(f"Actualizado: {time.strftime('%H:%M:%S')} (Frecuencia: 1s)")
            print(f"WebSocket: {'🟢 Conectado' if ws_connected else '🔴 Desconectado'}\n")
            print(f"{'PARÁMETRO':<35} | {'VALOR':<25}")
            print("-" * 65)

            for nombre, cmd in sensores:
                res = conn.query(cmd)

                if not res.is_null():
                    if cmd == obd.commands.STATUS:
                        mil_status = bool(res.value.MIL)
                        valor = "⚠️ ENCENDIDA" if res.value.MIL else "✅ APAGADA"
                        print(f"{nombre:<35} | {valor}")
                        print(f"{'Códigos de Error (DTC)':<35} | {res.value.DTC_count} encontrados")
                        # Don't add STATUS to sensor entries, handle separately
                    else:
                        print(f"{nombre:<35} | {res.value}")
                        sensor_entries.append(build_sensor_entry(nombre, cmd, res))
                else:
                    print(f"{nombre:<35} | [No reportado por ECU]")
                    sensor_entries.append(build_sensor_entry(nombre, cmd, res))

            # ── DTC Codes ──
            print("\n" + "=" * 30)
            print("LECTURA DE CÓDIGOS DE ERROR")
            print("=" * 30)
            dtc_res = conn.query(obd.commands.GET_DTC)
            dtc_codes = []

            if not dtc_res.is_null() and dtc_res.value:
                for code, desc in dtc_res.value:
                    print(f"📍 {code}: {desc}")
                    dtc_codes.append({"code": code, "description": desc or ""})
            else:
                print("No se detectaron códigos de falla activos.")

            # ── Send via WebSocket ──
            if ws_connected:
                payload = {
                    "timestamp": timestamp,
                    "protocol": protocol_name,
                    "sensors": sensor_entries,
                    "dtcCodes": dtc_codes,
                    "milStatus": mil_status,
                }
                try:
                    sio.emit('ecu-data', payload)
                except Exception as e:
                    print(f"\n⚠️ Error enviando datos: {e}")

            print(f"\nPresiona Ctrl+C para finalizar.")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nCerrando conexión y liberando puerto...")
    finally:
        # End session and disconnect
        if ws_connected:
            try:
                sio.emit('end-session', {})
                sio.disconnect()
            except Exception:
                pass
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OBD-II Diagnostic Script with WebSocket")
    parser.add_argument("--ws-url", default=os.environ.get("WS_URL", "http://localhost:3000"),
                        help="URL del backend WebSocket (default: from .env or http://localhost:3000)")
    parser.add_argument("--port", default=os.environ.get("OBD_PORT", "COM10"),
                        help="Puerto serial del adaptador ELM327 (default: from .env or COM10)")
    parser.add_argument("--baudrate", type=int, default=int(os.environ.get("OBD_BAUDRATE", "38400")),
                        help="Baudrate del adaptador (default: from .env or 38400)")
    args = parser.parse_args()

    obtener_diagnostico(args.ws_url, args.port, args.baudrate)