-- JOPML 1.4.0: Makro-Marktplatz, Ankündigungen, Bestenlisten.
-- Alle Zugriffe laufen über SECURITY-DEFINER-Funktionen; die Tabellen sind für Clients gesperrt.

create table if not exists public.jopml_m_macros (
  id         bigserial primary key,
  author_id  uuid not null references auth.users (id) on delete cascade,
  title      text not null,
  descr      text not null default '',
  script     text not null,
  downloads  integer not null default 0,
  hidden     boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists jopml_m_macros_created on public.jopml_m_macros (created_at desc);
create table if not exists public.jopml_m_ratings (
  macro_id bigint not null references public.jopml_m_macros (id) on delete cascade,
  user_id  uuid not null references auth.users (id) on delete cascade,
  stars    smallint not null check (stars between 1 and 5),
  primary key (macro_id, user_id)
);
create table if not exists public.jopml_m_reports (
  macro_id   bigint not null references public.jopml_m_macros (id) on delete cascade,
  reporter   uuid not null references auth.users (id) on delete cascade,
  reason     text not null default '',
  created_at timestamptz not null default now(),
  primary key (macro_id, reporter)
);
create table if not exists public.jopml_news (
  id         bigserial primary key,
  title      text not null,
  body       text not null default '',
  created_at timestamptz not null default now()
);
create table if not exists public.jopml_scores (
  user_id    uuid not null references auth.users (id) on delete cascade,
  kind       text not null check (kind in ('cps5', 'reaction')),
  value      numeric not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, kind)
);
alter table public.jopml_m_macros  enable row level security;
alter table public.jopml_m_ratings enable row level security;
alter table public.jopml_m_reports enable row level security;
alter table public.jopml_news      enable row level security;
alter table public.jopml_scores    enable row level security;
revoke all on public.jopml_m_macros, public.jopml_m_ratings, public.jopml_m_reports, public.jopml_news, public.jopml_scores
  from anon, authenticated, public;

-- Prüfung eines Makro-Textes: nur bekannte Befehle, Größe begrenzt
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
    if ln !~* '^(click|doubleclick|move|key|hold|type|scroll|wait|repeat|end)(\s|$)' then return false; end if;
  end loop;
  return true;
end $$;

create or replace function public.jopml_m_publish(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); t text := btrim(coalesce(p->>'title', '')); d text := btrim(coalesce(p->>'descr', '')); s text := p->>'script'; c text; mid bigint;
begin
  if length(t) < 3 or length(t) > 60 or length(d) > 500 then raise exception 'invalid_name'; end if;
  if not public.jopml_m_script_ok(s) then raise exception 'invalid_script'; end if;
  c := coalesce(public.jopml_c_check(t), public.jopml_c_check(d), public.jopml_c_check(s));
  if c is not null then raise exception 'filtered:%', c; end if;
  if (select count(*) from public.jopml_m_macros where author_id = u and created_at > now() - interval '1 day') >= 5 then raise exception 'rate_limited'; end if;
  insert into public.jopml_m_macros (author_id, title, descr, script) values (u, t, d, s) returning id into mid;
  return jsonb_build_object('id', mid);
end $$;

create or replace function public.jopml_m_list(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); q text := lower(btrim(coalesce(p->>'q', ''))); srt text := coalesce(p->>'sort', 'new');
        lim integer := least(50, greatest(1, coalesce((p->>'limit')::integer, 30))); off integer := greatest(0, coalesce((p->>'offset')::integer, 0));
begin
  return coalesce((select jsonb_agg(to_jsonb(x)) from (
    select m.id, m.title, m.descr, cu.handle as author, m.downloads, m.created_at, (m.author_id = u) as mine,
           coalesce(round(avg(r.stars)::numeric, 1), 0) as stars, count(r.user_id) as votes,
           coalesce((select r2.stars from public.jopml_m_ratings r2 where r2.macro_id = m.id and r2.user_id = u), 0) as my_stars
      from public.jopml_m_macros m
      left join public.jopml_c_users cu on cu.user_id = m.author_id
      left join public.jopml_m_ratings r on r.macro_id = m.id
     where not m.hidden and (q = '' or lower(m.title) like '%' || replace(replace(q, '%', ''), '_', '') || '%'
                                 or lower(m.descr) like '%' || replace(replace(q, '%', ''), '_', '') || '%')
     group by m.id, cu.handle
     order by case when srt = 'top' then coalesce(avg(r.stars), 0) end desc nulls last,
              case when srt = 'popular' then m.downloads end desc nulls last, m.created_at desc
     limit lim offset off) x), '[]'::jsonb);
end $$;

create or replace function public.jopml_m_get(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); m public.jopml_m_macros;
begin
  select * into m from public.jopml_m_macros where id = (p->>'id')::bigint and (not hidden or author_id = u);
  if not found then raise exception 'not_found'; end if;
  if m.author_id <> u then update public.jopml_m_macros set downloads = downloads + 1 where id = m.id; end if;
  return jsonb_build_object('id', m.id, 'title', m.title, 'script', m.script);
