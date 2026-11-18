# Supplied-image intake

Callable library and trusted-local CLI; **not a chat ingress or publisher**.
Derived from the original image-import engine. Uses pinned Pillow; optional URL
fetch uses system curl. No generated or proprietary images are distributed.

Create private runtime-owned inbound/output directories, then from the checkout:

	python -m toolkit.image_intake --source /private/inbound/photo.png --root /private/inbound --output-root /private/assets --request-id request-001

(The command starts with python; paths are examples to configure.)

A request saves original bytes, decoded original metadata, JPEG preview,
proportional platform derivative and per-file SHA256 in an atomic private folder.
Reusing a request with identical input validates and returns the existing receipt;
changed input is rejected. After cleanup, call recover(folder,
expected_sha256=the_independently_saved_original_hash). Missing or stale proof is
blocked. Receipt review remains NOT REVIEWED: inspect the actual original and
derivatives before owner review. Import success never grants publication.

Input restrictions: runtime-owned regular file, non-group/world-writable file and
root/subdirectories, no symlink traversal, maximum 20 MiB, JPEG/PNG/WebP,
single frame, minimum 320 pixels on each axis, maximum 40 million pixels. Parent
roots and output directory must be trusted and not writable by untrusted users.
Linux no-follow file descriptors and flock are required. Platform derivative is
at most 1080x1920 portrait / 1920x1080 landscape without crop or upscale; these
are the reference limits, not proof of every provider's current API acceptance.

Optional fetch_public_image requires allow_network=True, public-only DNS,
HTTPS port 443, no credentials, no redirects and DNS pinning. Its output still
requires authenticated provenance admission and local import. The fetch tests
mock DNS and curl; no real external image was downloaded in release tests.

22 regression tests cover actual decode/convert/recovery, unchanged originals,
symlinks, traversal, unsafe modes/FIFO, stale proof, request reuse, network denial,
URL policy, DNS pinning and proportional derivatives. No original photographs,
customer attachments, private state, uploads or live channel tests are included.

Differences from original: Pillow replaces ImageMagick/file, preview JPEG is
always re-encoded while original remains exact, durable fixed request folders
replace random output filenames. EXIF orientation is not interpreted; inspect
orientation in review before use. No imported source URL or local path is stored
in the public-facing receipt. Native owner/media association and social controller
integration remain PARTIALLY PORTED.
