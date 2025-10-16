# ProxmoxWeaver

ProxmoxWeaver is an OpenWebUI tool for managing and monitoring Proxmox VMs, containers, nodes, storage, backups, users, permissions, and more.

## Features

- **VM & Container Visibility**: List all VMs/containers (cluster-wide or per node), show running/stopped status, resource usage, details (name, ID, status, uptime, IP, OS type).
- **Node & Cluster Health**: List all nodes with status, health, load, resource usage, details (name, version, roles, uptime).
- **Storage & Backup**: List all storage pools (type, usage, available space), show storage status, attached devices, recent backups.
- **Task & Event Monitoring**: List recent tasks (migrations, backups, snapshots, etc.), show task status, logs, errors, recent cluster events.
- **Snapshots & Templates**: List VM/container snapshots, show snapshot details, list available templates for creation.
- **User & Permission Overview**: List users, roles, permissions per user/role, API tokens and scopes.
- **Network & Console**: Show VM/container network info (IP, MAC, bridge, firewall status), list active console sessions (VNC/SPICE).
- **Help & Troubleshooting**: List available commands/features, troubleshooting tips for common errors.

## Usage

1. Place your API credentials in the configuration (see `Valves` class in `test_weaver.py`).
2. Use the tool via OpenWebUI to run any of the available commands/methods.
3. Example command: `list_cluster_vms_and_containers_grouped()`

## Authentication

- Requires a Proxmox API token with sufficient permissions.
- Example config:
  - `PROXMOX_HOST`: `https://your-proxmox-host:8006`
  - `PROXMOX_USER`: `root@pam`
  - `PROXMOX_TOKEN_ID`: `your-token-id`
  - `PROXMOX_TOKEN_SECRET`: `your-token-secret`
  - `VERIFY_SSL`: `False` (if using self-signed certs)

## Troubleshooting

- If IP addresses are missing, ensure the QEMU guest agent is installed and running for VMs, and containers are started.
- Templates and stopped containers do not have IPs assigned by Proxmox.
- Check API token permissions if you receive authentication errors.
- For SSL errors, set VERIFY_SSL to False in configuration if using self-signed certificates.
- If you see 'error' in output, check the Proxmox API endpoint and network connectivity.

## Example Output

```bash
{
  "pve-host01": {
    "vms": [
      {"vmid": 101, "network": {"ip": "192.168.1.10", "mac": "BC:24:11:XX:XX:XX", "bridge": "vmbr0", "firewall": false}},
      ...
    ],
    "containers": [
      {"vmid": 201, "network": {"ip": "192.168.1.20", "mac": "BC:24:11:YY:YY:YY", "bridge": "vmbr0", "firewall": false}},
      ...
    ],
    "consoles": []
  }
}
```

## License

MIT
