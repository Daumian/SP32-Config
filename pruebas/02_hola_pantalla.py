# 02_hola_pantalla.py - Prueba en Thonny (Run, sin guardar en el ESP32)
# Escanea el bus I2C y escribe un texto de prueba en la OLED.
# Esperado en la consola: Dispositivos I2C: ['0x3c']

from machine import Pin, I2C
import ssd1306

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
print("Dispositivos I2C:", [hex(d) for d in i2c.scan()])

oled = ssd1306.SSD1306_I2C(128, 32, i2c)
oled.fill(0)
oled.text("Hola ESP32!", 0, 0)
oled.text("128 x 32 OK", 0, 12)
oled.rect(0, 24, 128, 8, 1)
oled.show()
