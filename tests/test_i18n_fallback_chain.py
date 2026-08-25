import gettext

import src.i18n as i18n


class _FakeTranslation(gettext.NullTranslations):
    def __init__(self, messages: dict[str, str]):
        super().__init__()
        self._messages = messages

    def gettext(self, message: str) -> str:
        if message in self._messages:
            return self._messages[message]
        return super().gettext(message)


def test_pt_br_translation_chain_uses_english_before_exposing_msgid(monkeypatch):
    catalogs = {
        ("pt-BR", "messages"): {"translated": "Traduzido"},
        ("pt-BR", "game_configs"): {"race": "Humano"},
        ("en-US", "messages"): {"missing_in_pt": "Readable English"},
        ("en-US", "game_configs"): {"config_missing_in_pt": "Readable config"},
    }

    def fake_translation(domain, *, localedir, languages):
        messages = catalogs.get((languages[0], domain))
        if messages is None:
            raise FileNotFoundError
        return _FakeTranslation(messages)

    monkeypatch.setattr(i18n.gettext, "translation", fake_translation)

    translation = i18n._load_translation_chain("pt-BR")

    assert translation is not None
    assert translation.gettext("translated") == "Traduzido"
    assert translation.gettext("race") == "Humano"
    assert translation.gettext("missing_in_pt") == "Readable English"
    assert translation.gettext("config_missing_in_pt") == "Readable config"
    assert translation.gettext("unknown_key") == "unknown_key"
