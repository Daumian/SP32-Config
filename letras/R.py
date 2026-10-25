# R: Rocky. Un corredorcito sube la escalera mientras suena el tema.
# Notas de "Gonna Fly Now" (tablaturas de guitarra y armonica). nota:tiempos
o = oled
PASOS = [
    ["..#..", ".##..", "#.##.", "..#..", ".#.#.", "#...#"],
    ["..#..", "..##.", ".##.#", "..#..", "..##.", "..#.#"],
]
BRAZOS_ARRIBA = ["#.#.#", ".###.", "..#..", "..#..", ".#.#.", ".#.#."]
HZ = {"si3": 247, "do": 262, "re": 294, "mi": 330, "sol": 392, "do5": 523, "mi5": 659}
TEMA = (
    "do:4 do:4 do:3 do:3 do:4 do:3 do:3 mi:2 do:3 do:3 do:7 "
    "mi:2 mi:3 mi:2 mi:2 mi:3 mi:2 mi:2 sol:2 mi:2 mi:2 mi:4 "
    "re:3 re:2 re:2 re:3 re:2 mi:2 mi:2 re:3 do:3 si3:4 "
    "mi:2 do5:2 mi5:6 mi:2 mi5:2 do5:6 mi:2 do5:2 mi5:6 mi:2 mi5:2 do5:8"
)
TIEMPO = 80  # ms por tiempo: mas chico = mas rapido
NOTAS = [(HZ[n], int(t) * TIEMPO) for n, t in (p.split(":") for p in TEMA.split())]


def muneco(dibujo, x, y):
    for fy, fila in enumerate(dibujo):
        for fx, c in enumerate(fila):
            if c == "#":
                o.pixel(x + fx, y + fy, 1)


def escena(dibujo, x, y):
    o.fill(0)
    o.hline(0, 31, 96, 1)
    for i in range(6):  # escalera
        o.fill_rect(96 + i * 5, 28 - i * 4, 5, 4 + i * 4, 1)
    muneco(dibujo, x, y)
    o.show()


x, cuadro = 0, 0
for f, ms in NOTAS:
    sonar(f)
    for _ in range(max(1, ms // 60)):
        centro = min(x, 122) + 2
        y = 22 - min(5, (centro - 96) // 5) * 4 if centro >= 96 else 25  # pisa el escalon
        escena(PASOS[cuadro % 2], min(x, 122), y)
        cuadro += 1
        x += 1 if x < 122 else 0
        esperar(60)
    callar()
    esperar(30)
escena(BRAZOS_ARRIBA, 122, 2)
o.text("ROCKY", 4, 4)
o.show()
esperar(2500)
