# config.py - configuracion del ESP32
#
# Copiar este archivo como "config.py", completar los datos y subirlo
# al ESP32 desde Thonny. El config.py real NO se sube a GitHub
# (esta en .gitignore) porque tiene la clave del WiFi.

WIFI_SSID = "NombreDeTuRed"       # solo redes de 2.4 GHz
WIFI_PASS = "ClaveDeTuRed"

ESP_FRAME_PORT = 8888             # puerto TCP donde escucha el ESP32
HTTP_PORT = 80                    # puerto de la web (pc/index.html)
SHARED_SECRET = "cambiame123"     # tiene que ser IDENTICA a la de app.py

BUTTON_PIN = 4                    # boton externo (0 = boton BOOT de la placa)
SCREEN_TIMEOUT_MS = 3 * 60 * 1000  # 3 minutos sin uso -> apaga la pantalla (opcional)
IDLE_TIMEOUT_MS = 10 * 60 * 1000  # 10 minutos sin actividad -> se duerme

# Plaquita de 2 botones (opcionales; None para no usarla)
PIN_LLAVE2 = 26         # D10, SW1 = otra llave de morse
PIN_INICIO = 14         # D8,  SW2 = volver al inicio
PIN_MASA_PLAQUITA = 27  # D9,  el firmware lo pone en 0 V
PIN_LED = 13            # D5,  LED prendido mientras tocamos
