-- JOPML 1.7.7: Module teilen (Community > Module).
-- Module sind Python-Code. Deshalb: nur Textdateien, strenge Grenzen, JEDES Modul eines normalen Kontos muss erst von einem Admin
-- freigegeben werden, bevor andere es sehen. Alle Zugriffe laufen über SECURITY-DEFINER-Funktionen; die Tabellen sind für Clients gesperrt.

create table if not exists public.jopml_mod_shares (
  id          bigserial primary key,
  author_id   uuid not null references auth.users (id) on delete cascade,
  name        text not null,
  title       text not null,
  descr       text not null default '',
  version     text not null default '1.0.0',
  files       jsonb not null,
  size        integer not null,
  status      text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  hidden      boolean not null default false,
  note        text not null default '',
  downloads   integer not null default 0,
  created_at  timestamptz not null default now(),
  reviewed_at timestamptz
);
create index if not exists jopml_mod_shares_status on public.jopml_mod_shares (status, created_at desc);
create table if not exists public.jopml_mod_reports (
  mod_id     bigint not null references public.jopml_mod_shares (id) on delete cascade,
  reporter   uuid not null references auth.users (id) on delete cascade,
  reason     text not null default '',
  created_at timestamptz not null default now(),
  primary key (mod_id, reporter)
);
alter table public.jopml_mod_shares  enable row level security;
alter table public.jopml_mod_reports enable row level security;
revoke all on public.jopml_mod_shares, public.jopml_mod_reports from anon, authenticated, public;

