# Third-party software and models

XISpeaks is GPL-3.0-or-later. The Windows build uses [Piper 1.8.0](https://github.com/OHF-Voice/piper1-gpl/tree/v1.8.0) (GPL-3.0-or-later) and the eSpeak NG revision pinned by that release. [Rubber Band 4.0.0](https://breakfastquay.com/rubberband/) supplies the R3 pitch effect. Their source archives accompany the release, together with libsndfile source. Python, ONNX Runtime, PyAudio, NumPy, SciPy, librosa and their dependencies retain their respective licenses. See the licenses directory in the ZIP.

The bundled English LibriTTS high voice was trained from scratch on LibriTTS train-clean-360. The model card credits [LibriTTS](https://www.openslr.org/60/) (CC BY 4.0, Heiga Zen and collaborators). XISpeaks distributes the original model unchanged. [Model card](https://huggingface.co/rhasspy/piper-voices/blob/e7229f7d33a10e145e109b886d661984201ac3c4/en/en_US/libritts/high/MODEL_CARD) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Other weights are obtained from [the upstream Piper collection](https://huggingface.co/rhasspy/piper-voices/tree/e7229f7d33a10e145e109b886d661984201ac3c4/en). Consult each model card under companion/data/piper-model-info before use. Terms vary by model and dataset, and some restrict commercial use. The XISpeaks license covers its code.
