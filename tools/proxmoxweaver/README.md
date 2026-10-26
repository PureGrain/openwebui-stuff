# ProxmoxWeaver: Proxmox VE Monitoring and Management for Open WebUI

## Table of Contents

- [Overview](#overview)
- [What's New in 3.0](#whats-new-in-30)
- [Features](#features)
- [Installation](#installation)
- [Settings (Valves)](#settings-valves)
- [Function Reference](#function-reference)
- [Example Questions](#example-questions)
- [Actions and Safety](#actions-and-safety)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [License](#license)

## Overview

ProxmoxWeaver lets a model in Open WebUI answer questions about your Proxmox VE cluster: what is running, where it lives, what IP it has, whether backups are current, what failed overnight, and whether anything needs attention. With actions turned on, it can also start, stop and snapshot guests, asking you to confirm each one.

**Version:** 3.0.2
**Author:** PureGrain at SLA Ops, LLC
**License:** MIT

---

### Support This Project

If ProxmoxWeaver has made your Proxmox management easier or saved you time, consider supporting its continued development. Sponsorship helps cover development costs and keeps new features coming.

**[Become a Sponsor on GitHub](https://github.com/sponsors/PureGrain)**

**[Get the Latest Version](https://github.com/PureGrain/openwebui-stuff/tree/main/tools/proxmoxweaver)**

---

## What's New in 3.0

- **No extra packages.** Talks to the Proxmox API directly with `httpx`, which ships with Open WebUI. `proxmoxer` is no longer needed.
- **Keeps working when a node is down.** Cluster-wide lists come from one `/cluster/resources` call, so an offline node no longer breaks them. Guests on an offline node show status `unknown`.
- **Host failover.** List several nodes in `PROXMOX_HOST`; the tool uses the first one that answers and remembers it.
- **Fully async** with live status updates in the chat, as Open WebUI recommends for current and future versions.
- **Built for small models.** 16 focused functions instead of 27, every argument documented, choices sent as fixed lists, and guests found by name or VMID with no node needed.
- **New:** health report, guest IP addresses, backup coverage, pending updates and disk SMART health, usage history with peaks, and a visual cluster dashboard in the chat.
- **Optional actions:** start, shutdown, reboot, stop and snapshot, off by default, admin only, and confirmed in the chat every time.
- **Token secret is masked** in the settings screen.

Function names changed from 2.x. If a model's system prompt names old functions, update it. See [Changelog](#changelog) for the mapping.

## Features

| Area | What you get |
|---|---|
| Cluster | Nodes online, quorum, CPU and memory per node, guest counts, storage use, warnings |
| Health | One call that flags offline nodes, lost quorum, full storage, failing disks, failed tasks, stuck locks, pending updates and missing or old backups |
| Guests | Every VM and container across the cluster, filtered by type, status, node or name |
| Guest details | Usage, IPs, CPU, memory, disks, network cards, boot settings, snapshots and description |
| IP addresses | Read live from containers and from VMs with the QEMU guest agent |
| Backups | Scheduled jobs and their next run, guests in no job, newest backup per guest with its age |
| Nodes | CPU model, load, kernel and Proxmox version, package updates waiting, disks with SMART health |
| History | Average and peak CPU, memory, network and disk activity over an hour, day, week, month or year |
| Tasks | Recent backups, starts, stops, snapshots and migrations with result and duration |
| Access | Users, API tokens (privilege separation, expiry), groups, custom roles, cluster firewall state |
| Dashboard | Node cards and a guest table drawn right in the chat, light and dark |
| Actions | Start, shutdown, reboot, stop, snapshot (optional, confirmed) |

## Installation

### Requirements

- Open WebUI 0.10.0 or newer
- Proxmox VE 7 or newer (tested on 9.2)
- A Proxmox API token
- A model with tool calling, with **Function Calling** set to **Native** (Admin Panel > Settings > Models > Advanced Params)

### Setup

1. **Create an API token** in Proxmox under Datacenter > Permissions > API Tokens.
   - For read-only use, give the token the `PVEAuditor` role on `/`. That covers everything except pending package updates, which Proxmox only shows with `Sys.Modify`; without it those checks are skipped.
   - With privilege separation on (the default), the token has no permissions until you add them under Datacenter > Permissions. With it off, the token has all of its user's permissions.
   - For actions, the token also needs `VM.PowerMgmt` (in `PVEVMUser`) and `VM.Snapshot` (in `PVEVMAdmin`, or a custom role) on the guests it may change.
2. **Add the tool** in Open WebUI under Workspace > Tools > New Tool, and paste in `proxmoxweaver.py`.
3. **Fill in the Valves** (the gear icon on the tool): at least `PROXMOX_HOST`, `PROXMOX_TOKEN_ID` and `PROXMOX_TOKEN_SECRET`.
4. **Enable the tool** on your model (Workspace > Models > your model > Tools), or per chat with the + button.
5. Ask "check the Proxmox connection". The answer lists every host it tried and whether the token was accepted.

**Context length:** tool descriptions, built-in tools and results all count against the model's context. With Ollama, set **Context Length** to 16384 or more in the model's Advanced Params. If your model is a Workspace model, set it there, because a Workspace model's own settings override the base model's.

**Upgrading from 2.x:** the settings `PROXMOX_HOST`, `PROXMOX_USER`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET` and `VERIFY_SSL` keep their names, so saved values carry over. `proxmoxer` and any startup step that installs it can be removed.

## Settings (Valves)

| Valve | Default | Purpose |
|---|---|---|
| `PROXMOX_HOST` | `192.168.1.10:8006` | One or more nodes, comma separated, for example `10.0.0.10:8006,10.0.0.11:8006`. Port 8006 is assumed if left out |
| `PROXMOX_USER` | `root@pam` | User that owns the token |
| `PROXMOX_TOKEN_ID` | empty | Token name (after the `!`), or the full `user@realm!name` |
| `PROXMOX_TOKEN_SECRET` | empty | Token secret, shown masked |
| `VERIFY_SSL` | off | Turn on only with a trusted certificate |
| `TIMEOUT_SECONDS` | 15 | Per request. Connecting to a host gives up after 5 seconds and moves to the next |
| `TIMEZONE` | empty | For example `America/New_York`. Empty uses the chat user's time zone, then UTC |
| `STORAGE_WARN_PERCENT` | 85 | Storage and root disks above this are flagged |
| `BACKUP_MAX_AGE_DAYS` | 7 | Guests whose newest backup is older are flagged |
| `ENABLE_ACTIONS` | off | Allows start, shutdown, reboot, stop and snapshots |
| `ACTIONS_ADMIN_ONLY` | on | Only Open WebUI admins can run actions |
| `CONFIRM_ACTIONS` | on | Every action asks for confirmation in the chat |

Valve values are stored in plain text in the Open WebUI database unless an administrator sets `ENABLE_VALVE_ENCRYPTION=true`.

## Function Reference

Guests can always be given by name, part of a name, or VMID. Nodes can be given by part of their name, for example `host01`.

| Function | Arguments | Returns |
|---|---|---|
| `get_cluster_overview` | none | Nodes, quorum, version, guest counts, storage, warnings |
| `get_health_report` | none | Overall OK, WARNING or CRITICAL with a sorted list of issues |
| `get_storage` | `node` (optional) | Each pool with type, used, free and contents; shared storage listed once |
| `get_recent_tasks` | `hours`, `errors_only`, `node`, `limit` | Tasks newest first with result and duration (console sessions left out) |
| `get_node_details` | `node` | CPU, load, memory, kernel, Proxmox version, pending updates, disks with SMART health |
| `list_guests` | `guest_type` (all, vm, ct), `status` (any, running, stopped), `search`, `node`, `include_templates` | Guests with status, CPU, memory, disk |
| `get_guest_details` | `name_or_id` | Everything about one guest, including IPs and snapshots |
| `get_guest_ips` | `name_or_id` (optional) | IPs of one guest, or of every running guest |
| `get_backup_status` | `name_or_id` (optional) | Jobs, uncovered guests and newest backup per guest; or one guest's last 10 backups |
| `list_snapshots` | `name_or_id` | Snapshots with time, age and description |
| `get_usage_history` | `name` (node or guest), `timeframe` (hour, day, week, month, year) | Average and peak with the time of the peak |
| `get_access_overview` | none | Users, tokens, groups, custom roles, cluster firewall |
| `check_connection` | none | Each configured host: reachable, token accepted, Proxmox version |
| `guest_power` | `name_or_id`, `action` (start, shutdown, reboot, stop) | Result of the action (actions must be on) |
| `create_snapshot` | `name_or_id`, `snapshot_name`, `description` | Result of the snapshot (actions must be on) |
| `show_cluster_dashboard` | none | A visual dashboard in the chat, plus a short summary for the model |

## Example Questions

- "How is the Proxmox cluster doing? Flag anything wrong."
- "What's the IP of open-webui?"
- "Which containers are running on host03?"
- "Has every VM been backed up this week?"
- "Did anything fail overnight?"
- "Was pve-host01 busy last night? When did CPU peak?"
- "Are there updates waiting on any node?"
- "Show me the cluster dashboard."
- "Take a snapshot of open-webui before I upgrade it." (actions on)

## Actions and Safety

Actions are off until an admin turns on `ENABLE_ACTIONS`. When on:

- Only Open WebUI admins can run them (`ACTIONS_ADMIN_ONLY`).
- Each action opens a confirmation dialog in the chat naming the guest, its node and the action. Nothing happens unless you confirm. If the browser is closed, the action is cancelled.
- A guest that is already in the requested state, a template, a locked guest, or a guest on an offline node is refused before any dialog.
- A write that times out is never retried on another host, so an action cannot run twice.
- `stop` is a hard power off and the dialog says so. Prefer `shutdown`.

For the strongest protection, give the token only the permissions you want the model to have, rather than a full `root@pam` token.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "ProxmoxWeaver is not set up yet" | Fill in `PROXMOX_HOST`, `PROXMOX_TOKEN_ID` and `PROXMOX_TOKEN_SECRET` |
| 401 / token rejected | Wrong or old secret, or the token was deleted. Run `check_connection` |
| 403 / permission denied | A token with privilege separation needs its own permissions under Datacenter > Permissions |
| "Could not reach any Proxmox host" | Check the host list and port. Add a second node so another can answer when one is down |
| A guest shows status `unknown` | Its node is offline |
| A VM's IP is unknown | Install and start `qemu-guest-agent` in the VM and enable the agent in its Options |
| The model stops partway with no answer | The context is full. Raise Context Length, and enable only the tools the chat needs |
| The model makes up arguments | Use Native function calling and a model with tool support |

## Changelog

### Version 3.0.2 (2026-10-26)

- Guest names with filler words now match: "budget VM", "the open webui container" and "silas server" find pve-budget, open-webui and pve-docker-silas

### Version 3.0.1 (2026-10-26)

- The dashboard's summary for the model now tells it the dashboard is already on screen, so small models stop printing the raw data as JSON or tags

### Version 3.0.0 (2026-10-26)

- Rewritten as async with `httpx`; `proxmoxer` removed
- Cluster-wide lists use `/cluster/resources`, so an offline node no longer breaks them
- Host failover across a comma-separated `PROXMOX_HOST` list
- Every argument documented with `:param` so the model knows what to pass
- Status updates in the chat while each function runs
- New: `get_health_report`, `get_guest_ips`, `get_backup_status`, `get_usage_history`, `show_cluster_dashboard`
- New optional actions: `guest_power`, `create_snapshot`, with admin-only and confirmation gates
- Token secret masked in the settings screen; times shown in the user's time zone
- Function changes from 2.x:
  - `list_all_vms`, `list_all_containers`, `list_vms`, `list_containers`, `list_templates` → `list_guests`
  - `get_vm_details`, `get_container_details`, `get_vm_status`, `get_container_status`, `get_vm_network` → `get_guest_details`
  - `get_cluster_status`, `list_nodes` → `get_cluster_overview`
  - `get_node_status` → `get_node_details`, or `get_cluster_overview` for all nodes
  - `list_storage_pools`, `get_storage_details`, `get_node_storage`, `get_nfs_storages` → `get_storage`
  - `list_backups` → `get_backup_status`
  - `list_recent_tasks`, `get_cluster_log` → `get_recent_tasks`
  - `list_users`, `list_groups`, `list_roles`, `get_firewall_status` → `get_access_overview` (per-guest firewall flags are in `get_guest_details`)
  - `help` removed; the function descriptions now carry that information

### Version 2.0.2 (2025-10-19)

- Complete rewrite with cluster-wide VM and container management, node and cluster health, storage (including NFS details), tasks, snapshots, templates, users and permissions, network and firewall information, and a help system

### Version 1.2.0

- Initial release with basic VM and container listing and status checks

## Contributing

Issues and pull requests are welcome at <https://github.com/PureGrain/openwebui-stuff>.

## License

MIT License. See the LICENSE file in the repository root. A commercial license is also available; see COMMERCIAL-LICENSE.txt.
