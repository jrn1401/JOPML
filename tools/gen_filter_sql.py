"""Erzeugt die Datenbank-Migration für den Server-Filter aus core/chatfilter(_words).py.

Aufruf:  python tools/gen_filter_sql.py   -> schreibt supabase/migrations/20261028000100_jopml_filter.sql
Nach Änderungen an den Wortlisten neu ausführen und die Datei als NEUE Migration (neuer Zeitstempel) einspielen.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import chatfilter as F  # noqa: E402

OUT = ROOT / "supabase" / "migrations" / "20261028000100_jopml_filter.sql"


def lit(s: str) -> str:
    return "$q$" + s + "$q$"


SEP = "[^a-z\\s㐀-䶿一-鿿]{0,2}"


def _comp(r: str) -> str:
    import re
    r = r.replace(SEP, "~S").replace("[^a-z]{1,2}", "~T").replace("(?<![a-z])", "~B").replace("(?![a-z])", "~A")
    return re.sub(r"\(\?:([a-z])\+\|\)", r"~\1", r)


def maps():
    keep = {k: v for k, v in F.LETTERS.items() if v}
    drop = [k for k, v in F.LETTERS.items() if not v]
    upper = {k.upper(): v for k, v in keep.items() if k.upper() != k and len(k.upper()) == 1}
    frm = "".join(keep) + "".join(upper)
    to = "".join(keep.values()) + "".join(upper.values())
    return frm, to, "".join(F.SYMBOLS), "".join(F.SYMBOLS.values()), "".join(drop)


def entries():
    """[(Kategorie, Art, [Buchstabenfolgen])] – kompakte Form der Muster aus F.build_patterns()."""
    from core import chatfilter_words as WL
    out = []
    for cat in WL.CATEGORIES:
        subs_l = [F._letters(w) for w in WL.S.get(cat, [])]
        subs = set(subs_l)
        words, phrases = [], []
        for w in WL.S.get(cat, []):
            pass
        sub = [x for x in subs_l if len(x) >= 2]
        for w in WL.W.get(cat, []):
            if " " in w.strip():
                phrases.append(" ".join(x for x in (F._letters(t) for t in w.split()) if x))
            elif F._letters(w) not in subs:
                words.append(F._letters(w))
        for ph in WL.PHRASES.get(cat, []):
            phrases.append(" ".join(x for x in (F._letters(t) for t in ph.split()) if x))
        # einwortige Phrasen verhalten sich wie 'word'
        ph2 = []
        for ph in phrases:
            if not ph:
                continue
            (words if " " not in ph else ph2).append(ph)
        words = [x for x in words if len(x) >= 2]
        for kind, lst in (("sub", sub), ("word", words), ("phrase", ph2)):
            if lst:
                out.append((cat, kind, lst))
    return out


def mkpat_sql():
    cjk = F.CJK
    return [
        "-- Baut aus einer Buchstabenfolge (oder Wörtern mit Leerzeichen bei 'phrase') die Regex-Muster.",
        "create or replace function public.jopml_c_mkpat(kind text, w text) returns text[]",
        "language plpgsql immutable set search_path = '' as $f$",
        "declare n int; i int; c text; units text[] := '{}'; words text[]; parts text[] := '{}'; wi text; res text[] := '{}'; isc boolean;",
        "  sep constant text := " + lit(F.SEP) + "; sepc constant text := " + lit(F.SEP_CJK) + ";",
        "  sps constant text := " + lit(F.SEP_SPACED) + "; spw constant text := " + lit(F.SEP_WORDS) + ";",
        "  bf constant text := " + lit(F.BEFORE) + "; af constant text := " + lit(F.AFTER) + "; wild constant text := chr(" + str(ord(F.WILD)) + ");",
        "  cj constant text := " + lit("[" + cjk + "]") + ";",
        "begin",
        "  if kind = 'phrase' then",
        "    foreach wi in array string_to_array(w, ' ') loop",
        "      units := '{}';",
        "      for i in 1..char_length(wi) loop c := substr(wi, i, 1);",
        "        units := units || (case when char_length(wi) >= 4 then '(?:' || c || '+|' || wild || ')' else c || '+' end);",
        "      end loop;",
        "      parts := parts || array_to_string(units, sep);",
        "    end loop;",
        "    return array[bf || array_to_string(parts, spw) || af];",
        "  end if;",
        "  n := char_length(w); isc := w ~ cj;",
        "  for i in 1..n loop c := substr(w, i, 1);",
        "    if c ~ cj then units := units || regexp_replace(c, '([\\\\.^$|?*+()\\[\\]{}-])', '\\\\\\1', 'g');",
        "    elsif n >= 4 then units := units || ('(?:' || c || '+|' || wild || ')');",
        "    else units := units || (c || '+'); end if;",
        "  end loop;",
        "  if isc then return array[array_to_string(units, sepc)]; end if;",
        "  res := array[case when kind = 'word' then bf || array_to_string(units, sep) || af else array_to_string(units, sep) end];",
        "  if n >= 3 then res := res || (bf || array_to_string(regexp_split_to_array(w, ''), sps) || af); end if;",
        "  return res;",
        "end $f$;",
        "",
    ]


def main():
    frm, to, sf, st, drop = maps()
    rows = F.build_patterns()
    allow = F.build_allow()
    lines = [
        "-- JOPML v1.3 – Server-Filter für öffentliche Texte (Forum, Benutzer-/Server-/Kanalnamen).",
        "-- GENERIERT von tools/gen_filter_sql.py aus core/chatfilter.py + core/chatfilter_words.py – nicht von Hand ändern.",
        "-- Ende-zu-Ende-verschlüsselte Chats kann der Server NICHT filtern (er sieht nur Chiffretext); dort filtert der Client.",
        "",
        "create table if not exists public.jopml_c_filter (id serial primary key, category text not null, kind text not null, pattern text not null);",
        "create table if not exists public.jopml_c_allow (id serial primary key, pattern text not null);",
        "alter table public.jopml_c_filter enable row level security;",
        "alter table public.jopml_c_allow enable row level security;",
        "revoke all on public.jopml_c_filter, public.jopml_c_allow from anon, authenticated, public;",
        "truncate public.jopml_c_filter, public.jopml_c_allow;",
        "",
        "create or replace function public.jopml_c_skel(t text, symbols boolean) returns text",
        "language sql immutable set search_path = '' as $f$",
        "  select regexp_replace(",
        "    translate(translate(",
        "      lower(regexp_replace(regexp_replace(normalize(replace(left(coalesce(t, ''), %d), 'ß', 'ss'), NFKD),"
        % F.MAX_CHARS,
        "        '[\\x0300-\\x036f\\x200b-\\x200f\\x2028-\\x202e\\x2060-\\x206f\\xfeff\\xad\\x180e\\x034f]', '', 'g'), '[\\s]', ' ', 'g')),",
        f"      {lit(F.WILD_CHARS)}, repeat(chr({ord(F.WILD)}), {len(F.WILD_CHARS)})),",
        f"      {lit(frm)} || case when symbols then {lit(sf)} else '' end || {lit(drop)},",
        f"      {lit(to)} || case when symbols then {lit(st)} else '' end),",
        "    '(.)\\1{3,}', '\\1\\1\\1', 'g')",
        "$f$;",
        "",
    ]
    # Reihenfolge der translate-Stufen: erst Platzhalter, dann Buchstaben/Symbole (wie in Python)
    # Kompakte Schreibweise (Migration bleibt klein): ~S ~T ~B ~A und ~x werden unten wieder aufgelöst.
    # Die Wortlisten gehen kompakt in die Datenbank; die Regex-Muster baut jopml_c_mkpat() (Spiegel von _word_regex/_phrase_regex).
    lines += mkpat_sql()
    lines.append("insert into public.jopml_c_filter (category, kind, pattern)")
    lines.append("select e.cat, e.kind, p from (values")
    lines.append(",\n".join(f"({lit(c)}, {lit(k)}, {lit(','.join(ws))})" for c, k, ws in entries()))
    lines.append(") as e(cat, kind, ws), lateral unnest(string_to_array(e.ws, ',')) as w, lateral unnest(public.jopml_c_mkpat(e.kind, w)) as p;")
    lines.append("insert into public.jopml_c_allow (pattern) values")
    lines.append(",\n".join(f"({lit(_comp(rx))})" for rx in allow) + ";")
    for tbl in ("jopml_c_filter", "jopml_c_allow"):
        lines.append(f"update public.{tbl} set pattern = regexp_replace(replace(replace(replace(replace(pattern, '~S', {lit(SEP)}),"
                     f" '~T', '[^a-z]{{1,2}}'), '~B', '(?<![a-z])'), '~A', '(?![a-z])'), '~([a-z])', '(?:\\1+|)', 'g');")
    lines += [
        "",
        "-- Liefert die Kategorie des ersten Treffers oder NULL, wenn der Text sauber ist.",
        "create or replace function public.jopml_c_check(t text) returns text",
        "language plpgsql stable security definer set search_path = '' as $f$",
        "declare v text; cat text; a record; sym boolean;",
        "begin",
        "  if t is null or t = '' then return null; end if;",
        "  foreach sym in array array[true, false] loop",
        "    v := public.jopml_c_skel(t, sym);",
        "    for a in select pattern from public.jopml_c_allow loop v := regexp_replace(v, a.pattern, ' ', 'g'); end loop;",
        "    select f.category into cat from public.jopml_c_filter f where v ~ f.pattern limit 1;",
        "    if cat is not null then return cat; end if;",
        "  end loop;",
        "  return null;",
        "end $f$;",
        "",
        "create or replace function public.jopml_c_assert_clean(t text) returns void",
        "language plpgsql stable security definer set search_path = '' as $f$",
        "declare cat text := public.jopml_c_check(t);",
        "begin",
        "  if cat is not null then raise exception 'filtered:%', cat; end if;",
        "end $f$;",
        "",
        "revoke all on function public.jopml_c_skel(text, boolean) from public, anon;",
        "revoke all on function public.jopml_c_check(text) from public, anon;",
        "revoke all on function public.jopml_c_assert_clean(text) from public, anon;",
        "grant execute on function public.jopml_c_skel(text, boolean) to authenticated;",
        "grant execute on function public.jopml_c_check(text) to authenticated;",
        "grant execute on function public.jopml_c_assert_clean(text) to authenticated;",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} Muster, {len(allow)} Ausnahmen -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
