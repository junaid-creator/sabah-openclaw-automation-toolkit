import io
import json
from pathlib import Path
import tempfile
import types
import unittest
import wave
from toolkit.local_voice import transcribe,synthesize,language,wav_info

class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.asset=self.root/'trusted';self.asset.write_bytes(b'synthetic executable/model placeholder');self.asset.chmod(0o600)
        self.audio=self.wav();self.source=self.root/'audio.wav';self.source.write_bytes(self.audio);self.source.chmod(0o600)
        path=str(self.asset)
        self.config=dict(model_license_reviewed=True,ffmpeg=path,asr=path,encoder=path,decoder=path,tokens=path,piper=path,voices={'female':{'en':path,'ur':path},'male':{'en':path}})
        self.calls=[]
    def wav(self,seconds=1):
        out=io.BytesIO()
        with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(bytes(32000*seconds))
        return out.getvalue()
    def runner(self,args,**kw):
        self.calls.append((args,kw))
        self.assertNotIn('shell',kw)
        if '-protocol_whitelist' in args:
            self.assertEqual(args[args.index('-protocol_whitelist')+1],'pipe')
            self.assertIn('-fs',args)
            Path(args[-1]).write_bytes(self.audio)
        elif '--output_file' in args:Path(args[args.index('--output_file')+1]).write_bytes(self.audio)
        return types.SimpleNamespace(stdout=b'log line'+bytes([10])+json.dumps({'text':'Synthetic transcript','lang':'en'}).encode())
    def test_asr_local_pipeline(self):
        result=transcribe(self.source,[self.root],self.config,runner=self.runner)
        self.assertEqual(result['text'],'Synthetic transcript');self.assertFalse(result['external_calls']);self.assertEqual(len(self.calls),2)
        self.assertEqual(self.calls[0][1]['input'],self.audio)
    def test_tts_file_only(self):
        result=synthesize('Hello',self.root/'out.wav',self.config,profile='female',runner=self.runner)
        self.assertFalse(result['sent']);self.assertEqual((self.root/'out.wav').read_bytes(),self.audio)
        self.assertEqual((self.root/'out.wav').stat().st_mode & 0o777,0o600)
    def test_no_unreviewed_license(self):
        self.config['model_license_reviewed']=False
        with self.assertRaises(PermissionError):transcribe(self.source,[self.root],self.config,runner=self.runner)
        self.assertEqual(self.calls,[])
    def test_arabic_unconfigured_fails_closed(self):
        self.assertEqual(language('مرحبا'),'ar')
        with self.assertRaises(ValueError):synthesize('مرحبا',self.root/'out.wav',self.config,profile='female',runner=self.runner)
        self.assertEqual(self.calls,[])
    def test_explicit_profile_and_urdu(self):
        self.assertEqual(language('آپ کیسے ہیں'),'ur')
        synthesize('آپ کیسے ہیں',self.root/'out.wav',self.config,profile='female',runner=self.runner)
        with self.assertRaises(ValueError):synthesize('hello',self.root/'out2.wav',self.config,profile='unknown',runner=self.runner)
    def test_no_output_overwrite(self):
        with self.assertRaises(ValueError):synthesize('hello',self.source,self.config,profile='female',runner=self.runner)
    def test_symlink_source_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.source)
        with self.assertRaises(OSError):transcribe(alias,[self.root],self.config,runner=self.runner)
    def test_bad_audio_container_rejected(self):
        self.source.write_bytes(b'http://127.0.0.1/private')
        with self.assertRaises(ValueError):transcribe(self.source,[self.root],self.config,runner=self.runner)
        self.assertEqual(self.calls,[])
    def test_duration_bounded(self):
        with self.assertRaises(ValueError):wav_info(self.wav(181))
    def test_text_bound(self):
        for text in ['','x'*3001]:
            with self.assertRaises(ValueError):synthesize(text,self.root/'out.wav',self.config,profile='female',runner=self.runner)

if __name__=='__main__':unittest.main()
