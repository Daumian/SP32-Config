# main.py - ESP32 + OLED SSD1306 (128x32) + boton (cfg.BUTTON_PIN), manejado en morse
#
# Primer toque: despierta y saluda ("Bienvenido / Que necesita?").
# Despues el boton es una llave de morse:
#   toque corto = punto, toque largo = raya
#   pausa corta = cierra la letra, pausa larga = cierra la palabra
#   mantener apretado 2 s = dormir
# Plaquita de 2 botones (opcional): SW1 es otra llave de morse (igual que el
# boton), SW2 vuelve al inicio, y su LED se prende mientras tocamos.
# Una palabra de UNA sola letra es un comando: W (WiFi) y B (Bluetooth) son
# fijos; el resto de la A a la Z corre el codigo Python guardado para esa
# letra en /letras/<L>.py, que se edita desde el panel web (X = imagen y
# M = escritura libre vienen de fabrica). Una letra sin codigo queda como
# texto. En escritura libre no hay comandos; mas de 6 puntos seguidos sale.
# Mientras tocamos la llave suena un bip en el parlantito (cfg.PIN_PARLANTE).
# 3 min sin uso apaga la pantalla (el WiFi sigue); 10 min duerme del todo.
#
# Con el WiFi prendido escucha frames de la PC por TCP (cfg.ESP_FRAME_PORT):
#   "clave:FRAME\n" + 512 bytes  -> dibuja el frame (MONO_VLSB)
#   "clave:RESET\n"              -> reinicia la placa
#   "clave\n" + 512 bytes        -> igual que FRAME (formato viejo)
#   conexion vacia               -> ping de /status, se ignora en silencio
#
# Y tambien un mini servidor HTTP (cfg.HTTP_PORT, 80 por defecto) para
# pc/index.html. Todas las rutas menos /estado piden ?clave=SHARED_SECRET:
#   GET  /                       -> sirve index.html (si lo subimos a la placa)
#   GET  /estado                 -> JSON con wifi, bluetooth y texto
#   POST /frame?clave=...        -> cuerpo de 512 bytes, se dibuja
#   POST /comando?clave=...&letra=B  -> ejecuta el comando de esa letra
#   GET  /letras?clave=...       -> codigo de cada letra A-Z
#   POST /letra?clave=...&l=A    -> guarda el codigo de la letra (cuerpo = Python)
#   POST /bloquear?clave=...&l=A&si=1  -> bloquea (si=1) o desbloquea (si=0) la letra
#   POST /titulo?clave=...&l=A&t=Luz   -> titulo de la letra (hasta 10 letras, lo usa la H)
#   POST /probar?clave=...       -> corre el Python del cuerpo sin guardarlo
#   POST /reset?clave=...        -> reinicia la placa

import network
import usocket as socket
import time
import os
import json
import select
import machine
import framebuf
import bluetooth
from machine import Pin, I2C, PWM
import ssd1306
import config as cfg
import imagenes

WIDTH = 128
HEIGHT = 32
FRAME_BYTES = WIDTH * HEIGHT // 8  # 512
HTTP_PORT = getattr(cfg, "HTTP_PORT", 80)
SCREEN_TIMEOUT_MS = getattr(cfg, "SCREEN_TIMEOUT_MS", 3 * 60 * 1000)
# Plaquita de 2 botones: pines de GPIO (None en config.py para no usarla).
# Su cable de masa va a un pin que ponemos en 0 V, asi no gastamos un GND.
PIN_LLAVE2 = getattr(cfg, "PIN_LLAVE2", 26)     # D10, SW1: llave de morse
PIN_INICIO = getattr(cfg, "PIN_INICIO", 14)     # D8, SW2: volver al inicio
PIN_MASA_PLAQUITA = getattr(cfg, "PIN_MASA_PLAQUITA", 27)  # D9
PIN_LED = getattr(cfg, "PIN_LED", 13)           # D5
PIN_PARLANTE = getattr(cfg, "PIN_PARLANTE", 25)  # D11, con resistencia en serie
TONO_MORSE = getattr(cfg, "TONO_MORSE", 700)     # Hz del bip mientras tocamos
VOLUMEN = getattr(cfg, "VOLUMEN", 50)            # 1 a 50 (% del ciclo)
CARPETA_LETRAS = "letras"
FIJAS = ("W", "B")  # no se editan: sin la W no hay forma de arreglar nada por WiFi
CODIGO_INICIAL = {
    "X": "imagen()\n",
    "M": "escritura_libre()\n",
    "H": "ayuda()\n",
}
LARGO_TITULO = 10
TITULOS_FIJOS = {"W": "WiFi", "B": "Bluetooth"}
TITULO_INICIAL = {"X": "Imagen", "M": "Escritura", "H": "Ayuda"}
MIN_PUNTOS_SALIR = 7  # mas de 6 puntos seguidos sale de la escritura libre
LETRAS_VISIBLES = 10  # letra de 12 px: entran 10 en un renglon

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)
button = Pin(cfg.BUTTON_PIN, Pin.IN, Pin.PULL_UP)
if PIN_MASA_PLAQUITA is not None:
    Pin(PIN_MASA_PLAQUITA, Pin.OUT, value=0)
