"""Chat-Filter: erkennt Schimpfwörter, sexuelle Belästigung, Hass/Extremismus und Bedrohungen – auch in Tarnschreibweisen.

Vorgehen
  1. Text in eine "Grundform" (skeleton) umwandeln: Kleinschreibung, Akzente weg, unsichtbare Zeichen weg, Look-alikes aus
     kyrillisch/griechisch → lateinisch, Leetspeak (sh1t, $hit), Zeichen wie * # als Platzhalter (f*ck), lange
     Buchstabenfolgen (fuuuuuck) werden gekürzt.
  2. Jede Wortlistenzeile wird zu einem regulären Ausdruck, der Wiederholungen (u+), Trennzeichen zwischen den Buchstaben
     (f.u.c.k, f_u_c_k), einzeln getippte Buchstaben (f u c k) und Platzhalter zulässt.
  3. Ganze-Wort-Prüfung für kurze/mehrdeutige Wörter ("class" enthält "ass" – das ist kein Treffer).

Dieselben Muster werden per tools/gen_filter_sql.py auch in die Datenbank geschrieben (öffentliche Texte: Forum, Namen).
Ehrlich: Kein Filter ist lückenlos. Wer es darauf anlegt (Bilder, neue Schreibweisen, andere Sprachen), kommt vorbei.
Bei Ende-zu-Ende-verschlüsselten Chats kann nur der Client filtern – ein veränderter Client könnte das umgehen.
Darum filtert auch der Empfänger beim Anzeigen noch einmal (mask).
"""
import re
import unicodedata
from dataclasses import dataclass

from core import chatfilter_words as WL
from core.i18n import tr

WILD = ""
WILD_CHARS = "*#•·×%^~"
SYMBOLS = {"@": "a", "$": "s", "!": "i", "|": "i", "+": "t", "¡": "i", "€": "e", "£": "e", "¢": "c", "©": "c", "§": "s", "°": "o",
           "¥": "y", "µ": "u"}
# Buchstaben-Look-alikes und Leetspeak (immer aktiv). "" = Zeichen entfernen.
LETTERS = {
    # kyrillisch (Aussehen vor Aussprache, wo beides geht)
    "а": "a", "б": "b", "в": "b", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "j", "з": "z", "и": "i", "й": "i", "к": "k",
    "л": "l", "м": "m", "н": "h", "о": "o", "п": "p", "р": "p", "с": "c", "т": "t", "у": "y", "ф": "f", "х": "x", "ц": "c",
    "ч": "c", "ш": "w", "щ": "w", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "u", "я": "a", "і": "i", "ї": "i", "є": "e",
    "ґ": "g", "ѕ": "s", "ј": "j", "һ": "h", "ԁ": "d",
    # griechisch
    "α": "a", "β": "b", "γ": "y", "ε": "e", "ζ": "z", "η": "n", "ι": "i", "κ": "k", "μ": "m", "ν": "u", "ο": "o", "π": "n",
    "ρ": "p", "σ": "s", "ς": "s", "τ": "t", "υ": "u", "χ": "x", "ω": "w",
    # lateinische Sonderzeichen ohne Zerlegung
    "ø": "o", "đ": "d", "ð": "d", "ł": "l", "ı": "i", "æ": "a", "œ": "o", "þ": "p",
    # Ziffern-Leetspeak
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g",
    # Verwechslungsklassen
    "l": "i", "v": "u",
}
CJK = "㐀-䶿一-鿿"
SEP = r"[^a-z\s" + CJK + "]{0,2}"
SEP_CJK = r"[^a-z0-9" + CJK + "]{0,2}"
SEP_SPACED = r"[^a-z]{1,2}"
SEP_WORDS = r"[^a-z" + CJK + "]{1,3}"
BEFORE, AFTER = "(?<![a-z])", "(?![a-z])"
MAX_CHARS = 6000

LABELS = {"profanity": "insults / profanity", "sexual": "sexual content", "hate": "hate / extremism", "threat": "threats"}


def _is_cjk(c: str) -> bool:
    return "㐀" <= c <= "䶿" or "一" <= c <= "鿿"


def skeleton(text: str, symbols: bool = True) -> tuple[str, list[int]]:
    """Grundform + für jedes Zeichen die Position im Originaltext."""
    out: list[str] = []
    idx: list[int] = []
    run_char, run_len = "", 0
    for oi, ch in enumerate(text[:MAX_CHARS]):
        low = "ss" if ch == "ß" else ch.lower()
        for c in unicodedata.normalize("NFKD", low):
            cat = unicodedata.category(c)
            if cat in ("Mn", "Me", "Cf") or c == "­":
                continue
            if c.isspace() or cat == "Cc":
                c = " "
            elif c in WILD_CHARS:
                c = WILD
            elif c in LETTERS:
                c = LETTERS[c]
            elif symbols and c in SYMBOLS:
                c = SYMBOLS[c]
            for d in c:
                if d == run_char:
                    run_len += 1
                    if run_len > 3:          # fuuuuuuck -> fuuuck (hält die Mustersuche schnell)
                        continue
                else:
                    run_char, run_len = d, 1
                out.append(d)
                idx.append(oi)
    return "".join(out), idx


