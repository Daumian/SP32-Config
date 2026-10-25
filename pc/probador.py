# probador.py - Probador de conexiones por USB (corre en la PC)
#
# Habla con el ESP32 por el cable USB y muestra en vivo:
#   - si la placa esta conectada y respondiendo
#   - que pines tocan GND o estan unidos entre si (por ejemplo al apretar un
#     boton de la plaquita), y si el contacto "parpadea" (falso contacto)
#
# Uso:
#   1. Cerrar Thonny (si no, el puerto USB queda ocupado).
#   2. pip install pyserial
#   3. python probador.py
#
# No guarda nada en la placa: le manda un script que corre en memoria. Al
# cerrar la ventana se frena, y con un reset vuelve el main.py de siempre.

import queue
import threading
import time
import tkinter as tk

import serial
import serial.tools.list_ports

# Pines a probar, con nuestra numeracion (docs/pines.html) -> numero de GPIO
PINES = {"D5": 13, "D8": 14, "D9": 27, "D10": 26}

T_SIN_DATOS = 1.5     # segundos sin lineas = la placa no responde
VENTANA_FLOJO = 2.0   # si un contacto cambia mucho en este tiempo...
CAMBIOS_FLOJO = 4     # ...mas de esta cantidad de veces, es falso contacto

# Script que corre en el ESP32: cada 100 ms imprime una linea
# "E <pares unidos> | <pines que tocan GND>"
SCRIPT_ESP = """
from machine import Pin
import time
P = %r
for g in P.values():
    Pin(g, Pin.IN, Pin.PULL_UP)
while True:
    # primero los que tocan GND: esos leen 0 siempre y confundirian las uniones
    gnd = [n for n, g in P.items() if Pin(g, Pin.IN, Pin.PULL_UP).value() == 0]
    pares = set()
    for n, g in P.items():
        if n in gnd:
            continue
        Pin(g, Pin.OUT, value=0)
        for n2, g2 in P.items():
            if g2 != g and n2 not in gnd and Pin(g2, Pin.IN, Pin.PULL_UP).value() == 0:
                pares.add('-'.join(sorted((n, n2))))
        Pin(g, Pin.IN, Pin.PULL_UP)
    print('E', ','.join(sorted(pares)), '|', ','.join(gnd))
    time.sleep_ms(100)
""" % (PINES,)


def buscar_puerto():
    """Devuelve el puerto que parece un ESP32 (CP210x / CH340), o None."""
    candidatos = []
    for p in serial.tools.list_ports.comports():
        desc = f"{p.description} {p.manufacturer or ''}".lower()
        if any(k in desc for k in ("cp210", "ch340", "ch910", "usb-serial", "uart", "silicon labs")):
            candidatos.insert(0, p.device)
        elif "usb" in desc:
            candidatos.append(p.device)
    return candidatos[0] if candidatos else None


class Placa(threading.Thread):
    """Hilo que se conecta al ESP32, le manda el script y lee las lineas."""

    def __init__(self, cola):
        super().__init__(daemon=True)
        self.cola = cola
        self.ser = None
        self.vivo = True

    def avisar(self, tipo, dato=""):
        self.cola.put((tipo, dato))

    def run(self):
        while self.vivo:
            puerto = buscar_puerto()
            if not puerto:
                self.avisar("estado", "No encuentro la placa: revisemos el cable USB")
                time.sleep(1.5)
                continue
            try:
                self.conectar(puerto)
                self.leer()
            except serial.SerialException as e:
                msg = str(e).lower()
                if "access" in msg or "denied" in msg or "busy" in msg or "permission" in msg:
                    self.avisar("estado", f"{puerto} ocupado: cerremos Thonny")
                else:
                    self.avisar("estado", f"Se corto el USB ({puerto})")
            except Exception as e:  # noqa: BLE001 - mostramos cualquier problema en la ventana
                self.avisar("estado", f"Problema: {e}")
            self.cerrar()
            time.sleep(1.5)

    def conectar(self, puerto):
        self.avisar("estado", f"Conectando a {puerto}...")
        ser = serial.Serial()
        ser.port = puerto
        ser.baudrate = 115200
        ser.timeout = 0.2
        ser.dtr = False  # que abrir el puerto no reinicie la placa
        ser.rts = False
        ser.open()
        self.ser = ser
        # frenamos lo que este corriendo (main.py) hasta ver el >>>
        visto = b""
        t0 = time.time()
        while b">>>" not in visto:
            if time.time() - t0 > 6:
                raise serial.SerialException("la placa no contesta al Ctrl+C")
            ser.write(b"\r\x03\x03")
            time.sleep(0.3)
            visto = (visto + ser.read(ser.in_waiting or 1))[-200:]
        # modo "raw REPL" para mandar el script entero de una
        ser.write(b"\x01")
        time.sleep(0.2)
        ser.read(ser.in_waiting or 1)
        ser.write(SCRIPT_ESP.encode() + b"\x04")
        self.avisar("estado", f"Conectado a {puerto}")

    def leer(self):
        resto = b""
        while self.vivo:
            data = self.ser.read(256)
            if not data:
                continue
            resto += data
            *lineas, resto = resto.split(b"\n")
            for linea in lineas:
                txt = linea.decode(errors="replace").strip().lstrip("OK").strip()
                if txt.startswith("E "):
                    pares, _, gnd = txt[2:].partition("|")
                    self.avisar("datos", (
                        [p for p in pares.strip().split(",") if p],
                        [g for g in gnd.strip().split(",") if g],
                    ))
                elif "Error" in txt or "Traceback" in txt:
                    self.avisar("estado", "La placa tiro un error: " + txt)

    def cerrar(self):
        if self.ser:
            try:
                self.ser.write(b"\x03\x03\x02")  # frenamos el script y volvemos al REPL normal
                self.ser.close()
            except Exception:  # noqa: BLE001
                pass
        self.ser = None


