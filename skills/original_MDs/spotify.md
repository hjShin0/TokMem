---
id: com.argo.spotify
name: Spotify
version: "1.0.0"
description: Search music and control playback via Spotify Web API
author: argo
tool_refs: [http_fetch, http_post]
tools: []
triggers: [spotify, music, song, playlist, play]
---

# Spotify Skill

Search tracks, albums, and artists, inspect and control the active playback device, and browse playlists via the Spotify Web API.

## Authentication

All requests require an OAuth 2.0 access token:
```
Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

The token must have the appropriate scopes (see per-verb notes). Tokens expire after 1 hour; if a 401 is returned, the user must refresh the token.

## Verbs

### search
Search for tracks, albums, artists, or playlists.

```
GET https://api.spotify.com/v1/search?q={query}&type=track&limit=10&market=US
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

- `type` — comma-separated: `track`, `album`, `artist`, `playlist` (e.g. `track,artist`)
- `limit` — 1–50, default 10
- `market` — ISO 3166-1 alpha-2 country code; omit to use account country
- `q` — supports field filters: `track:Shape artist:Ed+Sheeran`

Response keys per type: `tracks.items[]`, `albums.items[]`, `artists.items[]`, `playlists.items[]`.

Track fields: `id`, `name`, `uri` (`spotify:track:{id}`), `duration_ms`, `artists[].name`, `album.name`, `popularity`.

### now_playing
Get the currently playing track and device state. Requires scope `user-read-currently-playing`.

```
GET https://api.spotify.com/v1/me/player/currently-playing
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

Response: `is_playing` (bool), `progress_ms`, `item` (track object), `device` (`name`, `type`, `volume_percent`). Returns 204 with no body when nothing is playing.

### get_player
Get full player state including queue and device. Requires scope `user-read-playback-state`.

```
GET https://api.spotify.com/v1/me/player
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

### play
Start or resume playback. Requires scope `user-modify-playback-state`.

Play a specific track by URI:
```
PUT https://api.spotify.com/v1/me/player/play
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
         Content-Type: application/json
Body: { "uris": ["spotify:track:{trackId}"] }
```

Play a context (album or playlist):
```json
{ "context_uri": "spotify:playlist:{playlistId}", "offset": { "position": 0 }, "position_ms": 0 }
```

Omit body to resume current playback.

### pause
Pause playback. Requires scope `user-modify-playback-state`.

```
PUT https://api.spotify.com/v1/me/player/pause
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

### next / previous
Skip to next or previous track. Requires scope `user-modify-playback-state`.

```
POST https://api.spotify.com/v1/me/player/next
POST https://api.spotify.com/v1/me/player/previous
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

### set_volume
Set playback volume (0–100). Requires scope `user-modify-playback-state`.

```
PUT https://api.spotify.com/v1/me/player/volume?volume_percent={0-100}
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

### list_playlists
Get the current user's playlists. Requires scope `playlist-read-private`.

```
GET https://api.spotify.com/v1/me/playlists?limit=20&offset=0
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

Response: `items[]` with `id`, `name`, `uri`, `tracks.total`, `public`, `owner.display_name`.

### get_playlist_tracks
Get tracks from a playlist.

```
GET https://api.spotify.com/v1/playlists/{playlistId}/tracks?limit=50&offset=0&fields=items(track(id,name,uri,artists,duration_ms))
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

### list_devices
List available playback devices. Requires scope `user-read-playback-state`.

```
GET https://api.spotify.com/v1/me/player/devices
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
```

Response: `devices[]` with `id`, `name`, `type` (`Computer`, `Smartphone`, `Speaker`), `is_active`, `volume_percent`.

### transfer_playback
Move playback to a different device. Requires scope `user-modify-playback-state`.

```
PUT https://api.spotify.com/v1/me/player
Headers: Authorization: Bearer {ARGO_SPOTIFY_ACCESS_TOKEN}
         Content-Type: application/json
Body: { "device_ids": ["{deviceId}"], "play": true }
```

## Error Handling

| Status | Meaning |
|--------|---------|
| 401 | Token expired or invalid; user must re-authenticate |
| 403 | Scope missing or premium required |
| 404 | No active device; ask user to open Spotify on a device first |
| 429 | Rate limited; respect `Retry-After` header |

Error shape: `{ "error": { "status": 404, "message": "Player command failed: Premium required" } }`

Note: Most playback control endpoints require a Spotify Premium account.