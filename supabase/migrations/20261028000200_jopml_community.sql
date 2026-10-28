-- JOPML v1.3 – Community: Server, Kanäle, Direktnachrichten (Ende-zu-Ende-verschlüsselt) und öffentliches Forum.
--
-- WAS DER SERVER SIEHT
--   * Nachrichten (Server-Chats und DMs) liegen NUR als Chiffretext in `body` (AES-256-GCM, Schlüssel nur auf den Geräten der
--     Mitglieder). Der Server kennt Absender, Kanal, Zeitpunkt und Größe – nicht den Inhalt.
--   * Die privaten Schlüssel der Nutzer liegen hier nur passwortgeschützt ("key_bundle", scrypt + AES-GCM). Ohne die
--     Passphrase des Nutzers kann der Server sie nicht öffnen.
--   * Die Gruppenschlüssel liegen als "Wraps" (je Mitglied mit dessen öffentlichem Schlüssel verpackt) in jopml_c_wraps.
--   * Namen von Servern/Kanälen, Benutzernamen und das FORUM sind Klartext (öffentlich bzw. für Einladungen nötig) und
--     werden serverseitig gefiltert (jopml_c_assert_clean). Chat-Inhalte filtert nur der Client.
--   * Meldungen (jopml_c_reports) enthalten nur, was der Melder freiwillig mitschickt (Klartext der gemeldeten Nachricht).
--
-- ZUGRIFF: RLS ist überall an, es gibt absichtlich KEINE Policies. Alles läuft über SECURITY-DEFINER-Funktionen, die
-- immer auth.uid() verwenden und Rechte (Mitglied/Admin/Owner) selbst prüfen. anon hat keinerlei Zugriff.

-- ---------------------------------------------------------------- Tabellen
create table if not exists public.jopml_c_users (
  user_id      uuid primary key references auth.users (id) on delete cascade,
  handle       text not null check (handle ~ '^[a-z0-9_.-]{3,24}$'),
  display_name text not null check (char_length(display_name) between 1 and 40),
  enc_pub      text not null check (enc_pub ~ '^[A-Za-z0-9_=-]{40,64}$'),
  sign_pub     text not null check (sign_pub ~ '^[A-Za-z0-9_=-]{40,64}$'),
  key_bundle   text not null check (char_length(key_bundle) <= 4000),
  created_at   timestamptz not null default now()
);
create unique index if not exists jopml_c_users_handle_key on public.jopml_c_users (handle);

create table if not exists public.jopml_c_suspended (
  user_id uuid primary key references auth.users (id) on delete cascade,
  reason text, created_at timestamptz not null default now()
);

create table if not exists public.jopml_c_spaces (
  id             uuid primary key default gen_random_uuid(),
  kind           text not null check (kind in ('server', 'dm')),
  name           text not null default '',
  owner_id       uuid references auth.users (id) on delete cascade,     -- Konto gelöscht -> Server wird mit gelöscht
  epoch          integer not null default 1,
  needs_rotation boolean not null default false,
  created_at     timestamptz not null default now()
);
create table if not exists public.jopml_c_members (
  space_id  uuid not null references public.jopml_c_spaces (id) on delete cascade,
  user_id   uuid not null references auth.users (id) on delete cascade,
  role      text not null default 'member' check (role in ('owner', 'admin', 'member')),
  status    text not null default 'active' check (status in ('pending', 'active')),
  joined_at timestamptz not null default now(),
  primary key (space_id, user_id)
);
create index if not exists jopml_c_members_user on public.jopml_c_members (user_id);
create table if not exists public.jopml_c_bans (
  space_id uuid not null references public.jopml_c_spaces (id) on delete cascade,
  user_id  uuid not null references auth.users (id) on delete cascade,
  primary key (space_id, user_id)
);
create table if not exists public.jopml_c_wraps (
  space_id   uuid not null references public.jopml_c_spaces (id) on delete cascade,
  epoch      integer not null,
  user_id    uuid not null references auth.users (id) on delete cascade,
  wrapped    text not null check (char_length(wrapped) <= 600),
  wrapped_by uuid references auth.users (id) on delete set null,
  primary key (space_id, epoch, user_id)
);
create table if not exists public.jopml_c_channels (
  id         uuid primary key default gen_random_uuid(),
  space_id   uuid not null references public.jopml_c_spaces (id) on delete cascade,
  name       text not null,
  position   integer not null default 0,
  created_at timestamptz not null default now()
);
create unique index if not exists jopml_c_channels_name on public.jopml_c_channels (space_id, name);
create table if not exists public.jopml_c_messages (
  id         bigint generated always as identity primary key,
  channel_id uuid not null references public.jopml_c_channels (id) on delete cascade,
  space_id   uuid not null references public.jopml_c_spaces (id) on delete cascade,
  sender_id  uuid not null references auth.users (id) on delete cascade,
  epoch      integer not null,
  body       text not null check (char_length(body) <= 16000),
  sig        text not null check (char_length(sig) <= 200),
  created_at timestamptz not null default now()
);
create index if not exists jopml_c_messages_channel on public.jopml_c_messages (channel_id, id);
create index if not exists jopml_c_messages_sender on public.jopml_c_messages (sender_id, created_at);
create table if not exists public.jopml_c_invites (
  code       text primary key,
  space_id   uuid not null references public.jopml_c_spaces (id) on delete cascade,
  created_by uuid references auth.users (id) on delete cascade,
  expires_at timestamptz not null,
  max_uses   integer not null default 10,
  uses       integer not null default 0,
  created_at timestamptz not null default now()
);
create table if not exists public.jopml_c_user_invites (
  space_id   uuid not null references public.jopml_c_spaces (id) on delete cascade,
  invitee    uuid not null references auth.users (id) on delete cascade,
  invited_by uuid references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (space_id, invitee)
);
create table if not exists public.jopml_c_reports (
  id            bigint generated always as identity primary key,
  reporter      uuid references auth.users (id) on delete set null,
  kind          text not null check (kind in ('message', 'thread', 'post', 'server', 'user')),
  space_id      uuid,
  ref_id        text,
  reported_user uuid references auth.users (id) on delete set null,
  reason        text not null check (char_length(reason) <= 500),
  evidence      text check (char_length(evidence) <= 10000),
  evidence_sig  text check (char_length(evidence_sig) <= 200),
  status        text not null default 'open' check (status in ('open', 'done')),
  created_at    timestamptz not null default now()
);

