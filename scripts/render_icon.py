#!/usr/bin/env python3
"""Export native macOS appearances from IsolinearMemory.icon using Icon Composer.

Requires macOS, Icon Composer (bundled with Xcode) and Pillow. No runtime dependency.
"""
from pathlib import Path
import argparse
import subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
DEFAULT_TOOL = Path('/Applications/Xcode.app/Contents/Applications/Icon Composer.app/Contents/Executables/ictool')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh output directory')
    parser.add_argument('--ictool', type=Path, default=DEFAULT_TOOL, help='Icon Composer bundled ictool executable')
    args = parser.parse_args()
    if not args.ictool.is_file():
        parser.error('Icon Composer ictool is required; use --ictool for another installation.')
    args.output.mkdir(parents=True, exist_ok=False)
    for stem, rendition in [('isolinear-memory', 'Default'), ('isolinear-memory-dark', 'Dark')]:
        png = args.output / (stem + '.png')
        subprocess.run([str(args.ictool), str(ROOT / 'assets/IsolinearMemory.icon'),
                        '--export-image', '--output-file', str(png), '--platform', 'macOS',
                        '--rendition', rendition, '--width', '1024', '--height', '1024',
                        '--scale', '1', '--design-generation', '27'], check=True)
        icon = Image.open(png).convert('RGBA')
        icon.save(args.output / (stem + '.icns'), format='ICNS')
        for size in SIZES:
            icon.resize((size, size), Image.Resampling.LANCZOS).save(
                args.output / (stem + '-' + str(size) + '.png'))
    preview = Image.new('RGB', (1600, 800))
    preview.paste((231, 236, 245), (0, 0, 800, 800))
    preview.paste((23, 30, 43), (800, 0, 1600, 800))
    for x, stem in ((50, 'isolinear-memory'), (850, 'isolinear-memory-dark')):
        icon = Image.open(args.output / (stem + '.png')).convert('RGBA')
        icon = icon.resize((700, 700), Image.Resampling.LANCZOS)
        preview.paste(icon, (x, 50), icon)
    preview.save(args.output / 'light-dark-preview.png')
    print(args.output)


if __name__ == '__main__':
    main()
