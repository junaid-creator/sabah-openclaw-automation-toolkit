"""Stage only the four committed synthetic demo assets, never customer media."""
import os
from pathlib import Path

NAMES=('backdrop.svg','primary-logo.svg','secondary-logo.svg','qr-placeholder.svg')

def private_demo_assets(source, private_root):
    source=Path(source);root=Path(private_root).absolute()
    info=root.stat()
    if root!=root.resolve() or info.st_uid!=os.getuid() or info.st_mode & 0o077:
        raise ValueError('Private fixture root required')
    target=root/'demo-assets';target.mkdir(mode=0o700,exist_ok=True)
    if target.is_symlink() or target.stat().st_mode & 0o077:raise ValueError('Unsafe fixture destination')
    for name in NAMES:
        src=source/name
        if src.is_symlink() or not src.is_file() or src.stat().st_size>1_000_000:raise ValueError('Invalid committed demo asset')
        raw=src.read_bytes();dest=target/name
        if dest.exists() or dest.is_symlink():
            if dest.is_symlink() or dest.stat().st_mode & 0o077 or dest.read_bytes()!=raw:raise ValueError('Fixture changed; choose fresh output root')
            continue
        fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as handle:handle.write(raw)
    return target
