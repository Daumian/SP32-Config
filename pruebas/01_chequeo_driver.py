# 01_chequeo_driver.py - Prueba en Thonny (Run, sin guardar en el ESP32)
# Confirma que el driver ssd1306 esta instalado y dice donde vive.
# Esperado en la consola: /lib/ssd1306.py

import ssd1306
print(ssd1306.__file__)
