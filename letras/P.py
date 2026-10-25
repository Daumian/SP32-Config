# P: Marcha peronista (de la tablatura de armonica en La). Titulo: Marcha.
# Cada nota es nota:tiempos. "-" = silencio.
MELODIA = (
    "do#2:1 la:1 mi:1 do#2:1 la:1 mi:1 do#2:1 la:2 -:1 "               # Los muchachos peronistas
    "do#2:1 la:1 mi:1 do#2:1 do#2:1 si:1 la:1 si:1 sol#:2 -:1 "        # todos unidos triunfaremos
    "si:1 sol#:1 mi:1 si:1 sol#:1 mi:1 si:1 sol#:2 -:1 "               # y como siempre daremos
    "re2:1 re2:1 re2:1 re2:1 do#2:1 si:1 do#2:2 -:1 "                  # un grito de corazon
    "re2:1 do#2:1 si:1 do#2:2 -:1 "                                    # Viva Peron!
    "re2:1 do#2:1 si:1 do#2:2 -:1 "                                    # Viva Peron!
    "re2:1 do#2:1 si:1 do#2:3 "                                        # Viva Peron!
)
ESTRIBILLO = (
    "-:2 do#2:1 do#2:1 do#2:1 do#2:1 si:1 la:1 sol#:1 la:2 -:1 "       # Peron Peron que grande sos
    "do#2:1 do#2:1 do#2:1 do#2:1 si:1 la:1 sol#:1 la:3 "               # Peron Peron que grande sos
)
CON_ESTRIBILLO = False  # True = agrega "Peron, Peron, que grande sos"
TEMPO = 200             # ms por tiempo: mas chico = mas rapido

BASE = {"do": 262, "do#": 277, "re": 294, "re#": 311, "mi": 330, "fa": 349,
        "fa#": 370, "sol": 392, "sol#": 415, "la": 440, "la#": 466, "si": 494}


def frecuencia(nota):
    octava = 1
    if nota[-1] in "12":
        octava = 0.5 if nota[-1] == "1" else 2
        nota = nota[:-1]
    return int(BASE[nota] * octava)


mostrar("Los muchachos", "peronistas...")
notas = MELODIA + (ESTRIBILLO if CON_ESTRIBILLO else "")
for parte in notas.split():
    nota, tiempos = parte.split(":")
    ms = int(float(tiempos) * TEMPO)
    if nota == "-":
        esperar(ms)
    else:
        tono(frecuencia(nota), int(ms * 0.9))
        esperar(int(ms * 0.1))
mostrar("Viva Peron!", "Viva Peron!")
