# SSE Event Protocol

The Brain streams structured JSON events over Server-Sent Events (SSE). Each line follows the format `data: <json>\n\n`.

## Event Types

| Type | Description | Fields |
|---|---|---|
| `reasoning` | LLM is thinking / deciding next step | `message` |
| `tool_start` | LLM requested a tool call | `message`, `tool` |
| `tool_result` | Tool execution completed | `message`, `tool`, `status` |
| `answer` | Final LLM response (no more tool calls) | `message` |
| `error` | An error occurred during processing | `message` |
| `done` | Stream is complete | — |

### Field Reference

- **`type`** (string): One of the event types above.
- **`message`** (string): Human-readable description of the event.
- **`tool`** (string, optional): Name of the MCP tool involved.
- **`status`** (string, optional): `"success"` or `"error"` for `tool_result` events.

## Example: Successful Flow

```
data: {"type": "tool_start", "message": "Calling check_database_freshness...", "tool": "check_database_freshness"}
data: {"type": "tool_result", "message": "No fresh data found.", "tool": "check_database_freshness", "status": "success"}
data: {"type": "reasoning", "message": "No cached data — I need to scrape the website."}
data: {"type": "tool_start", "message": "Calling scrape_website...", "tool": "scrape_website"}
data: {"type": "tool_result", "message": "Scraped 42 elements.", "tool": "scrape_website", "status": "success"}
data: {"type": "tool_start", "message": "Calling save_metadata...", "tool": "save_metadata"}
data: {"type": "tool_result", "message": "Saved successfully.", "tool": "save_metadata", "status": "success"}
data: {"type": "answer", "message": "Here are the scraped results for https://example.com..."}
data: {"type": "done"}
```

## Example: Error Flow

```
data: {"type": "tool_start", "message": "Calling scrape_website...", "tool": "scrape_website"}
data: {"type": "tool_result", "message": "Error executing tool scrape_website: connection refused", "tool": "scrape_website", "status": "error"}
data: {"type": "error", "message": "Pipeline failed: connection refused"}
```

## Frontend Integration

```typescript
const evtSource = new EventSource(`/api/scraper/stream?url=${url}&model=${model}`);

evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case "reasoning":
      showThinking(data.message);
      break;
    case "tool_start":
      showToolProgress(data.tool, data.message);
      break;
    case "tool_result":
      updateToolStatus(data.tool, data.status, data.message);
      break;
    case "answer":
      showAnswer(data.message);
      break;
    case "error":
      showError(data.message);
      break;
    case "done":
      evtSource.close();
      break;
  }
};
```
