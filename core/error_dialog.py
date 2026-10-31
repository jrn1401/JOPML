"""Fehlerfenster mit Fehlercode und den Knöpfen "Ask AI" (KI erklärt den Fehler) und "Report" (an den Betreiber melden), plus das Melden-Fenster."""
import threading

import customtkinter as ctk

from core import errors, theme
from core.i18n import tr

CATEGORIES = {
    "bug": "Bug / something does not work",
    "module": "Module upload or import problem",
    "idea": "Idea or wish",
    "other": "Something else",
}


def show_error(app, title: str, message: str, code: str | None = None, parent=None, auto_report: bool = True) -> None:
    """Zeigt den Fehler (mit Code) und meldet ihn – wenn der Nutzer Diagnose erlaubt hat – automatisch."""
    code = code if errors.known(code) else errors.classify(message)
    if auto_report:
        try:
            app.record_error(code, message, "error")
        except Exception:
            pass
    top = ctk.CTkToplevel(parent or app)
    top.title(title)
    top.geometry("520x400")
    top.transient(parent or app)
    top.after(150, top.focus_force)
    ctk.CTkLabel(top, text="⚠  " + title, font=ctk.CTkFont(size=18, weight="bold"), anchor="w").pack(fill="x", padx=20, pady=(16, 4))
    ctk.CTkLabel(top, text=str(message)[:900], wraplength=470, justify="left", anchor="w").pack(fill="x", padx=20)
    ctk.CTkLabel(top, text=tr("Error code: {c} – {d}", c=code, d=tr(errors.describe(code))), text_color=theme.MUTED, wraplength=470,
                 justify="left", anchor="w").pack(fill="x", padx=20, pady=(8, 0))
    ctk.CTkLabel(top, text="💡 " + tr(errors.solution(code)), text_color=theme.TEXT, wraplength=470, justify="left", anchor="w").pack(fill="x", padx=20, pady=(8, 0))
    ctk.CTkLabel(top, text=tr("The AI explains errors; it can be wrong. Your message text is sent to the AI only when you press 'Ask AI'."),
                 text_color=theme.MUTED, wraplength=470, justify="left", anchor="w").pack(fill="x", padx=20, pady=(8, 0))
    row = ctk.CTkFrame(top, fg_color="transparent")
    row.pack(side="bottom", pady=16)

    def ask():
        top.destroy()
        app.ask_ai(errors.explain_prompt(code, message), "Explain an error")

    def report():
        top.destroy()
        open_report(app, code, message)
    def catalog():
        top.destroy()
        app.show("errorcodes")
        page = app.pages.get("errorcodes")
        if page is not None and hasattr(page, "focus_code"):
            page.focus_code(code)
    ctk.CTkButton(row, text="🤖  " + tr("Ask AI"), width=110, command=ask).pack(side="left", padx=4)
    ctk.CTkButton(row, text="📖  " + tr("All codes"), width=110, fg_color=theme.c("hover"), text_color=theme.TEXT, command=catalog).pack(side="left", padx=4)
    ctk.CTkButton(row, text="🚩  " + tr("Report"), width=100, fg_color=theme.c("hover"), text_color=theme.TEXT, command=report).pack(side="left", padx=4)
    ctk.CTkButton(row, text=tr("OK"), width=70, fg_color=theme.c("hover"), text_color=theme.TEXT, command=top.destroy).pack(side="left", padx=4)


