import sys, os
sys.path.insert(0, 'src')
os.chdir(r'C:\Dev\watt-spec-parser')
from spec_parser.pipeline import run_single

base = r'C:\Users\WattB\.openclaw\workspace\watt-spec-parser\Spec Samples'
specs = [
    ('PHX83/23_07_00', os.path.join(base, 'PHX83', '23_07_00_HVAC_INSULATION_M.2.pdf')),
    ('PHX83/22_07_00', os.path.join(base, 'PHX83', '22_07_00_PLUMBING_INSULATION.pdf')),
    ('UO2/230700',     os.path.join(base, 'UO2.MO', '230700.pdf')),
    ('UO2/22-07-00',   os.path.join(base, 'UO2.MO', '22-07-00.pdf')),
]
for name, path in specs:
    if not os.path.exists(path):
        print(f'{name}: FILE NOT FOUND at {path}')
        continue
    try:
        r = run_single(path)
        p = len(r.get('pipe_rows', []))
        d = len(r.get('duct_rows', []))
        j = len(r.get('jacket_rows', []))
        print(f'{name}: {p} pipe, {d} duct, {j} jacket')
    except Exception as e:
        print(f'{name}: ERROR - {e}')
