"""API 集成测试：TestClient 全链路（chat / context / history / diary / persona / memories / voice / providers）。"""
from datetime import datetime

import httpx
import pytest

from app.core.config import settings
from app.providers.llm import LLMError, LLMProvider, OllamaProvider, QwenProvider, get_llm
from app.services import weather


# =====================================================================
# 健康检查
# =====================================================================
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["llm"]["channel"] == settings.llm_channel
    assert data["llm"]["active_provider"] == "mock"  # 测试注入的 Provider


# =====================================================================
# 会话上下文
# =====================================================================
def test_context_fresh(client):
    resp = client.get("/api/chat/context")
    assert resp.status_code == 200
    data = resp.json()
    assert "希亚" in data["welcome"]  # 空库 → 陌生人欢迎语
    assert data["state"]["trust"] == 0
    assert data["state"]["intimacy_label"] == "陌生人"
    assert data["is_thunderstorm"] is False
    assert data["notify_thunder"] is False
    assert data["notify_birthday_eve"] is False
    assert isinstance(data["days_to_birthday"], int)


# =====================================================================
# 对话主链路
# =====================================================================
def test_chat_round(client):
    resp = client.post("/api/chat", json={"text": "你好"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "哼，知道了啦。"
    assert data["emotion"] == "开心"
    assert data["saved_memory"] is None
    assert data["state"]["trust"] == 3  # +1 基础 +2 开心

    # 历史落库
    hist = client.get("/api/chat/history").json()
    assert [h["role"] for h in hist] == ["user", "assistant"]

    # 有历史后 context 不再返回欢迎语
    ctx = client.get("/api/chat/context").json()
    assert ctx["welcome"] == ""


def test_chat_confession_trust(client):
    data = client.post("/api/chat", json={"text": "我喜欢你"}).json()
    assert data["state"]["trust"] == 8  # +1 +5 表白 +2 开心


def test_chat_blank_text_400(client):
    resp = client.post("/api/chat", json={"text": "   "})
    assert resp.status_code == 400


def test_chat_empty_text_422(client):
    resp = client.post("/api/chat", json={"text": ""})
    assert resp.status_code == 422  # Pydantic min_length=1


def test_chat_critique_switch(client, mock_llm):
    # enable_critique=False 时不发起人格审查调用
    client.post("/api/chat", json={"text": "你好", "enable_critique": False})
    critique_calls = [c for c in mock_llm.calls if "人格审查员" in c[0]["content"]]
    assert critique_calls == []


def test_chat_llm_error_502(client, monkeypatch):
    from app.providers.llm import LLMError as _LLMError

    def boom(*a, **k):
        raise _LLMError("通道全挂")

    monkeypatch.setattr("app.services.chat.process_message", boom)
    resp = client.post("/api/chat", json={"text": "你好"})
    assert resp.status_code == 502


# =====================================================================
# 记忆库接口
# =====================================================================
def test_memories_add_and_list(client):
    resp = client.post("/api/memories", json={"text": "小叶讨厌打雷"})
    assert resp.status_code == 200
    data = client.get("/api/memories").json()
    assert data["count"] == 1
    assert data["items"] == ["小叶讨厌打雷"]


def test_chat_saves_memory_flow(client):
    # MockProvider：含"生日"关键词 → 判定 yes；提取走默认回复
    data = client.post("/api/chat", json={"text": "我的生日是4月6日"}).json()
    assert data["saved_memory"] is not None
    mem = client.get("/api/memories").json()
    assert mem["count"] == 1
    # 日记里能看到沉淀的事实
    today = datetime.now().strftime("%Y-%m-%d")
    diary = client.get(f"/api/chat/diary/{today}").json()
    assert len(diary["memories"]) == 1


# =====================================================================
# 历史 / 搜索 / 日记
# =====================================================================
def test_history_clear(client):
    client.post("/api/chat", json={"text": "在吗"})
    assert len(client.get("/api/chat/history").json()) == 2
    resp = client.delete("/api/chat/history")
    assert resp.status_code == 200
    assert client.get("/api/chat/history").json() == []


def test_search_endpoint(client):
    client.post("/api/chat", json={"text": "今天好累啊"})
    today = datetime.now().strftime("%Y-%m-%d")
    hits = client.get("/api/chat/search", params={"start": today, "end": today, "q": "累"}).json()
    assert len(hits) == 1
    assert hits[0]["assistant"] == "哼，知道了啦。"
    assert client.get(
        "/api/chat/search", params={"start": today, "end": today, "q": "无关键词"}
    ).json() == []


def test_search_bad_date_400(client):
    resp = client.get("/api/chat/search", params={"start": "bad", "end": "bad"})
    assert resp.status_code == 400


def test_diary_endpoints(client):
    today = datetime.now().strftime("%Y-%m-%d")
    empty = client.get("/api/chat/diary/2020-01-01").json()
    assert empty["empty"] is True

    client.post("/api/chat", json={"text": "今天好累啊"})
    diary = client.get(f"/api/chat/diary/{today}").json()
    assert diary["empty"] is False
    assert diary["main_emotion"] == "开心"
    assert "累" in diary["keywords"]
    assert isinstance(diary["night_count"], int)

    resp = client.get("/api/chat/diary/not-a-date")
    assert resp.status_code == 400


# =====================================================================
# 用户画像 / 人格状态
# =====================================================================
def test_persona_get_default(client):
    data = client.get("/api/persona").json()
    assert data["profile"]["name"] == "小叶"
    assert data["state"]["trust"] == 0
    assert {g["id"] for g in data["goals"]} >= set()  # 空库目标列表可为空


def test_persona_put_updates_profile(client):
    resp = client.put("/api/persona", json={
        "name": "小叶子", "birthday": "04-06", "likes": "晴天,写代码",
    })
    assert resp.status_code == 200
    profile = client.get("/api/persona").json()["profile"]
    assert profile["name"] == "小叶子"
    assert profile["likes"] == ["晴天", "写代码"]


def test_persona_put_invalid_birthday_422(client):
    resp = client.put("/api/persona", json={"birthday": "4-6"})  # 不满足 MM-DD
    assert resp.status_code == 422


def test_reset_affinity(client):
    client.post("/api/chat", json={"text": "你好"})
    trust = client.get("/api/persona").json()["state"]["trust"]
    assert trust == 3
    client.post("/api/persona/reset-affinity")
    state = client.get("/api/persona").json()["state"]
    assert state["trust"] == 0
    assert state["intimacy_level"] == 1


# =====================================================================
# 语音路由（外设服务 monkeypatch，不触网）
# =====================================================================
def test_tts_ok(client, monkeypatch):
    monkeypatch.setattr("app.services.tts.text_to_speech", lambda text, voice=None: b"MP3DATA")
    resp = client.post("/api/voice/tts", json={"text": "哼"})
    assert resp.status_code == 200
    assert resp.content == b"MP3DATA"
    assert resp.headers["content-type"] == "audio/mpeg"


def test_tts_failure_502(client, monkeypatch):
    def boom(text, voice=None):
        raise RuntimeError("edge-tts 不可用")

    monkeypatch.setattr("app.services.tts.text_to_speech", boom)
    resp = client.post("/api/voice/tts", json={"text": "哼"})
    assert resp.status_code == 502


def test_stt_ok(client, monkeypatch):
    monkeypatch.setattr("app.services.stt.speech_to_text", lambda audio: "你好呀")
    resp = client.post("/api/voice/stt", json={"audio": "AAAAAAAA"})
    assert resp.status_code == 200
    assert resp.json() == {"text": "你好呀"}


def test_stt_empty_422(client, monkeypatch):
    monkeypatch.setattr("app.services.stt.speech_to_text", lambda audio: "")
    resp = client.post("/api/voice/stt", json={"audio": "AAAAAAAA"})
    assert resp.status_code == 422


# =====================================================================
# 天气服务（外呼 mock）
# =====================================================================
class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_weather_no_key_short_circuit(monkeypatch):
    monkeypatch.setattr(settings, "weather_api_key", "")
    assert weather.is_thunderstorm_now() is False


def test_weather_thunder_detected(monkeypatch):
    monkeypatch.setattr(settings, "weather_api_key", "k")
    monkeypatch.setattr(settings, "weather_host", "fake.host")
    monkeypatch.setattr(
        weather.httpx, "get",
        lambda *a, **k: _Resp(payload={"code": "200", "now": {"text": "雷阵雨"}}),
    )
    assert weather.is_thunderstorm_now() is True


def test_weather_normal_clear(monkeypatch):
    monkeypatch.setattr(settings, "weather_api_key", "k")
    monkeypatch.setattr(settings, "weather_host", "fake.host")
    monkeypatch.setattr(
        weather.httpx, "get",
        lambda *a, **k: _Resp(payload={"code": "200", "now": {"text": "晴"}}),
    )
    assert weather.is_thunderstorm_now() is False


def test_weather_http_error_silent(monkeypatch):
    monkeypatch.setattr(settings, "weather_api_key", "k")
    monkeypatch.setattr(settings, "weather_host", "fake.host")

    def boom(*a, **k):
        raise httpx.ConnectError("net down")

    monkeypatch.setattr(weather.httpx, "get", boom)
    assert weather.is_thunderstorm_now() is False


def test_weather_bad_status(monkeypatch):
    monkeypatch.setattr(settings, "weather_api_key", "k")
    monkeypatch.setattr(settings, "weather_host", "fake.host")
    monkeypatch.setattr(weather.httpx, "get", lambda *a, **k: _Resp(status_code=500))
    assert weather.is_thunderstorm_now() is False


# =====================================================================
# LLM Provider 层
# =====================================================================
class _AliveLocal(LLMProvider):
    name = "local"

    def chat(self, messages):
        return "本地"

    def health(self):
        return True


class _DeadLocal(LLMProvider):
    name = "local"

    def chat(self, messages):
        raise LLMError("down")

    def health(self):
        return False


def test_get_llm_channel_online(monkeypatch):
    monkeypatch.setattr(settings, "llm_channel", "online")
    assert isinstance(get_llm(), QwenProvider)


def test_get_llm_channel_local(monkeypatch):
    monkeypatch.setattr(settings, "llm_channel", "local")
    assert isinstance(get_llm(), OllamaProvider)


def test_get_llm_auto_local_first(monkeypatch):
    from app.providers import llm as llm_mod

    monkeypatch.setattr(settings, "llm_channel", "auto")
    monkeypatch.setattr(llm_mod, "_local_provider", lambda: _AliveLocal())
    assert isinstance(get_llm(), _AliveLocal)


def test_get_llm_auto_fallback_online(monkeypatch):
    from app.providers import llm as llm_mod

    monkeypatch.setattr(settings, "llm_channel", "auto")
    monkeypatch.setattr(llm_mod, "_local_provider", lambda: _DeadLocal())
    assert isinstance(get_llm(), QwenProvider)


def test_ollama_provider_chat_and_health(monkeypatch):
    ollama = pytest.importorskip("ollama")

    class _FakeClient:
        def __init__(self, host=None, timeout=None):
            pass

        def chat(self, model, messages, **kwargs):
            return {"message": {"content": "本地回复"}}

        def list(self):
            return {"models": []}

    monkeypatch.setattr(ollama, "Client", _FakeClient)
    p = OllamaProvider()
    assert p.chat([{"role": "user", "content": "hi"}]) == "本地回复"
    assert p.health() is True


def test_ollama_provider_failure(monkeypatch):
    ollama = pytest.importorskip("ollama")

    class _BoomClient:
        def __init__(self, host=None, timeout=None):
            pass

        def chat(self, model, messages, **kwargs):
            raise RuntimeError("down")

        def list(self):
            raise RuntimeError("down")

    monkeypatch.setattr(ollama, "Client", _BoomClient)
    p = OllamaProvider()
    assert p.health() is False
    with pytest.raises(LLMError):
        p.chat([{"role": "user", "content": "hi"}])


def test_qwen_provider_success(monkeypatch):
    from app.providers import llm as llm_mod

    monkeypatch.setattr(
        llm_mod.httpx, "post",
        lambda *a, **k: _Resp(payload={"output": {"text": "在线回复"}}),
    )
    assert QwenProvider().chat([{"role": "user", "content": "hi"}]) == "在线回复"


def test_qwen_provider_http_error(monkeypatch):
    from app.providers import llm as llm_mod

    def boom(*a, **k):
        raise httpx.ConnectError("net")

    monkeypatch.setattr(llm_mod.httpx, "post", boom)
    with pytest.raises(LLMError):
        QwenProvider().chat([{"role": "user", "content": "hi"}])


def test_qwen_provider_bad_status(monkeypatch):
    from app.providers import llm as llm_mod

    class _BadResp:
        status_code = 500
        text = "server error"

        def json(self):
            return {}

    monkeypatch.setattr(llm_mod.httpx, "post", lambda *a, **k: _BadResp())
    with pytest.raises(LLMError):
        QwenProvider().chat([{"role": "user", "content": "hi"}])


def test_qwen_provider_bad_payload(monkeypatch):
    from app.providers import llm as llm_mod

    monkeypatch.setattr(
        llm_mod.httpx, "post", lambda *a, **k: _Resp(payload={"unexpected": 1})
    )
    with pytest.raises(LLMError):
        QwenProvider().chat([{"role": "user", "content": "hi"}])
