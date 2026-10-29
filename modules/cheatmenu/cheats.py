"""Cheat-Listen für das Cheat-Menü (ohne GUI-Import).

Minecraft: Befehle über den Chat (Welt mit "Cheats erlauben" bzw. per LAN-Freigabe aktiviert).
GTA 5 Enhanced: die offiziellen Cheat-Codes von Rockstar über die Cheat-Konsole (nur Story-Modus).
Alles hier nutzt nur Funktionen, die das Spiel selbst anbietet – kein Speicher-Hacking, nichts für Online-Modi.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Cheat:
    id: str
    section: str
    title: str
    desc: str
    commands: tuple          # Minecraft: Chat-Befehle; GTA: genau ein Cheat-Code


# ---------------------------------------------------------------- Minecraft (Java 1.21.11+ / 1.26.x)
def _mc(id, section, title, desc, *commands):
    return Cheat(id, section, title, desc, tuple(commands))


_GOD = ("/effect give @s minecraft:resistance infinite 4 true",
        "/effect give @s minecraft:regeneration infinite 4 true",
        "/effect give @s minecraft:fire_resistance infinite 0 true",
        "/effect give @s minecraft:water_breathing infinite 0 true",
        "/effect give @s minecraft:saturation infinite 0 true")

MINECRAFT = [
    # Spielmodus
    _mc("mc_creative", "Spielmodus", "Kreativ", "Fliegen, unendlich Blöcke, unverwundbar.", "/gamemode creative"),
    _mc("mc_survival", "Spielmodus", "Überleben", "Zurück in den normalen Modus.", "/gamemode survival"),
    _mc("mc_spectator", "Spielmodus", "Zuschauer", "Durch Wände fliegen und alles ansehen.", "/gamemode spectator"),
    _mc("mc_adventure", "Spielmodus", "Abenteuer", "Blöcke können nicht abgebaut werden.", "/gamemode adventure"),
    # Spieler
    _mc("mc_god", "Spieler", "Gott-Modus", "Resistenz V, Regeneration, Feuer- und Wasserschutz, nie hungrig.", *_GOD),
    _mc("mc_heal", "Spieler", "Heilen & satt", "Volle Herzen und voller Hunger.",
        "/effect give @s minecraft:instant_health 1 10 true", "/effect give @s minecraft:saturation 1 20 true"),
    _mc("mc_nightvision", "Spieler", "Nachtsicht", "Auch in Höhlen alles sehen.", "/effect give @s minecraft:night_vision infinite 0 true"),
    _mc("mc_haste", "Spieler", "Turbo-Abbau", "Blöcke viel schneller abbauen (Eile III).", "/effect give @s minecraft:haste infinite 2 true"),
    _mc("mc_strength", "Spieler", "Superstärke", "Stärke V für 5 Minuten.", "/effect give @s minecraft:strength 300 4 true"),
    _mc("mc_invis", "Spieler", "Unsichtbar", "Unsichtbarkeit für 5 Minuten.", "/effect give @s minecraft:invisibility 300 0 true"),
    _mc("mc_slowfall", "Spieler", "Langsam fallen", "Kein Fallschaden für 5 Minuten.", "/effect give @s minecraft:slow_falling 300 0 true"),
    _mc("mc_xp", "Spieler", "+30 Level", "30 Erfahrungslevel dazu.", "/xp add @s 30 levels"),
    _mc("mc_clear_fx", "Spieler", "Effekte weg", "Entfernt alle Effekte.", "/effect clear @s"),
    # Körper (Attribute)
    _mc("mc_giant", "Körper", "Riese", "Dreimal so groß.", "/attribute @s minecraft:scale base set 3"),
    _mc("mc_tiny", "Körper", "Winzig", "Ein Drittel so groß.", "/attribute @s minecraft:scale base set 0.3"),
    _mc("mc_speed", "Körper", "Blitzschnell", "Läuft 2,5-mal so schnell.", "/attribute @s minecraft:movement_speed base set 0.25"),
    _mc("mc_jump", "Körper", "Mega-Sprung", "Springt mehrere Blöcke hoch.", "/attribute @s minecraft:jump_strength base set 1.0"),
    _mc("mc_moon", "Körper", "Mond-Schwerkraft", "Fällt ganz langsam.", "/attribute @s minecraft:gravity base set 0.02"),
    _mc("mc_step", "Körper", "Treppensteiger", "Läuft ohne Springen über ganze Blöcke.", "/attribute @s minecraft:step_height base set 1.5"),
    _mc("mc_reach", "Körper", "Lange Arme", "Blöcke aus 10 Blöcken Entfernung abbauen.", "/attribute @s minecraft:block_interaction_range base set 10"),
    _mc("mc_body_reset", "Körper", "Körper normal", "Setzt alle Körper-Cheats zurück.",
        "/attribute @s minecraft:scale base set 1", "/attribute @s minecraft:movement_speed base set 0.1",
        "/attribute @s minecraft:jump_strength base set 0.42", "/attribute @s minecraft:gravity base set 0.08",
        "/attribute @s minecraft:step_height base set 0.6", "/attribute @s minecraft:block_interaction_range base set 4.5"),
    # Gegenstände
    _mc("mc_diamonds", "Gegenstände", "64 Diamanten", "", "/give @s minecraft:diamond 64"),
    _mc("mc_netherite", "Gegenstände", "64 Netherit", "", "/give @s minecraft:netherite_ingot 64"),
    _mc("mc_armor", "Gegenstände", "Netherit-Rüstung", "Helm, Brustplatte, Hose, Stiefel.",
        "/give @s minecraft:netherite_helmet", "/give @s minecraft:netherite_chestplate",
        "/give @s minecraft:netherite_leggings", "/give @s minecraft:netherite_boots"),
    _mc("mc_sword", "Gegenstände", "Super-Schwert", "Netherit-Schwert mit Schärfe V, Haltbarkeit III, Plünderung III.",
        "/give @s minecraft:netherite_sword[minecraft:enchantments={sharpness:5,unbreaking:3,looting:3}]"),
    _mc("mc_pick", "Gegenstände", "Super-Spitzhacke", "Netherit-Spitzhacke mit Effizienz V, Glück III, Haltbarkeit III.",
        "/give @s minecraft:netherite_pickaxe[minecraft:enchantments={efficiency:5,fortune:3,unbreaking:3}]"),
    _mc("mc_elytra", "Gegenstände", "Elytra + Raketen", "Flügel und 64 Feuerwerksraketen.",
        "/give @s minecraft:elytra", "/give @s minecraft:firework_rocket 64"),
    _mc("mc_apples", "Gegenstände", "Verzauberte Äpfel", "16 verzauberte goldene Äpfel.", "/give @s minecraft:enchanted_golden_apple 16"),
    _mc("mc_totem", "Gegenstände", "Totem", "Rettet dich einmal vor dem Tod.", "/give @s minecraft:totem_of_undying"),
    # Welt
    _mc("mc_day", "Welt", "Tag", "", "/time set day"),
    _mc("mc_night", "Welt", "Nacht", "", "/time set midnight"),
    _mc("mc_clear", "Welt", "Sonne", "", "/weather clear"),
    _mc("mc_thunder", "Welt", "Gewitter", "", "/weather thunder"),
    _mc("mc_freeze_time", "Welt", "Zeit anhalten", "Die Tageszeit bleibt stehen.", "/gamerule minecraft:advance_time false"),
    _mc("mc_run_time", "Welt", "Zeit läuft", "Tageszeit läuft wieder.", "/gamerule minecraft:advance_time true"),
    _mc("mc_keepinv", "Welt", "Inventar behalten", "Nach dem Tod bleibt alles im Inventar.", "/gamerule minecraft:keep_inventory true"),
    _mc("mc_nomobs", "Welt", "Keine Monster-Spawns", "Es spawnen keine neuen Wesen mehr.", "/gamerule minecraft:spawn_mobs false"),
    _mc("mc_nophantoms", "Welt", "Keine Phantome", "", "/gamerule minecraft:spawn_phantoms false"),
    # Bewegung & Spaß
    _mc("mc_up", "Bewegung & Spaß", "50 Blöcke hoch", "Teleport nach oben (Langsam fallen nicht vergessen!).", "/tp @s ~ ~50 ~"),
    _mc("mc_spawnpoint", "Bewegung & Spaß", "Spawn hier", "Setzt deinen Wiederbelebungspunkt hierher.", "/spawnpoint @s"),
    _mc("mc_village", "Bewegung & Spaß", "Dorf finden", "Zeigt die Koordinaten des nächsten Ebenen-Dorfs.", "/locate structure minecraft:village_plains"),
    _mc("mc_lightning", "Bewegung & Spaß", "Blitz", "Blitz 5 Blöcke vor dir.", "/execute at @s run summon minecraft:lightning_bolt ^ ^ ^5"),
    _mc("mc_wolf", "Bewegung & Spaß", "Wolf", "Ein Wolf zum Zähmen.", "/summon minecraft:wolf ~ ~ ~"),
    _mc("mc_kill", "Bewegung & Spaß", "Umgebung leeren", "Entfernt alle Wesen im Umkreis von 30 Blöcken – Vorsicht, auch Tiere und Dorfbewohner.",
        "/kill @e[type=!minecraft:player,type=!minecraft:item,distance=..30]"),
]


# ---------------------------------------------------------------- GTA 5 Enhanced (Story-Modus)
def _gta(code, section, title, desc):
    return Cheat("gta_" + code.lower(), section, title, desc, (code,))


GTA = [
    _gta("PAINKILLER", "Spieler", "Unverwundbar", "5 Minuten unverwundbar."),
    _gta("TURTLE", "Spieler", "Leben & Rüstung", "Volles Leben und volle Schutzweste."),
    _gta("TOOLUP", "Spieler", "Alle Waffen", "Waffen und Munition."),
    _gta("POWERUP", "Spieler", "Spezialfähigkeit", "Spezialfähigkeit voll aufladen."),
    _gta("CATCHME", "Spieler", "Schnell rennen", ""),
    _gta("GOTGILLS", "Spieler", "Schnell schwimmen", ""),
    _gta("LIQUOR", "Spieler", "Betrunken", "Torkeln wie nach der Party."),
    _gta("LAWYERUP", "Fahndung", "Fahndung runter", "Ein Stern weniger."),
    _gta("FUGITIVE", "Fahndung", "Fahndung hoch", "Ein Stern mehr."),
    _gta("HIGHEX", "Kampf", "Explosive Munition", ""),
    _gta("INCENDIARY", "Kampf", "Brandmunition", ""),
    _gta("HOTHANDS", "Kampf", "Explosive Fäuste", ""),
    _gta("DEADEYE", "Kampf", "Zeitlupe beim Zielen", "Mehrfach eingeben für stärkere Wirkung."),
    _gta("SLOWMO", "Kampf", "Zeitlupe", "Mehrfach eingeben für stärkere Wirkung."),
    _gta("SKYFALL", "Welt", "Himmelssturz", "Fall aus großer Höhe."),
    _gta("CHUTE", "Welt", "Fallschirm", ""),
    _gta("FLOATER", "Welt", "Mond-Schwerkraft", ""),
    _gta("MAKEITRAIN", "Welt", "Wetter wechseln", ""),
    _gta("SNOWDAY", "Welt", "Rutschige Autos", ""),
    _gta("BUZZOFF", "Fahrzeuge", "Buzzard", "Kampfhubschrauber."),
    _gta("BARNSTORM", "Fahrzeuge", "Stuntflugzeug", ""),
    _gta("FLYSPRAY", "Fahrzeuge", "Duster", "Sprühflugzeug."),
    _gta("COMET", "Fahrzeuge", "Comet", "Sportwagen."),
    _gta("RAPIDGT", "Fahrzeuge", "Rapid GT", "Sportwagen."),
    _gta("VINEWOOD", "Fahrzeuge", "Stretch-Limo", ""),
    _gta("TRASHED", "Fahrzeuge", "Müllwagen", ""),
    _gta("ROCKET", "Fahrzeuge", "PCJ-600", "Motorrad."),
    _gta("OFFROAD", "Fahrzeuge", "Sanchez", "Geländemotorrad."),
    _gta("BANDIT", "Fahrzeuge", "BMX", ""),
    _gta("HOLEIN1", "Fahrzeuge", "Golf-Caddy", ""),
]

GTA_COMBOS = {
    "gta_combo_tank": ("Panzer-Paket", "Unverwundbar + Leben & Rüstung + alle Waffen.", ("PAINKILLER", "TURTLE", "TOOLUP")),
    "gta_combo_chaos": ("Chaos-Paket", "Explosive Munition + explosive Fäuste + Mond-Schwerkraft.", ("HIGHEX", "HOTHANDS", "FLOATER")),
}

ALL = {c.id: c for c in MINECRAFT + GTA}
for _cid, (_t, _d, _codes) in GTA_COMBOS.items():
    ALL[_cid] = Cheat(_cid, "Pakete", _t, _d, _codes)


def sections(cheats) -> dict:
    out = {}
    for c in cheats:
        out.setdefault(c.section, []).append(c)
    return out


def is_gta(cheat_id: str) -> bool:
    return cheat_id.startswith("gta_")


# ---------------------------------------------------------------- Minecraft: Makro bauen
_BAD = re.compile(r"[\"#\r\n]")
CHAT_KEYS = ("t", "enter", "y")


def check_command(cmd: str) -> str:
    """Prüft einen eigenen Befehl. Gibt den bereinigten Befehl zurück oder wirft ValueError."""
    cmd = (cmd or "").strip()
    if not cmd:
        raise ValueError("Please enter a command.")
    if _BAD.search(cmd):
        raise ValueError("Quotation marks (\") and # do not work in the macro language.")
    if len(cmd) > 250:
        raise ValueError("The command is too long (at most 250 characters).")
    return cmd if cmd.startswith("/") else "/" + cmd


def minecraft_script(commands, delay_s: float = 0, chat_key: str = "t") -> str:
    """Erzeugt ein Makro in der JOPML-Makro-Sprache: Chat öffnen, Befehl tippen, Enter – für jeden Befehl."""
    if chat_key not in CHAT_KEYS:
        chat_key = "t"
    lines = ["# Cheat-Menü: Minecraft-Befehle"]
    if delay_s > 0:
        lines.append(f"wait {int(delay_s * 1000)}ms")
    for i, cmd in enumerate(commands):
        cmd = check_command(cmd)
        if i:
            lines.append("wait 250ms")
        lines += [f"key {chat_key}", "wait 200ms", f'type "{cmd}"', "wait 80ms", "key enter"]
    return "\n".join(lines)
