---
id: com.argo.discord
name: Discord
version: "1.0.0"
description: Send and read Discord messages via Discord REST API v10
author: argo
tool_refs: [http_fetch, http_post]
tools: []
triggers: [discord, server, guild]
---

# Discord Skill

Use the Discord REST API v10 to interact with servers (guilds), channels, messages, reactions, and users.

## Authentication

All requests require:
```
Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
Content-Type: application/json
```

Base URL: `https://discord.com/api/v10`

## Verbs

### list_guilds
List all guilds (servers) the bot is a member of.

```
GET https://discord.com/api/v10/users/@me/guilds
Headers: Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
```

Response: array of guild objects with `id`, `name`, `icon`.

### list_channels
List all channels in a guild.

```
GET https://discord.com/api/v10/guilds/{guildId}/channels
Headers: Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
```

Response: array of channel objects with `id`, `name`, `type` (0=text, 2=voice, 4=category), `position`.

### read_messages
Fetch recent messages from a channel.

```
GET https://discord.com/api/v10/channels/{channelId}/messages?limit=20
Headers: Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
```

Response: array of message objects with `id`, `content`, `author.username`, `timestamp`.

### send_message
Send a message to a channel.

```
POST https://discord.com/api/v10/channels/{channelId}/messages
Headers: Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
         Content-Type: application/json
Body: {"content":"Hello, Discord!"}
```

Optional fields: `tts`, `embeds[]`, `message_reference.message_id` (for replies).

### add_reaction
Add an emoji reaction to a message. Expects HTTP 204 No Content on success.

```
PUT https://discord.com/api/v10/channels/{cId}/messages/{mId}/reactions/{emoji}/@me
Headers: Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
Body: (empty)
```

For custom emojis use `name:id` format. For Unicode emoji, URL-encode the character (e.g., `%F0%9F%91%8D` for 👍).

### edit_message
Edit an existing message sent by the bot.

```
PATCH https://discord.com/api/v10/channels/{cId}/messages/{mId}
Headers: Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
         Content-Type: application/json
Body: {"content":"Updated text"}
```

### get_user
Fetch a Discord user's public profile.

```
GET https://discord.com/api/v10/users/{userId}
Headers: Authorization: Bot {ARGO_DISCORD_BOT_TOKEN}
```

Response: `id`, `username`, `discriminator`, `avatar`, `bot`.

## Error Handling

HTTP 401 = invalid token. HTTP 403 = missing permissions. HTTP 429 = rate limited — check `retry_after` in JSON body and `X-RateLimit-Reset-After` header. HTTP 404 = unknown resource (channel/guild/message ID may be wrong).