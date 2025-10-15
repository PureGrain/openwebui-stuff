# ProxmoxWeaver

ProxmoxWeaver is a powerful tool for managing Proxmox VMs, containers, and nodes seamlessly from OpenWebUI. It provides an intuitive interface for interacting with your Proxmox cluster, making it easier to monitor and manage resources.

## Features

- List all VMs and containers across the cluster with their status.
- Get resource usage for specific nodes or all nodes.
- Retrieve resource usage for specific VMs or containers.
- Get a summary of the entire Proxmox cluster.
- Handles SSL verification for self-signed certificates.
- Comprehensive error handling for connection, authentication, and API issues.

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/PureGrain/openwebui-stuff.git
   ```

2. Navigate to the `proxmoxweaver` directory:

   ```bash
   cd tools/proxmoxweaver
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Update the `Valves` class in `proxmoxweaver.py` with your Proxmox credentials:

```python
class Valves(BaseModel):
    PROXMOX_HOST: str = "https://192.168.1.100:8006"
    PROXMOX_USER: str = "root@pam"
    PROXMOX_TOKEN_ID: str = "mytoken"
    PROXMOX_TOKEN_SECRET: str = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    VERIFY_SSL: bool = False
```

## Usage

### List VMs and Containers

```python
proxmox = ProxmoxWeaver(valves)
print(proxmox.list_vms_containers())
```

### Get Node Resources

```python
print(proxmox.get_node_resources(node_name="pve1"))
```

### Get VM Resources

```python
print(proxmox.get_vm_resources(vmid=100, node="pve1"))
```

### Get Cluster Summary

```python
print(proxmox.get_cluster_summary())
```

## Dependencies

- `requests`
- `pydantic`

Install dependencies using pip:

```bash
pip install requests pydantic
```

## License

This project is licensed under the MIT License. See the [LICENSE](../../LICENSE) file for details.

# ProxmoxWeaver Tool (Class: Tools)

## Overview

ProxmoxWeaver is an OpenWebUI tool for managing Proxmox VMs, containers, nodes, and storage directly from chat prompts. It provides resource summaries, historical stats, and NAS storage info, making it easy to interact with your Proxmox cluster using natural language.

## How the Code Works

- **Class Name:** `Tools` (required for OpenWebUI tool recognition)

- **Configuration:**

  - Uses `Valves` and `UserValves` classes for API credentials and settings.
  - Requires your Proxmox API host, user, token ID, token secret, and SSL verification flag.

- **Main Methods:**

  - `get_storage_summary(node=None, nas_only=False)`: Lists storage pools, NAS info, usage, and snapshot counts.
  - `get_historical_stats(target, target_id, node=None, timeframe="hour")`: Fetches historical CPU, memory, and disk stats for a VM or node.
  - Other methods (not shown) may include VM/container listing, node health, etc.

- **API Calls:**

  - Uses the Proxmox REST API via HTTP requests.
  - Handles errors gracefully and returns structured results.

## How to Use from the Prompt

### 1. Set Up Your API Credentials

Before using the tool, set your Proxmox API details in the UI or via environment variables:

- `PROXMOX_HOST`: e.g., `https://your-proxmox-server:8006`
- `PROXMOX_USER`: e.g., `root@pam`
- `PROXMOX_TOKEN_ID`: e.g., `your-token-id`
- `PROXMOX_TOKEN_SECRET`: e.g., `your-token-secret`
- `VERIFY_SSL`: `true` or `false` (set to `false` if using self-signed certs)

### 2. Example Prompts

#### A. List All Storage Pools (Including NAS Devices)

```text
Show me all storage pools in my Proxmox cluster, including NAS devices. Include usage stats and snapshot counts.
```

Or, for NAS only:

```text
List only NAS-type storage pools for node 'proxmox-node1'.
```

#### B. Get Historical Resource Stats for a VM

```text
Get historical CPU, memory, and disk usage for VM 101 on node 'proxmox-node1' for the past day.
```

Or, for a node:

```text
Show historical resource usage for node 'proxmox-node1' for the last week.
```

#### C. Troubleshooting and Error Handling

If you see an error (e.g., authentication failed), check your API credentials and network connectivity. The tool will return error messages in the output.

## Output Format

- Results are returned as lists of dictionaries, with clear keys for each resource (e.g., `Storage`, `Type`, `Total (GB)`, `Usage (%)`, etc.).
- Warnings or errors are included in the output if data is missing or API calls fail.

## Advanced Usage

- You can filter by node, storage type, or timeframe using prompt details.
- Combine multiple requests in one prompt for summary views (e.g., "Show me storage and VM stats for node 'proxmox-node1'").

## Troubleshooting

- **Tool not recognized?** Ensure the class is named `Tools`.
- **API errors?** Double-check your credentials and endpoint URLs.
- **SSL issues?** Set `VERIFY_SSL` to `false` if using self-signed certificates.

## Support & Documentation

- Author: PureGrain at SLA Ops, LLC
- GitHub: [openwebui-stuff](https://github.com/PureGrain/openwebui-stuff)
- License: MIT

## Example Prompt (Copy & Paste)

```text
Show me all storage pools and NAS devices for node 'proxmox-node1', including usage and snapshot counts.
```

Or for VM stats:

```text
Get historical stats for VM 101 on node 'proxmox-node1' for the last week.
```

This README will help you get started and prompt the tool effectively in OpenWebUI. For more advanced features, see the code comments and method docstrings.
