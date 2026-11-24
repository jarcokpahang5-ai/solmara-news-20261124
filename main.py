#!/usr/bin/env python3
"""Solmara Daily -- 24 November 2026 world news poster.

Draws a 1024x1024 newspaper front page as a PNG using only the Python
standard library (zlib + struct for the PNG encoder, a hand-built 3x5
bitmap font for text). No network, no third-party packages.
Deterministic: identical input always produces identical bytes.
SPDX-License-Identifier: MIT
"""
import os
import struct
import zlib

W, H = 1024, 1024

# --- palette ---------------------------------------------------------------
PAPER = (250, 246, 236)
INK = (24, 30, 46)
RED = (176, 32, 26)
TEAL = (13, 92, 99)
GOLD = (182, 138, 44)
LIGHT = (232, 225, 206)
GREY = (118, 114, 102)
WHITE = (255, 255, 255)
SKY = (214, 226, 232)
SEA = (31, 84, 96)
SMOKE = (150, 146, 136)
FIRE = (224, 92, 34)

# --- 3x5 bitmap font, designed for this poster -----------------------------
# Each glyph: 5 rows of 3 bits, '#' = on. Uppercase only; text is uppercased.
FONT = {
    'A': ("010", "101", "111", "101", "101"),
    'B': ("110", "101", "110", "101", "110"),
    'C': ("011", "100", "100", "100", "011"),
    'D': ("110", "101", "101", "101", "110"),
    'E': ("111", "100", "110", "100", "111"),
    'F': ("111", "100", "110", "100", "100"),
    'G': ("011", "100", "101", "101", "011"),
    'H': ("101", "101", "111", "101", "101"),
    'I': ("111", "010", "010", "010", "111"),
    'J': ("001", "001", "001", "101", "010"),
    'K': ("101", "101", "110", "101", "101"),
    'L': ("100", "100", "100", "100", "111"),
    'M': ("101", "111", "111", "101", "101"),
    'N': ("101", "111", "101", "101", "101"),
    'O': ("010", "101", "101", "101", "010"),
    'P': ("110", "101", "110", "100", "100"),
    'Q': ("010", "101", "101", "110", "011"),
    'R': ("110", "101", "110", "101", "101"),
    'S': ("011", "100", "010", "001", "110"),
    'T': ("111", "010", "010", "010", "010"),
    'U': ("101", "101", "101", "101", "111"),
    'V': ("101", "101", "101", "101", "010"),
    'W': ("101", "101", "101", "111", "101"),
    'X': ("101", "101", "010", "101", "101"),
    'Y': ("101", "101", "010", "010", "010"),
    'Z': ("111", "001", "010", "100", "111"),
    '0': ("011", "101", "101", "101", "110"),
    '1': ("010", "110", "010", "010", "111"),
    '2': ("110", "001", "010", "100", "111"),
    '3': ("110", "001", "010", "001", "110"),
    '4': ("101", "101", "111", "001", "001"),
    '5': ("111", "100", "110", "001", "110"),
    '6': ("011", "100", "110", "101", "010"),
    '7': ("111", "001", "010", "010", "010"),
    '8': ("010", "101", "010", "101", "010"),
    '9': ("010", "101", "011", "001", "110"),
    '.': ("000", "000", "000", "000", "010"),
    ',': ("000", "000", "000", "010", "100"),
    "'": ("010", "010", "000", "000", "000"),
    '-': ("000", "000", "111", "000", "000"),
    ':': ("000", "010", "000", "010", "000"),
    ';': ("000", "010", "000", "010", "100"),
    '!': ("010", "010", "010", "000", "010"),
    '?': ("110", "001", "010", "000", "010"),
    '(': ("001", "010", "010", "010", "001"),
    ')': ("100", "010", "010", "010", "100"),
    '/': ("001", "001", "010", "100", "100"),
    '%': ("101", "001", "010", "100", "101"),
    '&': ("010", "101", "010", "101", "011"),
    '+': ("000", "010", "111", "010", "000"),
    '=': ("000", "111", "000", "111", "000"),
    '*': ("000", "101", "010", "101", "000"),
    '$': ("010", "111", "010", "111", "010"),
    ' ': ("000", "000", "000", "000", "000"),
}
EMPTY = ("000", "000", "000", "000", "000")


def glyph_width(scale):
    return 4 * scale


