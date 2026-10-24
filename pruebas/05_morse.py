# 05_morse.py - Prueba en Thonny (Run, sin guardar en el ESP32)
# Escribimos en codigo Morse con el boton: toque corto = punto, largo = raya.
# Pausa corta cierra la letra, pausa larga agrega un espacio. Ctrl+C para frenar.

from machine import Pin, I2C
import ssd1306
import framebuf
import time

# --- Configuración Hardware ---
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
BOTON_PIN = 0  # BOOT de la placa (antes era 4, con un boton externo)
boton = Pin(BOTON_PIN, Pin.IN, Pin.PULL_UP)

# --- Diccionario Morse ---
MORSE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '.----': '1', '..---': '2', '...--': '3',
    '....-': '4', '.....': '5', '-....': '6', '--...': '7',
    '---..': '8', '----.': '9', '-----': '0'
}

# --- Tiempos de Configuración (ms) ---
T_PUNTO_MAX = 250
T_LETRA = 600
T_ESPACIO = 1200
T_INACTIVIDAD = 120000  # 2 minutos

# --- Variables de Control de Estado ---
texto_final = ""
morse_actual = ""
espacio_anadido = True
pantalla_encendida = True

estado_anterior_phys = 1
tiempo_presionado_phys = 0

tiempo_liberado = time.ticks_ms()
ultimo_cambio = time.ticks_ms()


def draw_large_text(text, x, y):
    """Renderiza texto al doble de tamaño usando un buffer temporal."""
    if not text:
        return
    width = len(text) * 8
    buf = bytearray(width)
    fbuf = framebuf.FrameBuffer(buf, width, 8, framebuf.MONO_VLSB)
    fbuf.text(text, 0, 0)
    for px in range(width):
        for py in range(8):
            if fbuf.pixel(px, py):
                oled.fill_rect(x + px * 2, y + py * 2, 2, 2, 1)


def dibujar_icono_morse(x, y):
    """Icono minimalista: punto - raya - punto."""
    oled.fill_rect(x, y, 3, 3, 1)
    oled.fill_rect(x + 7, y, 11, 3, 1)
    oled.fill_rect(x + 21, y, 3, 3, 1)


def actualizar_pantalla():
    if not pantalla_encendida:
        return
    oled.fill(0)
    texto_mostrar = texto_final[-8:]
    draw_large_text(texto_mostrar, 0, 0)
    oled.text(morse_actual, 0, 22)
    oled.show()


def despertar_pantalla():
    global pantalla_encendida, ultimo_cambio, tiempo_liberado
    oled.poweron()
    oled.fill(0)
    texto = "Codigo Morse"
    x_texto = (128 - len(texto) * 8) // 2
    oled.text(texto, x_texto, 4)
    dibujar_icono_morse((128 - 24) // 2, 18)
    oled.show()
    time.sleep(1.5)
    oled.fill(0)
    oled.show()
    pantalla_encendida = True
    ultimo_cambio = time.ticks_ms()
    tiempo_liberado = time.ticks_ms()
    actualizar_pantalla()


def procesar_pulsacion(duracion):
    global morse_actual, espacio_anadido
    if duracion < T_PUNTO_MAX:
        morse_actual += "."
    else:
        morse_actual += "-"
    espacio_anadido = False
    actualizar_pantalla()


# Inicio del sistema
despertar_pantalla()

while True:
    tiempo_actual = time.ticks_ms()
    b_phys = (boton.value() == 0)

    # Procesar Botón Físico
    if b_phys and estado_anterior_phys == 1:
        tiempo_presionado_phys = tiempo_actual
        estado_anterior_phys = 0
        ultimo_cambio = tiempo_actual
        if not pantalla_encendida:
            despertar_pantalla()
            estado_anterior_phys = 1
    elif not b_phys and estado_anterior_phys == 0:
        duracion_phys = time.ticks_diff(tiempo_actual, tiempo_presionado_phys)
        estado_anterior_phys = 1
        procesar_pulsacion(duracion_phys)
        tiempo_liberado = tiempo_actual
        ultimo_cambio = tiempo_actual

    if pantalla_encendida:
        pausa = time.ticks_diff(tiempo_actual, tiempo_liberado)

        if not b_phys and tiempo_liberado != 0:
            if morse_actual != "" and pausa > T_LETRA:
                letra = MORSE_DICT.get(morse_actual, "?")
                texto_final += letra
                morse_actual = ""
                ultimo_cambio = tiempo_actual
                actualizar_pantalla()
            elif morse_actual == "" and pausa > T_ESPACIO and not espacio_anadido:
                if len(texto_final) > 0 and texto_final[-1] != " ":
                    texto_final += " "
                espacio_anadido = True
                ultimo_cambio = tiempo_actual
                actualizar_pantalla()

        if time.ticks_diff(tiempo_actual, ultimo_cambio) > T_INACTIVIDAD:
            oled.fill(0)
            oled.show()
            oled.poweroff()
            pantalla_encendida = False

    time.sleep(0.01)
