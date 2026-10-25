# 🛠️ SP32-Config — ESP32 + OLED

Banco de pruebas de electrónica: un ESP32 con pantalla OLED que muestra
texto, imágenes y GIFs enviados desde una webapp que corre en la PC.
El ESP32 es "tonto" a propósito: solo recibe frames y los dibuja. Todo el
procesamiento vive en la PC.

---

## 1. 🔌 Hardware

| Pieza | Detalle |
|---|---|
| **Placa** | ESP32-WROOM-32 (tipo NodeMCU / DevKit), 4 MB de flash, WiFi + Bluetooth |
| **Pantalla** | OLED 0.96", **128 x 32 px**, chip SSD1306, I2C (dirección `0x3C`) |
| **Botón** | Externo en **GPIO 4** (el de morse). También sirve el **BOOT** (GPIO 0) poniendo `BUTTON_PIN = 0` |
| **Protoboard + jumpers** | Para el montaje sin soldar |
| **LED + resistencia** | Componentes de prueba (no se usan en este firmware) |
| **Parlante chico** | JST, ~8 Ω / 0.5 W. Pendiente: iría a GPIO 25 con resistencia en serie |

> 🗺️ Mapa de pines con nuestra numeración en `docs/pines.html`: placa con el
> **USB arriba**, pines contados desde el USB del 1 al 19, **I** = izquierda y
> **D** = derecha. Botón: **I7** (GPIO 4) y **D6** (GND). Pantalla: **I14**
> (SDA), **I17** (SCL), **I19** (GND) y **D19** (3.3V).

### Cableado de la pantalla

```
OLED VCC -> 3.3V
OLED GND -> GND
OLED SDA -> GPIO 21
OLED SCL -> GPIO 22
```

> ⚠️ **Siempre 128x32, nunca 64.** Cuando se asumió 128x64 la pantalla se
> veía cortada y apilada. Si algún día se cambia de pantalla, hay que tocar
> `main.py` (ESP32) y `app.py` (PC) a la vez.

> ⚠️ **GPIO 6 a 11 no se pueden usar** en el ESP32-WROOM-32 (están conectados
> a la flash interna). Por eso el botón es el BOOT (GPIO 0).

---

## 2. 💻 Software y herramientas

| Dónde | Qué | Para qué |
|---|---|---|
| ESP32 | **MicroPython v1.28.0** | Firmware base de la placa |
| ESP32 | `ssd1306.py` en `/lib` | Driver de la pantalla (ya venía instalado) |
| ESP32 | `main.py` + `config.py` en la raíz | Nuestro firmware y su configuración |
| PC | **Thonny** | Subir archivos al ESP32 y usar la consola (REPL) |
| PC | **VS Code** | Editar todo el código |
| PC | **Python + venv** | Entorno aislado para la webapp |
| PC | **Flask** | Servidor de la webapp |
| PC | **Pillow** | Conversión de imágenes / GIFs / texto a blanco y negro |
| PC | `iniciar.bat` | Un doble clic: crea el venv, instala dependencias, abre el navegador y arranca el server |

---

## 3. 🗂️ Estructura

### Este repo

```
SP32-Config/
├── README.md
├── .gitignore               ignora config.py (tiene la clave del WiFi)
├── esp32/                   -> se sube al ESP32 con Thonny
│   ├── main.py              firmware (morse + comandos + frames)
│   ├── imagenes.py          imágenes de 512 bytes (IMAGEN_X)
│   └── config.example.py    plantilla: copiar como config.py y completar
├── docs/
│   └── pines.html           mapa de pines I1–I19 / D1–D19 (USB arriba)
├── pc/
│   ├── index.html           panel web: doble clic y listo, sin Python
│   └── probador.py          ¿la PC ve el ESP32 por USB? (ventanita en la PC)
└── pruebas/                 scripts sueltos para probar cosas desde Thonny
    ├── 01_chequeo_driver.py
    ├── 02_hola_pantalla.py
    ├── 03_imagen_fija.py
    ├── 04_gif_animado.py
    ├── 05_morse.py
    ├── 06_microfono.py
    └── 07_buscar_pines.py
```

