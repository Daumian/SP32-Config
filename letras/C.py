# C: Cruzada. Castillo y pueblo, Dies Irae y los textos.
o = oled


def torre(x, y, w):
    o.fill_rect(x, y, w, 32 - y, 1)
    for i in range(w):
        o.hline(x + i // 2, y - 1 - i, w - (i // 2) * 2, 1)


def centro(t, y):
    o.text(t, (128 - 8 * len(t)) // 2, y)


def canto(notas, ms=380):
    for n in notas:
        tono(n, ms)
        esperar(40)


F, E, D, C, A = 349, 330, 294, 262, 220
try:
    o.fill(0)
    for x in range(56):
        o.vline(x, 24 + abs(x - 24) // 4, 8, 1)
    o.fill_rect(8, 20, 32, 12, 1)
    torre(10, 14, 6)
    torre(18, 8, 8)
    torre(30, 12, 6)
    for x in range(58, 128, 7):
        o.fill_rect(x, 25 + x % 3, 5, 7, 1)
    torre(78, 16, 4)
    torre(104, 18, 4)
    o.hline(40, 4, 14, 1)
    o.hline(44, 3, 6, 1)
    o.hline(88, 7, 18, 1)
    o.hline(93, 6, 8, 1)
    o.invert(1)
    o.show()
    canto([F, E, F, D, E, C, D, D])
    o.invert(0)
    for t in ("Es tiempo", "de una nueva"):
        o.fill(0)
        centro(t, 12)
        o.show()
        canto([F, F, E, D] if t[0] == "E" else [E, F, E, D])
    mostrar_grande("CRUZADA", 2)
    for x in (0, 123):
        o.vline(x + 2, 9, 14, 1)
        o.hline(x, 13, 5, 1)
    o.show()
    for _ in range(3):
        tono(D, 500)
        tono(A, 700)
        esperar(200)
    esperar(1500)
finally:
    o.invert(0)