-- Prüfung der Dateien: Objekt {Pfad: Text}, höchstens 40 Dateien, nur Textendungen, sichere Pfade, plugin.py vorhanden, höchstens 300 KB
create or replace function public.jopml_mod_files_ok(f jsonb) returns boolean
language plpgsql immutable set search_path = '' as $$
declare k text; v jsonb; total integer := 0; n integer := 0;
begin
  if f is null or jsonb_typeof(f) <> 'object' then return false; end if;
  if not (f ? 'plugin.py') then return false; end if;
  for k, v in select * from jsonb_each(f) loop
    n := n + 1;
    if n > 40 then return false; end if;
    if jsonb_typeof(v) <> 'string' then return false; end if;
    if k !~ '^[A-Za-z0-9_][A-Za-z0-9_./-]{0,80}$' or k ~ '\.\.' or k ~ '//' then return false; end if;
    if lower(k) !~ '\.(py|json|txt|md|csv)$' then return false; end if;
    total := total + length(v #>> '{}');
    if total > 300000 then return false; end if;
  end loop;
  return true;
end $$;

create or replace function public.jopml_mod_publish(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); n text := coalesce(p->>'name', ''); t text := btrim(coalesce(p->>'title', ''));
        d text := btrim(coalesce(p->>'descr', '')); v text := btrim(coalesce(p->>'version', '1.0.0')); f jsonb := p->'files';
        c text; mid bigint; st text; sz integer;
begin
  if n !~ '^[a-z][a-z0-9_]{1,30}$' or length(t) < 3 or length(t) > 60 or length(d) > 500 or length(v) > 20 then raise exception 'invalid_name'; end if;
  if not public.jopml_mod_files_ok(f) then raise exception 'invalid_module'; end if;
  c := coalesce(public.jopml_c_check(t), public.jopml_c_check(d));
  if c is not null then raise exception 'filtered:%', c; end if;
  if (select count(*) from public.jopml_mod_shares where author_id = u and created_at > now() - interval '1 day') >= 3 then raise exception 'rate_limited'; end if;
  if (select count(*) from public.jopml_mod_shares where author_id = u) >= 30 then raise exception 'limit_modules'; end if;
  sz := length(f::text);
  st := case when public.jopml_is_admin() then 'approved' else 'pending' end;
  insert into public.jopml_mod_shares (author_id, name, title, descr, version, files, size, status)
  values (u, n, t, d, v, f, sz, st) returning id into mid;
  return jsonb_build_object('id', mid, 'status', st);
end $$;

-- Liste: freigegebene, nicht ausgeblendete Module plus die eigenen (mit Status)
create or replace function public.jopml_mod_list(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); q text := lower(btrim(coalesce(p->>'q', ''))); srt text := coalesce(p->>'sort', 'new');
        lim integer := least(50, greatest(1, coalesce((p->>'limit')::integer, 30))); off integer := greatest(0, coalesce((p->>'offset')::integer, 0));
begin
  return coalesce((select jsonb_agg(to_jsonb(x)) from (
    select m.id, m.name, m.title, m.descr, m.version, m.size, cu.handle as author, m.downloads, m.created_at, m.status, m.hidden,
           (m.author_id = u) as mine, m.note
      from public.jopml_mod_shares m
      left join public.jopml_c_users cu on cu.user_id = m.author_id
     where ((m.status = 'approved' and not m.hidden) or m.author_id = u)
       and (q = '' or lower(m.title) like '%' || replace(replace(q, '%', ''), '_', '') || '%'
                   or lower(m.descr) like '%' || replace(replace(q, '%', ''), '_', '') || '%'
                   or m.name like '%' || replace(replace(q, '%', ''), '_', '') || '%')
     order by (m.author_id = u and m.status <> 'approved') desc,
              case when srt = 'popular' then m.downloads end desc nulls last, m.created_at desc
     limit lim offset off) x), '[]'::jsonb);
end $$;

-- Ein Modul samt Dateien holen (freigegeben, eigenes oder als Admin zur Prüfung)
create or replace function public.jopml_mod_get(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); m public.jopml_mod_shares; adm boolean := public.jopml_is_admin();
begin
  select * into m from public.jopml_mod_shares where id = (p->>'id')::bigint
     and ((status = 'approved' and not hidden) or author_id = u or adm);
  if not found then raise exception 'not_found'; end if;
  if m.author_id <> u and m.status = 'approved' and not m.hidden then
    update public.jopml_mod_shares set downloads = downloads + 1 where id = m.id;
  end if;
  return jsonb_build_object('id', m.id, 'name', m.name, 'title', m.title, 'descr', m.descr, 'version', m.version, 'files', m.files,
    'status', m.status, 'author', (select handle from public.jopml_c_users where user_id = m.author_id));
end $$;

create or replace function public.jopml_mod_pending(p jsonb default '{}'::jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  return coalesce((select jsonb_agg(to_jsonb(x)) from (
    select m.id, m.name, m.title, m.descr, m.version, m.size, cu.handle as author, m.created_at, m.status, m.hidden,
           (select count(*) from public.jopml_mod_reports r where r.mod_id = m.id) as reports
      from public.jopml_mod_shares m left join public.jopml_c_users cu on cu.user_id = m.author_id
     where m.status = 'pending' or m.hidden
     order by m.created_at limit 50) x), '[]'::jsonb);
end $$;

create or replace function public.jopml_mod_review(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare mid bigint := (p->>'id')::bigint; ok boolean := coalesce((p->>'approve')::boolean, false); nt text := left(btrim(coalesce(p->>'note', '')), 300);
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  if not exists (select 1 from public.jopml_mod_shares where id = mid) then raise exception 'not_found'; end if;
  update public.jopml_mod_shares
     set status = case when ok then 'approved' else 'rejected' end, hidden = false, note = nt, reviewed_at = now()
   where id = mid;
  if ok then delete from public.jopml_mod_reports where mod_id = mid; end if;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_mod_report(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); mid bigint := (p->>'id')::bigint;
begin
  if not exists (select 1 from public.jopml_mod_shares where id = mid and status = 'approved' and not hidden) then raise exception 'not_found'; end if;
  insert into public.jopml_mod_reports (mod_id, reporter, reason) values (mid, u, left(coalesce(p->>'reason', ''), 300))
  on conflict (mod_id, reporter) do nothing;
  if (select count(*) from public.jopml_mod_reports where mod_id = mid) >= 2 then
    update public.jopml_mod_shares set hidden = true where id = mid;
  end if;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_mod_delete(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); m public.jopml_mod_shares;
begin
  select * into m from public.jopml_mod_shares where id = (p->>'id')::bigint;
  if not found then raise exception 'not_found'; end if;
  if m.author_id <> u and not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  delete from public.jopml_mod_shares where id = m.id;
  return jsonb_build_object('ok', true);
end $$;

revoke all on function public.jopml_mod_files_ok(jsonb) from public, anon, authenticated;
revoke all on function public.jopml_mod_publish(jsonb), public.jopml_mod_list(jsonb), public.jopml_mod_get(jsonb),
  public.jopml_mod_pending(jsonb), public.jopml_mod_review(jsonb), public.jopml_mod_report(jsonb), public.jopml_mod_delete(jsonb) from public, anon;
grant execute on function public.jopml_mod_publish(jsonb), public.jopml_mod_list(jsonb), public.jopml_mod_get(jsonb),
  public.jopml_mod_pending(jsonb), public.jopml_mod_review(jsonb), public.jopml_mod_report(jsonb), public.jopml_mod_delete(jsonb) to authenticated;
