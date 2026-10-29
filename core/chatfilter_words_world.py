"""Erweiterte Wortlisten für den Chat-Filter: Schimpfwörter, sexuelle Belästigung, Hass und Drohungen in vielen Sprachen.

Wird von chatfilter_words.py eingelesen und an die Grundlisten angehängt (gleiche Arten: W ganzes Wort, S auch als Wortteil,
PHRASES Wortgruppen). Schreibweise: normal und klein; Akzente, Leetspeak, Trennzeichen, Wiederholungen, Platzhalter und
Look-alikes erledigt der Filter (chatfilter.skeleton).

Regeln für Einträge
  * Nur Wörter, die als Beleidigung/Schimpfwort/Drohung gebraucht werden. Was in einer anderen Sprache ein harmloses Wort
    oder ein Vorname ist (englisch "hoe", "randi", "lund", französisch "chut", spanisch "cono", portugiesisch "pula" ...),
    steht absichtlich NICHT drin; der Filter prüft alle Sprachen gleichzeitig.
  * Schriften ohne Wortgrenzen (Arabisch, Hebräisch, Hindi, Bengalisch, Koreanisch, Japanisch) vergleichen Teilstrings, deshalb
    nur Einträge ab 3 Zeichen (nach dem Entfernen der Vokalzeichen), die nicht in häufigen Wörtern stecken.
  * Thailändisch ist nur lateinisch umschrieben dabei: das Entfernen der Tonzeichen würde sonst zu viele harmlose Wörter treffen.
Ehrlich: Keine Liste ist vollständig. Weitere Wörter hier eintragen und `python tools/gen_filter_sql.py` ausführen.
"""


def _w(text: str) -> list[str]:
    """Wörter, durch Leerzeichen getrennt."""
    return text.split()


def _p(text: str) -> list[str]:
    """Wortgruppen, durch | getrennt."""
    return [x.strip() for x in text.split("|") if x.strip()]


