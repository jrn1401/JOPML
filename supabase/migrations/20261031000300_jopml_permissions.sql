-- Berechtigungen (nur Admins): Admin-Rolle vergeben/entziehen und KI-Tageslimit pro Nutzer ändern. Jede Änderung wird protokolliert.
create table if not exists public.jopml_ai_limits (
  user_id uuid primary key references auth.users (id) on delete cascade,
  daily_limit integer not null check (daily_limit between 0 and 100000),
  set_by uuid,
  updated_at timestamptz not null default now()
);
create table if not exists public.jopml_admin_audit (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  admin_id uuid,
  action text not null,
  target uuid,
  detail text
);
alter table public.jopml_ai_limits enable row level security;
alter table public.jopml_admin_audit enable row level security;
revoke all on public.jopml_ai_limits, public.jopml_admin_audit from anon, authenticated, public;

-- Liste für den Reiter "Berechtigungen"
create or replace function public.jopml_admin_people(p_limit integer default 200)
returns table(user_id uuid, email text, created_at timestamptz, is_admin boolean, ai_limit integer, ai_today integer)
language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  return query
    select u.id, u.email::text, u.created_at,
           exists (select 1 from public.jopml_admins a where a.user_id = u.id),
           l.daily_limit,
           coalesce((select x.hits from public.jopml_ai_usage x where x.user_id = u.id and x.day = current_date), 0)
    from auth.users u left join public.jopml_ai_limits l on l.user_id = u.id
    order by u.created_at desc limit greatest(1, least(p_limit, 500));
end $$;

create or replace function public.jopml_admin_set_admin(p_user uuid, p_admin boolean)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if not exists (select 1 from auth.users where id = p_user) then raise exception 'unknown user'; end if;
  if p_admin then
    insert into public.jopml_admins (user_id, note) values (p_user, 'granted by admin') on conflict (user_id) do nothing;
  else
    if p_user = auth.uid() then raise exception 'cannot remove yourself'; end if;
    if (select count(*) from public.jopml_admins) <= 1 then raise exception 'last admin'; end if;
    delete from public.jopml_admins where user_id = p_user;
  end if;
  insert into public.jopml_admin_audit (admin_id, action, target, detail) values (auth.uid(), case when p_admin then 'grant_admin' else 'revoke_admin' end, p_user, null);
end $$;

-- p_limit = null entfernt die Sonderregel (dann gilt wieder der Standard)
create or replace function public.jopml_admin_set_ai_limit(p_user uuid, p_limit integer)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.jopml_is_admin() then raise exception 'not allowed'; end if;
  if not exists (select 1 from auth.users where id = p_user) then raise exception 'unknown user'; end if;
  if p_limit is null then
    delete from public.jopml_ai_limits where user_id = p_user;
  else
    if p_limit < 0 or p_limit > 100000 then raise exception 'bad limit'; end if;
    insert into public.jopml_ai_limits (user_id, daily_limit, set_by) values (p_user, p_limit, auth.uid())
      on conflict (user_id) do update set daily_limit = excluded.daily_limit, set_by = excluded.set_by, updated_at = now();
  end if;
  insert into public.jopml_admin_audit (admin_id, action, target, detail) values (auth.uid(), 'set_ai_limit', p_user, coalesce(p_limit::text, 'default'));
end $$;

-- KI-Kontingent: ein persönliches Limit hat Vorrang vor dem Standard der Edge Function
create or replace function public.jopml_ai_hit(p_user uuid, p_user_limit integer default 60, p_global_limit integer default 2000)
returns integer language plpgsql security definer set search_path = '' as $$
declare u integer; g integer; lim integer;
begin
  select l.daily_limit into lim from public.jopml_ai_limits l where l.user_id = p_user;
  lim := coalesce(lim, p_user_limit);
  insert into public.jopml_ai_global as t (day, hits) values (current_date, 1)
    on conflict (day) do update set hits = t.hits + 1 returning hits into g;
  if g > p_global_limit then raise exception 'rate_limited_global'; end if;
  insert into public.jopml_ai_usage as t (user_id, day, hits) values (p_user, current_date, 1)
    on conflict (user_id, day) do update set hits = t.hits + 1 returning hits into u;
  if u > lim then raise exception 'rate_limited'; end if;
  return lim - u;
end $$;

revoke all on function public.jopml_admin_people(integer), public.jopml_admin_set_admin(uuid, boolean), public.jopml_admin_set_ai_limit(uuid, integer) from public, anon;
grant execute on function public.jopml_admin_people(integer), public.jopml_admin_set_admin(uuid, boolean), public.jopml_admin_set_ai_limit(uuid, integer) to authenticated;
revoke all on function public.jopml_ai_hit(uuid, integer, integer) from public, anon, authenticated;
grant execute on function public.jopml_ai_hit(uuid, integer, integer) to service_role;
