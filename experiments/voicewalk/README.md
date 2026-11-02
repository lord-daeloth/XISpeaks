# Inno → KVoiceWalk comparison

Standalone local experiment, not a Studio/addon feature. It starts with an Inno
voice tensor, uses KVoiceWalk's mutation and hybrid scoring implementation, and
renders two held-out sentences for listening. It does not train Kokoro's weights.

The comparison uses [RobViren/kvoicewalk](https://github.com/RobViren/kvoicewalk)
(Apache-2.0), tested at `3a38c6030cc4657df073c67ded37cdf7627c4969`.
Clone it into `.reference/kvoicewalk`. With the project virtualenv already set up:

```powershell
.\.venv\Scripts\python.exe -m pip install --target build/kvoicewalk-deps --no-deps resemblyzer==0.1.4 webrtcvad-wheels==2.0.14
.\.venv\Scripts\python.exe experiments/voicewalk/compare.py --pack PATH_TO_INNO.pt --reference PATH_TO_REFERENCE.wav --transcript PATH_TO_TRANSCRIPT.txt --steps 100 --output experiments/voicewalk/output-my-test
```

The script expects Kokoro and English voice assets already staged under
`build/assets/models/hub`, as on the development machine. It uses those offline.
The selected reference and exact transcript must match, including repeated lines.
The output directory must be new; it never overwrites an existing experiment.

Changes relative to the upstream CLI:

- Start directly from the supplied Inno pack, using cached English stock packs
  plus Inno as the mutation population. Skip upstream stock-selection/interpolation.
- Use British pronunciation for a `b*` pack, American otherwise.
- Guard zero/near-zero denominators in audio feature comparisons; adapt the
  current librosa tempo-array return type to upstream's scalar assumption.
- Set an explicit seed, bounded step count, CPU thread count, and save final
  pack even if no candidate improves the score.
- Keep final audition sentences outside both the target and self-consistency
  text used during search. Save metrics and an HTML listening page.

This is an adapted KVoiceWalk pilot, not an exact reproduction of its CLI
defaults or a claim about a fully converged 10,000-step search. Feature similarity
can saturate at upstream's 0.01 floor; inspect results rather than treating the
hybrid score as a calibrated quality measure. A higher speaker-embedding score
does not establish perceptual likeness, pronunciation accuracy, or naturalness.

The output contains a copy of the volunteer reference, generated WAVs, the
optimized tensor and results. Output directories, transcripts, model caches and
recordings are ignored by Git. Nothing uploads the recording, changes the source
pack, or edits NPC assignments. Review audio before choosing any candidate.
