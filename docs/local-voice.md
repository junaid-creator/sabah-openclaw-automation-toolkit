# Local speech adapters discovered outside the old inventory

The original extensionless ASR/Piper executables were outside the workspace-only
scan. toolkit.local_voice ports the local conversion/transcription and explicit
voice-profile selection behavior. No model, executable or voice is redistributed.

Upstream requirements: [sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/),
[FFmpeg](https://ffmpeg.org/), and an operator-reviewed
[Piper distribution](https://github.com/OHF-Voice/piper1-gpl). The maintained Piper
project and individual voice/model files have their own licenses; the toolkit MIT
license does not apply to them. Review commercial-use terms and dependencies
before setting model_license_reviewed=true. No downloads/installations are run.

Configure explicit local paths using examples/local-voice.json. Require trusted,
non-writable-by-others executables/models; untrusted chat cannot choose them.

    python -m toolkit.local_voice --config /private/voice.json transcribe --source /private/inbound/audio.ogg --root /private/inbound
    python -m toolkit.local_voice --config /private/voice.json synthesize --text-file /private/text.txt --text-root /private --output /private/new-output.wav --profile female

Input audio is bounded to 20 MiB. Supported WAV/Ogg/MP3/MP4 input is fed through a
pipe with pipe-only input protocol policy, not a source-controlled URL/playlist.
FFmpeg has a 30-second timeout and output byte bound; decoded PCM duration is at
most 180 seconds. ASR runs two threads with a 150-second timeout. Text is at most
3,000 characters; Piper has a 90-second timeout. Output is a new private WAV,
never a message. Transcripts are returned to the caller, not retained in metrics.

English/Urdu/Arabic selection retains the original script heuristic: it is not a
full language detector. Unsupported or unlicensed voice profiles fail closed,
including Arabic when not explicitly configured. Voice-profile choice is an
explicit operator setting, not an inferred user identity. There is no cloud fallback.

Ten synthetic subprocess/PCM tests pass. Actual recognition quality, pronunciation,
voice licensing, installed-binary compatibility, microphone/WhatsApp ingress,
audio/text priority, and customer voice replies are NOT TESTED. Config mutation,
auto voice activation and patched native WhatsApp handlers are intentionally not
ported by this module. The original control service required privileged deployment
changes; a standalone local adapter is not that integration.
