from enlace import *
import time
import struct
import numpy as np

serialName = "COM11"  

def main():
    try:
        print("Iniciou o Client")
        com1 = enlace(serialName)
        com1.enable()

        # Byte de sacrifício
        time.sleep(.2)
        com1.sendData(b'00')
        time.sleep(1)
        print("Byte de sacrifício enviado.")

        qtd = 0
        while qtd < 5 or qtd > 15:
            qtd = int(input("Quantos números deseja enviar (entre 5 e 15)? "))

        numeros = []
        for i in range(qtd):
            while True:
                try:
                    num = float(input(f"Digite o número {i+1}: "))
                    if abs(num) > 1e38:
                        print("Número fora do intervalo permitido! Tente novamente.")
                        continue
                    numeros.append(num)
                    break
                except ValueError:
                    print("Entrada inválida, digite novamente.")

        print(f"Enviando {qtd} números:", numeros)

        #enviando quantidade de números
        com1.sendData(struct.pack('!I', qtd))
        time.sleep(0.1)

        #envia os números(Float32)
        i=0
        for num in numeros:
            #data = struct.pack('!f', num)
            #com1.sendData(data)
            #time.sleep(0.05)
            if i == 2:
                data = struct.pack('!f', num)[:1]
                com1.sendData(data)
            else:
                data = struct.pack('!f', num)
                com1.sendData(data)
            time.sleep(0.05)
            
            i+=1

        #espera servidor
        print("Aguardando soma do servidor...")
        start = time.time()
        soma_bytes, nRx = b"", 0
        while (time.time() - start) < 5 and nRx == 0:
            if not com1.rx.getIsEmpty():
                soma_bytes, nRx = com1.getData(4)

        if nRx == 0:
            print("Time out: servidor não respondeu.")
        else:
            soma = struct.unpack('!f', soma_bytes)[0]
            soma_check = np.sum(np.array(numeros, dtype=np.float32))
            print(f"Soma recebida do servidor: {soma:.6f}")
            print(f"Soma calculada localmente: {soma_check:.6f}")
            if abs(soma - soma_check) > 1e-5:
                print("Resultado inconsistente!")
            else:
                print("Soma correta!")

        print("-------------------------")
        print("Comunicação encerrada")
        print("-------------------------")
        com1.disable()

    except Exception as erro:
        print("ops! :-\\", erro)
        com1.disable()

if __name__ == "__main__":
    main()
