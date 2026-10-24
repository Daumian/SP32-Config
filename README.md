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
| **Botón** | El botón **BOOT** de la placa (GPIO 0), el que está junto al USB |
| **Protoboard + jumpers** | Para el montaje sin soldar |
| **LED + resistencia** | Componentes de prueba (no se usan en este firmware) |
| **Parlante chico** | JST, ~8 Ω / 0.5 W. Pendiente: iría a GPIO 25 con resistencia en serie |

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
│   ├── main.py              firmware
│   └── config.example.py    plantilla: copiar como config.py y completar
└── pruebas/                 scripts sueltos para probar cosas desde Thonny
    ├── 01_chequeo_driver.py
    ├── 02_hola_pantalla.py
    ├── 03_imagen_fija.py
    ├── 04_gif_animado.py
    └── 05_morse.py
```

> 📌 La webapp (`app.py`, `templates/index.html`, `requirements.txt`,
> `iniciar.bat`) todavía vive solo en la PC, en la carpeta `visual/`.
> Pendiente: sumarla al repo en una carpeta `pc/`.

### En el ESP32 (raíz del dispositivo)

```
├── boot.py                  el original de fábrica (no tocar)
├── main.py                  nuestro firmware
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

## 5. 🔘 El botón (BOOT, GPIO 0)

| Situación | Un toque hace... |
|---|---|
| ESP32 dormido | **Despierta**: prende pantalla, conecta WiFi, muestra "Listo" + IP |
| ESP32 despierto | **Duerme**: apaga WiFi y pantalla |

- Al enchufarlo arranca **dormido** (pantalla apagada): hay que tocar BOOT.
- A los **10 minutos sin actividad** se duerme solo (`IDLE_TIMEOUT_MS`).
- **Modo edición**: si mantenemos apretado BOOT *mientras reiniciamos* la
  placa (botón EN), `main()` no corre y el puerto queda libre para subir
  archivos desde Thonny sin el error "Device is busy". Para volver a modo
  normal, reiniciar **sin** apretar BOOT.

---

## 6. 🌐 La webapp

Se abre en `http://localhost:5000` (o desde el celu con la IP de la PC).

- **Mensaje de texto**: si entra en pantalla se centra; si es largo se desliza
  como cartel de LED.
- **Imagen**: se convierte a 128x32 en blanco y negro. Checkbox **Negativo**
  para invertir blanco/negro.
- **GIF**: se convierte cuadro por cuadro y se reproduce en loop. También
  tiene checkbox **Negativo**.
- **Indicador arriba a la derecha**: punto verde/rojo que dice si el ESP32 está
  conectado. Se actualiza cada 10 s (sin mandarle datos).
  - Botón **Verificar**: chequea al instante.
  - Botón **Reiniciar**: le manda `RESET` por WiFi (solo sirve si el ESP32
    todavía responde).

### Rutas del servidor

| Ruta | Método | Función |
|---|---|---|
| `/` | GET | La página |
| `/send_text` | POST | Envía un texto |
| `/upload_image` | POST | Envía una imagen (`invert` opcional) |
| `/upload_gif` | POST | Envía un GIF (`invert` opcional) |
| `/status` | GET | Dice si el ESP32 está despierto |
| `/restart` | POST | Reinicia el ESP32 |

---

## 7. ⚙️ Configuración

### `config.py` (ESP32)

Se arma copiando `esp32/config.example.py` como `config.py`.

| Variable | Qué es |
|---|---|
| `WIFI_SSID` / `WIFI_PASS` | La red WiFi (2.4 GHz) |
| `ESP_FRAME_PORT` | Puerto TCP donde escucha (8888) |
| `SHARED_SECRET` | Clave compartida con la PC |
| `BUTTON_PIN` | 0 (botón BOOT) |
| `IDLE_TIMEOUT_MS` | Cuánto tarda en dormirse solo (10 min) |

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
2. Tocar BOOT → esperar "Listo" + IP en la pantalla.
3. Doble clic a `iniciar.bat` → se abre la web.
4. Chequear que el punto de arriba a la derecha esté verde.
5. Mandar texto, imagen o GIF.
6. Al terminar, tocar BOOT de nuevo (o esperar los 10 min).

---

## 9. 📤 Subir el firmware al ESP32 (Thonny)

1. Conectar el ESP32 y elegir en Thonny el intérprete **MicroPython (ESP32)**
   (abajo a la derecha).
2. **Ctrl+C** en la consola para frenar `main.py`. Si dice "busy", usar el
   **modo edición** (BOOT apretado al reiniciar).
3. Abrir `config.py` → *Guardar como* → **MicroPython device** → `config.py`.
4. Abrir `esp32/main.py` → *Guardar como* → **MicroPython device** → `main.py`.
   (Siempre **`main.py` al final**.)
5. Reiniciar la placa (botón EN) **sin** apretar BOOT.
6. Tocar BOOT → en la consola tiene que aparecer `Despierto. IP: ...`.

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

> 💡 Para hacer imágenes a mano: herramientas tipo *image2cpp* exportan bytes
> en formato **vertical, 1 bit por pixel** (`MONO_VLSB`), 128x32.

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

---

## 12. 🩺 Problemas conocidos y soluciones

| Síntoma | Causa probable | Solución |
|---|---|---|
| Thonny: "Device is busy" | `main.py` está corriendo y ocupa el puerto | Ctrl+C, o modo edición (BOOT al reiniciar) |
| Pantalla cortada/apilada | Se configuró 128x64 en vez de 128x32 | Revisar que ambos lados usen 32 de alto |
| `i2c.scan()` devuelve `[]` | Cableado SDA/SCL flojo o invertido | Revisar GPIO 21 (SDA) y 22 (SCL), y VCC a 3.3V |
| Texto minúsculo en la pantalla | Es la fuente por defecto de 8 px | Mandar texto desde la web (se renderiza más grande) |
| IP `0.0.0.0` en Thonny | El ESP32 está dormido, WiFi apagado | Tocar BOOT para despertarlo |
| Pantalla apagada al enchufar | Arranca dormido a propósito | Tocar BOOT |
| Web dice "apagado/dormido" pero la pantalla dice "Listo" | IP distinta en `app.py`, o el ESP32 se colgó | Verificar IP, `ping`, y probar Reiniciar |
| `timed out` en la consola de Flask | El ESP32 duerme; el loop reintenta cada 2 s | Normal. Despertarlo con BOOT |
| `Clave incorrecta` en la consola del ESP32 | `SHARED_SECRET` distinta en cada lado | Igualarlas en `config.py` y `app.py` |
| `/restart` da 404 | `app.py` viejo en la PC | Reemplazar por la versión completa y reiniciar el server |
| `ConnectionError: EOF` / Thonny no encuentra el puerto | Cuelgue o brownout del ESP32 | Cable USB corto, puerto directo de la PC |
| Reinicios solos al usar WiFi | **Caída de tensión** por los picos de corriente del WiFi | USB directo, cable corto y bueno, capacitor de 100–220 µF entre 3.3V y GND |
| `ImportError: no module named 'config'` | Falta `config.py` en el ESP32 | Subirlo (ver sección 9) |
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

- Subir la webapp (`app.py`, `index.html`, `iniciar.bat`) al repo en `pc/`.
- Parlante: terminar el cableado (GPIO 25 + resistencia en serie) y probar
  tonos con PWM.
- Reservar la IP del ESP32 en el router para no tocar `app.py` cada vez.
- Texto más grande en pantalla para los mensajes del propio ESP32 (IP, estados).
- Alimentación más estable (capacitor) si siguen los cuelgues.
