import obd
import time
import sys

# Activamos el log para ver la negociación de protocolos en la consola
obd.logger.setLevel(obd.logging.DEBUG)

def iniciar_escaneo():
    print("--- Iniciando diagnóstico en Windows ---")
    
    # En Windows, puedes dejarlo vacío para que busque automáticamente
    # o poner el puerto específico: connection = obd.OBD("COM3")
    connection = obd.OBD() 

    if connection.status() == obd.OBDStatus.NOT_CONNECTED:
        print("\n❌ No se detectó el adaptador.")
        print("Asegúrate de que el dispositivo esté vinculado en Windows y el motor encendido.")
        return None
    
    if connection.status() == obd.OBDStatus.ELM_CONNECTED:
        print("\n⚠️  Adaptador conectado, pero la ECU del vehículo no responde.")
        print("Verifica que el switch esté en posición ON o el motor encendido.")
    
    return connection

def monitorear():
    conn = iniciar_escaneo()
    
    if not conn or not conn.is_connected():
        return

    print(f"\n✅ Conexión establecida!")
    print(f"Protocolo: {conn.protocol_name()}")
    print("Presiona Ctrl+C para detener la lectura.\n")

    cmd = obd.commands.RPM

    try:
        while True:
            response = conn.query(cmd)
            
            if not response.is_null():
                # Obtenemos el valor numérico
                valor_rpm = response.value.magnitude
                # \r permite que la línea se sobrescriba en la terminal
                sys.stdout.write(f"\r>> RPM en tiempo real: {valor_rpm:.2f}          ")
                sys.stdout.flush()
            else:
                sys.stdout.write("\r>> Esperando respuesta de la ECU...      ")
                sys.stdout.flush()
            
            # Un delay de 0.1s es ideal para no saturar el bus de datos
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nLectura finalizada por el usuario.")
    finally:
        conn.close()
        print("Puerto COM liberado.")

if __name__ == "__main__":
    monitorear()