-- 1.10.0: Release-Notes je Version in den Ankündigungen (beim Upload automatisch; ein Eintrag je Version, erneutes Hochladen aktualisiert ihn).
alter table public.jopml_news add column if not exists version text;
create unique index if not exists jopml_news_version_uq on public.jopml_news (version) where version is not null;

create or replace function public.jopml_news_list() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'not_authenticated'; end if;
  return coalesce((select jsonb_agg(to_jsonb(x)) from (select id, title, body, created_at, version from public.jopml_news order by id desc limit 60) x), '[]'::jsonb);
end $$;

create or replace function public.jopml_admin_release_note(p jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare v text := btrim(coalesce(p->>'version', '')); t text := btrim(coalesce(p->>'title', '')); b text := btrim(coalesce(p->>'body', '')); nid bigint;
begin
  if auth.uid() is null or not public.jopml_is_admin() then raise exception 'forbidden'; end if;
  if v !~ '^\d{1,3}\.\d{1,3}\.\d{1,3}$' or length(t) < 3 or length(t) > 100 or length(b) > 6000 then raise exception 'invalid_payload'; end if;
  insert into public.jopml_news (title, body, version) values (t, b, v)
    on conflict (version) where version is not null do update set title = excluded.title, body = excluded.body
    returning id into nid;
  insert into public.jopml_admin_audit (admin_id, action, detail) values (auth.uid(), 'release_note', v);
  return jsonb_build_object('id', nid);
end $$;
revoke execute on function public.jopml_admin_release_note(jsonb) from public, anon;
grant execute on function public.jopml_admin_release_note(jsonb) to authenticated;
