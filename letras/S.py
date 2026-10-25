# S: Star Wars. Un caza TIE cruza las estrellas hacia la Estrella de la
# Muerte con la Marcha Imperial; al final, el rayo. Titulo: Star Wars.
o = oled
TIE = ["#.....#", "#.###.#", "###.###", "#.###.#", "#.....#"]
ESTRELLAS = [((i * 37) % 128, (i * 17) % 30) for i in range(16)]
LA, FA, DO2, MI2, FA2, SOLs = 440, 349, 523, 659, 698, 415
NOTAS = [(LA, 500), (LA, 500), (LA, 500), (FA, 350), (DO2, 150),
         (LA, 500), (FA, 350), (DO2, 150), (LA, 900),
         (MI2, 500), (MI2, 500), (MI2, 500), (FA2, 350), (DO2, 150),
         (SOLs, 500), (FA, 350), (DO2, 150), (LA, 900)]


def escena(x, cuadro, rayo=False):
    o.fill(0)
    for i, (ex, ey) in enumerate(ESTRELLAS):
        if (i + cuadro // 3) % 5:  # algunas titilan
            o.pixel(ex, ey, 1)
    o.ellipse(110, 15, 11, 11, 0, True)  # tapa las estrellas de atras
    o.ellipse(110, 15, 11, 11, 1)
    o.hline(99, 16, 23, 1)
    o.ellipse(106, 10, 3, 3, 1)
    if rayo:
        o.line(103, 9, 0, 1, 1)
    for fy, fila in enumerate(TIE):
        for fx, c in enumerate(fila):
            if c == "#":
                o.pixel(x + fx, 13 + fy, 1)
    o.show()


cuadro = 0
for f, ms in NOTAS:
    sonar(f)
    for _ in range(max(1, ms // 60)):
        escena(min(cuadro * 2 // 3 - 7, 80), cuadro)
        cuadro += 1
        esperar(60)
    callar()
    esperar(30)
for _ in range(3):  # el rayo
    escena(80, cuadro, True)
    tono(150, 120)
    escena(80, cuadro)
    esperar(80)
o.text("STAR WARS", 2, 0)
o.show()
esperar(2500)