> 📌 La webapp vieja con Flask (`app.py`, `templates/index.html`,
> `requirements.txt`, `iniciar.bat`) vive solo en la PC, en la carpeta
> `visual/`. Sigue andando por el puerto 8888, pero ahora la reemplaza
> `pc/index.html`, que no necesita Python.

### En el ESP32 (raíz del dispositivo)

```
├── boot.py                  el original de fábrica (no tocar)
├── main.py                  nuestro firmware
├── imagenes.py              imágenes para los comandos
├── index.html               el panel web (copia de pc/index.html, opcional)
├── config.py                WiFi, puerto, clave, pin, timeout
└── lib/
    └── ssd1306.py           driver de la pantalla
```

> `main.py` y `config.py` se editan en VS Code pero **corren en el ESP32**.
> `app.py` es el único que corre en la PC.

---

## 4. 🧠 Cómo funciona

```
 Navegador  ──HTTP──▶  Flask (PC, :5000)  ──TCP :8888──▶  ESP32  ──I2C──▶  OLED
  (web)               convierte a 1 bit                  recibe y dibuja
                      128x32 y manda frames
```

1. En la web subimos texto, imagen o GIF.
2. Flask lo convierte a blanco y negro de 128x32 (con dithering para que las
   fotos se vean bien) y lo parte en frames.
3. Un hilo en segundo plano manda los frames al ESP32 en loop.
4. El ESP32 copia cada frame directo al buffer de la pantalla.

### Protocolo TCP (puerto 8888)

Una conexión por mensaje. Cada mensaje arranca con una línea de cabecera
terminada en `\n`:

| Cabecera | Qué hace | Datos que siguen |
|---|---|---|
| `clave:FRAME\n` | Dibuja un frame | Exactamente **512 bytes** (128x32 px, formato `MONO_VLSB`) |
| `clave:RESET\n` | Reinicia el ESP32 (`machine.reset()`) | Nada |
| `clave\n` | Formato viejo, se toma como `FRAME` | 512 bytes |
| *(nada, se cierra)* | Ping de `/status`, se ignora en silencio | — |

Si la clave no coincide, el ESP32 ignora la conexión y lo avisa por consola.

### Formato `MONO_VLSB` en dos líneas

La pantalla se divide en 4 "páginas" de 8 px de alto. Cada byte es una
columna de 8 px de una página (bit 0 = pixel de arriba). Los primeros 128
bytes son la página de arriba, los siguientes 128 la segunda, y así:
`128 columnas x 4 páginas = 512 bytes`.

---

## 5. 🔘 El botón (BOOT, GPIO 0) y el morse 📡

Todo se maneja en **morse** con el botón BOOT.

| Situación | Qué hacemos | Qué pasa |
|---|---|---|
| Dormido | Un toque | **Despierta**: "Bienvenido! / Que necesita?" y queda esperando morse |
| Despierto | Toque corto / largo | Punto (`.`) / raya (`-`) |
| Despierto | Pausa corta (0,6 s) | Se cierra la letra |
| Despierto | Pausa larga (1,2 s) | Se cierra la palabra |
| Despierto | **Mantener 2 s** | **Duerme**: apaga WiFi, Bluetooth y pantalla |

### Plaquita de 2 botones (llave doble)

Una plaquita reciclada con 2 botones y un LED, conectada así (el detective
`pruebas/07_buscar_pines.py` encontró qué era cada cable):

| Cable | Pin | Qué es |
|---|---|---|
| gris | **D5** (GPIO 13) | LED: titila con cada punto y raya |
| blanco 1 | **D8** (GPIO 14) | **SW2 = raya** |
| blanco 2 | **D9** (GPIO 27) | Masa de la plaquita (el firmware lo pone en 0 V) |
| blanco 3 | **D10** (GPIO 26) | **SW1 = punto** |

Con SW1 y SW2 cada toque suma un punto o una raya al instante, sin medir
tiempos. Las pausas cierran letras y palabras igual que con el botón de
siempre, que sigue andando. Cualquiera de los botones despierta la placa.
Los pines se cambian (o se apaga la plaquita con `None`) en `config.py`.

### Comandos

Una palabra de **una sola letra** ejecuta un comando. Si la letra está dentro
de una palabra (por ejemplo "BOX"), queda como texto normal.