end $$;

create or replace function public.jopml_m_rate(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); mid bigint := (p->>'id')::bigint; st integer := (p->>'stars')::integer;
begin
  if st is null or st < 1 or st > 5 then raise exception 'invalid_payload'; end if;
  if not exists (select 1 from public.jopml_m_macros where id = mid and not hidden and author_id <> u) then raise exception 'forbidden'; end if;
  insert into public.jopml_m_ratings (macro_id, user_id, stars) values (mid, u, st)
  on conflict (macro_id, user_id) do update set stars = excluded.stars;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_m_report(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); mid bigint := (p->>'id')::bigint;
begin
  if not exists (select 1 from public.jopml_m_macros where id = mid) then raise exception 'not_found'; end if;
  insert into public.jopml_m_reports (macro_id, reporter, reason) values (mid, u, left(coalesce(p->>'reason', ''), 300))
  on conflict (macro_id, reporter) do nothing;
  if (select count(*) from public.jopml_m_reports where macro_id = mid) >= 3 then
    update public.jopml_m_macros set hidden = true where id = mid;
  end if;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_m_delete(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); m public.jopml_m_macros;
begin
  select * into m from public.jopml_m_macros where id = (p->>'id')::bigint;
  if not found then raise exception 'not_found'; end if;
  if m.author_id <> u and not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  delete from public.jopml_m_macros where id = m.id;
  return jsonb_build_object('ok', true);
end $$;

-- Ankündigungen
create or replace function public.jopml_news_list() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'not_authenticated'; end if;
  return coalesce((select jsonb_agg(to_jsonb(x)) from (select id, title, body, created_at from public.jopml_news order by id desc limit 30) x), '[]'::jsonb);
end $$;

create or replace function public.jopml_news_post(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare t text := btrim(coalesce(p->>'title', '')); b text := btrim(coalesce(p->>'body', '')); nid bigint;
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  if length(t) < 3 or length(t) > 100 or length(b) > 2000 then raise exception 'invalid_payload'; end if;
  insert into public.jopml_news (title, body) values (t, b) returning id into nid;
  return jsonb_build_object('id', nid);
end $$;

create or replace function public.jopml_news_delete(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  delete from public.jopml_news where id = (p->>'id')::bigint;
  return jsonb_build_object('ok', true);
end $$;

-- Bestenlisten (CPS in 5 s: höher ist besser; Reaktionszeit in ms: niedriger ist besser)
create or replace function public.jopml_score_submit(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); k text := p->>'kind'; v numeric := (p->>'value')::numeric; cur numeric; last timestamptz;
begin
  if k = 'cps5' then
    if v is null or v < 1 or v > 20 then raise exception 'invalid_payload'; end if;
  elsif k = 'reaction' then
    if v is null or v < 80 or v > 2000 then raise exception 'invalid_payload'; end if;
  else raise exception 'invalid_payload'; end if;
  select value, updated_at into cur, last from public.jopml_scores where user_id = u and kind = k;
  if last is not null and last > now() - interval '4 seconds' then raise exception 'rate_limited'; end if;
  if cur is null then
    insert into public.jopml_scores (user_id, kind, value) values (u, k, round(v, 2));
  elsif (k = 'cps5' and v > cur) or (k = 'reaction' and v < cur) then
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
  if k not in ('cps5', 'reaction') then raise exception 'invalid_payload'; end if;
  return coalesce((select jsonb_agg(to_jsonb(x)) from (
    select cu.handle, cu.display_name, s.value, (s.user_id = u) as mine
      from public.jopml_scores s join public.jopml_c_users cu on cu.user_id = s.user_id
     where s.kind = k
     order by case when k = 'cps5' then -s.value else s.value end, s.updated_at
     limit lim) x), '[]'::jsonb);
end $$;

revoke all on function public.jopml_m_script_ok(text) from public, anon, authenticated;
revoke all on function public.jopml_m_publish(jsonb), public.jopml_m_list(jsonb), public.jopml_m_get(jsonb), public.jopml_m_rate(jsonb),
  public.jopml_m_report(jsonb), public.jopml_m_delete(jsonb), public.jopml_news_list(), public.jopml_news_post(jsonb),
  public.jopml_news_delete(jsonb), public.jopml_score_submit(jsonb), public.jopml_score_top(jsonb) from public, anon;
grant execute on function public.jopml_m_publish(jsonb), public.jopml_m_list(jsonb), public.jopml_m_get(jsonb), public.jopml_m_rate(jsonb),
  public.jopml_m_report(jsonb), public.jopml_m_delete(jsonb), public.jopml_news_list(), public.jopml_news_post(jsonb),
  public.jopml_news_delete(jsonb), public.jopml_score_submit(jsonb), public.jopml_score_top(jsonb) to authenticated;
