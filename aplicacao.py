# server.py
import os, time
from enlace import enlace
from protocol import *

# ajuste a porta do SERVIDOR
serialName = "COM7"  # exemplo Windows; use sua porta

FILES_DIR = "./server_files"  # coloque aqui os arquivos que o cliente pode baixar
TIMEOUT_ACK = 5.0
MAX_RETX = 10

def list_files():
    return [f for f in os.listdir(FILES_DIR) if os.path.isfile(os.path.join(FILES_DIR, f))]

def segment_file(path):
    data = open(path, "rb").read()
    chunks = [data[i:i+MAX_PAYLOAD] for i in range(0, len(data), MAX_PAYLOAD)]
    return chunks

def wait_bytes_with_timeout(com, needed, timeout):
    start = time.time()
    while time.time() - start < timeout:
        if com.rx.getBufferLen() >= needed:
            return com.rx.getBuffer(needed)
        time.sleep(0.02)
    return None  # timeout

def recv_packet_with_timeout(com, timeout=TIMEOUT_ACK):
    # tenta ler header
    hdr = wait_bytes_with_timeout(com, HEADER_SIZE, timeout)
    if hdr is None:
        return None, "timeout header"
    hdr = bytes(hdr)
    h = parse_header(hdr)
    # payload + eop
    rest = wait_bytes_with_timeout(com, h["payload_len"] + len(EOP), timeout)
    if rest is None:
        return None, "timeout body"
    payload = bytes(rest[:-len(EOP)])
    eop = bytes(rest[-len(EOP):])
    ok, msg, _ = verify_packet(hdr, payload, eop)
    if not ok:
        return None, msg
    return (h, payload), "ok"

