from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

SUPPORTED_MODELS: dict[str, tuple[str, str]] = {
    "gemini-2.0-flash": ("google", "gemini-2.0-flash"),
    "llama-3.3-70b": ("groq", "llama-3.3-70b-versatile"),
}

DEFAULT_MODEL = "gemini-2.0-flash"


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

    if provider == "google":
        api_key = user_keys.get("google")
        if api_key:
            return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
        return ChatGoogleGenerativeAI(model=model_name)
    if provider == "groq":
        api_key = user_keys.get("groq")
        if api_key:
            return ChatGroq(model=model_name, api_key=api_key)  # type: ignore[call-arg]
        return ChatGroq(model=model_name)
    raise ValueError(f"Unknown provider '{provider}'")
