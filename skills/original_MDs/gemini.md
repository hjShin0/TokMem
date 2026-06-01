---
id: com.argo.gemini
name: Google Gemini
version: "1.0.0"
description: Generate text and analyze content via Google Gemini API
author: argo
tool_refs: [http_fetch, http_post]
tools: []
triggers: [gemini, google ai, generate]
---

# Google Gemini Skill

Use the Google Gemini generative AI API to generate text, count tokens, list available models, and run code execution tasks.

## Authentication

Pass the API key as a query parameter on every request:
```
?key={ARGO_GEMINI_API_KEY}
```
All requests also require:
```
Content-Type: application/json
```

## Recommended Models

| Alias | Model ID | Notes |
|-------|----------|-------|
| fast  | gemini-2.0-flash | Low latency, great for most tasks |
| smart | gemini-2.0-pro   | Higher quality, slower |
| lite  | gemini-1.5-flash | Very fast, smaller context |

## Verbs

### generate
Generate text from a user prompt.

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={ARGO_GEMINI_API_KEY}
Headers: Content-Type: application/json
Body:
{
  "contents": [
    { "role": "user", "parts": [{ "text": "Your prompt here" }] }
  ],
  "generationConfig": {
    "temperature": 0.7,
    "maxOutputTokens": 1024,
    "topP": 0.95,
    "topK": 40
  },
  "systemInstruction": {
    "parts": [{ "text": "Optional system prompt" }]
  }
}
```

Response:
```json
{
  "candidates": [
    {
      "content": { "parts": [{ "text": "Generated text..." }], "role": "model" },
      "finishReason": "STOP",
      "safetyRatings": [...]
    }
  ],
  "usageMetadata": { "promptTokenCount": 10, "candidatesTokenCount": 200, "totalTokenCount": 210 }
}
```

Extract the reply from `candidates[0].content.parts[0].text`.

### multi_turn
Multi-turn conversation: include prior turns in `contents` array.

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={ARGO_GEMINI_API_KEY}
Body:
{
  "contents": [
    { "role": "user",  "parts": [{ "text": "Hello!" }] },
    { "role": "model", "parts": [{ "text": "Hi there!" }] },
    { "role": "user",  "parts": [{ "text": "What can you do?" }] }
  ],
  "generationConfig": { "maxOutputTokens": 512 }
}
```

### list_models
List all available Gemini models.

```
GET https://generativelanguage.googleapis.com/v1beta/models?key={ARGO_GEMINI_API_KEY}
```

Response: `models[]` — each has `name`, `displayName`, `description`, `inputTokenLimit`, `outputTokenLimit`, `supportedGenerationMethods`.

### count_tokens
Count how many tokens a prompt will consume before sending it.

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:countTokens?key={ARGO_GEMINI_API_KEY}
Headers: Content-Type: application/json
Body:
{
  "contents": [
    { "role": "user", "parts": [{ "text": "Your prompt here" }] }
  ]
}
```

Response: `{ "totalTokens": 42 }`

### code_execute
Ask the model to write and run code using the built-in code execution tool.

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={ARGO_GEMINI_API_KEY}
Headers: Content-Type: application/json
Body:
{
  "contents": [
    { "role": "user", "parts": [{ "text": "Calculate the sum of primes below 100." }] }
  ],
  "tools": [{ "codeExecution": {} }],
  "generationConfig": { "maxOutputTokens": 2048 }
}
```

Response parts may include `executableCode` (the code written) and `codeExecutionResult` (stdout/stderr).

## Error Handling

HTTP 400 — invalid request body or unsupported model.
HTTP 403 — API key invalid or quota exceeded.
HTTP 429 — rate limited; back off exponentially.
HTTP 500/503 — transient server error; retry after a short delay.

Error shape:
```json
{ "error": { "code": 400, "message": "...", "status": "INVALID_ARGUMENT" } }
```