led = Pin(PIN_LED, Pin.OUT, value=0) if PIN_LED is not None else None
llaves = [button] + ([Pin(PIN_LLAVE2, Pin.IN, Pin.PULL_UP)] if PIN_LLAVE2 is not None else [])
boton_inicio = Pin(PIN_INICIO, Pin.IN, Pin.PULL_UP) if PIN_INICIO is not None else None
parlante = PWM(Pin(PIN_PARLANTE), freq=TONO_MORSE, duty_u16=0) if PIN_PARLANTE is not None else None
wlan = network.WLAN(network.STA_IF)
ble = bluetooth.BLE()

MORSE = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '.----': '1', '..---': '2', '...--': '3',
    '....-': '4', '.....': '5', '-....': '6', '--...': '7',
    '---..': '8', '----.': '9', '-----': '0'
}

# Tiempos (ms)
T_REBOTE = 20        # toques mas cortos que esto se ignoran
T_PUNTO_MAX = 250    # hasta aca es punto, mas largo es raya
T_LETRA = 600        # pausa que cierra la letra
T_ESPACIO = 1200     # pausa que cierra la palabra
T_DORMIR = 2000      # mantener apretado = dormir
T_MENSAJE = 1500     # cuanto queda un mensaje de comando en pantalla
T_VENTANA_EDICION = 2000  # al arrancar, tocar BOOT en este tiempo = modo edicion

STATE_SLEEP = 0
STATE_AWAKE = 1
state = STATE_SLEEP

last_activity = time.ticks_ms()
srv_socket = None
http_socket = None
http_pendientes = []  # [conn, addr, t0]: conexiones que todavia no mandaron nada
MAX_PENDIENTES = 6
T_PENDIENTE = 5000    # una conexion callada mas de esto se cierra

texto = ""
palabra = ""
morse_actual = ""
presionado_desde = None
soltado_en = time.ticks_ms()
escritura_libre = False
pantalla_on = False
ignorar_toque = False  # el toque que prende la pantalla no cuenta como morse
inicio_antes = 1
sonando = False
ultimo_error = ""
ultimo_toque_us = 0  # microsegundos del ultimo toque: suma azar a azar()


# ---------------------------------------------------------------- pantalla

def show_lines(*lines):
    oled.fill(0)
    y = 0
    for line in lines:
        oled.text(line, 0, y)
        y += 12
    oled.show()


def draw_scaled_text(text, x, y, num=3, den=2):
    """Texto agrandado num/den veces (3/2 = letra de 12 px)."""
    if not text:
        return
    width = len(text) * 8
    buf = bytearray(width)
    fbuf = framebuf.FrameBuffer(buf, width, 8, framebuf.MONO_VLSB)
    fbuf.text(text, 0, 0)
    for px in range(width):
        x0 = px * num // den
        x1 = (px + 1) * num // den
        for py in range(8):
            if fbuf.pixel(px, py):
                y0 = py * num // den
                y1 = (py + 1) * num // den
                oled.fill_rect(x + x0, y + y0, x1 - x0, y1 - y0, 1)


def dibujar():
    oled.fill(0)
    draw_scaled_text(texto[-LETRAS_VISIBLES:], 4, 4)
    y = 24
    oled.text(morse_actual[-10:], 0, y)
    # indicadores abajo a la derecha
    if escritura_libre:
        oled.text("M", 88, y)
    if wlan.isconnected():
        oled.text("W", 104, y)
    if ble.active():
        oled.text("B", 120, y)
    oled.show()


def prender_pantalla():
    global pantalla_on
    if not pantalla_on:
        oled.poweron()
        pantalla_on = True


def apagar_pantalla():
    global pantalla_on
    oled.fill(0)
    oled.show()
    oled.poweroff()
    pantalla_on = False
    print("Pantalla apagada (sin uso)")


def mostrar_frame(data):
    global last_activity
    prender_pantalla()
    oled.buffer[:] = data
    oled.show()
    last_activity = time.ticks_ms()


