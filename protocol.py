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

def checksum16(data: bytes) -> int:
    return sum(data) & 0xFFFF

def pack_header(tp, file_id, seq, total_pkts, payload_len, flags, payload):
    # checksum é calculado com campo checksum=0
    hdr_wo_ck = struct.pack(">BBHHHHH", tp, file_id, seq, total_pkts, payload_len, 0, flags)
    cks = checksum16(hdr_wo_ck + payload)
    return struct.pack(">BBHHHHH", tp, file_id, seq, total_pkts, payload_len, cks, flags)

def build_packet(tp, file_id=0, seq=0, total_pkts=0, payload=b"", flags=0):
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload > 100 bytes")
    header = pack_header(tp, file_id, seq, total_pkts, len(payload), flags, payload)
    return header + payload + EOP

def parse_header(hdr: bytes):
    if len(hdr) != HEADER_SIZE:
        raise ValueError("header size")
    tp, file_id, seq, total_pkts, payload_len, cks, flags = struct.unpack(">BBHHHHH", hdr)
    return {
        "type": tp, "file_id": file_id, "seq": seq, "total_pkts": total_pkts,
        "payload_len": payload_len, "checksum": cks, "flags": flags
    }

def verify_packet(hdr: bytes, payload: bytes, eop: bytes):
    h = parse_header(hdr)
    if eop != EOP:
        return False, "bad EOP", h
    # recompute checksum with checksum field=0
    hdr_wo_ck = hdr[:8] + b"\x00\x00" + hdr[10:12]
    cks = checksum16(hdr_wo_ck + payload)
    if cks != h["checksum"]:
        return False, "bad checksum", h
    return True, "ok", h
