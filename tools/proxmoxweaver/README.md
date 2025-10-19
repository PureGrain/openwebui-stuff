# ProxmoxWeaver v1.2.0 - Proxmox OpenWebUI Tool

A robust tool for managing and monitoring Proxmox Virtual Environment through OpenWebUI using the proxmoxer library.

## Requirements

Before using this tool, ensure you have the following installed:

```bash
pip install proxmoxer
pip install pydantic
```

## Current Version: v1.2.0

The latest stable version is `proxmoxweaver_v1.2.py` which uses dynamic imports to work seamlessly with OpenWebUI.

## History & Issues Resolved

### Original Implementation Issues
The initial versions of ProxmoxWeaver faced several challenges:

1. **Manual HTTP Requests**: The original implementation used raw `requests` library calls, which required manual handling of:
   - Authentication tokens
   - Session management
   - URL construction
   - Error handling for each endpoint

2. **OpenWebUI Import Validation**: OpenWebUI performs module-level import validation that would fail with direct proxmoxer imports, showing errors like:
   ```
   [ERROR: ProxmoxAPI (https backend for https://https:8006/api2/json) is not a module, class, method, or function.]
   ```

3. **URL Formatting Issues**: Earlier versions had problems with:
   - Double protocol prefixes (`https://https://`)
   - Incorrect default values with protocols included
   - Port configuration mixed with host values

### Why We Moved to Proxmoxer

The `proxmoxer` library provides:
- **Pythonic API**: Clean, chainable API calls like `proxmox.nodes(node).qemu.get()`
- **Built-in Authentication**: Handles API tokens and session management automatically
- **Error Handling**: Provides structured error responses
- **Maintained Library**: Actively maintained and widely used in the Proxmox community

### The v1.2.0 Solution

To resolve OpenWebUI's import validation issues while using proxmoxer, we:
1. **Dynamic Imports**: Import proxmoxer inside each method call using `importlib`
2. **Module Caching**: Check if proxmoxer is already loaded to avoid redundant imports
3. **Error Wrapping**: All API calls wrapped in try/except blocks for graceful failure
4. **Clean Configuration**: Separated host and port configuration with clear defaults

## Installation in OpenWebUI

1. Navigate to **Workspace** → **Tools** in OpenWebUI
2. Click **"+ Add Tool"**
3. Upload or paste the contents of `proxmoxweaver_v1.2.py`
4. Configure the Valves (settings) with your Proxmox credentials

## Configuration

Configure these values in the OpenWebUI Valves interface:

| Setting | Example Value | Description |
|---------|--------------|-------------|
| **PROXMOX_HOST** | `192.168.1.100` | Proxmox server IP or hostname (NO https://) |
| **PROXMOX_USER** | `root@pam` | Username with realm |
| **PROXMOX_TOKEN_ID** | `openwebui-token` | Your API token ID |
| **PROXMOX_TOKEN_SECRET** | `xxxxxxxx-xxxx-xxxx` | Your API token secret |
| **VERIFY_SSL** | `False` | Set to False for self-signed certificates |

### Creating an API Token in Proxmox

1. Log into Proxmox web interface
2. Navigate to **Datacenter** → **Permissions** → **API Tokens**
3. Click **Add** to create a new token
4. Select your user (e.g., `root@pam`)
5. Enter a Token ID (e.g., `openwebui-token`)
6. **Important**: Uncheck "Privilege Separation" for full access
7. Click **Add** and copy the secret (shown only once!)

## Available Commands

Once configured, you can use these commands in OpenWebUI chat:

- `list_nodes` - List all nodes in the Proxmox cluster
- `list_vms("node-name")` - List all VMs on a specific node
- `list_containers("node-name")` - List all containers on a specific node
- `get_vm_status("node-name", vmid)` - Get status of a specific VM
- `get_container_status("node-name", vmid)` - Get status of a specific container

### Example Usage

```
User: list_nodes
Assistant: Here are the available Proxmox nodes...

User: list_vms("pve")
Assistant: Here are the VMs on node 'pve'...

User: get_vm_status("pve", 100)
Assistant: VM 100 status on node 'pve'...
```

## Troubleshooting

### Common Issues

1. **"Module 'proxmoxer' not found"**
   - Solution: Install proxmoxer with `pip install proxmoxer`

2. **"Authentication failed"**
   - Verify your API token is correct
   - Ensure the token has appropriate permissions
   - Check that the user account is enabled

3. **"Connection failed"**
   - Verify PROXMOX_HOST contains only IP/hostname (no https://)
   - Check that port 8006 is accessible
   - Verify network connectivity to Proxmox server

4. **SSL Certificate Errors**
   - Set VERIFY_SSL to `False` in configuration

## File Structure

```
tools/proxmoxweaver/
├── README.md                      # This file
├── proxmoxweaver_v1.2.py         # Current stable version
├── test_v1.2.py                  # Test script for v1.2
└── [legacy files]                # Previous versions for reference
```

## Development

### Testing Locally

To test the tool locally before importing to OpenWebUI:

```bash
cd tools/proxmoxweaver
python test_v1.2.py
```

### Contributing

Contributions are welcome! Please ensure any changes:
- Maintain the dynamic import pattern to work with OpenWebUI
- Include proper error handling
- Update this README with any new features

## Technical Details

### How Dynamic Imports Work

The key innovation in v1.2.0 is the use of dynamic imports within each method:

```python
def list_nodes(self):
    import sys
    import importlib
    if 'proxmoxer' not in sys.modules:
        proxmoxer = importlib.import_module('proxmoxer')
    else:
        proxmoxer = sys.modules['proxmoxer']
```

This approach:
- Bypasses OpenWebUI's module-level import validation
- Only loads proxmoxer when a method is actually called
- Caches the module after first load for efficiency

## License

MIT License - See LICENSE file for details

## Author

**PureGrain** at SLA Ops, LLC
- GitHub: [@PureGrain](https://github.com/PureGrain)
- Repository: [openwebui-stuff](https://github.com/PureGrain/my-openwebui/tree/main/tools/proxmoxweaver)

## Support

For issues or questions:
- Open an issue on [GitHub](https://github.com/PureGrain/my-openwebui/issues)
- Check the troubleshooting section above
- Ensure proxmoxer is properly installed

## Version History

- **v1.2.0** (Current) - Dynamic import implementation for OpenWebUI compatibility
- **v2.0.x** - Various attempts with different import strategies (deprecated)
- **v1.0.0** - Original implementation using manual HTTP requests
