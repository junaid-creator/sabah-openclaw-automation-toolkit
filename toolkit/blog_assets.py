"""Bounded same-byte WebP validation; no generation/upload capability."""
import hashlib,io
from pathlib import Path
from PIL import Image
MAX_WEBP_BYTES=20*1024*1024

def validate_webp_structure(data):
    """Validate bounded RIFF/WebP framing; this is not a full image decode."""
    if not isinstance(data, bytes) or len(data) < 20 or len(data) > MAX_WEBP_BYTES:
        raise ValueError('Invalid WebP size')
    if data[:4] != b'RIFF' or data[8:12] != b'WEBP' or int.from_bytes(data[4:8], 'little') + 8 != len(data):
        raise ValueError('Invalid WebP container')
    pos=12; image=False
    while pos < len(data):
        if pos + 8 > len(data): raise ValueError('Truncated WebP chunk header')
        kind=data[pos:pos+4]; size=int.from_bytes(data[pos+4:pos+8], 'little')
        start=pos+8; end=start+size; next_pos=end+(size & 1)
        if next_pos > len(data): raise ValueError('Truncated WebP chunk')
        payload=data[start:end]
        if kind == b'VP8 ':
            if size < 10 or payload[3:6] != b'\x9d\x01\x2a': raise ValueError('Invalid VP8 frame header')
            image=True
        elif kind == b'VP8L':
            if size < 5 or payload[:1] != b'\x2f': raise ValueError('Invalid VP8L frame header')
            image=True
        elif kind == b'ANMF':
            raise ValueError('Animated WebP not supported for blog assets')
        pos=next_pos
    if pos != len(data) or not image: raise ValueError('WebP image frame missing')
    return True

def read_upload_image(image, *, asset_root):
    """Bind the actual upload bytes to the validated plan and decode them again."""
    path = Path(image['path']).resolve()
    if not path.is_relative_to(Path(asset_root).resolve()):
        raise ValueError('Image must belong to blog asset directory')
    with path.open('rb') as file:
        data = file.read(MAX_WEBP_BYTES + 1)
    validate_webp_decode(data)
    if hashlib.sha256(data).hexdigest() != image['sha256']:
        raise ValueError('Image changed since validation')
    return data

def validate_webp_decode(data):
    validate_webp_structure(data)
    with Image.open(io.BytesIO(data)) as image:
        if image.format!='WEBP' or image.width*image.height>20_000_000 or getattr(image,'is_animated',False): raise ValueError('Bounded still WebP required')
        image.load()
    return True