def mensaje(*lines, ms=T_MENSAJE):
    show_lines(*lines)
    time.sleep_ms(ms)


# ---------------------------------------------------------------- wifi

def wifi_on():
    wlan.active(True)
    wlan.connect(cfg.WIFI_SSID, cfg.WIFI_PASS)
    t0 = time.ticks_ms()
    while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 10000:
        time.sleep_ms(200)
    return wlan.isconnected()


def wifi_off():
    global srv_socket, http_socket
    for s in (srv_socket, http_socket):
        if s:
            try:
                s.close()
            except Exception:
                pass
    srv_socket = http_socket = None
    for c in http_pendientes:
        try:
            c[0].close()
        except Exception:
            pass
    http_pendientes.clear()
    try:
        wlan.disconnect()
    except Exception:
        pass
    wlan.active(False)


def abrir_servidor(puerto):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', puerto))
    s.listen(4)
    s.settimeout(0)  # no bloqueante
    return s


def start_frame_server():
    global srv_socket, http_socket
    srv_socket = abrir_servidor(cfg.ESP_FRAME_PORT)
    http_socket = abrir_servidor(HTTP_PORT)


# ---------------------------------------------------------------- comandos

def cmd_bluetooth():
    antes = ble.active()
    ble.active(not antes)
    mensaje("Bluetooth: " + ("ON" if antes else "OFF"),
            "Ahora: " + ("ON" if ble.active() else "OFF"))


def cmd_wifi():
    if wlan.isconnected():
        wifi_off()
        mensaje("WiFi: ON", "Ahora: OFF")
        return
    show_lines("WiFi: OFF", "Conectando...")
    if wifi_on():
        start_frame_server()
        ip = wlan.ifconfig()[0]
        print("WiFi conectado. IP:", ip)
        mensaje("WiFi: ON", ip, ms=3000)
    else:
        wifi_off()
        mensaje("WiFi: OFF", "No conecto :(")


COMANDOS = {  # los fijos; las demas letras usan el codigo guardado
    'B': cmd_bluetooth,
    'W': cmd_wifi,
}


# ---------------------------------------------------------------- sonido

