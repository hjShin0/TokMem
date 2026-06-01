---
id: com.argo.smartthings
name: SmartThings
version: "2.0.0"
description: >
  Control Samsung SmartThings devices, locations, rooms, and scenes
  through the official REST API. Tools mirror the Samsung CLI
  (`smartthings devices`, `smartthings devices:status`, etc.) so prior
  CLI experience translates directly. No Node, no npm — pure HTTP via
  the standard `fetch()` global.
author: argo
runtime: quickjs
tools:
  - name: smartthings_locations_list
    description: >
      List every SmartThings location the user's PAT has access to.
      Returns `{ items: [{ locationId, name, ... }], _links: ... }`.
      Maps to `GET /v1/locations`.
    parameters:
      type: object
      properties: {}

  - name: smartthings_rooms_list
    description: >
      List rooms in a specific location. Returns `{ items: [{ roomId,
      name, locationId, ... }] }`. Maps to
      `GET /v1/locations/{locationId}/rooms`.
    parameters:
      type: object
      required: [location_id]
      properties:
        location_id:
          type: string
          description: "Location id from `smartthings_locations_list`."

  - name: smartthings_devices_list
    description: >
      List devices. Every filter is optional and composes; passing no
      filters lists every device the PAT can see. Maps to
      `GET /v1/devices` with query params.
    parameters:
      type: object
      properties:
        location_id:
          type: string
          description: "Restrict to one location."
        capability:
          type: string
          description: "Restrict to devices that have a given capability id (e.g. `switch`, `colorControl`)."
        device_id:
          type: string
          description: "Look up one specific device id (rare — use `smartthings_devices_status` for the full status)."
        installed_app_id:
          type: string
          description: "Restrict to devices owned by a specific installed app."
        type:
          type: string
          description: "Restrict to a device type (e.g. `OCF`, `EDGE_CHILD`)."
        include_status:
          type: boolean
          description: "Inline current capability values in the listing. Slower; prefer `smartthings_devices_status` for one device."
        include_health:
          type: boolean
          description: "Inline online/offline + battery health in the listing."

  - name: smartthings_devices_status
    description: >
      Full per-component capability values for one device. Use BEFORE
      issuing a command when the supported command set is unclear.
      Maps to `GET /v1/devices/{deviceId}/status`.
    parameters:
      type: object
      required: [device_id]
      properties:
        device_id:
          type: string
          description: "Device id from `smartthings_devices_list`."

  - name: smartthings_devices_command
    description: >
      Issue one or more commands to a device. Maps to
      `POST /v1/devices/{deviceId}/commands`. Common shapes —
      `[{capability:"switch", command:"on"}]`,
      `[{capability:"switchLevel", command:"setLevel", arguments:[80]}]`,
      `[{capability:"colorControl", command:"setColor", arguments:[{hue:20, saturation:50}]}]`.
    parameters:
      type: object
      required: [device_id, commands]
      properties:
        device_id:
          type: string
          description: "Target device id."
        commands:
          type: array
          minItems: 1
          description: "One or more capability:command tuples to execute."
          items:
            type: object
            required: [capability, command]
            properties:
              component:
                type: string
                description: "Component id; defaults to `main` per the SmartThings contract."
              capability:
                type: string
                description: "Capability id (e.g. `switch`, `switchLevel`, `colorControl`, `audioVolume`)."
              command:
                type: string
                description: "Command name on that capability (e.g. `on`, `off`, `setLevel`)."
              arguments:
                type: array
                description: "Positional arguments for the command. Empty array when the command takes no args."

  - name: smartthings_scenes_list
    description: >
      List scenes, optionally restricted to one location. Maps to
      `GET /v1/scenes` (with `?locationId=…` when the filter is set).
    parameters:
      type: object
      properties:
        location_id:
          type: string
          description: "Restrict to one location."

  - name: smartthings_scenes_execute
    description: >
      Execute a scene by id. Maps to
      `POST /v1/scenes/{sceneId}/execute`.
    parameters:
      type: object
      required: [scene_id]
      properties:
        scene_id:
          type: string
          description: "Scene id from `smartthings_scenes_list`."

  - name: smartthings_inventory_refresh
    description: >
      Pull every location, room, device, and scene the PAT can see and
      persist them as a JSON cache at
      `<home>/.argo/skills-state/smartthings/inventory.json`. Returns
      a diff vs the prior cache (added / removed / changed by id) plus
      totals — useful for reactive flows that only act when the
      inventory shape has changed since the last sweep.
    parameters:
      type: object
      properties:
        ttl_secs:
          type: number
          description: "How long the cache is considered fresh, in seconds. Default 86400 (24h)."

  - name: smartthings_inventory_get
    description: >
      Read the persisted inventory cache. Returns `{ present, is_stale,
      age_secs, ttl_secs, totals, locations, rooms, devices, scenes }`
      or `{ present: false }` if the cache hasn't been written yet.
      Optional filters narrow the `devices` array without a network call.
    parameters:
      type: object
      properties:
        kind:
          type: string
          description: "Restrict the returned `devices` to those advertising a specific capability id (e.g. `switch`, `audioVolume`)."
        room:
          type: string
          description: "Restrict the returned `devices` to those whose `roomId` matches."

  - name: smartthings_inventory_clear
    description: >
      Truncate the inventory cache file. Subsequent
      `smartthings_inventory_get` calls report `{ present: false }`.
    parameters:
      type: object
      properties: {}

triggers: [smartthings, iot, smart home, device, samsung, light, tv, ac, inventory]

tool_impl:
  kind: js
  source: ""
---

# SmartThings

Talk to the SmartThings cloud directly. Tools mirror the official
Samsung CLI's command names so prior `smartthings-cli` knowledge maps 1:1.

## Auth

The user's personal access token (PAT) lives in the secret store under
the key `smartthings_api_key`. Generate one at
<https://account.smartthings.com/tokens> and set it via argo's
secret-store CLI before any of these tools will work; missing tokens
produce an actionable error.

## Suggested order of operations

1. `smartthings_locations_list` once to discover location ids.
2. `smartthings_devices_list` (optionally with `location_id` /
   `capability`) to discover device ids.
3. `smartthings_devices_status` BEFORE issuing a command when the
   supported command set on a given device is unclear.
4. `smartthings_devices_command` to actually flip switches / set
   levels / change colors / adjust volume.
5. `smartthings_scenes_list` + `smartthings_scenes_execute` for
   composite, user-defined automations the platform pre-built.

## Common command examples

| Intent                | `commands` array                                           |
|-----------------------|------------------------------------------------------------|
| Turn on               | `[{capability:"switch", command:"on"}]`                    |
| Turn off              | `[{capability:"switch", command:"off"}]`                   |
| Dim to 80%            | `[{capability:"switchLevel", command:"setLevel", arguments:[80]}]` |
| Set color (HSV)       | `[{capability:"colorControl", command:"setColor", arguments:[{hue:20, saturation:50}]}]` |
| Set color temperature | `[{capability:"colorTemperature", command:"setColorTemperature", arguments:[3000]}]` |
| Volume up             | `[{capability:"audioVolume", command:"volumeUp"}]`         |
| Set thermostat heat   | `[{capability:"thermostatHeatingSetpoint", command:"setHeatingSetpoint", arguments:[68]}]` |

The full capability + command catalog is at
<https://developer.smartthings.com/docs/api/public#tag/Capabilities>.
When in doubt about the command set a device supports, call
`smartthings_devices_status` first — the response lists every
component + capability the device exposes.