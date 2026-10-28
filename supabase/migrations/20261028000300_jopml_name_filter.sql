-- v1.3: Namensfilter für Benutzername und Anzeigename (serverseitig, zusätzlich zur Prüfung in der App).
create or replace function public.jopml_ensure_profile(p_username text default null, p_display_name text default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  k text := public.jopml_key();
  mail text; row public.jopml_profiles; uname text; disp text;
begin
  if uid is null then raise exception 'not_authenticated'; end if;
  if k is null then raise exception 'encryption key missing'; end if;
  select * into row from public.jopml_profiles where user_id = uid;
  if found then return public.jopml_decode(row); end if;

  select lower(email) into mail from auth.users where id = uid;
  uname := nullif(lower(btrim(coalesce(p_username, ''))), '');
  if uname is not null then
    if uname !~ '^[a-z0-9_.-]{3,24}$' then raise exception 'invalid_username'; end if;
    if split_part(split_part(coalesce(mail, ''), '@', 1), '+', 2) is distinct from uname then raise exception 'username_mismatch'; end if;
    if exists (select 1 from public.jopml_profiles where lower(username) = uname) then raise exception 'username_taken'; end if;
  end if;
  disp := left(coalesce(nullif(btrim(p_display_name), ''), uname,
               nullif(auth.jwt() -> 'user_metadata' ->> 'full_name', ''), 'User'), 40);

  -- v1.3: Namensfilter (Benutzername/Anzeigename) und Eindeutigkeit gegenüber Community-Namen
  if uname is not null then
    if public.jopml_c_check(uname) is not null then raise exception 'name_not_allowed'; end if;
    if exists (select 1 from public.jopml_c_users where handle = uname) then raise exception 'username_taken'; end if;
  end if;
  if nullif(btrim(p_display_name), '') is not null and public.jopml_c_check(disp) is not null then raise exception 'name_not_allowed'; end if;
  if public.jopml_c_check(disp) is not null then disp := 'User'; end if;      -- z. B. unpassender Name aus dem Google-Profil

  insert into public.jopml_profiles (user_id, username, data_enc)
  values (uid, uname, extensions.pgp_sym_encrypt(
            jsonb_build_object('display_name', disp, 'email', '', 'settings', '{}'::jsonb)::text, k))
  returning * into row;
  return public.jopml_decode(row);
end $$;
revoke all on function public.jopml_ensure_profile(text, text) from public, anon;
grant execute on function public.jopml_ensure_profile(text, text) to authenticated;

create or replace function public.jopml_save_profile(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  k text := public.jopml_key();
  row public.jopml_profiles; cur jsonb; setts jsonb; allowed text[] :=
    array['appearance_mode','accent','colors','language','dl_limit_kbps','cpu_priority','cpu_cores','ram_limit_mb','icon_bg','nav_order','nav_hidden','bg_dim','bg_height'];
  key text;
begin
  if uid is null then raise exception 'not_authenticated'; end if;
  if jsonb_typeof(p) is distinct from 'object' then raise exception 'invalid_payload'; end if;
  select * into row from public.jopml_profiles where user_id = uid for update;
  if not found then raise exception 'no_profile'; end if;
  cur := extensions.pgp_sym_decrypt(row.data_enc, k)::jsonb;

  if p ? 'display_name' then
    if jsonb_typeof(p->'display_name') <> 'string' then raise exception 'invalid_display_name'; end if;
    if public.jopml_c_check(left(btrim(p->>'display_name'), 40)) is not null then raise exception 'name_not_allowed'; end if;
    cur := jsonb_set(cur, '{display_name}', to_jsonb(left(btrim(p->>'display_name'), 40)));
    update public.jopml_c_users set display_name = left(btrim(p->>'display_name'), 40) where user_id = uid and btrim(p->>'display_name') <> '';
  end if;
  if p ? 'email' then
    if jsonb_typeof(p->'email') <> 'string' or length(p->>'email') > 254
       or (p->>'email' <> '' and p->>'email' !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$') then raise exception 'invalid_email'; end if;
    cur := jsonb_set(cur, '{email}', to_jsonb(p->>'email'));
  end if;
  if p ? 'settings' then
    if jsonb_typeof(p->'settings') <> 'object' or length((p->'settings')::text) > 8000 then raise exception 'invalid_settings'; end if;
    setts := coalesce(cur->'settings', '{}'::jsonb);
    for key in select jsonb_object_keys(p->'settings') loop
      if key = any (allowed) then setts := jsonb_set(setts, array[key], p->'settings'->key); end if;   -- unbekannte Schlüssel werden verworfen
    end loop;
    cur := jsonb_set(cur, '{settings}', setts);
  end if;

  update public.jopml_profiles set data_enc = extensions.pgp_sym_encrypt(cur::text, k), updated_at = now()
   where user_id = uid returning * into row;
  return public.jopml_decode(row);
end $$;

revoke all on function public.jopml_save_profile(jsonb) from public, anon;
grant execute on function public.jopml_save_profile(jsonb) to authenticated;
