# Multi-Model Support

The Brain supports multiple LLM providers via the `brain/models.py` module using a factory-based provider system.

## Supported Models

| Model Key | Provider | Underlying Model | Notes |
|---|---|---|---|
| `gemini-2.0-flash` | Google | `gemini-2.0-flash` | Default model |
| `llama-3.3-70b` | Groq | `llama-3.3-70b-versatile` | Fast inference |
| `gpt-4o` | OpenAI | `gpt-4o` | GPT-4o |
| `gpt-4o-mini` | OpenAI | `gpt-4o-mini` | Cost-effective GPT |
| `claude-sonnet-4-20250514` | Anthropic | `claude-sonnet-4-20250514` | Claude Sonnet |
| `mistral-large-latest` | Mistral | `mistral-large-latest` | Mistral Large |

## Usage

Pass the `model` query parameter to any streaming endpoint:

```
GET /api/scraper/stream?url=https://example.com&model=llama-3.3-70b
GET /api/chat/stream?message=hello&model=gpt-4o
GET /api/test/stream?url=https://example.com&model=gemini-2.0-flash
```

If omitted, the default model (`gemini-2.0-flash`) is used.

## BYOK (Bring Your Own Key)

Users can store their own API keys via the `/api/keys` endpoints. Keys are encrypted at rest using Fernet symmetric encryption (`KEY_ENCRYPTION_KEY` env var on the Hands service).

When a user has stored a key for a provider, it is used instead of the server's default key. This allows users to bring their own OpenAI, Anthropic, or other provider keys.

### Key Management Endpoints

- `POST /api/keys` — Store a key (`provider`, `api_key`)
- `GET /api/keys` — List providers with stored keys
- `DELETE /api/keys/{provider}` — Delete a stored key

## Adding a New Model

1. Install the LangChain provider package (e.g., `langchain-openai`).
2. Add an entry to `SUPPORTED_MODELS` in `brain/models.py`:
   ```python
   "model-key": ("provider", "model-name"),
   ```
3. If the provider is new, add it to `_PROVIDER_FACTORIES`:
   ```python
   "provider": (ChatProviderClass, "api_key_param_name"),
   ```
4. Set the required API key environment variable on Fly.io.

## Environment Variables

| Variable | Required For |
|---|---|
| `GOOGLE_API_KEY` | Gemini models |
| `GROQ_API_KEY` | Groq / Llama models |
| `OPENAI_API_KEY` | OpenAI / GPT models |
| `ANTHROPIC_API_KEY` | Anthropic / Claude models |
| `MISTRAL_API_KEY` | Mistral models |
