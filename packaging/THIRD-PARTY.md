# XISpeaks beta 3 distribution

XISpeaks code is GPL-3.0-or-later. Pocket TTS 4.0.1 by Kyutai is MIT;
the public English 18M model and tokenizer carry CC BY 4.0, and are distributed
unchanged. Model source: https://huggingface.co/kyutai/pocket-tts-without-voice-cloning
Pinned model revision: a7056f505a4a8ca72d8b5fb1440071d6f1a35739.
Tokenizer revision: 08ffc58775e62aad9409511b9591c9af626270f3.

Voice states are generated adaptations of recordings in Kyutai's tts-voices
collection. The pinned source URL and license for each imported profile are in
companion/pocket_voices/sources.json and catalog.json. See VOICE-LICENSES.md.
Voice licenses apply separately from the program's GPL license. Expresso and
EARS profiles are CC BY-NC 4.0; this curated beta pack includes them and is
not a commercial-use voice pack. Original collection attribution is reproduced
in licenses/UPSTREAM-VOICES.md. Custom profiles retain their supplied credit and permission notes in VOICE-LICENSES.md; they must not be described as volunteer recordings unless that is documented.

Rubber Band 4.0.0 by Breakfast Quay is GPL; its source archive and binary notices
are included. libsndfile 1.2.2 source is included alongside it. Python, PyTorch,
NumPy, SciPy, PyAudio, librosa, SentencePiece, safetensors, and other dependencies
retain their own licenses, reproduced under licenses/. packages.json records
the build environment. No Piper models or gated cloning weights are included.
