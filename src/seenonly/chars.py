"""Characters a reader never sees.

Removing them must not break text. ZWJ joins emoji and Indic letters, ZWNJ is correct spelling
in Persian, a variation selector turns a symbol into an emoji, and the flag of England is spelled
with Unicode tag characters. These stay where they belong and go everywhere else.
"""
from __future__ import annotations

import re
from typing import List, Tuple

_ALWAYS = set(
    [0x00AD, 0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180C, 0x180D, 0x180E, 0x200B, 0x2060, 0x2061, 0x2062,
     0x2063, 0x2064, 0x2065, 0x3164, 0xFEFF, 0xFFA0, 0xFFF9, 0xFFFA, 0xFFFB, 0x1BCA0, 0x1BCA1, 0x1BCA2, 0x1BCA3]
    + list(range(0x206A, 0x2070))
    + list(range(0x1D173, 0x1D17B))
)
_BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
_JOINERS = {0x200C, 0x200D}
_MARKS = {0x200E, 0x200F, 0x061C}
_TAG = range(0xE0000, 0xE0080)
_VS_LOW = range(0xFE00, 0xFE10)
_VS_HIGH = range(0xE0100, 0xE01F0)
_BLACK_FLAG = 0x1F3F4
_SPACES = dict.fromkeys(list(range(0x2000, 0x200B)) + [0x00A0, 0x202F, 0x205F, 0x3000, 0x2028, 0x2029], " ")
_ANY = re.compile(
    "[­͏؜ᅟᅠ឴឵᠋-᠎​-‏‪-‮⁠-⁯ㅤ︀-️"
    "﻿ﾠ￹-￻\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e007f\U000e0100-\U000e01ef"
    "\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)
# Scripts below this code point (Latin, Greek, Cyrillic, Armenian) never need a joiner or a mark.
_SCRIPT_NEEDS_JOINERS = 0x0590


def _is_vs(cp: int) -> bool:
    return cp in _VS_LOW or cp in _VS_HIGH


def _vs_byte(cp: int) -> int:
    return cp - 0xFE00 if cp in _VS_LOW else cp - 0xE0100 + 16


def clean_chars(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """(text without invisible characters, [(reason, what it hid)])."""
    if not _ANY.search(text):
        return text.translate(_SPACES), []
    out: List[str] = []
    found: List[Tuple[str, str]] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        cp = ord(ch)
        if cp in _TAG:
            j = i
            while j < n and ord(text[j]) in _TAG:
                j += 1
            run = text[i:j]
            if out and ord(out[-1][-1]) == _BLACK_FLAG and ord(run[-1]) == 0xE007F:
                out.append(run)  # a subdivision flag: England, Scotland, Wales
            else:
                decoded = "".join(chr(ord(c) - 0xE0000) for c in run if 0x20 <= ord(c) - 0xE0000 < 0x7F)
                found.append(("unicode tag characters", decoded))
            i = j
        elif _is_vs(cp):
            j = i
            while j < n and _is_vs(ord(text[j])):
                j += 1
            prev = ord(text[i - 1]) if i else 0
            if j - i == 1 and prev >= 0x2190:
                out.append(ch)  # a real variation: an emoji, or a CJK ideograph variant
            elif j - i >= 4:
                raw = bytes(_vs_byte(ord(c)) for c in text[i:j])
                found.append(("variation selector smuggling", raw.decode("utf-8", "replace")))
            i = j
        elif cp in _JOINERS or cp in _MARKS:
            j = i
            while j < n and ord(text[j]) in (_JOINERS | {0x200B, 0x2060, 0xFEFF}):
                j += 1
            if j - i >= 4:
                found.append(("run of zero-width characters", f"{j - i} characters"))
            else:
                prev = ord(text[i - 1]) if i else 0
                nxt = ord(text[i + 1]) if i + 1 < n else 0
                if j - i == 1 and (prev >= _SCRIPT_NEEDS_JOINERS or nxt >= _SCRIPT_NEEDS_JOINERS):
                    out.append(ch)
            i = j if j > i else i + 1
        elif cp in _ALWAYS:
            j = i
            while j < n and ord(text[j]) in (_ALWAYS | _JOINERS):
                j += 1
            if j - i >= 4 and cp != 0x00AD:
                found.append(("run of zero-width characters", f"{j - i} characters"))
            i = j
        elif cp in _BIDI:
            if cp == 0x202E:
                found.append(("right-to-left override", ""))
            i += 1
        elif cp < 32 and ch not in "\t\n\r" or 0x7F <= cp <= 0x9F:
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out).translate(_SPACES), found
