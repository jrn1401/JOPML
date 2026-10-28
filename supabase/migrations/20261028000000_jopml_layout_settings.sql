-- v1.3: Layout-Einstellungen (Reihenfolge/Sichtbarkeit der Module) dürfen mit dem Profil synchronisiert werden.
-- Teilweise aktualisieren: p darf display_name, email (leer = löschen) und settings (wird zusammengeführt) enthalten.
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
    cur := jsonb_set(cur, '{display_name}', to_jsonb(left(btrim(p->>'display_name'), 40)));
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
