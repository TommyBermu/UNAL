# hecho por Tomas Alejandro Bermudez Guaqueta


def mcd(a, b):
    # devuelve el MCD de a y b usando el algoritmo de euclides
    a, b = abs(a), abs(b)  # por si vienen negativos

    while b != 0:
        resto = a % b  # sacamos el resto de la división
        a = b  # el divisor pasa a ser el nuevo dividendo
        b = resto  # y el resto pasa a ser el nuevo divisor

    return a


def mcd_recursivo(a, b):
    # misma idea pero recursiva
    if b == 0:
        return abs(a)
    return mcd_recursivo(b, a % b)


def pedir_numero(mensaje):
    # pide un numero entero por teclado y repite hasta que sea valido
    while True:
        texto = input(mensaje)
        try:
            numero = int(texto)
            return numero
        except ValueError:
            # por si no dan números
            print("Eso no es un número entero, intenta otra vez")


print("=== algoritmo de euclides ===")
n1 = pedir_numero("primer número: ")
n2 = pedir_numero("segundo número: ")

# si los dos son 0 el MCD no está definido
if n1 == 0 and n2 == 0:
    print("el MCD de 0 y 0 no está definido")

else:
    resultado_iterativo = mcd(n1, n2)
    resultado_recursivo = mcd_recursivo(n1, n2)

    print("MCD (iterativo):", resultado_iterativo)
    print("MCD (recursivo):", resultado_recursivo)
