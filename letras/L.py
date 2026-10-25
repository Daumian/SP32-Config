# L: prende el LED de la plaquita 10 segundos. Titulo: Luz.
mostrar("Luz!", "10 segundos")
led(True)
tono(880, 150)
esperar(10000)
led(False)
tono(440, 150)
mostrar("Chau luz")
