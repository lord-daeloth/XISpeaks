"""FFXI wire format and dialogue cleanup. No game or speech dependencies."""
from dataclasses import dataclass
import re
import unicodedata

MAX_DATAGRAM = 12000


@dataclass(frozen=True)
class Message:
    command: str
    identity: str
    mode: int
    raw: bytes


@dataclass(frozen=True)
class Dialogue:
    speaker: str
    text: str


def parse_frame(data: bytes) -> Message:
    if len(data) > MAX_DATAGRAM:
        raise ValueError('Oversized frame')
    header, separator, raw = data.partition(b'\n')
    if not separator or len(header) > 160:
        raise ValueError('Missing or oversized header')
    parts = header.decode('ascii').split('\t')
    if len(parts) != 4 or parts[0] != 'XIS1':
        raise ValueError('Unknown protocol')
    _, command, identity, mode = parts
    if command not in {'speak', 'stop', 'ping'} or not re.fullmatch(r'[\w-]{1,80}', identity):
        raise ValueError('Invalid command or identity')
    mode = int(mode)
    if command == 'speak' and mode not in {150, 151}:
        raise ValueError('Not an NPC/narration channel')
    if command != 'speak' and (raw or mode != 0):
        raise ValueError('Invalid control frame')
    return Message(command, identity, mode, raw)


def clean_dialogue(raw: bytes) -> Dialogue | None:
    # FFXI-specific glyphs must be replaced before CP932 decoding. In
    # particular EF 1F is an element glyph, not a color-control sequence.
    elements = ('Fire', 'Ice', 'Wind', 'Earth', 'Lightning', 'Water', 'Light', 'Dark')
    for code, name in enumerate(elements, 0x1F):
        raw = raw.replace(bytes((0xEF, code)), f' {name} '.encode('ascii'))
    for source, replacement in {
        b'\x81\x40': b' ', b'\x81\xf4': b' ', b'\x81\x99': b' ',
        b'\x81\x9a': b' ', b'\x81\x60': b'~',
        b'\x87\xb2': b'"', b'\x87\xb3': b'"',
    }.items():
        raw = raw.replace(source, replacement)
    # Preserve the game's custom accented e, which is not CP932's mapping.
    chunks = raw.split(b'\x88\x69')
    decoded = []
    for chunk in chunks:
        chunk = re.sub(rb'\x7f[1-7][\x01-\x06]?', b'', chunk)
        chunk = re.sub(rb'[\x1e\x1f].', b'', chunk, flags=re.DOTALL)
        chunk = chunk.replace(b'\x07', b' ')
        chunk = re.sub(rb'[\x00-\x1f\x7f]', b'', chunk)
        decoded.append(chunk.decode('cp932', errors='replace'))
    text = unicodedata.normalize('NFKC', 'é'.join(decoded))
    text = ' '.join(text.replace('\ufffd', ' ').split())
    speaker = ''
    match = re.match(r'^(.{1,48}?)\s+:\s+(.*)$', text)
    if match:
        speaker, text = match[1].strip(), match[2].strip()
    if not any(c.isalnum() for c in text):
        return None
    return Dialogue(speaker, text)
