# protocol.py
import struct

EOP = b"\xAA\xBB\xCC\xDD" #indica o final do pacote
HEADER_SIZE = 12 #o cabeçalho tem 12 bytes
MAX_PAYLOAD = 100 #tamanho máximo dos dados que podem ser enviados em pacote

# TIPOS
#permite que o receptor saiba a finalidade do pacote
#representa o tipo de mensagem
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

FLAG_LAST = 1  #ultimo pacote de uma sequência

#detecta erros de transmissão, soma todos os bytes do pacote e se algum foi alterado durante a transmissão,a soma final não irá corresponder ao valor inicial
def checksum16(data: bytes) -> int:
    return sum(data) & 0xFFFF

#cria o cabeçalho do pacote
#recebe todas as informações necessárias e empacota em um cabeçalho
def pack_header(tp, file_id, seq, total_pkts, payload_len, flags, payload):
    # checksum é calculado com campo checksum=0
    # ceda letra represeta um campo do cabeçalho
    hdr_wo_ck = struct.pack(">BBHHHHH", tp, file_id, seq, total_pkts, payload_len, 0, flags)
    cks = checksum16(hdr_wo_ck + payload) #check sum é calculado antes, por isso ele é 0 temporariamente, pois ele não deve fazer parte do cálculo
    return struct.pack(">BBHHHHH", tp, file_id, seq, total_pkts, payload_len, cks, flags)

#monstar o pacote completo, recebe o tipo do pacote e os dados(payload) e chama a função pck_header para criar o cabeçalho, concatena o cabeçalho e dados e o EOP
def build_packet(tp, file_id=0, seq=0, total_pkts=0, payload=b"", flags=0):
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload > 100 bytes")
    header = pack_header(tp, file_id, seq, total_pkts, len(payload), flags, payload)
    return header + payload + EOP

#interpreta os bytes do cabeçalho e desempacota em um dicionário
def parse_header(hdr: bytes):
    if len(hdr) != HEADER_SIZE:
        raise ValueError("header size")
    tp, file_id, seq, total_pkts, payload_len, cks, flags = struct.unpack(">BBHHHHH", hdr)#extrair os valores do cabeçalho inário, o dicionário facilita o acesso a cada campo
    return {
        "type": tp, "file_id": file_id, "seq": seq, "total_pkts": total_pkts,
        "payload_len": payload_len, "checksum": cks, "flags": flags
    }

#verifica se o pacote é recebido sem erros
def verify_packet(hdr: bytes, payload: bytes, eop: bytes):
    h = parse_header(hdr)
    if eop != EOP: #checa a sequência final de bytes, se corresponde ao EOP
        return False, "bad EOP", h
    # recompute checksum with checksum field=0
    hdr_wo_ck = hdr[:8] + b"\x00\x00" + hdr[10:12] #recalcula o checksun do pacote e compara com o valor que veio no cabeçalho original
    cks = checksum16(hdr_wo_ck + payload)
    if cks != h["checksum"]:
        return False, "bad checksum", h
    return True, "ok", h
