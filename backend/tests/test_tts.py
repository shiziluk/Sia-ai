import json
import threading
import time

import httpx

from app.services import tts


def _manifest_entry(audio, text="prompt"):
    return {"audio": str(audio), "text": text, "style": "test"}


def test_load_ref_manifest_reads_tiers_and_skips_missing_audio(tmp_path):
    audio = tmp_path / "ref.wav"
    audio.write_bytes(b"wav")
    missing = tmp_path / "missing.wav"
    manifest = {
        "version": 1,
        "tiers": {"low": {"speed": 0.9, "top_p": 0.6, "temperature": 0.5}},
        "refs": {
            "zh": {
                "low": [_manifest_entry(audio), _manifest_entry(missing)],
                "mid": [],
            },
            "ja": {"low": [_manifest_entry(audio, "日本語")]},
        },
    }
    path = tmp_path / "voice_refs.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    parsed = tts._load_ref_manifest(str(path), path.stat().st_mtime_ns)

    assert len(parsed.refs[(tts.VoiceLang.ZH, tts.VoiceTier.LOW)]) == 1
    assert parsed.refs[(tts.VoiceLang.ZH, tts.VoiceTier.LOW)][0].audio == audio
    assert (tts.VoiceLang.ZH, tts.VoiceTier.MID) not in parsed.refs
    assert parsed.tunes[tts.VoiceTier.LOW].temperature == 0.5


def test_pick_ref_is_stable_for_same_text(tmp_path, monkeypatch):
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    manifest = tts.RefManifest(
        refs={
            (tts.VoiceLang.ZH, tts.VoiceTier.MID): (
                tts.RefSample(first, "a"),
                tts.RefSample(second, "b"),
            )
        },
        tunes=dict(tts._DEFAULT_TUNES),
    )
    monkeypatch.setattr(tts, "load_ref_manifest", lambda: manifest)

    one = tts.pick_ref(tts.VoiceTier.MID, tts.VoiceLang.ZH, "same text")
    two = tts.pick_ref(tts.VoiceTier.MID, tts.VoiceLang.ZH, "same text")

    assert one == two


def test_gpt_sovits_uses_actual_api_v2_contract(tmp_path, monkeypatch):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/tts":
            return httpx.Response(
                200,
                content=b"WAV",
                headers={"content-type": "audio/wav"},
            )
        return httpx.Response(200, json={"message": "ok"})

    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"ref")
    gpt_weight = tmp_path / "gpt.ckpt"
    gpt_weight.write_bytes(b"gpt")
    sovits_weight = tmp_path / "sovits.pth"
    sovits_weight.write_bytes(b"sovits")
    backend = tts.GptSovitsBackend(
        base_url="http://api-v2.test",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(backend, "_to_mp3", lambda wav: b"MP3:" + wav)

    result = backend.synthesize(
        text="你好",
        lang=tts.VoiceLang.ZH,
        ref=tts.RefSample(ref_audio, "プロンプト", prompt_lang="ja"),
        gpt_weight=gpt_weight,
        sovits_weight=sovits_weight,
        tune=tts.VoiceTune(speed=1.2, top_p=0.8, temperature=0.9),
    )

    assert result == b"MP3:WAV"
    assert [request.method for request in requests] == ["GET", "GET", "POST"]
    assert requests[0].url.path == "/set_gpt_weights"
    assert requests[1].url.path == "/set_sovits_weights"
    payload = json.loads(requests[2].content)
    assert payload["prompt_text"] == "プロンプト"
    assert payload["text_lang"] == "zh"
    assert payload["prompt_lang"] == "ja"
    assert payload["speed_factor"] == 1.2
    assert "ref_text" not in payload
    assert "speed" not in payload


def test_weight_switch_and_synthesis_are_serialized(tmp_path):
    active = 0
    max_active = 0
    guard = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        with guard:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.02)
        with guard:
            active -= 1
        if request.url.path == "/tts":
            return httpx.Response(
                200,
                content=b"WAV",
                headers={"content-type": "audio/wav"},
            )
        return httpx.Response(200, json={"message": "ok"})

    ref = tts.RefSample(tmp_path / "ref.wav", "prompt")
    gpt = tmp_path / "gpt.ckpt"
    sovits = tmp_path / "sovits.pth"
    backend = tts.GptSovitsBackend(
        base_url="http://api-v2.test",
        transport=httpx.MockTransport(handler),
    )
    backend._to_mp3 = lambda wav: b"MP3"

    threads = [
        threading.Thread(
            target=lambda: backend.synthesize(
                text="text",
                lang=tts.VoiceLang.ZH,
                ref=ref,
                gpt_weight=gpt,
                sovits_weight=sovits,
                tune=tts.VoiceTune(),
            )
        )
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert max_active == 1


def test_synthesize_speech_reports_edge_fallback(tmp_path, monkeypatch):
    ref = tts.RefSample(tmp_path / "ref.wav", "prompt")
    manifest = tts.RefManifest(
        refs={(tts.VoiceLang.ZH, tts.VoiceTier.LOW): (ref,)},
        tunes=dict(tts._DEFAULT_TUNES),
    )
    monkeypatch.setattr(tts, "load_ref_manifest", lambda: manifest)
    monkeypatch.setattr(tts.settings, "tts_backend", "gpt_sovits")
    monkeypatch.setattr(tts, "_weights_for", lambda lang: (tmp_path / "g.ckpt", tmp_path / "s.pth"))
    monkeypatch.setattr(
        tts.GptSovitsBackend,
        "synthesize",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(
        tts.EdgeTtsBackend,
        "synthesize",
        lambda *args, **kwargs: b"EDGE",
    )

    result = tts.synthesize_speech("text", intimacy_level=1, lang="zh")

    assert result.audio == b"EDGE"
    assert result.backend == "edge"
