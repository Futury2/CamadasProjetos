# protocol.py
import struct
import crcmod

#3 partes fixas
#Header - 12 bytes
#payload - 100 bytes - parte real do arqui sendo transferido 
#EOP - 4 bites - indica que o pacote terinou, 4bytes fixos 
#Total = 116 bytes

#HEADER
# tipo do pacotes 1
# id do arquivo 1
# numero de sequencia do pacotes 2
# numero total de pacotes do arquivo 2
# quantos bytes de payload esse pacote carrega 2
# verificação de integridade(ckecksun) 2
# flag_last para marcar o ultimo pacote 2


EOP = b"\xAA\xBB\xCC\xDD" #indica o final do pacote
HEADER_SIZE = 12 #o cabeçalho tem 12 bytes
MAX_PAYLOAD = 100 #tamanho máximo dos dados que podem ser enviados em pacote

# TIPOS
#permite que o receptor saiba a finalidade do pacote
#representa o tipo de mensagem
#HANDSHAKE, sequencis de bytes iniciais entre client e servidor antes da transmissão dos arquivos
T_HELLO    = 0 #cliente  pergunta se o servidor ta ativo
T_FILELIST = 1 #servidor resonde com a lista de arquivo
T_FILEREQ  = 2 #cliente pede o arquivo, manda o nome no payload
T_FILEOK   = 3 #servidor confirma e envia o id e o total de pacotes
T_START    = 4 #cliente sinaliza que terminou a escolha e está pronto para dowload
T_DATA     = 5 #intercala os pacotes, envia um pacote do arquivo A, outro do B
T_ACK      = 6 #cliente responde cada pacote com T_ACK, confirmação, recebi o pacote x fo arquivo y corretamente
T_PAUSE    = 7 
T_RESUME   = 8
T_ABORT    = 9
T_END      = 10 #servidor responde que vai iniciar a transmisão

FLAG_LAST = 1  #ultimo pacote de uma sequência

_crc16 = crcmod.mkCrcFun(0x11021, initCrc=0xFFFF, rev=False, xorOut=0x0000)
def checksum16(data: bytes) -> int:
    return _crc16(data) & 0xFFFF

#cria o cabeçalho do pacote
#recebe todas as informações necessárias e empacota em um cabeçalho
def pack_header(tp, file_id, seq, total_pkts, payload_len, flags, payload):
    # checksum é calculado com campo checksum=0
    # ceda letra represeta um campo do cabeçalho
    cks = checksum16(payload) #check sum é calculado antes, por isso ele é 0 temporariamente, pois ele não deve fazer parte do cálculo
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
    cks = checksum16(payload)
    if cks != h["checksum"]:
        return False, "bad checksum", h
    return True, "ok", h
