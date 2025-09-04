# client.py
import os, time
from enlace import enlace
from protocol import *

# ajuste a porta do CLIENTE
serialName = "COM12"  # troque pela sua

DOWNLOAD_DIR = "./client_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

TIMEOUT = 5.0

def wait_bytes_with_timeout(com, needed, timeout):
    start = time.time()
    while time.time() - start < timeout:
        if com.rx.getBufferLen() >= needed:
            return com.rx.getBuffer(needed)
        time.sleep(0.02)
    return None

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
    if not ok:
        return None, msg
    return (h, payload), "ok"

def send_and_wait(com, pkt, expect_types, timeout=TIMEOUT):
    com.sendData(pkt)
    while True:
        resp, why = recv_packet_with_timeout(com, timeout)
        if not resp:
            return None, why
        h, pl = resp
        if h["type"] in expect_types:
            return (h, pl), "ok"

def main():
    print("CLIENTE: abrindo porta", serialName)
    com = enlace(serialName)
    com.enable()
    print("CLIENTE: pronto")

    time.sleep(.2)
    com.sendData(b'00')
    time.sleep(1)
    print("Byte de sacrifício enviado.")

    try:
        # 1) HELLO -> FILE_LIST
        (h, pl), _ = send_and_wait(com, build_packet(T_HELLO), expect_types=[T_FILELIST], timeout=10)
        files = pl.decode().split("|") if pl else []
        print("\nArquivos disponíveis no servidor:")
        for i, name in enumerate(files, 1):
            print(f"  {i}. {name}")

        # 2) seleção de >=2 arquivos
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

        # manda N x FILE_REQ e guarda FILE_IDs
        id_to_name = {}
        for idx, name in enumerate(wanted, start=1):
            (hh, ppl), _ = send_and_wait(
                com, build_packet(T_FILEREQ, payload=name.encode()),
                expect_types=[T_FILEOK], timeout=10
            )
            fid = hh["file_id"]
            id_to_name[fid] = name
            print(f"Servidor confirmou {name} com FILE_ID={fid} (total_pkts={hh['total_pkts']})")

        # sinaliza START
        resp, why = send_and_wait(com, build_packet(T_START), expect_types=[T_END], timeout=10)
        if not resp:
            print("CLIENTE: falha ao iniciar download:", why)
            return
        (h_end, pl_end) = resp
        print("Servidor:", pl_end.decode(errors="ignore"))

        # pequena pausa para garantir que o servidor não dispare DATA antes do cliente estar pronto
        time.sleep(0.5)


        # 3) recebimento: grava por FILE_ID, envia ACK por pacote
        buffers = {fid: bytearray() for fid in id_to_name}
        pkts_count = {fid: 0 for fid in id_to_name}
        finished = set()

        print("\nBaixando... (P=pausa, R=resume, Q=abort)")
        import threading, sys

        ctrl = {"paused": False, "aborted": False}
        def key_thread():
            while True:
                k = sys.stdin.readline().strip().lower()
                if k == "p":
                    com.sendData(build_packet(T_PAUSE))
                    ctrl["paused"] = True
                    print("[CLIENTE] PAUSE enviado")
                elif k == "r":
                    com.sendData(build_packet(T_RESUME))
                    ctrl["paused"] = False
                    print("[CLIENTE] RESUME enviado")
                elif k == "q":
                    com.sendData(build_packet(T_ABORT))
                    ctrl["aborted"] = True
                    print("[CLIENTE] ABORT enviado")
                    break
        threading.Thread(target=key_thread, daemon=True).start()

        while len(finished) < len(buffers) and not ctrl["aborted"]:
            pkt, why = recv_packet_with_timeout(com, timeout=10)
            if not pkt:
                print("CLIENTE: timeout esperando DATA -> continuo aguardando...", why)
                continue
            h, payload = pkt
            if h["type"] == T_DATA:
                fid, seq = h["file_id"], h["seq"]
                # (cheque duplicados, se quiser, pelo seq)
                buffers[fid].extend(payload)
                pkts_count[fid] += 1
                # ACK
                com.sendData(build_packet(T_ACK, file_id=fid, seq=seq))
                if (h["flags"] & FLAG_LAST) != 0:
                    finished.add(fid)
                    print(f"CLIENTE: arquivo {id_to_name[fid]} finalizado ({pkts_count[fid]} pacotes)")
            elif h["type"] == T_END:
                # servidor pode avisar erro/encerramento
                print("Servidor:", payload.decode(errors="ignore"))
                if payload != b"done":
                    break

        # 4) salvar arquivos e resumo
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
