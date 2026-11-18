"""Explicit local ASR/Piper adapters. No models, downloads, channel activation or sends.

Operator-owned executable/model configuration is required. Voice/model licensing
is external; configured consent is not a legal determination by this library.
"""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave
from .image_intake import read_attachment, _trusted, _exclusive


def asset(value):
    path=Path(value).absolute()
    if path != path.resolve(strict=True) or not path.is_file() or path.stat().st_mode & 0o022:
        raise ValueError('Explicit non-writable trusted local asset required')
    return path


def language(text):
    if any(c in text for c in 'پچژگٹڈڑںےھ'):return 'ur'
    if any(chr(0x600)<=c<=chr(0x6ff) for c in text):return 'ar'
    return 'en'


def wav_info(raw):
    if len(raw)>24*1024*1024:raise ValueError('Decoded audio exceeds bound')
    with wave.open(io.BytesIO(raw),'rb') as sound:
        if sound.getcomptype()!='NONE' or sound.getnchannels() not in (1,2) or sound.getsampwidth()!=2:
            raise ValueError('PCM audio required')
        rate,frames=sound.getframerate(),sound.getnframes()
        if not 8000<=rate<=48000 or not 0<frames/rate<=180:raise ValueError('Audio duration/rate outside bound')
        actual=sound.readframes(frames)
        if len(actual)!=frames*sound.getnchannels()*sound.getsampwidth():raise ValueError('Truncated WAV')
        return {'duration_seconds':frames/rate,'sample_rate':rate,'channels':sound.getnchannels()}


def transcribe(source, roots, config, *, runner=subprocess.run):
    if config.get('model_license_reviewed') is not True:raise PermissionError('Review model license first')
    ffmpeg=asset(config['ffmpeg']);asr=asset(config['asr'])
    models={key:asset(config[key]) for key in ('encoder','decoder','tokens')}
    raw=read_attachment(source,roots)
    # Only local pipe input: no source-controlled network or filesystem playlist.
    if raw.startswith(b'RIFF') and raw[8:12]==b'WAVE':fmt='wav'
    elif raw.startswith(b'OggS'):fmt='ogg'
    elif raw.startswith(b'ID3') or (len(raw)>2 and raw[0]==255 and raw[1]&224==224):fmt='mp3'
    elif len(raw)>12 and raw[4:8]==b'ftyp':fmt='mov'
    else:raise ValueError('Supported audio container required')
    with tempfile.TemporaryDirectory(prefix='toolkit-asr-') as tmp:
        wav=Path(tmp)/'audio.wav'
        try:
            runner([str(ffmpeg),'-hide_banner','-loglevel','error','-nostdin','-y',
                    '-protocol_whitelist','pipe','-f',fmt,'-i','pipe:0','-ar','16000','-ac','1','-c:a','pcm_s16le','-fs',str(24*1024*1024+1),str(wav)],
                   input=raw,capture_output=True,check=True,timeout=30)
            wav.chmod(0o600)
            info=wav_info(read_attachment(wav,[tmp],max_bytes=24*1024*1024))
            result=runner([str(asr),'--whisper-encoder='+str(models['encoder']),
                '--whisper-decoder='+str(models['decoder']),'--tokens='+str(models['tokens']),
                '--num-threads=2','--debug=false',str(wav)],capture_output=True,check=True,timeout=150)
        except (OSError,subprocess.SubprocessError):
            raise RuntimeError('Local transcription failed; no external fallback') from None
        if len(result.stdout)>1_000_000:raise ValueError('ASR response exceeds bound')
        for line in reversed(result.stdout.decode('utf-8',errors='replace').splitlines()):
            if line.startswith('{'):
                value=json.loads(line);text=value.get('text','').strip()
                if text and len(text)<=20000:
                    return {'text':text,'detected_language':value.get('lang'),'audio':info,'external_calls':False}
        raise ValueError('No verified transcription result')


def synthesize(text, output, config, *, profile, runner=subprocess.run):
    if not isinstance(text,str) or not text.strip() or len(text)>3000:raise ValueError('Bounded nonempty text required')
    if config.get('model_license_reviewed') is not True:raise PermissionError('Review voice model license first')
    selected=config.get('voices',{}).get(profile,{}).get(language(text))
    if not selected:raise ValueError('No reviewed voice for selected profile/script; no fallback')
    executable=asset(config['piper']);model=asset(selected)
    output=Path(output).absolute();_trusted(output.parent,directory=True)
    if output.exists() or output.is_symlink():raise ValueError('Fresh output path required')
    with tempfile.TemporaryDirectory(prefix='.voice-',dir=output.parent) as tmp:
        wav=Path(tmp)/'audio.wav'
        try:
            runner([str(executable),'--model',str(model),'--output_file',str(wav),'--quiet'],
                   input=text+chr(10),text=True,capture_output=True,check=True,timeout=90)
            wav.chmod(0o600);raw=read_attachment(wav,[tmp],max_bytes=24*1024*1024);info=wav_info(raw)
        except (OSError,subprocess.SubprocessError):
            raise RuntimeError('Local voice generation failed; no external fallback') from None
        _exclusive(output,raw)
    return {'output':str(output),'language_heuristic':language(text),'profile':profile,'audio':info,'sent':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('transcribe');a.add_argument('--source',required=True);a.add_argument('--root',action='append',required=True)
    a=sub.add_parser('synthesize');a.add_argument('--text-file',required=True);a.add_argument('--text-root',required=True);a.add_argument('--output',required=True);a.add_argument('--profile',required=True)
    a=p.parse_args();config_path=asset(a.config)
    if config_path.stat().st_uid!=os.geteuid():raise PermissionError('Operator-owned configuration required')
    config=json.loads(config_path.read_text())
    result=transcribe(a.source,a.root,config) if a.command=='transcribe' else synthesize(read_attachment(a.text_file,[a.text_root],max_bytes=12000).decode(),a.output,config,profile=a.profile)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