def open_report(app, code: str | None = None, text: str = "", category: str = "bug") -> None:
    """Fenster "Report": Nutzer beschreibt ein Problem oder eine Idee; geht an den Admin-Bereich (Reiter "User reports")."""
    top = ctk.CTkToplevel(app)
    top.title(tr("Report a problem or idea"))
    top.geometry("540x540")
    top.transient(app)
    top.after(150, top.focus_force)
    ctk.CTkLabel(top, text="🚩  " + tr("Report a problem or idea"), font=ctk.CTkFont(size=18, weight="bold"), anchor="w").pack(fill="x", padx=20, pady=(16, 4))
    ctk.CTkLabel(top, text=tr("Your report is stored on our server and read by the operator. Do not write passwords or personal data. "
                              "Sent along: category, your text, error code, app version and operating system."),
                 text_color=theme.MUTED, wraplength=490, justify="left", anchor="w").pack(fill="x", padx=20)
    names = {tr(v): k for k, v in CATEGORIES.items()}
    cat = ctk.CTkOptionMenu(top, values=list(names), width=300)
    cat.set(tr(CATEGORIES.get(category, CATEGORIES["bug"])))
    cat.pack(anchor="w", padx=20, pady=8)
    box = ctk.CTkTextbox(top, height=200, wrap="word")
    box.pack(fill="both", expand=True, padx=20)
    if text:
        box.insert("1.0", errors.explain_prompt(code, text).split("\nExplain")[0])
    info = ctk.CTkLabel(top, text=(tr("Error code: {c}", c=code) if code else ""), text_color=theme.MUTED, anchor="w", wraplength=490, justify="left")
    info.pack(fill="x", padx=20, pady=(4, 0))
    ctx_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(top, text=tr("Also send the page I was on and the last pages I visited (names only, no inputs)"), variable=ctx_var).pack(anchor="w", padx=20, pady=(6, 0))
    send_btn = ctk.CTkButton(top, text=tr("Send report"), width=160)
    send_btn.pack(pady=(10, 4))
    ctk.CTkButton(top, text="📬  " + tr("My reports"), width=160, fg_color=theme.c("hover"), text_color=theme.TEXT, command=lambda: my_reports(app, top)).pack(pady=(0, 10))

    def done(err):
        if not top.winfo_exists():
            return
        send_btn.configure(state="normal")
        if err:
            info.configure(text=err, text_color=theme.DANGER)
        else:
            info.configure(text=tr("Thank you! The report was sent."), text_color=theme.OK)
            top.after(1200, top.destroy)

    def send():
        msg = box.get("1.0", "end").strip()
        if len(msg) < 5:
            info.configure(text=tr("Please describe the problem in a few words."), text_color=theme.DANGER)
            return
        send_btn.configure(state="disabled")
        k = names.get(cat.get(), "bug")
        with_ctx = bool(ctx_var.get())

        def work():
            try:
                app.telemetry.report_user(k, msg, code, with_context=with_ctx)
                app.call_soon(done, None)
            except Exception as exc:
                low = str(exc).lower()
                text = (tr("You can send at most 10 reports per day.") if "rate_limited" in low
                        else tr("The report could not be sent: {e}", e=str(exc)[:200]) + " [E-REP-001]")
                app.call_soon(done, text)
        threading.Thread(target=work, daemon=True).start()
    send_btn.configure(command=send)


STATUS_TEXT = {"new": "Received", "in_progress": "We are working on it", "fixed": "Fixed"}


def my_reports(app, parent=None, then=None):
    """Meine Meldungen: Status (Ticket) und Antworten des Betreibers; öffnen markiert Antworten als gelesen."""
    top = ctk.CTkToplevel(parent or app)
    top.title(tr("My reports"))
    top.geometry("560x520")
    top.transient(parent or app)
    ctk.CTkLabel(top, text="📬  " + tr("My reports"), font=ctk.CTkFont(size=18, weight="bold"), anchor="w").pack(fill="x", padx=20, pady=(16, 4))
    info = ctk.CTkLabel(top, text=tr("Loading …"), text_color=theme.MUTED, anchor="w")
    info.pack(fill="x", padx=20)
    lst = ctk.CTkScrollableFrame(top, fg_color=theme.c("card"), corner_radius=theme.CARD_RADIUS)
    lst.pack(fill="both", expand=True, padx=20, pady=10)

    def show(rows, err):
        if not top.winfo_exists():
            return
        if err:
            info.configure(text=tr("Your reports could not be loaded: {e}", e=err[:160]) + " [E-REP-001]", text_color=theme.DANGER)
            return
        info.configure(text=tr("{n} reports (newest first).", n=len(rows)) if rows else tr("You have not sent a report yet."))
        for r in rows:
            card = ctk.CTkFrame(lst, fg_color=theme.c("inset"), corner_radius=10)
            card.pack(fill="x", pady=3, padx=4)
            st = r.get("status")
            head = f"{str(r.get('created_at') or '')[:10]}  ·  {r.get('code') or '–'}  ·  " + (tr(STATUS_TEXT[st]) if st in STATUS_TEXT else tr("Received"))
            ctk.CTkLabel(card, text=head, anchor="w", text_color=theme.OK if st == "fixed" else theme.MUTED).pack(fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(card, text=str(r.get("message") or "")[:300], anchor="w", justify="left", wraplength=480).pack(fill="x", padx=10)
            if r.get("reply"):
                ctk.CTkLabel(card, text="↩ " + tr("Answer from the operator") + ":\n" + str(r["reply"]), anchor="w", justify="left", wraplength=480,
                             text_color=theme.accent()).pack(fill="x", padx=10, pady=(2, 6))
        if any(r.get("reply") and not r.get("reply_seen") for r in rows):
            threading.Thread(target=lambda: _quiet(app.telemetry.reports_seen), daemon=True).start()
            if then:
                then()

    def work():
        try:
            rows, err = app.telemetry.my_reports(), None
        except Exception as exc:
            rows, err = [], str(exc)
        app.call_soon(show, rows, err)
    threading.Thread(target=work, daemon=True).start()
    return top


def _quiet(fn):
    try:
        fn()
    except Exception:
        pass


def unseen_replies(app) -> int:
    """Anzahl neuer, ungelesener Antworten des Betreibers (blockierend, im Thread aufrufen; 0 bei Fehler)."""
    try:
        return sum(1 for r in app.telemetry.my_reports() if r.get("reply") and not r.get("reply_seen"))
    except Exception:
        return 0
