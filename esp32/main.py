# main.py - ESP32 + OLED SSD1306 (128x32) + boton (cfg.BUTTON_PIN), manejado en morse
#
# Primer toque: despierta y saluda ("Bienvenido / Que necesita?").
# Despues el boton es una llave de morse:
#   toque corto = punto, toque largo = raya
#   pausa corta = cierra la letra, pausa larga = cierra la palabra
#   mantener apretado 2 s = dormir
# Una palabra de UNA sola letra que este en COMANDOS ejecuta ese comando
# (B = Bluetooth, W = WiFi, X = imagen). Cualquier otra cosa queda como texto.
#
# Con el WiFi prendido escucha frames de la PC por TCP (cfg.ESP_FRAME_PORT):
#   "clave:FRAME\n" + 512 bytes  -> dibuja el frame (MONO_VLSB)
#   "clave:RESET\n"              -> reinicia la placa
#   "clave\n" + 512 bytes        -> igual que FRAME (formato viejo)
#   conexion vacia               -> ping de /status, se ignora en silencio
#
# Y tambien un mini servidor HTTP (cfg.HTTP_PORT, 80 por defecto) para
# pc/index.html. Todas las rutas menos /estado piden ?clave=SHARED_SECRET:
#   GET  /estado                 -> JSON con wifi, bluetooth y texto
#   POST /frame?clave=...        -> cuerpo de 512 bytes, se dibuja
#   POST /comando?clave=...&letra=B  -> ejecuta un comando de COMANDOS
#   POST /reset?clave=...        -> reinicia la placa

import network
import usocket as socket
import time
import json
import machine
import framebuf
import bluetooth
from machine import Pin, I2C
import ssd1306
import config as cfg
import imagenes

WIDTH = 128
HEIGHT = 32
FRAME_BYTES = WIDTH * HEIGHT // 8  # 512
HTTP_PORT = getattr(cfg, "HTTP_PORT", 80)

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)
button = Pin(cfg.BUTTON_PIN, Pin.IN, Pin.PULL_UP)
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

texto = ""
palabra = ""
morse_actual = ""
presionado_desde = None
soltado_en = time.ticks_ms()


# ---------------------------------------------------------------- pantalla

def show_lines(*lines):
    oled.fill(0)
    y = 0
    for line in lines:
        oled.text(line, 0, y)
        y += 12
    oled.show()


def draw_large_text(text, x, y):
    """Texto al doble de tamano (16 px de alto)."""
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


def dibujar():
    oled.fill(0)
    draw_large_text(texto[-8:], 0, 0)
    oled.text(morse_actual, 0, 22)
    # indicadores abajo a la derecha
    if wlan.isconnected():
        oled.text("W", 104, 22)
    if ble.active():
        oled.text("B", 120, 22)
    oled.show()


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
    try:
        wlan.disconnect()
    except Exception:
        pass
    wlan.active(False)


def abrir_servidor(puerto):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', puerto))
    s.listen(2)
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


def cmd_imagen():
    oled.buffer[:] = imagenes.IMAGEN_X
    oled.show()
    time.sleep_ms(3000)


COMANDOS = {
    'B': cmd_bluetooth,
    'W': cmd_wifi,
    'X': cmd_imagen,
}


# ---------------------------------------------------------------- morse

def cerrar_letra():
    global morse_actual, texto, palabra
    letra = MORSE.get(morse_actual, "?")
    morse_actual = ""
    texto = (texto + letra)[-40:]
    palabra += letra
    dibujar()


def ejecutar_comando(letra):
    global soltado_en, last_activity
    print("Comando:", letra)
    COMANDOS[letra]()
    soltado_en = time.ticks_ms()
    last_activity = soltado_en


def cerrar_palabra():
    global texto, palabra
    p = palabra
    palabra = ""
    if len(p) == 1 and p in COMANDOS:
        texto = texto[:-1]  # el comando no queda escrito
        ejecutar_comando(p)
    else:
        texto += " "
    dibujar()


