# Multi-Model Support

The Brain supports multiple LLM providers via the `brain/models.py` module.

## Supported Models

| Model Key | Provider | Underlying Model | Notes |
|---|---|---|---|
| `gemini-2.0-flash` | Google | `gemini-2.0-flash` | Default model |
| `llama-3.3-70b` | Groq | `llama-3.3-70b-versatile` | Fast inference |

## Usage

Pass the `model` query parameter to any streaming endpoint:

```
GET /api/scraper/stream?url=https://example.com&model=llama-3.3-70b
GET /api/test/stream?url=https://example.com&model=gemini-2.0-flash
```

If omitted, the default model (`gemini-2.0-flash`) is used.

## Adding a New Model

1. Install the LangChain provider package (e.g., `langchain-openai`).
2. Add an entry to `SUPPORTED_MODELS` in `brain/models.py`:
   ```python
   "gpt-4o": ("openai", "gpt-4o"),
   ```
3. Add a provider branch in `get_llm()`:
   ```python
   if provider == "openai":
       return ChatOpenAI(model=model_name)
   ```
4. Set the required API key environment variable on Fly.io.

## Environment Variables

| Variable | Required For |
|---|---|
| `GOOGLE_API_KEY` | Gemini models |
| `GROQ_API_KEY` | Groq / Llama models |
