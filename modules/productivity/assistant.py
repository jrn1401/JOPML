"""KI-Makro-Assistent: Gespräch, in dem aus Beschreibungen (und späteren Änderungswünschen) ein Makro entsteht."""
from core.i18n import tr
from modules.macros import dsl, generator

MAX_TURNS = 8


class Conversation:
    """history: abwechselnd user/assistant (nur gültige Skripte als assistant). ask(messages) -> KI-Antwort."""

    def __init__(self, ask=None):
        self.ask = ask
        self.history: list[dict] = []
        self.script = ""

    def reset(self):
        self.history, self.script = [], ""

    def send(self, text: str) -> tuple[str, str]:
        """Gibt (Skript, Quelle) zurück. Wirft generator.GenerateError mit anzeigbarem Text."""
        text = (text or "").strip()
        if len(text) < 3:
            raise generator.GenerateError(tr("Please describe what the macro should do."))
        if len(text) > 1000:
            raise generator.GenerateError(tr("The description is too long (max. 1000 characters)."))
        if not self.history:
            script, source = generator.generate(text, self.ask)
        else:
            if self.ask is None:
                raise generator.GenerateError(tr("Changes need the AI (cloud account)."))
            script, source = self._refine(text), "ai"
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": script}]
        del self.history[:-2 * MAX_TURNS]
        self.script = script
        return script, source

    def _refine(self, text: str) -> str:
        msgs = self.history + [{"role": "user", "content": f"Change the macro above as follows and return the complete new script only: {text}"}]
        last = ""
        for _ in range(2):
            try:
                reply = self.ask(msgs)
            except Exception as exc:
                raise generator.GenerateError(str(exc)) from None
            script = dsl.extract_script(reply)
            try:
                dsl.parse(script)
                return script
            except dsl.MacroError as exc:
                last = str(exc)
                msgs = msgs + [{"role": "assistant", "content": reply},
                               {"role": "user", "content": f"Invalid: {exc.message}. Return only the corrected script."}]
        raise generator.GenerateError(tr("The AI did not produce a valid macro ({err}). Please rephrase.", err=last))