def leer_boton():
    global presionado_desde, soltado_en, morse_actual, last_activity
    now = time.ticks_ms()
    if button.value() == 0:
        if presionado_desde is None:
            presionado_desde = now
            last_activity = now
        elif time.ticks_diff(now, presionado_desde) > T_DORMIR:
            presionado_desde = None
            go_to_sleep()
            esperar_que_suelte()
        return

    if presionado_desde is None:
        return
    dur = time.ticks_diff(now, presionado_desde)
    presionado_desde = None
    if dur < T_REBOTE:
        return
    morse_actual += "." if dur < T_PUNTO_MAX else "-"
    soltado_en = now
    last_activity = now
    dibujar()


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
                oled.buffer[:] = data
                oled.show()
                last_activity = time.ticks_ms()
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
            largo = min(int(v.strip()), 4096)
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
    global last_activity
    if http_socket is None:
        return
    try:
        conn, addr = http_socket.accept()
    except OSError:
        return
    conn.settimeout(3)
    despues = None  # lo que se ejecuta una vez cerrada la conexion
    try:
        metodo, ruta, params, cuerpo = leer_peticion(conn)
        if metodo == "OPTIONS":
            responder(conn, "204 No Content")
        elif ruta == "/estado":
            responder(conn, "200 OK", {
                "wifi": wlan.isconnected(),
                "bluetooth": ble.active(),
                "texto": texto,
                "comandos": sorted(COMANDOS.keys()),
            })
        elif params.get("clave") != cfg.SHARED_SECRET:
            print("HTTP: clave incorrecta desde", addr[0])
            responder(conn, "403 Forbidden", {"error": "clave incorrecta"})
        elif ruta == "/frame" and metodo == "POST":
            if len(cuerpo) == FRAME_BYTES:
                oled.buffer[:] = cuerpo
                oled.show()
                last_activity = time.ticks_ms()
                responder(conn, "200 OK", {"ok": True})
            else:
                responder(conn, "400 Bad Request",
                          {"error": "el frame tiene que ser de 512 bytes"})
        elif ruta == "/comando" and metodo == "POST":
            letra = params.get("letra", "").upper()
            if letra in COMANDOS:
                responder(conn, "200 OK", {"ok": True, "letra": letra})
                despues = letra
            else:
                responder(conn, "404 Not Found", {"error": "comando desconocido"})
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
    while button.value() == 0:
        time.sleep_ms(10)
    time.sleep_ms(30)


def wake_up():
    global state, last_activity, soltado_en, texto, palabra, morse_actual
    oled.poweron()
    show_lines("Bienvenido!", "Que necesita?")
    esperar_que_suelte()  # el toque que despierta no cuenta como morse
    time.sleep_ms(1500)
    texto = palabra = morse_actual = ""
    state = STATE_AWAKE
    soltado_en = last_activity = time.ticks_ms()
    print("Despierto, esperando morse")
    dibujar()


def go_to_sleep():
    global state
    wifi_off()
    ble.active(False)
    oled.fill(0)
    oled.show()
    oled.poweroff()
    state = STATE_SLEEP
    print("Dormido")


def main():
    oled.poweroff()  # arrancamos dormidos, la pantalla apagada
    while True:
        if state == STATE_SLEEP:
            if button.value() == 0:
                time.sleep_ms(30)  # anti rebote
                if button.value() == 0:
                    wake_up()
        else:
            leer_boton()
            if state == STATE_AWAKE:
                revisar_pausas()
                check_incoming_frame()
                check_http()
                if time.ticks_diff(time.ticks_ms(), last_activity) > cfg.IDLE_TIMEOUT_MS:
                    go_to_sleep()
        time.sleep_ms(10)


def modo_edicion_pedido():
    """Al arrancar damos unos segundos para tocar BOOT y entrar en modo edicion."""
    oled.poweron()
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
