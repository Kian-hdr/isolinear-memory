#!/usr/bin/env python3
"""Render outlined Isolinear Memory wordmarks from pinned Manrope source.

Development only: use pinned Manrope, fontTools 4.66.1 and @resvg/resvg-js 2.6.2.
The renderer module is installed outside the repository and is never bundled.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


ROOT = Path(__file__).resolve().parents[1]
FONT_SHA256 = '3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


def render(font_path: Path, output: Path, renderer_module: Path) -> None:
    if hashlib.sha256(font_path.read_bytes()).hexdigest() != FONT_SHA256:
        raise ValueError('Manrope source differs from the pinned Google Fonts file.')
    if output.exists():
        raise ValueError('Choose a fresh output directory.')
    if not renderer_module.is_dir():
        raise ValueError('Choose an installed @resvg/resvg-js module directory.')
    output.mkdir(parents=True)
    font = instantiateVariableFont(TTFont(font_path), {'wght': 600}, inplace=False)
    cmap = font.getBestCmap()
    widths = font['hmtx'].metrics
    glyphs = font.getGlyphSet()
    title = 'Isolinear Memory'
    template = ET.parse(ROOT / 'assets/isolinear-memory-mark-dark.svg').getroot()
    mark = template[1]
    for appearance, color in (('dark', '#323232'), ('light', '#F3F3F3')):
        svg = ET.Element(f'{{{NS}}}svg', {'width': '1024', 'height': '220',
                                        'viewBox': '0 0 1024 220', 'role': 'img'})
        ET.SubElement(svg, f'{{{NS}}}title').text = title
        icon = deepcopy(mark)
        icon.set('transform', 'translate(-12 -8) scale(.23)')
        icon.set('color', color)
        svg.append(icon)
        text = ET.SubElement(svg, f'{{{NS}}}g', {'fill': color,
            'transform': 'translate(230 141) scale(0.0435 -0.0435)'})
        position = 0
        for character in title:
            glyph_name = cmap[ord(character)]
            pen = SVGPathPen(glyphs)
            glyphs[glyph_name].draw(pen)
            path = pen.getCommands()
            if path:
                ET.SubElement(text, f'{{{NS}}}path', {'transform': f'translate({position} 0)', 'd': path})
            position += widths[glyph_name][0]
        if 230 + position * 0.0435 > 1024 - 24:
            raise ValueError('Wordmark exceeds its viewBox margin.')
        stem = f'isolinear-memory-wordmark-{appearance}'
        raw = ET.tostring(svg, encoding='utf-8') + b'\n'
        svg_path = output / f'{stem}.svg'
        svg_path.write_bytes(raw)
        js = ('const fs=require("fs");const {Resvg}=require(process.argv[1]);'
              'const svg=fs.readFileSync(process.argv[2]);'
              'fs.writeFileSync(process.argv[3],new Resvg(svg).render().asPng());')
        subprocess.run(['node', '-e', js, str(renderer_module), str(svg_path),
                        str(output / f'{stem}.png')], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--renderer-module', type=Path, required=True)
    args = parser.parse_args()
    render(args.font, args.output, args.renderer_module)
