-- 1.10.0: KI-Budget (80 %-Warnung), Nutzungslog pro Anbieter, Fehler-Tickets, Antworten an Melder, optionaler Kontext.
alter table public.jopml_ai_settings add column if not exists global_requests integer not null default 2000;
alter table public.jopml_ai_settings add column if not exists global_tokens bigint not null default 5000000;

create table if not exists public.jopml_ai_log (
  day date not null default current_date,
  provider text not null,
  model text not null,
  hits integer not null default 0,
  tokens bigint not null default 0,
  fallbacks integer not null default 0,
  primary key (day, provider, model)
);
alter table public.jopml_ai_log enable row level security;
revoke all on public.jopml_ai_log from anon, authenticated, public;

create table if not exists public.jopml_tickets (
  id bigint generated always as identity primary key,
  fingerprint text,
  code text,
  title text not null,
  status text not null default 'new' check (status in ('new', 'in_progress', 'fixed')),
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.jopml_tickets enable row level security;
revoke all on public.jopml_tickets from anon, authenticated, public;

alter table public.jopml_user_reports add column if not exists ticket_id bigint references public.jopml_tickets (id) on delete set null;
alter table public.jopml_user_reports add column if not exists reply text;
alter table public.jopml_user_reports add column if not exists replied_at timestamptz;
alter table public.jopml_user_reports add column if not exists reply_seen boolean not null default true;
alter table public.jopml_user_reports add column if not exists context text;
alter table public.jopml_error_groups add column if not exists sample_context text;

-- Kontext (optional, vom Nutzer erlaubt) kommt als zusätzlicher Parameter; die alten Aufrufe ohne Kontext gehen weiter.
create or replace function public.jopml_report_error(p_code text, p_kind text, p_message text, p_trace text, p_version text, p_os text, p_context text)
returns void language plpgsql security definer set search_path = '' as $$
declare fp text; msg text; v text; o text;
begin
  if auth.uid() is null then return; end if;
  msg := left(coalesce(p_message, ''), 600);
  v := left(coalesce(p_version, '?'), 20);
  o := left(coalesce(p_os, '?'), 40);
  fp := md5(coalesce(p_code, '') || '|' || left(coalesce(p_kind, ''), 40) || '|' || regexp_replace(left(msg, 160), '[0-9a-fA-F-]{6,}|[0-9]+', '#', 'g'));
  insert into public.jopml_error_groups as g (fingerprint, code, kind, message, sample_trace, sample_context, versions, systems)
    values (fp, left(p_code, 20), left(coalesce(p_kind, 'error'), 40), msg, left(p_trace, 3000), left(p_context, 300), jsonb_build_object(v, 1), jsonb_build_object(o, 1))
  on conflict (fingerprint) do update set
    hits = g.hits + 1, last_seen = now(),
    sample_context = coalesce(g.sample_context, excluded.sample_context),
    versions = jsonb_set(g.versions, array[v], to_jsonb(coalesce((g.versions ->> v)::int, 0) + 1)),
    systems = jsonb_set(g.systems, array[o], to_jsonb(coalesce((g.systems ->> o)::int, 0) + 1));
  if (select count(*) from public.jopml_error_groups) > 2000 then
    delete from public.jopml_error_groups where fingerprint in (select fingerprint from public.jopml_error_groups order by last_seen asc limit 200);
  end if;
end $$;

create or replace function public.jopml_log_error(p_kind text, p_message text, p_trace text, p_version text, p_os text)
returns void language sql security definer set search_path = '' as $$
  select public.jopml_report_error(null, p_kind, p_message, p_trace, p_version, p_os, null);
$$;
drop function if exists public.jopml_report_error(text, text, text, text, text, text);

drop function if exists public.jopml_user_report(text, text, text, text, text);
create or replace function public.jopml_user_report(p_category text, p_message text, p_code text, p_version text, p_os text, p_context text default null)
returns void language plpgsql security definer set search_path = '' as $$
declare tid bigint;
begin
  if auth.uid() is null then raise exception 'not allowed'; end if;
  if length(trim(coalesce(p_message, ''))) < 5 then raise exception 'too short'; end if;
  if (select count(*) from public.jopml_user_reports where user_id = auth.uid() and created_at > now() - interval '1 day') >= 10 then
    raise exception 'rate_limited';
  end if;
  -- gleicher Fehlercode wie ein offenes Ticket: Meldung wird automatisch verknüpft
  if p_code is not null then
    select t.id into tid from public.jopml_tickets t where t.code = p_code and t.status <> 'fixed' order by t.id desc limit 1;
  end if;
  insert into public.jopml_user_reports (user_id, category, code, message, version, os, context, ticket_id)
    values (auth.uid(), left(coalesce(p_category, 'bug'), 30), left(p_code, 20), left(p_message, 2000), left(p_version, 20), left(p_os, 40), left(p_context, 300), tid);
  delete from public.jopml_user_reports where created_at < now() - interval '180 days';
end $$;

-- Nutzer sehen eigene Meldungen mit Ticket-Status und Antwort
create or replace function public.jopml_my_reports()
returns table(id bigint, created_at timestamptz, category text, code text, message text, status text, reply text, replied_at timestamptz, reply_seen boolean)
language sql security definer set search_path = '' as $$
  select r.id, r.created_at, r.category, r.code, left(r.message, 300), t.status, r.reply, r.replied_at, r.reply_seen
  from public.jopml_user_reports r left join public.jopml_tickets t on t.id = r.ticket_id
  where r.user_id = auth.uid() order by r.created_at desc limit 30;
$$;
create or replace function public.jopml_my_reports_seen()
returns void language sql security definer set search_path = '' as $$
  update public.jopml_user_reports set reply_seen = true where user_id = auth.uid() and reply is not null and not reply_seen;
$$;

drop function if exists public.jopml_admin_user_reports(integer);
create or replace function public.jopml_admin_user_reports(p_limit integer default 100)
returns table(id bigint, created_at timestamptz, category text, code text, message text, version text, os text, email text, context text, ticket_id bigint, ticket_status text, reply text)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select r.id, r.created_at, r.category, r.code, r.message, r.version, r.os, u.email::text, r.context, r.ticket_id, t.status, r.reply
    from public.jopml_user_reports r left join auth.users u on u.id = r.user_id left join public.jopml_tickets t on t.id = r.ticket_id
    order by r.created_at desc limit greatest(1, least(p_limit, 500));
end $$;

-- Tickets (Admin)
create or replace function public.jopml_admin_tickets()
returns table(id bigint, fingerprint text, code text, title text, status text, note text, created_at timestamptz, updated_at timestamptz, reports bigint)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select t.id, t.fingerprint, t.code, t.title, t.status, t.note, t.created_at, t.updated_at,
                      (select count(*) from public.jopml_user_reports r where r.ticket_id = t.id)
               from public.jopml_tickets t order by (t.status = 'fixed'), t.updated_at desc limit 300;
end $$;

create or replace function public.jopml_admin_ticket_from_group(p_fingerprint text, p_title text)
returns bigint language plpgsql security definer set search_path = '' as $$
declare g public.jopml_error_groups; tid bigint;
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  select * into g from public.jopml_error_groups where fingerprint = p_fingerprint;
  if not found then raise exception 'unknown group'; end if;
  select id into tid from public.jopml_tickets where fingerprint = p_fingerprint and status <> 'fixed' limit 1;
  if tid is null then
    insert into public.jopml_tickets (fingerprint, code, title) values (p_fingerprint, g.code, left(coalesce(nullif(trim(p_title), ''), g.message), 200)) returning id into tid;
  end if;
  if g.code is not null then
    update public.jopml_user_reports set ticket_id = tid where code = g.code and ticket_id is null;
  end if;
  insert into public.jopml_admin_audit (admin_id, action, detail) values (auth.uid(), 'ticket_create', tid::text);
  return tid;
end $$;

create or replace function public.jopml_admin_ticket_set(p_id bigint, p_status text, p_note text default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if p_status not in ('new', 'in_progress', 'fixed') then raise exception 'bad status'; end if;
  update public.jopml_tickets set status = p_status, note = coalesce(left(p_note, 1000), note), updated_at = now() where id = p_id;
  insert into public.jopml_admin_audit (admin_id, action, detail) values (auth.uid(), 'ticket_set', p_id || ':' || p_status);
end $$;

create or replace function public.jopml_admin_report_link(p_report bigint, p_ticket bigint)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  update public.jopml_user_reports set ticket_id = p_ticket where id = p_report;
end $$;

create or replace function public.jopml_admin_report_reply(p_report bigint, p_text text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if length(trim(coalesce(p_text, ''))) < 2 then raise exception 'too short'; end if;
  update public.jopml_user_reports set reply = left(p_text, 1000), replied_at = now(), reply_seen = false where id = p_report;
  insert into public.jopml_admin_audit (admin_id, action, detail) values (auth.uid(), 'report_reply', p_report::text);
end $$;

-- KI-Budget (80 %-Warnung) und Nutzung pro Tag und Anbieter
create or replace function public.jopml_admin_set_ai_budget(p_requests integer, p_tokens bigint)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if p_requests not between -1 and 1000000 or p_tokens not between -1 and 10000000000 then raise exception 'bad limit'; end if;
  update public.jopml_ai_settings set global_requests = p_requests, global_tokens = p_tokens, updated_at = now() where id = 1;
  insert into public.jopml_admin_audit (admin_id, action, detail) values (auth.uid(), 'set_ai_budget', p_requests || '/' || p_tokens);
end $$;

create or replace function public.jopml_admin_ai_budget()
returns table(requests_today integer, requests_budget integer, tokens_today bigint, tokens_budget bigint)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select coalesce((select g.hits from public.jopml_ai_global g where g.day = current_date), 0), s.global_requests,
                      coalesce((select sum(l.tokens)::bigint from public.jopml_ai_log l where l.day = current_date), 0), s.global_tokens
               from public.jopml_ai_settings s where s.id = 1;
end $$;

create or replace function public.jopml_admin_ai_stats(p_days integer default 14)
returns table(day date, provider text, hits bigint, tokens bigint, fallbacks bigint)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query select l.day, l.provider, sum(l.hits)::bigint, sum(l.tokens)::bigint, sum(l.fallbacks)::bigint
               from public.jopml_ai_log l where l.day > current_date - greatest(1, least(p_days, 90))
               group by l.day, l.provider order by l.day;
end $$;

create or replace function public.jopml_ai_log(p_provider text, p_model text, p_tokens integer, p_fallback boolean)
returns void language sql security definer set search_path = '' as $$
  insert into public.jopml_ai_log as t (day, provider, model, hits, tokens, fallbacks)
  values (current_date, left(p_provider, 20), left(p_model, 80), 1, greatest(p_tokens, 0), case when p_fallback then 1 else 0 end)
  on conflict (day, provider, model) do update set hits = t.hits + 1, tokens = t.tokens + greatest(p_tokens, 0),
    fallbacks = t.fallbacks + case when p_fallback then 1 else 0 end;
$$;

-- Globales Budget kommt jetzt aus den Einstellungen (Parameter bleibt als Rückfall); -1 = kein Budget
create or replace function public.jopml_ai_hit(p_user uuid, p_user_limit integer default 60, p_global_limit integer default 2000)
returns integer language plpgsql security definer set search_path = '' as $$
declare u integer; g integer; lim integer; tl integer; tu bigint; gl integer; gt bigint; gtu bigint;
begin
  select coalesce(l.daily_limit, s.daily_requests), coalesce(l.daily_tokens, s.daily_tokens), s.global_requests, s.global_tokens
    into lim, tl, gl, gt from public.jopml_ai_settings s left join public.jopml_ai_limits l on l.user_id = p_user where s.id = 1;
  lim := coalesce(lim, p_user_limit);
  gl := coalesce(gl, p_global_limit);
  select coalesce(x.tokens, 0) into tu from public.jopml_ai_usage x where x.user_id = p_user and x.day = current_date;
  if tl is not null and tl >= 0 and coalesce(tu, 0) >= tl then raise exception 'token_limited'; end if;
  if gt is not null and gt >= 0 then
    select coalesce(sum(l.tokens), 0) into gtu from public.jopml_ai_log l where l.day = current_date;
    if gtu >= gt then raise exception 'rate_limited_global'; end if;
  end if;
  insert into public.jopml_ai_global as t (day, hits) values (current_date, 1)
    on conflict (day) do update set hits = t.hits + 1 returning hits into g;
  if gl >= 0 and g > gl then raise exception 'rate_limited_global'; end if;
  insert into public.jopml_ai_usage as t (user_id, day, hits) values (p_user, current_date, 1)
    on conflict (user_id, day) do update set hits = t.hits + 1 returning hits into u;
  if lim >= 0 and u > lim then raise exception 'rate_limited'; end if;
  return case when lim < 0 then 999999 else lim - u end;
end $$;

revoke all on function public.jopml_report_error(text,text,text,text,text,text,text), public.jopml_user_report(text,text,text,text,text,text),
  public.jopml_my_reports(), public.jopml_my_reports_seen(), public.jopml_admin_user_reports(integer), public.jopml_admin_tickets(),
  public.jopml_admin_ticket_from_group(text,text), public.jopml_admin_ticket_set(bigint,text,text), public.jopml_admin_report_link(bigint,bigint),
  public.jopml_admin_report_reply(bigint,text), public.jopml_admin_set_ai_budget(integer,bigint), public.jopml_admin_ai_budget(),
  public.jopml_admin_ai_stats(integer) from public, anon;
grant execute on function public.jopml_report_error(text,text,text,text,text,text,text), public.jopml_user_report(text,text,text,text,text,text),
  public.jopml_my_reports(), public.jopml_my_reports_seen(), public.jopml_admin_user_reports(integer), public.jopml_admin_tickets(),
  public.jopml_admin_ticket_from_group(text,text), public.jopml_admin_ticket_set(bigint,text,text), public.jopml_admin_report_link(bigint,bigint),
  public.jopml_admin_report_reply(bigint,text), public.jopml_admin_set_ai_budget(integer,bigint), public.jopml_admin_ai_budget(),
  public.jopml_admin_ai_stats(integer) to authenticated;
revoke all on function public.jopml_ai_log(text,text,integer,boolean), public.jopml_ai_hit(uuid,integer,integer) from public, anon, authenticated;
grant execute on function public.jopml_ai_log(text,text,integer,boolean), public.jopml_ai_hit(uuid,integer,integer) to service_role;
