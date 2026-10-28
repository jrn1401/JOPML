-- JOPML 1.7.0: Admin-Übersicht, Lebenszeichen (online) und Fehlerberichte.
-- Stand wie auf dem Server eingespielt (Version 20261028201220). Tabellen: RLS an, keine Policies -> nur über die Funktionen.
create table if not exists public.jopml_presence (
  user_id uuid primary key references auth.users(id) on delete cascade,
  last_seen timestamptz not null default now(),
  version text, os text, page text
);
create table if not exists public.jopml_errors (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  version text, os text, kind text, message text, trace text
);
create index if not exists jopml_errors_created on public.jopml_errors(created_at desc);
alter table public.jopml_presence enable row level security;
alter table public.jopml_errors enable row level security;

create or replace function public.jopml_heartbeat(p_version text, p_os text, p_page text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return; end if;
  insert into public.jopml_presence(user_id, last_seen, version, os, page)
  values (auth.uid(), now(), left(p_version,20), left(p_os,40), left(p_page,40))
  on conflict (user_id) do update set last_seen = now(), version = excluded.version, os = excluded.os, page = excluded.page;
end $$;

create or replace function public.jopml_log_error(p_kind text, p_message text, p_trace text, p_version text, p_os text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return; end if;
  if (select count(*) from public.jopml_errors where user_id = auth.uid() and created_at > now() - interval '10 minutes') >= 20 then return; end if;
  insert into public.jopml_errors(user_id, version, os, kind, message, trace)
  values (auth.uid(), left(p_version,20), left(p_os,40), left(p_kind,40), left(p_message,500), left(p_trace,4000));
end $$;

create or replace function public.jopml_admin_overview()
returns jsonb language plpgsql security definer set search_path = '' as $$
declare r jsonb;
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  select jsonb_build_object(
    'online_now', (select count(*) from public.jopml_presence where last_seen > now() - interval '2 minutes'),
    'online_24h', (select count(*) from public.jopml_presence where last_seen > now() - interval '24 hours'),
    'registered', (select count(*) from auth.users),
    'new_7d', (select count(*) from auth.users where created_at > now() - interval '7 days'),
    'errors_24h', (select count(*) from public.jopml_errors where created_at > now() - interval '24 hours'),
    'errors_total', (select count(*) from public.jopml_errors),
    'db_bytes', pg_database_size(current_database()),
    'connections', (select count(*) from pg_stat_activity where datname = current_database()),
    'max_connections', current_setting('max_connections')::int,
    'started_at', pg_postmaster_start_time(),
    'server_time', now(),
    'pg_version', current_setting('server_version'),
    'cache_hit', (select round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 1) from pg_stat_database where datname = current_database()),
    'messages', (select count(*) from public.jopml_c_messages),
    'macros', (select count(*) from public.jopml_m_macros),
    'versions', coalesce((select jsonb_agg(jsonb_build_object('v', version, 'n', n)) from (select coalesce(version,'?') version, count(*) n from public.jopml_presence where last_seen > now() - interval '7 days' group by 1 order by 2 desc limit 8) x), '[]'::jsonb),
    'top_tables', coalesce((select jsonb_agg(jsonb_build_object('t', relname, 'b', sz)) from (select relname, pg_total_relation_size(c.oid) sz from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' order by 2 desc limit 5) y), '[]'::jsonb)
  ) into r;
  return r;
end $$;

create or replace function public.jopml_admin_users(p_limit int default 100)
returns table(email text, created_at timestamptz, last_sign_in_at timestamptz, last_seen timestamptz, online boolean)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select u.email::text, u.created_at, u.last_sign_in_at, p.last_seen,
    coalesce(p.last_seen > now() - interval '2 minutes', false)
  from auth.users u left join public.jopml_presence p on p.user_id = u.id
  order by u.created_at desc limit greatest(1, least(p_limit, 500));
end $$;

create or replace function public.jopml_admin_errors(p_limit int default 100)
returns table(id bigint, created_at timestamptz, version text, os text, kind text, message text, trace text)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select e.id, e.created_at, e.version, e.os, e.kind, e.message, e.trace
  from public.jopml_errors e order by e.created_at desc limit greatest(1, least(p_limit, 500));
end $$;

create or replace function public.jopml_admin_clear_errors()
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  delete from public.jopml_errors;
end $$;

revoke all on function public.jopml_heartbeat(text,text,text), public.jopml_log_error(text,text,text,text,text),
  public.jopml_admin_overview(), public.jopml_admin_users(int), public.jopml_admin_errors(int), public.jopml_admin_clear_errors() from public, anon;
grant execute on function public.jopml_heartbeat(text,text,text), public.jopml_log_error(text,text,text,text,text),
  public.jopml_admin_overview(), public.jopml_admin_users(int), public.jopml_admin_errors(int), public.jopml_admin_clear_errors() to authenticated;
