"""Findet und lädt Module aus dem Paket `modules`."""
import importlib
import pkgutil
import traceback


def _module_names() -> list[str]:
    import modules

    names = list(getattr(modules, "BUILTIN_MODULES", []))
    try:  # automatische Suche (funktioniert im Quellcode-Betrieb zuverlässig)
        for info in pkgutil.iter_modules(modules.__path__):
            if info.ispkg and info.name not in names:
                names.append(info.name)
    except Exception:
        traceback.print_exc()
    return names


def _user_names() -> list[str]:
    """Importierte Module (Einstellungen > System > Module importieren). Ein Modul mit dem Namen eines eingebauten wird nie geladen."""
    try:
        from core import module_import
        root = module_import.user_dir()
        builtin = module_import.builtin_names()
        names = [n for n in module_import.installed(root) if n not in builtin and n not in module_import.RESERVED]
        if names:
            import sys
            import types
            pkg = sys.modules.get("jopml_user")
            if pkg is None:
                pkg = types.ModuleType("jopml_user")
                pkg.__path__ = [str(root)]
                sys.modules["jopml_user"] = pkg
        return names
    except Exception:
        traceback.print_exc()
        return []


def discover(app):
    """Gibt (plugins, failed) zurück. failed = [(modulname, fehlertext)]."""
    plugins, failed = [], []
    user_plugins = []
    for name in _user_names():
        try:
            mod = importlib.import_module(f"jopml_user.{name}.plugin")
            plugin = mod.Plugin(app)
            plugin.user_module = True
            user_plugins.append((name, plugin))
        except Exception as exc:
            traceback.print_exc()
            failed.append((name, f"{type(exc).__name__}: {exc}"))
    for name in _module_names():
        try:
            mod = importlib.import_module(f"modules.{name}.plugin")
            plugins.append(mod.Plugin(app))
        except Exception as exc:  # ein kaputtes Modul darf den Launcher nicht stoppen
            traceback.print_exc()
            failed.append((name, f"{type(exc).__name__}: {exc}"))
    taken = {p.id for p in plugins} | {"dashboard", "settings", "assistant", "contact"}
    for name, plugin in user_plugins:           # importierte Module dürfen kein eingebautes Modul ersetzen
        if getattr(plugin, "id", None) in taken or not isinstance(getattr(plugin, "id", None), str):
            failed.append((name, "The module id is already in use."))
            continue
        taken.add(plugin.id)
        plugins.append(plugin)
    plugins.sort(key=lambda p: (p.order, p.name))
    return plugins, failed
