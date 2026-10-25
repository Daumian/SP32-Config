# 08_parlante.py - Prueba en Thonny (Run, sin guardar en el ESP32)
# Hace sonar un parlantito con PWM: un bip, una escala, SOS en morse y una
# melodia cortita. Ctrl+C para frenar.
#
# Cableado (el parlante no tiene polaridad para esto, da igual el orden):
#   D11 (GPIO 25) --[resistencia]-- cable 1 del parlante
#   I13 (GND) --------------------- cable 2 del parlante
#
# La resistencia NO se saltea: sin ella el parlante (8 ohm) le pide al pin
# mucha mas corriente de la que aguanta. Con 100 a 220 ohm suena bien; con
# 2.2k suena bajito pero sirve para probar.

from machine import Pin, PWM
import time

VOLUMEN = 50  # 1 a 50 (% del ciclo). 50 es lo mas fuerte

pwm = PWM(Pin(25), freq=440, duty_u16=0)


def tono(frecuencia, ms):
    if frecuencia:
        pwm.freq(frecuencia)
        pwm.duty_u16(65535 * VOLUMEN // 100)
    time.sleep_ms(ms)
    pwm.duty_u16(0)


def silencio(ms):
    pwm.duty_u16(0)
    time.sleep_ms(ms)


# notas (Hz)
DO, RE, MI, FA, SOL, LA, SI, DO2 = 262, 294, 330, 349, 392, 440, 494, 523

try:
    print("1) Bip")
    tono(1000, 300)
    silencio(600)

    print("2) Escala")
    for nota in (DO, RE, MI, FA, SOL, LA, SI, DO2):
        tono(nota, 180)
        silencio(40)
    silencio(600)

    print("3) SOS en morse")
    PUNTO = 100
    for simbolo in "... --- ...":
        if simbolo == " ":
            silencio(PUNTO * 3)
            continue
        tono(700, PUNTO if simbolo == "." else PUNTO * 3)
        silencio(PUNTO)
    silencio(600)

    print("4) Melodia")
    for nota, dur in ((MI, 150), (MI, 150), (0, 150), (MI, 150), (0, 150), (DO, 150),
                      (MI, 300), (SOL, 300), (0, 300), (SOL // 2, 300)):
        tono(nota, dur)
        silencio(30)
    print("Listo!")
finally:
    pwm.deinit()  # dejamos el pin quieto
