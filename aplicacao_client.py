# client.py
import sys 
import os, time
from enlace import enlace
from protocol import *
from datetime import datetime

# ajuste a porta do CLIENTE
serialName = "COM9"  

LOG_FILE = "client_log.txt"
DOWNLOAD_DIR = "./client_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

TIMEOUT = 5.0

def log_event(sent_recv, h, payload=b"", error_msg=None):
    """
    sent_recv: 'envio' ou 'receb'
    h: dicionário do cabeçalho (parse_header)
    payload: bytes do payload
    """
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]
        if error_msg:
            tipo = "ERRO"
            tam = "-"
            linha = f"{ts} / {sent_recv} / {tipo} / {tam} / {error_msg}"
        else:
            tipo = h["type"]
            tam = h["payload_len"] + HEADER_SIZE + len(EOP)
        
            linha = f"{ts} / {sent_recv} / {tipo} / {tam}"

            # Se for DATA, incluir extras
            if tipo == T_DATA:
                crc = checksum16(payload)
                linha += f" / {h['seq']} / {h['total_pkts']} / {crc:04X}"
        
        f.write(linha + "\n")

#espera até chegar uma quantidade no buffer, se passo um tempo e não chegou, retorna None
def wait_bytes_with_timeout(com, needed, timeout):
    start = time.time()
    while time.time() - start < timeout:
        if com.rx.getBufferLen() >= needed:
            return com.rx.getBuffer(needed)
        time.sleep(0.02)
    return None

#tenta ler o header primeiro, depois le o corpo, verifica integridade, se tiver ok retorna e se falhar retorna None
def recv_packet_with_timeout(com, timeout=TIMEOUT):
    hdr = wait_bytes_with_timeout(com, HEADER_SIZE, timeout)
    if hdr is None: 
        return None, "timeout header"
    hdr = bytes(hdr)
    h = parse_header(hdr)
    rest = wait_bytes_with_timeout(com, h["payload_len"] + len(EOP), timeout)
    if rest is None:
        return None, "timeout body"
    payload = bytes(rest[:-len(EOP)])
    eop = bytes(rest[-len(EOP):])
    ok, msg, _ = verify_packet(hdr, payload, eop)
    if ok:
        log_event("receb", h, payload)
    if not ok:
        log_event("receb", error_msg=msg)
        return None, msg
    return (h, payload), "ok"

#envia um pacote e espera os pacotes do servidor, só retorna quando chega um pacote
def send_and_wait(com, pkt, expect_types, timeout=TIMEOUT):
    com.sendData(pkt)
    hdr = parse_header(pkt[:HEADER_SIZE])
    payload = pkt[HEADER_SIZE:-len(EOP)] if len(pkt) > HEADER_SIZE + len(EOP) else b""
    log_event("envio", hdr, payload)
    start = time.time()
    while True:
        remaining = max(0.1, timeout - (time.time() - start))
        resp, why = recv_packet_with_timeout(com, timeout)
        if not resp:
            return None, why
        h, pl = resp
        if h["type"] in expect_types:
            return (h, pl), "ok"

def print_progress_bar(filename, received, total, length=40):
        percent = received/total
        filled = int(length*percent)
        bar = "█" * filled + "-" * (length - filled)
        sys.stdout.write(f"\rArquivo {filename}: |{bar}| {percent:.0%} ({received}/{total} pacotes)")
        sys.stdout.flush()
        if received == total:
            print()
