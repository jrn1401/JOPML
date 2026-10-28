-- JOPML 1.5.0+: Der Marktplatz akzeptiert die Makro-Befehle "down" und "up" (Taste/Maustaste gedrückt halten / loslassen).
-- Vorher lehnte der Server solche Makros mit 'invalid_script' ab, obwohl der Launcher sie seit 1.5.0 kennt.
-- Zufällige Wartezeiten ("wait 100ms-300ms") waren schon erlaubt, weil nur das erste Wort geprüft wird.
create or replace function public.jopml_m_script_ok(s text) returns boolean
language plpgsql immutable set search_path = '' as $$
declare ln text; n integer := 0;
begin
  if s is null or length(btrim(s)) = 0 or length(s) > 20000 then return false; end if;
  foreach ln in array regexp_split_to_array(s, E'\r?\n') loop
    ln := btrim(ln);
    n := n + 1;
    if n > 600 then return false; end if;
    if ln = '' or left(ln, 1) = '#' then continue; end if;
    if ln !~* '^(click|doubleclick|move|key|hold|down|up|type|scroll|wait|repeat|end)(\s|$)' then return false; end if;
  end loop;
  return true;
end $$;

revoke all on function public.jopml_m_script_ok(text) from public, anon, authenticated;
