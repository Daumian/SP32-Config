# P: Marcha + el General
import framebuf, binascii
o = oled
M = (
    "do#2:1 la:1 mi:1 do#2:1 la:1 mi:1 do#2:1 la:2 -:1 "
    "do#2:1 la:1 mi:1 do#2:1 do#2:1 si:1 la:1 si:1 sol#:2 -:1 "
    "si:1 sol#:1 mi:1 si:1 sol#:1 mi:1 si:1 sol#:2 -:1 "
    "re2:1 re2:1 re2:1 re2:1 do#2:1 si:1 do#2:2 -:1 "
    "re2:1 do#2:1 si:1 do#2:2 -:1 re2:1 do#2:1 si:1 do#2:2 -:1 "
    "re2:1 do#2:1 si:1 do#2:3"
)
TEMPO = 200
BASE = {"do#": 277, "re": 294, "mi": 330, "sol#": 415, "la": 440, "si": 494}
FIG = framebuf.FrameBuffer(bytearray(binascii.a2b_base64(
    "KAAAAGoAAAB+AAAAfAAAADwAAAA4AAAAMAAAADAH8AAwD/gAMB/8ADAYDAAwEAQAMBY0ADAQBAA4EIQAOBAEADwX9AAcCcgAHgQQAA8D4AAHgIAAA+OAAAH/wAAD//AAB//8AA///gAf//8AH///gD///4A////AP///wD///8A=")), 26, 32, framebuf.MONO_HLSB)


def grande(t, x, y):
    n = len(t) * 8
    b = framebuf.FrameBuffer(bytearray(n), n, 8, framebuf.MONO_VLSB)
    b.text(t, 0, 0)
    for i in range(n):
        for j in range(8):
            if b.pixel(i, j):
                o.fill_rect(x + 2 * i, y + 2 * j, 2, 2, 1)


def pan(f):
    o.fill(0)
    if f == 0:
        grande("PERON", 24, 8)
    elif f == 1:
        o.blit(FIG, 0, 0)
        grande("PERON", 34, 8)
    elif f == 2:
        grande("GOOGLEA", 8, 8)
    else:
        o.blit(FIG, 0, 0)
        grande("PERON", 34, 0)
        o.text("14 ANOS", 40, 22)
        for dx, dy in ((1, 20), (2, 19), (3, 20), (4, 20), (5, 19)):
            o.pixel(72 + dx, dy, 1)
    o.show()


notas = M.split()
antes = -1
try:
    for i, parte in enumerate(notas):
        fase = (0, 0, 0, 1, 1, 1, 2, 2, 3, 3)[i * 10 // len(notas)]
        if fase != antes:
            pan(fase)
            antes = fase
        o.invert(i % 2 if fase == 0 else 0)
        nota, t = parte.split(":")
        ms = int(t) * TEMPO
        if nota == "-":
            esperar(ms)
        else:
            tono(BASE[nota.rstrip("2")] * (2 if nota[-1] == "2" else 1), int(ms * 0.9))
            esperar(int(ms * 0.1))
finally:
    o.invert(0)
esperar(1500)
