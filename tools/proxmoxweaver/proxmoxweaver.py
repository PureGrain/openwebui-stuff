"""
title: ProxmoxWeaver - Comprehensive Proxmox Management Tool
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/openwebui-stuff/tree/main/tools/proxmoxweaver
funding_url: https://github.com/sponsors/PureGrain
version: 2.0.2
license: MIT
required_open_webui_version: 0.6.34
description: Comprehensive Proxmox management tool with full VM, container, node, storage, and cluster monitoring capabilities via OpenWebUI.
"""
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import json

class Tools:
    class Valves(BaseModel):
        PROXMOX_HOST: str = Field(default="192.168.1.1:8006", description="Proxmox host IP:port or hostname:port")
        PROXMOX_USER: str = Field(default="root@pam", description="Proxmox user")
        PROXMOX_TOKEN_ID: str = Field(default="token", description="API token ID")
        PROXMOX_TOKEN_SECRET: str = Field(default="secret", description="API token secret")
        VERIFY_SSL: bool = Field(default=False, description="Verify SSL certificate")
        CACHE_TIMEOUT: int = Field(default=60, description="Cache timeout in seconds")

    def __init__(self):
        self.valves = self.Valves()
        self._api_cache = None
        self._cache_time = None

    # ============= HELPER METHODS =============
    
    def _get_api(self):
        """Get or create cached API connection."""
        try:
            import sys
            import importlib
            from datetime import datetime, timedelta
            
            # Check if we have a cached connection that's still valid
            if self._api_cache and self._cache_time:
                if datetime.now() - self._cache_time < timedelta(seconds=self.valves.CACHE_TIMEOUT):
                    return self._api_cache
            
            # Import proxmoxer
            if 'proxmoxer' not in sys.modules:
                proxmoxer = importlib.import_module('proxmoxer')
            else:
                proxmoxer = sys.modules['proxmoxer']
            
            # Create new API connection
            self._api_cache = proxmoxer.ProxmoxAPI(
                self.valves.PROXMOX_HOST,
                user=self.valves.PROXMOX_USER,
                token_name=self.valves.PROXMOX_TOKEN_ID,
                token_value=self.valves.PROXMOX_TOKEN_SECRET,
                verify_ssl=self.valves.VERIFY_SSL
            )
            self._cache_time = datetime.now()
            
            return self._api_cache
            
        except Exception as e:
            return None, f"API Connection Error: {str(e)}"
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes to human readable format."""
        value = float(bytes_value)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if value < 1024.0:
                return f"{value:.2f} {unit}"
            value /= 1024.0
        return f"{value:.2f} PB"
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime seconds to human readable format."""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def _calculate_percentage(self, used: float, total: float) -> float:
        """Calculate percentage safely."""
        if total == 0:
            return 0.0
        return (used / total) * 100

    # ============= VM & CONTAINER MANAGEMENT =============
    
    def list_all_vms(self) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        List all VMs across all nodes with detailed information.
        Returns comprehensive VM information including resource usage.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            all_vms = []
            nodes = api.nodes.get()
            
            for node in nodes:
                node_name = node['node']
                vms = api.nodes(node_name).qemu.get()
                
                for vm in vms:
                    # Get detailed status for each VM
                    try:
                        status = api.nodes(node_name).qemu(vm['vmid']).status.current.get()
                        vm_info = {
                            "vmid": vm['vmid'],
                            "name": vm.get('name', 'unnamed'),
                            "node": node_name,
                            "status": vm['status'],
                            "cpu": f"{vm.get('cpu', 0):.2%}" if 'cpu' in vm else "0%",
                            "memory": self._format_bytes(vm.get('mem', 0)),
                            "max_memory": self._format_bytes(vm.get('maxmem', 0)),
                            "memory_usage": f"{self._calculate_percentage(vm.get('mem', 0), vm.get('maxmem', 1)):.1f}%",
                            "disk": self._format_bytes(vm.get('disk', 0)),
                            "max_disk": self._format_bytes(vm.get('maxdisk', 0)),
                            "uptime": self._format_uptime(vm.get('uptime', 0)) if vm.get('uptime') else 'stopped',
                            "cpus": status.get('cpus', 1),
                            "pid": vm.get('pid', 'N/A')
                        }
                        all_vms.append(vm_info)
                    except:
                        # Basic info if detailed status fails
                        vm_info = {
                            "vmid": vm['vmid'],
                            "name": vm.get('name', 'unnamed'),
                            "node": node_name,
                            "status": vm['status'],
                            "cpu": f"{vm.get('cpu', 0):.2%}" if 'cpu' in vm else "0%",
                            "memory": self._format_bytes(vm.get('mem', 0)),
                            "uptime": self._format_uptime(vm.get('uptime', 0)) if vm.get('uptime') else 'stopped'
                        }
                        all_vms.append(vm_info)
            
            return all_vms if all_vms else [{"message": "No VMs found in cluster"}]
            
        except Exception as e:
            return {"error": f"Failed to list VMs: {str(e)}"}
    
    def list_all_containers(self) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        List all LXC containers across all nodes with detailed information.
        Returns comprehensive container information including resource usage.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            all_containers = []
            nodes = api.nodes.get()
            
            for node in nodes:
                node_name = node['node']
                containers = api.nodes(node_name).lxc.get()
                
                for ct in containers:
                    ct_info = {
                        "vmid": ct['vmid'],
                        "name": ct.get('name', 'unnamed'),
                        "node": node_name,
                        "status": ct['status'],
                        "cpu": f"{ct.get('cpu', 0):.2%}" if 'cpu' in ct else "0%",
                        "memory": self._format_bytes(ct.get('mem', 0)),
                        "max_memory": self._format_bytes(ct.get('maxmem', 0)),
                        "memory_usage": f"{self._calculate_percentage(ct.get('mem', 0), ct.get('maxmem', 1)):.1f}%",
                        "disk": self._format_bytes(ct.get('disk', 0)),
                        "max_disk": self._format_bytes(ct.get('maxdisk', 0)),
                        "uptime": self._format_uptime(ct.get('uptime', 0)) if ct.get('uptime') else 'stopped',
                        "swap": self._format_bytes(ct.get('swap', 0)),
                        "max_swap": self._format_bytes(ct.get('maxswap', 0))
                    }
                    all_containers.append(ct_info)
            
            return all_containers if all_containers else [{"message": "No containers found in cluster"}]
            
        except Exception as e:
            return {"error": f"Failed to list containers: {str(e)}"}
    
    def get_vm_details(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific VM including configuration.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            # Get current status
            status = api.nodes(node).qemu(vmid).status.current.get()
            
            # Get configuration
            config = api.nodes(node).qemu(vmid).config.get()
            
            # Get snapshot list
            try:
                snapshots = api.nodes(node).qemu(vmid).snapshot.get()
            except:
                snapshots = []
            
            details = {
                "vmid": vmid,
                "node": node,
                "name": status.get('name', 'unnamed'),
                "status": status.get('status'),
                "uptime": self._format_uptime(status.get('uptime', 0)) if status.get('uptime') else 'stopped',
                "cpu": {
                    "usage": f"{status.get('cpu', 0):.2%}",
                    "cores": config.get('cores', 1),
                    "sockets": config.get('sockets', 1)
                },
                "memory": {
                    "current": self._format_bytes(status.get('mem', 0)),
                    "maximum": self._format_bytes(status.get('maxmem', 0)),
                    "usage": f"{self._calculate_percentage(status.get('mem', 0), status.get('maxmem', 1)):.1f}%"
                },
                "disk": {
                    "usage": self._format_bytes(status.get('disk', 0)),
                    "maximum": self._format_bytes(status.get('maxdisk', 0)),
                    "read": self._format_bytes(status.get('diskread', 0)),
                    "write": self._format_bytes(status.get('diskwrite', 0))
                },
                "network": {
                    "in": self._format_bytes(status.get('netin', 0)),
                    "out": self._format_bytes(status.get('netout', 0))
                },
                "boot_order": config.get('boot', 'cdn'),
                "bios": config.get('bios', 'seabios'),
                "machine": config.get('machine'),
                "os_type": config.get('ostype', 'other'),
                "snapshots": len(snapshots) if snapshots else 0,
                "agent": config.get('agent', 0),
                "protection": config.get('protection', 0),
                "template": config.get('template', 0)
            }
            
            return details
            
        except Exception as e:
            return {"error": f"Failed to get VM details: {str(e)}"}
    
    def get_container_details(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific container including configuration.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            # Get current status
            status = api.nodes(node).lxc(vmid).status.current.get()
            
            # Get configuration
            config = api.nodes(node).lxc(vmid).config.get()
            
            # Get snapshot list
            try:
                snapshots = api.nodes(node).lxc(vmid).snapshot.get()
            except:
                snapshots = []
            
            details = {
                "vmid": vmid,
                "node": node,
                "name": status.get('name', 'unnamed'),
                "status": status.get('status'),
                "uptime": self._format_uptime(status.get('uptime', 0)) if status.get('uptime') else 'stopped',
                "cpu": {
                    "usage": f"{status.get('cpu', 0):.2%}",
                    "cores": config.get('cores')
                },
                "memory": {
                    "current": self._format_bytes(status.get('mem', 0)),
                    "maximum": self._format_bytes(status.get('maxmem', 0)),
                    "usage": f"{self._calculate_percentage(status.get('mem', 0), status.get('maxmem', 1)):.1f}%",
                    "swap": self._format_bytes(status.get('swap', 0)),
                    "max_swap": self._format_bytes(status.get('maxswap', 0))
                },
                "disk": {
                    "usage": self._format_bytes(status.get('disk', 0)),
                    "maximum": self._format_bytes(status.get('maxdisk', 0)),
                    "read": self._format_bytes(status.get('diskread', 0)),
                    "write": self._format_bytes(status.get('diskwrite', 0))
                },
                "network": {
                    "in": self._format_bytes(status.get('netin', 0)),
                    "out": self._format_bytes(status.get('netout', 0))
                },
                "hostname": config.get('hostname'),
                "ostype": config.get('ostype', 'unmanaged'),
                "arch": config.get('arch', 'amd64'),
                "snapshots": len(snapshots) if snapshots else 0,
                "protection": config.get('protection', 0),
                "template": config.get('template', 0),
                "unprivileged": config.get('unprivileged', 1)
            }
            
            return details
            
        except Exception as e:
            return {"error": f"Failed to get container details: {str(e)}"}

    # ============= NODE & CLUSTER HEALTH =============
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Get overall cluster health and resource summary.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            # Get cluster status
            cluster_status = api.cluster.status.get()
            
            # Get resource summary
            resources = api.cluster.resources.get(type='node')
            
            # Calculate totals
            total_cpu = 0
            total_memory = 0
            total_memory_used = 0
            total_disk = 0
            total_disk_used = 0
            online_nodes = 0
            
            nodes_info = []
            for node in resources:
                if node['type'] == 'node':
                    total_cpu += node.get('maxcpu', 0)
                    total_memory += node.get('maxmem', 0)
                    total_memory_used += node.get('mem', 0)
                    total_disk += node.get('maxdisk', 0)
                    total_disk_used += node.get('disk', 0)
                    
                    if node.get('status') == 'online':
                        online_nodes += 1
                    
                    nodes_info.append({
                        "name": node['node'],
                        "status": node.get('status', 'unknown'),
                        "cpu_usage": f"{node.get('cpu', 0):.1%}" if 'cpu' in node else "0%",
                        "memory_usage": f"{self._calculate_percentage(node.get('mem', 0), node.get('maxmem', 1)):.1f}%",
                        "uptime": self._format_uptime(node.get('uptime', 0)) if node.get('uptime') else 'offline'
                    })
            
            # Get VM and container counts
            vms = api.cluster.resources.get(type='vm')
            vm_count = sum(1 for vm in vms if vm['type'] == 'qemu')
            ct_count = sum(1 for vm in vms if vm['type'] == 'lxc')
            running_vms = sum(1 for vm in vms if vm['type'] == 'qemu' and vm.get('status') == 'running')
            running_cts = sum(1 for vm in vms if vm['type'] == 'lxc' and vm.get('status') == 'running')
            
            cluster_info = {
                "name": cluster_status[0].get('name', 'Proxmox Cluster') if cluster_status else 'Proxmox Cluster',
                "version": cluster_status[0].get('version') if cluster_status else 'unknown',
                "nodes": {
                    "total": len(nodes_info),
                    "online": online_nodes,
                    "details": nodes_info
                },
                "resources": {
                    "cpu": {
                        "total_cores": total_cpu,
                        "usage": f"{(total_memory_used / total_memory * 100):.1f}%" if total_memory > 0 else "0%"
                    },
                    "memory": {
                        "total": self._format_bytes(total_memory),
                        "used": self._format_bytes(total_memory_used),
                        "free": self._format_bytes(total_memory - total_memory_used),
                        "usage": f"{self._calculate_percentage(total_memory_used, total_memory):.1f}%"
                    },
                    "storage": {
                        "total": self._format_bytes(total_disk),
                        "used": self._format_bytes(total_disk_used),
                        "free": self._format_bytes(total_disk - total_disk_used),
                        "usage": f"{self._calculate_percentage(total_disk_used, total_disk):.1f}%"
                    }
                },
                "virtual_machines": {
                    "total": vm_count,
                    "running": running_vms,
                    "stopped": vm_count - running_vms
                },
                "containers": {
                    "total": ct_count,
                    "running": running_cts,
                    "stopped": ct_count - running_cts
                },
                "quorate": cluster_status[0].get('quorate', True) if cluster_status else True
            }
            
            return cluster_info
            
        except Exception as e:
            return {"error": f"Failed to get cluster status: {str(e)}"}
    
    def get_node_status(self, node: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get detailed status and health information for a specific node or all nodes.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            if node:
                # Get specific node status
                node_status = api.nodes(node).status.get()
                node_info = {
                    "node": node,
                    "status": "online",
                    "uptime": self._format_uptime(node_status.get('uptime', 0)),
                    "load_average": node_status.get('loadavg', [0, 0, 0]),
                    "cpu": {
                        "model": node_status.get('cpuinfo', {}).get('model', 'Unknown'),
                        "cores": node_status.get('cpuinfo', {}).get('cpus', 0),
                        "sockets": node_status.get('cpuinfo', {}).get('sockets', 0),
                        "usage": f"{node_status.get('cpu', 0):.1%}"
                    },
                    "memory": {
                        "total": self._format_bytes(node_status.get('memory', {}).get('total', 0)),
                        "used": self._format_bytes(node_status.get('memory', {}).get('used', 0)),
                        "free": self._format_bytes(node_status.get('memory', {}).get('free', 0)),
                        "usage": f"{self._calculate_percentage(node_status.get('memory', {}).get('used', 0), node_status.get('memory', {}).get('total', 1)):.1f}%"
                    },
                    "swap": {
                        "total": self._format_bytes(node_status.get('swap', {}).get('total', 0)),
                        "used": self._format_bytes(node_status.get('swap', {}).get('used', 0)),
                        "free": self._format_bytes(node_status.get('swap', {}).get('free', 0))
                    },
                    "kernel": node_status.get('kversion'),
                    "pve_version": node_status.get('pveversion')
                }
                return node_info
            else:
                # Get all nodes status
                nodes = api.nodes.get()
                nodes_status = []
                
                for n in nodes:
                    try:
                        status = api.nodes(n['node']).status.get()
                        node_info = {
                            "node": n['node'],
                            "status": n.get('status', 'unknown'),
                            "uptime": self._format_uptime(n.get('uptime', 0)) if n.get('uptime') else 'offline',
                            "cpu_usage": f"{n.get('cpu', 0):.1%}" if 'cpu' in n else "0%",
                            "memory": {
                                "used": self._format_bytes(n.get('mem', 0)),
                                "total": self._format_bytes(n.get('maxmem', 0)),
                                "usage": f"{self._calculate_percentage(n.get('mem', 0), n.get('maxmem', 1)):.1f}%"
                            },
                            "disk": {
                                "used": self._format_bytes(n.get('disk', 0)),
                                "total": self._format_bytes(n.get('maxdisk', 0)),
                                "usage": f"{self._calculate_percentage(n.get('disk', 0), n.get('maxdisk', 1)):.1f}%"
                            }
                        }
                        nodes_status.append(node_info)
                    except:
                        nodes_status.append({
                            "node": n['node'],
                            "status": n.get('status', 'unknown'),
                            "error": "Unable to fetch detailed status"
                        })
                
                return nodes_status
                
        except Exception as e:
            return {"error": f"Failed to get node status: {str(e)}"}

    # ============= STORAGE & BACKUP =============
    
    def list_storage_pools(self) -> List[Dict[str, Any]]:
        """
        List all storage pools with usage information.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            storages = api.storage.get()
            storage_list = []
            
            for storage in storages:
                storage_info = {
                    "storage": storage['storage'],
                    "type": storage.get('type', 'unknown'),
                    "enabled": storage.get('enabled', 0),
                    "shared": storage.get('shared', 0),
                    "content": storage.get('content', '').split(',') if storage.get('content') else [],
                    "nodes": storage.get('nodes', 'all')
                }
                
                # Try to get usage information for each storage
                try:
                    # Get storage status from first available node
                    nodes = api.nodes.get()
                    if nodes:
                        node = nodes[0]['node']
                        status = api.nodes(node).storage(storage['storage']).status.get()
                        storage_info.update({
                            "total": self._format_bytes(status.get('total', 0)),
                            "used": self._format_bytes(status.get('used', 0)),
                            "available": self._format_bytes(status.get('avail', 0)),
                            "usage": f"{self._calculate_percentage(status.get('used', 0), status.get('total', 1)):.1f}%",
                            "active": status.get('active', 0)
                        })
                except:
                    storage_info.update({
                        "total": "N/A",
                        "used": "N/A",
                        "available": "N/A",
                        "usage": "N/A",
                        "active": "unknown"
                    })
                
                storage_list.append(storage_info)
            
            return storage_list
            
        except Exception as e:
            return [{"error": f"Failed to list storage pools: {str(e)}"}]
    
    def get_storage_details(self, storage: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific storage pool including NFS mount details.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            # Get storage configuration
            config = api.storage(storage).get()[0]
            
            details = {
                "storage": storage,
                "type": config.get('type', 'unknown'),
                "enabled": config.get('enabled', 0),
                "shared": config.get('shared', 0),
                "content": config.get('content', '').split(',') if config.get('content') else [],
                "nodes": config.get('nodes', 'all')
            }
            
            # Add type-specific details
            storage_type = config.get('type', '').lower()
            
            if storage_type == 'nfs':
                details['nfs'] = {
                    "server": config.get('server', 'N/A'),
                    "export": config.get('export', 'N/A'),
                    "path": config.get('path', 'N/A'),
                    "options": config.get('options', 'N/A')
                }
            elif storage_type == 'cifs':
                details['cifs'] = {
                    "server": config.get('server', 'N/A'),
                    "share": config.get('share', 'N/A'),
                    "username": config.get('username', 'N/A'),
                    "domain": config.get('domain', 'N/A')
                }
            elif storage_type == 'glusterfs':
                details['glusterfs'] = {
                    "server": config.get('server', 'N/A'),
                    "volume": config.get('volume', 'N/A')
                }
            elif storage_type == 'iscsi':
                details['iscsi'] = {
                    "portal": config.get('portal', 'N/A'),
                    "target": config.get('target', 'N/A')
                }
            elif storage_type in ['dir', 'lvm', 'lvmthin', 'zfs', 'zfspool', 'rbd', 'cephfs']:
                details['path'] = config.get('path', 'N/A')
                if storage_type == 'rbd':
                    details['rbd'] = {
                        "pool": config.get('pool', 'N/A'),
                        "monhost": config.get('monhost', 'N/A'),
                        "username": config.get('username', 'N/A')
                    }
            
            # Try to get current usage from a node
            try:
                nodes = api.nodes.get()
                if nodes:
                    node = nodes[0]['node']
                    status = api.nodes(node).storage(storage).status.get()
                    details['status'] = {
                        "total": self._format_bytes(status.get('total', 0)),
                        "used": self._format_bytes(status.get('used', 0)),
                        "available": self._format_bytes(status.get('avail', 0)),
                        "usage": f"{self._calculate_percentage(status.get('used', 0), status.get('total', 1)):.1f}%",
                        "active": status.get('active', 0)
                    }
            except:
                details['status'] = "Unable to fetch current status"
            
            return details
            
        except Exception as e:
            return {"error": f"Failed to get storage details: {str(e)}"}
    
    def get_node_storage(self, node: str) -> List[Dict[str, Any]]:
        """
        Get all storage pools accessible from a specific node with their status.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            storages = api.nodes(node).storage.get()
            storage_list = []
            
            for storage in storages:
                storage_info = {
                    "storage": storage['storage'],
                    "type": storage.get('type', 'unknown'),
                    "active": storage.get('active', 0),
                    "enabled": storage.get('enabled', 0),
                    "shared": storage.get('shared', 0),
                    "content": storage.get('content', '').split(',') if storage.get('content') else [],
                    "total": self._format_bytes(storage.get('total', 0)),
                    "used": self._format_bytes(storage.get('used', 0)),
                    "available": self._format_bytes(storage.get('avail', 0)),
                    "usage": f"{self._calculate_percentage(storage.get('used', 0), storage.get('total', 1)):.1f}%"
                }
                
                # Get detailed status if available
                try:
                    status = api.nodes(node).storage(storage['storage']).status.get()
                    storage_info['status_details'] = {
                        "type": status.get('type', storage.get('type', 'unknown')),
                        "total": status.get('total', 0),
                        "used": status.get('used', 0),
                        "available": status.get('avail', 0),
                        "active": status.get('active', 0)
                    }
                except:
                    pass
                
                storage_list.append(storage_info)
            
            return storage_list
            
        except Exception as e:
            return [{"error": f"Failed to get node storage: {str(e)}"}]
    
    def get_nfs_storages(self) -> List[Dict[str, Any]]:
        """
        Get all NFS storage pools with mount details.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            storages = api.storage.get()
            nfs_storages = []
            
            for storage in storages:
                if storage.get('type', '').lower() == 'nfs':
                    nfs_info = {
                        "storage": storage['storage'],
                        "type": "NFS",
                        "server": storage.get('server', 'N/A'),
                        "export": storage.get('export', 'N/A'),
                        "path": storage.get('path', 'N/A'),
                        "enabled": storage.get('enabled', 0),
                        "shared": storage.get('shared', 0),
                        "content": storage.get('content', '').split(',') if storage.get('content') else [],
                        "nodes": storage.get('nodes', 'all'),
                        "options": storage.get('options', 'defaults')
                    }
                    
                    # Try to get mount status from a node
                    try:
                        nodes = api.nodes.get()
                        if nodes:
                            node = nodes[0]['node']
                            status = api.nodes(node).storage(storage['storage']).status.get()
                            nfs_info['mount_status'] = {
                                "mounted": status.get('active', 0) == 1,
                                "total": self._format_bytes(status.get('total', 0)),
                                "used": self._format_bytes(status.get('used', 0)),
                                "available": self._format_bytes(status.get('avail', 0)),
                                "usage": f"{self._calculate_percentage(status.get('used', 0), status.get('total', 1)):.1f}%"
                            }
                    except:
                        nfs_info['mount_status'] = "Unable to determine mount status"
                    
                    nfs_storages.append(nfs_info)
            
            return nfs_storages if nfs_storages else [{"message": "No NFS storages found"}]
            
        except Exception as e:
            return [{"error": f"Failed to get NFS storages: {str(e)}"}]
    
    def list_backups(self, storage: Optional[str] = None, node: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all backups, optionally filtered by storage or node.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            backups = []
            
            if storage and node:
                # Get backups from specific storage on specific node
                content = api.nodes(node).storage(storage).content.get()
                for item in content:
                    if item.get('content') == 'backup':
                        backup_info = {
                            "volid": item['volid'],
                            "vmid": item.get('vmid'),
                            "node": node,
                            "storage": storage,
                            "size": self._format_bytes(item.get('size', 0)),
                            "format": item.get('format'),
                            "creation_time": datetime.fromtimestamp(item.get('ctime', 0)).strftime('%Y-%m-%d %H:%M:%S') if item.get('ctime') else 'unknown',
                            "notes": item.get('notes', '')
                        }
                        backups.append(backup_info)
            else:
                # Get all backups from all storages on all nodes
                nodes = api.nodes.get()
                storages = api.storage.get()
                
                for node_info in nodes:
                    node_name = node_info['node']
                    for stor in storages:
                        if 'backup' in stor.get('content', ''):
                            try:
                                content = api.nodes(node_name).storage(stor['storage']).content.get()
                                for item in content:
                                    if item.get('content') == 'backup':
                                        backup_info = {
                                            "volid": item['volid'],
                                            "vmid": item.get('vmid'),
                                            "node": node_name,
                                            "storage": stor['storage'],
                                            "size": self._format_bytes(item.get('size', 0)),
                                            "format": item.get('format'),
                                            "creation_time": datetime.fromtimestamp(item.get('ctime', 0)).strftime('%Y-%m-%d %H:%M:%S') if item.get('ctime') else 'unknown',
                                            "notes": item.get('notes', '')
                                        }
                                        backups.append(backup_info)
                            except:
                                continue
            
            return backups if backups else [{"message": "No backups found"}]
            
        except Exception as e:
            return [{"error": f"Failed to list backups: {str(e)}"}]

    # ============= TASK & EVENT MONITORING =============
    
    def list_recent_tasks(self, node: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List recent tasks, optionally filtered by node.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            tasks = []
            
            if node:
                # Get tasks from specific node
                node_tasks = api.nodes(node).tasks.get(limit=limit)
                for task in node_tasks:
                    task_info = {
                        "upid": task.get('upid'),
                        "node": task.get('node'),
                        "pid": task.get('pid'),
                        "pstart": task.get('pstart'),
                        "type": task.get('type'),
                        "status": task.get('status', 'running'),
                        "user": task.get('user'),
                        "starttime": datetime.fromtimestamp(task.get('starttime', 0)).strftime('%Y-%m-%d %H:%M:%S') if task.get('starttime') else 'unknown',
                        "endtime": datetime.fromtimestamp(task.get('endtime', 0)).strftime('%Y-%m-%d %H:%M:%S') if task.get('endtime') else 'running'
                    }
                    tasks.append(task_info)
            else:
                # Get tasks from all nodes
                nodes = api.nodes.get()
                for node_info in nodes:
                    try:
                        node_tasks = api.nodes(node_info['node']).tasks.get(limit=limit // len(nodes))
                        for task in node_tasks:
                            task_info = {
                                "upid": task.get('upid'),
                                "node": task.get('node'),
                                "pid": task.get('pid'),
                                "type": task.get('type'),
                                "status": task.get('status', 'running'),
                                "user": task.get('user'),
                                "starttime": datetime.fromtimestamp(task.get('starttime', 0)).strftime('%Y-%m-%d %H:%M:%S') if task.get('starttime') else 'unknown',
                                "endtime": datetime.fromtimestamp(task.get('endtime', 0)).strftime('%Y-%m-%d %H:%M:%S') if task.get('endtime') else 'running'
                            }
                            tasks.append(task_info)
                    except:
                        continue
            
            # Sort by start time (most recent first)
            tasks.sort(key=lambda x: x['starttime'], reverse=True)
            
            return tasks[:limit] if tasks else [{"message": "No recent tasks found"}]
            
        except Exception as e:
            return [{"error": f"Failed to list tasks: {str(e)}"}]
    
    def get_cluster_log(self, max_lines: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent cluster log entries.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            # Get cluster log
            log_entries = api.cluster.log.get(max=max_lines)
            
            formatted_logs = []
            for entry in log_entries:
                log_info = {
                    "time": datetime.fromtimestamp(entry.get('time', 0)).strftime('%Y-%m-%d %H:%M:%S') if entry.get('time') else 'unknown',
                    "node": entry.get('node', 'cluster'),
                    "user": entry.get('user', 'system'),
                    "message": entry.get('msg', ''),
                    "priority": entry.get('pri', 6),
                    "tag": entry.get('tag', 'system')
                }
                formatted_logs.append(log_info)
            
            return formatted_logs if formatted_logs else [{"message": "No log entries found"}]
            
        except Exception as e:
            return [{"error": f"Failed to get cluster log: {str(e)}"}]

    # ============= SNAPSHOTS & TEMPLATES =============
    
    def list_snapshots(self, node: str, vmid: int, vm_type: str = "qemu") -> List[Dict[str, Any]]:
        """
        List snapshots for a VM or container.
        vm_type should be 'qemu' for VMs or 'lxc' for containers.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            if vm_type == "qemu":
                snapshots = api.nodes(node).qemu(vmid).snapshot.get()
            else:
                snapshots = api.nodes(node).lxc(vmid).snapshot.get()
            
            snapshot_list = []
            for snap in snapshots:
                if snap['name'] != 'current':  # Skip the 'current' entry
                    snap_info = {
                        "name": snap['name'],
                        "description": snap.get('description', ''),
                        "creation_time": datetime.fromtimestamp(snap.get('snaptime', 0)).strftime('%Y-%m-%d %H:%M:%S') if snap.get('snaptime') else 'unknown',
                        "parent": snap.get('parent'),
                        "vmstate": snap.get('vmstate', 0),
                        "ram_included": "Yes" if snap.get('vmstate') else "No"
                    }
                    snapshot_list.append(snap_info)
            
            return snapshot_list if snapshot_list else [{"message": f"No snapshots found for {vm_type} {vmid}"}]
            
        except Exception as e:
            return [{"error": f"Failed to list snapshots: {str(e)}"}]
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """
        List all available templates (VMs and containers marked as templates).
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            templates = []
            nodes = api.nodes.get()
            
            for node in nodes:
                node_name = node['node']
                
                # Check VMs for templates
                vms = api.nodes(node_name).qemu.get()
                for vm in vms:
                    if vm.get('template', 0) == 1:
                        template_info = {
                            "vmid": vm['vmid'],
                            "name": vm.get('name', 'unnamed'),
                            "node": node_name,
                            "type": "qemu",
                            "disk_size": self._format_bytes(vm.get('maxdisk', 0)),
                            "memory": self._format_bytes(vm.get('maxmem', 0)),
                            "cpus": vm.get('cpus', 1)
                        }
                        templates.append(template_info)
                
                # Check containers for templates
                containers = api.nodes(node_name).lxc.get()
                for ct in containers:
                    if ct.get('template', 0) == 1:
                        template_info = {
                            "vmid": ct['vmid'],
                            "name": ct.get('name', 'unnamed'),
                            "node": node_name,
                            "type": "lxc",
                            "disk_size": self._format_bytes(ct.get('maxdisk', 0)),
                            "memory": self._format_bytes(ct.get('maxmem', 0)),
                            "cpus": ct.get('cpus', 1)
                        }
                        templates.append(template_info)
            
            return templates if templates else [{"message": "No templates found in cluster"}]
            
        except Exception as e:
            return [{"error": f"Failed to list templates: {str(e)}"}]

    # ============= USER & PERMISSIONS =============
    
    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users in the Proxmox cluster.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            users = api.access.users.get()
            
            user_list = []
            for user in users:
                user_info = {
                    "userid": user['userid'],
                    "enable": "Enabled" if user.get('enable', 1) == 1 else "Disabled",
                    "expire": datetime.fromtimestamp(user['expire']).strftime('%Y-%m-%d') if user.get('expire', 0) > 0 else 'Never',
                    "firstname": user.get('firstname', ''),
                    "lastname": user.get('lastname', ''),
                    "email": user.get('email', ''),
                    "comment": user.get('comment', ''),
                    "groups": user.get('groups', '').split(',') if user.get('groups') else [],
                    "tokens": user.get('tokens', [])
                }
                user_list.append(user_info)
            
            return user_list if user_list else [{"message": "No users found"}]
            
        except Exception as e:
            return [{"error": f"Failed to list users: {str(e)}"}]
    
    def list_groups(self) -> List[Dict[str, Any]]:
        """
        List all groups in the Proxmox cluster.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            groups = api.access.groups.get()
            
            group_list = []
            for group in groups:
                group_info = {
                    "groupid": group['groupid'],
                    "comment": group.get('comment', ''),
                    "users": group.get('users', '').split(',') if group.get('users') else []
                }
                group_list.append(group_info)
            
            return group_list if group_list else [{"message": "No groups found"}]
            
        except Exception as e:
            return [{"error": f"Failed to list groups: {str(e)}"}]
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """
        List all roles in the Proxmox cluster.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            
            roles = api.access.roles.get()
            
            role_list = []
            for role in roles:
                role_info = {
                    "roleid": role['roleid'],
                    "privs": role.get('privs', '').split(',') if role.get('privs') else [],
                    "special": role.get('special', 0)
                }
                role_list.append(role_info)
            
            return role_list if role_list else [{"message": "No roles found"}]
            
        except Exception as e:
            return [{"error": f"Failed to list roles: {str(e)}"}]

    # ============= NETWORK & CONSOLE =============
    
    def get_vm_network(self, node: str, vmid: int, vm_type: str = "qemu") -> Dict[str, Any]:
        """
        Get network configuration for a VM or container.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            if vm_type == "qemu":
                config = api.nodes(node).qemu(vmid).config.get()
            else:
                config = api.nodes(node).lxc(vmid).config.get()
            
            network_info = {
                "vmid": vmid,
                "node": node,
                "type": vm_type,
                "interfaces": []
            }
            
            # Extract network interfaces
            for key in config:
                if key.startswith('net'):
                    net_config = config[key]
                    interface = {
                        "name": key,
                        "config": net_config
                    }
                    
                    # Parse network configuration string
                    if isinstance(net_config, str):
                        parts = net_config.split(',')
                        for part in parts:
                            if '=' in part:
                                k, v = part.split('=', 1)
                                interface[k] = v
                    
                    network_info["interfaces"].append(interface)
            
            # Try to get IP addresses if agent is running
            if vm_type == "qemu":
                try:
                    agent_info = api.nodes(node).qemu(vmid).agent.get('network-get-interfaces')
                    network_info["agent_network"] = agent_info.get('result', [])
                except:
                    network_info["agent_network"] = "Agent not available"
            
            return network_info
            
        except Exception as e:
            return {"error": f"Failed to get network info: {str(e)}"}
    
    def get_firewall_status(self, node: str, vmid: Optional[int] = None) -> Dict[str, Any]:
        """
        Get firewall status and rules for a node or VM.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            
            if vmid:
                # Get VM firewall status
                options = api.nodes(node).qemu(vmid).firewall.options.get()
                rules = api.nodes(node).qemu(vmid).firewall.rules.get()
            else:
                # Get node firewall status
                options = api.nodes(node).firewall.options.get()
                rules = api.nodes(node).firewall.rules.get()
            
            firewall_info = {
                "target": f"VM {vmid}" if vmid else f"Node {node}",
                "enabled": options.get('enable', 0),
                "policy_in": options.get('policy_in', 'ACCEPT'),
                "policy_out": options.get('policy_out', 'ACCEPT'),
                "log_level": options.get('log_level_in', 'nolog'),
                "rules": []
            }
            
            for rule in rules:
                rule_info = {
                    "pos": rule.get('pos'),
                    "type": rule.get('type'),
                    "action": rule.get('action'),
                    "enable": rule.get('enable', 1),
                    "source": rule.get('source', 'any'),
                    "dest": rule.get('dest', 'any'),
                    "proto": rule.get('proto', 'any'),
                    "dport": rule.get('dport', ''),
                    "sport": rule.get('sport', ''),
                    "comment": rule.get('comment', '')
                }
                firewall_info["rules"].append(rule_info)
            
            return firewall_info
            
        except Exception as e:
            return {"error": f"Failed to get firewall status: {str(e)}"}

    # ============= HELP & TROUBLESHOOTING =============
    
    def help(self) -> Dict[str, Any]:
        """
        Display comprehensive help with all available commands, descriptions, and usage examples.
        """
        help_info = {
            "🔧 ProxmoxWeaver v2.0.0 - Comprehensive Proxmox Management Tool": {
                "Description": "A powerful tool for managing and monitoring your Proxmox cluster through OpenWebUI",
                "Author": "PureGrain at SLA Ops, LLC",
                "Repository": "https://github.com/PureGrain/my-openwebui/tree/main/tools/proxmoxweaver",
                "Latest Version": "Check the repository for updates and new features!"
            },
            
            "💖 Support This Project": {
                "Sponsor": "If ProxmoxWeaver saves you time or makes your work easier, consider supporting its development!",
                "GitHub Sponsors": "https://github.com/sponsors/PureGrain",
                "Message": "Your support helps cover costs and motivates continued development. Every contribution, big or small, is deeply appreciated! 🙏"
            },
            
            "🔌 CONNECTION & STATUS": {
                "check_connection()": {
                    "description": "Test API connectivity to your Proxmox cluster",
                    "usage": "check_connection()",
                    "returns": "Connection status, version info, and diagnostics"
                },
                "help()": {
                    "description": "Display this comprehensive help message",
                    "usage": "help()",
                    "returns": "All available commands with descriptions and examples"
                }
            },
            
            "📊 CLUSTER MANAGEMENT": {
                "get_cluster_status()": {
                    "description": "Get complete cluster health overview with resource summary",
                    "usage": "get_cluster_status()",
                    "returns": "Cluster name, version, node status, total resources (CPU/RAM/Storage), VM/container counts, quorum status"
                },
                "get_node_status(node)": {
                    "description": "Get detailed status and health for specific node or all nodes",
                    "usage": [
                        "get_node_status('pve-node1')  # Specific node details",
                        "get_node_status()  # All nodes summary"
                    ],
                    "returns": "Node uptime, load average, CPU/memory/swap usage, kernel version"
                },
                "get_cluster_log(max_lines)": {
                    "description": "View recent cluster-wide log entries",
                    "usage": "get_cluster_log(50)  # Last 50 log entries",
                    "returns": "Timestamped log entries with node, user, and message details"
                }
            },
            
            "🖥️ VM & CONTAINER MANAGEMENT": {
                "list_all_vms()": {
                    "description": "List all virtual machines across entire cluster with resource usage",
                    "usage": "list_all_vms()",
                    "returns": "VM list with: VMID, name, node, status, CPU/memory/disk usage, uptime"
                },
                "list_all_containers()": {
                    "description": "List all LXC containers across entire cluster",
                    "usage": "list_all_containers()",
                    "returns": "Container list with: VMID, name, node, status, resource usage, swap"
                },
                "get_vm_details(node, vmid)": {
                    "description": "Get comprehensive information about a specific VM",
                    "usage": "get_vm_details('pve-node1', 100)",
                    "returns": "Full VM config: CPU cores, memory, disk, network I/O, snapshots, boot order, OS type"
                },
                "get_container_details(node, vmid)": {
                    "description": "Get comprehensive information about a specific container",
                    "usage": "get_container_details('pve-node1', 101)",
                    "returns": "Full container config: resources, hostname, architecture, privilege level"
                }
            },
            
            "💾 STORAGE & BACKUP": {
                "list_storage_pools()": {
                    "description": "List all storage pools with usage statistics",
                    "usage": "list_storage_pools()",
                    "returns": "Storage name, type, total/used/available space, content types, active status"
                },
                "get_storage_details(storage)": {
                    "description": "Get detailed information about a specific storage pool including NFS mount details",
                    "usage": "get_storage_details('nfs-storage')",
                    "returns": "Complete storage configuration including type-specific details (NFS server, export path, mount options)"
                },
                "get_node_storage(node)": {
                    "description": "Get all storage pools accessible from a specific node with their status",
                    "usage": "get_node_storage('pve-node1')",
                    "returns": "Storage pools on node with usage statistics and mount status"
                },
                "get_nfs_storages()": {
                    "description": "Get all NFS storage pools with mount details across the cluster",
                    "usage": "get_nfs_storages()",
                    "returns": "NFS server, export path, mount status, usage statistics for all NFS mounts"
                },
                "list_backups(storage, node)": {
                    "description": "List backup files with optional filtering",
                    "usage": [
                        "list_backups()  # All backups",
                        "list_backups(storage='local')  # Specific storage",
                        "list_backups(node='pve-node1')  # Specific node"
                    ],
                    "returns": "Backup list with: VMID, size, creation time, storage location, notes"
                }
            },
            
            "📋 TASK & EVENT MONITORING": {
                "list_recent_tasks(node, limit)": {
                    "description": "View recent tasks with status and execution details",
                    "usage": [
                        "list_recent_tasks()  # All nodes, last 20 tasks",
                        "list_recent_tasks('pve-node1', 50)  # Specific node, 50 tasks"
                    ],
                    "returns": "Task type, status, user, start/end times, UPID"
                }
            },
            
            "📸 SNAPSHOTS & TEMPLATES": {
                "list_snapshots(node, vmid, vm_type)": {
                    "description": "List snapshots for a VM or container",
                    "usage": [
                        "list_snapshots('pve-node1', 100, 'qemu')  # VM snapshots",
                        "list_snapshots('pve-node1', 101, 'lxc')  # Container snapshots"
                    ],
                    "returns": "Snapshot name, description, creation time, RAM inclusion status"
                },
                "list_templates()": {
                    "description": "List all VM and container templates available for deployment",
                    "usage": "list_templates()",
                    "returns": "Template VMID, name, type, resource allocations"
                }
            },
            
            "👥 ACCESS CONTROL": {
                "list_users()": {
                    "description": "List all Proxmox users with their status and details",
                    "usage": "list_users()",
                    "returns": "User ID, enabled status, expiration, email, groups, tokens"
                },
                "list_groups()": {
                    "description": "List all user groups and memberships",
                    "usage": "list_groups()",
                    "returns": "Group ID, description, member users"
                },
                "list_roles()": {
                    "description": "List all available roles with privileges",
                    "usage": "list_roles()",
                    "returns": "Role ID, privileges list, special status"
                }
            },
            
            "🌐 NETWORK & SECURITY": {
                "get_vm_network(node, vmid, vm_type)": {
                    "description": "Get network configuration for VM or container",
                    "usage": [
                        "get_vm_network('pve-node1', 100)  # VM network (default)",
                        "get_vm_network('pve-node1', 101, 'lxc')  # Container network"
                    ],
                    "returns": "Network interfaces, MAC addresses, bridges, agent IP info"
                },
                "get_firewall_status(node, vmid)": {
                    "description": "Check firewall status and rules",
                    "usage": [
                        "get_firewall_status('pve-node1')  # Node firewall",
                        "get_firewall_status('pve-node1', 100)  # VM firewall"
                    ],
                    "returns": "Firewall enabled status, policies, rules list"
                }
            },
            
            "🔄 LEGACY COMPATIBILITY": {
                "Note": "Original methods preserved for backward compatibility",
                "Methods": [
                    "list_nodes() - Basic node listing",
                    "list_vms(node) - VMs on specific node",
                    "list_containers(node) - Containers on specific node",
                    "get_vm_status(node, vmid) - Basic VM status",
                    "get_container_status(node, vmid) - Basic container status"
                ]
            },
            
            "💡 QUICK START EXAMPLES": {
                "1. Test Connection": "check_connection()",
                "2. View Cluster": "get_cluster_status()",
                "3. List All VMs": "list_all_vms()",
                "4. Check Storage": "list_storage_pools()",
                "5. Recent Tasks": "list_recent_tasks()",
                "6. Get Help": "help()"
            },
            
            "⚙️ CONFIGURATION": {
                "Required Settings": {
                    "PROXMOX_HOST": "Your Proxmox server (e.g., '192.168.1.1:8006')",
                    "PROXMOX_USER": "Username (e.g., 'root@pam')",
                    "PROXMOX_TOKEN_ID": "API token ID",
                    "PROXMOX_TOKEN_SECRET": "API token secret"
                },
                "Optional Settings": {
                    "VERIFY_SSL": "SSL verification (default: False)",
                    "CACHE_TIMEOUT": "Connection cache timeout in seconds (default: 60)"
                }
            },
            
            "❓ TROUBLESHOOTING": {
                "Connection Failed": "Check host address, credentials, and network connectivity",
                "Permission Denied": "Ensure API token has appropriate privileges",
                "SSL Error": "Set VERIFY_SSL to False for self-signed certificates",
                "No Data": "Verify the resource exists and you have access rights"
            }
        }
        
        return help_info
    
    def check_connection(self) -> Dict[str, str]:
        """
        Test API connectivity and return connection status.
        """
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {
                    "status": "Failed",
                    "error": api[1],
                    "host": self.valves.PROXMOX_HOST
                }
            
            # Try to get version to verify connection
            version = api.version.get()
            
            return {
                "status": "Connected",
                "host": self.valves.PROXMOX_HOST,
                "user": self.valves.PROXMOX_USER,
                "version": version.get('version', 'unknown'),
                "release": version.get('release', 'unknown')
            }
            
        except Exception as e:
            return {
                "status": "Failed",
                "error": str(e),
                "host": self.valves.PROXMOX_HOST,
                "suggestion": "Check your host, credentials, and network connectivity"
            }
    
    # ============= LEGACY COMPATIBILITY =============
    # Keep original methods for backward compatibility
    
    def list_nodes(self) -> List[Dict[str, Any]]:
        """List all nodes in the Proxmox cluster (legacy method)."""
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            return api.nodes.get()
        except Exception as e:
            return [{"error": str(e)}]
    
    def list_vms(self, node: str) -> List[Dict[str, Any]]:
        """List all VMs on a specific node (legacy method)."""
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            return api.nodes(node).qemu.get()
        except Exception as e:
            return [{"error": str(e)}]
    
    def list_containers(self, node: str) -> List[Dict[str, Any]]:
        """List all containers on a specific node (legacy method)."""
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return [{"error": api[1]}]
            return api.nodes(node).lxc.get()
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_vm_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """Get the status of a specific VM (legacy method)."""
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            return api.nodes(node).qemu(vmid).status.current.get()
        except Exception as e:
            return {"error": str(e)}
    
    def get_container_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """Get the status of a specific container (legacy method)."""
        try:
            api = self._get_api()
            if isinstance(api, tuple):
                return {"error": api[1]}
            return api.nodes(node).lxc(vmid).status.current.get()
        except Exception as e:
            return {"error": str(e)}