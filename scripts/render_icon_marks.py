#!/usr/bin/env python3
"""Export transparent SVG and PNG marks from the Icon Composer foregrounds.

Development only: requires Node.js and a local @resvg/resvg-js module.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


def render(output: Path, renderer_module: Path) -> None:
    if output.exists():
        raise ValueError('Choose a fresh output directory.')
    if not renderer_module.is_dir():
        raise ValueError('Choose an installed @resvg/resvg-js module directory.')
    output.mkdir(parents=True)
    js = ('const fs=require("fs");const {Resvg}=require(process.argv[1]);'
          'const svg=fs.readFileSync(process.argv[2]);'
          'fs.writeFileSync(process.argv[3],new Resvg(svg).render().asPng());')
    for variant, source_name in (('dark', 'foreground.svg'),
                                 ('light', 'foreground-dark.svg')):
        source = ET.parse(ROOT / 'assets/IsolinearMemory.icon/Assets' / source_name).getroot()
        left, top, width, height = (float(value) for value in source.get('viewBox').split())
        if width != height:
            raise ValueError('Foreground viewBox must be square.')
        scale = 1024 / width
        svg = ET.Element(f'{{{NS}}}svg', {'width': '1024', 'height': '1024',
                          'viewBox': '0 0 1024 1024', 'role': 'img'})
        ET.SubElement(svg, f'{{{NS}}}title').text = 'Isolinear Memory lattice'
        group = ET.SubElement(svg, f'{{{NS}}}g', {
            'transform': f'translate({-left * scale:g} {-top * scale:g}) scale({scale:g})'})
        for child in source:
            if child.tag != f'{{{NS}}}title':
                group.append(deepcopy(child))
        stem = f'isolinear-memory-mark-{variant}'
        svg_path = output / f'{stem}.svg'
        svg_path.write_bytes(ET.tostring(svg, encoding='utf-8') + b'\n')
        subprocess.run(['node', '-e', js, str(renderer_module), str(svg_path),
                        str(output / f'{stem}.png')], check=True)
    (output / 'isolinear-memory-mark.svg').write_bytes(
        (output / 'isolinear-memory-mark-dark.svg').read_bytes())
    (output / 'isolinear-memory-mark.png').write_bytes(
        (output / 'isolinear-memory-mark-dark.png').read_bytes())
    (output / 'isolinear-memory.svg').write_bytes(
        (output / 'isolinear-memory-mark-dark.svg').read_bytes())
    (output / 'isolinear-memory-dark.svg').write_bytes(
        (output / 'isolinear-memory-mark-light.svg').read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--renderer-module', type=Path, required=True)
    args = parser.parse_args()
    render(args.output, args.renderer_module)
