# J: Juego del dinosaurio (como el de Chrome). Titulo: Dino.
#   tocar la llave = saltar   |   SW2 = salir
# Los cactus vienen cada vez mas rapido. El record queda guardado en la placa.
# Al perder suena la musica de cuando muere Mario (Super Mario Bros, NES).

import framebuf

SUELO = 30            # fila del piso
FRAME_MS = 30         # ~33 cuadros por segundo
SALTO = 3.9           # fuerza del salto (mas = salta mas alto)
GRAVEDAD = 0.45
ARCHIVO_RECORD = "letras/record.txt"

# musica de perder de Mario: (frecuencia, duracion en ms); 0 = silencio
MUSICA_PERDER = [
    (523, 70), (554, 70), (587, 70), (0, 350),          # tu-tu-tu
    (494, 210), (698, 210), (0, 210), (698, 210),       # ta ... taaa
    (698, 280), (659, 280), (587, 280),                 # ta-ta-ta
    (523, 210), (330, 210), (0, 210), (330, 210), (262, 420),  # ...bum bum
]


def sprite(filas):
    """Dibujo hecho con # y . -> FrameBuffer listo para blit."""
    alto, ancho = len(filas), len(filas[0])
    fb = framebuf.FrameBuffer(bytearray(ancho * ((alto + 7) // 8)), ancho, alto, framebuf.MONO_VLSB)
    for y, fila in enumerate(filas):
        for x, c in enumerate(fila):
            if c == "#":
                fb.pixel(x, y, 1)
    return fb, ancho, alto


CUERPO = [
    "......######",
    ".....##.####",
    ".....#######",
    ".....####...",
    "#....######.",
    "#...####....",
    "##.######...",
    "#########...",
    ".#######....",
    "..#####.....",
]
DINO = [
    sprite(CUERPO + ["..##.##.....", "..#...##...."]),   # paso 1
    sprite(CUERPO + ["...##.#.....", "...#..##...."]),   # paso 2
]
CACTUS = [
    sprite(["..#..", "..#.#", "#.#.#", "#.###", "###..", "..#..",
            "..#..", "..#..", "..#..", "..#.."]),
    sprite(["...#...", "...#...", ".#.#...", ".#.#.#.", ".#.#.#.", ".###.#.",
            "...###.", "...#...", "...#...", "...#...", "...#...", "...#..."]),
    sprite(["..#....#..", "..#.#..#.#", "#.#.##.#.#", "#.###..###", "###...##..",
            "..#....#..", "..#....#..", "..#....#..", "..#....#..", "..#....#.."]),
]
NUBE = sprite(["...###...", ".##...##.", "#.......#", ".#######."])


def leer_record():
    try:
        with open(ARCHIVO_RECORD) as f:
            return int(f.read())
    except (OSError, ValueError):
        return 0


def guardar_record(n):
    try:
        with open(ARCHIVO_RECORD, "w") as f:
            f.write(str(n))
    except OSError:
        pass


def esperar_toque(max_ms):
    """True si tocamos la llave antes de max_ms; espera a que la soltemos."""
    for _ in range(max_ms // 20):
        if llave():
            while llave():
                esperar(10)
            return True
        esperar(20)
    return False


def partida():
    altura, vel_y = 0.0, 0.0
    obstaculos = []           # [x, tipo]
    velocidad = 2.0
    puntos = cuadro = 0
    proximo = 40
    nube_x = 100.0
    antes = llave()
    while True:
        t0 = time.ticks_ms()

        # salto: solo cuando recien tocamos y estamos en el piso
        ahora = llave()
        if ahora and not antes and altura == 0:
            vel_y = SALTO
        antes = ahora
        if altura > 0 or vel_y > 0:
            altura += vel_y
            vel_y -= GRAVEDAD
            if altura <= 0:
                altura, vel_y = 0.0, 0.0

        # cactus nuevos y movimiento
        proximo -= 1
        if proximo <= 0:
            obstaculos.append([128.0, azar(0, 2)])
            proximo = azar(28, 60)
        for o in obstaculos:
            o[0] -= velocidad
        obstaculos = [o for o in obstaculos if o[0] > -12]
        nube_x -= velocidad / 4
        if nube_x < -10:
            nube_x = 130.0

        # choque (con un pixel de margen para que sea justo)
        abajo = SUELO - 1 - int(altura)
        for o in obstaculos:
            _, ancho, alto = CACTUS[o[1]]
            x = int(o[0])
            if 4 + 10 > x + 1 and 4 + 2 < x + ancho - 1 and abajo >= SUELO - alto + 1:
                return puntos

        # dibujo
        oled.fill(0)
        oled.hline(0, SUELO, 128, 1)
        for i in range(0, 128, 11):
            oled.pixel((i - cuadro * int(velocidad)) % 128, SUELO + 1, 1)
        oled.blit(NUBE[0], int(nube_x), 5, 0)
        paso = 0 if altura > 0 else (cuadro // 4) % 2
        oled.blit(DINO[paso][0], 4, abajo - 11, 0)
        for o in obstaculos:
            fb, ancho, alto = CACTUS[o[1]]
            oled.blit(fb, int(o[0]), SUELO - alto, 0)
        marcador = str(puntos)
        oled.text(marcador, 128 - 8 * len(marcador), 0)
        oled.show()

        # puntaje y velocidad
        cuadro += 1
        if cuadro % 3 == 0:
            puntos += 1
            velocidad = min(5.0, 2.0 + puntos / 120)
        esperar(max(1, FRAME_MS - time.ticks_diff(time.ticks_ms(), t0)))


mostrar("DINO", "Toca = saltar", "SW2 = salir")
if esperar_toque(15000):
    while True:
        puntos = partida()
        record = leer_record()
        if puntos > record:
            guardar_record(puntos)
            mostrar("GAME OVER", "Puntos: " + str(puntos), "NUEVO RECORD!")
        else:
            mostrar("GAME OVER", "Puntos: " + str(puntos), "Record: " + str(record))
        for frecuencia, ms in MUSICA_PERDER:
            if frecuencia:
                tono(frecuencia, int(ms * 0.9))
                esperar(int(ms * 0.1))
            else:
                esperar(ms)
        esperar(800)  # para no reiniciar sin querer
        if not esperar_toque(20000):
            break
