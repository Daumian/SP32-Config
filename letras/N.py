# N: Notas. Toca la escala y muestra cada nota con su frecuencia.
NOTAS = [("DO", 262), ("RE", 294), ("MI", 330), ("FA", 349),
         ("SOL", 392), ("LA", 440), ("SI", 494), ("DO", 523)]
OCTAVA = 1   # 2 o 4 = mas agudo y mas fuerte en el buzzer
DURA = 800   # ms por nota

for nombre, hz in NOTAS:
    hz = hz * OCTAVA
    mostrar_grande(nombre, 2)
    texto = str(hz) + " Hz"
    oled.text(texto, (128 - 8 * len(texto)) // 2, 24)
    oled.show()
    tono(hz, DURA)
    esperar(200)
