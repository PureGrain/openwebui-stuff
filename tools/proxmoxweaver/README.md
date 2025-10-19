# ProxmoxWeaver - Comprehensive Proxmox Management Tool for OpenWebUI

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage Examples](#usage-examples)
- [Function Reference](#function-reference)
- [Support](#support)
- [License](#license)

---

## Overview

ProxmoxWeaver is a powerful, comprehensive Proxmox management tool designed specifically for OpenWebUI. It provides full access to your Proxmox cluster's capabilities through an easy-to-use interface, offering extensive monitoring, management, and troubleshooting features.

**Version:** 2.0.2
**Author:** PureGrain at SLA Ops, LLC
**License:** MIT

---

### 💖 Support This Project

If ProxmoxWeaver has made your Proxmox management easier or saved you time, consider supporting its continued development! Your sponsorship helps cover development costs and motivates me to keep adding new features and improvements. Whether it's a coffee's worth or more, every contribution is deeply appreciated and keeps this project alive and growing.

🎉 **[Become a Sponsor on GitHub](https://github.com/sponsors/PureGrain)**

📦 **[Get the Latest Version](https://github.com/PureGrain/my-openwebui/tree/main/tools/proxmoxweaver)** - Stay updated with new features and improvements!

---

## Features

### 🖥️ VM & Container Management

- **List All VMs**: View all virtual machines across all nodes with detailed resource usage
- **List All Containers**: View all LXC containers with comprehensive information
- **Detailed VM/Container Info**: Get in-depth configuration and status details
- **Resource Monitoring**: Real-time CPU, memory, disk, and network usage statistics

### 📊 Node & Cluster Health

- **Cluster Overview**: Complete cluster health summary with resource aggregation
- **Node Status**: Detailed node health, uptime, and performance metrics
- **Resource Distribution**: View how resources are allocated across the cluster
- **Load Monitoring**: Track load averages and performance indicators

### 💾 Storage & Backup Management

- **Storage Pools**: List all storage pools with usage statistics
- **NFS Mount Details**: Get complete NFS server, export path, and mount status
- **Node Storage**: View storage pools accessible from specific nodes
- **Backup Management**: View, manage, and monitor backups across the cluster
- **Storage Health**: Monitor storage availability and performance
- **Content Management**: Browse storage content including ISOs, templates, and backups

### 📋 Task & Event Monitoring

- **Recent Tasks**: Track all recent operations with status and completion times
- **Cluster Logs**: Access cluster-wide event logs
- **Task History**: Review completed, running, and failed tasks
- **Audit Trail**: Monitor user actions and system events

### 📸 Snapshots & Templates

- **Snapshot Management**: List and manage VM/container snapshots
- **Template Library**: Browse available templates for quick deployment
- **Snapshot Details**: View snapshot creation times, sizes, and RAM inclusion

### 👥 User & Access Control

- **User Management**: List all users with their status and permissions
- **Group Management**: View user groups and memberships
- **Role Overview**: Understand available roles and privileges
- **Token Management**: Monitor API tokens and access methods

### 🌐 Network & Security

- **Network Configuration**: View VM/container network settings
- **Firewall Status**: Check firewall rules and policies
- **Network Interfaces**: List network bridges and configurations
- **IP Management**: Track IP assignments and MAC addresses

### 🛠️ Help & Troubleshooting

- **Built-in Help**: Comprehensive command reference
- **Connection Testing**: Verify API connectivity
- **Error Handling**: Detailed error messages with suggestions
- **Smart Caching**: Efficient API connection management

## Installation

### Requirements

- OpenWebUI version 0.6.34 or higher
- Proxmox Virtual Environment (PVE) cluster
- Python package: `proxmoxer`
- API token with appropriate permissions

### Setup Steps

1. **Install the proxmoxer library** in your OpenWebUI environment:

   ```bash
   pip install proxmoxer
   ```

2. **Create a Proxmox API Token:**
   - Log into Proxmox web interface
   - Navigate to Datacenter → Permissions → API Tokens
   - Create a new token (note the token ID and secret)
   - Ensure the token has appropriate permissions

3. **Import the tool** into OpenWebUI:
   - Go to Workspace → Tools in OpenWebUI
   - Click "Import Tool"
   - Upload the `proxmoxweaver.py` file

4. **Configure the valves** in OpenWebUI:
   - `PROXMOX_HOST`: Your Proxmox server address (e.g., `192.168.1.1:8006`)
   - `PROXMOX_USER`: Username (e.g., `root@pam`)
   - `PROXMOX_TOKEN_ID`: Your API token ID
   - `PROXMOX_TOKEN_SECRET`: Your API token secret
   - `VERIFY_SSL`: Set to `true` if using valid SSL certificates
   - `CACHE_TIMEOUT`: Connection cache timeout in seconds (default: 60)

## Usage Examples

### Check Connection

```python
check_connection()
```

Returns connection status and Proxmox version information.

### Get Cluster Overview

```python
get_cluster_status()
```

Returns comprehensive cluster health including:

- Node status summary
- Total resources (CPU, memory, storage)
- VM and container counts
- Quorum status

### List All VMs with Details

```python
list_all_vms()
```

Returns all VMs across the cluster with:

- Resource usage (CPU, memory, disk)
- Current status and uptime
- Node location

### Get Specific VM Details

```python
get_vm_details(node="pve-node1", vmid=100)
```

Returns detailed information about VM 100 including:

- Full configuration
- Network settings
- Resource allocation
- Snapshot count

### Monitor Recent Tasks

```python
list_recent_tasks(limit=20)
```

Shows the 20 most recent tasks with status and timing information.

### View Storage Pools

```python
list_storage_pools()
```

Lists all storage pools with:

- Type and status
- Usage statistics
- Content types
- Node availability

### List Backups

```python
list_backups()
# or filter by storage/node
list_backups(storage="local", node="pve-node1")
```

### Check Node Health

```python
get_node_status("pve-node1")
# or get all nodes
get_node_status()
```

### View Snapshots

```python
list_snapshots(node="pve-node1", vmid=100, vm_type="qemu")
# For containers, use vm_type="lxc"
```

### Get Network Configuration

```python
get_vm_network(node="pve-node1", vmid=100, vm_type="qemu")
```

### Check Firewall Status

```python
# For node firewall
get_firewall_status(node="pve-node1")
# For VM firewall
get_firewall_status(node="pve-node1", vmid=100)
```

### Get Help

```python
help()
```

Displays all available commands with descriptions.

## Command Reference

### Connection & Status

- `check_connection()` - Test API connectivity
- `help()` - Display command reference

### Cluster Management

- `get_cluster_status()` - Overall cluster health
- `get_node_status([node])` - Node status (optional: specific node)
- `get_cluster_log([max_lines])` - Recent cluster logs

### VM & Container Management

- `list_all_vms()` - All VMs across cluster
- `list_all_containers()` - All containers across cluster
- `get_vm_details(node, vmid)` - Detailed VM information
- `get_container_details(node, vmid)` - Detailed container information

### Storage & Backup

- `list_storage_pools()` - All storage pools
- `list_backups([storage], [node])` - List backups (optional filters)

### Tasks & Monitoring

- `list_recent_tasks([node], [limit])` - Recent tasks

### Snapshots & Templates

- `list_snapshots(node, vmid, [vm_type])` - VM/container snapshots
- `list_templates()` - Available templates

### Access Control

- `list_users()` - All users
- `list_groups()` - All groups  
- `list_roles()` - All roles

### Network & Security

- `get_vm_network(node, vmid, [vm_type])` - Network configuration
- `get_firewall_status(node, [vmid])` - Firewall status

### Legacy Methods (Backward Compatibility)

- `list_nodes()` - List nodes (basic)
- `list_vms(node)` - List VMs on node (basic)
- `list_containers(node)` - List containers on node (basic)
- `get_vm_status(node, vmid)` - VM status (basic)
- `get_container_status(node, vmid)` - Container status (basic)

## Features in Detail

### Smart Connection Caching

The tool implements intelligent API connection caching to reduce overhead and improve performance. Connections are reused within the cache timeout period.

### Comprehensive Error Handling

All methods include proper error handling with informative messages to help diagnose issues quickly.

### Human-Readable Formatting

- Bytes are automatically formatted (KB, MB, GB, etc.)
- Uptime is displayed in days/hours/minutes
- Percentages are calculated and displayed clearly
- Timestamps are formatted in readable date/time format

### Resource Monitoring

Track resource usage across your entire cluster:

- CPU utilization percentages
- Memory usage with free/used/total
- Disk usage and I/O statistics
- Network traffic in/out

### Flexible Filtering

Many commands support optional parameters for filtering:

- Filter tasks by node
- Filter backups by storage or node
- Get specific node status or all nodes

## Troubleshooting

### Connection Issues

If you're having connection problems:

1. Run `check_connection()` to test connectivity
2. Verify your Proxmox host address includes the port (usually 8006)
3. Check that your API token has appropriate permissions
4. Ensure network connectivity between OpenWebUI and Proxmox

### Permission Errors

If you encounter permission errors:

1. Verify your API token has the necessary privileges
2. Check role assignments in Proxmox
3. Ensure the token is not expired

### SSL Certificate Issues

If you get SSL errors:

1. Set `VERIFY_SSL` to `false` for self-signed certificates
2. Or import your CA certificate to the system trust store

## Contributing

Contributions are welcome! Please submit issues and pull requests at:
<https://github.com/PureGrain/my-openwebui>

## Support

For support and sponsorship:

- GitHub Sponsors: <https://github.com/sponsors/PureGrain>
- Repository: <https://github.com/PureGrain/my-openwebui/tree/main/tools/proxmoxweaver>

## Changelog

### Version 2.0.2 (2025-10-19)

- Complete rewrite with comprehensive functionality
- Added cluster-wide VM and container management
- Implemented node and cluster health monitoring
- Enhanced storage management with NFS mount details
- New storage methods: get_storage_details(), get_node_storage(), get_nfs_storages()
- Support for NFS, CIFS, GlusterFS, iSCSI, and other storage types
- Implemented task and event monitoring
- Added snapshot and template management
- Implemented user and permission overview
- Added network and firewall information
- Included comprehensive help system
- Improved error handling and caching
- Maintained backward compatibility

### Version 1.2.0

- Initial release with basic VM and container listing
- Basic status checking functionality

## License

MIT License - see LICENSE file for details

---

## Function Reference

This section provides a quick reference for all available functions in ProxmoxWeaver, along with their descriptions and usage examples.

### VM Management Functions

- **`get_vm_list(host: str)`**
  - **Description**: Return a list of all VMs running on the specified host.
  - **Example**:

    ```python
    get_vm_list(host="pve-node1")
    ```

### Cluster Management Functions

- **`get_cluster_info(host: str)`**
  - **Description**: Retrieve information about the whole cluster (nodes, status, version, etc.).
  - **Example**:

    ```python
    get_cluster_info(host="pve-node1")
    ```

### Storage Management Functions

- **`get_storage_info(host: str, storage: str)`**
  - **Description**: Show detailed information for a particular storage pool (type, size, used space).
  - **Example**:

    ```python
    get_storage_info(host="pve-node1", storage="local")
    ```

### Network Management Functions

- **`get_network_info(host: str)`**
  - **Description**: List network interfaces and their configurations on the host.
  - **Example**:

    ```python
    get_network_info(host="pve-node1")
    ```

### Task Management Functions

- **`get_task_info(host: str)`**
  - **Description**: Return the current list of tasks/operations in progress on the host.
  - **Example**:

    ```python
    get_task_info(host="pve-node1")
    ```

### Host Information Functions

- **`get_host_info(host: str)`**
  - **Description**: General host information (OS, kernel, uptime, etc.).
  - **Example**:

    ```python
    get_host_info(host="pve-node1")
    ```

... (Include all other functions in a similar format) ...
