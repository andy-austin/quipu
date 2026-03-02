from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

SUPPORTED_MODELS: dict[str, tuple[str, str]] = {
    "gemini-2.0-flash": ("google", "gemini-2.0-flash"),
    "llama-3.3-70b": ("groq", "llama-3.3-70b-versatile"),
}

DEFAULT_MODEL = "gemini-2.0-flash"


def get_llm(model: str | None = None) -> BaseChatModel:
    """Return a LangChain chat model for the given identifier."""
    key = model or DEFAULT_MODEL
    if key not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model '{key}'. Choose from: {list(SUPPORTED_MODELS)}")

    provider, model_name = SUPPORTED_MODELS[key]
    if provider == "google":
        return ChatGoogleGenerativeAI(model=model_name)
    if provider == "groq":
        return ChatGroq(model=model_name)
    raise ValueError(f"Unknown provider '{provider}'")