def _letters(word: str) -> str:
    """Eintrag der Wortliste in reine Buchstaben der Grundform (Apostroph/Bindestrich weg)."""
    sk, _ = skeleton(word, True)
    return "".join(c for c in sk if "a" <= c <= "z" or _is_cjk(c))


def _unit(c: str, wild: bool = True) -> str:
    if _is_cjk(c):
        return re.escape(c)
    return f"(?:{c}+|{WILD})" if wild else f"{c}+"


def _word_regex(word: str, whole: bool) -> list[str]:
    sk = _letters(word)
    if len(sk) < 2:
        return []
    if any(_is_cjk(c) for c in sk):
        return [SEP_CJK.join(_unit(c) for c in sk)]
    wild = len(sk) >= 4                          # "f*ck" ja, aber "x*y" (Mathe) nicht
    body = SEP.join(_unit(c, wild) for c in sk)
    pats = [BEFORE + body + AFTER if whole else body]
    if len(sk) >= 3:                             # "f u c k": einzeln getippte Buchstaben
        pats.append(BEFORE + SEP_SPACED.join(sk) + AFTER)
    return pats


def _phrase_regex(phrase: str) -> list[str]:
    words = [_letters(w) for w in phrase.split()]
    words = [w for w in words if w]
    if not words:
        return []
    if len(words) == 1:
        return _word_regex(words[0], whole=True)
    return [BEFORE + SEP_WORDS.join(SEP.join(_unit(c, len(w) >= 4) for c in w) for w in words) + AFTER]


def build_patterns() -> list[tuple[str, str, str]]:
    """[(Kategorie, Art, Regex)] – Art: word | sub | phrase. Auch Grundlage für die Datenbank."""
    seen: set[tuple[str, str]] = set()
    rows: list[tuple[str, str, str]] = []

    def add(cat, kind, pats):
        for p in pats:
            if (cat, p) not in seen:
                seen.add((cat, p))
                rows.append((cat, kind, p))

    for cat in WL.CATEGORIES:
        subs = {_letters(w) for w in WL.S.get(cat, [])}
        for w in WL.S.get(cat, []):
            add(cat, "sub", _word_regex(w, whole=False))
        for w in WL.W.get(cat, []):
            if " " in w.strip():
                add(cat, "phrase", _phrase_regex(w))
            elif _letters(w) not in subs:
                add(cat, "word", _word_regex(w, whole=True))
        for p in WL.PHRASES.get(cat, []):
            add(cat, "phrase", _phrase_regex(p))
    return rows


def build_allow() -> list[str]:
    out = []
    for w in WL.ALLOW:
        words = [_letters(x) for x in w.split() if _letters(x)]
        if words:
            out.append(BEFORE + SEP_WORDS.join("".join(f"{c}+" for c in x) for x in words) + "[a-z]{0,4}" + AFTER)
    return out


_COMPILED: dict | None = None


def _compiled() -> dict:
    global _COMPILED
    if _COMPILED is None:
        by_cat: dict[str, list[str]] = {}
        for cat, _kind, rx in build_patterns():
            by_cat.setdefault(cat, []).append(rx)
        _COMPILED = {
            "cats": [(cat, re.compile("|".join(f"(?:{r})" for r in rxs))) for cat, rxs in by_cat.items()],
            "allow": [re.compile(a) for a in build_allow()],
        }
    return _COMPILED


@dataclass(frozen=True)
class Verdict:
    ok: bool
    category: str = ""

    def __bool__(self):
        return self.ok


def _views(text: str):
    for symbols in (True, False):
        sk, idx = skeleton(text, symbols)
        for rx in _compiled()["allow"]:
            sk = rx.sub(lambda m: " " * (m.end() - m.start()), sk)
        yield sk, idx


def check(text: str) -> Verdict:
    """Ist der Text in Ordnung? Bei Treffer steht die Kategorie im Ergebnis (nie das Wort selbst)."""
    if not text:
        return Verdict(True)
    for sk, _idx in _views(text):
        for cat, rx in _compiled()["cats"]:
            if rx.search(sk):
                return Verdict(False, cat)
    return Verdict(True)


def mask(text: str, char: str = "•") -> tuple[str, bool]:
    """Ersetzt alle Treffer im Originaltext durch `char`. Gibt (Text, wurde_etwas_ersetzt) zurück."""
    if not text:
        return text, False
    hit = [False] * len(text)
    for sk, idx in _views(text):
        for _cat, rx in _compiled()["cats"]:
            for m in rx.finditer(sk):
                if m.end() > m.start():
                    for k in range(m.start(), m.end()):
                        hit[idx[k]] = True
    if not any(hit):
        return text, False
    return "".join(char if (h and not c.isspace()) else c for c, h in zip(text, hit)) + text[MAX_CHARS:], True


def category_label(cat: str) -> str:
    return tr(LABELS.get(cat, "insults / profanity"))


def explain(v: Verdict) -> str:
    return tr("This text contains content that is not allowed here ({c}). Please rephrase it.", c=category_label(v.category))


class FilterError(Exception):
    """Fehlertext darf dem Nutzer angezeigt werden."""


def require_clean(text: str) -> None:
    v = check(text)
    if not v.ok:
        raise FilterError(explain(v))
