def cifrado_cesar(texto):
    resultado = ""
    for caracter in texto:
        # se obtiene el código en ascii del carácter
        codigo = ord(caracter)
        # códigos de las minúsculas 97 (a) a 122 (z)
        if 97 <= codigo <= 122:
            # se resta 97 para que vaya al rango 0-25 en ascii
            codigo -= 97
            # se usa la fórmula para el cifrado cesar con clave 3
            codigo = (codigo + 3) % 26
            print(f"C = E(3,{caracter}) = ({caracter} + 3) mod 26 = {chr(codigo+97)}")
            # se vuelve a sumar 97 para volver a su codigo ascii
            codigo += 97

        # se va concatenando el texto cifrado
        resultado += chr(codigo)
    return resultado


def descifrado_cesar(texto, desplazamiento=3):
    resultado = ""
    for caracter in texto:
        # se obtiene el código en ascii del carácter
        codigo = ord(caracter)
        if 97 <= codigo <= 122:
            codigo -= 97
            codigo = (codigo - 3) % 26
            print(f"C = E(3,{caracter}) = ({caracter} - 3) mod 26 = {chr(codigo+97)}")
            codigo += 97

        # se va concatenando el texto descifrado
        resultado += chr(codigo)
    return resultado


opcion = int(input(""" elige una opción:
    1. encriptar
    2. desencriptar
"""))

if opcion == 1:
    texto = input("Escribe el texto a encriptar: ")
    print("Texto encriptado:", cifrado_cesar(texto))
else:
    texto = input("Escribe el texto a desencriptar: ")
    print("Texto desencriptado:", descifrado_cesar(texto))
