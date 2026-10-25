# probador.py - Se fija si la PC ve el ESP32 por el cable USB (corre en la PC)
#
# Boton "Probar": revisa cada medio segundo si el ESP32 aparece en el USB.
# Boton "Stop": deja de revisar.
# Anota cada vez que se conecta o se desconecta, asi vemos si "entra y sale"
# (cable flojo, cable malo o puerto USB con problemas).
#
# No le manda nada a la placa: solo mira si el puerto existe, asi que puede
# estar abierto al mismo tiempo que Thonny.
#
# Uso:
#   pip install pyserial
#   python probador.py

import time
import tkinter as tk

import serial.tools.list_ports

CADA_MS = 500   # cada cuanto revisa
# palabras que aparecen en el nombre del puerto USB de las placas ESP32
CHIPS_USB = ("cp210", "ch340", "ch910", "silicon labs", "usb-serial", "usb serial", "uart")


def buscar_esp32():
    """Devuelve (puerto, descripcion) si la PC ve un ESP32, o None."""
    for p in serial.tools.list_ports.comports():
        desc = f"{p.description} {p.manufacturer or ''}"
        if any(k in desc.lower() for k in CHIPS_USB):
            return p.device, p.description
    return None


class Probador:
    def __init__(self, root):
        self.root = root
        self.probando = False
        self.antes = None        # ultimo estado visto: None (sin saber), True o False
        self.cortes = 0

        root.title("Probador USB ESP32")
        root.configure(bg="white", padx=20, pady=16)
        root.minsize(380, 330)

        self.estado = tk.Label(root, text="Apretá Probar", font=("Segoe UI", 20, "bold"),
                               bg="white", fg="#777")
        self.estado.pack(pady=(0, 2))
        self.detalle = tk.Label(root, text=" ", font=("Segoe UI", 11), bg="white", fg="#555")
        self.detalle.pack()

        botones = tk.Frame(root, bg="white")
        botones.pack(pady=12)
        self.btn_probar = tk.Button(botones, text="▶  Probar", font=("Segoe UI", 12, "bold"),
                                    width=10, bg="#22b35e", fg="white", command=self.probar)
        self.btn_probar.pack(side="left", padx=6)
        self.btn_stop = tk.Button(botones, text="■  Stop", font=("Segoe UI", 12, "bold"),
                                  width=10, state="disabled", command=self.stop)
        self.btn_stop.pack(side="left", padx=6)

        self.contador = tk.Label(root, text="Desconexiones: 0", font=("Segoe UI", 11, "bold"),
                                 bg="white")
        self.contador.pack(anchor="w")
        self.registro = tk.Listbox(root, height=8, font=("Consolas", 10), bg="#f6f8f6",
                                   relief="flat", highlightthickness=0)
        self.registro.pack(fill="both", expand=True, pady=(4, 0))

    def anotar(self, texto):
        self.registro.insert(0, time.strftime("%H:%M:%S  ") + texto)

    def probar(self):
        self.probando = True
        self.antes = None
        self.cortes = 0
        self.contador.config(text="Desconexiones: 0")
        self.registro.delete(0, "end")
        self.btn_probar.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.anotar("Empezamos a probar")
        self.revisar()

    def stop(self):
        self.probando = False
        self.btn_probar.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.estado.config(text="Detenido", fg="#777")
        self.anotar("Detenido")

    def revisar(self):
        if not self.probando:
            return
        encontrado = buscar_esp32()
        conectado = encontrado is not None

        if conectado:
            puerto, desc = encontrado
            self.estado.config(text="✔ Conectado", fg="#1a8a4a")
            self.detalle.config(text=f"{puerto}  ·  {desc}")
        else:
            self.estado.config(text="✘ No conectado", fg="#c0392b")
            self.detalle.config(text="La PC no ve el ESP32: revisemos el cable USB")

        if conectado != self.antes:
            if conectado:
                self.anotar(f"Conectado en {encontrado[0]}")
            else:
                if self.antes:  # estaba conectado y se fue
                    self.cortes += 1
                    self.contador.config(text=f"Desconexiones: {self.cortes}",
                                         fg="#c0392b" if self.cortes else "black")
                self.anotar("No se ve el ESP32")
            self.antes = conectado

        self.root.after(CADA_MS, self.revisar)


if __name__ == "__main__":
    root = tk.Tk()
    Probador(root)
    root.mainloop()