-- Forum (öffentlich, Klartext)
create table if not exists public.jopml_f_boards (id text primary key, sort integer not null default 0);
create table if not exists public.jopml_f_threads (
  id        bigint generated always as identity primary key,
  board     text not null references public.jopml_f_boards (id) on delete cascade,
  author_id uuid references auth.users (id) on delete set null,
  title     text not null check (char_length(title) between 3 and 120),
  body      text not null check (char_length(body) between 1 and 8000),
  created_at timestamptz not null default now(),
  last_at   timestamptz not null default now(),
  replies   integer not null default 0,
  locked    boolean not null default false,
  pinned    boolean not null default false
);
create index if not exists jopml_f_threads_board on public.jopml_f_threads (board, pinned desc, last_at desc);
create table if not exists public.jopml_f_posts (
  id        bigint generated always as identity primary key,
  thread_id bigint not null references public.jopml_f_threads (id) on delete cascade,
  author_id uuid references auth.users (id) on delete set null,
  body      text not null check (char_length(body) between 1 and 8000),
  created_at timestamptz not null default now()
);
create index if not exists jopml_f_posts_thread on public.jopml_f_posts (thread_id, id);
insert into public.jopml_f_boards (id, sort) values ('general', 1), ('help', 2), ('macros', 3), ('ideas', 4), ('offtopic', 5)
  on conflict do nothing;

