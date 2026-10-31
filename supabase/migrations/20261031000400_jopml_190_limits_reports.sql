-- 1.9.0: KI-Limits (Antwortlänge, Tokens pro Tag), komprimierte Fehlergruppen, Nutzer-Meldungen, KI-Analyse-Speicher.
-- Werte: NULL = Standard erben, -1 = kein Limit, sonst Zahl ("Maximum" = Obergrenze des Systems).
create table if not exists public.jopml_ai_settings (
  id integer primary key default 1 check (id = 1),
  daily_requests integer not null default 60,
  max_answer integer not null default 2048,
  daily_tokens integer not null default 200000,
  updated_at timestamptz not null default now()
);
insert into public.jopml_ai_settings (id) values (1) on conflict do nothing;
alter table public.jopml_ai_settings enable row level security;
revoke all on public.jopml_ai_settings from anon, authenticated, public;

alter table public.jopml_ai_limits alter column daily_limit drop not null;
alter table public.jopml_ai_limits drop constraint if exists jopml_ai_limits_daily_limit_check;
alter table public.jopml_ai_limits add column if not exists max_answer integer;
alter table public.jopml_ai_limits add column if not exists daily_tokens integer;
alter table public.jopml_ai_usage add column if not exists tokens bigint not null default 0;

-- Fehlergruppen (komprimiert): ein Eintrag je Fingerabdruck
create table if not exists public.jopml_error_groups (
  fingerprint text primary key,
  code text,
  kind text not null,
  message text not null,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  hits bigint not null default 1,
  users_seen integer not null default 1,
  versions jsonb not null default '{}'::jsonb,
  systems jsonb not null default '{}'::jsonb,
  sample_trace text,
  analysis text,
  analyzed_at timestamptz
);
create table if not exists public.jopml_user_reports (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  category text not null,
  code text,
  message text not null,
  version text,
  os text
);
alter table public.jopml_error_groups enable row level security;
alter table public.jopml_user_reports enable row level security;
revoke all on public.jopml_error_groups, public.jopml_user_reports from anon, authenticated, public;

-- Automatische Meldung (auch von alten Clients über jopml_log_error): wird in Gruppen zusammengefasst
create or replace function public.jopml_report_error(p_code text, p_kind text, p_message text, p_trace text, p_version text, p_os text)
returns void language plpgsql security definer set search_path = '' as $$
declare fp text; msg text; v text; o text;
begin
  if auth.uid() is null then return; end if;
  msg := left(coalesce(p_message, ''), 600);
  v := left(coalesce(p_version, '?'), 20);
  o := left(coalesce(p_os, '?'), 40);
  fp := md5(coalesce(p_code, '') || '|' || left(coalesce(p_kind, ''), 40) || '|' || regexp_replace(left(msg, 160), '[0-9a-fA-F-]{6,}|[0-9]+', '#', 'g'));
  insert into public.jopml_error_groups as g (fingerprint, code, kind, message, sample_trace, versions, systems)
    values (fp, left(p_code, 20), left(coalesce(p_kind, 'error'), 40), msg, left(p_trace, 3000), jsonb_build_object(v, 1), jsonb_build_object(o, 1))
  on conflict (fingerprint) do update set
    hits = g.hits + 1, last_seen = now(),
    versions = jsonb_set(g.versions, array[v], to_jsonb(coalesce((g.versions ->> v)::int, 0) + 1)),
    systems = jsonb_set(g.systems, array[o], to_jsonb(coalesce((g.systems ->> o)::int, 0) + 1));
  -- Obergrenze: älteste, selten gesehene Gruppen entfernen
  if (select count(*) from public.jopml_error_groups) > 2000 then
    delete from public.jopml_error_groups where fingerprint in (select fingerprint from public.jopml_error_groups order by last_seen asc limit 200);
  end if;
end $$;

create or replace function public.jopml_log_error(p_kind text, p_message text, p_trace text, p_version text, p_os text)
returns void language sql security definer set search_path = '' as $$
  select public.jopml_report_error(null, p_kind, p_message, p_trace, p_version, p_os);
$$;