def measure(text, scale):
    """Pixel width of text at given scale (4 px advance per char)."""
    return len(text) * glyph_width(scale)


def wrap(text, max_width, scale):
    """Greedy word wrap; returns list of lines."""
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else cur + " " + word
        if measure(trial, scale) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# --- page ------------------------------------------------------------------
class Page:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def dot(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def box(self, x, y, w, h, color):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.dot(xx, yy, color)

    def rule(self, x, y, w, color, thick=1):
        self.box(x, y, w, thick, color)

    def put(self, x, y, text, scale, color):
        cx = x
        for ch in text.upper():
            bits = FONT.get(ch, EMPTY)
            for row in range(5):
                for col in range(3):
                    if bits[row][col] == '1':
                        self.box(cx + col * scale, y + row * scale,
                                 scale, scale, color)
            cx += glyph_width(scale)
        return cx

    def centred(self, cx, y, text, scale, color):
        x = cx - measure(text, scale) // 2
        return self.put(x, y, text, scale, color)

    def block(self, x, y, text, scale, color, max_width, leading=None):
        if leading is None:
            leading = 7 * scale
        for line in wrap(text, max_width, scale):
            self.put(x, y, line, scale, color)
            y += leading
        return y


# --- PNG writer ------------------------------------------------------------
def save_png(path, page):
    raw = bytearray()
    stride = page.w * 3
    for y in range(page.h):
        raw.append(0)
        start = y * stride
        raw += page.px[start:start + stride]
    packed = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", page.w, page.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", packed)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# --- content: Tuesday 24 November 2026 -------------------------------------
LEAD = {
    "kicker": "UKRAINE WAR SPREADS",
    "headline": "RUSSIAN WARSHIP BURNS IN LIBYA PORT",
    "summary": ("A naval drone strike reportedly destroyed the corvette "
                "Merkury at Benghazi, opening the war's newest front far "
                "from Ukraine's shores."),
}

STORIES = [
    {
        "kicker": "MARKETS",
        "color": TEAL,
        "headline": "HUANG RETURNS AS NVIDIA SOARS",
        "summary": ("Nvidia climbs almost $1tn as Jensen Huang returns; "
                    "Trump says he spoke to the board."),
    },
    {
        "kicker": "ASIA",
        "color": RED,
        "headline": "TRUMP-KIM TALKS STALL",
        "summary": ("Pyongyang ignores Trump's bids to revive dialogue "
                    "as the North expands its nuclear arsenal."),
    },
    {
        "kicker": "MIDDLE EAST",
        "color": RED,
        "headline": "GAZA POISONED FOR DECADES",
        "summary": ("Oxfam report: explosives and heavy metals leave "
                    "Gaza's air, soil and water toxic."),
    },
    {
        "kicker": "ENERGY",
        "color": TEAL,
        "headline": "TANKERS HIT IN HORMUZ",
        "summary": ("Two tankers struck in the strait as Iran vows to "
                    "counter a US blockade."),
    },
]

WIDE = {
    "kicker": "THE HAGUE",
    "color": GOLD,
    "headline": "ICJ: MYANMAR GUILTY OF GENOCIDE",
    "summary": ("The court holds Myanmar responsible for the Rohingya "
                "genocide, nine votes to six."),
}

BRIEFS = [
    "DENMARK COURT BACKS GHETTO LAW.",
    "FIFA PICKS 2031, 2035 WOMEN'S HOSTS.",
    "SUPERMOON MEETS THE SEVEN SISTERS.",
    "UN CHIEF SEEKS AI SAFETY PACT.",
    "S. KOREA: DRONES BREACH AIRSPACE.",
    "FACTORY FIRE KILLS 30 IN INDONESIA.",
    "DE BRUYNE: FEELINGS NEVER CHANGE.",
]


