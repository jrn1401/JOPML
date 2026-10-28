-- JOPML 1.3.3: Moderation – Stummschalten und Langsam-Modus (Slowmode)
alter table public.jopml_c_spaces  add column if not exists slowmode integer not null default 0 check (slowmode between 0 and 3600);
alter table public.jopml_c_members add column if not exists muted_until timestamptz;

create or replace function public.jopml_c_set_slowmode(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; secs integer := (p->>'seconds')::integer;
begin
  if not public.jopml_c_is_mod(sid, u) or secs is null or secs < 0 or secs > 3600 then raise exception 'forbidden'; end if;
  if not exists (select 1 from public.jopml_c_spaces where id = sid and kind = 'server') then raise exception 'forbidden'; end if;
  update public.jopml_c_spaces set slowmode = secs where id = sid;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.jopml_c_mute(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid; t uuid := (p->>'user_id')::uuid;
        mins integer := (p->>'minutes')::integer; mr text; tr text;
begin
  mr := public.jopml_c_role(sid, u);
  select role into tr from public.jopml_c_members where space_id = sid and user_id = t;
  if mr is null or tr is null or t = u or tr = 'owner' or mr = 'member' or (mr = 'admin' and tr = 'admin') or mins is null or mins < 0 or mins > 43200 then
    raise exception 'forbidden';
  end if;
  if not exists (select 1 from public.jopml_c_spaces where id = sid and kind = 'server') then raise exception 'forbidden'; end if;
  update public.jopml_c_members set muted_until = case when mins = 0 then null else now() + make_interval(mins => mins) end
   where space_id = sid and user_id = t;
  return jsonb_build_object('ok', true);
end $$;

-- Liste der Server: zusätzlich slowmode und die eigene Stummschaltung
create or replace function public.jopml_c_spaces() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg();
begin
  return coalesce((
    select jsonb_agg(x order by x->>'name') from (
      select jsonb_build_object(
        'id', s.id, 'kind', s.kind, 'name', s.name, 'owner_id', s.owner_id, 'epoch', s.epoch,
        'needs_rotation', s.needs_rotation, 'role', m.role, 'status', m.status,
        'slowmode', s.slowmode, 'muted_until', case when m.muted_until > now() then m.muted_until end,
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

-- Mitgliederliste: zusätzlich muted_until
create or replace function public.jopml_c_members(p jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); sid uuid := (p->>'space_id')::uuid;
begin
  if public.jopml_c_role(sid, u) is null then raise exception 'forbidden'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('user_id', cu.user_id, 'handle', cu.handle, 'display_name', cu.display_name,
                       'role', m.role, 'status', m.status, 'enc_pub', cu.enc_pub, 'sign_pub', cu.sign_pub,
                       'muted_until', case when m.muted_until > now() then m.muted_until end) order by m.role, cu.handle)
                     from public.jopml_c_members m join public.jopml_c_users cu on cu.user_id = m.user_id where m.space_id = sid), '[]'::jsonb);
end $$;

-- Senden: Stummschaltung und Slowmode prüfen (Admins/Owner sind vom Slowmode ausgenommen)
create or replace function public.jopml_c_send(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u uuid := public.jopml_c_reg(); cid uuid := (p->>'channel_id')::uuid; s public.jopml_c_spaces; mid bigint; ts timestamptz;
        mu timestamptz;
begin
  select sp.* into s from public.jopml_c_spaces sp join public.jopml_c_channels c on c.space_id = sp.id where c.id = cid;
  if not found or public.jopml_c_role(s.id, u) is null then raise exception 'forbidden'; end if;
  select muted_until into mu from public.jopml_c_members where space_id = s.id and user_id = u;
  if mu is not null and mu > now() then raise exception 'muted'; end if;
  if (p->>'epoch')::integer is distinct from s.epoch then raise exception 'stale_epoch'; end if;
  if not exists (select 1 from public.jopml_c_wraps where space_id = s.id and epoch = s.epoch and user_id = u) then raise exception 'no_key'; end if;
  if (select count(*) from public.jopml_c_messages where sender_id = u and created_at > now() - interval '10 seconds') >= 10 then raise exception 'rate_limited'; end if;
  if s.slowmode > 0 and not public.jopml_c_is_mod(s.id, u)
     and exists (select 1 from public.jopml_c_messages where sender_id = u and space_id = s.id
                    and created_at > now() - make_interval(secs => s.slowmode)) then
    raise exception 'slowmode';
  end if;
  if coalesce(p->>'body', '') = '' or coalesce(p->>'sig', '') = '' then raise exception 'invalid_payload'; end if;
  insert into public.jopml_c_messages (channel_id, space_id, sender_id, epoch, body, sig)
  values (cid, s.id, u, s.epoch, p->>'body', p->>'sig') returning id, created_at into mid, ts;
  return jsonb_build_object('id', mid, 'created_at', ts);
end $$;

revoke all on function public.jopml_c_set_slowmode(jsonb) from public, anon;
revoke all on function public.jopml_c_mute(jsonb) from public, anon;
grant execute on function public.jopml_c_set_slowmode(jsonb) to authenticated;
grant execute on function public.jopml_c_mute(jsonb) to authenticated;