def main():

    #ERRO CRC###############################################
    erro_crc_proposital = True 
    crc_enviado = False
    #######################################

    print("-----------------------------------------------------------------------------------")
    print("┹┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ ▭ ▬▬▬▬▬▬▟ ✩ ▙▬▬▬▬▬▬ ▭ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┲")
    print("┹┄┄┄┄┄┄┄┄┄┄┄┄┄┄ ▭ Tranferência de Arquivos entre Client e Servidor ▭ ┄┄┄┄┄┄┄┄┄┄┄┄┄┲")
    print("-----------------------------------------------------------------------------------\n")
    print("CLIENTE: abrindo porta", serialName)
    com = enlace(serialName)
    com.enable()
    print("CLIENTE: pronto")

    time.sleep(.2)
    com.sendData(b'00')
    time.sleep(1)
    print("Byte de sacrifício enviado.")

    try:
        #handshake inicial, cliente envia hello, servidor responde com a lista de arquivos disponíveis
        (h, pl), _ = send_and_wait(com, build_packet(T_HELLO), expect_types=[T_FILELIST], timeout=10)
        files = pl.decode().split("|") if pl else []
        print("\nArquivos disponíveis no servidor:")
        for i, name in enumerate(files, 1):
            print(f"  {i}. {name}")

        #seleção dos arquivos
        wanted = []
        while True:
            sel = input("Digite o nome do arquivo a adicionar (ou ENTER para finalizar): ").strip()
            if not sel:
                break
            if sel not in files:
                print("Nome inválido.")
                continue
            wanted.append(sel)
        if len(wanted) < 2:
            print("Selecione pelo menos 2 arquivos.")
            return

        #requisição dos arquivos 
        id_to_name = {}
        for idx, name in enumerate(wanted, start=1):
            (hh, ppl), _ = send_and_wait(
                com, build_packet(T_FILEREQ, payload=name.encode()),
                expect_types=[T_FILEOK], timeout=10
            )
            fid = hh["file_id"]
            id_to_name[fid] = name
            print(f"Servidor confirmou {name} com FILE_ID={fid} (total_pkts={hh['total_pkts']})")

        #transferência dos arquivos, cliente manda start e servidor confirma que vai começar com end no início da mensagem
        resp, why = send_and_wait(com, build_packet(T_START), expect_types=[T_END], timeout=10)
        if not resp:
            print("CLIENTE: falha ao iniciar download:", why)
            return
        (h_end, pl_end) = resp
        print("-----------------------------------------------------------------------------------")
        print("Servidor:", pl_end.decode(errors="ignore"))

        # pequena pausa para garantir que o servidor não dispare DATA antes do cliente estar pronto
        time.sleep(0.5)


        # cria buffers para armazenar os bytes de cada arquivo, para cada pacote DATA, extrai o id, acrescenta o payload, atualiza a barra, responde com ACK, se flag_last estiver ativa, arquivo acabpou
        buffers = {fid: bytearray() for fid in id_to_name}
        pkts_count = {fid: 0 for fid in id_to_name}
        finished = set()

        last_sent = {}  # guarda último pacote enviado (ACK ou DATA)

        print("\nBaixando... (P=pausa, R=resume, Q=abort)")
        print("-----------------------------------------------------------------------------------")
        import threading, sys

        ctrl = {"paused": False, "aborted": False}
        def key_thread():
            while True:
                k = sys.stdin.readline().strip().lower()
                if k == "p":
                    com.sendData(build_packet(T_PAUSE))
                    ctrl["paused"] = True
                    print("CLIENTE: PAUSE enviado")
                    print("-----------------------------------------------------------------------------------")
                elif k == "r":
                    com.sendData(build_packet(T_RESUME))
                    ctrl["paused"] = False
                    print("CLIENTE: RESUME enviado")
                    print("-----------------------------------------------------------------------------------")
                elif k == "q":
                    com.sendData(build_packet(T_ABORT))
                    ctrl["aborted"] = True
                    print("CLIENTE: ABORT enviado")
                    print("-----------------------------------------------------------------------------------")
                    break
        threading.Thread(target=key_thread, daemon=True).start()


        #ERRO DE PACOTE 
        erro_proposital = True  # ativa ou desativa erro proposital
        erro_enviado = False    # controla se o erro já ocorreu

        while len(finished) < len(buffers) and not ctrl["aborted"]:
            pkt, why = recv_packet_with_timeout(com, timeout=10)
            if not pkt:
                print("CLIENTE: timeout esperando DATA -> continuo aguardando...", why)
                continue
            h, payload = pkt
            if h["type"] == T_DATA:
                fid, seq = h["file_id"], h["seq"]

                # === ERRO PROPOSITAL PULAR PACOTE ==============
                if erro_proposital and not erro_enviado:
                    # Exemplo: pular o pacote 2
                    if seq == 2:
                        print(f"Erro proposital: pacote {seq}")
                        log_event("receb", h, payload)  # loga tentativa
                        erro_enviado = True
                        continue  # pacote não é processado nem ACK enviado
                # =============================

                # ERRO CRC por exemplo seq == 3 ##############################################
                if erro_crc_proposital and not crc_enviado and seq == 3:
                    pkt = build_packet(T_DATA, file_id=fid, seq=seq, payload=payload)
                    pkt_corrompido = pkt[:10] + b"\x00\x00" + pkt[12:]  # checksum errado
                    com.sendData(pkt_corrompido)
                    log_event("envio", parse_header(pkt_corrompido[:HEADER_SIZE]), pkt_corrompido[HEADER_SIZE:-len(EOP)])
                    print(f"Erro proposital: pacote seq {seq} enviado com CRC errado")
                    crc_enviado = True
                    continue  # não processa payload nem envia ACK
                #############################################################################
                
                # (cheque duplicados, se quiser, pelo seq)
                buffers[fid].extend(payload)
                pkts_count[fid] += 1
                # Atualiza barra de progresso
                print_progress_bar(id_to_name[fid], pkts_count[fid], h["total_pkts"])
                # ACK
                ack_pkt = build_packet(T_ACK, file_id=fid, seq=seq, payload=b"OK")
                com.sendData(ack_pkt)
                last_sent[(fid, seq)] = ack_pkt
                if (h["flags"] & FLAG_LAST) != 0:
                    finished.add(fid)
                    print(f"CLIENTE: arquivo {id_to_name[fid]} finalizado ({pkts_count[fid]} pacotes)")
                    print("-----------------------------------------------------------------------------------")
            elif h["type"] == T_END:
                # servidor pode avisar erro/encerramento
                print("-----------------------------------------------------------------------------------")
                print("Servidor:", payload.decode(errors="ignore"))
                if payload != b"done":
                    break
                    ...
            elif h["type"] == T_ACK:
                if payload == b"CRC_ERROR":
                    fid, seq = h["file_id"], h["seq"]
                    print(f"CLIENTE: servidor pediu retransmissão -> file_id={fid}, seq={seq}")
                if (fid, seq) in last_sent:
                    com.sendData(last_sent[(fid, seq)])
                    print(f"CLIENTE: pacote {seq} reenviado")

        #salva arquivo 
        print("-----------------------------------------------------------------------------------")
        print("\nResumo:")
        total_bytes = 0
        for fid, name in id_to_name.items():
            path = os.path.join(DOWNLOAD_DIR, name)
            with open(path, "wb") as f:
                f.write(buffers[fid])
            print(f"- {name}: {len(buffers[fid])} bytes, {pkts_count[fid]} pacotes")
            total_bytes += len(buffers[fid])
        print(f"TOTAL: {total_bytes} bytes")

    finally:
        com.disable()
    

if __name__ == "__main__":
    main()
