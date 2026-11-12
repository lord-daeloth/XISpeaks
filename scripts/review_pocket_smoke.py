"""Keep warning-producing profiles available manually and publish the smoke report."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
stage=ROOT/'build/pocket-release/XISpeaksPocket'
results=json.loads((stage/'companion/pocket-runtime/self-test/results.json').read_text())
catalog_path=ROOT/'pocket_voices/catalog.json'
catalog=json.loads(catalog_path.read_text())
assert len(results)==len(catalog) and {r['voice'] for r in results}==set(catalog)
assert all('warnings' in r for r in results), 'Run the diagnostic EXE first'
flagged=[]
for result in results:
    if result['warnings']:
        entry=catalog[result['voice']]
        entry['automatic']=False
        entry['validation_warnings']=result['warnings']
        flagged.append(result['voice'])
catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
sources_path=ROOT/'pocket_voices/sources.json'
sources=json.loads(sources_path.read_text())
for row in sources['voices']:
    row.update(catalog[row['key']])
sources_path.write_text(json.dumps(sources,indent=2)+'\n')
(stage/'VOICE-TEST-RESULTS.json').write_text(json.dumps(dict(text='Welcome, adventurer.',seed=42,model='public English 18M',note='Synthesis smoke test, not human listening review. Profiles producing model warnings are manual-only.',profiles=results),indent=2))
(stage/'VOICE-TEST-REPORT.txt').write_text(f'{len(results)} profiles generated nonempty audio using the packaged public model.\n{len(flagged)} profiles produced model warnings and are manual-only pending listening review.\nAll other newly exported profiles also need human review and calibration.\n\nManual-only warning profiles:\n'+'\n'.join(flagged)+'\n')
print('Warning profiles made manual-only:',len(flagged),flagged)