# --- layout ----------------------------------------------------------------
def draw_harbour(page, x, y, w, h):
    """Stylised harbour at dusk: sky, sea, a burning ship, smoke."""
    sky_h = h * 2 // 5
    page.box(x, y, w, sky_h, SKY)
    page.box(x, y + sky_h, w, h - sky_h, SEA)
    # sun low on the horizon
    page.box(x + w - 130, y + 12, 54, 54, GOLD)
    # ship hull and deck
    hull_y = y + sky_h + 26
    page.box(x + 60, hull_y, w - 220, 34, INK)
    page.box(x + 120, hull_y - 34, 150, 34, INK)
    page.box(x + 150, hull_y - 58, 18, 26, INK)
    page.box(x + 210, hull_y - 58, 18, 26, INK)
    # fire glow on the deck
    page.box(x + 300, hull_y - 14, 90, 14, FIRE)
    page.box(x + 320, hull_y - 26, 50, 12, FIRE)
    # smoke rising in blocks
    page.box(x + 320, y + 8, 30, 26, SMOKE)
    page.box(x + 336, y + 2, 22, 18, SMOKE)
    page.box(x + 300, y + 30, 18, 18, SMOKE)
    # harbour wall
    page.box(x, y + h - 12, w, 12, INK)


def story(page, x, top, item, width):
    page.box(x, top, width, 3, item["color"])
    page.put(x, top + 10, item["kicker"], 2, item["color"])
    hy = page.block(x, top + 34, item["headline"], 3, INK, width,
                    leading=26)
    page.block(x, hy + 4, item["summary"], 2, GREY, width, leading=20)


def build():
    p = Page(W, H, PAPER)
    M = 36
    inner = W - 2 * M

    # --- masthead ----------------------------------------------------------
    p.rule(M, 26, inner, INK, 4)
    p.centred(W // 2, 44, "THE SOLMARA DAILY", 7, INK)
    p.rule(M, 108, inner, RED, 3)
    p.put(M, 122, "TUESDAY 24 NOVEMBER 2026", 2, RED)
    right = "WORLD NEWS  |  ONE PAGE"
    p.put(W - M - measure(right, 2), 122, right, 2, GREY)
    p.rule(M, 146, inner, INK, 2)

    # --- lead story --------------------------------------------------------
    y = 162
    p.box(M, y, inner, 8, RED)
    y += 16
    p.put(M, y, LEAD["kicker"], 2, RED)
    y += 24
    y = p.block(M, y, LEAD["headline"], 5, INK, inner, leading=38)
    y += 6
    y = p.block(M, y, LEAD["summary"], 3, INK, inner, leading=28)
    y += 10
    draw_harbour(p, M, y, inner, 96)
    y += 96 + 10
    p.rule(M, y, inner, INK, 2)
    y += 14

    # --- story grid: 2 columns x 2 rows ------------------------------------
    gap = 20
    col_w = (inner - gap) // 2
    for row in range(2):
        a, b = STORIES[row * 2], STORIES[row * 2 + 1]
        story(p, M, y, a, col_w)
        story(p, M + col_w + gap, y, b, col_w)
        y += 128
        if row == 0:
            y += 4
            p.rule(M, y, inner, LIGHT, 2)
            y += 8
    y += 6

    # --- wide story ----------------------------------------------------------
    p.rule(M, y, inner, GOLD, 3)
    p.put(M, y + 12, WIDE["kicker"], 2, WIDE["color"])
    hy = p.block(M, y + 36, WIDE["headline"], 3, INK, inner, leading=26)
    y = p.block(M, hy + 4, WIDE["summary"], 2, GREY, inner, leading=20)
    y += 10
    p.rule(M, y, inner, INK, 2)
    y += 12

    # --- briefs ------------------------------------------------------------
    p.box(M, y, 150, 30, INK)
    p.put(M + 12, y + 8, "BRIEFS", 2, WHITE)
    y += 40
    half = (len(BRIEFS) + 1) // 2
    bottom = y
    for col in range(2):
        by = y
        for i in range(col * half, min((col + 1) * half, len(BRIEFS))):
            x = M + col * (col_w + gap)
            p.box(x, by + 3, 8, 8, RED if col == 0 else TEAL)
            by = p.block(x + 16, by, BRIEFS[i], 2, INK, col_w - 16,
                         leading=18)
            by += 6
        bottom = max(bottom, by)
    y = bottom + 2

    # --- footer ------------------------------------------------------------
    p.rule(M, H - 52, inner, INK, 2)
    p.centred(W // 2, H - 40,
              "ALL STORIES VERIFIED FROM PUBLIC REPORTING", 2, GREY)
    p.centred(W // 2, H - 22,
              "THE SOLMARA DAILY  -  24 NOVEMBER 2026", 2, GREY)
    assert y < H - 52, "layout overflow: content ends at %d" % y
    return p


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "entry.png")
    page = build()
    save_png(out, page)
    print("wrote", out)


if __name__ == "__main__":
    main()
