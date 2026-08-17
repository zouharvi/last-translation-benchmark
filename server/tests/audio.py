"""
Audio input handling for audio-capable models such as openai/gpt-audio.
"""

from last_translation_benchmark.routers import MODEL_LIBRARY
from last_translation_benchmark.services import audio_format_from_mime


def test_audio_format_from_mime():
    # browsers report .mp3 uploads as audio/mpeg and .wav under several aliases,
    # but OpenAI-served models only accept "mp3" and "wav"
    assert audio_format_from_mime("audio/mpeg") == "mp3"
    assert audio_format_from_mime("audio/mp3") == "mp3"
    assert audio_format_from_mime("audio/wav") == "wav"
    assert audio_format_from_mime("audio/x-wav") == "wav"
    assert audio_format_from_mime("audio/wave") == "wav"
    assert audio_format_from_mime("audio/vnd.wave") == "wav"

    # casing and stray whitespace from the data URL header
    assert audio_format_from_mime("AUDIO/MPEG") == "mp3"
    assert audio_format_from_mime(" audio/wav ") == "wav"

    # unknown types fall back to the subtype
    assert audio_format_from_mime("audio/ogg") == "ogg"
    assert audio_format_from_mime("audio/flac") == "flac"


def test_gpt_audio_is_registered():
    gpt_audio = [m for m in MODEL_LIBRARY if m["name"] == "GPT Audio"]
    assert len(gpt_audio) == 1

    # gpt-audio takes audio (and text) but no image or video
    assert gpt_audio[0]["support_audio"]
    assert not gpt_audio[0]["support_image"]
    assert not gpt_audio[0]["support_video"]
    assert not gpt_audio[0]["support_textonly"]
