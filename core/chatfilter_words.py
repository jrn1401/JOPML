"""Wortlisten für den Chat-Filter (Schimpfwörter, sexuelle Belästigung, Hass/Extremismus, Bedrohung).

Schreibweise: ganz normal und klein, so wie man das Wort schreibt. Der Filter wandelt Liste UND Nachricht in dieselbe
Grundform um (siehe chatfilter.skeleton): Groß-/Kleinschreibung, Akzente, Leetspeak (sh1t, $hit), Look-alike-Buchstaben
aus anderen Alphabeten, Leerzeichen/Punkte zwischen den Buchstaben, Wiederholungen (fuuuck) und Sternchen (f*ck) sind
damit abgedeckt.

Eintragsarten
  W        ganzes Wort (verhindert "Scunthorpe"-Fehler wie "class" -> "ass")
  S        auch als Teil eines Wortes (nur für Wörter, die praktisch nie harmlos in anderen Wörtern vorkommen)
  PHRASES  Wortgruppen (Wörter in beliebigem Abstand von 1–3 Trennzeichen)
ALLOW      harmlose Wörter, die sonst fälschlich auffallen würden (werden vor der Prüfung entfernt)

Die Listen sind bewusst nicht vollständig – keine Wortliste ist das. Weitere Begriffe einfach ergänzen und
`python tools/gen_filter_sql.py` ausführen, damit der Server dieselben Regeln bekommt.
Wörter, die in einer anderen Sprache harmlos sind (z. B. englisch "bite", spanisch "con"), stehen absichtlich nicht drin.
"""

CATEGORIES = ("profanity", "sexual", "hate", "threat")

