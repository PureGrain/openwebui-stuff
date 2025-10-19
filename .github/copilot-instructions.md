# Copilot Instructions for ProxmoxWeaver

This guide helps AI coding agents work productively in the `proxmoxweaver` tool codebase. It summarizes key architecture, workflows, and conventions unique to this project.

## Project Overview
- **Purpose:** OpenWebUI tool for managing and monitoring Proxmox clusters, VMs, containers, nodes, storage, backups, users, permissions, and more.
- **Structure:**
  - `test_weaver.py` — Main tool file, all features implemented as top-level methods in the `Tools` class.
  - `README.md` — Documentation for features, usage, troubleshooting, and examples.

## Key Patterns & Conventions
- **Modularity:** All features are implemented as top-level methods in the `Tools` class.
- **Naming:** Methods are descriptive and match their functionality (e.g., `list_cluster_vms_and_containers_grouped`).
- **Extensibility:** Add new features as new top-level methods in `Tools`.

## Developer Workflows
- **Authentication:** Configure API credentials in the `Valves` class in `test_weaver.py`.
- **Debugging:** Run methods directly via OpenWebUI or Python for testing.
- **Error Handling:** All API calls use `_make_request`, which handles errors and returns structured output.

## Features
- VM & Container Visibility
- Node & Cluster Health
- Storage & Backup
- Task & Event Monitoring
- Snapshots & Templates
- User & Permission Overview
- Network & Console
- Help & Troubleshooting

## Troubleshooting
- Missing IPs: Ensure QEMU guest agent is running for VMs, containers are started.
- Templates/stopped containers: No IPs assigned.
- Authentication errors: Check API token permissions.
- SSL errors: Set VERIFY_SSL to False for self-signed certs.
- Output errors: Check API endpoint and connectivity.

## Example Usage
- Call any method in `Tools` via OpenWebUI or Python.
- Example: `Tools().list_cluster_vms_and_containers_grouped()`

---
*Update this file whenever major architectural or workflow changes occur.*
