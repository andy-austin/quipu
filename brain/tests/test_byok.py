"""Tests for BYOK (Bring Your Own Key) — brain model selection with user keys."""

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI

from brain.models import DEFAULT_MODEL, SUPPORTED_MODELS, get_llm


class TestGetLlm:
    def test_default_model_type(self):
        """Default model returns a Google model."""
        llm = get_llm(user_api_keys={"google": "fake-key-for-test"})
        assert isinstance(llm, ChatGoogleGenerativeAI)

    def test_google_with_user_key(self):
        llm = get_llm("gemini-2.0-flash", user_api_keys={"google": "user-goog-key"})
        assert isinstance(llm, ChatGoogleGenerativeAI)

    def test_groq_with_user_key(self):
        llm = get_llm("llama-3.3-70b", user_api_keys={"groq": "user-groq-key"})
        assert isinstance(llm, ChatGroq)

    def test_openai_with_user_key(self):
        llm = get_llm("gpt-4o", user_api_keys={"openai": "sk-test-key"})
        assert isinstance(llm, ChatOpenAI)

    def test_openai_mini_with_user_key(self):
        llm = get_llm("gpt-4o-mini", user_api_keys={"openai": "sk-test-key"})
        assert isinstance(llm, ChatOpenAI)

    def test_anthropic_with_user_key(self):
        llm = get_llm("claude-sonnet", user_api_keys={"anthropic": "sk-ant-test"})
        assert isinstance(llm, ChatAnthropic)

    def test_anthropic_haiku_with_user_key(self):
        llm = get_llm("claude-haiku", user_api_keys={"anthropic": "sk-ant-test"})
        assert isinstance(llm, ChatAnthropic)

    def test_mistral_with_user_key(self):
        llm = get_llm("mistral-large", user_api_keys={"mistral": "test-mistral-key"})
        assert isinstance(llm, ChatMistralAI)

    def test_mistral_small_with_user_key(self):
        llm = get_llm("mistral-small", user_api_keys={"mistral": "test-mistral-key"})
        assert isinstance(llm, ChatMistralAI)

    def test_unsupported_model_raises(self):
        with pytest.raises(ValueError, match="Unsupported model"):
            get_llm("nonexistent-model")

    def test_supported_models_has_all_providers(self):
        assert len(SUPPORTED_MODELS) == 8
        assert DEFAULT_MODEL in SUPPORTED_MODELS
        providers = {v[0] for v in SUPPORTED_MODELS.values()}
        assert providers == {"google", "groq", "openai", "anthropic", "mistral"}


class TestBrainKeyEndpoints:
    """Test the /api/keys endpoints via the FastAPI test client."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from brain.dependencies import verify_user
        from brain.server import app

        app.dependency_overrides[verify_user] = lambda: "user-1"
        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            app.dependency_overrides.clear()

    def test_store_key_no_mcp(self, client):
        """Without MCP tools, store returns error."""
        resp = client.post("/api/keys", params={"provider": "google", "api_key": "test-key"})
        assert resp.status_code == 200
        assert resp.json() == {"error": "Key storage not available"}

    def test_delete_key_no_mcp(self, client):
        resp = client.delete("/api/keys/google")
        assert resp.status_code == 200
        assert resp.json() == {"error": "Key storage not available"}

    def test_list_keys_no_mcp(self, client):
        resp = client.get("/api/keys")
        assert resp.status_code == 200
        assert resp.json() == {"providers": []}
