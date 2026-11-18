import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from toolkit import image_intake as m


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.incoming = self.root/'inbound'
        self.output = self.root/'output'
        self.incoming.mkdir(mode=0o700)
        self.output.mkdir(mode=0o700)
        self.source = self.incoming/'image.png'
        self.make()

    def make(self, size=(640, 800), color='red', fmt='PNG'):
        out = io.BytesIO()
        Image.new('RGB', size, color).save(out, format=fmt)
        self.source.write_bytes(out.getvalue())
        self.source.chmod(0o600)
        return out.getvalue()

    def run_import(self, request='request-one'):
        return m.import_image(self.source, [self.incoming], self.output, request)

    def test_original_bytes_and_replay(self):
        raw = self.source.read_bytes()
        one = self.run_import()
        two = self.run_import()
        self.assertEqual(one, two)
        self.assertEqual((self.output/'request-one/original').read_bytes(), raw)
        self.assertFalse(one['published'])
        self.assertEqual(one['review'], 'NOT REVIEWED')
        self.assertEqual(len([p for p in self.output.iterdir() if p.is_dir()]), 1)

    def test_recover_after_source_cleanup(self):
        receipt = self.run_import()
        self.source.unlink()
        self.assertEqual(m.recover(self.output/'request-one', expected_sha256=receipt['files']['original']['sha256']), receipt)

    def test_changed_source_rejected(self):
        self.run_import()
        self.make(color='blue')
        with self.assertRaises(ValueError): self.run_import()

    def test_missing_import_proof_rejected(self):
        self.run_import()
        (self.output/'request-one/receipt.json').unlink()
        with self.assertRaises(FileNotFoundError): m.recover(self.output/'request-one')

    def test_changed_output_rejected(self):
        self.run_import()
        (self.output/'request-one/preview.jpg').write_bytes(self.source.read_bytes())
        with self.assertRaises(ValueError): m.recover(self.output/'request-one')

    def test_wrong_saved_original_hash_rejected(self):
        self.run_import()
        with self.assertRaises(ValueError): m.recover(self.output/'request-one', expected_sha256='0'*64)

    def test_all_outputs_private(self):
        self.run_import()
        for p in (self.output/'request-one').iterdir(): self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_platform_fit_and_no_upscale(self):
        self.make(size=(1600, 2400))
        one = self.run_import()
        self.assertEqual(one['files']['platform.jpg']['dimensions'], [1080, 1620])
        self.assertEqual(one['files']['original']['dimensions'], [1600, 2400])
        self.make(size=(640, 800))
        two = self.run_import('two')
        self.assertEqual(two['files']['platform.jpg']['dimensions'], [640, 800])

    def test_landscape_fit(self):
        self.make(size=(2400, 1600))
        self.assertEqual(self.run_import()['files']['platform.jpg']['dimensions'], [1620, 1080])

    def test_too_small_and_too_thin(self):
        for size in [(100,100),(320,5000)]:
            self.make(size=size)
            with self.assertRaises(ValueError): self.run_import()
        self.assertFalse((self.output/'request-one').exists())

    def test_symlink_file_rejected(self):
        alias = self.incoming/'alias.png'
        alias.symlink_to(self.source)
        with self.assertRaises(OSError): m.import_image(alias, [self.incoming], self.output, 'x')

    def test_symlink_ancestor_rejected(self):
        alias = self.incoming/'alias'
        alias.symlink_to(self.incoming, target_is_directory=True)
        with self.assertRaises(OSError): m.import_image(alias/'image.png', [self.incoming], self.output, 'x')

    def test_outside_and_traversal_rejected(self):
        with self.assertRaises(ValueError): m.import_image(self.source, [self.output], self.output, 'x')
        with self.assertRaises(ValueError): m.import_image(self.incoming/'../inbound/image.png', [self.incoming], self.output, 'x')

    def test_unsafe_modes_rejected(self):
        self.source.chmod(0o666)
        with self.assertRaises(ValueError): self.run_import()
        self.source.chmod(0o600)
        self.incoming.chmod(0o777)
        with self.assertRaises(ValueError): self.run_import()

    def test_fifo_rejected_without_blocking(self):
        self.source.unlink()
        os.mkfifo(self.source, 0o600)
        with self.assertRaises(ValueError): self.run_import()

    def test_unsafe_request_rejected(self):
        for request in ['../escape', '', 'a/b', 'x'*65]:
            with self.assertRaises(ValueError): self.run_import(request)

    def test_corrupt_and_unsupported_format(self):
        self.source.write_bytes(b'not an image')
        with self.assertRaises(OSError): self.run_import()
        self.make(fmt='BMP')
        with self.assertRaises(ValueError): self.run_import()

    def test_json_path_injection_rejected(self):
        self.run_import()
        p = self.output/'request-one/receipt.json'
        data = json.loads(p.read_text())
        data['files']['../../private'] = data['files'].pop('original')
        p.write_text(json.dumps(data))
        with self.assertRaises(ValueError): m.recover(p.parent)

    def test_fetch_disabled_by_default(self):
        with patch.object(socket, 'getaddrinfo') as resolve:
            with self.assertRaises(PermissionError): m.fetch_public_image('https://example.com/x', self.root/'new')
            resolve.assert_not_called()

    def test_fetch_rejects_private_and_mixed_dns(self):
        for addresses in [['127.0.0.1'], ['1.1.1.1','192.168.0.1'], ['::1']]:
            with patch.object(socket, 'getaddrinfo', return_value=[(2,1,6,'',(ip,443)) for ip in addresses]):
                with self.assertRaises(ValueError): m.fetch_public_image('https://example.com/x', self.root/'new', allow_network=True)

    def test_fetch_url_policy(self):
        for url in ['http://example.com/x','https://user:pw@example.com/x','https://example.com:8443/x','https://example.com/x#fragment']:
            with self.assertRaises(ValueError): m.fetch_public_image(url, self.root/'new', allow_network=True)

    def test_fetch_pins_dns_no_redirect_and_validates_image(self):
        raw = self.source.read_bytes()
        def download(args, **kwargs):
            self.assertIn('--resolve', args)
            self.assertIn('example.com:443:1.1.1.1', args)
            self.assertNotIn('--location', args)
            self.assertNotIn('-L', args)
            self.assertNotIn('shell', kwargs)
            Path(args[args.index('--output')+1]).write_bytes(raw)
        with patch.object(socket, 'getaddrinfo', return_value=[(2,1,6,'',('1.1.1.1',443))]), patch.object(m.subprocess, 'run', side_effect=download) as execute:
            result = m.fetch_public_image('https://example.com/image', self.root/'new', allow_network=True)
            self.assertEqual(result['sha256'], m.digest(raw))
            self.assertEqual(execute.call_count, 1)
            with self.assertRaises(ValueError): m.fetch_public_image('https://example.com/image', self.root/'new', allow_network=True)


if __name__ == '__main__': unittest.main()
