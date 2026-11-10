# código hecho por Tomas Bermudez


def cifrado_cesar(texto, alfabeto, desplazamiento):
    resultado = ""

    # se crea un diccionario para saber el índice de una letra sin iterar por todo el arreglo cada vez que se quiera saber
    diccionario = dict()
    for i in range(len(alfabeto)):
        diccionario[alfabeto[i]] = i

    for caracter in texto:
        # se busca el código del caracter
        codigo = diccionario[caracter]
        # se usa la fórmula para sacar el código del caractar cifrado
        cifrado = (codigo + desplazamiento) % len(alfabeto)
        print(
            f"C = E({desplazamiento},{caracter}) = ({caracter} + {desplazamiento}) mod {len(alfabeto)} = {alfabeto[cifrado]}"
        )

        # se va concatenando el caracter cifrado con el alfabeto
        resultado += alfabeto[cifrado]
    return resultado


def descifrado_cesar(texto, alfabeto, desplazamiento):
    resultado = ""

    # se crea un diccionario para saber el índice de una letra sin iterar por todo el arreglo cada vez que se quiera saber
    diccionario = dict()
    for i in range(len(alfabeto)):
        diccionario[alfabeto[i]] = i

    for caracter in texto:
        # se busca el código del caracter
        codigo = diccionario[caracter]
        # se usa la fórmula para sacar el código del caractar descifrado
        descifrado = (codigo - desplazamiento) % len(alfabeto)
        print(
            f"C = E({desplazamiento},{caracter}) = ({caracter} - {desplazamiento}) mod {len(alfabeto)} = {alfabeto[descifrado]}"
        )

        # se va concatenando el caracter descifrado con el alfabeto
        resultado += alfabeto[descifrado]
    return resultado


# esta función sirve para detectar si hay separador o no, si sí hay, entonces es
# el caracter que se repite en el alfabeto (el resto no se repiten) por lo que
# se supone que el cada dos carácteres es un caracter perteneciente al alfabeto
# los que están en medio son los separadores y se omiten
def extraer_elementos_por_salto(linea):
    linea = linea.strip()

    # Si la línea no tiene caracteres repetidos, no hay separador
    if len(linea) == len(set(linea)):
        return list(linea)

    # Slicing directo de paso 2 (toma índice 0, 2, 4, 6...)
    elementos = list(linea[::2])

    return elementos


with open("entrada_programa.txt", "r", encoding="utf-8") as file:
    lineas = file.readlines()

# primera linea: alfabeto
alfabeto = extraer_elementos_por_salto(lineas[0])

# segunda linea: el texto a cifrar
texto = lineas[1].strip()

# tercera linea: clave
clave = int(lineas[2].strip())

opcion = int(input("""
    1. Encriptar
    2. Desencriptar
"""))

if opcion == 1:
    print(f"Texto encriptado: {cifrado_cesar(texto, alfabeto, clave)}")
else:
    print(f"Texto desencriptado: {descifrado_cesar(texto, alfabeto, clave)}")
