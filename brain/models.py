from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI

SUPPORTED_MODELS: dict[str, tuple[str, str]] = {
    # Google
    "gemini-2.0-flash": ("google", "gemini-2.0-flash"),
    # Groq
    "llama-3.3-70b": ("groq", "llama-3.3-70b-versatile"),
    # OpenAI
    "gpt-4o": ("openai", "gpt-4o"),
    "gpt-4o-mini": ("openai", "gpt-4o-mini"),
    # Anthropic
    "claude-sonnet": ("anthropic", "claude-sonnet-4-20250514"),
    "claude-haiku": ("anthropic", "claude-haiku-4-20250414"),
    # Mistral
    "mistral-large": ("mistral", "mistral-large-latest"),
    "mistral-small": ("mistral", "mistral-small-latest"),
}

DEFAULT_MODEL = "gemini-2.0-flash"

_PROVIDER_FACTORIES: dict[str, tuple[type, str]] = {
    "google": (ChatGoogleGenerativeAI, "google_api_key"),
    "groq": (ChatGroq, "api_key"),
    "openai": (ChatOpenAI, "api_key"),
    "anthropic": (ChatAnthropic, "api_key"),
    "mistral": (ChatMistralAI, "api_key"),
}


def get_llm(
    model: str | None = None,
    user_api_keys: dict[str, str] | None = None,
) -> BaseChatModel:
    """Return a LangChain chat model, using user keys when available.

    Args:
        model: Model identifier (defaults to DEFAULT_MODEL).
        user_api_keys: Optional dict of provider -> api_key from BYOK.
    """
    key = model or DEFAULT_MODEL
    if key not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model '{key}'. Choose from: {list(SUPPORTED_MODELS)}")

    provider, model_name = SUPPORTED_MODELS[key]
    user_keys = user_api_keys or {}

    if provider not in _PROVIDER_FACTORIES:
        raise ValueError(f"Unknown provider '{provider}'")

    cls, key_param = _PROVIDER_FACTORIES[provider]
    api_key = user_keys.get(provider)
    if api_key:
        return cls(model=model_name, **{key_param: api_key})  # type: ignore[call-arg]
    return cls(model=model_name)  # type: ignore[call-arg]
