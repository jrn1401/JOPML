-- JOPML v1.3 – Server-Filter für öffentliche Texte (Forum, Benutzer-/Server-/Kanalnamen).
-- GENERIERT von tools/gen_filter_sql.py aus core/chatfilter.py + core/chatfilter_words.py – nicht von Hand ändern.
-- Ende-zu-Ende-verschlüsselte Chats kann der Server NICHT filtern (er sieht nur Chiffretext); dort filtert der Client.

create table if not exists public.jopml_c_filter (id serial primary key, category text not null, kind text not null, pattern text not null);
create table if not exists public.jopml_c_allow (id serial primary key, pattern text not null);
alter table public.jopml_c_filter enable row level security;
alter table public.jopml_c_allow enable row level security;
revoke all on public.jopml_c_filter, public.jopml_c_allow from anon, authenticated, public;
truncate public.jopml_c_filter, public.jopml_c_allow;

create or replace function public.jopml_c_skel(t text, symbols boolean) returns text
language sql immutable set search_path = '' as $f$
  select regexp_replace(
    translate(translate(
      lower(regexp_replace(regexp_replace(normalize(replace(left(coalesce(t, ''), 6000), 'ß', 'ss'), NFKD),
        '[\x0300-\x036f\x200b-\x200f\x2028-\x202e\x2060-\x206f\xfeff\xad\x180e\x034f]', '', 'g'), '[\s]', ' ', 'g')),
      $q$*#•·×%^~$q$, repeat(chr(57344), 8)),
      $q$абвгдеёжзийклмнопрстуфхцчшщыэюяіїєґѕјһԁαβγεζηικμνοπρσςτυχωøđðłıæœþ01345789lvАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЫЭЮЯІЇЄҐЅЈҺԀΑΒΓΕΖΗΙΚΜΝΟΠΡΣΤΥΧΩØĐÐŁIÆŒÞLV$q$ || case when symbols then $q$@$!|+¡€£¢©§°¥µ$q$ else '' end || $q$ъь$q$,
      $q$abbgdeejziiklmhoppctyfxccwwieuaiiegsjhdabyeznikmuonpsstuxwoddliaopoieastbgiuabbgdeejziiklmhoppctyfxccwwieuaiiegsjhdabyeznikmuonpstuxwoddliaopiu$q$ || case when symbols then $q$asiitieeccsoyu$q$ else '' end),
    '(.)\1{3,}', '\1\1\1', 'g')
$f$;

-- Baut aus einer Buchstabenfolge (oder Wörtern mit Leerzeichen bei 'phrase') die Regex-Muster.
create or replace function public.jopml_c_mkpat(kind text, w text) returns text[]
language plpgsql immutable set search_path = '' as $f$
declare n int; i int; c text; units text[] := '{}'; words text[]; parts text[] := '{}'; wi text; res text[] := '{}'; isc boolean;
  sep constant text := $q$[^a-z\s㐀-䶿一-鿿]{0,2}$q$; sepc constant text := $q$[^a-z0-9㐀-䶿一-鿿]{0,2}$q$;
  sps constant text := $q$[^a-z]{1,2}$q$; spw constant text := $q$[^a-z㐀-䶿一-鿿]{1,3}$q$;
  bf constant text := $q$(?<![a-z])$q$; af constant text := $q$(?![a-z])$q$; wild constant text := chr(57344);
  cj constant text := $q$[㐀-䶿一-鿿]$q$;
begin
  if kind = 'phrase' then
    foreach wi in array string_to_array(w, ' ') loop
      units := '{}';
      for i in 1..char_length(wi) loop c := substr(wi, i, 1);
        units := units || (case when char_length(wi) >= 4 then '(?:' || c || '+|' || wild || ')' else c || '+' end);
      end loop;
      parts := parts || array_to_string(units, sep);
    end loop;
    return array[bf || array_to_string(parts, spw) || af];
  end if;
  n := char_length(w); isc := w ~ cj;
  for i in 1..n loop c := substr(w, i, 1);
    if c ~ cj then units := units || regexp_replace(c, '([\\.^$|?*+()\[\]{}-])', '\\\1', 'g');
    elsif n >= 4 then units := units || ('(?:' || c || '+|' || wild || ')');
    else units := units || (c || '+'); end if;
  end loop;
  if isc then return array[array_to_string(units, sepc)]; end if;
  res := array[case when kind = 'word' then bf || array_to_string(units, sep) || af else array_to_string(units, sep) end];
  if n >= 3 then res := res || (bf || array_to_string(regexp_split_to_array(w, ''), sps) || af); end if;
  return res;
end $f$;

insert into public.jopml_c_filter (category, kind, pattern)
select e.cat, e.kind, p from (values
($q$profanity$q$, $q$sub$q$, $q$fuck,shit,buiishit,cunt,bitch,wanker,motherfucker,asshoie,arschioch,wichser,scheisse,hurensohn,fotze,schiampe,missgeburt,giiipoiias,putain,connard,connasse,saiope,encuie,pizda,pizdec,ebat,mudak,pidoras,cyka,blat,blad,pizda,pizdec,ebat,mydak,pidopac,zalypa,dolboeb,haxyi,ybludok,傻逼,操你妈,草泥马,他妈的,妈的,婊子,王八蛋,鸡巴,狗杂种,mierda,cabron,pendejo,hijueputa,chingar,chinga,couiiies,branier,bougnouie$q$),
($q$profanity$q$, $q$word$q$, $q$ass,arse,bastard,bitches,cock,cocksucker,dick,dickhead,douche,douchebag,dumbass,jackass,piss,pissed,pissing,prick,twat,retard,retarded,retards,scumbag,shithead,fuk,fuc,phuck,fck,arsch,fick,ficken,ficker,hure,wixer,scheiss,scheisskeri,spast,spasti,drecksau,uerpiss,uoiiidiot,dreckskeri,miststueck,joder,puta,puto,putas,uerga,marica,maricon,zorra,cuiero,mamon,merde,encuier,pute,ntm,fdp,batard,saiaud,couiiie,branieur,foutre,cyki,xyi,xya,xye,ebal,ebah,eblo,mydila,pidop,gahdoh,wluxa,mpaz,poxyi,suka,biyat,biyad,pidor,nahui,naxui,nahuy,huy,xuy,hui,zaiupa,gandon,shiyuha,ubiyudok,doiboeb,傻比,操你媽,艹你妈,他媽的,你妈的,贱人,賤人,雞巴,滚蛋,傻屌,狗日的,妈逼,马勒戈壁,尼玛,你妈逼,操你,干你娘$q$),
($q$profanity$q$, $q$phrase$q$, $q$fuck you,fuck off,go to heii,hait die fresse,hait die kiappe,ta gueuie,nique ta mere,hijo de puta,uete a ia mierda,fiis de pute,idi haxyi,powel haxyi,idi ha xyi,zatkhi pact,caiiate ia boca$q$),
($q$sexual$q$, $q$sub$q$, $q$pussy,biowjob,handjob,cumshot,diido,bukkake,gangbang,creampie,deepthroat,nacktbiider,arschficker,spermaschiucker,sexskiaue,dpocit,mihet,做爱,约炮,裸照,口交,打飞机,操逼$q$),
($q$sexual$q$, $q$word$q$, $q$pussies,tits,titties,boobs,boobies,nude,nudes,porn,porno,horny,sext,sexting,siut,siuts,whore,whores,miif,jerkoff,cum,fap,fapping,titten,muschi,nutte,pimmei,nacktfoto,wichsen,fickbar,tetas,foiiar,foiiame,cuio,pajero,nichons,sucemoi,cicki,otcoc,otcoci,siski,drochit,otsos,minet,trahat,約炮,骚货,性奴$q$),
($q$sexual$q$, $q$phrase$q$, $q$send nudes,send me nudes,show me your tits,show me your boobs,suck my dick,suck my cock,eat my pussy,wanna fuck,want to fuck,iets fuck,iets fuck,fuck me,schick nudes,zeig mir deine titten,iutsch meinen,bias mir einen,ich wiii dich ficken$q$),
($q$hate$q$, $q$sub$q$, $q$nigger,nigga,faggot,judensau,judenschwein,schwuchtei,kameitreiber,untermensch,hoiohoax,kanaken,higgep,cephomazii,黑鬼,支那,kummeiturke,kuemmeituerke$q$),
($q$hate$q$, $q$word$q$, $q$niggers,niggas,faggots,fag,fags,tranny,trannies,kike,kikes,spic,spics,chink,chinks,gook,gooks,wetback,wetbacks,paki,pakis,toweihead,beaner,raghead,shemaie,zipperhead,jewboy,neger,kanake,zigeuner,untermenschen,itaker,poiacke,sudaca,negrata,bougnouie,youpin,bicot,jid,jidi,xoxol,kacap,cypka,higep,hegp,zhid,khokhoi,katsap,churka,死基佬,棒子,小日本,尼哥,kkk,siegheii,heiihitier,whitepower,杀光犹太人,杀光黑人$q$),
($q$hate$q$, $q$phrase$q$, $q$gas the jews,jews to the gas,kiii aii jews,kiii aii musiims,kiii aii biacks,kiii aii gays,kiii aii niggers,kiii aii whites,kiii aii arabs,kiii aii christians,death to jews,death to aii jews,death to musiims,death to gays,hang the niggers,adoif hitier was right,hitier did nothing wrong,ausiander raus,ausiaender raus,juden raus,totet aiie juden,toetet aiie juden,totet aiie musiime,sieg heii,heii hitier,white power,gas them aii,cmept ebpeam,cmept jidam,bei jidob$q$),
($q$threat$q$, $q$word$q$, $q$kys,dox,doxx,doxxing,matate,suicidate,杀了你,去死,自杀吧,我知道你住哪$q$),
($q$threat$q$, $q$phrase$q$, $q$kiii yourseif,go kiii yourseif,i wiii kiii you,iii kiii you,iii kiii you,i wiii find you,i know where you iiue,hang yourseif,neck yourseif,go die,drink bieach,you shouid die,die in a fire,bring dich um,erschiess dich,erschiess dich,geh sterben,ich bring dich um,ich tote dich,ich toete dich,ich weiss wo du wohnst,ich weiss wo du wohnst,te uoy a matar,je uais te tuer,ua te pendre,tue toi,ybei ceba,a teba ybu,a zhau gde ti jibew$q$)
) as e(cat, kind, ws), lateral unnest(string_to_array(e.ws, ',')) as w, lateral unnest(public.jopml_c_mkpat(e.kind, w)) as p;
insert into public.jopml_c_allow (pattern) values
($q$~Bs+c+u+n+t+h+o+r+p+e+[a-z]{0,4}~A$q$),
($q$~Bs+h+i+i+t+a+k+e+[a-z]{0,4}~A$q$),
($q$~Bs+h+i+t+a+k+e+[a-z]{0,4}~A$q$),
($q$~Bs+n+i+g+g+e+r+[a-z]{0,4}~A$q$),
($q$~Bn+i+g+g+a+r+d+[a-z]{0,4}~A$q$),
($q$~Bc+u+m+[^a-z㐀-䶿一-鿿]{1,3}i+a+u+d+e+[a-z]{0,4}~A$q$),
($q$~Bp+u+s+s+y+c+a+t+[a-z]{0,4}~A$q$),
($q$~Bp+u+s+s+y+[^a-z㐀-䶿一-鿿]{1,3}w+i+i+i+o+w+[a-z]{0,4}~A$q$);
update public.jopml_c_filter set pattern = regexp_replace(replace(replace(replace(replace(pattern, '~S', $q$[^a-z\s㐀-䶿一-鿿]{0,2}$q$), '~T', '[^a-z]{1,2}'), '~B', '(?<![a-z])'), '~A', '(?![a-z])'), '~([a-z])', '(?:\1+|)', 'g');
update public.jopml_c_allow set pattern = regexp_replace(replace(replace(replace(replace(pattern, '~S', $q$[^a-z\s㐀-䶿一-鿿]{0,2}$q$), '~T', '[^a-z]{1,2}'), '~B', '(?<![a-z])'), '~A', '(?![a-z])'), '~([a-z])', '(?:\1+|)', 'g');

-- Liefert die Kategorie des ersten Treffers oder NULL, wenn der Text sauber ist.
create or replace function public.jopml_c_check(t text) returns text
language plpgsql stable security definer set search_path = '' as $f$
declare v text; cat text; a record; sym boolean;
begin
  if t is null or t = '' then return null; end if;
  foreach sym in array array[true, false] loop
    v := public.jopml_c_skel(t, sym);
    for a in select pattern from public.jopml_c_allow loop v := regexp_replace(v, a.pattern, ' ', 'g'); end loop;
    select f.category into cat from public.jopml_c_filter f where v ~ f.pattern limit 1;
    if cat is not null then return cat; end if;
  end loop;
  return null;
end $f$;

create or replace function public.jopml_c_assert_clean(t text) returns void
language plpgsql stable security definer set search_path = '' as $f$
declare cat text := public.jopml_c_check(t);
begin
  if cat is not null then raise exception 'filtered:%', cat; end if;
end $f$;

revoke all on function public.jopml_c_skel(text, boolean) from public, anon;
revoke all on function public.jopml_c_check(text) from public, anon;
revoke all on function public.jopml_c_assert_clean(text) from public, anon;
grant execute on function public.jopml_c_skel(text, boolean) to authenticated;
grant execute on function public.jopml_c_check(text) to authenticated;
grant execute on function public.jopml_c_assert_clean(text) to authenticated;
