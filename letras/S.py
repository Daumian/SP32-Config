# S: Star Wars, la Marcha Imperial. Titulo: Star Wars.
LA, FA, DO2, MI2, FA2, SOLs = 440, 349, 523, 659, 698, 415
FRASES = [
    ("STAR", [(LA, 500), (LA, 500), (LA, 500), (FA, 350), (DO2, 150),
              (LA, 500), (FA, 350), (DO2, 150), (LA, 900)]),
    ("WARS", [(MI2, 500), (MI2, 500), (MI2, 500), (FA2, 350), (DO2, 150),
              (SOLs, 500), (FA, 350), (DO2, 150), (LA, 900)]),
]
for texto, notas in FRASES:
    mostrar_grande(texto, 3)
    for f, ms in notas:
        tono(f, int(ms * 0.9))
        esperar(int(ms * 0.1))
mostrar("STAR WARS")
esperar(1000)
