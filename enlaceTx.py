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
class TX(object):
 
    def __init__(self, fisica):
        self.fisica      = fisica
        self.buffer      = bytes(bytearray())
        self.transLen    = 0
        self.empty       = True
        self.threadMutex = False
        self.threadStop  = False


    def thread(self):
        while not self.threadStop:
            if(self.threadMutex):
                self.transLen    = self.fisica.write(self.buffer)
                self.threadMutex = False

    def threadStart(self):
        self.thread = threading.Thread(target=self.thread, args=())
        self.thread.start()

    def threadKill(self):
        self.threadStop = True

    def threadPause(self):
        self.threadMutex = False

    def threadResume(self):
        self.threadMutex = True

    # Manda os dados para transmitir
    def sendBuffer(self, data):
        self.transLen   = 0 # Zera a contagem de quantos bytes foram transmitidos
        self.buffer = data # Coloca os bytes que eu quero transmitir dentro do buffer de transmição, guarda os bytes até a thread conseguir mandar
        self.threadMutex  = True # Envia um sinal para a thread que tem dado pronto para ser transmitido, pega o conteúdo self.buffer e chama outro método para amndar os dados pela porta serial

    def getBufferLen(self):
        return(len(self.buffer))
    
    # Eu quero que ele me fale quantos bytes foram transmitidos
    def getStatus(self):
        return(self.transLen) 

    def getIsBussy(self):
        return(self.threadMutex)