create or replace function public.jopml_user_report(p_category text, p_message text, p_code text, p_version text, p_os text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'not allowed'; end if;
  if length(trim(coalesce(p_message, ''))) < 5 then raise exception 'too short'; end if;
  if (select count(*) from public.jopml_user_reports where user_id = auth.uid() and created_at > now() - interval '1 day') >= 10 then
    raise exception 'rate_limited';
  end if;
  insert into public.jopml_user_reports (user_id, category, code, message, version, os)
    values (auth.uid(), left(coalesce(p_category, 'bug'), 30), left(p_code, 20), left(p_message, 2000), left(p_version, 20), left(p_os, 40));
  delete from public.jopml_user_reports where created_at < now() - interval '180 days';
end $$;

create or replace function public.jopml_admin_error_groups(p_limit integer default 100)
returns setof public.jopml_error_groups language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select * from public.jopml_error_groups order by last_seen desc limit greatest(1, least(p_limit, 500));
end $$;

create or replace function public.jopml_admin_user_reports(p_limit integer default 100)
returns table(id bigint, created_at timestamptz, category text, code text, message text, version text, os text, email text)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select r.id, r.created_at, r.category, r.code, r.message, r.version, r.os, u.email::text
    from public.jopml_user_reports r left join auth.users u on u.id = r.user_id
    order by r.created_at desc limit greatest(1, least(p_limit, 500));
end $$;

create or replace function public.jopml_admin_clear_reports(p_what text, p_id bigint default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if p_what = 'groups' then delete from public.jopml_error_groups;
  elsif p_what = 'reports' then delete from public.jopml_user_reports;
  elsif p_what = 'report' then delete from public.jopml_user_reports where id = p_id;
  else raise exception 'bad arg'; end if;
  insert into public.jopml_admin_audit (admin_id, action, detail) values (auth.uid(), 'clear_' || p_what, p_id::text);
end $$;

create or replace function public.jopml_admin_set_analysis(p_fingerprint text, p_text text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  update public.jopml_error_groups set analysis = left(p_text, 4000), analyzed_at = now() where fingerprint = p_fingerprint;
end $$;

-- Standardwerte und Nutzerwerte
create or replace function public.jopml_admin_ai_defaults()
returns table(daily_requests integer, max_answer integer, daily_tokens integer)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select s.daily_requests, s.max_answer, s.daily_tokens from public.jopml_ai_settings s where s.id = 1;
end $$;

create or replace function public.jopml_admin_set_ai_defaults(p_requests integer, p_answer integer, p_tokens integer)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if p_requests not between -1 and 100000 or p_answer not between -1 and 65536 or p_tokens not between -1 and 100000000 then raise exception 'bad limit'; end if;
  update public.jopml_ai_settings set daily_requests = p_requests, max_answer = p_answer, daily_tokens = p_tokens, updated_at = now() where id = 1;
  insert into public.jopml_admin_audit (admin_id, action, detail) values (auth.uid(), 'set_ai_defaults', p_requests || '/' || p_answer || '/' || p_tokens);
end $$;

drop function if exists public.jopml_admin_set_ai_limit(uuid, integer);
create or replace function public.jopml_admin_set_ai_user(p_user uuid, p_requests integer, p_answer integer, p_tokens integer)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if not exists (select 1 from auth.users where id = p_user) then raise exception 'unknown user'; end if;
  if p_requests is null and p_answer is null and p_tokens is null then
    delete from public.jopml_ai_limits where user_id = p_user;
  else
    if p_requests not between -1 and 100000 or p_answer not between -1 and 65536 or p_tokens not between -1 and 100000000 then raise exception 'bad limit'; end if;
    insert into public.jopml_ai_limits (user_id, daily_limit, max_answer, daily_tokens, set_by)
      values (p_user, p_requests, p_answer, p_tokens, auth.uid())
      on conflict (user_id) do update set daily_limit = excluded.daily_limit, max_answer = excluded.max_answer,
        daily_tokens = excluded.daily_tokens, set_by = excluded.set_by, updated_at = now();
  end if;
  insert into public.jopml_admin_audit (admin_id, action, target, detail)
    values (auth.uid(), 'set_ai_user', p_user, coalesce(p_requests::text, 'def') || '/' || coalesce(p_answer::text, 'def') || '/' || coalesce(p_tokens::text, 'def'));
end $$;

drop function if exists public.jopml_admin_people(integer);
create or replace function public.jopml_admin_people(p_limit integer default 200)
returns table(user_id uuid, email text, created_at timestamptz, is_admin boolean, ai_requests integer, ai_answer integer, ai_tokens integer, ai_today integer, tokens_today bigint)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query
    select u.id, u.email::text, u.created_at,
           exists (select 1 from public.jopml_admins a where a.user_id = u.id),
           l.daily_limit, l.max_answer, l.daily_tokens,
           coalesce((select x.hits from public.jopml_ai_usage x where x.user_id = u.id and x.day = current_date), 0),
           coalesce((select x.tokens from public.jopml_ai_usage x where x.user_id = u.id and x.day = current_date), 0)
    from auth.users u left join public.jopml_ai_limits l on l.user_id = u.id
    order by u.created_at desc limit greatest(1, least(p_limit, 500));
end $$;

-- Für die Edge Function: wirksame Regeln eines Nutzers (Nutzerwert > Standard; -1 = unbegrenzt)
create or replace function public.jopml_ai_policy(p_user uuid)
returns table(daily_requests integer, max_answer integer, daily_tokens integer, tokens_used bigint)
language plpgsql security definer set search_path = '' as $$
begin
  return query
    select coalesce(l.daily_limit, s.daily_requests), coalesce(l.max_answer, s.max_answer), coalesce(l.daily_tokens, s.daily_tokens),
           coalesce((select x.tokens from public.jopml_ai_usage x where x.user_id = p_user and x.day = current_date), 0)
    from public.jopml_ai_settings s left join public.jopml_ai_limits l on l.user_id = p_user where s.id = 1;
end $$;

create or replace function public.jopml_ai_add_tokens(p_user uuid, p_tokens integer)
returns void language sql security definer set search_path = '' as $$
  insert into public.jopml_ai_usage as t (user_id, day, hits, tokens) values (p_user, current_date, 0, greatest(p_tokens, 0))
  on conflict (user_id, day) do update set tokens = t.tokens + greatest(p_tokens, 0);
$$;

create or replace function public.jopml_ai_hit(p_user uuid, p_user_limit integer default 60, p_global_limit integer default 2000)
returns integer language plpgsql security definer set search_path = '' as $$
declare u integer; g integer; lim integer; tl integer; tu bigint;
begin
  select coalesce(l.daily_limit, s.daily_requests), coalesce(l.daily_tokens, s.daily_tokens)
    into lim, tl from public.jopml_ai_settings s left join public.jopml_ai_limits l on l.user_id = p_user where s.id = 1;
  lim := coalesce(lim, p_user_limit);
  select coalesce(x.tokens, 0) into tu from public.jopml_ai_usage x where x.user_id = p_user and x.day = current_date;
  if tl is not null and tl >= 0 and coalesce(tu, 0) >= tl then raise exception 'token_limited'; end if;
  insert into public.jopml_ai_global as t (day, hits) values (current_date, 1)
    on conflict (day) do update set hits = t.hits + 1 returning hits into g;
  if g > p_global_limit then raise exception 'rate_limited_global'; end if;
  insert into public.jopml_ai_usage as t (user_id, day, hits) values (p_user, current_date, 1)
    on conflict (user_id, day) do update set hits = t.hits + 1 returning hits into u;
  if lim >= 0 and u > lim then raise exception 'rate_limited'; end if;
  return case when lim < 0 then 999999 else lim - u end;
end $$;

revoke all on function public.jopml_report_error(text,text,text,text,text,text), public.jopml_user_report(text,text,text,text,text),
  public.jopml_admin_error_groups(integer), public.jopml_admin_user_reports(integer), public.jopml_admin_clear_reports(text,bigint),
  public.jopml_admin_set_analysis(text,text), public.jopml_admin_ai_defaults(), public.jopml_admin_set_ai_defaults(integer,integer,integer),
  public.jopml_admin_set_ai_user(uuid,integer,integer,integer), public.jopml_admin_people(integer) from public, anon;
grant execute on function public.jopml_report_error(text,text,text,text,text,text), public.jopml_user_report(text,text,text,text,text),
  public.jopml_admin_error_groups(integer), public.jopml_admin_user_reports(integer), public.jopml_admin_clear_reports(text,bigint),
  public.jopml_admin_set_analysis(text,text), public.jopml_admin_ai_defaults(), public.jopml_admin_set_ai_defaults(integer,integer,integer),
  public.jopml_admin_set_ai_user(uuid,integer,integer,integer), public.jopml_admin_people(integer) to authenticated;
revoke all on function public.jopml_ai_policy(uuid), public.jopml_ai_add_tokens(uuid,integer), public.jopml_ai_hit(uuid,integer,integer) from public, anon, authenticated;
grant execute on function public.jopml_ai_policy(uuid), public.jopml_ai_add_tokens(uuid,integer), public.jopml_ai_hit(uuid,integer,integer) to service_role;
