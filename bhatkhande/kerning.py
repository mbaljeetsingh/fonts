# -*- coding: utf-8 -*-
"""Build-time kerning for the Ome Bhatkhande faces.

The faces are deliberately monospaced -- every swara gets the same advance
(1582/2048 em) so the notation grid stays tabular -- but the glyph INK
varies per language: Gurmukhi ni overhangs its box while sa/re/ga leave
~0.1em of side bearing on each side, so a run like `sssr` reads spread out
next to a naturally-touching `nnns`.

This module measures the real side bearings of the swara glyphs of a
generated face (AFTER language glyph replacement, so each language's own
outlines drive the values -- never a shared hand-measured table) and adds
kerning under the `kern` feature that closes each swara-to-swara gap down
to TARGET_GAP. Values are negative only: pairs the font already draws
tighter than the target (ni-ni's designed overlap) keep their spacing.

The kerning is authored as a chained context rather than plain GPOS
pairs, because of the zero-advance mark glyphs (komal `l`/`L`, octave
dots `u`/`U`): a pair kern on the first glyph's advance would drag the
mark drawn after it off its base note, and a pair value on the second
glyph makes shapers consume that glyph, losing every second kern in a
run. Instead, each rule matches [glyphs sharing a right bearing]
[glyphs sharing a left bearing] -- with marks skipped via the
ignore-marks lookup flag, so a join still kerns ACROSS a mark -- and
applies a single adjustment (placement + advance) to the second glyph
only. The first glyph's advance is untouched, so its mark stays glued;
nothing is consumed, so every join in a run kerns.

Everything that is not a swara or a mark (dashes, strokes, digits,
chhand arcs) breaks the chain and keeps natural spacing.
"""

# Swara glyphs that participate in kerning (regular + variant notes).
SWARAS = ['s', 'r', 'g', 'm', 'p', 'd', 'n', 'R', 'G', 'M', 'D', 'N']

# Zero-advance komal / octave marks a kerned join may form across.
MARKS = ['l', 'L', 'u', 'U']

# Desired ink gap between adjacent swaras, in em. Chosen to match how the
# tightest naturally-fitting pairs (e.g. Gurmukhi ni-ni) read.
TARGET_GAP_EM = 0.030

CONTEXT_LOOKUP = 'Swara kerning'


def side_bearings(font):
    """Measure (lsb, rsb) of each swara glyph from its outlines, in font
    units. Must run after glyph replacement so the language's own ink is
    measured."""
    bearings = {}
    for name in SWARAS:
        glyph = font[name]
        xmin, _, xmax, _ = glyph.boundingBox()
        if xmax <= xmin:
            # Blank outline (e.g. a language SFD missing the glyph) would
            # masquerade as enormous bearings; leave it unkerned instead.
            print('  kerning: skipping blank glyph {}'.format(name))
            continue
        bearings[name] = (int(round(xmin)), int(round(glyph.width - xmax)))
    return bearings


def add_kerning(font):
    """Add the `kern` chained-context lookup to a generated face."""
    target_gap = int(round(TARGET_GAP_EM * font.em))
    bearings = side_bearings(font)

    # GDEF mark classification, so the ignore-marks flag can skip them.
    for name in MARKS:
        font[name].glyphclass = 'mark'

    # Swaras sharing a right side bearing kern identically as the first
    # glyph of a join; sharing a left side bearing, as the second.
    def classes_by(bearing_index):
        groups = {}
        for name in bearings:
            groups.setdefault(bearings[name][bearing_index], []).append(name)
        return sorted(groups.items())

    first_classes = classes_by(1)   # grouped by rsb
    second_classes = classes_by(0)  # grouped by lsb

    # One single-adjustment lookup per distinct kern value, shared by
    # every (first, second) class pair that needs that value.
    kerns = {}
    for rsb, first in first_classes:
        for lsb, second in second_classes:
            kern = min(0, target_gap - (rsb + lsb))
            if kern:
                kerns.setdefault(kern, []).append((first, second))
    for kern, class_pairs in sorted(kerns.items()):
        lookup = kern_lookup_name(kern)
        font.addLookup(lookup, 'gpos_single', (), ())
        font.addLookupSubtable(lookup, lookup + ' subtable')
        adjusted = set()
        for first, second in class_pairs:
            for name in second:
                if name not in adjusted:
                    font[name].addPosSub(
                        lookup + ' subtable', kern, 0, kern, 0)
                    adjusted.add(name)

    font.addLookup(
        CONTEXT_LOOKUP,
        'gpos_contextchain',
        ('ignore_marks',),
        (('kern', (('DFLT', ('dflt',)), ('latn', ('dflt',)))),)
    )
    # One rule per class pair: backtrack [first glyphs], input [second
    # glyph, which takes the shift]. Backtracks are disjoint (classes
    # partition by bearing), so at most one rule matches at a position.
    rule_no = 0
    for kern, class_pairs in sorted(kerns.items()):
        for first, second in class_pairs:
            rule_no += 1
            font.addContextualSubtable(
                CONTEXT_LOOKUP, 'kern rule {}'.format(rule_no), 'coverage',
                '[{}] | [{}] @<{}> |'.format(
                    ' '.join(first), ' '.join(second),
                    kern_lookup_name(kern)))

    report(font, bearings, kerns)


def kern_lookup_name(kern):
    return 'Swara kern {}'.format(kern)


def report(font, bearings, kerns):
    """Print measured bearings and kern classes for build logs."""
    print('  kerning {} (em {}):'.format(font.fontname, font.em))
    for name in sorted(bearings, key=SWARAS.index):
        print('    {}: lsb {:>5} rsb {:>5}'.format(
            name, bearings[name][0], bearings[name][1]))
    pairs = 0
    for kern, class_pairs in sorted(kerns.items()):
        for first, second in class_pairs:
            pairs += len(first) * len(second)
            print('    [{}][{}] {}'.format(
                ''.join(first), ''.join(second), kern))
    print('  {} kerned pairs'.format(pairs))
