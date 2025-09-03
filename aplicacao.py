from enlace import *
import time
import struct

# Ajuste a porta
serialName = "COM6"  

def main():
    try:
        print("Iniciou o Server")
        com1 = enlace(serialName)
        com1.enable()

        # Byte de sacrifício
        print("esperando 1 byte de sacrifício...")
        rxBuffer, nRx = com1.getData(1) #Comentar para erro de interpretação do enunciado
        com1.rx.clearBuffer()
        time.sleep(.1)
        print("Byte de sacrifício recebido e descartado.")

        # Recebe quantidade de números (int32)
        qtd_bytes, _ = com1.getData(4)
        qtd = struct.unpack('!I', qtd_bytes)[0]
        print(f"Servidor receberá {qtd} números.")

        numeros = []
        for i in range(qtd):
            rxBuffer, _ = com1.getData(4)  # float32 = 4 bytes
            num = struct.unpack('!f', rxBuffer)[0]
            numeros.append(num)
            print(f"Recebi número {i+1}: {num:.6f}")

        soma = sum(numeros)
        print(f"Soma calculada: {soma:.6f}")

        # Envia a soma de volta (float32)
        soma_bytes = struct.pack('>f', soma)
        com1.sendData(soma_bytes)

        print("-------------------------")
        print("Comunicação encerrada")
        print("-------------------------")
        com1.disable()

    except Exception as erro:
        print("ops! :-\\", erro)
        com1.disable()

if __name__ == "__main__":
    main()
