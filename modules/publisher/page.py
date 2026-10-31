import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import cloud, theme, ui
from core.version import APP_VERSION, SUPABASE_URL

from . import logic


class PublisherPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self.files: dict[str, str] = {}
        self.columnconfigure(0, weight=1)
        ui.page_title(self, "Neue Version veröffentlichen",
                      "Nur für dein Admin-Konto sichtbar. Die Dateien gehen in den öffentlichen Supabase-Bereich "
                      "'releases'; danach sehen alle Apps das Update.").grid(row=0, column=0, sticky="w", padx=24, pady=(20, 8))
        self._overview()
        card = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        card.grid(row=2, column=0, sticky="ew", padx=24, pady=6)
        b = ctk.CTkFrame(card, fg_color="transparent")
        b.pack(fill="x", padx=16, pady=14)

        r = ui.row(b)
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text="Versionsnummer", width=150, anchor="w").pack(side="left")
        self.e_ver = ctk.CTkEntry(r, width=140)
        self.e_ver.insert(0, APP_VERSION)
        self.e_ver.pack(side="left")
        ctk.CTkLabel(r, text="  (muss zur gebauten Datei passen; die EXE wird geprüft)", text_color=theme.MUTED).pack(side="left")

        self.lbl = {}
        for ext, label in ((".exe", "Windows (.exe)"), (".dmg", "Mac (.dmg)")):
            rr = ui.row(b)
            rr.pack(fill="x", pady=3)
            ctk.CTkLabel(rr, text=label, width=150, anchor="w").pack(side="left")
            ctk.CTkButton(rr, text="Datei wählen …", width=130, command=lambda e=ext: self.pick(e)).pack(side="left")
            self.lbl[ext] = ctk.CTkLabel(rr, text="  keine Datei", text_color=theme.MUTED, anchor="w")
            self.lbl[ext].pack(side="left", padx=8)

        ctk.CTkLabel(b, text="Was ist neu? (wird den Nutzern angezeigt; die Release-Note schreibt das Programm selbst und hängt diesen Text an)", anchor="w").pack(fill="x", pady=(10, 2))
        self.notes = ctk.CTkTextbox(b, height=90, border_width=1, border_color=("gray70", "gray30"))
        self.notes.pack(fill="x")
        self.status = ctk.CTkLabel(b, text="", anchor="w", justify="left", wraplength=560)
        self.status.pack(fill="x", pady=(10, 0))
        self.btn = ctk.CTkButton(b, text="Hochladen und veröffentlichen", height=40, command=self.publish)
        self.btn.pack(anchor="w", pady=(8, 0))

        vc = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        vc.grid(row=5, column=0, sticky="ew", padx=24, pady=6)
        vb = ctk.CTkFrame(vc, fg_color="transparent")
        vb.pack(fill="x", padx=16, pady=14)
        top = ui.row(vb)
        top.pack(fill="x")
        ctk.CTkLabel(top, text="Wiederherstellen · hochgeladene Versionen", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Liste laden", width=110, command=self.load_versions).pack(side="right")
        ctk.CTkLabel(vb, anchor="w", justify="left", wraplength=560, text_color=theme.MUTED,
                     text="WIEDERHERSTELLEN: Alle .exe- und .dmg-Dateien im Bereich 'releases'. „Aktiv“ ist die Version, die Nutzer gerade angeboten bekommen. "
                          "Mit „Aktiv setzen“ stellst du eine ältere Version zurück, falls die neue fehlerhaft ist. Apps ab Version 1.4.0 "
                          "stellen dann auch von der fehlerhaften Version zurück; ältere Apps bleiben, wo sie sind.").pack(fill="x", pady=(4, 6))
        self.vlist = ctk.CTkFrame(vb, fg_color="transparent")
        self.vlist.pack(fill="x")
        self.vstatus = ctk.CTkLabel(vb, text="", anchor="w", justify="left", wraplength=560)
        self.vstatus.pack(fill="x", pady=(6, 0))
        ac = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        ac.grid(row=3, column=0, sticky="ew", padx=24, pady=6)
        ctk.CTkLabel(ac, text="Recoil Arena veröffentlichen", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(ac, anchor="w", justify="left", wraplength=560, text_color=theme.MUTED,
                     text="Nur für Nutzer ohne EXE (Python-Weg): Die EXE enthält die Arena schon. Packt die mitgelieferte Arena (Quellcode) als ZIP, lädt sie in den Bereich 'releases' und schreibt arena.json. "
                          "Danach können alle im Modul „Recoil Arena“ auf „Download“ drücken.").pack(fill="x", padx=16)
        self.arena_status = ctk.CTkLabel(ac, text="", anchor="w", justify="left", wraplength=560)
        self.arena_status.pack(fill="x", padx=16, pady=(6, 0))
        ctk.CTkButton(ac, text="Arena hochladen", height=36, command=self.publish_arena).pack(anchor="w", padx=16, pady=(6, 14))
        self._module_card()
        self.after(300, self.load_versions)

    def _overview(self):
        """Oben: alles, was hochgeladen werden kann, mit den genauen Kriterien (aus dem Code erzeugt, immer aktuell)."""
        from core import doc_viewer, requirements_doc as rd
        oc = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        oc.grid(row=1, column=0, sticky="ew", padx=24, pady=6)
        top = ui.row(oc)
        top.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(top, text="Das kannst du hochladen", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Als Datei ansehen / speichern", width=200, fg_color=theme.c("hover"), text_color=theme.TEXT,
                      command=lambda: doc_viewer.show(self, "Upload-Übersicht", lambda: rd.uploads_text("de"), "jopml-uploads.txt")).pack(side="right")
        for u in rd.uploads_catalog("de"):
            ctk.CTkLabel(oc, anchor="w", justify="left", wraplength=620, font=ctk.CTkFont(weight="bold"),
                         text=f"{u['name']}   →   {u['where']}").pack(fill="x", padx=16, pady=(6, 0))
            ctk.CTkLabel(oc, anchor="w", justify="left", wraplength=620, text_color=theme.MUTED,
                         text="\n".join("•  " + c for c in u["criteria"])).pack(fill="x", padx=30)
        ctk.CTkLabel(oc, text="", height=6).pack()

    def _module_card(self):
        from core import module_import
        mc = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS, border_width=1, border_color=theme.c("hover"))
        mc.grid(row=4, column=0, sticky="ew", padx=24, pady=6)
        ctk.CTkLabel(mc, text="Modul für alle hochladen", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(mc, anchor="w", justify="left", wraplength=560, text_color=theme.MUTED,
                     text="Wähle ein Modul, das du unter „Modules“ hinzugefügt hast. Als Admin ist es sofort für alle sichtbar (Community > Module). "
                          "Es gelten die Kriterien oben; nur Textdateien, nie Passwörter oder Schlüssel mitschicken.").pack(fill="x", padx=16)
        names = module_import.installed() or ["(keins hinzugefügt)"]
        r = ui.row(mc)
        r.pack(fill="x", padx=16, pady=4)
        self.mod_pick = ctk.CTkOptionMenu(r, values=names, width=200)
        self.mod_pick.pack(side="left")
        self.mod_title = ctk.CTkEntry(r, width=200, placeholder_text="Titel (3–60 Zeichen)")
        self.mod_title.pack(side="left", padx=8)
        self.mod_ver = ctk.CTkEntry(r, width=80, placeholder_text="1.0.0")
        self.mod_ver.pack(side="left")
        self.mod_descr = ctk.CTkEntry(mc, placeholder_text="Beschreibung (bis 500 Zeichen)")
        self.mod_descr.pack(fill="x", padx=16, pady=4)
        self.mod_status = ctk.CTkLabel(mc, text="", anchor="w", justify="left", wraplength=560)
        self.mod_status.pack(fill="x", padx=16)
        ctk.CTkButton(mc, text="Modul hochladen", height=36, command=self.publish_module).pack(anchor="w", padx=16, pady=(6, 14))

    def publish_module(self):
        from modules.community import modshare
        name = self.mod_pick.get()
        try:
            client = self._client()
            if not client.is_admin():
                raise RuntimeError("Dieses Konto ist kein Admin-Konto.")
            files = modshare.collect_installed(name)
            err = modshare.check_for_publish(name, self.mod_title.get(), self.mod_descr.get(), files)
            if err:
                raise RuntimeError(err)
            notes = modshare.risk_notes(files)
            if not messagebox.askyesno("Modul für alle hochladen",
                                       f"{name} wird sofort für ALLE sichtbar.\n\nAuffällige Stellen im Code:\n" + ("\n".join("• " + n for n in notes) or "keine gefunden (keine Garantie)") + "\n\nHochladen?"):
                return
            svc = self.app.plugin_by_id["community"].service()
            if svc is None:
                raise RuntimeError("Community ist nicht verbunden.")
        except Exception as exc:
            self.mod_status.configure(text=str(exc), text_color=theme.DANGER)
            return
        title, descr, ver = self.mod_title.get(), self.mod_descr.get(), self.mod_ver.get().strip() or "1.0.0"
        self.mod_status.configure(text="Lade hoch …", text_color=theme.MUTED)

        def work():
            try:
                res = modshare.ModShareService(svc).publish(name, title, descr, files, ver)
                self.app.call_soon(self._mod_done, f"Fertig: {name} ({res.get('status', 'ok')}).", True)
            except Exception as exc:
                self.app.call_soon(self._mod_done, str(exc), False)
        threading.Thread(target=work, daemon=True).start()

    def _mod_done(self, msg, ok):
        if self.winfo_exists():
            self.mod_status.configure(text=msg, text_color=theme.OK if ok else theme.DANGER)

    def _say(self, text, ok=True):
        if not ok:
            try:
                from core import errors
                code = errors.classify(text, "E-MOD-005")
                self.app.record_error(code, text, "publish")
                text = errors.tag(text, code)
            except Exception:
                pass
        if self.winfo_exists():
            self.status.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def pick(self, ext):
        kind = "*.exe" if ext == ".exe" else "*.dmg"
        path = filedialog.askopenfilename(title="Datei wählen", filetypes=[("Programmdatei", kind)])
        if path:
            self.files[ext] = path
            self.lbl[ext].configure(text="  " + path.replace("\\", "/").rsplit("/", 1)[-1])

    def publish(self):
        try:
            version = logic.check_version(self.e_ver.get())
            if not self.files:
                raise ValueError("Wähle mindestens eine Datei.")
            for p in self.files.values():
                logic.platform_of(p)
            if ".exe" not in self.files and version != APP_VERSION and not messagebox.askyesno(
                    "Nur Mac-Datei",
                    f"Die Nummer einer .dmg-Datei lässt sich nicht prüfen. Du hast {version} eingetragen. Stimmt das genau mit der Version "
                    "überein, die in der Datei gebaut wurde?"):
                return
        except ValueError as exc:
            self._say(str(exc), False)
            return
        notes = self.notes.get("1.0", "end").strip()
        files = dict(self.files)
        self.btn.configure(state="disabled")
        self._say("Die EXE wird geprüft und hochgeladen … bitte warten (das kann eine Minute dauern), das Fenster nicht schließen.")
        client = getattr(self.app.identity, "client", None)

        def work():
            try:
                exe = files.get(".exe")
                exe_v = logic.probe_exe_version(exe) if exe else None
                problem = logic.judge_version(version, APP_VERSION, exe_v, bool(exe))
                if problem:
                    raise RuntimeError(problem)
                url = self._run(client, version, notes, files)
                msg, ok = f"Fertig! Version {version} ist veröffentlicht.\nManifest: {url}" + getattr(self, "note_result", ""), True
            except Exception as exc:
                traceback.print_exc()
                msg, ok = f"Fehler: {exc}", False
            self.app.call_soon(self._done, msg, ok)

        threading.Thread(target=work, daemon=True).start()

    def _run(self, client, version, notes, files) -> str:
        if client is None or not client.configured:
            raise RuntimeError("Dafür musst du mit einem Cloud-Konto angemeldet sein.")
        if not client.is_admin():
            raise RuntimeError("Dieses Konto ist kein Admin-Konto.")
        packages = {}
        for path in files.values():
            plat, template = logic.platform_of(path)
            import os
            size = os.path.getsize(path)
            if size > logic.MAX_BYTES:
                raise RuntimeError(f"Die Datei ist zu groß ({size // 1048576} MB, erlaubt sind 150 MB).")
            name = template.format(v=version)
            with open(path, "rb") as fh:
                data = fh.read()
            client.upload_release(name, data, "application/octet-stream", cache_seconds=3600)
            packages[plat] = {"url": client.public_release_url(name), "sha256": logic.sha256_file(path)}
        current = client.read_manifest()
        manifest = logic.build_manifest(current, version, notes, packages)
        client.upload_release("version.json", cloud.json_bytes(manifest), "application/json", cache_seconds=30)
        self.note_result = ""
        try:                                           # Release-Note selbst schreiben und in Community > News eintragen (Fehler hier lassen den Upload gültig)
            from core import release_notes
            release_notes.post(client, version, notes)
            self.note_result = "\nRelease-Note wurde in Community > News eingetragen."
        except Exception as exc:
            self.note_result = f"\nHinweis: Die Release-Note konnte nicht in Community > News eingetragen werden ({exc}). Der Upload selbst ist fertig."
        return client.public_release_url("version.json")

    def publish_arena(self):
        self.arena_status.configure(text="Lade hoch …", text_color=theme.MUTED)

        def work():
            try:
                self.app.call_soon(self._arena_done, self._run_arena(self._client()), True)
            except Exception as exc:
                self.app.call_soon(self._arena_done, str(exc), False)
        threading.Thread(target=work, daemon=True).start()

    def _run_arena(self, client) -> str:
        import hashlib
        import tempfile
        from modules.arena import plugin as AP
        if not client.is_admin():
            raise RuntimeError("Dieses Konto ist kein Admin-Konto.")
        version = AP.bundled_version()
        if not version:
            raise RuntimeError("Die Arena-Quellen gehören nicht zu dieser Programmfassung.")
        tmp = tempfile.mkdtemp(prefix="jopml_arena_pub_")
        zpath = tmp + "/arena.zip"
        AP.Plugin.export_zip(AP.Plugin.__new__(AP.Plugin), zpath)
        data = open(zpath, "rb").read()
        name = f"jopml-arena-{version}.zip"
        client.upload_release(name, data, "application/zip", cache_seconds=3600)
        manifest = {"version": version, "url": client.public_release_url(name), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        client.upload_release("arena.json", cloud.json_bytes(manifest), "application/json", cache_seconds=30)
        return f"Arena {version} veröffentlicht ({len(data) // 1024} KB)."

    def _arena_done(self, msg, ok):
        if self.winfo_exists():
            self.arena_status.configure(text=msg, text_color=theme.OK if ok else theme.DANGER)

    def _done(self, msg, ok):
        if not self.winfo_exists():
            return
        self.btn.configure(state="normal")
        self._say(msg, ok)

    # ---------- Versionsliste / Zurückstellen
    def _vsay(self, text, ok=True):
        if self.winfo_exists():
            self.vstatus.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _client(self):
        client = getattr(self.app.identity, "client", None)
        if client is None or not client.configured:
            raise RuntimeError("Dafür musst du mit einem Cloud-Konto angemeldet sein.")
        return client

    def load_versions(self):
        try:
            client = self._client()
        except RuntimeError as exc:
            self._vsay(str(exc), False)
            return
        self._vsay("Liste wird geladen …")

        def work():
            try:
                self.app.call_soon(self._show_versions, self._all_entries(client))
            except Exception as exc:
                self.app.call_soon(self._vsay, f"Fehler: {exc}", False)
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _all_entries(client, manifest=None, arena=None):
        objs = client.list_releases()
        return (logic.release_entries(objs, manifest if manifest is not None else client.read_manifest())
                + logic.arena_entries(objs, arena if arena is not None else client.read_manifest("arena.json")))

    def _show_versions(self, entries):
        if not self.winfo_exists():
            return
        for w in self.vlist.winfo_children():
            w.destroy()
        names = {"windows": "Windows", "macos": "Mac", "arena": "Arena"}
        for e in entries:
            r = ui.row(self.vlist)
            r.pack(fill="x", pady=2)
            size = f"{e['size'] / 1048576:.0f} MB" if e["size"] else "?"
            ctk.CTkLabel(r, anchor="w", width=330, text=f"{names[e['platform']]}  ·  {e['version']}  ·  {size}  ·  {e['date']}  ·  {e['name']}").pack(side="left")
            if e["active"]:
                ctk.CTkLabel(r, text="AKTIV", text_color=theme.OK, width=70).pack(side="left")
            else:
                ctk.CTkButton(r, text="Aktiv setzen", width=100, command=lambda x=e: self.activate(x)).pack(side="left", padx=(0, 4))
                ctk.CTkButton(r, text="Löschen", width=70, fg_color=theme.DANGER, hover_color="#b3363a", command=lambda x=e: self.remove(x)).pack(side="left")
        self._vsay("" if entries else "Keine Versionsdateien gefunden.")

    def activate(self, e):
        if not messagebox.askyesno("Version aktiv setzen", f"{e['name']} für alle {e['platform']}-Nutzer als aktuelle Version anbieten?"):
            return
        try:
            client = self._client()
        except RuntimeError as exc:
            self._vsay(str(exc), False)
            return
        self._vsay("Prüfsumme wird berechnet und Manifest geschrieben … bitte warten.")

        def work():
            try:
                sha = client.release_sha256(e["name"])
                if e["platform"] == "arena":
                    am = logic.arena_manifest(e["version"], client.public_release_url(e["name"]), sha, e["size"])
                    client.upload_release("arena.json", cloud.json_bytes(am), "application/json", cache_seconds=30)
                    self.app.call_soon(self._show_versions, self._all_entries(client, arena=am))
                    self.app.call_soon(self._vsay, f"Fertig: {e['name']} ist jetzt die angebotene Arena.", True)
                    return
                manifest = logic.activate_manifest(client.read_manifest(), e["platform"], e["version"],
                                                   client.public_release_url(e["name"]), sha, f"Zurückgestellt auf Version {e['version']}.")
                client.upload_release("version.json", cloud.json_bytes(manifest), "application/json", cache_seconds=30)
                self.app.call_soon(self._show_versions, self._all_entries(client, manifest=manifest))
                self.app.call_soon(self._vsay, f"Fertig: {e['name']} ist jetzt aktiv.", True)
            except Exception as exc:
                self.app.call_soon(self._vsay, f"Fehler: {exc}", False)
        threading.Thread(target=work, daemon=True).start()

    def remove(self, e):
        if not messagebox.askyesno("Datei löschen", f"{e['name']} endgültig aus dem Bereich 'releases' löschen?"):
            return
        try:
            client = self._client()
        except RuntimeError as exc:
            self._vsay(str(exc), False)
            return

        def work():
            try:
                if any(x["active"] and x["name"] == e["name"] for x in self._all_entries(client)):
                    raise RuntimeError("Diese Version ist gerade aktiv. Setze zuerst eine andere aktiv.")
                client.delete_release(e["name"])
                self.app.call_soon(self._show_versions, self._all_entries(client))
                self.app.call_soon(self._vsay, f"{e['name']} gelöscht.", True)
            except Exception as exc:
                self.app.call_soon(self._vsay, f"Fehler: {exc}", False)
        threading.Thread(target=work, daemon=True).start()
