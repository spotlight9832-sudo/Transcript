"""
Shared text-chunking logic used by every content source (YouTube, RedNote, ...).

Telegram hard-limits a single message to 4096 characters, and 3000 real
words is almost always well beyond that. So a chunk ends at whichever
limit is hit first. Either way, a chunk only ever ends on a finished word,
never in the middle of one.
"""

MAX_WORDS_PER_CHUNK = 3000
MAX_CHARS_PER_CHUNK = 3900


def chunk_text(
    text: str,
    max_words: int = MAX_WORDS_PER_CHUNK,
    max_chars: int = MAX_CHARS_PER_CHUNK,
) -> list[str]:
    """Splits text on whitespace into chunks of at most `max_words` words
    AND at most `max_chars` characters (whichever limit is hit first).
    A chunk boundary only ever falls between two words, never inside one."""
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0

    for word in words:
        extra = len(word) + (1 if current else 0)  # +1 for the joining space
        if current and (len(current) + 1 > max_words or current_chars + extra > max_chars):
            chunks.append(" ".join(current))
            current = [word]
            current_chars = len(word)
        else:
            current.append(word)
            current_chars += extra

    if current:
        chunks.append(" ".join(current))

    return chunks
