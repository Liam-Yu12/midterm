"""Derive a short session name from the user's first message, locally (no LLM call).

Heuristic: first sentence -> drop a leading greeting / filler phrase ("what are some",
"help me", "can you", ...) -> drop low-information words -> at most MAX_WORDS words
without a dangling "to/for/and/..." -> at most MAX_LENGTH characters. The first
letter is capitalised only when a filler prefix was removed, so "hello" stays
"hello". Falls back to the raw first words, then to the default session name.
"""
import re

MAX_WORDS = 6
MAX_LENGTH = 60
FALLBACK = 'Untitled session'

_GREETING = re.compile(r'^(?:hi|hey|hello|hiya|good (?:morning|afternoon|evening))(?: there)?\b[\s,!.]*', re.I)

# Longest phrases first, so "what are some" wins over "what are".
_FILLER_PREFIXES = [
    r'is there a way to', r'i need you to', r'i want you to', r'i would like to', r"i'd like to",
    r'what are some', r'what are the', r'what is the', r"what's the", r'what are', r'what is', r"what's",
    r'can you help me(?: to)?', r'could you help me(?: to)?', r'help me(?: to)?',
    r'can you tell me(?: about)?', r'tell me(?: about)?', r'give me', r'show me',
    r'how do i', r'how can i', r'how to', r'i want to', r'i need to',
    r'can you', r'could you', r'would you', r'will you', r"let's", r'lets', r'please',
]
_FILLER = re.compile(r'^(?:' + '|'.join(_FILLER_PREFIXES) + r')\b[\s,]*', re.I)

_DROP_WORDS = {'a', 'an', 'the', 'my', 'our', 'your', 'some', 'any', 'good', 'nice', 'really', 'very',
               'just', 'me', 'please'}
_NO_TRAILING = {'to', 'for', 'and', 'or', 'of', 'in', 'on', 'at', 'with', 'about', 'from', 'by',
                'is', 'are', 'a', 'an', 'the', 'my', 'whether', 'that', 'if', 'which', 'who', 'how', 'what'}
_EDGE_PUNCTUATION = '.,;:!?"\'()[]{}«»“”‘’'


def _words(text):
    words = (w.strip(_EDGE_PUNCTUATION) for w in text.split())
    return [w for w in words if any(ch.isalnum() for ch in w)]


def _truncate(name):
    if len(name) <= MAX_LENGTH:
        return name
    cut = name[:MAX_LENGTH - 1]
    if ' ' in cut:
        cut = cut[:cut.rindex(' ')]
    return cut.rstrip() + '…'


def suggest_session_name(message):
    """Return a short (<= MAX_WORDS words, <= MAX_LENGTH chars) name for a chat session."""
    text = ' '.join((message or '').split())  # collapse all whitespace
    if not text:
        return FALLBACK

    body = _GREETING.sub('', text, count=1) or text  # keep a greeting if it's all there is
    body = re.split(r'(?<=[.!?:])\s', body, maxsplit=1)[0].rstrip(':')  # first sentence/clause only

    stripped = False
    while True:
        rest = _FILLER.sub('', body, count=1)
        if rest == body or not _words(rest):
            break
        body, stripped = rest, True

    words = _words(body)
    # Drop low-information words; keep the user's own first word unless it follows a
    # stripped filler ("What are some good ..." -> "Study ...", but "My name is ..." stays).
    content = [w for i, w in enumerate(words)
               if w.lower() not in _DROP_WORDS or (i == 0 and not stripped)]
    words = (content or words)[:MAX_WORDS]
    while len(words) > 1 and words[-1].lower() in _NO_TRAILING:
        words.pop()

    if not words:  # nothing useful left: fall back to the raw first words
        words = _words(text)[:MAX_WORDS]
        stripped = False
    if not words:
        return FALLBACK

    name = ' '.join(words)
    if stripped:
        name = name[0].upper() + name[1:]
    return _truncate(name)
