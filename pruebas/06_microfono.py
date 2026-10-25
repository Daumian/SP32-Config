# 06_microfono.py - Prueba en Thonny (Run, sin guardar en el ESP32)
# Vumetro con un microfono electret: una barra en la OLED que sube con el ruido.
# Sin amplificador solo se notan sonidos fuertes y cercanos (aplauso, soplido,
# golpecito). Ctrl+C para frenar.
#
# Cableado (la pata del mic unida a la carcasa metalica es la de GND):
#   3.3V --[resistencia 2.2k a 10k]--+-- mic (+) , cable rojo
#                                    |
#                                 GPIO 34
#   GND -------------------------------- mic (-) , cable negro
#
# Usamos GPIO 34 porque es del ADC1: los pines del ADC2 no andan con el WiFi
# prendido.

from machine import Pin, I2C, ADC
import ssd1306
import time

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
oled = ssd1306.SSD1306_I2C(128, 32, i2c)

mic = ADC(Pin(34))
mic.atten(ADC.ATTN_11DB)  # rango completo 0 a ~3.3 V

VENTANA_MS = 30    # medimos el ruido en ventanas cortas
SENSIBILIDAD = 4   # mas alto = la barra sube con menos ruido

base = mic.read_u16()
print("Nivel en silencio (0-65535):", base)

while True:
    t0 = time.ticks_ms()
    minimo = maximo = mic.read_u16()
    while time.ticks_diff(time.ticks_ms(), t0) < VENTANA_MS:
        v = mic.read_u16()
        if v < minimo:
            minimo = v
        if v > maximo:
            maximo = v
    ruido = maximo - minimo  # cuanto "se movio" la senal: mas sonido, mas grande

    barra = min(128, ruido * SENSIBILIDAD // 64)
    oled.fill(0)
    oled.text("Ruido: %d" % ruido, 0, 0)
    oled.fill_rect(0, 16, barra, 16, 1)
    oled.show()
    print(ruido)