W = {
    "profanity": [
        # Englisch
        "ass", "arse", "asshole", "bastard", "bitch", "bitches", "cock", "cocksucker", "cunt", "dick", "dickhead", "douche",
        "douchebag", "dumbass", "jackass", "motherfucker", "piss", "pissed", "pissing", "prick", "twat", "wanker",         "retard", "retarded", "retards", "scumbag", "shithead", "fuk", "fuc", "phuck", "fck",         # Deutsch
        "arsch", "arschloch", "fick", "ficken", "ficker", "fotze", "hure", "hurensohn", "wichser", "wixer",         "scheisse", "scheiss", "scheisskerl", "schlampe", "spast", "spasti", "missgeburt", "drecksau", "verpiss",
        "vollidiot", "dreckskerl", "miststueck",         # Spanisch
        "mierda", "joder", "puta", "puto", "putas", "cabron", "pendejo", "gilipollas", "verga", "chinga", "chingar",
        "marica", "maricon", "zorra", "hijueputa", "culero", "mamon",
        # Französisch
        "merde", "putain", "connard", "connasse", "salope", "encule", "enculer", "pute", "ntm", "fdp", "batard",
        "salaud", "couille", "couilles", "branleur", "foutre",
        # Russisch (kyrillisch und lateinisch geschrieben)
        "сука", "суки", "блять", "блядь", "бляд", "хуй", "хуя", "хуе", "пизда", "пиздец", "ебать", "ебал", "ебан", "ебло",
        "мудак", "мудила", "пидор", "пидорас", "залупа", "долбоеб", "гандон", "шлюха", "мразь", "ублюдок", "нахуй", "похуй",
        "suka", "blyat", "blyad", "pizda", "pizdec", "pidor", "pidoras", "mudak", "ebat", "nahui", "naxui", "nahuy", "huy",
        "xuy", "hui", "zalupa", "gandon", "shlyuha", "ublyudok", "dolboeb",
        # Chinesisch
        "傻逼", "傻比", "操你妈", "操你媽", "草泥马", "艹你妈", "他妈的", "他媽的", "妈的", "你妈的", "婊子", "贱人", "賤人", "狗杂种",
        "王八蛋", "鸡巴", "雞巴", "滚蛋", "傻屌", "狗日的", "妈逼", "马勒戈壁", "尼玛", "你妈逼", "操你", "干你娘",
    ],
    "sexual": [
        # Englisch
        "pussy", "pussies", "tits", "titties", "boobs", "boobies", "nude", "nudes", "porn", "porno", "blowjob", "handjob",
        "cumshot", "dildo", "horny", "sext", "sexting", "slut", "sluts", "whore", "whores", "milf", "bukkake",
        "gangbang", "creampie", "deepthroat", "jerkoff", "cum", "fap", "fapping",
        # Deutsch
        "titten", "muschi", "nutte", "pimmel", "nacktbilder", "nacktfoto", "wichsen",         "fickbar", "arschficker", "sexsklave", "spermaschlucker",
        # Spanisch
        "tetas", "follar", "follame", "culo", "pajero",         # Französisch
        "nichons", "sucemoi",         # Russisch
        "сиськи", "дрочить", "отсос", "отсоси", "минет", "siski", "drochit", "otsos", "minet", "trahat",
        # Chinesisch
        "做爱", "約炮", "约炮", "裸照", "口交", "打飞机", "操逼", "骚货", "性奴",
    ],
    "hate": [
        # Beleidigungen gegen Gruppen (Auswahl der gängigsten)
        "nigger", "niggers", "nigga", "niggas", "faggot", "faggots", "fag", "fags", "tranny", "trannies", "kike", "kikes",
        "spic", "spics", "chink", "chinks", "gook", "gooks", "wetback", "wetbacks", "paki", "pakis",
        "towelhead", "beaner", "raghead", "shemale", "zipperhead", "jewboy",
        "neger", "kanake", "kanaken", "zigeuner", "judensau", "judenschwein", "schwuchtel", "kameltreiber", "untermensch",
        "untermenschen", "kümmeltürke", "kuemmeltuerke", "itaker", "polacke",         "sudaca", "negrata", "bougnoule", "youpin", "bicot",         "жид", "жиды", "хохол", "кацап", "чурка", "нигер", "ниггер", "негр", "черномазый", "zhid", "khokhol", "katsap", "churka",
        "黑鬼", "支那", "死基佬", "棒子", "小日本", "尼哥",
        # Symbole / Gruppen
        "kkk", "holohoax", "siegheil", "heilhitler", "whitepower",
    ],
    "threat": [
        "kys", "dox", "doxx", "doxxing",     ],
}

# Bei diesen Wörtern gilt auch die Schreibweise als Teil eines längeren Wortes (S-Modus).
S = {
    "profanity": [
        "fuck", "shit", "bullshit", "cunt", "bitch", "wanker", "motherfucker", "asshole", "arschloch", "wichser", "scheisse",
        "hurensohn", "fotze", "schlampe", "missgeburt", "gilipollas", "putain", "connard", "connasse", "salope", "encule",
        "pizda", "pizdec", "ebat", "mudak", "pidoras", "сука", "блять", "блядь", "пизда", "пиздец", "ебать", "мудак", "пидорас",
        "залупа", "долбоеб", "нахуй", "ублюдок", "傻逼", "操你妈", "草泥马", "他妈的", "妈的", "婊子", "王八蛋", "鸡巴", "狗杂种",
        "mierda", "cabron", "pendejo", "hijueputa", "chingar", "chinga", "couilles", "branler", "bougnoule",
    ],
    "sexual": [
        "pussy", "blowjob", "handjob", "cumshot", "dildo", "bukkake", "gangbang", "creampie", "deepthroat", "nacktbilder",
        "arschficker", "spermaschlucker", "sexsklave", "дрочить", "минет", "做爱", "约炮", "裸照", "口交", "打飞机", "操逼",
    ],
    "hate": [
        "nigger", "nigga", "faggot", "judensau", "judenschwein", "schwuchtel", "kameltreiber", "untermensch", "holohoax",
        "kanaken", "ниггер", "черномазый", "黑鬼", "支那", "kümmeltürke", "kuemmeltuerke",
    ],
    "threat": [],
}