| Letra | Morse | Comando |
|---|---|---|
| **B** | `-...` | Muestra si el **Bluetooth** está ON/OFF y lo cambia |
| **W** | `.--` | Muestra si el **WiFi** está ON/OFF y lo cambia (al prender muestra la IP) |
| **X** | `-..-` | Muestra la imagen `IMAGEN_X` (de `imagenes.py`) 3 segundos |
| **M** | `--` | **Escritura libre**: se apagan los comandos y escribimos lo que queramos. **más de 6 puntos seguidos** (`.......`) para salir |

Abajo a la derecha de la pantalla aparece una **W** si el WiFi está prendido y
una **B** si el Bluetooth está prendido, y una **M** en escritura libre.

El texto en morse se ve en **un renglón de 10 letras** de tamaño mediano
(12 px); a medida que escribimos se va corriendo como un cartel. Para sumar comandos nuevos se agrega
una función y una letra al diccionario `COMANDOS` en `main.py`.

- Al enchufarlo arranca **dormido**, con WiFi y Bluetooth apagados.
- Para mandar cosas desde la PC, primero prendemos el WiFi con **W**.
- A los **3 minutos sin uso** se apaga solo la pantalla (`SCREEN_TIMEOUT_MS`).
  El WiFi sigue prendido. El primer toque la prende sin escribir nada, y si
  llega algo desde la web también se prende sola.
- A los **10 minutos sin actividad** se duerme del todo (`IDLE_TIMEOUT_MS`).
- **Modo edición**: al reiniciar (botón EN), la pantalla dice
  "BOOT = editar (2 segundos)". Si tocamos BOOT **en esos 2 segundos**,
  `main()` no corre y Thonny puede usar la placa sin "Device is busy".
  ⚠️ No hay que tener BOOT apretado *en el momento* del reset, porque así entra
  en modo bootloader.

---

## 6. 🌐 El panel web (`pc/index.html`)

Un solo archivo HTML: **doble clic** y se abre en el navegador. No necesita
Python, Flask ni nada instalado. La conversión a 128x32 en blanco y negro
(con dithering) la hace el propio navegador, y le manda los frames al ESP32
por **HTTP** (puerto 80).

1. En el ESP32: despertarlo y mandar **W** (`.--`) en morse → anotar la IP.
2. Abrir `pc/index.html` (Chrome o Edge), poner la **IP** y la **clave**
   (`SHARED_SECRET`). Quedan guardadas en el navegador.
3. Si Chrome pregunta si dejamos que la página acceda a **dispositivos de la
   red local**, decir que sí.

Qué tiene:

- **Indicador** verde/rojo arriba a la derecha (se actualiza cada 10 s) y el
  texto que venimos escribiendo en morse.
- **Vista previa** de lo que se ve en la OLED.
- **Texto**: si entra se centra; si es largo se desliza como cartel de LED.
  Tamaño chico/mediano/grande y **Negativo**.
- **Imagen o GIF**: entera o recortada, dithering y negativo. Los GIF
  animados se reproducen en loop.
- **Comandos**: los mismos del morse (B, X, W) y **Reiniciar**.
- **Detener** frena una animación o un texto deslizante.

### 📱 Usarlo desde el celu (u otro aparato)

Cualquier aparato con navegador **en el mismo WiFi** sirve. Para no tener que
pasarle el archivo, subimos `index.html` **a la placa** y la placa misma
sirve la página:

