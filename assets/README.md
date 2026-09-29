# Isolinear Memory artwork

Neutral silver and graphite pages connected by one continuous line. The complete
standard and dark icons are exported by Apple's Icon Composer for macOS. The
background, mask and edge treatment come from the native renderer, not a manually
drawn tile. The README selects the PNG matching the viewer's preferred color scheme.

| Asset | Standard / light background | Dark appearance / background |
|---|---|---|
| Native icon, 1024px | [PNG](isolinear-memory.png) | [PNG](isolinear-memory-dark.png) |
| macOS icon container | [ICNS](isolinear-memory.icns) | [ICNS](isolinear-memory-dark.icns) |
| Transparent symbol | [Dark ink](isolinear-memory-mark-dark.svg) | [Light ink](isolinear-memory-mark-light.svg) |
| Publication wordmark | [Dark ink](isolinear-memory-wordmark-dark.svg) | [Light ink](isolinear-memory-wordmark-light.svg) |

[Native Icon Composer source](IsolinearMemory.icon/icon.json) ·
[Appearance preview](light-dark-preview.png).
PNG exports include 16, 24, 32, 48, 64, 128, 256, 512 and 1024 pixels. Internal detail
softens at 16px. Wordmark lettering is outlined and needs no installed font.

`isolinear-memory.svg` and `isolinear-memory-dark.svg` contain the unmasked
foreground vector, identical across appearances. They do not reproduce the
native background. Use the PNG exports for the complete icon or open
`IsolinearMemory.icon` in Icon Composer for native editing and appearance previews.
The `shared-memory*` files remain in the source kit for older integrations.

The native source follows Apple's layered icon workflow. The checked-in exports
were rendered with Icon Composer 27.0 (129), design generation 27, macOS Default
and Dark. These are standalone artwork assets, not a shipped macOS application.
The ICNS files are explicit alternatives and do not switch Finder appearance
automatically. No app installation or runtime appearance-switching test is claimed.

## Regenerate native exports

On a Mac with Icon Composer 27 and Pillow in your development Python environment:

```sh
python scripts/render_icon.py --output /path/to/a/new/icon-output
```

The script uses Icon Composer bundled with Xcode. Set `--ictool` for another
installation; `xcrun ictool` may resolve to a different, incompatible executable.
It writes both appearances to a fresh directory. These are artwork development
requirements only, not Isolinear Memory runtime dependencies.

## Regenerate outlined wordmarks

The v0.5.0 publication wordmarks visibly read **Isolinear Memory**. They reuse
the existing mark and outlined Manrope SemiBold lettering. The four
`shared-memory-wordmark-*` files remain historical source assets and are excluded
from the new public icons ZIP. To regenerate the new SVG and PNG files, supply
the Manrope variable TTF with SHA-256
`3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6`
and an external `@resvg/resvg-js` 2.6.2 module to
[`scripts/render_wordmark.py`](../scripts/render_wordmark.py). The script refuses
an unexpected font or an existing output directory. FontTools, Node and resvg are
development tools only; no font binary or renderer is shipped in the runtime.

```sh
npm install --prefix /tmp/isolinear-wordmark-render --no-save --ignore-scripts --no-audit --no-fund @resvg/resvg-js@2.6.2
uv run --no-project --with fonttools==4.66.1 python scripts/render_wordmark.py \
  --font /path/to/Manrope-wght.ttf \
  --renderer-module /tmp/isolinear-wordmark-render/node_modules/@resvg/resvg-js \
  --output /path/to/a/new/wordmark-output
```

## Provenance

Original refinement of this repository's MIT shared-pages artwork. Previous color
versions and Shared Memory lettering remain in Git history/source. Wordmark lettering uses outlined Manrope SemiBold
from [Google Fonts](https://github.com/google/fonts/tree/main/ofl/manrope), licensed
under the [SIL Open Font License 1.1](Manrope-OFL.txt). No font binaries, Apple icon
artwork or SF fonts are redistributed. No trademark clearance is claimed.

References: [Apple app icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
and [Icon Composer workflow](https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer).
