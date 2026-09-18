from __future__ import annotations

import json
import locale
import os
import sys
from pathlib import Path

FALLBACK = "en"


def _lang_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "lang"
    return Path(__file__).resolve().parent / "lang"


def detect_language() -> str:
    candidates = [
        locale.getlocale()[0],
        locale.getdefaultlocale()[0] if hasattr(locale, "getdefaultlocale") else None,
        os.environ.get("LANG"),
        os.environ.get("LC_ALL"),
        os.environ.get("LANGUAGE"),
    ]
    for value in candidates:
        if not value:
            continue
        lowered = value.replace("-", "_").lower()
        if lowered.startswith("it") or "italian" in lowered:
            return "it"
    return FALLBACK


def _load_json(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in data.items()}


class Translator:
    def __init__(self) -> None:
        folder = _lang_dir()
        self.fallback = _load_json(folder / f"{FALLBACK}.json")
        self.language = detect_language()
        overlay = (
            _load_json(folder / f"{self.language}.json")
            if self.language != FALLBACK
            else {}
        )
        self.strings = {**self.fallback, **overlay}

    def t(self, key: str, **kwargs: object) -> str:
        text = self.strings.get(key) or self.fallback.get(key) or key
        if kwargs:
            return text.format(**kwargs)
        return text


_translator = Translator()
language = _translator.language


def t(key: str, **kwargs: object) -> str:
    return _translator.t(key, **kwargs)
