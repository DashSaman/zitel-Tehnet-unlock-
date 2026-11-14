"""Verified ZLT P19H 3.2.27 PAC codec. Offline only; never contacts a device.

Derived from five original exports and a fresh export, not a firmware loader.
PAC component integrity is an MD5 stored in a fixed trailing directory.
The config component is XOR encoded; its decoded payload is a big-endian
32-bit text length, text, optional zero byte to even length, and the one's
complement of the low 16 bits of the big-endian word sum (no carry folding).
No guarantee is made for other hardware/firmware versions.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

KEY = bytes.fromhex("78899aabbccddeef")
RECORD_SIZE = 480
MAX_RECORDS = 50
FOOTER_SIZE = 24160

def xor(data: bytes) -> bytes:
    return bytes(value ^ KEY[i % 8] for i, value in enumerate(data))

def checksum(data: bytes) -> int:
    if len(data) % 2:
        raise ValueError("Checksum input must have even length")
    return (~sum(int.from_bytes(data[i:i+2], "big") for i in range(0, len(data), 2))) & 0xFFFF

def encode_config(text: bytes) -> bytes:
    block = len(text).to_bytes(4, "big") + text
    block += b"\0" * (len(block) % 2)
    return xor(block + checksum(block).to_bytes(2, "big"))

def decode_config(data: bytes, verify: bool = True) -> bytes:
    block = xor(data)
    if len(block) < 6 or len(block) % 2:
        raise ValueError("Invalid encoded config size")
    length = int.from_bytes(block[:4], "big")
    if 4 + length + length % 2 + 2 != len(block):
        raise ValueError("Config length does not match component size")
    if block[4+length:-2] != b"\0" * (length % 2):
        raise ValueError("Nonzero config padding")
    if verify and checksum(block[:-2]) != int.from_bytes(block[-2:], "big"):
        raise ValueError("Config word checksum mismatch")
    return block[4:4+length]

def field(data: bytes, offset: int, width: int = 32) -> bytes:
    return data[offset:offset+width].split(b"\0", 1)[0]

def put_field(data: bytearray, offset: int, value: bytes, width: int = 32):
    if len(value) > width:
        raise ValueError("Metadata field overflow")
    data[offset:offset+width] = value.ljust(width, b"\0")

@dataclass
class Entry:
    name: bytes
    platform: bytes
    filename: bytes
    content: bytes

@dataclass
class Pac:
    entries: list[Entry]
    footer: bytes

    @classmethod
    def parse(cls, data: bytes, verify: bool = True):
        if len(data) < FOOTER_SIZE or field(data, len(data)-96) != str(FOOTER_SIZE).encode():
            raise ValueError("Unsupported PAC footer")
        footer = data[-FOOTER_SIZE:]
        count = int(field(footer, 0))
        if not 1 <= count <= MAX_RECORDS:
            raise ValueError("Invalid component count")
        entries = []
        next_offset = 0
        for i in range(count):
            base = 32 + i * RECORD_SIZE
            size = int(field(footer, base+96))
            offset = int(field(footer, base+128))
            if offset != next_offset or size < 0 or offset+size > len(data)-FOOTER_SIZE:
                raise ValueError("Noncontiguous or out-of-range component")
            content = data[offset:offset+size]
            if verify and hashlib.md5(content).hexdigest().encode() != field(footer, base+160, 64):
                raise ValueError("Component MD5 mismatch")
            entries.append(Entry(field(footer, base), field(footer, base+32, 64),
                                 field(footer, base+224, 224), content))
            next_offset = offset + size
        if next_offset != len(data)-FOOTER_SIZE:
            raise ValueError("Unexpected bytes before directory")
        result = cls(entries, footer)
        if verify:
            decode_config(result.config_entry().content)
        return result

    def config_entry(self):
        matches = [entry for entry in self.entries if entry.name == b"config"]
        if len(matches) != 1:
            raise ValueError("Expected one config component")
        return matches[0]

    def text(self):
        return decode_config(self.config_entry().content)

    def replace_text(self, text: bytes):
        self.config_entry().content = encode_config(text)

    def pack(self):
        footer = bytearray(self.footer)
        offset = 0
        for i, entry in enumerate(self.entries):
            base = 32 + i * RECORD_SIZE
            put_field(footer, base+96, str(len(entry.content)).encode())
            put_field(footer, base+128, str(offset).encode())
            put_field(footer, base+160, hashlib.md5(entry.content).hexdigest().encode(), 64)
            offset += len(entry.content)
        return b"".join(entry.content for entry in self.entries) + bytes(footer)

def config_values(text: bytes) -> dict[str, str]:
    pairs = re.findall(rb'^export (TZ_[A-Z0-9_]+)="([^"\r\n]*)"$', text, re.M)
    values = {k.decode(): v.decode() for k, v in pairs}
    if len(values) != len(pairs):
        raise ValueError("Duplicate configuration key")
    return values

def replace_values(text: bytes, changes: dict[str, str]) -> bytes:
    existing = config_values(text)
    if not changes.keys() <= existing.keys():
        raise ValueError("Cannot add unknown configuration keys")
    for key, value in changes.items():
        if any(c in value for c in '\r\n"`$\\'):
            raise ValueError("Only literal configuration values are allowed")
        pattern = rb'(?m)^(export ' + re.escape(key.encode()) + rb'=)"[^"\r\n]*"$'
        text, count = re.subn(pattern, lambda m: m[1] + b'"' + value.encode() + b'"', text)
        if count != 1:
            raise ValueError("Key replacement count mismatch")
    return text

if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pac", type=Path)
    args = parser.parse_args()
    data = args.pac.read_bytes()
    pac = Pac.parse(data)
    rebuilt = pac.pack()
    text = pac.text()
    pac.replace_text(text)
    assert pac.pack() == data, "Decoded-config roundtrip mismatch"
    print(json.dumps({"valid": True, "byte_exact_roundtrip": rebuilt == data,
        "text_bytes": len(text), "components": [e.name.decode() for e in pac.entries],
        "sha256": hashlib.sha256(data).hexdigest()}, indent=2))
