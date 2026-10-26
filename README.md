# OpenWebUI Stuff

[![GitHub Sponsors](https://img.shields.io/github/sponsors/PureGrain?label=Sponsor&logo=GitHub-Sponsors&style=for-the-badge)](https://github.com/sponsors/PureGrain)
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

- [ProxmoxWeaver](tools/proxmoxweaver/README.md) (v3): Proxmox VE monitoring and safe management for OpenWebUI. Async, no extra packages, and keeps working when a node is down. Features include:
  - Cluster Overview and Health Report: nodes, quorum, storage, failing disks, failed tasks, pending updates and missing backups, flagged in one call
  - Guests by Name: list, details and live IP addresses for VMs and containers, no node or VMID needed
  - Backups: scheduled jobs, guests in no job, newest backup per guest with its age
  - Nodes and History: CPU, load, kernel, updates, SMART health, and average and peak usage over time
  - Tasks, Snapshots and Access: recent tasks with results, snapshots, users, tokens and firewall state
  - Visual Dashboard: node cards and a guest table drawn in the chat
  - Optional Actions: start, shutdown, reboot, stop and snapshot, off by default and confirmed in the chat
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
