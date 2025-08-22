#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#####################################################
# Camada Física da Computação
#Carareto
#17/02/2018
#  Camada de Enlace
####################################################

# Importa pacote de tempo
import time

# Threads
import threading

# Class
class RX(object):
  
    def __init__(self, fisica):
        self.fisica      = fisica
        self.buffer      = bytes(bytearray())
        self.threadStop  = False
        self.threadMutex = True
        self.READLEN     = 1024

    def thread(self): 
        while not self.threadStop:
            if(self.threadMutex == True):
                rxTemp, nRx = self.fisica.read(self.READLEN)
                if (nRx > 0):
                    self.buffer += rxTemp  
                time.sleep(0.01)

    def threadStart(self):       
        self.thread = threading.Thread(target=self.thread, args=())
        self.thread.start()

    def threadKill(self):
        self.threadStop = True

    def threadPause(self):
        self.threadMutex = False

    def threadResume(self):
        self.threadMutex = True

    def getIsEmpty(self):
        if(self.getBufferLen() == 0):
            return(True)
        else:
            return(False)

    # Retorna o tamanho atual do buffer de recepção, o quanto de dado ja foi recebido
    # Buffer são os dados que ja foram lidos na camada física
    # Mede quantos bytes existem no buffer até o momento
    def getBufferLen(self):
        return(len(self.buffer))

    # Pega todos os dados que estão no buffer nesse momento, devolve e esvazia o bufer
    def getAllBuffer(self, len):
        self.threadPause() # Para a thread de recepção, não mexe mais no buffer, evita ler o buffer enquanto novos dados chegam
        b = self.buffer[:] # Cópia do buffer atual
        self.clearBuffer() # Esvazia o buffer, depois de chamar a função, os dados que estavam lá ja foram consumidos e não seram entreguer novamente
        self.threadResume() # Libera o thread de recepção para colocar novos dados
        return(b) # retorna os dados que estavam no buffer

    # Retira os primeiros nData bytes do buffer e devolve. Depois remove esses dados do buffer, mantendo só o que sobrou
    # Devolve os n primeiros bytes do buffer para mim 
    # Os primeiros dados que chegam, que são os primeiros que eu vou processar
    # Depois de consumidos, eles não fazem sentido de ficar guardados, se não remover processaríamos a mesma info várias vezes
    def getBuffer(self, nData):
        self.threadPause() # Para de ficar recebendo dados, não mexe no buffer enquanto esmos lendo
        b           = self.buffer[0:nData] # Copia os primeiros bytes do buffer
        self.buffer = self.buffer[nData:] # Remove do buffer os dados que ja foram lidos
        self.threadResume() # libera a thread de recepção para voltar a encher o buffer com dados novamente
        return(b) # devolve os bytes que eu pedi 
    
    # Garante que só peguemos os dados do buffer quando ele já tiver pelo menos um certo número de bytes disponíveis
    # evita ler dados que ainda não chegaram
    def getNData(self, size):
        while(self.getBufferLen() < size):
            time.sleep(0.05) # para não travar em um loop infinito             
        return(self.getBuffer(size)) #chama a função para  retirar exatamente size bytes e devolver para mim


    def clearBuffer(self):
        self.buffer = b""
        