"""Spielt tools/translations_1100.py in core/lang/*.py ein (nur Schlüssel, die es dort noch nicht gibt). Einmalig benutzt für 1.10.0."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tests" / "stubs"), str(ROOT)]
spec = importlib.util.spec_from_file_location("tr1100", ROOT / "tools" / "translations_1100.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
LANGS = ["de", "es", "fr", "ru", "zh"]
MARK = "    'Single-player cheats for Minecraft and GTA 5 Enhanced"


def table():
    out = {}
    for name in ("SHORT", "LONG", "CODES"):
        out.update(getattr(mod, name))
    for code, vals in mod.SOLUTIONS.items():
        from core import errors
        out[errors.SOLUTIONS[code]] = vals
    return out


def main():
    data = table()
    for i, lang in enumerate(LANGS):
        path = ROOT / "core" / "lang" / f"{lang}.py"
        text = path.read_text(encoding="utf-8")
        ns = {}
        exec(compile(text, str(path), "exec"), ns)
        have = ns["T"]
        add = []
        for key, vals in data.items():
            v = vals[i]
            if v and key not in have:
                add.append(f"    {key!r}: {v!r},\n")
        if not add:
            continue
        assert MARK in text, lang
        text = text.replace(MARK, "".join(add) + MARK, 1)
        path.write_text(text, encoding="utf-8")
        print(lang, len(add), "eingefügt")


if __name__ == "__main__":
    main()