# ------------------------------------------------------------------------------------------------ Beleidigungen / Schimpfwörter
W = {
    "profanity": (
        # Englisch (Ergänzungen)
        _w("fucker fuckers fucking fuckin fuckwit fuckface fuckhead fuckboy fuckup motherfucking shitty shitting shitface shitbag "
           "bollocks  bellend knobhead knobend tosser dipshit dumbfuck dumbfucks cockhead cockface twatface arsehole arseholes "
           "goddamn goddamnit jackoff skank skanks   spaz spazz whoreson stfu gtfo cunts bitchass sonofabitch dickwad dickface "
           "prickface shitlord asswipe asshat assclown buttfucker fuckwad cumslut cumbucket jizz wankers pissflaps")
        # Deutsch
        + _w("kackbratze kackbrocken kackhure kackscheisse wixxer votze fotzen hurensoehne arschgeige pisser pissnelke drecksack "
             "schweinehund hundesohn mistkerl schwanzlutscher schwanzgesicht fickfresse fotzenlecker hurentochter wichsfresse "
             "scheissdreck ficksau fickdich arschgesicht affenarsch ekelhure mutterficker   ")
        # Spanisch / Portugiesisch
        + _w("carajo   mamahuevo malparido malparida  chupapollas cojones   pajillero cabrona cabrones "
             "putero huevon weon aweonao culiao culiado ctm  conchatumadre conchetumare conchesumadre chingada chingado "
             "mamaguevo cagon pendejos pendeja puñeta puneta soplapollas tontopolla hijodeputa")
        + _w("caralho porra foda fodase fodido foder fodeu buceta boceta xoxota xereca piroca punheta putaria vadia vagabunda viado "
             "viadinho arrombado cuzao babaca otario bosta    merdinha")
        # Italienisch
        + _w("cazzo cazzi minchia stronzo stronza stronzi stronze vaffanculo fanculo puttana puttane troia troie coglione coglioni "
             "mignotta zoccola pompino pompinara sborra sborrata  culattone frocio froci ricchione bastardo bastardi fottiti "
             "porcodio porcamadonna rompicoglioni leccaculo succhiacazzi testadicazzo")
        # Französisch
        + _w("enculé enfoiré enfoire petasse pétasse  nique niquer niquetamere tapette tantouze pouffiasse salopard salopards "
             "connards conasse trouduc trouduc  sacdemerde batards putes")
        # Niederländisch
        + _w("kut  kankerhoer kankerlijer kankerzooi  teringlijer  tyfuslijer klootzak klootzakken  lul hoer "
             "hoerenzoon hoerenkind   kutwijf kutkind godverdomme godver rotzak  hoeren kutzak lulhannes")
        # Skandinavisch / Finnisch
        + _w("jävla jävel javla jävlar fitta fittan kuk knulla knullare   fitte pikk hore luder røvhul rovhul pikfjæs "
             "vittu vittuun vitun perkele saatana paska kusipää kusipaa mulkku runkkari huora jaevla")
        # Polnisch / Tschechisch / Slowakisch
        + _w("kurwa kurwy kurwo kurwie chuj chuju chujowy pierdolić pierdolic pierdole pierdolony jebać jebac jebany jebana jebie "
             "skurwysyn skurwysyny cipa cipka pizda dupa szmata ruchać ruchac spierdalaj cwel gnoju kutas ")
        + _w("kurva kurvy kokot kokoti čurák curak hovno zasranej zasraný zmrd zmrdi buzerant jebat jebem mrdat mrdka sráč srac "
             "pojebaný pojebany jebať jebat kokotina ")
        # Ungarisch / Rumänisch / Albanisch / Südslawisch / Baltisch
        + _w("geci fasz faszfej faszszopó faszszopo picsa szar baszd bazdmeg bazmeg baszki   kurvaanyád kurvaanyad "
             "muie futut fututi dracu dracului curva cacat labagiu poponar poponarule curvă pizdă "
             " pidh  jebote jebo kurac kurcina picka pička govno sranje drolja   odjebi zajebi "
             "kurva bybis pyzda pyderas")
        # Türkisch
        + _w("orospu orospuçocuğu siktir sikerim sikeyim sikik amk    yarrak yarak ibne pezevenk gavat kahpe kaltak sürtük "
             "surtuk   götveren gotveren dalyarak yavşak yavsak amcık amcik sikik siktirgit")
        # Griechisch (Schrift und lateinisch)
        + _w("μαλάκας μαλακας μαλακα γαμώ γαμω γαμημένος πούτσα πουτσα πούστης πουστης αρχίδια αρχιδια μουνί μουνι πουτάνα πουτανα "
             "σκατά σκατα καριόλα καριολα καριόλης malakas malaka gamoto gamw poustis poutsa arxidia mouni poutana skata kariolis kariola")
        # Russisch (Ergänzungen, kyrillisch und lateinisch)
        + _w("хуесос хуила хуйло хуета хуйня пиздабол пиздюк пиздеть ебанутый ебанат ебаный ебучий уебок уебан заебал отъебись "
             "отьебись пидр пидарас пидарасы педик гомик чмо чмошник мразота падла паскуда дерьмо говно говнюк жополиз манда "
             "мандавошка шалава курва дрочила гнида сучара блядина ебанько хуесосы "
             "   huynya pizdabol pizdyuk pizdet ebanutyj ebanat ebanyj ebuchij uebok zaebal otebis pidr pidarasy "
             " chmo mrazota padla paskuda  govno govnyuk zhopoliz  mandavoshka shalava drochila gnida suchara blyadina")
        # Ukrainisch / Bulgarisch / Serbisch (kyrillisch)
        + _w("курво піздець підор підарас виблядок блядюга підар їбати довбойоб залупа "
             "путка пичка чукам майната "
             "јебем јебо јеботе курац пичка пизда говно срање дроља педер одјеби")
        # Arabisch (Schrift und Umschrift)
        + _w("شرموطة شرموطه عاهرة عاهره قحبة قحبه كسمك كسختك منيوك منيك متناك متناكة معرص ابنالكلب "
             "sharmouta sharmota sharmuta sharmoota kosomak kosommak kosokhtak    metnak mitnak mnayek manyouk khawal qahba kahba kahbe")
        # Persisch
        + _w("کسکش جنده حرومزاده مادرجنده کسخل گاییدم پدرسگ خارکسه مادرقهبه کونکش kosshar koskesh jende haroomzade haromzade madarjende pedarsag kirekhar")
        # Hebräisch
        + _w("זונה שרמוטה מניאק תזדיין להזדיין מזדיין sharmuta kusemek")
        # Hindi / Urdu (Umschrift und Devanagari)
        + _w("madarchod maderchod madarchodh bhenchod behenchod bhenchodh bhosdi bhosdike bhosadike bhosda bhosdika chutiya chutiye chutia "
             "chodu chodna  lawda  gaand gandu raand randwa harami haramzada haramzade haramkhor kamina kamine kutiya bhadwa "
             "bhadwe bhadve jhaant jhaatu lavda lavde gaandu randikhana "
             "मादरचोद भेनचोद बहनचोद चूतिया हरामी हरामजादा हरामखोर भोसड़ीके कमीना भड़वा लौड़ा")
        # Bengalisch / Tamil / Telugu (Umschrift)
        + _w("খানকি হারামজাদা বেশ্যা মাগি  pundai thevidiya thevdiya  koothi ommala okkala thayoli lanjakodaka dengey lanja")
        # Indonesisch / Malaiisch / Filipino
        + _w(" bangsat bajingan kontol memek ngentot kampret brengsek jancok jancuk pantek puki pukimak  sialan keparat "
             "tolol goblok bedebah    "
             "putangina tangina tanginamo gago  ulol tarantado pakyu kantot kantotan punyeta pokpok ")
        # Vietnamesisch (ohne Akzente)
        + _w("dcm dkm vcl vkl clgt")
        # Thailändisch (Umschrift)
        + _w("khuay aisat eedok dokthong")
        # Japanisch / Koreanisch (Umschrift und Schrift)
        + _w("kuso chinko chinpo manko kichigai bakayaro konoyaro yariman sibal ssibal shibal byeongsin byungshin gaesaekki gaesekki jonna "
             "jiral  michinnom michinnyeon ssibalnom ssibalnyeon  "
             "ちんこ ちんぽ まんこ チンコ チンポ マンコ キチガイ きちがい 気違い 씨발 시발 씨팔 병신 개새끼 좆같 존나 지랄 미친놈 미친년 썅 창녀 "
             "ㅅㅂ ㅆㅂ ㅂㅅ ㅈㄹ ㅄ")
    ),
    "sexual": (
        _w("pornhub xvideos xnxx   camslut    handjobs blowjobs dildos   cumming  "
           "       upskirt creepshot rapeporn ")
        + _w("pimmelgesicht nacktbild schwanzbild titenfoto wichsvorlage fickmich fickbock spermaschlampe ")
        + _w("pajeros follando follame chupame  polvazo  verga")
        + _w("buceta xoxota punheta putaria    ")
        + _w("pompini sborrare   tettona tettone")
        + _w("suce sucer    branlette  nichons")
        + _w(" sikişmek   yarak amcik ")
        + _w("pierdolenie ruchanie bzykanie  lodzik cycki cycek")
        + _w("ебаться дрочить сиськи  хуй  трахать трахнуть трахаться минет   "
             "ebatsya drochit siski pisya trahat trahnut trahatsya minet")
        + _w(" سكس   طيزك  "
             "  ")
        + _w("चुदाई चोदना चुदवा chudai chodna chudwa chodunga chodungi lundchus")
        + _w(" ngentot colmek  bokep ")
        + _w("   エロ動画   야동 ")
    ),
    "hate": (
        # Englisch / allgemein
        _w("  darkie darky  jigaboo   squaw    faggots tranny trannies kikes  "
           "porchmonkey sandnigger sandnigga niglet nigs nignog    beaners wetbacks chinks japs ")
        # Deutsch
        + _w("schlitzauge fidschi zigeunerschwein judenpack judenschweine kanakenpack negerschwein ausländerschwein asylantenpack "
             "schwuchteln  nazischwein ")
        # Spanisch / Portugiesisch / Italienisch
        + _w(" sudacas maricones  ")
        + _w(" crioulo ")
        + _w("terrone terroni   ")
        # Französisch / Niederländisch
        + _w("bamboula crouille crouilles   niakoué niakoue chinetoque pédés  negresse")
        + _w("nikker nikkers zwartjoekel makkak makakken poepchinees kankerjood joodsekut")
        # Slawisch
        + _w("хач хачи чурка чурки чурбан косоглазый узкоглазый черножопый черномазый жидяра жидовка хохлы кацапы  "
             "hach hachi churka churki churban kosoglazyj uzkoglazyj chernozhopyj zhidyara chernomazyj")
        + _w("czarnuch ciapaty      ")
        # Türkisch / Arabisch / Hebräisch / Persisch / Hindi
        + _w("   "
             "    "
             " ערבוש "
             " paki")
        # Ostasien
        + _w("ジャップ  シナ人 支那人 チャンコロ 쪽바리 짱깨 검둥이 대국놈 "
             "小日本鬼子 日本鬼子 黑鬼 黑奴 死基佬 阿三  韩国棒子 台巴子 老外滚 回族滚")
    ),
    "threat": (
        _w("  ")
        + _w("  اقتلك سأقتلك")
        + _w("ぶっ殺す ぶっころす 殺すぞ ころすぞ 殺してやる 죽여버릴  ")
    ),
}

