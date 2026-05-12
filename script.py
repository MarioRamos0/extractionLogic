import obd
import time
import os

# Nivel de log mínimo para mantener la terminal limpia
obd.logger.setLevel(obd.logging.CRITICAL)

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def obtener_diagnostico():
    # Conexión optimizada (Modo estable para clones v2.1)
    conn = obd.OBD("COM10", baudrate=38400, fast=False, timeout=30)

    if not conn.is_connected():
        print("❌ Error de conexión. Verifica el adaptador y el encendido.")
        return

    # Lista de comandos corregida y ampliada
    sensores = [
        ("RPM del Motor", obd.commands.RPM),
        ("Velocidad", obd.commands.SPEED),
        ("Voltaje del Adaptador", obd.commands.ELM_VOLTAGE),
        ("Temperatura Refrigerante", obd.commands.COOLANT_TEMP),
        ("Carga del Motor", obd.commands.ENGINE_LOAD),
        ("Posición del Acelerador", obd.commands.THROTTLE_POS),
        ("Presión Manifold (MAP)", obd.commands.INTAKE_PRESSURE), # Nombre corregido
        ("Flujo de Aire (MAF)", obd.commands.MAF),
        ("Temperatura Aire Admisión", obd.commands.INTAKE_TEMP),
        ("Nivel de Combustible", obd.commands.FUEL_LEVEL),
        ("Presión Rampa Combustible", obd.commands.FUEL_RAIL_PRESSURE_DIRECT),
        ("Avance del Encendido", obd.commands.TIMING_ADVANCE),
        ("Estatus de Luz MIL", obd.commands.STATUS),
    ]

    try:
        while True:
            limpiar_pantalla()
            print(f"--- REPORTE DE SISTEMA OBD-II | Protocolo: {conn.protocol_name()} ---")
            print(f"Actualizado: {time.strftime('%H:%M:%S')} (Frecuencia: 3s)\n")
            print(f"{'PARÁMETRO':<35} | {'VALOR':<25}")
            print("-" * 65)

            for nombre, cmd in sensores:
                res = conn.query(cmd)
                
                if not res.is_null():
                    if cmd == obd.commands.STATUS:
                        valor = "⚠️ ENCENDIDA" if res.value.MIL else "✅ APAGADA"
                        print(f"{nombre:<35} | {valor}")
                        print(f"{'Códigos de Error (DTC)':<35} | {res.value.DTC_count} encontrados")
                    else:
                        print(f"{nombre:<35} | {res.value}")
                else:
                    print(f"{nombre:<35} | [No reportado por ECU]")

            # Sección de Códigos de Falla (DTC)
            print("\n" + "="*30)
            print("LECTURA DE CÓDIGOS DE ERROR")
            print("="*30)
            dtc_res = conn.query(obd.commands.GET_DTC)
            
            if not dtc_res.is_null() and dtc_res.value:
                for code, desc in dtc_res.value:
                    print(f"📍 {code}: {desc}")
            else:
                print("No se detectaron códigos de falla activos.")

            print("\nPresiona Ctrl+C para finalizar.")
            time.sleep(3) # Pausa de 3 segundos solicitada

    except KeyboardInterrupt:
        print("\n\nCerrando conexión y liberando puerto...")
    finally:
        conn.close()

if __name__ == "__main__":
    obtener_diagnostico()