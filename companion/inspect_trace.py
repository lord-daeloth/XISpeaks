"""Read addon traces without speech dependencies: python companion/inspect_trace.py FILE."""
import argparse
from collections import Counter
import csv
from pathlib import Path

from dialogue import clean_dialogue


def describe(encoded):
    raw = bytes.fromhex(encoded)
    cleaned = clean_dialogue(raw)
    if not cleaned:
        return repr(raw)
    return f'{cleaned.speaker} : {cleaned.text}' if cleaned.speaker else cleaned.text


def inspect(path, contains=''):
    counts = Counter()
    with path.open(encoding='utf-8', newline='') as source:
        for row in csv.DictReader(source, delimiter='\t'):
            if row['kind'] == 'packet':
                if not contains:
                    print(f"{row['elapsed_ms']:>6}ms packet 0x{int(row['mode_or_packet']):03X}")
                continue
            text = describe(row['original_hex'])
            modified = describe(row['modified_hex']) if row['modified_hex'] else ''
            if contains.casefold() not in (text + modified).casefold():
                continue
            key = (row['mode_low'], row['injected'], row['decision'])
            counts[key] += 1
            print(f"{row['elapsed_ms']:>6}ms mode={row['mode_or_packet']} low={row['mode_low']} "
                  f"modified_mode={row['mode_modified']} injected={row['injected']} "
                  f"blocked={row['blocked']} decision={row['decision']}\n  {text}")
            if modified and modified != text:
                print(f'  modified: {modified}')
            if int(row['original_bytes']) > 1024 or int(row['modified_bytes']) > 1024:
                print('  [text truncated to 1024 bytes per field in capture]')
    print('\nCounts by (low mode, injected, decision):')
    for key, count in counts.items():
        print(f'  {key}: {count}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--contains', default='', help='Show only matching text, e.g. Halver')
    args = parser.parse_args()
    inspect(args.trace, args.contains)


if __name__ == '__main__':
    main()