1. En Thonny (modo edición): panel **Archivos** → arriba, en *Este equipo*,
   buscamos `index.html` → clic derecho → **Subir a /**.
2. Desde el celu (o cualquier aparato): `http://192.168.1.53` (la IP del
   ESP32). La IP se completa sola; solo falta la clave.

> 💡 En iPhone (Safari) los GIF se ven como imagen fija; lo demás anda igual.

### Rutas HTTP del ESP32

Todas menos `/estado` llevan `?clave=SHARED_SECRET`.

| Ruta | Método | Función |
|---|---|---|
| `/` | GET | El panel (`index.html` guardado en la placa) |
| `/estado` | GET | JSON con `wifi`, `bluetooth`, `texto`, `escritura_libre`, `pantalla` y `comandos` |
| `/frame` | POST | Cuerpo de 512 bytes (`MONO_VLSB`): se dibuja |
| `/comando?letra=B` | POST | Ejecuta un comando, igual que en morse |
| `/reset` | POST | Reinicia la placa |

### La webapp vieja (Flask, carpeta `visual/` en la PC)

Sigue funcionando por TCP (puerto 8888) con el mismo protocolo de la sección 4.
Rutas: `/`, `/send_text`, `/upload_image`, `/upload_gif`, `/status`, `/restart`.

---

## 7. ⚙️ Configuración

### `config.py` (ESP32)

Se arma copiando `esp32/config.example.py` como `config.py`.

| Variable | Qué es |
|---|---|
| `WIFI_SSID` / `WIFI_PASS` | La red WiFi (2.4 GHz) |
| `ESP_FRAME_PORT` | Puerto TCP para la webapp vieja (8888) |
| `HTTP_PORT` | Puerto del panel web (opcional, 80 por defecto) |
| `SHARED_SECRET` | Clave compartida con la PC |
| `BUTTON_PIN` | 0 (botón BOOT) |
| `SCREEN_TIMEOUT_MS` | Cuánto tarda en apagar la pantalla (opcional, 3 min) |
| `IDLE_TIMEOUT_MS` | Cuánto tarda en dormirse del todo (10 min) |

### `app.py` (PC)

| Variable | Qué es |
|---|---|
| `ESP32_IP` | IP del ESP32 en la red (la última vista fue `192.168.1.53`) |
| `ESP32_PORT` | 8888 |
| `SHARED_SECRET` | **Tiene que ser idéntica** a la de `config.py` |
| `WIDTH, HEIGHT` | 128, 32 |
| `MIN_FRAME_DELAY` | Velocidad máxima de frames (0.05 s) para no saturar al ESP32 |
| `STILL_IMAGE_REFRESH` | Cada cuánto se re-manda una imagen fija (1 s) |
| `SCROLL_STEP_PX` / `SCROLL_FRAME_DELAY` | Velocidad del texto deslizante |

> 💡 **La IP del ESP32 puede cambiar** si el router se la reasigna. Lo ideal es
> reservarla en el router (reserva DHCP) para que quede fija.

---

## 8. 🚀 Uso diario

1. Enchufar el ESP32.
2. Tocar BOOT → "Bienvenido!". Mandar **W** (`.--`) → esperar la IP en pantalla.
3. Doble clic a `pc/index.html` → se abre el panel.
4. Chequear que el punto de arriba a la derecha esté verde.
5. Mandar texto, imagen o GIF.
6. Al terminar, mantener BOOT 2 s (o esperar los 10 min).

---

### 🔋 Sin la PC (con batería)

El firmware vive en la placa: la PC solo hace falta para cambiarle el código.
Para usarlo suelto alcanza con darle energía por el USB:

- **Power bank** común + cable USB: lo más fácil. Algunos se apagan solos si
  el consumo es bajo (por ejemplo con la placa dormida); si pasa, probar otro.
- El panel se abre desde el celu en `http://<IP del ESP32>` (ver sección 6),
  siempre que el celu y la placa estén en el **mismo WiFi**.
- Fuera de casa: poner en `config.py` el hotspot del celu como red WiFi.

---

## 9. 📤 Subir el firmware al ESP32 (Thonny)

1. Conectar el ESP32 y elegir en Thonny el intérprete **MicroPython (ESP32)**
   (abajo a la derecha).
2. **Ctrl+C** en la consola para frenar `main.py`. Si dice "busy", usar el
   **modo edición** (BOOT apretado al reiniciar).
3. Abrir `config.py` → *Guardar como* → **MicroPython device** → `config.py`.
4. Abrir `esp32/imagenes.py` → *Guardar como* → **MicroPython device** → `imagenes.py`.
5. Abrir `esp32/main.py` → *Guardar como* → **MicroPython device** → `main.py`.
   (Siempre **`main.py` al final**.)
6. Reiniciar la placa (botón EN) y **no** tocar BOOT durante los 2 segundos.
7. Tocar BOOT → "Bienvenido!". En la consola sale `Despierto, esperando morse`.

---

## 10. 🧪 Pruebas sueltas (`pruebas/`)

Scripts para probar cosas sin tocar el firmware. Se corren con **Run (F5)**
en Thonny **sin guardarlos en el ESP32**: corren en RAM y al reiniciar
vuelve el `main.py` normal. Antes de cada uno, Ctrl+C para frenar `main.py`.

| Script | Qué prueba | Qué tendríamos que ver |
|---|---|---|
| `01_chequeo_driver.py` | Que el driver `ssd1306` esté instalado | `/lib/ssd1306.py` en la consola |
| `02_hola_pantalla.py` | Cableado I2C + pantalla | `['0x3c']` en consola y texto en la OLED |
| `03_imagen_fija.py` | Dibujar 512 bytes a mano | Una imagen fija |
| `04_gif_animado.py` | Animación por frames | Un GIF en loop (Ctrl+C para frenar) |
| `05_morse.py` | Lectura del botón con tiempos | Escribir en Morse con BOOT |
| `06_microfono.py` | Micrófono electret en GPIO 34 (con resistencia a 3.3V) | Un vúmetro: la barra sube con aplausos o soplidos |
| `07_buscar_pines.py` | Qué cable es cada cosa en una plaquita de botones | Pares de GPIO que se unen al apretar cada botón |

> 💡 Para hacer imágenes a mano: herramientas tipo *image2cpp* exportan bytes
> en formato **vertical, 1 bit por pixel** (`MONO_VLSB`), 128x32.

---

### 🔌 Probador USB (`pc/probador.py`)

Ventanita en la PC que se fija si la PC **ve el ESP32 por el cable USB**.
Sirve cuando Thonny dice "Couldn't find the device" y la placa "entra y sale".

- **▶ Probar**: revisa cada medio segundo. **■ Stop**: deja de revisar.
- Anota con la hora cada vez que se conecta o se desconecta, y cuenta las
  desconexiones. Si el número sube sin tocar nada: cable flojo o malo, o
  puerto USB con problemas.
- No le manda nada a la placa, así que puede estar abierto junto con Thonny.

```
pip install pyserial
python probador.py
```

---

## 11. 📓 Bitácora del proceso

Lo que fuimos aprendiendo (y rompiendo) en el camino:

1. **Primeros pasos**: MicroPython 1.28 en el ESP32, Thonny para subir cosas.
   Chequeamos que el driver `ssd1306` ya venía en `/lib` (`01_chequeo_driver.py`).
2. **Pantalla**: arrancamos asumiendo 128x64 y se veía cortada/apilada. Era
   **128x32**. Desde ahí, siempre 32 de alto en todos lados.
3. **Imágenes a mano**: convertimos imágenes a arrays de 512 bytes y las
   dibujamos con `framebuf` (`03_imagen_fija.py`).
4. **Animaciones**: varios arrays en una lista, en loop con `sleep`
   (`04_gif_animado.py`).
5. **Morse**: un botón externo en GPIO 4 para escribir en Morse, con texto al
   doble de tamaño y apagado por inactividad (`05_morse.py`). Después pasamos
   a usar el **BOOT (GPIO 0)** para no depender de cableado extra.
6. **WiFi + PC**: en vez de meter los bytes en el código, la PC (Flask +
   Pillow) convierte texto/imagen/GIF y los manda por TCP. El ESP32 solo dibuja.
7. **Botón de encendido**: un toque despierta/duerme; 10 min de inactividad lo
   duerme solo.
8. **"Device is busy" en Thonny**: como `main.py` ocupa el puerto, sumamos el
   **modo edición** (BOOT apretado al reiniciar).
9. **Webapp completa**: indicador de estado, botón Verificar, botón Reiniciar
   por WiFi, checkbox Negativo, texto deslizante.
10. **Cuelgues/reinicios**: probablemente caída de tensión por los picos del
    WiFi → cable USB corto y bueno, puerto directo, capacitor pendiente.
11. **Firmware unificado** (este repo): `main.py` ahora entiende `FRAME`,
    `RESET` y el formato viejo, y no ensucia la consola con los pings de
    `/status`. `config.py` sale de una plantilla y no se sube a GitHub.
12. **Todo en morse**: el BOOT pasa a ser llave de morse. Comandos de una
    letra (B Bluetooth, W WiFi, X imagen), saludo al despertar y modo edición
    con ventana de 2 s después del reset. El morse pasa al botón externo
    (GPIO 4, cambiando `BUTTON_PIN` en `config.py`).
13. **Panel web sin Python**: `pc/index.html` convierte todo en el navegador
    y se lo manda al ESP32 por HTTP.
14. **Escritura libre y ahorro**: comando **M** (`--`) para escribir sin comandos
    (más de 6 puntos para salir), pantalla que se apaga a los 3 min y la placa
    sirviendo el panel para usarlo desde el celu.
15. **Llave doble**: una plaquita reciclada de 2 botones (SW1 punto, SW2
    raya) con su LED titilando, más el mapa de pines (`docs/pines.html`)
    y el probador USB (`pc/probador.py`).

---

## 12. 🩺 Problemas conocidos y soluciones

| Síntoma | Causa probable | Solución |
|---|---|---|
| Thonny: "Device is busy" | `main.py` está corriendo y ocupa el puerto | Ctrl+C, o modo edición (BOOT al reiniciar) |
| Pantalla cortada/apilada | Se configuró 128x64 en vez de 128x32 | Revisar que ambos lados usen 32 de alto |
| `i2c.scan()` devuelve `[]` | Cableado SDA/SCL flojo o invertido | Revisar GPIO 21 (SDA) y 22 (SCL), y VCC a 3.3V |
| Texto minúsculo en la pantalla | Es la fuente por defecto de 8 px | Mandar texto desde la web (se renderiza más grande) |
| IP `0.0.0.0` en Thonny | WiFi apagado | Despertarlo y mandar **W** en morse |
| Thonny: "make sure the device is not in bootloader mode" | BOOT apretado justo en el reset | Soltar EN primero y *después* tocar BOOT |
| Pantalla apagada al enchufar | Arranca dormido a propósito | Tocar BOOT |
| Web dice "apagado/dormido" pero la pantalla dice "Listo" | IP distinta en `app.py`, o el ESP32 se colgó | Verificar IP, `ping`, y probar Reiniciar |
| `timed out` en la consola de Flask | El ESP32 duerme; el loop reintenta cada 2 s | Normal. Despertarlo con BOOT |
| `Clave incorrecta` en la consola del ESP32 | `SHARED_SECRET` distinta en cada lado | Igualarlas en `config.py` y `app.py` |
| `/restart` da 404 | `app.py` viejo en la PC | Reemplazar por la versión completa y reiniciar el server |
| `ConnectionError: EOF` / Thonny no encuentra el puerto | Cuelgue o brownout del ESP32 | Cable USB corto, puerto directo de la PC |
| Reinicios solos al usar WiFi | **Caída de tensión** por los picos de corriente del WiFi | USB directo, cable corto y bueno, capacitor de 100–220 µF entre 3.3V y GND |
| `ImportError: no module named 'config'` / `'imagenes'` | Falta ese archivo en el ESP32 | Subirlo (ver sección 9) |
| `.bat` tira `´╗┐@echo` | El archivo se guardó con BOM | En VS Code: *Save with Encoding → UTF-8* |
| Error `runtime.lastError` en la consola del navegador | Ruido de una extensión de Chrome | Ignorar |
| Cambios en la web no se ven | Caché del navegador | Ctrl+Shift+R |

---

## 13. 🔒 Seguridad

- Todo funciona **solo dentro de la red local**; nada se expone a internet y
  no hay que abrir puertos en el router.
- La `SHARED_SECRET` es una capa mínima: sin ella, el ESP32 ignora los
  comandos. No está cifrada (va en texto plano por la LAN), así que alcanza
  para uso casero pero no es seguridad "seria".
- `config.py` tiene la **contraseña del WiFi en texto plano**: está en
  `.gitignore` y **nunca** se sube a GitHub. En el repo solo va
  `config.example.py` con datos de mentira.
- Conviene cambiar la clave `cambiame123` por una propia (igual en los dos lados).

---

## 14. 🔭 Ideas / pendientes

- Parlante: terminar el cableado (GPIO 25 + resistencia en serie) y probar
  tonos con PWM.
- Reservar la IP del ESP32 en el router para no tocar `app.py` cada vez.
- Texto más grande en pantalla para los mensajes del propio ESP32 (IP, estados).
- Alimentación más estable (capacitor) si siguen los cuelgues.