def main():
    print("-----------------------------------------------------------------------------------")
    print("┹┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ ▭ ▬▬▬▬▬▬▟ ✩ ▙▬▬▬▬▬▬ ▭ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┲")
    print("┹┄┄┄┄┄┄┄┄┄┄┄┄┄┄ ▭ Tranferência de Arquivos entre Client e Servidor ▭ ┄┄┄┄┄┄┄┄┄┄┄┄┄┲")
    print("-----------------------------------------------------------------------------------\n")


    print("SERVIDOR: abrindo porta", serialName)
    com = enlace(serialName)   # usa sua camada de enlace
    com.enable()               # abre porta + inicia threads RX/TX
    print("SERVIDOR: pronto")

    # --------------------------
    # Byte de sacrifício (mantido)
    # --------------------------
    print("SERVIDOR: esperando 1 byte de sacrifício...")
    try:
        rxBuffer, nRx = com.getData(1)
    except Exception:
        # se der erro aqui, seguimos mesmo assim
        pass
    com.rx.clearBuffer()
    time.sleep(.1)
    print("SERVIDOR: byte de sacrifício recebido e descartado.")
    # --------------------------

    selected = []           # [(file_id, filename, chunks, next_seq)]
    id_map = {}             # filename -> file_id (para confirmar ao cliente)

    try:
        # 1) HELLO -> FILE_LIST
        pkt, reason = recv_packet_with_timeout(com, timeout=10)
        if not pkt or pkt[0]["type"] != T_HELLO:
            print("SERVIDOR: esperando HELLO, motivo:", reason)
            return

        names = list_files()
        payload = ("|".join(names)).encode()
        com.sendData(build_packet(T_FILELIST, payload=payload))

        # 2) Receber N x FILE_REQ ... responder FILE_OK com FILE_ID crescente
        print("SERVIDOR: esperando seleção de arquivo(s)...")
        next_id = 1
        i = 0 
        print("-----------------------------------------------------------------------------------")

        while True:
            # if i==0: 
            #     print("SERVIDOR: arquivos escolhidos")
            #     i+=1
            pkt, _ = recv_packet_with_timeout(com, timeout=30)
            if not pkt:
                print("SERVIDOR: timeout esperando seleção")
                return
            h, payload = pkt
            if h["type"] == T_FILEREQ:
                filename = payload.decode()
                if filename not in names:
                    # manda END com erro simples
                    com.sendData(build_packet(T_END, payload=b"file not found"))
                    return
                file_id = next_id
                next_id += 1
                id_map[filename] = file_id
                chunks = segment_file(os.path.join(FILES_DIR, filename))
                selected.append([file_id, filename, chunks, 0])  # next_seq=0
                total = len(chunks)
                com.sendData(build_packet(T_FILEOK, file_id=file_id, total_pkts=total, payload=filename.encode()))
                print(f"SERVIDOR: arquivo '{filename}' selecionado, id={file_id}, {total} pacotes.")
            elif h["type"] == T_START:
                com.sendData(build_packet(T_END, payload=b"starting"))
                time.sleep(0.5)
                break
        print("-----------------------------------------------------------------------------------")


        

        # 3) Loop de transmissão alternada com ACK
        paused = False
        done = set()

        while len(done) < len(selected):

            while paused:
                pkt, _ = recv_packet_with_timeout(com, timeout=0.5)
                if pkt:
                    hh, pl = pkt
                    if hh["type"] == T_RESUME:
                        paused = False
                        #print("SERVIDOR: RESUME")
                        #print("SERVIDOR: Botão de Pause apertado pelo Client: ▌▌ Pause1" )
                        print("SERVIDOR: Botão de Resume apertado pelo Client: ▶ Resume " )

                    elif hh["type"] == T_ABORT:
                        print("SERVIDOR: Botão de Abort apertado pelo Client: ( ͡° ͜ʖ ͡°) Abort" )
                        com.sendData(build_packet(T_END, payload=b"aborted by client"))
                        return
                    # PAUSE repetido ou outros tipos são ignorados aqui

            for i, (fid, fname, chunks, seq) in enumerate(selected):
                if fid in done:
                    continue

                # Verifica pausa antes de enviar este pacote
                if paused:
                    break  # volta ao while externo para tratar o loop de pausa

                # prepara pacote DATA
                payload = chunks[seq]
                flags = FLAG_LAST if (seq == len(chunks)-1) else 0
                pkt_bytes = build_packet(
                    T_DATA,
                    file_id=fid,
                    seq=seq,
                    total_pkts=len(chunks),
                    payload=payload,
                    flags=flags
                )
                com.sendData(pkt_bytes)

                # espera ACK desse pacote, com timeout e retransmissão
                retx = 0
                ack_ok = False
                while retx <= MAX_RETX and not ack_ok:
                    resp, why = recv_packet_with_timeout(com, timeout=TIMEOUT_ACK)
                    if resp:
                        hh, pl = resp

                        # ACK esperado
                        if hh["type"] == T_ACK and hh["file_id"] == fid and hh["seq"] == seq:
                            ack_ok = True
                            break

                        # Comandos de controle durante a espera
                        if hh["type"] == T_PAUSE:
                            paused = True
                            print("SERVIDOR: Botão de Pause apertado pelo Client: ▌▌ Pause" )
                            # mesmo pausado, ainda precisamos terminar este ciclo de ACK;
                            # o próximo envio só ocorrerá após sair do modo pausa lá em cima
                        elif hh["type"] == T_RESUME:
                            paused = False
                            print("SERVIDOR: Botão de Resume apertado pelo Client: ► Resume " )
                        elif hh["type"] == T_ABORT:
                            print("SERVIDOR: Botão de Abort apertado pelo Client: ( ͡° ͜ʖ ͡°) Abort " )
                            com.sendData(build_packet(T_END, payload=b"aborted by client"))
                            return
                        # Outros tipos recebidos aqui são ignorados
                    else:
                        # timeout -> retransmite o mesmo pacote
                        retx += 1
                        com.sendData(pkt_bytes)

                if not ack_ok:
                    com.sendData(build_packet(T_END, payload=b"too many timeouts"))
                    print("SERVIDOR: encerrando por excesso de timeouts aguardando ACK.")
                    return

                # avançar seq / marcar done
                seq += 1
                selected[i][3] = seq
                if seq == len(chunks):
                    done.add(fid)

        # 4) Finaliza
        com.sendData(build_packet(T_END, payload=b"done"))
        print("-----------------------------------------------------------------------------------")
        print("SERVIDOR: transmissão concluída.")
        print("-----------------------------------------------------------------------------------")

    finally:
        com.disable()  # encerra threads e fecha porta

if __name__ == "__main__":
    main()