# Teilstring-Modus: nur lange, eindeutige Wörter (kommen praktisch nie in harmlosen Wörtern vor).
S = {
    "profanity": _w("skurwysyn pierdol pierdolic vaffanculo coglione stronzo puttana caralho fodase orospu siktir sikerim vittu perkele "
                    "madarchod bhenchod behenchod bhosdike bhosadike chutiya bhosdi kurwa jebany mamahuevo hijodeputa conchatumadre "
                    "klootzak godverdomme enfoire enculé  putaria arschgeige hurensoehne schwanzlutscher motherfucking "
                    "хуесос пиздабол ебанутый ебанат уебок пидарас мудила говнюк шалава мандавошка "
                    "شرموطة شرموطه عاهرة قحبة كسمك مادرجنده حرومزاده 씨발 시발 씨팔 병신 개새끼 ちんこ ちんぽ まんこ"),
    "sexual": _w("cumslut  pornhub xvideos fickmich sborrare chudai"),
    "hate": _w("sandnigger porchmonkey judenpack schlitzauge zigeunerschwein crouille bamboula nikker zwartjoekel makkak poepchinees "
               "ジャップ 小日本鬼子 日本鬼子"),
    "threat": [],
}

# ------------------------------------------------------------------------------------------------ Wortgruppen
PHRASES = {
    "profanity": (
        _p("son of a bitch|piece of shit|go fuck yourself|fuck your mother|shut the fuck up|shut up bitch|suck my dick|eat shit|"
           "|you fucking idiot||you suck cock")
        + _p(" am arsch|fick dich|halts maul|halt dein maul|halt deine fresse|du hurensohn|du wichser|du arschloch|"
             "verpiss dich||geh ficken|du missgeburt||fick deine mutter|ich ficke deine mutter")
        + _p("hijo de la gran puta|la puta madre|vete a la verga|vete a la chingada|chinga tu madre|la concha de tu madre|"
             "me cago en tu madre|me cago en dios|hijo de tu puta madre|vete a la mierda|puta madre||come mierda|"
             "tu puta madre|mamame la verga|chupame la pija")
        + _p("filho da puta|vai se foder|vai tomar no cu|tomar no cu|puta que pariu|vai pra puta que pariu|vai a merda|"
             "foda se||filha da puta| pau|come merda")
        + _p("figlio di puttana|pezzo di merda|testa di cazzo|vai a cagare|va fanculo|vai a fanculo|dio cane|dio porco|madonna puttana|"
             "mortacci tua|succhiami il cazzo|vaffanculo stronzo|porco dio")
        + _p("va te faire foutre|va te faire enculer|nique ta mere|nique ta race|ferme ta gueule|sale pute|sale con|pauvre con|"
             "fils de pute|ta mere la pute|enculé de ta mère|va chier|sale race|suce ma bite|casse toi connard")
        + _p("krijg de |krijg de |krijg de ||| op|lazer op||hoerenzoon|"
             "kankerhoer|fuck jou|neuk je moeder|ik neuk je moeder|godver de godver")
        + _p("jebany w dupe|pierdol się|pierdol sie|wal się|spierdalaj stad|jebać cię|jebac cie|chuj ci w dupę|"
             "chuj ci w dupe|pierdolę cię|pierdole cie|kurwa mać|kurwa mac|pierdolony kurwa")
        + _p("jebi se|jebem ti mater|jebem ti majku|pickumaterinu|pičku materinu|pizda ti materina|odjebi od mene|"
             "idi u pizdu materinu|idi u kurac|odi u pm|odlazi u pm")
        + _p("|||vyjebat se|jdi |jdi do hajzlu|ty kurvo|||"
             "|zasraný kurvy||seru na tebe")
        + _p("baszd meg|a kurva anyád|a kurva anyad|anyád picsája|anyad picsaja|bazdmeg te|geci vagy|bassza meg|"
             "menj a picsába|menj a picsaba|rohadj meg|kurva életbe|kurva eletbe")
        + _p("suge pula|sugi pula|pula mea||futu-ti|fututi mortii|mortii tai||du-te dracu|"
             "du te dracu|pizda matii||dute in pula mea")
        + _p("haista vittu|mene vittuun|vittu saatana|perkele vittu|painu vittuun||")
        + _p("din jävla|din jävel|håll käften|hall kaften|fan ta dig||dra åt helvete|dra at helvete|"
             "jævla|din fitte|hold kjeft|hold kæft|fuck dig|røvhul|din luder")
        + _p("orospu çocuğu|orospu cocugu|anani sikeyim|ananı sikeyim| koyayım| koyayim|siktir git|siktir lan|"
             "sana sikeyim|ananı avradını|anani avradini|göt veren|got veren|git öl|git ol|defol git")
        + _p("ابن الكلب|ابن العاهرة|ابن الشرموطة|ابن القحبة|ابن المتناكة|كس امك|كس أمك|كس اختك|كس أختك|يلعن ابوك|يلعن أبوك|يلعن دينك|يلعن شرفك|"
             "ibn el kalb|ibn el sharmouta|ibn sharmouta|ibn el sharmota|ya ibn el kalb|kos omak|kos ommak|kos okhtak|"
             "yel3an abouk|yilan abuk|ya kalb|ya sharmouta|ya sharmota|ana anik|ya ibn el sharmouta")
        + _p("پدر سگ|مادر جنده|کس کش|کیرم دهنت|کیر تو|کص ننت|کس ننت|ننه جنده|kir to|kir to dahanet|kos nanat|kos nane|pedar sag|"
             "madar jende|kiram tush|kiram to|")
        + _p("בן זונה|בן שרמוטה|כוס אמק|כוס אמא שלך|לך תזדיין|בן של זונה|הלך תזדיין|ben zona|ben sharmuta|kus emek|kus ummak|lech tizdayen")
        + _p("teri maa ki|maa ki chut|teri maa ka bhosda|behen ke lode|bhen ke |teri behen ki|maa chod|behen chod|"
             "||teri gaand|gaand mara||lund chus|lund le|lund pe|madar chod|bhen chod|"
             "तेरी माँ की|माँ की चूत|बहन के लौड़े|तेरी माँ का भोसड़ा")
        + _p("anak |anak haram|mati kau|mampus kau|dasar |dasar |bangsat lu|kontol lu|memek lu|"
             "puki mak kau|pukimak kau|cibai kau| kau|sial kau|tai kau|")
        + _p("putang ina mo|putang ina|tang ina mo|gago ka|ulol ka|| ka|punyeta ka|pakshet||"
             "anak ng puta|")
        + _p("dit me|dit con me||du ma|du me||con cac||thang cho|con cho|oc cho|||"
             "địt mẹ|đụ má|đụ mẹ|thằng chó|con đĩ|đồ chó|vãi lồn||||cái lồn||lồn ")
        + _p("||ee dok|dok thong||||||||")
        + _p("このやろう|くたばれ||死ねよ|うざい死ね|ばかやろう|ばかやろ|クソ野郎|くそやろう|くそったれ|クソったれ|"
             "kono yaro|kuso yaro|kutabare||bakayaro|kuso tare|")
        + _p("씨발놈|씨발년|개새끼야|좆까|좆까라|지랄하네|지랄 하네|엿먹어|엿 먹어|꺼져라||니 애미|니애미|느금마|"
             "ssibal nom|ssibal nyeon|jot kka|jotkka|jiral hane|yeot meogeo||ni aemi|neogeum ma")
    ),
    "sexual": (
        _p("|send pussy pics|send me pics of you|show me your pussy|show me your ass|take off your clothes|"
           "show me your body|i want to fuck you|come sit on my face|wanna suck|let me lick|bend over for me|suck me off")
        + _p("zeig mir deinen arsch|zeig deine muschi||schick mir nacktbilder|schick mir fotos von dir|ich will dich nackt sehen|"
             "ich will dich lecken|setz dich auf mein gesicht|blas mir|lutsch mir|")
        + _p("enviame fotos|enviame nudes|muéstrame las tetas|muestrame las tetas|quiero follarte|quiero cogerte||"
             "|chupamela|chupámela|mandame fotos| nudes|mandame nudes")
        + _p(" nudes|mande nudes|me  foto pelada|quero te comer|quero te foder||mostra a bunda|")
        + _p("mandami le foto|mandami nudes|fammi vedere le tette|ti voglio |togliti i vestiti|succhiami")
        + _p("montre tes seins|envoie des nudes|envoie moi des nudes|je veux te |enlève tes vêtements|enleve tes vetements|"
             "montre moi ta |suce moi")
        + _p("пришли фото голой|скинь нюдсы|скинь ню|покажи сиськи|хочу тебя трахнуть|раздевайся|покажи грудь|давай трахаться|"
             "соси хуй|отсоси мне|хочу тебя выебать|покажи пизду|скинь фото без одежды")
        + _p("发裸照|发你的裸照|||给我看你的胸|我想操你|我想干你||约炮吗")
        + _p("mande nudes|بدي نيكك|ابعتلي صور عارية|ابعت صورك عارية|اخلع ملابسك|سكس معي|baddi nikek|ab3atli suwar|")
        + _p("nudes bhej|nude bhej|kapde utaar|apni photo bhej|tujhe chodunga|chodne ka mann| karna hai|nanga ho ja")
        + _p("kirim foto |kirim nude|buka bajumu|mau ngentot|ayo ngewe||kirim bugil")
        + _p("お前とやりたい|裸の写真送って|脱いで見せて|ヌード送って|벗어봐|누드 보내|벗은 사진| 사진 보내")
    ),
    "hate": (
        _p("kill all the jews|kill all jews|kill the niggers|death to all muslims||death to blacks|gas the muslims|"
           "gas the gays|go back to africa|go back to your country|burn the mosque|burn the synagogue|white genocide|"
           "great replacement||the holocaust never happened|holocaust is a lie|race war now|rahowa||"
           "i hate all muslims|i hate jews|i hate blacks|i hate gays|all muslims are terrorists|jews control the world|"
           "||niggers are|faggots should die|gays should die|gays must die|"
           "kill all faggots|kill all queers|hang all gays|send them to the ovens")
        + _p("juden vergasen|alle juden töten|alle juden toeten|tötet die juden|toetet die juden|ausländer raus|auslaender raus|"
             "alle ausländer töten|alle auslaender toeten|neger raus|türken raus|tuerken raus|moslems raus|muslime raus|"
             "homosexuelle aufhängen|schwule aufhängen|schwule vergasen|vergast sie|ab ins gas|holocaust lüge|holocaust luege|"
             "sieg heil|heil hitler||")
        + _p("mueran los judios|mueran los negros|muerte a los judios|muerte a los musulmanes|muerte a los gays|"
             "matad a todos los|mátalos a todos|vuelve a tu país|vuelve a tu pais|moro de mierda|sudaca de mierda|negro de mierda|"
             "maricón de mierda|maricon de mierda| de mierda|gitano de mierda")
        + _p("morte aos judeus|morte aos negros|morte aos gays|volta pra áfrica|volta pra africa| de merda|negro de merda|"
             "viado de merda|nordestino de merda")
        + _p("morte agli ebrei|morte ai neri|morte ai gay|tornate a casa vostra|negro di merda|frocio di merda|terrone di merda|"
             " di merda|ebreo di merda")
        + _p("mort aux juifs|mort aux arabes|mort aux noirs|mort aux pédés|mort aux |retourne dans ton pays|sale arabe|sale noir|"
             "sale juif|sale nègre|sale negre|sale pédé|sale pede|sale bougnoule|sale crouille|sale blanc|sale gouine")
        + _p("dood aan de joden|dood aan alle joden|dood aan moslims|dood aan homo's|ga terug naar je land|vuile neger|vuile jood|"
             "vuile moslim|vuile homo|vuile marokkaan|vuile turk| marokkanen|kankerjood|kankerneger|kankermoslim")
        + _p("смерть евреям|смерть черным|смерть чёрным|смерть мусульманам|смерть геям|бей хачей|бей чурок|бей жидов|"
             "|москаль на ножи|чурки вон|хачи вон|убить всех евреев|убить всех геев|убейте всех|"
             "|в печь жидов|чурка нерусь|нерусь вон")
        + _p("śmierć żydom|smierc zydom| do gazu|zydzi do gazu|czarnuchy do afryki|||"
             "wypierdalać z polski|wypierdalac z polski|zabić wszystkich|zabic wszystkich")
        + _p("yahudilere ölüm|yahudilere olum|ermenilere ölüm|kürtlere ölüm|gavur ölsün|gavurlar ölsün|çingene pislik|cingene pislik")
        + _p("الموت لليهود|الموت للمسلمين|الموت للمثليين|الموت للسود|اقتلوا اليهود|اقتلوا المسلمين|اقتلوا الكفار|اقتلوا المثليين|"
             " اليهود|يهود الكلاب|مثلي قذر|kill el yahood|mout lil yahoud|el mawt lel yahood")
        + _p("|מוות לערבים|מוות לערבים|||mavet laaravim")
        + _p("মুসলমানদের মার|हिंदुओं को मारो|मुसलमानों को मारो|katwe katwe|katue ko maro|mullo ko maro|mulle ko maro|"
             "kafiron ko maro|hinduon ko maro|musalmano ko maro|pakistan jao|pakistan chale jao")
        + _p("ジャップは死ね|シナ人は死ね|朝鮮人は死ね|チョンは死ね|在日は出ていけ|在日は帰れ|中国人は出ていけ|"
             "日本人は死ね|中国人は死ね|韩国人去死|朝鲜人去死|黑人去死|犹太人去死|外国人滚出|"
             "일본인 죽어|중국인 죽어|흑인 죽어|조선족 꺼져|짱깨 꺼져|쪽바리 꺼져")
        + _p("bunuh semua cina|bunuh semua china|usir cina|cina kafir|kafir bunuh|bunuh semua kafir|bunuh semua orang kristen|"
             "bunuh semua yahudi|bunuh semua muslim|yahudi laknat")
    ),
    "threat": (
        _p("i will rape you|i'll rape you|ill rape you|im going to rape you|i'm going to rape you|gonna rape you|i will murder you|"
           "i'll murder you|ill murder you|i will shoot you|i'll shoot you|ill shoot you|i will stab you|i'll stab you|ill stab you|"
           "i will hurt you|i'll hurt you|ill hurt you|i will beat you up|i'll beat you up|im gonna kill you|i'm gonna kill you|"
           "gonna kill you|going to kill you|i will end you|i will burn your house|i know your address|i found your address|"
           "i will find your family|i will kill your family|kill yourself now|please kill yourself|end yourself|hope you die|"
           "i hope you die|i hope you get cancer|hope you get cancer|i hope your family dies|you deserve to die|die slowly|"
           "slit your throat|cut your throat|i will bomb|||shoot up the school|going to shoot up")
        + _p("ich vergewaltige dich|ich werde dich vergewaltigen|ich erschiesse dich|ich erschieße dich|ich ersteche dich|ich steche dich ab|"
             "ich schlage dich tot|ich prügel dich|ich pruegel dich|ich bring dich um|ich töte deine familie|ich toete deine familie|"
             "ich weiss wo du wohnst|ich weiß wo du wohnst|ich finde dich|ich finde deine adresse|ich zünde dein haus an|"
             "bring dich um|bring dich endlich um|stirb endlich|stirb langsam|ich hoffe du stirbst|hoffentlich stirbst du|"
             "ich hoffe du verreckst|verreck|verrecke|krepier|ich lass dich verschwinden| an der schule")
        + _p("te voy a violar|te voy a matar|te voy a destripar|te voy a apuñalar|te voy a disparar|te mato|voy a matarte|"
             "voy a violarte|sé dónde vives|se donde vives|se donde vives|ojalá te mueras|ojala te mueras|muérete|muerete|"
             "mátate|matate|suicídate|suicidate|ahórcate|ahorcate|ojalá tu familia muera|voy a quemar tu casa")
        + _p("vou te matar|vou te estuprar|vou te esfaquear|vou te dar um tiro|eu sei onde você mora|eu sei onde voce mora|"
             "|se mate|morra logo|espero que você morra|espero que voce morra|vou matar sua família|vou matar sua familia|"
             "vou queimar sua casa||mata-te")
        + _p("ti ammazzo|ti uccido|ti stupro|ti accoltello|ti sparo|so dove abiti|ammazzati|uccidati|spero che muori|spero che tu muoia|"
             "ti brucio la casa|ti sgozzo|ti taglio la gola|ti faccio fuori")
        + _p("je vais te tuer|je vais te violer|je vais te buter|je vais te planter|je sais où tu habites|je sais ou tu habites|"
             "|| salope|suicide toi|suicide-toi|pends toi|pends-toi|j'espère que tu meurs|j espere que tu meurs|"
             "j'espère que tu crèves|je vais brûler ta maison|je vais bruler ta maison|je vais te retrouver|va crever")
        + _p("ik vermoord je|ik ga je vermoorden|ik ga je verkrachten|ik steek je neer|ik schiet je neer|ik weet waar je woont|"
             "|ga maar dood|hoop dat je doodgaat|ik hoop dat je doodgaat|ik hoop dat je  krijgt|doe jezelf wat aan|"
             "hang jezelf op|ik steek je huis in brand|ik maak je af")
        + _p("zabiję cię|zabije cie|zabiję was|zabije was|zgwałcę cię|zgwalce cie|wiem gdzie mieszkasz|zabij się|zabij sie|"
             "powieś się|powies sie|oby cię szlag trafił|oby cie szlag trafil|mam nadzieję że zdechniesz|zdychaj|zdechnij|"
             "spalę ci dom|spale ci dom|wypatroszę cię|wypatrosze cie")
        + _p("zabiju tě|zabiju te|zabiju vás|znásilním tě|znasilnim te|vím kde bydlíš|vim kde bydlis|zabij se|oběs se|obes se|"
             "doufám že chcípneš|doufam ze chcipnes|chcípni|chcipni|seber se a zdechni")
        + _p("megöllek|megerőszakollak|megerőszakollak|tudom hol laksz|öld meg magad|old meg magad|akaszd fel magad|dögölj meg|dogolj meg|"
             "remélem meghalsz|remelem meghalsz|felgyújtom a házad|felgyujtom a hazad")
        + _p("te omor|te violez|stiu unde locuiesti|știu unde locuiești|sinucide-te|sinucide te|spânzură-te|spanzura te|"
             "sper să mori|sper sa mori|||o să te omor|o sa te omor|iti dau foc la casa")
        + _p("tapan sinut|tapan sut|raiskaan sinut|tiedän missä asut|tiedan missa asut|tapa itsesi|mene tappamaan itsesi||"
             "toivottavasti kuolet|poltan talosi| pois")
        + _p("jag dödar dig|jag dodar dig|jag ska döda dig|jag ska doda dig|jag våldtar dig|jag vet var du bor|ta livet av dig|"
             "hoppas du dör|hoppas du dor||jag bränner ditt hus|jag skjuter dig|jeg dreper deg|jeg vet hvor du bor|ta livet av deg|"
             "jeg slår deg ihjel|håper du dør|haper du dor|jeg dræber dig|jeg draeber dig|jeg ved hvor du bor|tag dit eget liv|håber du dør")
        + _p("seni öldüreceğim|seni olduruecegim|seni öldürürüm|seni oldururum|sana tecavüz edeceğim|nerede oturduğunu biliyorum|"
             "nerede oturdugunu biliyorum|| lan|kendini öldür|kendini oldur|kendini as|umarım ölürsün|umarim olursun|"
             "evini yakacağım|evini yakacagim|seni gebertirim|seni bulacağım|seni bulacagim")
        + _p("ты сдохнешь|сдохни|сдохни тварь|я тебя убью|я тебя найду|я знаю где ты живёшь|я знаю где ты живешь|убейся|повесься|"
             "вскрой вены|надеюсь ты сдохнешь|чтоб ты сдох|чтоб ты сдохла|я тебя изнасилую|я сожгу твой дом|я убью твою семью|"
             "иди убейся|иди повесься|выпей яд|хорошо бы тебе сдохнуть|ya tebya ub'yu|ya tebya ubyu|sdohni|ubejsya|povesisya")
        + _p("سأقتلك|سوف اقتلك|سأغتصبك|اعرف اين تسكن|أعرف أين تسكن|اقتل نفسك|انتحر|شنق نفسك|اتمنى ان تموت|أتمنى أن تموت|"
             "سأحرق بيتك|سأذبحك|اذبحك|||sa2tolak|sa2taloka|ana ha2tolak|ahrop baytak|entahir|ontahir|")
        + _p("אני אהרוג אותך|אני יודע איפה אתה גר|תתאבד||אני אחסל אותך|ani ehereg otcha|titabed|tamut")
        + _p("میکشمت|می‌کشمت|میکشمت|میدونم کجا زندگی میکنی|خودتو بکش|برو بمیر|امیدوارم بمیری|خونه ات رو آتش میزنم|mikosham to|mikoshamet|"
             "khodeto bokosh|boro bemir|omidvaram bemiri")
        + _p("tujhe maar dunga|tujhe jaan se maar dunga|main tujhe maar dalunga|mai tujhe maar dalunga||||"
             "tujhe jala dunga|tera ghar jala dunga|jaan se mar dunga|teri jaan le lunga|khud ko maar|suicide kar le|"
             "तुझे मार डालूंगा|तुझे जान से मार दूंगा|मर जा|जाके मर|तेरा घर जला दूंगा")
        + _p("aku bunuh kau|aku akan membunuhmu|gue bunuh lo|gua bunuh lu|aku perkosa kamu|aku tahu rumahmu|bunuh diri sana|mati sana|"
             "semoga kau mati|semoga lo mati|mampus lo|mampus kau|aku bakar rumahmu|gue bakar rumah lo|akan kubunuh kau|bunuh dirimu")
        + _p("papatayin kita|papatayin ko kayo|gagahasain kita|alam ko kung saan ka nakatira|magpakamatay ka|magpakamatay ka na|mamatay ka na|"
             "sana mamatay ka|susunugin ko bahay mo|patay ka sa akin")
        + _p("tao giet may|tao se giet may|tao biet may o dau|di chet di|chet di|chet  di|tu tu di|may chet di|tao dam may|"
             "mong may chet|tao dot nha may|tao dot nha may")
        + _p("||| sa|||||||"
             " || sa")
        + _p("殺してやる|殺す|ぶっ殺す|ぶっ殺してやる|死ねばいいのに|死んでしまえ|自殺しろ|首吊れ|飛び降りろ|お前の家を燃やす|家燃やす|"
             "住所知ってる|どこに住んでるか知ってる|レイプしてやる|犯してやる|殺されたいのか|消えろ死ね|"
             "죽여버릴게|죽여버린다|죽여 버린다|죽이겠다|죽일거야|죽일 거야|죽어버려|뒤져라|뒤져버려|자살해|목매|뛰어내려|"
             "너네 집 알아|집 알아|강간할|강간해|불 질러|네 가족 죽|니 가족 죽|"
             "杀了你|杀你全家|我要杀你|我知道你住哪|去死吧|你怎么不去死|自杀吧|跳楼吧|上吊吧|我要强奸你|烧你家|烧了你家|弄死你|砍死你|"
             "我会找到你|搞死你|弄死你全家|死全家|全家死光|你全家|你妈死了|祝你早死|祝你全家")
    ),
}

# Harmlose Wörter, die sonst auffallen würden (werden vor der Prüfung entfernt). Nur eintragen, was ein Test als Fehltreffer zeigt.
ALLOW = []
