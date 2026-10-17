"""Name normalization for the player ID mapping. Both sides go through
`normalize()`, so "Martin Ødegaard", "martin-odegaard" and "ØDEGAARD, M."
all reduce to plain lowercase ASCII words.
"""

import re
import unicodedata

# Letters NFKD does not split into base letter + accent.
_TRANSLITERATE = str.maketrans(
    {
        "ø": "o",
        "Ø": "o",
        "đ": "d",
        "Đ": "d",
        "ł": "l",
        "Ł": "l",
        "ı": "i",
        "ß": "ss",
        "æ": "ae",
        "Æ": "ae",
        "œ": "oe",
        "Œ": "oe",
        "þ": "th",
        "ð": "d",
    }
)
# Apostrophes join ("Jun'ai" -> "junai"); any other non-letter splits words.
_APOSTROPHES = re.compile(r"['’`´]")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(name: str | None) -> str:
    """Lowercase ASCII words separated by single spaces. Accents stripped,
    hyphens and dots become spaces ("Lewis-Skelly" -> "lewis skelly",
    "B.Fernandes" -> "b fernandes")."""
    if not name:
        return ""
    text = name.translate(_TRANSLITERATE)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = _APOSTROPHES.sub("", text)
    return _NON_WORD.sub(" ", text).strip()


def tokens(name: str | None) -> list[str]:
    return normalize(name).split()


def order_free(name: str | None) -> str:
    """Words sorted, so name order does not matter ("Son Heung-min" ==
    "Heung-min Son", "Tóth.A" == "A. Tóth")."""
    return " ".join(sorted(tokens(name)))


def initial_and_surname(short_name: str | None) -> tuple[str, list[str]] | None:
    """Split a source short name like "B. Saka" or "J. P. van Hecke" into
    the first initial and the surname words. None if it does not start
    with an initial."""
    words = tokens(short_name)
    if len(words) < 2 or len(words[0]) != 1:
        return None
    surname = [w for w in words[1:] if len(w) > 1]
    if not surname:
        return None
    return words[0], surname


def contains_run(words: list[str], run: list[str]) -> bool:
    """`run` appears in `words` as consecutive words."""
    n = len(run)
    return any(words[i : i + n] == run for i in range(len(words) - n + 1))
