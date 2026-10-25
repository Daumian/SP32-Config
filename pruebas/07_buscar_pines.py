# 07_buscar_pines.py - Prueba en Thonny (Run, sin guardar en el ESP32)
# Detective de cables: averigua que cable de una plaquita de botones es masa
# y cual es cada boton. Conectamos los 4 cables a los 4 pines de PINES (en
# cualquier orden), corremos esto y apretamos los botones de a uno.
# Ctrl+C para frenar.
#
# Como funciona: de a uno, pone cada pin a masa (0 V) y deja los otros con
# pull-up (1). Si al apretar un boton algun pin baja a 0, ese boton une esos
# dos cables: uno es la masa y el otro es la senal del boton.

from machine import Pin
import time

PINES = [13, 14, 27, 26]   # pines libres y seguros del ESP32

print("Apretamos los botones de a uno (mantenerlos ~1 segundo)...")
visto = set()

while True:
    for masa in PINES:
        Pin(masa, Pin.OUT, value=0)
        otros = [p for p in PINES if p != masa]
        entradas = [Pin(p, Pin.IN, Pin.PULL_UP) for p in otros]
        time.sleep_ms(5)
        for p, e in zip(otros, entradas):
            if e.value() == 0:
                par = (masa, p)
                if par not in visto:
                    visto.add(par)
                    print("Conexion: GPIO %d (masa?) <-> GPIO %d" % par)
        Pin(masa, Pin.IN, Pin.PULL_UP)  # lo soltamos antes de probar el siguiente
    time.sleep_ms(20)
