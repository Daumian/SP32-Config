# G: Gato (imagen de 128x32, fondo claro como el grabado)
import binascii
oled.buffer[:] = binascii.a2b_base64(
    "///////////++MDA/////////+/HBwcPD08/Pz+fj8/n5+fHx8fn54fX8eLNlzd7/f////9/"
    "f/9/f38/Pz8fHw8HhwcDAQAAAACAgICAAAAAAAAAEDBwwICAAAAADB4/d/vw4IAAAAAAAAAP"
    "f/7AAAAAAAAAwICAAAABAwMAgAD//////////////////////////////ngAAAACAQEJDT9D"
    "ceF5Pw8P/78/v3///4CBwfD4+PDwwICI/Pjw4ODA4MCAgAAIGHh48PDgwMCBgDBw8Pj4+PHx"
    "58fHxoyIgIAAAAEDAwcODgQAAPDw8AEDAwAAAAAwdH5+fn5+fn5+fwMBEB8fH9//////////"
    "///nw5uZOD14fPD4eGROHPDgwIAAAAAAOHBhBxhn37w9+/f///////////////38/fv79///"
    "/vz4+Pjw4+Pn58/fnx8/JwcPHx8fHx8fHz8/Pz9/f38+fP7/29gA////+AD8/AAAAAAAAgMG"
    "BgYGBgYHBALGzu7/f///Px+f3/////////9//v78+Pjw4ODgwMGBAQEAAAAAAAAAAAAAAwcP"
    "Hw8DAwEBQOP//z8fP39/PxMDAcHvfz8fDw8/Px0ZEQHA4PDw+Pz8/Pz+/v7+/n5/Pj4+Pj4c"
    "/f352EAB////AD///wAA/Pz83Pz8/Pz8/Pw="
)
oled.show()
esperar(5000)
