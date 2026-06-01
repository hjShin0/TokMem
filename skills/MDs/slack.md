---
id: com.argo.slack
name: Slack
version: "1.0.0"
description: Send and read Slack messages via Slack Web API
author: argo
tool_refs: [http_fetch, http_post]
tools: []
triggers: [slack, message, channel]
---

# Slack Skill

Use the Slack Web API to list channels, read messages, send messages, search, react, and fetch user info.

## Authentication

All requests require:
```
Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
```

## Verbs

### list_channels
List public channels (excluding archived).

```
GET https://slack.com/api/conversations.list?limit=50&exclude_archived=true
Headers: Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
```

Response: `channels[]` — each has `id`, `name`, `is_private`, `num_members`.

### read_channel
Fetch recent messages from a channel.

```
GET https://slack.com/api/conversations.history?channel={id}&limit=20
Headers: Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
```

Response: `messages[]` — each has `ts`, `user`, `text`, `thread_ts`.

### send_message
Post a message to a channel or thread.

```
POST https://slack.com/api/chat.postMessage
Headers: Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
         Content-Type: application/json
Body: {"channel":"C1234567","text":"Hello!","thread_ts":"optional-parent-ts"}
```

Omit `thread_ts` for a top-level message. Response includes `ts` of the new message.

### search
Search messages across the workspace.

```
GET https://slack.com/api/search.messages?query={q}&count=10
Headers: Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
```

Response: `messages.matches[]` — each has `channel.id`, `ts`, `text`, `permalink`.

### add_reaction
Add an emoji reaction to a message.

```
POST https://slack.com/api/reactions.add
Headers: Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
         Content-Type: application/json
Body: {"channel":"C1234567","timestamp":"1234567890.123456","name":"thumbsup"}
```

`name` is the emoji name without colons (e.g., `thumbsup`, `tada`).

### get_thread
Fetch all replies in a message thread.

```
GET https://slack.com/api/conversations.replies?channel={id}&ts={ts}&limit=20
Headers: Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
```

`ts` is the timestamp of the parent message.

### get_user
Fetch profile info for a Slack user.

```
GET https://slack.com/api/users.info?user={userId}
Headers: Authorization: Bearer {ARGO_SLACK_BOT_TOKEN}
```

Response: `user` object with `id`, `name`, `real_name`, `profile.email`, `profile.image_72`.

## Error Handling

All Slack API responses return HTTP 200. Check `ok: false` and `error` field for failures (e.g., `not_authed`, `channel_not_found`, `ratelimited`). On `ratelimited`, respect `Retry-After` header.