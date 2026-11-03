"""Export a local trainer generator snapshot to a player-ready Piper model."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from paths import ROOT, ASSETS

def export(snapshot, output):
    sys.path.insert(0, str(ROOT / 'experiments/piper_training'))
    import run
    run.ROOT = ASSETS
    run.setup_imports()
    import torch
    sys.path.insert(0, str(ROOT / "build/export-deps"))
    from piper.train.vits.lightning import VitsModel
    torch.set_num_threads(4)
    saved = torch.load(snapshot, map_location='cpu', weights_only=True)
    model = VitsModel(**saved['parameters']).model_g
    model.load_state_dict(saved['model_g'], strict=True)
    model.eval()
    with torch.no_grad():
        model.dec.remove_weight_norm()
    def forward(text, lengths, scales):
        return model.infer(text, lengths, noise_scale=scales[0], length_scale=scales[1], noise_scale_w=scales[2])[0]
    model.forward = forward
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Output already exists; choose a new voice name')
    temporary = output.with_suffix('.partial.onnx')
    try:
        torch.onnx.export(model, (torch.randint(0, model.n_vocab, (1, 30)), torch.LongTensor([30]), torch.FloatTensor([.667, 1, .8])),
            str(temporary), opset_version=15, dynamo=False, input_names=['input','input_lengths','scales'], output_names=['output'],
            dynamic_axes={'input': {0:'batch_size',1:'phonemes'}, 'input_lengths':{0:'batch_size'}, 'output':{0:'batch_size',2:'time'}})
        import onnx
        onnx.checker.check_model(str(temporary))
        config = Path(snapshot).parent / 'voice-config.json'
        if not config.exists():
            raise ValueError('Missing voice-config.json beside snapshot')
        # Validate real phonemization and inference before publishing the model.
        shutil.copyfile(config, str(temporary)+'.json')
        from piper import PiperVoice
        voice = PiperVoice.load(temporary)
        chunks = list(voice.synthesize('Welcome, adventurer. What brings you here?'))
        if not chunks or not any(c.audio_int16_bytes for c in chunks):
            raise ValueError('Export produced no speech')
        del voice
        temporary.replace(output)
        Path(str(temporary)+'.json').replace(Path(str(output)+'.json'))
    finally:
        temporary.unlink(missing_ok=True)
        Path(str(temporary)+'.json').unlink(missing_ok=True)
    print(json.dumps({'export':str(output), 'bytes':output.stat().st_size}), flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('snapshot',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();export(args.snapshot,args.output)
