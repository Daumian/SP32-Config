# R: Rocky. Un corredorcito sube la escalera mientras suena el tema.
# Notas aproximadas de "Gonna Fly Now": si alguna no suena bien, se cambia aca.
o = oled
PASOS = [
    ["..#..", ".##..", "#.##.", "..#..", ".#.#.", "#...#"],
    ["..#..", "..##.", ".##.#", "..#..", "..##.", "..#.#"],
]
BRAZOS_ARRIBA = ["#.#.#", ".###.", "..#..", "..#..", ".#.#.", ".#.#."]
MI, SOL, LA, SI, MI2, RE2 = 330, 392, 440, 494, 659, 587
NOTAS = [(MI, 150), (SOL, 150), (LA, 600), (LA, 150), (SI, 150), (MI, 600),
         (MI, 150), (SOL, 150), (LA, 600), (LA, 150), (SI, 150), (MI2, 900),
         (RE2, 300), (SI, 300), (LA, 300), (SOL, 300), (LA, 1200)]


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
        x += 2 if x < 122 else 0
        esperar(60)
    callar()
    esperar(30)
escena(BRAZOS_ARRIBA, 122, 2)
o.text("ROCKY", 4, 4)
o.show()
esperar(2500)
