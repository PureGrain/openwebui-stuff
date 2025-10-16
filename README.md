# openwebui-stuff

Central hub for PureGrain's OpenWebUI tools, models, functions, and prompt assets.

## Structure

- `functions/` — Utility or core logic modules
- `models/` — ML models or data abstractions
- `prompts/` — Prompt templates and engineering assets
- `tools/` — Specialized tools for OpenWebUI

## Finished Tools

- [ProxmoxWeaver](tools/proxmoxweaver/README.md): Cluster-wide Proxmox monitoring and management tool for OpenWebUI. Features include:
  - VM & Container Visibility: List all VMs/containers (status, resource usage, details)
  - Node & Cluster Health: Node status, health, load, uptime, version, roles
  - Storage & Backup: Storage pools, usage, attached devices, recent backups
  - Task & Event Monitoring: Recent tasks (migrations, backups, snapshots), logs, errors, cluster events
  - Snapshots & Templates: VM/container snapshots, details, available templates
  - User & Permission Overview: Users, roles, permissions, API tokens
  - Network & Console: VM/container network info (IP, MAC, bridge, firewall), active console sessions
  - Help & Troubleshooting: Command list and tips for common errors
- [TimeWeaver](tools/timeweaver/README.md): Timezone-aware date/time tool with DST intelligence and easy import via JSON
- [WeatherWeaver](tools/weatherweaver/README.md): Enhanced weather tool with comprehensive data from Open-Meteo (free, no API key required)

## How to Use

Refer to each tool's README for installation and usage instructions.

---
For more details, see the README in each folder.
Made with ⏰ for Open WebUI
