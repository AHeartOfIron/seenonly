"""Sentences that talk to an AI instead of to a reader.

A list of phrases is a speed bump, not a wall: an attacker can always reword. It still catches what
is actually copied around, in ten languages, through the usual disguises (look-alike letters, spaced
letters, punctuation between words, base64). Hidden text is removed whatever it says; this module
exists for the instructions that are in plain sight.
"""
from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from typing import List, Optional, Tuple

# Latin look-alikes among Cyrillic, Greek and fullwidth letters, for words that mix alphabets.
_LOOKALIKE = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s", "һ": "h",
    "ԁ": "d", "ɡ": "g", "ո": "n", "ν": "v", "ο": "o", "α": "a", "ρ": "p", "ι": "i", "κ": "k", "τ": "t", "ѵ": "v",
})
_LATIN = re.compile(r"[a-z]")
_CYR_GREEK = re.compile(r"[Ͱ-ϿЀ-ԯ]")
_LETTER_RUN = re.compile(r"\b(?:\w[ ._\-*]){3,}\w\b")


def _plain(c: str) -> str:
    base = unicodedata.normalize("NFKD", c)[0]
    return base if base.isascii() else c


def fold(text: str) -> str:
    """Lower case, no accents, no punctuation, one alphabet per word, spaced letters closed up."""
    # Accents go from Latin letters only: in Cyrillic, "й" is its own letter, not a marked "и".
    s = "".join(_plain(c) for c in unicodedata.normalize("NFKC", text)).casefold()
    s = _LETTER_RUN.sub(lambda m: re.sub(r"[ ._\-*]", "", m.group()), s)
    words = []
    for w in re.split(r"[^\w]+|_+", s):
        if w:
            words.append(w.translate(_LOOKALIKE) if _LATIN.search(w) and _CYR_GREEK.search(w) else w)
    return " ".join(words)


_NOT = r"(?<!\bnot )(?<!\bdon t )(?<!\bdont )(?<!\bnever )(?<!\bне )(?<!\bnicht )(?<!\bpas )(?<!\bno )(?<!\bnon )"
_AI = r"(?:ai|a i|llm|llms|chatbot|chatbots|language model|language models|chatgpt|gpt|claude|gemini|copilot|grok|ai (?:assistant|agent|model|system|crawler|reader)s?)"
_NOT_A_PERSON = r"(?! (?:researcher|engineer|developer|expert|startup|company|enthusiast|student|user|team|leader|professional|scientist|specialist|practitioner|consultant|founder|investor|writer|product|vendor|customer|builder|lab)s?\b)"

