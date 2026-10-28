-- JOPML 1.4.0: Server-Einladung per E-Mail-Adresse.
-- Die Antwort ist immer gleich ("ok"), egal ob es ein Konto mit dieser Adresse gibt -> man kann keine Adressen ausforschen.
create table if not exists public.jopml_c_email_tries (
  user_id    uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);
create index if not exists jopml_c_email_tries_user on public.jopml_c_email_tries (user_id, created_at);
alter table public.jopml_c_email_tries enable row level security;
revoke all on public.jopml_c_email_tries from anon, authenticated, public;

create or replace function public.jopml_c_invite_email(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; mail text := lower(btrim(coalesce(p->>'email', ''))); t uuid;
begin
  if not exists (select 1 from public.jopml_c_spaces where id = sid and kind = 'server') or public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  if mail !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' or length(mail) > 254 then raise exception 'invalid_email'; end if;
  if (select count(*) from public.jopml_c_email_tries where user_id = u and created_at > now() - interval '1 day') >= 20 then raise exception 'rate_limited'; end if;
  insert into public.jopml_c_email_tries (user_id) values (u);
  select cu.user_id into t from auth.users a join public.jopml_c_users cu on cu.user_id = a.id where lower(a.email) = mail;
  if t is not null and t <> u
     and not exists (select 1 from public.jopml_c_members where space_id = sid and user_id = t)
     and not exists (select 1 from public.jopml_c_bans where space_id = sid and user_id = t)
     and (select count(*) from public.jopml_c_user_invites where invitee = t) < 30 then
    insert into public.jopml_c_user_invites (space_id, invitee, invited_by) values (sid, t, u) on conflict do nothing;
  end if;
  return jsonb_build_object('ok', true);
end $$;
revoke all on function public.jopml_c_invite_email(jsonb) from public, anon;
grant execute on function public.jopml_c_invite_email(jsonb) to authenticated;
