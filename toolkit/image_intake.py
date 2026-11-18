"""Durable supplied-image intake; no uploads, generation or publication.

Source-derived from the original image importer. Call only after the host has
verified the owner and attachment association; filesystem eligibility is NOT
identity verification. CLI use is a trusted local operator action.
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit
import warnings
from PIL import Image

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
FORMATS = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _trusted(path, directory=False):
    path = Path(path).absolute()
    if path != path.resolve(strict=True):
        raise ValueError('Symlink or traversal path rejected')
    info = path.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError('Runtime-owned, non-writable-by-others path required')
    if directory and not stat.S_ISDIR(info.st_mode):
        raise ValueError('Directory required')
    return path


def read_attachment(source, roots, max_bytes=MAX_BYTES):
    """Walk from an explicitly trusted root using no-follow directory FDs."""
    source = Path(source).absolute()
    if '..' in source.parts:
        raise ValueError('Traversal rejected')
    candidates = [_trusted(p, directory=True) for p in roots]
    root = next((p for p in candidates if source.is_relative_to(p)), None)
    if root is None or source == root:
        raise ValueError('Attachment outside configured roots')
    parts = source.relative_to(root).parts
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
            info = os.fstat(fd)
            if info.st_uid != os.geteuid() or info.st_mode & 0o022:
                raise ValueError('Unsafe attachment directory')
        incoming = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(incoming, 'rb') as handle:
            before = os.fstat(handle.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or before.st_mode & 0o022 or not 0 < before.st_size <= max_bytes):
                raise ValueError('Unsafe attachment type, owner, mode or size')
            raw = handle.read(max_bytes+1)
            after = os.fstat(handle.fileno())
            if (len(raw) != before.st_size or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns):
                raise ValueError('Attachment changed during read')
            return raw
    finally:
        os.close(fd)


def _decode(raw):
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Image size outside limit')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            if (image.format not in FORMATS or min(width, height) < 320
                    or width * height > MAX_PIXELS or getattr(image, 'n_frames', 1) != 1):
                raise ValueError('Unsupported image format, dimensions or animation')
            mime = FORMATS[image.format]
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            return image.copy(), mime


def _jpeg(image):
    # Preserve the original separately. Flatten transparency; no cropping.
    rgba = image.convert('RGBA')
    rgb = Image.new('RGB', image.size, 'white')
    rgb.paste(rgba, mask=rgba.getchannel('A'))
    out = io.BytesIO()
    rgb.save(out, format='JPEG', quality=92)
    return out.getvalue()


def _exclusive(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def _lock(root, request_id):
    import fcntl
    path = root / ('.' + request_id + '.lock')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Unsafe intake lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def recover(folder, *, expected_sha256=None):
    """Validate persisted import proof and ALL output hashes; never regenerate."""
    folder = _trusted(folder, directory=True)
    record = json.loads(read_attachment(folder/'receipt.json', [folder], 100_000))
    if (record.get('schema') != 1 or record.get('published') is not False
            or set(record.get('files', {})) != {'original', 'preview.jpg', 'platform.jpg'}):
        raise ValueError('Invalid import proof')
    if expected_sha256 and record['files']['original']['sha256'] != expected_sha256:
        raise ValueError('Persisted source identity mismatch')
    for name, proof in record['files'].items():
        raw = read_attachment(folder/name, [folder])
        image, mime = _decode(raw)
        if (digest(raw) != proof['sha256'] or list(image.size) != proof['dimensions']
                or mime != proof['mime']):
            raise ValueError('Changed image or stale proof')
    return record


def import_image(source, roots, output_root, request_id):
    """One request -> one durable original. Changed bytes require a new review.

    No remote write or owner approval is implied by this function. If source
    was cleaned up, use recover() with the caller's saved original SHA256.
    """
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', request_id):
        raise ValueError('Safe request ID required')
    root = _trusted(output_root, directory=True)
    raw = read_attachment(source, roots)
    source_hash = digest(raw)
    folder = root/request_id
    with _lock(root, request_id):
        if folder.exists() or folder.is_symlink():
            return recover(folder, expected_sha256=source_hash)
        image, mime = _decode(raw)
        preview = _jpeg(image)
        limit = (1080, 1920) if image.width <= image.height else (1920, 1080)
        platform = image.copy()
        platform.thumbnail(limit, Image.Resampling.LANCZOS)
        if min(platform.size) < 320:
            raise ValueError('Proportional platform derivative too small')
        platform_raw = _jpeg(platform)
        outputs = {'original': raw, 'preview.jpg': preview, 'platform.jpg': platform_raw}
        record = {'schema': 1, 'request_id': request_id, 'published': False,
                  'conversion': 'Original unchanged; JPEG quality 92, white alpha; platform proportional fit, no crop',
                  'review': 'NOT REVIEWED', 'files': {}}
        for name, content in outputs.items():
            decoded, content_mime = _decode(content)
            record['files'][name] = {'sha256': digest(content), 'dimensions': list(decoded.size), 'mime': content_mime}
        with tempfile.TemporaryDirectory(prefix='.'+request_id+'-', dir=root) as temporary:
            stage = Path(temporary)/'complete'
            stage.mkdir(mode=0o700)
            for name, content in outputs.items():
                _exclusive(stage/name, content)
            _exclusive(stage/'receipt.json', json.dumps(record, sort_keys=True).encode())
            fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            os.rename(stage, folder)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        return recover(folder, expected_sha256=source_hash)


def fetch_public_image(url, destination, *, allow_network=False):
    """Original pinned-public-DNS HTTPS fetch. No redirects or credentials.

    Optional lower-level ingress; destination must be a fresh staging path.
    Use import_image afterwards. This alone grants no attachment provenance.
    """
    if not allow_network:
        raise PermissionError('Network disabled')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or len(parsed.query) > 3000 or parsed.port not in (None, 443)
            or any(c in url for c in ('\r', '\n'))):
        raise ValueError('Public HTTPS URL required')
    host = parsed.hostname.encode('idna').decode('ascii')
    addresses = {a[4][0] for a in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or not all(ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('Non-public address rejected')
    destination = Path(destination).absolute()
    _trusted(destination.parent, directory=True)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Fresh destination required')
    ip = sorted(addresses)[0]
    pin = '['+ip+']' if ':' in ip else ip
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        downloaded = Path(tmp)/'download'
        args = ['curl', '--silent', '--show-error', '--fail', '--noproxy', '*', '--proto', '=https',
                '--connect-timeout', '10', '--max-time', '60', '--max-filesize', str(MAX_BYTES),
                '--resolve', host+':443:'+pin, '--output', str(downloaded), url]
        # No shell and no redirect following. Suppress external error bodies/URLs.
        try:
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=75)
            downloaded.chmod(0o600)
            raw = read_attachment(downloaded, [Path(tmp)])
            _decode(raw)
        except (subprocess.SubprocessError, OSError):
            raise RuntimeError('Image download failed; no retry performed') from None
        _exclusive(destination, raw)
    return {'sha256': digest(raw), 'bytes': len(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--root', action='append', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--request-id', required=True)
    args = parser.parse_args()
    print(json.dumps(import_image(args.source, args.root, args.output_root, args.request_id), indent=2))


if __name__ == '__main__':
    main()