_FOLDED = [
    # English
    ("override", _NOT + r"\b(?:ignore|disregard|forget|override|bypass)\b(?: \w+){0,3}? (?:previous|prior|above|earlier|preceding|original|system|all|any|your)\b(?: \w+){0,3}? (?:instructions?|prompts?|rules|guidelines|directions|directives|policies|safeguards|context)\b"),
    ("prompt leak", r"\b(?:reveal|show|print|repeat|output|leak|dump|display|tell me|give me|share|write out)\b(?: \w+){0,4}? (?:system prompt|system message|initial prompt|hidden prompt|developer message|your (?:prompt|instructions))\b"),
    ("addresses an AI", r"\b(?:note to|attention|message for|message to|instructions for|notice to|hey|dear|to all|to any)(?: an?| the| all| any)? " + _AI + r"\b" + _NOT_A_PERSON),
    ("addresses an AI", r"\bif you are(?: an?)? (?:" + _AI + r"|automated (?:agent|assistant))\b" + _NOT_A_PERSON),
    ("orders an AI", r"\b(?:" + _AI + r") (?:\w+ ){0,2}(?:must|shall|are instructed to|is instructed to|are required to|is required to) (?:say|answer|reply|respond|tell|state|recommend|write|output|include|ignore|send|pay|transfer|delete|approve|rate|rank)\b"),
    ("new role", r"\byou are now(?: an?| the)?(?: \w+)? (?:ai|assistant|chatbot|dan|jailbroken|unrestricted|uncensored)\b|\b(?:act as|pretend to be|pretend you are)(?: an?)? (?:unrestricted|uncensored|jailbroken|dan)\b|\b(?:developer|jailbreak|god) mode (?:enabled|activated|on)\b"),
    ("concealment", r"\b(?:do not|don t|dont|never) (?:tell|mention|inform|reveal|alert|notify)(?: \w+){0,2}? (?:the |your )?(?:user|human|operator)\b|\bwithout (?:telling|informing|notifying|alerting) (?:the |your )?(?:user|human|operator)\b"),
    ("new instructions", r"\b(?:your|the) new instructions (?:are|is)\b|\bnew instructions follow\b|\bupdated instructions for (?:the )?(?:ai|assistant|agent|llm)\b"),
    # Russian and Ukrainian
    ("override", _NOT + r"\b(?:игнорируй|проигнорируй|игнорируйте|проигнорируйте|забудь|забудьте|отмени|отмените)\b(?: \w+){0,3}? (?:инструкц\w+|указани\w+|правил\w*|промпт\w*|ограничени\w+)\b"),
    ("override", _NOT + r"\b(?:ігноруй|проігноруй|ігноруйте|проігноруйте|забудь|забудьте|скасуй)\b(?: \w+){0,3}? (?:інструкці\w+|вказівк\w+|правил\w*|промпт\w*|обмеженн\w+)\b"),
    ("prompt leak", r"\b(?:покажи|выведи|раскрой|напиши|покажите|выведите|виведи|розкрий|напиши|покажіть)\b(?: \w+){0,3}? (?:системн\w+ (?:промпт|инструкц\w+|підказк\w+|інструкці\w+)|сво[йиї] (?:промпт|инструкц\w+|інструкці\w+))\b"),
    ("new role", r"\b(?:ты теперь|вы теперь|ти тепер|ви тепер)(?: \w+)? (?:ии|ші|ассистент|асистент|чат бот|чатбот|без ограничений|без обмежень)\b"),
    ("concealment", r"\b(?:не говори|не сообщай|не упоминай|не кажи|не повідомляй|не згадуй)(?: \w+){0,2}? (?:пользовател\w+|користувач\w+)\b"),
    # French
    ("override", r"\b(?:ignore|ignorez|oublie|oubliez)\b(?: toutes?)? (?:les|vos|tes)\b(?: \w+){0,2}? (?:instructions|consignes|directives)(?: \w+)?\b"),
    ("prompt leak", r"\b(?:revele|revelez|affiche|affichez|montre|montrez)\b(?: \w+){0,3}? (?:prompt systeme|invite systeme|instructions systeme|vos instructions|tes instructions)\b"),
    # German
    ("override", _NOT + r"\b(?:ignoriere|ignorier|ignorieren sie|vergiss|vergessen sie)\b(?: \w+){0,3}? (?:anweisungen|vorgaben|regeln|anordnungen|instruktionen)\b"),
    ("prompt leak", r"\b(?:zeige|zeig|gib|nenne)\b(?: \w+){0,3}? (?:system ?prompt|systemanweisungen?|deine anweisungen)\b"),
    # Spanish, Italian, Portuguese, Polish
    ("override", r"\b(?:ignora|ignore|ignorar|ignoren|olvida|olvide|olvidar)\b(?: todas?)? (?:las|tus|sus)\b(?: \w+){0,2}? (?:instrucciones|indicaciones|directrices)\b"),
    ("prompt leak", r"\b(?:revela|muestra|imprime|repite)\b(?: \w+){0,3}? (?:prompt del sistema|instrucciones del sistema|tus instrucciones)\b"),
    ("override", r"\b(?:ignora|ignorate|dimentica|dimenticate)\b(?: tutte)? (?:le|tue)\b(?: \w+){0,2}? (?:istruzioni|indicazioni|direttive)\b"),
    ("override", r"\b(?:ignore|ignora|ignorar|esqueca|esquece)\b(?: todas)? (?:as|suas)\b(?: \w+){0,2}? (?:instrucoes|diretrizes|orientacoes)\b"),
    ("override", r"\b(?:zignoruj|zignorujcie|ignoruj|zapomnij)\b(?: \w+){0,3}? (?:instrukcje|polecenia|wytyczne|zasady)\b"),
    # Chinese
    ("override", r"(?:忽略|无视|忽视|忘记|忘掉)(?:\w| ){0,8}(?:指令|指示|提示词|规则)"),
    ("prompt leak", r"(?:显示|输出|告诉我|透露)(?:\w| ){0,8}系统提示"),
]
_FOLDED_RE = [(label, re.compile(p)) for label, p in _FOLDED]

_RAW = [
    ("chat template token", r"<\|\s*(?:im_start|im_end|system|endoftext|eot_id|start_header_id)\s*\|>|\[/?INST\]|<<\s*/?SYS\s*>>"),
    ("role tag", r"</?\s*(?:system|assistant|instructions?)\s*>"),
    ("role header", r"(?im)^\s*#{2,}\s*(?:system|instructions?)\s*:?\s*$"),
    ("new instructions", r"(?i)\bnew (?:system )?instructions\s*:"),
    ("data exfiltration link", r"!\[[^\]\n]*\]\(\s*https?://[^)\s]*\?[^)\s]*\)"),
]
_RAW_RE = [(label, re.compile(p)) for label, p in _RAW]
_B64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])")
_SENTENCE = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def _detect_plain(text: str) -> Optional[str]:
    for label, rx in _RAW_RE:
        if rx.search(text):
            return label
    folded = fold(text)
    for label, rx in _FOLDED_RE:
        if rx.search(folded):
            return label
    return None


def detect(text: str) -> Optional[str]:
    """What kind of injection this text looks like, or None."""
    if not text or not text.strip():
        return None
    found = _detect_plain(text)
    if found:
        return found
    for m in _B64.finditer(text):
        tok = m.group()
        try:
            raw = base64.b64decode(tok + "=" * (-len(tok) % 4))
            decoded = raw.decode("utf-8")
        except (binascii.Error, ValueError):
            continue
        if decoded.isprintable() or "\n" in decoded:
            found = _detect_plain(decoded)
            if found:
                return "base64: " + found
    return None


def strip_sentences(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """(text without the sentences that match, [(what matched, the sentence)])."""
    label = detect(text)
    if not label:
        return text, []
    keep: List[str] = []
    hits: List[Tuple[str, str]] = []
    pos = 0
    for m in list(_SENTENCE.finditer(text)) + [None]:
        end = m.start() if m else len(text)
        sentence = text[pos:end]
        sep = m.group() if m else ""
        hit = detect(sentence)
        if hit:
            hits.append((hit, sentence.strip()))
        else:
            keep.append(sentence + sep)
        pos = m.end() if m else pos
    if not hits:  # the words were spread over sentences on purpose: the whole block goes
        return "", [(label, text.strip())]
    return "".join(keep).strip(), hits
