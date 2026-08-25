# -*- coding: utf-8 -*-
"""Kan (grace note) rendering for the Ome Bhatkhande faces (issue #76).

A kan is written between braces -- `{m}srg`, `{sr}g` -- and should read as
a small raised note cluster leading into the swara it ornaments, the way
`<sup>` renders it on the web. This module bakes that into the font:

- For every swara, mark, and digit glyph, a `.kan` variant is added: a
  scaled reference to the original outline, raised above the midline, with
  a proportionally scaled advance. Ink stays identical, so each language's
  own letterforms drive the small forms automatically.
- The braces become zero-width, blank `.kan` variants inside a kan, so
  `{m}` paints exactly like `<sup>m</sup>` (the characters remain in the
  text for editing/copying -- they just take no space and leave no ink).
- A `calt` chained-context lookup (on by default in every browser and
  shaper) drives the substitutions: an opening brace followed by a kan
  glyph turns blank, any kan glyph after it is scaled, and the closing
  brace after a scaled glyph turns blank. Braces in any other context are
  untouched.
"""

# Glyphs that may appear inside a kan and get small raised variants.
SWARAS = ['s', 'r', 'g', 'm', 'p', 'd', 'n', 'R', 'G', 'M', 'D', 'N']
MARKS = ['l', 'L', 'u', 'U']                # komal / octave, zero-advance
DIGITS = ['one', 'two', 'three', 'four', 'five',
          'six', 'seven', 'eight', 'nine', 'zero']
KAN_GLYPHS = SWARAS + MARKS + DIGITS

SCALE = 0.60      # small-form size, relative to the full glyph
RAISE_EM = 0.34   # baseline raise of the small form, in em

SINGLE_LOOKUP = 'Kan small forms'
SINGLE_SUBTABLE = 'Kan small forms subtable'
CONTEXT_LOOKUP = 'Kan context'
MARK_KERN_LOOKUP = 'Kan mark kerning'
MARK_KERN_SUBTABLE = 'Kan mark kerning subtable'


def add_kan(font):
    """Add `.kan` variants and the brace-driven contextual substitution."""
    dy = int(round(RAISE_EM * font.em))

    for name in KAN_GLYPHS:
        small = font.createChar(-1, name + '.kan')
        small.clear()
        small.addReference(name, (SCALE, 0, 0, SCALE, 0, dy))
        small.width = int(round(font[name].width * SCALE))
    for name in ['braceleft', 'braceright']:
        blank = font.createChar(-1, name + '.kan')
        blank.clear()
        blank.width = 0

    font.addLookup(SINGLE_LOOKUP, 'gsub_single', (), ())
    font.addLookupSubtable(SINGLE_LOOKUP, SINGLE_SUBTABLE)
    for name in KAN_GLYPHS + ['braceleft', 'braceright']:
        font[name].addPosSub(SINGLE_SUBTABLE, name + '.kan')

    kannable = ' '.join(KAN_GLYPHS)
    kans = ' '.join(name + '.kan' for name in KAN_GLYPHS)
    font.addLookup(
        CONTEXT_LOOKUP,
        'gsub_contextchain',
        (),
        (('calt', (('DFLT', ('dflt',)), ('latn', ('dflt',)))),)
    )
    # Rules fire per position as the shaper walks the run, so each rule can
    # rely on the previous position already carrying its .kan form.
    font.addContextualSubtable(
        CONTEXT_LOOKUP, 'kan open', 'coverage',
        '| [braceleft] @<%s> | [%s]' % (SINGLE_LOOKUP, kannable))
    font.addContextualSubtable(
        CONTEXT_LOOKUP, 'kan run', 'coverage',
        '[braceleft.kan %s] | [%s] @<%s> |' % (kans, kannable, SINGLE_LOOKUP))
    font.addContextualSubtable(
        CONTEXT_LOOKUP, 'kan close', 'coverage',
        '[%s] | [braceright] @<%s> |' % (kans, SINGLE_LOOKUP))

    add_scaled_mark_kerns(font)
    print('  kan: {} small forms added'.format(len(KAN_GLYPHS)))


def add_scaled_mark_kerns(font):
    """The base font centers its zero-advance marks with a few GPOS kern
    pairs (r+l +100, M+u +190, ...). The `.kan` variants are new glyphs
    those pairs do not cover, so replicate each pair between the small
    forms, scaled along with them."""
    pairs = []
    for base in KAN_GLYPHS:
        for entry in font[base].getPosSub('*'):
            if entry[1] == 'Pair' and entry[2] in KAN_GLYPHS:
                pairs.append((base, entry[2], entry[3:]))
    if not pairs:
        return
    font.addLookup(
        MARK_KERN_LOOKUP,
        'gpos_pair',
        (),
        (('kern', (('DFLT', ('dflt',)), ('latn', ('dflt',)))),)
    )
    font.addLookupSubtable(MARK_KERN_LOOKUP, MARK_KERN_SUBTABLE)
    for base, other, values in pairs:
        scaled = [int(round(v * SCALE)) for v in values]
        font[base + '.kan'].addPosSub(
            MARK_KERN_SUBTABLE, other + '.kan', *scaled)
    print('  kan: {} mark kern pairs scaled'.format(len(pairs)))