def sonar(frecuencia):
    global sonando
    if parlante is None:
        return
    parlante.freq(frecuencia)
    parlante.duty_u16(65535 * VOLUMEN // 100)
    sonando = True


def callar():
    global sonando
    if parlante is not None and sonando:
        parlante.duty_u16(0)
    sonando = False


# ---------------------------------------------------------------- letras programables

class Cortado(Exception):
    pass


def esperar(ms):
    """Espera, pero si apretamos SW2 (inicio) corta el codigo que esta corriendo."""
    fin = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(fin, time.ticks_ms()) > 0:
        if boton_inicio is not None and boton_inicio.value() == 0:
            raise Cortado()
        time.sleep_ms(10)


def mostrar(*lineas):
    prender_pantalla()
    show_lines(*[str(x) for x in lineas])


def tono(frecuencia, ms=200):
    sonar(frecuencia)
    try:
        esperar(ms)
    finally:
        callar()


def prender_led(prendido=True):
    if led:
        led.value(1 if prendido else 0)


def imagen(ms=3000):
    prender_pantalla()
    oled.buffer[:] = imagenes.IMAGEN_X
    oled.show()
    esperar(ms)


def empezar_escritura_libre():
    global escritura_libre, texto
    escritura_libre = True
    texto = ""
    mensaje("Escritura libre", "7+ puntos=salir", ms=2000)


def deslizar(txt, paso=3, ms=25):
    """Cartel que cruza la pantalla de derecha a izquierda (letra de 12 px)."""
    prender_pantalla()
    txt = str(txt)
    # dibujamos el texto agrandado una sola vez y despues solo lo corremos
    chico = bytearray(len(txt) * 8)
    fchico = framebuf.FrameBuffer(chico, len(txt) * 8, 8, framebuf.MONO_VLSB)
    fchico.text(txt, 0, 0)
    ancho = len(txt) * 12
    grande = bytearray(ancho * 2)  # 16 px de alto = 2 paginas
    fgrande = framebuf.FrameBuffer(grande, ancho, 16, framebuf.MONO_VLSB)
    for px in range(len(txt) * 8):
        x0, x1 = px * 3 // 2, (px + 1) * 3 // 2
        for py in range(8):
            if fchico.pixel(px, py):
                y0, y1 = py * 3 // 2, (py + 1) * 3 // 2
                fgrande.fill_rect(x0, y0, x1 - x0, y1 - y0, 1)
    for x in range(WIDTH, -ancho, -paso):
        oled.fill(0)
        oled.blit(fgrande, x, 10)
        oled.show()
        esperar(ms)


def leer_titulos():
    try:
        with open(CARPETA_LETRAS + "/titulos.json") as f:
            return json.loads(f.read())
    except (OSError, ValueError):
        return {}


def titulo_de(letra, titulos=None):
    if letra in TITULOS_FIJOS:
        return TITULOS_FIJOS[letra]
    if titulos is None:
        titulos = leer_titulos()
    return titulos.get(letra, TITULO_INICIAL.get(letra, ""))


def guardar_titulo(letra, titulo):
    # la pantalla solo tiene letras sin acentos
    titulo = "".join(c for c in titulo if 32 <= ord(c) < 127).strip()[:LARGO_TITULO]
    titulos = leer_titulos()
    titulos[letra] = titulo
    try:
        os.mkdir(CARPETA_LETRAS)
    except OSError:
        pass  # ya existia
    with open(CARPETA_LETRAS + "/titulos.json", "w") as f:
        f.write(json.dumps(titulos))
    return titulo


def esperar_toques(max_espera=None):
    """Espera que toquemos la llave y devuelve lo que tocamos ("...", "-", etc).

    Termina cuando hacemos una pausa de letra. Devuelve "" si pasan max_espera
    ms sin tocar nada. Mientras tocamos suena el bip y se prende el LED.
    SW2 corta el codigo, como en esperar().
    """
    global ultimo_toque_us
    inicio = time.ticks_ms()
    simbolos = ""
    apretado_desde = None
    soltado = inicio
    while True:
        if boton_inicio is not None and boton_inicio.value() == 0:
            callar()
            prender_led(False)
            raise Cortado()
        ahora = time.ticks_ms()
        if llave_apretada():
            if apretado_desde is None:
                apretado_desde = ahora
                sonar(TONO_MORSE)
                prender_led(True)
        elif apretado_desde is not None:
            dur = time.ticks_diff(ahora, apretado_desde)
            callar()
            prender_led(False)
            if dur >= T_REBOTE:
                simbolos += "." if dur < T_PUNTO_MAX else "-"
                ultimo_toque_us = time.ticks_us()
            apretado_desde = None
            soltado = ahora
        elif simbolos and time.ticks_diff(ahora, soltado) > T_LETRA:
            return simbolos
        elif not simbolos and max_espera is not None and time.ticks_diff(ahora, inicio) > max_espera:
            return ""
        time.sleep_ms(5)


def azar(desde, hasta):
    """Numero al azar entre desde y hasta (incluidos).

    Mezcla el generador por hardware del ESP32 (ruido de la radio) con los
    microsegundos del ultimo toque, que nadie puede repetir igual.
    """
    semilla = int.from_bytes(os.urandom(4), "little") ^ ultimo_toque_us ^ time.ticks_us()
    return desde + semilla % (hasta - desde + 1)


def mostrar_grande(txt, escala=3):
    """Texto gigante y centrado (escala 3 = letras de 24 px, entran 5)."""
    prender_pantalla()
    txt = str(txt)
    oled.fill(0)
    draw_scaled_text(txt, max(0, (WIDTH - len(txt) * 8 * escala) // 2),
                     (HEIGHT - 8 * escala) // 2, escala, 1)
    oled.show()


def ayuda():
    """La lista de letras con algo asignado, deslizandose por la pantalla."""
    titulos = leer_titulos()
    partes = [l + ":" + (titulo_de(l, titulos) or "?") for l in letras_con_comando()]
    deslizar("   ".join(partes))


# lo que tiene a mano el codigo de cada letra
AYUDANTES = {
    "mostrar": mostrar,            # mostrar("Hola", "mundo"): hasta 3 renglones
    "tono": tono,                  # tono(440, 300): frecuencia en Hz, duracion en ms
    "esperar": esperar,            # esperar(1000): ms; SW2 corta el codigo
    "led": prender_led,            # led(True) / led(False)
    "imagen": imagen,              # imagen(): muestra IMAGEN_X 3 segundos
    "escritura_libre": empezar_escritura_libre,
    "deslizar": deslizar,          # deslizar("Hola!"): cartel que cruza la pantalla
    "mostrar_grande": mostrar_grande,  # mostrar_grande("7"): gigante y centrado
    "esperar_toques": esperar_toques,  # esperar_toques(30000): "...", "-", o "" si no tocamos
    "azar": azar,                  # azar(1, 6): numero al azar (hardware + tus toques)
    "ayuda": ayuda,                # ayuda(): lista de letras con su titulo
    "oled": oled,
    "Pin": Pin,
    "time": time,
}


def ruta_letra(letra):
    return CARPETA_LETRAS + "/" + letra + ".py"


def letras_guardadas():
    try:
        return [n[0] for n in os.listdir(CARPETA_LETRAS) if n.endswith(".py") and len(n) == 4]
    except OSError:
        return []


def leer_codigo(letra):
    try:
        with open(ruta_letra(letra)) as f:
            return f.read()
    except OSError:
        return CODIGO_INICIAL.get(letra, "")


def guardar_codigo(letra, codigo):
    """Codigo vacio = borra el archivo (la letra vuelve a lo de fabrica)."""
    try:
        os.mkdir(CARPETA_LETRAS)
    except OSError:
        pass  # ya existia
    if codigo.strip():
        with open(ruta_letra(letra), "w") as f:
            f.write(codigo)
    else:
        try:
            os.remove(ruta_letra(letra))
        except OSError:
            pass


def ruta_bloqueadas():
    return CARPETA_LETRAS + "/bloqueadas.txt"


def leer_bloqueadas():
    """Letras con bloqueo suave: no se editan hasta destildar el candado."""
    try:
        with open(ruta_bloqueadas()) as f:
            return f.read().strip()
    except OSError:
        return ""


def poner_bloqueo(letra, bloquear):
    letras = set(leer_bloqueadas())
    if bloquear:
        letras.add(letra)
    else:
        letras.discard(letra)
    try:
        os.mkdir(CARPETA_LETRAS)
    except OSError:
        pass  # ya existia
    with open(ruta_bloqueadas(), "w") as f:
        f.write("".join(sorted(letras)))


def letras_con_comando():
    return sorted(set(COMANDOS) | set(CODIGO_INICIAL) | set(letras_guardadas()))


def correr_codigo(codigo, nombre):
    """Corre el Python de una letra. Devuelve el error como texto, o "" si anduvo."""
    global ultimo_error, soltado_en, last_activity
    prender_pantalla()
    ultimo_error = ""
    try:
        exec(codigo, dict(AYUDANTES))
    except Cortado:
        mensaje("Cortado", ms=800)
    except Exception as e:
        ultimo_error = "%s: %s" % (type(e).__name__, e)
        print("Error en", nombre, "->", ultimo_error)
        mensaje("Error en " + nombre, ultimo_error[:16], ultimo_error[16:32], ms=3000)
    finally:
        callar()
        prender_led(False)
    soltado_en = last_activity = time.ticks_ms()
    return ultimo_error


# ---------------------------------------------------------------- morse

def agregar_texto(t):
    global texto
    texto = (texto + t)[-40:]


def cerrar_letra():
    global morse_actual, texto, palabra, escritura_libre
    if (escritura_libre and len(morse_actual) >= MIN_PUNTOS_SALIR
            and morse_actual.count(".") == len(morse_actual)):
        morse_actual = ""
        escritura_libre = False
        palabra = ""
        texto = ""
        print("Fin de escritura libre")
        mensaje("Fin escritura", "Que necesita?")
        dibujar()
        return
    letra = MORSE.get(morse_actual, "?")
    morse_actual = ""
    agregar_texto(letra)
    palabra += letra
    dibujar()


def ejecutar_comando(letra):
    """Corre lo que tenga asignado la letra. Devuelve False si no tiene nada."""
    global soltado_en, last_activity
    if letra in COMANDOS:
        print("Comando:", letra)
        prender_pantalla()
        COMANDOS[letra]()
        soltado_en = last_activity = time.ticks_ms()
        return True
    codigo = leer_codigo(letra)
    if not codigo.strip():
        return False
    print("Codigo de la letra:", letra)
    correr_codigo(codigo, letra)
    return True


def cerrar_palabra():
    global texto, palabra
    p = palabra
    palabra = ""
    if not escritura_libre and len(p) == 1 and p in letras_con_comando():
        texto = texto[:-1]  # el comando no queda escrito
        ejecutar_comando(p)
    else:
        agregar_texto(" ")
    dibujar()


def leer_boton():
    global presionado_desde, soltado_en, morse_actual, last_activity, ignorar_toque
    now = time.ticks_ms()
    apretada = llave_apretada()
    if led:
        led.value(1 if apretada and pantalla_on else 0)
    if apretada and pantalla_on and not ignorar_toque:
        if not sonando:
            sonar(TONO_MORSE)  # el bip de morse mientras tocamos
    else:
        callar()
    if apretada:
        if presionado_desde is None:
            presionado_desde = now
            last_activity = now
            if not pantalla_on:
                prender_pantalla()
                dibujar()
                ignorar_toque = True
        elif time.ticks_diff(now, presionado_desde) > T_DORMIR:
            presionado_desde = None
            go_to_sleep()
            esperar_que_suelte()
        return

    if presionado_desde is None:
        return
    dur = time.ticks_diff(now, presionado_desde)
    presionado_desde = None
    if ignorar_toque:
        ignorar_toque = False
        soltado_en = now
        return
    if dur < T_REBOTE:
        return
    morse_actual += "." if dur < T_PUNTO_MAX else "-"
    soltado_en = now
    last_activity = now
    dibujar()


def llave_apretada():
    return any(k.value() == 0 for k in llaves)


def algun_boton_apretado():
    return llave_apretada() or (boton_inicio is not None and boton_inicio.value() == 0)


def ir_al_inicio():
    global texto, palabra, morse_actual, escritura_libre, soltado_en, last_activity
    texto = palabra = morse_actual = ""
    escritura_libre = False
    prender_pantalla()
    mensaje("Inicio", "Que necesita?", ms=1000)
    soltado_en = last_activity = time.ticks_ms()
    dibujar()


def leer_boton_inicio():
    global inicio_antes
    if boton_inicio is None:
        return
    v = boton_inicio.value()
    if v == 0 and inicio_antes == 1:
        print("Volver al inicio")
        ir_al_inicio()
    inicio_antes = v


def revisar_pausas():
    if presionado_desde is not None:
        return
    pausa = time.ticks_diff(time.ticks_ms(), soltado_en)
    if morse_actual and pausa > T_LETRA:
        cerrar_letra()
    elif not morse_actual and palabra and pausa > T_ESPACIO:
        cerrar_palabra()


# ---------------------------------------------------------------- frames de la PC

def read_header(conn):
    header = b""
    while b"\n" not in header and len(header) < 64:
        b = conn.recv(1)
        if not b:
            break
        header += b
    return header.decode().strip()


def read_frame(conn):
    data = b""
    while len(data) < FRAME_BYTES:
        chunk = conn.recv(FRAME_BYTES - len(data))
        if not chunk:
            break
        data += chunk
    return data


def check_incoming_frame():
    global last_activity
    if srv_socket is None:
        return
    try:
        conn, addr = srv_socket.accept()
    except OSError:
        return
    conn.settimeout(2)
    try:
        header = read_header(conn)
        if not header:
            return  # ping de /status: solo queria saber si estamos vivos

        secret, _, cmd = header.partition(":")
        if secret != cfg.SHARED_SECRET:
            print("Clave incorrecta, se ignora conexion de", addr[0])
            return

        cmd = cmd or "FRAME"
        if cmd == "FRAME":
            data = read_frame(conn)
            if len(data) == FRAME_BYTES:
                mostrar_frame(data)
            else:
                print("Frame incompleto:", len(data), "bytes")
        elif cmd == "RESET":
            print("RESET pedido desde", addr[0])
            show_lines("Reiniciando...")
            conn.close()
            time.sleep_ms(300)
            machine.reset()
        else:
            print("Comando desconocido:", cmd)
    except Exception as e:
        print("Error leyendo frame:", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------- HTTP (para pc/index.html)

def unquote(s):
    s = s.replace("+", " ")
    partes = s.split("%")
    out = partes[0]
    for p in partes[1:]:
        try:
            out += chr(int(p[:2], 16)) + p[2:]
        except ValueError:
            out += "%" + p
    return out


def leer_peticion(conn):
    data = b""
    while b"\r\n\r\n" not in data and len(data) < 2048:
        chunk = conn.recv(256)
        if not chunk:
            break
        data += chunk
    cabeza, _, cuerpo = data.partition(b"\r\n\r\n")
    lineas = cabeza.decode().split("\r\n")
    metodo, ruta, _ = lineas[0].split(" ", 2)
    largo = 0
    for linea in lineas[1:]:
        k, _, v = linea.partition(":")
        if k.strip().lower() == "content-length":
            largo = min(int(v.strip()), 8192)
    while len(cuerpo) < largo:
        chunk = conn.recv(largo - len(cuerpo))
        if not chunk:
            break
        cuerpo += chunk
    ruta, _, qs = ruta.partition("?")
    params = {}
    for par in qs.split("&"):
        k, _, v = par.partition("=")
        if k:
            params[k] = unquote(v)
    return metodo, ruta, params, cuerpo


def servir_archivo(conn, nombre, tipo):
    try:
        f = open(nombre, "rb")
    except OSError:
        responder(conn, "404 Not Found", {"error": "falta " + nombre + " en la placa"})
        return
    try:
        conn.sendall((
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: " + tipo + "\r\n"
            "Connection: close\r\n\r\n").encode())
        while True:
            pedazo = f.read(1024)
            if not pedazo:
                break
            conn.sendall(pedazo)
    finally:
        f.close()


def responder(conn, codigo, datos=None):
    cuerpo = json.dumps(datos).encode() if datos is not None else b""
    conn.sendall((
        "HTTP/1.1 " + codigo + "\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        "Access-Control-Allow-Headers: *\r\n"
        "Access-Control-Allow-Private-Network: true\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: " + str(len(cuerpo)) + "\r\n"
        "Connection: close\r\n\r\n").encode())
    if cuerpo:
        conn.sendall(cuerpo)


def check_http():
    """Acepta conexiones sin bloquear y solo atiende las que ya mandaron algo.

    Chrome abre conexiones "de reserva" que no mandan nada; si las leyeramos
    de una, la placa se quedaria trabada esperando.
    """
    if http_socket is None:
        return
    while len(http_pendientes) < MAX_PENDIENTES:
        try:
            conn, addr = http_socket.accept()
        except OSError:
            break
        http_pendientes.append([conn, addr, time.ticks_ms()])
    if not http_pendientes:
        return

    poller = select.poll()
    for c in http_pendientes:
        poller.register(c[0], select.POLLIN)
    listos = [ev[0] for ev in poller.poll(0)]

    ahora = time.ticks_ms()
    for c in http_pendientes[:]:
        conn, addr, t0 = c
        if conn in listos:
            http_pendientes.remove(c)
            atender_http(conn, addr)
        elif time.ticks_diff(ahora, t0) > T_PENDIENTE:
            http_pendientes.remove(c)
            try:
                conn.close()
            except Exception:
                pass


def atender_http(conn, addr):
    global last_activity
    conn.settimeout(2)
    despues = None  # lo que se ejecuta una vez cerrada la conexion
    try:
        metodo, ruta, params, cuerpo = leer_peticion(conn)
        if metodo == "OPTIONS":
            responder(conn, "204 No Content")
        elif ruta in ("/", "/index.html") and metodo == "GET":
            servir_archivo(conn, "index.html", "text/html; charset=utf-8")
        elif ruta == "/estado":
            responder(conn, "200 OK", {
                "wifi": wlan.isconnected(),
                "bluetooth": ble.active(),
                "texto": texto,
                "escritura_libre": escritura_libre,
                "pantalla": pantalla_on,
                "comandos": letras_con_comando(),
                "error": ultimo_error,
            })
        elif params.get("clave") != cfg.SHARED_SECRET:
            print("HTTP: clave incorrecta desde", addr[0])
            responder(conn, "403 Forbidden", {"error": "clave incorrecta"})
        elif ruta == "/frame" and metodo == "POST":
            if len(cuerpo) == FRAME_BYTES:
                mostrar_frame(cuerpo)
                responder(conn, "200 OK", {"ok": True})
            else:
                responder(conn, "400 Bad Request",
                          {"error": "el frame tiene que ser de 512 bytes"})
        elif ruta == "/comando" and metodo == "POST":
            letra = params.get("letra", "").upper()
            if letra in letras_con_comando():
                responder(conn, "200 OK", {"ok": True, "letra": letra})
                despues = letra
            else:
                responder(conn, "404 Not Found", {"error": "esa letra no tiene comando"})
        elif ruta == "/letras" and metodo == "GET":
            inverso = {v: k for k, v in MORSE.items()}
            bloqueadas = leer_bloqueadas()
            titulos = leer_titulos()
            letras = {}
            for n in range(26):
                l = chr(65 + n)
                letras[l] = {
                    "morse": inverso[l],
                    "fija": l in FIJAS,
                    "bloqueada": l in bloqueadas,
                    "codigo": "" if l in FIJAS else leer_codigo(l),
                    "inicial": CODIGO_INICIAL.get(l, ""),
                    "titulo": titulo_de(l, titulos),
                }
            responder(conn, "200 OK", {"letras": letras, "error": ultimo_error})
        elif ruta == "/letra" and metodo == "POST":
            letra = params.get("l", "").upper()
            if len(letra) != 1 or not "A" <= letra <= "Z":
                responder(conn, "400 Bad Request", {"error": "letra invalida"})
            elif letra in FIJAS:
                responder(conn, "403 Forbidden", {"error": letra + " es fija, no se edita"})
            elif letra in leer_bloqueadas():
                responder(conn, "403 Forbidden",
                          {"error": letra + " esta bloqueada: destilda el candado para editarla"})
            else:
                guardar_codigo(letra, cuerpo.decode())
                print("Codigo guardado para la letra", letra)
                responder(conn, "200 OK", {"ok": True, "codigo": leer_codigo(letra)})
        elif ruta == "/titulo" and metodo == "POST":
            letra = params.get("l", "").upper()
            if len(letra) != 1 or not "A" <= letra <= "Z" or letra in FIJAS:
                responder(conn, "400 Bad Request", {"error": "letra invalida"})
            elif letra in leer_bloqueadas():
                responder(conn, "403 Forbidden",
                          {"error": letra + " esta bloqueada: destilda el candado para editarla"})
            else:
                responder(conn, "200 OK", {"ok": True, "titulo": guardar_titulo(letra, params.get("t", ""))})
        elif ruta == "/bloquear" and metodo == "POST":
            letra = params.get("l", "").upper()
            if len(letra) != 1 or not "A" <= letra <= "Z" or letra in FIJAS:
                responder(conn, "400 Bad Request", {"error": "letra invalida"})
            else:
                poner_bloqueo(letra, params.get("si") == "1")
                responder(conn, "200 OK", {"ok": True, "bloqueada": letra in leer_bloqueadas()})
        elif ruta == "/probar" and metodo == "POST":
            print("Probando codigo desde la web")
            error = correr_codigo(cuerpo.decode(), "prueba")
            dibujar()
            responder(conn, "200 OK", {"ok": not error, "error": error})
        elif ruta == "/reset" and metodo == "POST":
            responder(conn, "200 OK", {"ok": True})
            despues = "RESET"
        else:
            responder(conn, "404 Not Found", {"error": "ruta desconocida"})
    except Exception as e:
        print("Error HTTP:", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if despues == "RESET":
        show_lines("Reiniciando...")
        time.sleep_ms(300)
        machine.reset()
    elif despues:
        ejecutar_comando(despues)
        dibujar()


# ---------------------------------------------------------------- dormir / despertar

def esperar_que_suelte():
    while algun_boton_apretado():
        time.sleep_ms(10)
    time.sleep_ms(30)


def wake_up():
    global state, last_activity, soltado_en, texto, palabra, morse_actual, escritura_libre
    prender_pantalla()
    show_lines("Bienvenido!", "Que necesita?")
    esperar_que_suelte()  # el toque que despierta no cuenta como morse
    time.sleep_ms(1500)
    texto = palabra = morse_actual = ""
    escritura_libre = False
    state = STATE_AWAKE
    soltado_en = last_activity = time.ticks_ms()
    print("Despierto, esperando morse")
    dibujar()


def go_to_sleep():
    global state, pantalla_on
    callar()
    if led:
        led.value(0)
    wifi_off()
    ble.active(False)
    oled.fill(0)
    oled.show()
    oled.poweroff()
    pantalla_on = False
    state = STATE_SLEEP
    print("Dormido")


def main():
    global pantalla_on
    oled.poweroff()  # arrancamos dormidos, la pantalla apagada
    pantalla_on = False
    while True:
        if state == STATE_SLEEP:
            if algun_boton_apretado():
                time.sleep_ms(30)  # anti rebote
                if algun_boton_apretado():
                    wake_up()
        else:
            leer_boton()
            if state == STATE_AWAKE:
                leer_boton_inicio()
                revisar_pausas()
                check_incoming_frame()
                check_http()
                quieto = time.ticks_diff(time.ticks_ms(), last_activity)
                if quieto > cfg.IDLE_TIMEOUT_MS:
                    go_to_sleep()
                elif pantalla_on and quieto > SCREEN_TIMEOUT_MS:
                    apagar_pantalla()
        time.sleep_ms(10)


def modo_edicion_pedido():
    """Al arrancar damos unos segundos para tocar el boton y entrar en modo edicion."""
    prender_pantalla()
    show_lines("BOOT = editar", "(2 segundos)")
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < T_VENTANA_EDICION:
        if button.value() == 0:
            return True
        time.sleep_ms(20)
    return False


time.sleep_ms(100)  # da tiempo a que el pin del boton se estabilice al arrancar
if modo_edicion_pedido():
    # deja el puerto libre para subir archivos desde Thonny sin "Device is busy"
    show_lines("Modo edicion", "no autorun")
    print("Modo edicion: main() no se ejecuta. Reset normal para correrlo.")
else:
    main()
