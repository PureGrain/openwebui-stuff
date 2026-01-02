# OpenWebUI Stuff

[![GitHub Sponsors](https://img.shields.io/github/sponsors/PureGrain?label=Sponsor&logo=GitHub-Sponsors&style=for-the-badge)](https://github.com/sponsors/PureGrain)
[![Build & Scan](https://github.com/PureGrain/openwebui-stuff/actions/workflows/build-and-scan.yml/badge.svg)](https://github.com/PureGrain/openwebui-stuff/actions/workflows/build-and-scan.yml)
[![Last Commit](https://img.shields.io/github/last-commit/PureGrain/openwebui-stuff)](https://github.com/PureGrain/openwebui-stuff/commits/main)
[![Repo Size](https://img.shields.io/github/repo-size/PureGrain/openwebui-stuff)](https://github.com/PureGrain/openwebui-stuff)
[![Issues](https://img.shields.io/github/issues/PureGrain/openwebui-stuff)](https://github.com/PureGrain/openwebui-stuff/issues)

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

## License

This project is dual-licensed under the following terms:

- **MIT License**: For open-source use. See the [LICENSE](LICENSE) file for details.
- **Commercial License**: For proprietary use. See the [COMMERCIAL-LICENSE.txt](COMMERCIAL-LICENSE.txt) file for details.

For commercial licensing inquiries, please contact: [Your Email or Website]

---
For more details, see the README in each folder.
Made with ⏰ for Open WebUI
