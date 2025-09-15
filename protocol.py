# protocol.py
import struct

EOP = b"\xAA\xBB\xCC\xDD"
HEADER_SIZE = 12
MAX_PAYLOAD = 100

# TIPOS
T_HELLO    = 0
T_FILELIST = 1
T_FILEREQ  = 2
T_FILEOK   = 3
T_START    = 4
T_DATA     = 5
T_ACK      = 6
T_PAUSE    = 7
T_RESUME   = 8
T_ABORT    = 9
T_END      = 10

FLAG_LAST = 1  # bit0


# Faz a soma e poe em formato de 16 bits
def checksum16(data: bytes) -> int:
    return sum(data) & 0xFFFF


def pack_header(tp, file_id, seq, total_pkts, payload_len, flags, payload):
    # checksum é calculado com campo checksum=0 p n afetar
    #  hdr_wo_ck significa header without checksum é o header sem o checksum 
    # !!! SEM STRUCT: hdr_wo_ck = [tipo, seq, len(payload), 0] e dps pacote = bytes(hdr_wo_ck) + payload

    hdr_wo_ck = struct.pack(">BBHHHHH", tp, file_id, seq, total_pkts, payload_len, 0, flags)
    cks = checksum16(hdr_wo_ck + payload)
    return struct.pack(">BBHHHHH", tp, file_id, seq, total_pkts, payload_len, cks, flags)

def build_packet(tp, file_id=0, seq=0, total_pkts=0, payload=b"", flags=0):
    # Se payload (dados) for maior que 100 bytes lança o errrrooo
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload > 100 bytes")
    # cria header 
    # ? Oq é tp,file_id e etc ?
    header = pack_header(tp, file_id, seq, total_pkts, len(payload), flags, payload)
    # Devolve Pacote com 3 partes 
    return header + payload + EOP



# Recebe o header e decodifica cada campo para variveis do pythonnn
# Lê o header e devolve um dicionário com os campos
def parse_header(hdr: bytes):
    if len(hdr) != HEADER_SIZE:
        raise ValueError("header size")
    tp, file_id, seq, total_pkts, payload_len, cks, flags = struct.unpack(">BBHHHHH", hdr)
    return {
        "type": tp, "file_id": file_id, "seq": seq, "total_pkts": total_pkts,
        "payload_len": payload_len, "checksum": cks, "flags": flags
    }


# Verifica se o pacote está correto (EOP, checksum)
def verify_packet(hdr: bytes, payload: bytes, eop: bytes):
    # h é o header em formato dicionário
    h = parse_header(hdr)
    # verifica se o END of PACKET (EOF) tá certo
    if eop != EOP:
        return False, "bad EOP", h
    # recria header com checksum=0
    hdr_wo_ck = hdr[:8] + b"\x00\x00" + hdr[10:12]
    cks = checksum16(hdr_wo_ck + payload)
    if cks != h["checksum"]:
        return False, "bad checksum", h
    return True, "ok", h