do $$
declare t text;
begin
  foreach t in array array['jopml_c_users','jopml_c_suspended','jopml_c_spaces','jopml_c_members','jopml_c_bans','jopml_c_wraps',
      'jopml_c_channels','jopml_c_messages','jopml_c_invites','jopml_c_user_invites','jopml_c_reports','jopml_f_boards',
      'jopml_f_threads','jopml_f_posts'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated, public', t);
  end loop;
end $$;

-- ---------------------------------------------------------------- interne Helfer (kein Zugriff für Clients)
create or replace function public.jopml_c_uid() returns uuid
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := auth.uid();
begin
  if u is null then raise exception 'not_authenticated'; end if;
  if exists (select 1 from public.jopml_c_suspended where user_id = u) then raise exception 'suspended'; end if;
  return u;
end $$;

create or replace function public.jopml_c_reg() returns uuid          -- angemeldet UND für die Community eingerichtet
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_uid();
begin
  if not exists (select 1 from public.jopml_c_users where user_id = u) then raise exception 'not_registered'; end if;
  return u;
end $$;

create or replace function public.jopml_c_role(s uuid, u uuid) returns text      -- Rolle als AKTIVES Mitglied, sonst NULL
language sql stable security definer set search_path = '' as $$
  select role from public.jopml_c_members where space_id = s and user_id = u and status = 'active'
$$;

create or replace function public.jopml_c_is_mod(s uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(public.jopml_c_role(s, u) in ('owner', 'admin'), false)
$$;

revoke all on function public.jopml_c_uid() from public, anon, authenticated;
revoke all on function public.jopml_c_reg() from public, anon, authenticated;
revoke all on function public.jopml_c_role(uuid, uuid) from public, anon, authenticated;
revoke all on function public.jopml_c_is_mod(uuid, uuid) from public, anon, authenticated;

-- ---------------------------------------------------------------- Einrichtung & Verzeichnis
create or replace function public.jopml_c_me() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := auth.uid(); r public.jopml_c_users;
begin
  if u is null then raise exception 'not_authenticated'; end if;
  select * into r from public.jopml_c_users where user_id = u;
  if not found then
    return jsonb_build_object('registered', false, 'suggested_handle', (select username from public.jopml_profiles where user_id = u),
                              'is_admin', public.jopml_is_admin());
  end if;
  return jsonb_build_object('registered', true, 'user_id', r.user_id, 'handle', r.handle, 'display_name', r.display_name,
                            'enc_pub', r.enc_pub, 'sign_pub', r.sign_pub, 'bundle', r.key_bundle, 'is_admin', public.jopml_is_admin());
end $$;

create or replace function public.jopml_c_setup(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  u uuid := public.jopml_c_uid();
  h text := lower(btrim(coalesce(p->>'handle', '')));
  d text := left(btrim(coalesce(p->>'display', '')), 40);
  prof text;
begin
  if jsonb_typeof(p) is distinct from 'object' then raise exception 'invalid_payload'; end if;
  if exists (select 1 from public.jopml_c_users where user_id = u) then raise exception 'already_registered'; end if;
  select username into prof from public.jopml_profiles where user_id = u;
  if prof is not null then h := prof;                                            -- Passwort-Konto: Benutzername bleibt gleich
  elsif exists (select 1 from public.jopml_profiles where lower(username) = h) then raise exception 'handle_taken';
  end if;
  if h !~ '^[a-z0-9_.-]{3,24}$' then raise exception 'invalid_handle'; end if;
  if d = '' then d := h; end if;
  if coalesce(p->>'enc_pub', '') !~ '^[A-Za-z0-9_=-]{40,64}$' or coalesce(p->>'sign_pub', '') !~ '^[A-Za-z0-9_=-]{40,64}$'
     or char_length(coalesce(p->>'bundle', '')) not between 20 and 4000 then raise exception 'invalid_keys'; end if;
  if public.jopml_c_check(h) is not null or public.jopml_c_check(d) is not null then raise exception 'name_not_allowed'; end if;
  if exists (select 1 from public.jopml_c_users where handle = h) then raise exception 'handle_taken'; end if;
  insert into public.jopml_c_users (user_id, handle, display_name, enc_pub, sign_pub, key_bundle)
  values (u, h, d, p->>'enc_pub', p->>'sign_pub', p->>'bundle');
  return public.jopml_c_me();
end $$;

create or replace function public.jopml_c_set_display(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); d text := left(btrim(coalesce(p->>'display', '')), 40);
begin
  if d = '' then raise exception 'invalid_name'; end if;
  if public.jopml_c_check(d) is not null then raise exception 'name_not_allowed'; end if;
  update public.jopml_c_users set display_name = d where user_id = u;
  return public.jopml_c_me();
end $$;

-- Genau ein Benutzername wird aufgelöst (keine Suche/Liste).
create or replace function public.jopml_c_lookup(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); r public.jopml_c_users;
begin
  select * into r from public.jopml_c_users where handle = lower(btrim(coalesce(p->>'handle', '')));
  if not found then return null; end if;
  return jsonb_build_object('user_id', r.user_id, 'handle', r.handle, 'display_name', r.display_name,
                            'enc_pub', r.enc_pub, 'sign_pub', r.sign_pub);
end $$;

-- Passphrase vergessen: Community-Identität zurücksetzen. Entfernt Schlüssel, eigene Server, DMs, Mitgliedschaften und eigene Nachrichten;
-- danach ist eine neue Einrichtung (mit neuer Passphrase und neuem Schlüssel) möglich. Das Forum bleibt (Beiträge zeigen dann "[gelöscht]").
create or replace function public.jopml_c_reset() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg();
begin
  delete from public.jopml_c_spaces where owner_id = u;
  delete from public.jopml_c_spaces where kind = 'dm' and id in (select space_id from public.jopml_c_members where user_id = u);
  delete from public.jopml_c_messages where sender_id = u;
  delete from public.jopml_c_members where user_id = u;
  delete from public.jopml_c_wraps where user_id = u;
  delete from public.jopml_c_user_invites where invitee = u or invited_by = u;
  delete from public.jopml_c_users where user_id = u;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- Server, Kanäle, DMs
create or replace function public.jopml_c_spaces() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg();
begin
  return coalesce((
    select jsonb_agg(x order by x->>'name') from (
      select jsonb_build_object(
        'id', s.id, 'kind', s.kind, 'name', s.name, 'owner_id', s.owner_id, 'epoch', s.epoch,
        'needs_rotation', s.needs_rotation, 'role', m.role, 'status', m.status,
        'channels', case when m.status = 'active' then coalesce((
            select jsonb_agg(jsonb_build_object('id', c.id, 'name', c.name, 'position', c.position,
                                                'last_id', (select max(id) from public.jopml_c_messages where channel_id = c.id))
                             order by c.position, c.name)
              from public.jopml_c_channels c where c.space_id = s.id), '[]'::jsonb) else '[]'::jsonb end,
        'wraps', coalesce((select jsonb_agg(jsonb_build_object('epoch', w.epoch, 'wrapped', w.wrapped, 'wrapped_by', w.wrapped_by))
                             from public.jopml_c_wraps w where w.space_id = s.id and w.user_id = u), '[]'::jsonb),
        'pending', case when m.status = 'active' and m.role in ('owner', 'admin') then
                          (select count(*) from public.jopml_c_members p where p.space_id = s.id and p.status = 'pending') else 0 end,
        'peer', case when s.kind = 'dm' then (
                  select jsonb_build_object('user_id', cu.user_id, 'handle', cu.handle, 'display_name', cu.display_name,
                                            'enc_pub', cu.enc_pub, 'sign_pub', cu.sign_pub)
                    from public.jopml_c_members pm join public.jopml_c_users cu on cu.user_id = pm.user_id
                   where pm.space_id = s.id and pm.user_id <> u limit 1) end
      ) as x
      from public.jopml_c_spaces s join public.jopml_c_members m on m.space_id = s.id and m.user_id = u
    ) t), '[]'::jsonb);
end $$;

create or replace function public.jopml_c_create_server(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); n text := left(btrim(coalesce(p->>'name', '')), 40); sid uuid; cid uuid;
begin
  if char_length(n) < 2 then raise exception 'invalid_name'; end if;
  if public.jopml_c_check(n) is not null then raise exception 'name_not_allowed'; end if;
  if (select count(*) from public.jopml_c_spaces where owner_id = u and kind = 'server') >= 5 then raise exception 'limit_servers'; end if;
  insert into public.jopml_c_spaces (kind, name, owner_id) values ('server', n, u) returning id into sid;
  insert into public.jopml_c_members (space_id, user_id, role, status) values (sid, u, 'owner', 'active');
  insert into public.jopml_c_channels (space_id, name, position) values (sid, 'general', 0) returning id into cid;
  return jsonb_build_object('space_id', sid, 'channel_id', cid, 'epoch', 1);
end $$;

-- Gruppenschlüssel für Mitglieder hinterlegen (Owner/Admin). Aktiviert wartende Mitglieder.
create or replace function public.jopml_c_put_wraps(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; e integer := (p->>'epoch')::integer;
  s public.jopml_c_spaces; w jsonb; n integer := 0;
begin
  select * into s from public.jopml_c_spaces where id = sid;
  if not found or s.kind <> 'server' then raise exception 'not_found'; end if;
  if not public.jopml_c_is_mod(sid, u) then raise exception 'forbidden'; end if;
  if e is distinct from s.epoch then raise exception 'stale_epoch'; end if;
  if jsonb_typeof(p->'wraps') is distinct from 'array' or jsonb_array_length(p->'wraps') > 500 then raise exception 'invalid_payload'; end if;
  for w in select * from jsonb_array_elements(p->'wraps') loop
    if not exists (select 1 from public.jopml_c_members where space_id = sid and user_id = (w->>'user_id')::uuid) then continue; end if;
    insert into public.jopml_c_wraps (space_id, epoch, user_id, wrapped, wrapped_by)
    values (sid, e, (w->>'user_id')::uuid, w->>'wrapped', u)
    on conflict (space_id, epoch, user_id) do update set wrapped = excluded.wrapped, wrapped_by = excluded.wrapped_by;
    update public.jopml_c_members set status = 'active' where space_id = sid and user_id = (w->>'user_id')::uuid and status = 'pending';
    n := n + 1;
  end loop;
  return jsonb_build_object('wrapped', n);
end $$;

create or replace function public.jopml_c_open_dm(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); peer public.jopml_c_users; sid uuid; cid uuid;
begin
  select * into peer from public.jopml_c_users where handle = lower(btrim(coalesce(p->>'handle', '')));
  if not found then raise exception 'user_not_found'; end if;
  if peer.user_id = u then raise exception 'invalid_target'; end if;
  select s.id into sid from public.jopml_c_spaces s
   where s.kind = 'dm'
     and exists (select 1 from public.jopml_c_members where space_id = s.id and user_id = u)
     and exists (select 1 from public.jopml_c_members where space_id = s.id and user_id = peer.user_id)
   limit 1;
  if found then
    return jsonb_build_object('space_id', sid, 'channel_id', (select id from public.jopml_c_channels where space_id = sid limit 1), 'existing', true);
  end if;
  if char_length(coalesce(p->'wraps'->>'me', '')) = 0 or char_length(coalesce(p->'wraps'->>'peer', '')) = 0 then raise exception 'invalid_payload'; end if;
  if (select count(*) from public.jopml_c_members m join public.jopml_c_spaces s on s.id = m.space_id
       where m.user_id = u and s.kind = 'dm') >= 200 then raise exception 'limit_dms'; end if;
  insert into public.jopml_c_spaces (id, kind, name, owner_id) values (coalesce(nullif(p->>'space_id', '')::uuid, gen_random_uuid()), 'dm', '', null) returning id into sid;   -- die ID bindet den Schlüssel-Wrap, darum wählt sie der Client
  insert into public.jopml_c_members (space_id, user_id, role, status) values (sid, u, 'member', 'active'), (sid, peer.user_id, 'member', 'active');
  insert into public.jopml_c_channels (space_id, name) values (sid, 'dm') returning id into cid;
  insert into public.jopml_c_wraps (space_id, epoch, user_id, wrapped, wrapped_by)
  values (sid, 1, u, p->'wraps'->>'me', u), (sid, 1, peer.user_id, p->'wraps'->>'peer', u);
  return jsonb_build_object('space_id', sid, 'channel_id', cid, 'existing', false);
end $$;

create or replace function public.jopml_c_create_channel(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; n text := lower(btrim(coalesce(p->>'name', ''))); cid uuid;
begin
  if not exists (select 1 from public.jopml_c_spaces where id = sid and kind = 'server') or not public.jopml_c_is_mod(sid, u) then raise exception 'forbidden'; end if;
  if n !~ '^[a-z0-9_-]{1,32}$' then raise exception 'invalid_name'; end if;
  if public.jopml_c_check(n) is not null then raise exception 'name_not_allowed'; end if;
  if (select count(*) from public.jopml_c_channels where space_id = sid) >= 25 then raise exception 'limit_channels'; end if;
  if exists (select 1 from public.jopml_c_channels where space_id = sid and name = n) then raise exception 'name_taken'; end if;
  insert into public.jopml_c_channels (space_id, name, position)
  values (sid, n, coalesce((select max(position) + 1 from public.jopml_c_channels where space_id = sid), 0)) returning id into cid;
  return jsonb_build_object('channel_id', cid);
end $$;

create or replace function public.jopml_c_delete_channel(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); cid uuid := (p->>'channel_id')::uuid; sid uuid;
begin
  select c.space_id into sid from public.jopml_c_channels c join public.jopml_c_spaces s on s.id = c.space_id and s.kind = 'server' where c.id = cid;
  if sid is null or not public.jopml_c_is_mod(sid, u) then raise exception 'forbidden'; end if;
  if (select count(*) from public.jopml_c_channels where space_id = sid) <= 1 then raise exception 'last_channel'; end if;
  delete from public.jopml_c_channels where id = cid;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_c_delete_space(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; s public.jopml_c_spaces;
begin
  select * into s from public.jopml_c_spaces where id = sid;
  if not found then raise exception 'not_found'; end if;
  if s.kind = 'server' and public.jopml_c_role(sid, u) is distinct from 'owner' then raise exception 'forbidden'; end if;
  if s.kind = 'dm' and public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  delete from public.jopml_c_spaces where id = sid;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- Einladungen (Code und Benutzername)
create or replace function public.jopml_c_create_invite(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid;
  hrs integer := least(168, greatest(1, coalesce((p->>'hours')::integer, 24)));
  mx integer := least(100, greatest(1, coalesce((p->>'max_uses')::integer, 10)));
  raw text; code text; exp timestamptz;
begin
  if not exists (select 1 from public.jopml_c_spaces where id = sid and kind = 'server') or public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  if (select count(*) from public.jopml_c_invites where space_id = sid and expires_at > now()) >= 20 then raise exception 'limit_invites'; end if;
  raw := upper(encode(extensions.gen_random_bytes(8), 'hex'));
  code := 'JOPML-' || substr(raw, 1, 4) || '-' || substr(raw, 5, 4) || '-' || substr(raw, 9, 4) || '-' || substr(raw, 13, 4);
  exp := now() + make_interval(hours => hrs);
  insert into public.jopml_c_invites (code, space_id, created_by, expires_at, max_uses) values (code, sid, u, exp, mx);
  return jsonb_build_object('code', code, 'expires_at', exp, 'max_uses', mx);
end $$;

create or replace function public.jopml_c_join(u uuid, sid uuid) returns void     -- intern: als wartendes Mitglied eintragen
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from public.jopml_c_bans where space_id = sid and user_id = u) then raise exception 'banned'; end if;
  if (select count(*) from public.jopml_c_members where space_id = sid) >= 200 then raise exception 'limit_members'; end if;
  if (select count(*) from public.jopml_c_members where user_id = u) >= 100 then raise exception 'limit_memberships'; end if;
  insert into public.jopml_c_members (space_id, user_id, role, status) values (sid, u, 'member', 'pending') on conflict do nothing;
end $$;
revoke all on function public.jopml_c_join(uuid, uuid) from public, anon, authenticated;

create or replace function public.jopml_c_redeem_invite(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); c text := upper(regexp_replace(coalesce(p->>'code', ''), '\s', '', 'g')); inv public.jopml_c_invites; s public.jopml_c_spaces;
begin
  select * into inv from public.jopml_c_invites where code = c for update;
  if not found or inv.expires_at < now() or inv.uses >= inv.max_uses then raise exception 'invite_invalid'; end if;
  select * into s from public.jopml_c_spaces where id = inv.space_id;
  if exists (select 1 from public.jopml_c_members where space_id = s.id and user_id = u) then
    return jsonb_build_object('space_id', s.id, 'name', s.name, 'already', true);
  end if;
  perform public.jopml_c_join(u, s.id);
  update public.jopml_c_invites set uses = uses + 1 where code = c;
  return jsonb_build_object('space_id', s.id, 'name', s.name, 'already', false);
end $$;

create or replace function public.jopml_c_invite_user(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; t public.jopml_c_users;
begin
  if not exists (select 1 from public.jopml_c_spaces where id = sid and kind = 'server') or public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  select * into t from public.jopml_c_users where handle = lower(btrim(coalesce(p->>'handle', '')));
  if not found then raise exception 'user_not_found'; end if;
  if exists (select 1 from public.jopml_c_members where space_id = sid and user_id = t.user_id) then raise exception 'already_member'; end if;
  if exists (select 1 from public.jopml_c_bans where space_id = sid and user_id = t.user_id) then raise exception 'banned'; end if;
  if (select count(*) from public.jopml_c_user_invites where invitee = t.user_id) >= 30 then raise exception 'limit_invites'; end if;
  insert into public.jopml_c_user_invites (space_id, invitee, invited_by) values (sid, t.user_id, u) on conflict do nothing;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_c_my_invites() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg();
begin
  return coalesce((select jsonb_agg(jsonb_build_object('space_id', i.space_id, 'space_name', s.name, 'from', cu.handle, 'created_at', i.created_at) order by i.created_at desc)
                     from public.jopml_c_user_invites i join public.jopml_c_spaces s on s.id = i.space_id
                     left join public.jopml_c_users cu on cu.user_id = i.invited_by where i.invitee = u), '[]'::jsonb);
end $$;

create or replace function public.jopml_c_answer_invite(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid;
begin
  if not exists (select 1 from public.jopml_c_user_invites where space_id = sid and invitee = u) then raise exception 'invite_invalid'; end if;
  delete from public.jopml_c_user_invites where space_id = sid and invitee = u;
  if coalesce((p->>'accept')::boolean, false) then perform public.jopml_c_join(u, sid); end if;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- Mitglieder & Moderation
create or replace function public.jopml_c_members(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid;
begin
  if public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('user_id', cu.user_id, 'handle', cu.handle, 'display_name', cu.display_name,
                       'role', m.role, 'status', m.status, 'enc_pub', cu.enc_pub, 'sign_pub', cu.sign_pub) order by m.role, cu.handle)
                     from public.jopml_c_members m join public.jopml_c_users cu on cu.user_id = m.user_id where m.space_id = sid), '[]'::jsonb);
end $$;

create or replace function public.jopml_c_set_role(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; t uuid := (p->>'user_id')::uuid; r text := p->>'role';
begin
  if public.jopml_c_role(sid, u) is distinct from 'owner' or r not in ('admin', 'member') then raise exception 'forbidden'; end if;
  update public.jopml_c_members set role = r where space_id = sid and user_id = t and role <> 'owner';
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_c_kick(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; t uuid := (p->>'user_id')::uuid; tr text; mr text;
begin
  mr := public.jopml_c_role(sid, u);
  select role into tr from public.jopml_c_members where space_id = sid and user_id = t;
  if mr is null or tr is null or t = u or tr = 'owner' or mr = 'member' or (mr = 'admin' and tr = 'admin') then raise exception 'forbidden'; end if;
  if not exists (select 1 from public.jopml_c_spaces where id = sid and kind = 'server') then raise exception 'forbidden'; end if;
  delete from public.jopml_c_members where space_id = sid and user_id = t;
  delete from public.jopml_c_wraps where space_id = sid and user_id = t;
  if coalesce((p->>'ban')::boolean, false) then insert into public.jopml_c_bans (space_id, user_id) values (sid, t) on conflict do nothing; end if;
  update public.jopml_c_spaces set needs_rotation = true where id = sid;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_c_leave(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; s public.jopml_c_spaces;
begin
  select * into s from public.jopml_c_spaces where id = sid;
  if not found or not exists (select 1 from public.jopml_c_members where space_id = sid and user_id = u) then raise exception 'not_found'; end if;
  if s.kind = 'dm' then raise exception 'use_delete'; end if;
  if s.owner_id = u then raise exception 'owner_cannot_leave'; end if;
  delete from public.jopml_c_members where space_id = sid and user_id = u;
  delete from public.jopml_c_wraps where space_id = sid and user_id = u;
  update public.jopml_c_spaces set needs_rotation = true where id = sid;
  return jsonb_build_object('ok', true);
end $$;

-- Neuer Gruppenschlüssel nach Austritt/Rauswurf: muss für ALLE aktiven Mitglieder Wraps enthalten.
create or replace function public.jopml_c_rotate(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; s public.jopml_c_spaces; w jsonb; ids uuid[] := '{}'; need uuid[];
begin
  select * into s from public.jopml_c_spaces where id = sid for update;
  if not found or s.kind <> 'server' or not public.jopml_c_is_mod(sid, u) then raise exception 'forbidden'; end if;
  if (p->>'epoch')::integer is distinct from s.epoch + 1 then raise exception 'stale_epoch'; end if;
  if jsonb_typeof(p->'wraps') is distinct from 'array' or jsonb_array_length(p->'wraps') > 500 then raise exception 'invalid_payload'; end if;
  for w in select * from jsonb_array_elements(p->'wraps') loop ids := ids || (w->>'user_id')::uuid; end loop;
  select array_agg(user_id) into need from public.jopml_c_members where space_id = sid and status = 'active';
  if not (need <@ ids) then raise exception 'wraps_incomplete'; end if;
  for w in select * from jsonb_array_elements(p->'wraps') loop
    if exists (select 1 from public.jopml_c_members where space_id = sid and user_id = (w->>'user_id')::uuid and status = 'active') then
      insert into public.jopml_c_wraps (space_id, epoch, user_id, wrapped, wrapped_by)
      values (sid, s.epoch + 1, (w->>'user_id')::uuid, w->>'wrapped', u);
    end if;
  end loop;
  update public.jopml_c_spaces set epoch = s.epoch + 1, needs_rotation = false where id = sid;
  return jsonb_build_object('epoch', s.epoch + 1);
end $$;

-- ---------------------------------------------------------------- Nachrichten (nur Chiffretext)
create or replace function public.jopml_c_send(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); cid uuid := (p->>'channel_id')::uuid; s public.jopml_c_spaces; mid bigint; ts timestamptz;
begin
  select sp.* into s from public.jopml_c_spaces sp join public.jopml_c_channels c on c.space_id = sp.id where c.id = cid;
  if not found or public.jopml_c_role(s.id, u) is null then raise exception 'forbidden'; end if;
  if (p->>'epoch')::integer is distinct from s.epoch then raise exception 'stale_epoch'; end if;
  if not exists (select 1 from public.jopml_c_wraps where space_id = s.id and epoch = s.epoch and user_id = u) then raise exception 'no_key'; end if;
  if (select count(*) from public.jopml_c_messages where sender_id = u and created_at > now() - interval '10 seconds') >= 10 then raise exception 'rate_limited'; end if;
  if coalesce(p->>'body', '') = '' or coalesce(p->>'sig', '') = '' then raise exception 'invalid_payload'; end if;
  insert into public.jopml_c_messages (channel_id, space_id, sender_id, epoch, body, sig)
  values (cid, s.id, u, s.epoch, p->>'body', p->>'sig') returning id, created_at into mid, ts;
  return jsonb_build_object('id', mid, 'created_at', ts);
end $$;

create or replace function public.jopml_c_fetch(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  u uuid := public.jopml_c_reg(); cid uuid := (p->>'channel_id')::uuid; sid uuid;
  lim integer := least(200, greatest(1, coalesce((p->>'limit')::integer, 50)));
  aft bigint := (p->>'after')::bigint; bef bigint := (p->>'before')::bigint;
begin
  select space_id into sid from public.jopml_c_channels where id = cid;
  if sid is null or public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object('id', q.id, 'sender_id', q.sender_id, 'handle', q.handle, 'display_name', q.display_name,
                                        'epoch', q.epoch, 'body', q.body, 'sig', q.sig, 'created_at', q.created_at) order by q.id)
      from (
        select m.id, m.sender_id, cu.handle, cu.display_name, m.epoch, m.body, m.sig, m.created_at
          from public.jopml_c_messages m left join public.jopml_c_users cu on cu.user_id = m.sender_id
         where m.channel_id = cid and (aft is null or m.id > aft) and (bef is null or m.id < bef)
         order by case when aft is null then m.id end desc, case when aft is not null then m.id end asc
         limit lim
      ) q), '[]'::jsonb);
end $$;

create or replace function public.jopml_c_delete_message(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); m public.jopml_c_messages;
begin
  select * into m from public.jopml_c_messages where id = (p->>'message_id')::bigint;
  if not found then raise exception 'not_found'; end if;
  if m.sender_id <> u and not public.jopml_c_is_mod(m.space_id, u) then raise exception 'forbidden'; end if;
  delete from public.jopml_c_messages where id = m.id;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- Melden & Admin
create or replace function public.jopml_c_report(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := nullif(p->>'space_id', '')::uuid; rep uuid; k text := p->>'kind';
begin
  if k not in ('message', 'thread', 'post', 'server', 'user') then raise exception 'invalid_payload'; end if;
  if sid is not null and public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  if (select count(*) from public.jopml_c_reports where reporter = u and created_at > now() - interval '1 day') >= 20 then raise exception 'rate_limited'; end if;
  select user_id into rep from public.jopml_c_users where handle = lower(btrim(coalesce(p->>'handle', '')));
  insert into public.jopml_c_reports (reporter, kind, space_id, ref_id, reported_user, reason, evidence, evidence_sig)
  values (u, k, sid, left(p->>'ref_id', 64), rep, left(coalesce(p->>'reason', ''), 500), left(p->>'evidence', 10000), left(p->>'sig', 200));
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_c_admin_reports() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id', r.id, 'kind', r.kind, 'space_id', r.space_id, 'ref_id', r.ref_id,
            'reporter', rc.handle, 'reported', uc.handle, 'reported_id', r.reported_user, 'reason', r.reason, 'evidence', r.evidence,
            'created_at', r.created_at) order by r.id desc)
          from public.jopml_c_reports r left join public.jopml_c_users rc on rc.user_id = r.reporter
          left join public.jopml_c_users uc on uc.user_id = r.reported_user where r.status = 'open'), '[]'::jsonb);
end $$;

-- action: dismiss | delete_server | suspend_user | delete_thread | delete_post
create or replace function public.jopml_c_admin_resolve(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.jopml_c_reports; a text := p->>'action';
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  select * into r from public.jopml_c_reports where id = (p->>'id')::bigint;
  if not found then raise exception 'not_found'; end if;
  if a = 'delete_server' and r.space_id is not null then delete from public.jopml_c_spaces where id = r.space_id and kind = 'server';
  elsif a = 'suspend_user' and r.reported_user is not null then
    insert into public.jopml_c_suspended (user_id, reason) values (r.reported_user, left(r.reason, 200)) on conflict do nothing;
  elsif a = 'delete_thread' and r.kind = 'thread' then delete from public.jopml_f_threads where id = r.ref_id::bigint;
  elsif a = 'delete_post' and r.kind = 'post' then delete from public.jopml_f_posts where id = r.ref_id::bigint;
  elsif a <> 'dismiss' then raise exception 'invalid_payload';
  end if;
  update public.jopml_c_reports set status = 'done' where id = r.id;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- Forum
create or replace function public.jopml_f_boards() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform public.jopml_c_uid();
  return coalesce((select jsonb_agg(jsonb_build_object('id', b.id, 'threads', (select count(*) from public.jopml_f_threads t where t.board = b.id)) order by b.sort)
                     from public.jopml_f_boards b), '[]'::jsonb);
end $$;

create or replace function public.jopml_f_threads(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare off integer := greatest(0, coalesce((p->>'offset')::integer, 0));
begin
  perform public.jopml_c_uid();
  return coalesce((select jsonb_agg(jsonb_build_object('id', q.id, 'title', q.title, 'author', q.handle, 'author_name', q.display_name,
            'replies', q.replies, 'locked', q.locked, 'pinned', q.pinned, 'created_at', q.created_at, 'last_at', q.last_at) order by q.pinned desc, q.last_at desc)
     from (select t.*, cu.handle, cu.display_name from public.jopml_f_threads t left join public.jopml_c_users cu on cu.user_id = t.author_id
            where t.board = p->>'board' order by t.pinned desc, t.last_at desc limit 30 offset off) q), '[]'::jsonb);
end $$;

create or replace function public.jopml_f_thread(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare t public.jopml_f_threads; tid bigint := (p->>'id')::bigint; me uuid := public.jopml_c_uid(); adm boolean := public.jopml_is_admin();
begin
  select * into t from public.jopml_f_threads where id = tid;
  if not found then raise exception 'not_found'; end if;
  return jsonb_build_object(
    'thread', (select jsonb_build_object('id', t.id, 'board', t.board, 'title', t.title, 'body', t.body, 'author', cu.handle, 'author_name', cu.display_name,
                       'mine', t.author_id = me, 'locked', t.locked, 'pinned', t.pinned, 'created_at', t.created_at)
                 from (select 1) x left join public.jopml_c_users cu on cu.user_id = t.author_id),
    'posts', coalesce((select jsonb_agg(jsonb_build_object('id', po.id, 'body', po.body, 'author', cu.handle, 'author_name', cu.display_name,
                       'mine', po.author_id = me, 'created_at', po.created_at) order by po.id)
                 from (select * from public.jopml_f_posts where thread_id = tid order by id limit 300) po
                 left join public.jopml_c_users cu on cu.user_id = po.author_id), '[]'::jsonb),
    'can_moderate', adm);
end $$;

create or replace function public.jopml_f_new_thread(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); ti text := left(btrim(coalesce(p->>'title', '')), 120); bo text := left(btrim(coalesce(p->>'body', '')), 8000); tid bigint;
begin
  if char_length(ti) < 3 or char_length(bo) < 1 then raise exception 'invalid_payload'; end if;
  if not exists (select 1 from public.jopml_f_boards where id = p->>'board') then raise exception 'not_found'; end if;
  if public.jopml_c_check(ti) is not null or public.jopml_c_check(bo) is not null then raise exception 'filtered'; end if;
  if (select count(*) from public.jopml_f_threads where author_id = u and created_at > now() - interval '10 minutes')
   + (select count(*) from public.jopml_f_posts where author_id = u and created_at > now() - interval '1 minute') >= 6 then raise exception 'rate_limited'; end if;
  insert into public.jopml_f_threads (board, author_id, title, body) values (p->>'board', u, ti, bo) returning id into tid;
  return jsonb_build_object('id', tid);
end $$;

create or replace function public.jopml_f_reply(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); t public.jopml_f_threads; bo text := left(btrim(coalesce(p->>'body', '')), 8000); pid bigint;
begin
  select * into t from public.jopml_f_threads where id = (p->>'thread_id')::bigint for update;
  if not found then raise exception 'not_found'; end if;
  if t.locked then raise exception 'thread_locked'; end if;
  if char_length(bo) < 1 then raise exception 'invalid_payload'; end if;
  if public.jopml_c_check(bo) is not null then raise exception 'filtered'; end if;
  if (select count(*) from public.jopml_f_posts where author_id = u and created_at > now() - interval '1 minute') >= 6 then raise exception 'rate_limited'; end if;
  insert into public.jopml_f_posts (thread_id, author_id, body) values (t.id, u, bo) returning id into pid;
  update public.jopml_f_threads set replies = replies + 1, last_at = now() where id = t.id;
  return jsonb_build_object('id', pid);
end $$;

create or replace function public.jopml_f_delete(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); rid bigint := (p->>'id')::bigint; adm boolean := public.jopml_is_admin(); tid bigint;
begin
  if p->>'kind' = 'thread' then
    delete from public.jopml_f_threads t where t.id = rid and (t.author_id = u or adm);
  elsif p->>'kind' = 'post' then
    delete from public.jopml_f_posts po where po.id = rid and (po.author_id = u or adm) returning po.thread_id into tid;
    if tid is not null then update public.jopml_f_threads set replies = greatest(0, replies - 1) where id = tid; end if;
  else raise exception 'invalid_payload';
  end if;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_f_set_flags(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  update public.jopml_f_threads set locked = coalesce((p->>'locked')::boolean, locked), pinned = coalesce((p->>'pinned')::boolean, pinned)
   where id = (p->>'id')::bigint;
  return jsonb_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- Rechte
do $$
declare f text;
begin
  foreach f in array array[
    'jopml_c_me()', 'jopml_c_reset()', 'jopml_c_setup(jsonb)', 'jopml_c_set_display(jsonb)', 'jopml_c_lookup(jsonb)', 'jopml_c_spaces()',
    'jopml_c_create_server(jsonb)', 'jopml_c_put_wraps(jsonb)', 'jopml_c_open_dm(jsonb)', 'jopml_c_create_channel(jsonb)',
    'jopml_c_delete_channel(jsonb)', 'jopml_c_delete_space(jsonb)', 'jopml_c_create_invite(jsonb)', 'jopml_c_redeem_invite(jsonb)',
    'jopml_c_invite_user(jsonb)', 'jopml_c_my_invites()', 'jopml_c_answer_invite(jsonb)', 'jopml_c_members(jsonb)',
    'jopml_c_set_role(jsonb)', 'jopml_c_kick(jsonb)', 'jopml_c_leave(jsonb)', 'jopml_c_rotate(jsonb)', 'jopml_c_send(jsonb)',
    'jopml_c_fetch(jsonb)', 'jopml_c_delete_message(jsonb)', 'jopml_c_report(jsonb)', 'jopml_c_admin_reports()',
    'jopml_c_admin_resolve(jsonb)', 'jopml_f_boards()', 'jopml_f_threads(jsonb)', 'jopml_f_thread(jsonb)',
    'jopml_f_new_thread(jsonb)', 'jopml_f_reply(jsonb)', 'jopml_f_delete(jsonb)', 'jopml_f_set_flags(jsonb)'] loop
    execute format('revoke all on function public.%s from public, anon', f);
    execute format('grant execute on function public.%s to authenticated', f);
  end loop;
end $$;
