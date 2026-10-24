# main.py - ESP32 + OLED SSD1306 (128x32) + boton BOOT
#
# Firmware minimo: el boton solo prende/apaga el ESP32 (wifi + pantalla).
# Todo lo demas -- imagenes, gifs, o mensajes de texto -- se maneja desde
# la PC, que le manda frames ya listos por un socket TCP.
#
# Protocolo (puerto cfg.ESP_FRAME_PORT), una linea de cabecera con "\n":
#   "clave:FRAME\n" + 512 bytes  -> dibuja el frame (MONO_VLSB)
#   "clave:RESET\n"              -> reinicia la placa
#   "clave\n" + 512 bytes        -> igual que FRAME (formato viejo)
#   conexion vacia               -> ping de /status, se ignora en silencio

import network
import usocket as socket
import time
import machine
from machine import Pin, I2C
import ssd1306
import config as cfg

WIDTH = 128
HEIGHT = 32
FRAME_BYTES = WIDTH * HEIGHT // 8  # 512

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)
button = Pin(cfg.BUTTON_PIN, Pin.IN, Pin.PULL_UP)
wlan = network.WLAN(network.STA_IF)

STATE_SLEEP = 0
STATE_AWAKE = 1
state = STATE_SLEEP

last_activity = time.ticks_ms()
press_start = None
srv_socket = None


def wifi_on():
    wlan.active(True)
    wlan.connect(cfg.WIFI_SSID, cfg.WIFI_PASS)
    t0 = time.ticks_ms()
    while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 10000:
        time.sleep_ms(200)
    return wlan.isconnected()


def wifi_off():
    global srv_socket
    if srv_socket:
        try:
            srv_socket.close()
        except Exception:
            pass
        srv_socket = None
    try:
        wlan.disconnect()
    except Exception:
        pass
    wlan.active(False)


def start_frame_server():
    global srv_socket
    srv_socket = socket.socket()
    srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv_socket.bind(('0.0.0.0', cfg.ESP_FRAME_PORT))
    srv_socket.listen(1)
    srv_socket.settimeout(0)  # no bloqueante


def show_lines(*lines):
    oled.fill(0)
    y = 0
    for line in lines:
        oled.text(line, 0, y)
        y += 12
    oled.show()


def wake_up():
    global state, last_activity
    oled.poweron()
    show_lines("Conectando...")
    if wifi_on():
        start_frame_server()
        state = STATE_AWAKE
        ip = wlan.ifconfig()[0]
        show_lines("Listo", ip)
        print("Despierto. IP:", ip)
    else:
        show_lines("Sin WiFi")
        print("No se pudo conectar a", cfg.WIFI_SSID)
        time.sleep(2)
        go_to_sleep()
        return
    last_activity = time.ticks_ms()


def go_to_sleep():
    global state
    wifi_off()
    oled.fill(0)
    oled.show()
    oled.poweroff()
    state = STATE_SLEEP
    print("Dormido")


def check_button():
    global press_start
    pressed = button.value() == 0
    now = time.ticks_ms()

    if state == STATE_SLEEP:
        if pressed:
            time.sleep_ms(30)  # anti rebote
            if button.value() == 0:
                wake_up()
                while button.value() == 0:
                    time.sleep_ms(10)
        return

    # STATE_AWAKE: un toque completo (apretar y soltar) apaga todo
    if pressed:
        if press_start is None:
            press_start = now
    else:
        if press_start is not None:
            press_start = None
            go_to_sleep()


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


def main():
    oled.poweroff()  # arrancamos dormidos, la pantalla apagada
    while True:
        check_button()
        if state == STATE_AWAKE:
            check_incoming_frame()
            if time.ticks_diff(time.ticks_ms(), last_activity) > cfg.IDLE_TIMEOUT_MS:
                go_to_sleep()
        time.sleep_ms(10)


time.sleep_ms(300)  # da tiempo a que el pin del boton se estabilice al arrancar
if button.value() == 0:
    # BOOT esta apretado justo al arrancar -> modo edicion, no ejecuta nada
    # (esto deja el puerto libre para subir archivos desde Thonny sin errores)
    oled.poweron()
    show_lines("Modo edicion", "no autorun")
    print("BOOT apretado al iniciar: main() no se ejecuta. Reset normal para correrlo.")
else:
    main()
