-- JOPML 1.7.7: Bestenlisten für den Rückstoß-Trainer (je Muster eine Liste; höher ist besser, 1-100 Punkte).
-- Hinweis: Die Punkte kommen vom Programm des Spielers; der Server prüft nur Wertebereich und Häufigkeit, nicht den Spielverlauf.

alter table public.jopml_scores drop constraint if exists jopml_scores_kind_check;
alter table public.jopml_scores add constraint jopml_scores_kind_check
  check (kind in ('cps5', 'reaction', 'recoil_up', 'recoil_right', 'recoil_zigzag', 'recoil_random'));

create or replace function public.jopml_score_submit(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); k text := p->>'kind'; v numeric := (p->>'value')::numeric; cur numeric; last timestamptz;
begin
  if k = 'cps5' then
    if v is null or v < 1 or v > 20 then raise exception 'invalid_payload'; end if;
  elsif k = 'reaction' then
    if v is null or v < 80 or v > 2000 then raise exception 'invalid_payload'; end if;
  elsif k in ('recoil_up', 'recoil_right', 'recoil_zigzag', 'recoil_random') then
    if v is null or v < 1 or v > 100 then raise exception 'invalid_payload'; end if;
  else raise exception 'invalid_payload'; end if;
  select value, updated_at into cur, last from public.jopml_scores where user_id = u and kind = k;
  if last is not null and last > now() - interval '4 seconds' then raise exception 'rate_limited'; end if;
  if cur is null then
    insert into public.jopml_scores (user_id, kind, value) values (u, k, round(v, 2));
  elsif (k <> 'reaction' and v > cur) or (k = 'reaction' and v < cur) then
    update public.jopml_scores set value = round(v, 2), updated_at = now() where user_id = u and kind = k;
  else
    update public.jopml_scores set updated_at = now() where user_id = u and kind = k;
  end if;
  return jsonb_build_object('best', (select value from public.jopml_scores where user_id = u and kind = k));
end $$;

create or replace function public.jopml_score_top(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); k text := p->>'kind'; lim integer := least(50, greatest(1, coalesce((p->>'limit')::integer, 20)));
begin
  if k not in ('cps5', 'reaction', 'recoil_up', 'recoil_right', 'recoil_zigzag', 'recoil_random') then raise exception 'invalid_payload'; end if;
  return coalesce((select jsonb_agg(to_jsonb(x)) from (
    select cu.handle, cu.display_name, s.value, (s.user_id = u) as mine
      from public.jopml_scores s join public.jopml_c_users cu on cu.user_id = s.user_id
     where s.kind = k
     order by case when k = 'reaction' then s.value else -s.value end, s.updated_at
     limit lim) x), '[]'::jsonb);
end $$;
