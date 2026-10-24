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

BUTTON_PIN = 0                    # boton BOOT de la placa
IDLE_TIMEOUT_MS = 10 * 60 * 1000  # 10 minutos sin actividad -> se duerme