class Ventana:
    def __init__(self, root):
        self.root = root
        root.title("Probador ESP32")
        root.configure(bg="white")
        root.minsize(420, 360)
        self.cola = queue.Queue()
        self.ultimo_dato = 0.0
        self.historial = {}   # clave -> lista de momentos en que cambio
        self.antes = set()
        self.vistos = set()

        fuente = ("Segoe UI", 12)
        self.estado = tk.Label(root, text="Buscando la placa...", font=("Segoe UI", 13, "bold"),
                               bg="white", anchor="w")
        self.estado.pack(fill="x", padx=16, pady=(14, 4))

        tk.Label(root, text="Pines (tocar con un cable a GND o apretar un boton):",
                 font=fuente, bg="white", fg="#555").pack(anchor="w", padx=16, pady=(8, 2))
        marco = tk.Frame(root, bg="white")
        marco.pack(fill="x", padx=16)
        self.filas = {}
        for nombre in PINES:
            f = tk.Frame(marco, bg="white")
            f.pack(fill="x", pady=3)
            c = tk.Canvas(f, width=22, height=22, bg="white", highlightthickness=0)
            c.pack(side="left")
            punto = c.create_oval(2, 2, 20, 20, fill="#d0d0d0", outline="")
            tk.Label(f, text=f"{nombre}  (GPIO {PINES[nombre]})", font=("Consolas", 12, "bold"),
                     bg="white", width=16, anchor="w").pack(side="left", padx=6)
            txt = tk.Label(f, text="suelto", font=fuente, bg="white", fg="#777", anchor="w")
            txt.pack(side="left")
            self.filas[nombre] = (c, punto, txt)

        tk.Label(root, text="Uniones ahora:", font=fuente, bg="white", fg="#555").pack(
            anchor="w", padx=16, pady=(12, 0))
        self.uniones = tk.Label(root, text="-", font=("Consolas", 16, "bold"), bg="white", fg="#1a8a4a",
                                anchor="w", justify="left")
        self.uniones.pack(fill="x", padx=16)
        tk.Label(root, text="Vistas alguna vez:", font=fuente, bg="white", fg="#555").pack(
            anchor="w", padx=16, pady=(8, 0))
        self.vistas = tk.Label(root, text="-", font=("Consolas", 12), bg="white", anchor="w", justify="left")
        self.vistas.pack(fill="x", padx=16)
        tk.Button(root, text="Borrar historial", command=self.borrar).pack(anchor="w", padx=16, pady=10)

        self.placa = Placa(self.cola)
        self.placa.start()
        root.protocol("WM_DELETE_WINDOW", self.salir)
        self.refrescar()

    def borrar(self):
        self.vistos.clear()
        self.historial.clear()
        self.vistas.config(text="-")

    def salir(self):
        self.placa.vivo = False
        self.placa.cerrar()
        self.root.destroy()

    def refrescar(self):
        while not self.cola.empty():
            tipo, dato = self.cola.get()
            if tipo == "estado":
                self.estado.config(text=dato, fg="#1a8a4a" if dato.startswith("Conectado") else "#b23a2b")
            elif tipo == "datos":
                self.ultimo_dato = time.time()
                self.mostrar(*dato)
        if self.ultimo_dato and time.time() - self.ultimo_dato > T_SIN_DATOS:
            self.estado.config(text="La placa no responde (revisemos el USB)", fg="#b23a2b")
        self.root.after(80, self.refrescar)

    def registrar_cambios(self, actuales):
        """Anota cuando aparece o desaparece cada union; devuelve las que parpadean."""
        ahora = time.time()
        for clave in self.antes ^ actuales:
            self.historial.setdefault(clave, []).append(ahora)
        for clave, cambios in list(self.historial.items()):
            cambios[:] = [t for t in cambios if ahora - t < VENTANA_FLOJO]
            if not cambios:
                del self.historial[clave]
        self.antes = actuales
        return {k for k, v in self.historial.items() if len(v) > CAMBIOS_FLOJO}

    def mostrar(self, pares, gnd):
        actuales = set(pares) | {"GND-" + g for g in gnd}
        flojos = self.registrar_cambios(actuales)
        for nombre, (c, punto, txt) in self.filas.items():
            unido = [p.replace(nombre, "").strip("-") for p in pares if nombre in p.split("-")]
            if nombre in gnd:
                color, texto = "#22b35e", "toca GND"
            elif unido:
                color, texto = "#22b35e", "unido con " + ", ".join(unido)
            else:
                color, texto = "#d0d0d0", "suelto"
            if any(nombre in k.split("-") for k in flojos):
                color, texto = "#f2c21b", texto + "  ⚠ parpadea: falso contacto?"
            c.itemconfig(punto, fill=color)
            txt.config(text=texto, fg="#222" if color != "#d0d0d0" else "#777")
        self.vistos |= set(pares)
        self.uniones.config(text="  ".join(p.replace("-", " ↔ ") for p in pares) or "-")
        self.vistas.config(text="  ".join(p.replace("-", " ↔ ") for p in sorted(self.vistos)) or "-")

if __name__ == "__main__":
    root = tk.Tk()
    Ventana(root)
    root.mainloop()
