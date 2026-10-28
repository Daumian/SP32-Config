# K: Funkytown. Riff disco con la pantalla destellando. Titulo: Funkytown.
# Cada nota es nota:tiempos ("-" = silencio). Si el ritmo no convence, se cambia aca.
HZ = {"sol": 392, "sib": 466, "do": 523, "re": 587, "mi": 659, "fa": 698}
RIFF = "do:1 do:1 sib:1 do:2 sol:2 sol:1 do:1 fa:1 mi:1 do:3 -:2 "
PARTE2 = "do:1 do:1 do:1 do:1 mi:2 -:1 mi:1 re:1 do:2 do:3 -:2 "
CANCION = RIFF + RIFF + PARTE2 + RIFF
TIEMPO = 120  # ms por tiempo: mas chico = mas rapido

try:
    n = 0
    for parte in CANCION.split():
        nota, t = parte.split(":")
        ms = int(t) * TIEMPO
        if nota == "-":
            esperar(ms)
            continue
        mostrar_grande("FUNKY" if (n // 8) % 2 == 0 else "TOWN", 3)
        oled.invert(n % 2)
        led(True)
        tono(HZ[nota], int(ms * 0.85))
        led(False)
        esperar(int(ms * 0.15))
        n += 1
finally:
    oled.invert(0)
    led(False)
mostrar("FUNKYTOWN!")
esperar(1500)
