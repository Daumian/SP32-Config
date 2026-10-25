# D: Dado. Se pega en el panel web, en Letras -> D (titulo: Dado).
#   puntos rapidos (por ejemplo 7) -> numero al azar entre 1 y 7
#   una raya larga                 -> SI o NO
# Despues, cada toque vuelve a tirar igual. SW2 o 30 s sin tocar = salir.

mostrar("Dado", "puntos = 1 a N", "raya = si / no")
toques = esperar_toques(15000)

if not toques:
    mostrar("Dado", "No tocaste nada")
    esperar(1500)
else:
    si_no = "-" in toques
    maximo = len(toques)
    while True:
        if si_no:
            # sonido de "pensando"
            for i, f in enumerate((500, 650, 520, 700, 560, 800)):
                mostrar("Pensando" + "." * (i % 4))
                tono(f, 90)
                esperar(60)
            resultado = "SI" if azar(0, 1) else "NO"
        else:
            # barrita de "cargando"
            for i in range(1, 9):
                mostrar("Tirando 1 a " + str(maximo), "[" + "#" * i + " " * (8 - i) + "]")
                tono(300 + i * 60, 40)
                esperar(80)
            resultado = str(azar(1, maximo))
        mostrar_grande(resultado)
        tono(880, 120)
        if not esperar_toques(30000):  # otro toque = tirar de nuevo
            break
