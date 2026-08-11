"""
Language names arrive as free text, so canonicalize_language() is what keeps one
language from being counted as two.
"""

from last_translation_benchmark.languages import (
    LANGUAGE_ALIASES,
    LANGUAGES,
    canonicalize_language,
)


def test_canonical_names_are_unique():
    names = [x["name"] for x in LANGUAGES]
    assert len(names) == len(set(names))


def test_aliases_do_not_shadow_a_canonical_name():
    canonical = {x["name"].lower() for x in LANGUAGES}
    assert not (set(LANGUAGE_ALIASES) & canonical)


def test_endonyms_and_other_names_resolve():
    assert canonicalize_language("Farsi") == "Persian"
    assert canonicalize_language("farsi") == "Persian"
    assert canonicalize_language("Bangla") == "Bengali"
    assert canonicalize_language("Odia (Oriya)") == "Odia"


def test_spacing_width_and_invisible_characters_are_repaired():
    assert canonicalize_language("Spanish(colombia)") == "Spanish (Colombia)"
    assert canonicalize_language("Romanian(Moldova)") == "Romanian (Moldova)"
    assert canonicalize_language("English‎") == "English"
    assert canonicalize_language("  German  ") == "German"
    assert (
        canonicalize_language("Chinese （Lanzhou Dialect）")
        == "Chinese (Lanzhou dialect)"
    )


def test_dialect_spellings_collapse_to_one():
    for name in ["Arabic Algerian", "Algerian Arabic", "Algerian (Arabic)"]:
        assert canonicalize_language(name) == "Arabic (Algerian)"
    assert canonicalize_language("Neapolitan") == "Italian (Neapolitan)"
    assert canonicalize_language("German (Bern)") == "Swiss German (Bern)"


def test_an_unknown_variety_is_left_alone():
    assert canonicalize_language("Pnar") == "Pnar"
    assert canonicalize_language("Chinese (Hunanese, Yueyang)") == (
        "Chinese (Hunanese, Yueyang)"
    )
    # separate languages that only look related
    assert canonicalize_language("Dari") == "Dari"
    assert canonicalize_language("Tajik") == "Tajik"
    assert canonicalize_language("Gilaki") == "Gilaki"
    assert canonicalize_language("Old Persian") == "Old Persian"