PHRASES = {
    "profanity": [
        "fuck you", "fuck off", "go to hell", "halt die fresse", "halt die klappe", "ta gueule", "nique ta mere", "hijo de puta",
        "vete a la mierda", "fils de pute", "иди нахуй", "пошел нахуй", "иди на хуй", "заткни пасть", "cállate la boca",
    ],
    "sexual": [
        "send nudes", "send me nudes", "show me your tits", "show me your boobs", "suck my dick", "suck my cock", "eat my pussy",
        "wanna fuck", "want to fuck", "lets fuck", "let's fuck", "fuck me", "schick nudes", "zeig mir deine titten", "lutsch meinen",
        "blas mir einen", "ich will dich ficken",
    ],
    "hate": [
        "gas the jews", "jews to the gas", "kill all jews", "kill all muslims", "kill all blacks", "kill all gays",
        "kill all niggers", "kill all whites", "kill all arabs", "kill all christians", "death to jews", "death to all jews",
        "death to muslims", "death to gays", "hang the niggers", "adolf hitler was right", "hitler did nothing wrong",
        "ausländer raus", "auslaender raus", "juden raus", "tötet alle juden", "toetet alle juden", "tötet alle muslime",
        "sieg heil", "heil hitler", "white power", "gas them all",
        "смерть евреям", "смерть жидам", "бей жидов", "杀光犹太人", "杀光黑人",
    ],
    "threat": [
        "kill yourself", "go kill yourself", "i will kill you", "ill kill you", "i'll kill you", "i will find you",
        "i know where you live", "hang yourself", "neck yourself", "go die", "drink bleach", "you should die", "die in a fire",
        "bring dich um", "erschiess dich", "erschieß dich", "geh sterben", "ich bring dich um", "ich töte dich", "ich toete dich",
        "ich weiss wo du wohnst", "ich weiß wo du wohnst", "matate", "suicidate", "te voy a matar", "je vais te tuer",
        "va te pendre", "tue toi", "убей себя", "я тебя убью", "я знаю где ты живешь", "杀了你", "去死", "自杀吧", "我知道你住哪",
    ],
}

ALLOW = [
    "scunthorpe", "shiitake", "shitake", "snigger", "niggard", "cum laude", "pussycat", "pussy willow",
]


# --- Weltweite Erweiterung (v1.7.5) ------------------------------------------
from core import chatfilter_words_world as _world  # noqa: E402


# Einträge der Weltliste, die als eigenes Wort zu viele harmlose Treffer ergeben würden (Namen, Alltagswörter in anderen Sprachen).
_DROP = {"pau", "op", "jdi", "anak", "dasar", "kau", "ka", "lồn", "pois", "lan", "sa", "pidh", "vcl", "vkl", "clgt", "hach", "хач",
         "huy", "hui", "eedok", "ee dok", "시발",
         "你全家", "祝你全家", "死全家", "全家死光", "我会找到你", "du ma", "du me", "krijg de", "an der schule", "ich finde dich", "mort aux",
         "de mierda", "de merda", "di merda", "je veux te", "montre moi ta", "karna hai", "bhen ke", "tu tu di", "hachi", "xaci", "pedes",
         "mort aux pedes", "اليهود", "marokkanen", "lul", "jonna", "jirai", "kamina", "kamine", "pytka", "minet", "pajero", "pajeros", "nude"}


def _merge(base, extra):
    for cat in CATEGORIES:
        seen = set(base[cat])
        for w in extra.get(cat, []):
            w = w.strip()
            if w and w not in seen and w not in _DROP:
                seen.add(w)
                base[cat].append(w)


_merge(W, _world.W)
_merge(S, _world.S)
_merge(PHRASES, _world.PHRASES)
ALLOW += [a for a in _world.ALLOW if a not in ALLOW]
