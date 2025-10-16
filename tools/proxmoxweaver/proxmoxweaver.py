"""
title: ProxmoxWeaver - Proxmox OpenWebUI Tool
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/my-openwebui/tree/main/tools/proxmoxweaver
funding_url: https://github.com/open-webui
version: 1.0.0
license: MIT
required_open_webui_version: 0.3.9
description: ProxmoxWeaver tool for managing and monitoring Proxmox VMs and nodes via OpenWebUI.
"""
import requests
import json
from typing import Optional, Dict, List, Any, Union
from pydantic import BaseModel, Field
import sys
import os

class Tools:
    # =============================================================
    # DO NOT REMOVE THIS CLASS!
    # The Valves class is critical for configuration and API access.
    # Removing or altering this class will break authentication and tool operation.
    # =============================================================
    class Valves(BaseModel):
        PROXMOX_HOST: str = Field(default="https://example.com")
        PROXMOX_USER: str = Field(default="root@pam")
        PROXMOX_TOKEN_ID: str = Field(default="default-token")
        PROXMOX_TOKEN_SECRET: str = Field(default="default-secret")
        VERIFY_SSL: bool = Field(default=False)

    def __init__(self):
        self.valves = self.Valves()
        self._node_cache = None  # Cache for node list

    def _make_request(self, endpoint: str, method: str = "GET") -> Any:
        url = f"{self.valves.PROXMOX_HOST}{endpoint}"
        headers = {
            "Authorization": f"PVEAPIToken={self.valves.PROXMOX_USER}!{self.valves.PROXMOX_TOKEN_ID}={self.valves.PROXMOX_TOKEN_SECRET}"
        }
        try:
            response = requests.request(
                method, url, headers=headers, verify=self.valves.VERIFY_SSL, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    # =============================================================
    # DO NOT REMOVE OR MODIFY THIS METHOD!
    # _make_request is the core API communication method for ProxmoxWeaver.
    # Any changes here may break authentication, requests, or error handling.
    # =============================================================

    def list_cluster_vms_and_containers_grouped(self) -> dict:
        """
        Lists all VMs and containers in the cluster, grouped by node.
        Returns a dictionary: {node_name: [vm_and_container_dicts]}
        Each entry includes type (vm/container), id, name, status, cpu, ram, disk, uptime, ip, os.
        """
        nodes_data = self._make_request("/api2/json/nodes")
        if "error" in nodes_data:
            return {"error": nodes_data["error"]}
        result = {}
        for node in nodes_data.get("data", []):
            node_name = node.get("node")
            node_vms = []
            # VMs
            vms_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu")
            for vm in vms_data.get("data", []):
                vm_details = {
                    "type": "vm",
                    "id": vm.get("vmid"),
                    "name": vm.get("name"),
                    "status": vm.get("status"),
                    "cpu": vm.get("cpu", 0),
                    "ram": vm.get("mem", 0),
                    "disk": vm.get("disk", 0),
                    "uptime": vm.get("uptime", 0),
                    "ip": vm.get("ip", None),  # May need extra API call for IP
                    "os": vm.get("ostype", None)
                }
                node_vms.append(vm_details)
            # Containers
            ct_data = self._make_request(f"/api2/json/nodes/{node_name}/lxc")
            for ct in ct_data.get("data", []):
                ct_details = {
                    "type": "container",
                    "id": ct.get("vmid"),
                    "name": ct.get("name"),
                    "status": ct.get("status"),
                    "cpu": ct.get("cpu", 0),
                    "ram": ct.get("mem", 0),
                    "disk": ct.get("disk", 0),
                    "uptime": ct.get("uptime", 0),
                    "ip": ct.get("ip", None),  # May need extra API call for IP
                    "os": ct.get("ostype", None)
                }
                node_vms.append(ct_details)
            result[node_name] = node_vms
        return result
    def list_cluster_nodes_health(self) -> dict:
        """
        Lists all nodes in the cluster with status, resource usage, and details.
        Returns a dictionary: {node_name: {status, uptime, maxcpu, memory}}
        Uses API calls for all data, with fallback to basic info if detailed status fails.
        """
        nodes_data = self._make_request("/api2/json/nodes")
        if "error" in nodes_data:
            return {"error": nodes_data["error"]}
        result = {}
        for node in nodes_data.get("data", []):
            node_name = node.get("node")
            node_info = {"status": node.get("status", "unknown")}
            try:
                status_data = self._make_request(f"/api2/json/nodes/{node_name}/status")
                node_info["uptime"] = status_data.get("data", {}).get("uptime", 0)
                node_info["maxcpu"] = status_data.get("data", {}).get("cpuinfo", {}).get("cpus", "N/A")
                node_info["memory"] = {
                    "used": status_data.get("data", {}).get("memory", {}).get("used", 0),
                    "total": status_data.get("data", {}).get("memory", {}).get("total", 0)
                }
                node_info["version"] = status_data.get("data", {}).get("version", "N/A")
                node_info["roles"] = status_data.get("data", {}).get("roles", [])
            except Exception:
                # Fallback to basic info if detailed status fails
                node_info["uptime"] = 0
                node_info["maxcpu"] = "N/A"
                node_info["memory"] = {
                    "used": node.get("maxmem", 0) - node.get("mem", 0),
                    "total": node.get("maxmem", 0)
                }
                node_info["version"] = "N/A"
                node_info["roles"] = []
            result[node_name] = node_info
        return result
    def list_cluster_storage_and_backups(self) -> dict:
            """
            Lists all storage pools in the cluster with type, usage, available space, attached devices, and recent backups.
            Returns a dictionary: {node_name: [{storage details, recent backups}]}
            """
            nodes_data = self._make_request("/api2/json/nodes")
            if "error" in nodes_data:
                return {"error": nodes_data["error"]}
            result = {}
            for node in nodes_data.get("data", []):
                node_name = node.get("node")
                storage_data = self._make_request(f"/api2/json/nodes/{node_name}/storage")
                if "error" in storage_data:
                    result[node_name] = {"error": storage_data["error"]}
                    continue
                storages = []
                for storage in storage_data.get("data", []):
                    storage_info = {
                        "id": storage.get("storage"),
                        "type": storage.get("type"),
                        "enabled": storage.get("enabled", True),
                        "content": storage.get("content", []),
                        "used": storage.get("used", 0),
                        "total": storage.get("total", 0),
                        "avail": storage.get("avail", 0),
                        "attached_devices": storage.get("devices", []),
                        "status": storage.get("status", "unknown"),
                    }
                    # Recent backups (if any)
                    backups = []
                    if "backup" in storage_info["content"]:
                        backup_data = self._make_request(f"/api2/json/nodes/{node_name}/storage/{storage_info['id']}/content")
                        for item in backup_data.get("data", []):
                            if item.get("content") == "backup":
                                backups.append({
                                    "volid": item.get("volid"),
                                    "size": item.get("size", 0),
                                    "ctime": item.get("ctime", 0),
                                    "vmid": item.get("vmid", None),
                                    "status": item.get("status", "unknown")
                                })
                    storage_info["recent_backups"] = backups
                    storages.append(storage_info)
                result[node_name] = storages
            return result
    def list_cluster_tasks_and_events(self) -> dict:
                """
                Lists recent tasks (migrations, backups, snapshots, etc.) and recent cluster events (failures, warnings, changes) for each node.
                Returns a dictionary: {node_name: {tasks: [...], events: [...]}}
                """
                nodes_data = self._make_request("/api2/json/nodes")
                if "error" in nodes_data:
                    return {"error": nodes_data["error"]}
                result = {}
                for node in nodes_data.get("data", []):
                    node_name = node.get("node")
                    # Recent tasks
                    tasks_data = self._make_request(f"/api2/json/nodes/{node_name}/tasks")
                    tasks = []
                    for task in tasks_data.get("data", []):
                        tasks.append({
                            "upid": task.get("upid"),
                            "type": task.get("type"),
                            "id": task.get("id"),
                            "status": task.get("status"),
                            "starttime": task.get("starttime"),
                            "endtime": task.get("endtime"),
                            "exitstatus": task.get("exitstatus"),
                            "user": task.get("user"),
                            "node": node_name,
                            "log": None,  # Optionally fetch logs below
                            "error": None
                        })
                    # Optionally fetch logs/errors for each task (limit to recent)
                    for t in tasks[:5]:  # Limit to 5 most recent for performance
                        upid = t["upid"]
                        log_data = self._make_request(f"/api2/json/nodes/{node_name}/tasks/{upid}/log")
                        if "data" in log_data:
                            t["log"] = [entry.get("t") for entry in log_data["data"]]
                        if "error" in log_data:
                            t["error"] = log_data["error"]
                    # Recent events (cluster-wide)
                    events_data = self._make_request("/api2/json/cluster/log")
                    events = []
                    for event in events_data.get("data", [])[:10]:  # Limit to 10 most recent
                        events.append({
                            "time": event.get("time"),
                            "type": event.get("type"),
                            "user": event.get("user"),
                            "msg": event.get("msg"),
                            "node": event.get("node", None)
                        })
                    result[node_name] = {"tasks": tasks, "events": events}
                return result
    def list_snapshots_and_templates(self) -> dict:
                    """
                    Lists VM/container snapshots and available templates for creation.
                    Returns a dictionary: {node_name: {vms: [{vmid, snapshots, templates}], containers: [{vmid, snapshots, templates}]}}
                    """
                    nodes_data = self._make_request("/api2/json/nodes")
                    if "error" in nodes_data:
                        return {"error": nodes_data["error"]}
                    result = {}
                    for node in nodes_data.get("data", []):
                        node_name = node.get("node")
                        vms_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu")
                        vms = []
                        for vm in vms_data.get("data", []):
                            vmid = vm.get("vmid")
                            # Snapshots
                            snapshots_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu/{vmid}/snapshot")
                            snapshots = []
                            for snap in snapshots_data.get("data", []):
                                snapshots.append({
                                    "name": snap.get("name"),
                                    "description": snap.get("description", ""),
                                    "snaptime": snap.get("snaptime", 0),
                                    "vmstate": snap.get("vmstate", False),
                                    "size": snap.get("size", 0)
                                })
                            # Templates
                            templates_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu/{vmid}/template")
                            templates = []
                            for tmpl in templates_data.get("data", []):
                                templates.append({
                                    "name": tmpl.get("name"),
                                    "description": tmpl.get("description", ""),
                                    "vmid": tmpl.get("vmid", None)
                                })
                            vms.append({"vmid": vmid, "snapshots": snapshots, "templates": templates})
                        # Containers
                        ct_data = self._make_request(f"/api2/json/nodes/{node_name}/lxc")
                        containers = []
                        for ct in ct_data.get("data", []):
                            vmid = ct.get("vmid")
                            # Snapshots
                            snapshots_data = self._make_request(f"/api2/json/nodes/{node_name}/lxc/{vmid}/snapshot")
                            snapshots = []
                            for snap in snapshots_data.get("data", []):
                                snapshots.append({
                                    "name": snap.get("name"),
                                    "description": snap.get("description", ""),
                                    "snaptime": snap.get("snaptime", 0),
                                    "size": snap.get("size", 0)
                                })
                            # Templates
                            templates_data = self._make_request(f"/api2/json/nodes/{node_name}/lxc/{vmid}/template")
                            templates = []
                            for tmpl in templates_data.get("data", []):
                                templates.append({
                                    "name": tmpl.get("name"),
                                    "description": tmpl.get("description", ""),
                                    "vmid": tmpl.get("vmid", None)
                                })
                            containers.append({"vmid": vmid, "snapshots": snapshots, "templates": templates})
                        result[node_name] = {"vms": vms, "containers": containers}
                    return result
    def list_users_and_permissions(self) -> dict:
            """
            Lists users, roles, permissions per user/role, and API tokens with their scopes.
            Returns a dictionary: {users: [...], roles: [...], permissions: [...], tokens: [...]}
            """
            # Users
            users_data = self._make_request("/api2/json/access/users")
            users = []
            for user in users_data.get("data", []):
                users.append({
                    "userid": user.get("userid"),
                    "enable": user.get("enable", True),
                    "expire": user.get("expire", None),
                    "tokens": []
                })
            # Roles
            roles_data = self._make_request("/api2/json/access/roles")
            roles = []
            for role in roles_data.get("data", []):
                roles.append({
                    "roleid": role.get("roleid"),
                    "privs": role.get("privs", [])
                })
            # Permissions
            perms_data = self._make_request("/api2/json/access/acl")
            permissions = []
            for perm in perms_data.get("data", []):
                permissions.append({
                    "path": perm.get("path"),
                    "users": perm.get("users", []),
                    "roles": perm.get("roles", [])
                })
            # API Tokens
            tokens_data = self._make_request("/api2/json/access/ticket")
            tokens = []
            for user in users:
                # For each user, try to get tokens (if any)
                token_data = self._make_request(f"/api2/json/access/users/{user['userid']}/token")
                for token in token_data.get("data", []):
                    tokens.append({
                        "userid": user["userid"],
                        "tokenid": token.get("tokenid"),
                        "expire": token.get("expire", None),
                        "privs": token.get("privs", [])
                    })
                    user["tokens"].append(token.get("tokenid"))
            return {
                "users": users,
                "roles": roles,
                "permissions": permissions,
                "tokens": tokens
            }

    def list_network_and_console_info(self) -> dict:
                """
                Shows VM/container network info (IP, MAC, bridge, firewall status) and lists active console sessions (VNC/SPICE).
                Returns a dictionary: {node_name: {vms: [...], containers: [...], consoles: [...]}}
                """
                nodes_data = self._make_request("/api2/json/nodes")
                if "error" in nodes_data:
                    return {"error": nodes_data["error"]}
                result = {}
                for node in nodes_data.get("data", []):
                    node_name = node.get("node")
                    # VMs
                    vms_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu")
                    vms = []
                    for vm in vms_data.get("data", []):
                        vmid = vm.get("vmid")
                        config_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu/{vmid}/config")
                        # Prefer agent/network-get-interfaces for IP info
                        agent_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu/{vmid}/agent/network-get-interfaces")
                        ipv4 = None
                        ipv6 = None
                        mac = None
                        bridge = None
                        if "data" in agent_data and "result" in agent_data["data"]:
                            for iface in agent_data["data"]["result"]:
                                mac = iface.get("hardware-address")
                                for ip_entry in iface.get("ip-addresses", []):
                                    ip_addr = ip_entry.get("ip-address")
                                    if ip_addr and ip_addr != "127.0.0.1":
                                        if ":" in ip_addr:
                                            if not ipv6:
                                                ipv6 = ip_addr
                                        else:
                                            if not ipv4:
                                                ipv4 = ip_addr
                        if not ipv4 and not ipv6:
                            # Fallback to status/current
                            status_data = self._make_request(f"/api2/json/nodes/{node_name}/qemu/{vmid}/status/current")
                            if "data" in status_data:
                                if "network" in status_data["data"]:
                                    for iface, net in status_data["data"]["network"].items():
                                        mac = net.get("hwaddr", iface)
                                        ip = net.get("ip", None)
                                        ip6 = net.get("ip6", None)
                                        if ip and ip != "127.0.0.1" and not ipv4:
                                            ipv4 = ip
                                        if ip6 and not ipv6:
                                            ipv6 = ip6
                                        if net.get("bridge"):
                                            bridge = net.get("bridge")
                        # Fallback to config parsing for MAC/bridge
                        if not mac or not bridge:
                            for k, v in config_data.get("data", {}).items():
                                if k.startswith("net"):
                                    if isinstance(v, dict):
                                        if not mac:
                                            mac = v.get("macaddr", None)
                                        if not bridge:
                                            bridge = v.get("bridge", None)
                                    elif isinstance(v, str):
                                        parts = v.split(",")
                                        for part in parts:
                                            if part.startswith("bridge=") and not bridge:
                                                bridge = part.split("=", 1)[1]
                                            elif (part.startswith("virtio=") or part.startswith("macaddr=")) and not mac:
                                                mac = part.split("=", 1)[1]
                        vms.append({
                            "vmid": vmid,
                            "network": {
                                "ip": ipv4 if ipv4 else ipv6,
                                "ipv4": ipv4,
                                "ipv6": ipv6,
                                "mac": mac,
                                "bridge": bridge,
                                "firewall": config_data.get("data", {}).get("firewall", False)
                            }
                        })
                    # Containers
                    ct_data = self._make_request(f"/api2/json/nodes/{node_name}/lxc")
                    containers = []
                    for ct in ct_data.get("data", []):
                        vmid = ct.get("vmid")
                        config_data = self._make_request(f"/api2/json/nodes/{node_name}/lxc/{vmid}/config")
                        status_data = self._make_request(f"/api2/json/nodes/{node_name}/lxc/{vmid}/status/current")
                        ipv4 = None
                        ipv6 = None
                        mac = None
                        bridge = None
                        if "data" in status_data and "network" in status_data["data"]:
                            for iface, net in status_data["data"]["network"].items():
                                mac = net.get("hwaddr", iface)
                                ip = net.get("ip", None)
                                ip6 = net.get("ip6", None)
                                if ip and ip != "127.0.0.1" and not ipv4:
                                    ipv4 = ip
                                if ip6 and not ipv6:
                                    ipv6 = ip6
                                if net.get("bridge"):
                                    bridge = net.get("bridge")
                        # Fallback to config parsing for MAC/bridge
                        if not mac or not bridge:
                            for k, v in config_data.get("data", {}).items():
                                if k.startswith("net"):
                                    if isinstance(v, dict):
                                        if not mac:
                                            mac = v.get("hwaddr", None)
                                        if not bridge:
                                            bridge = v.get("bridge", None)
                                    elif isinstance(v, str):
                                        parts = v.split(",")
                                        for part in parts:
                                            if part.startswith("bridge=") and not bridge:
                                                bridge = part.split("=", 1)[1]
                                            elif part.startswith("hwaddr=") and not mac:
                                                mac = part.split("=", 1)[1]
                        containers.append({
                            "vmid": vmid,
                            "network": {
                                "ip": ipv4 if ipv4 else ipv6,
                                "ipv4": ipv4,
                                "ipv6": ipv6,
                                "mac": mac,
                                "bridge": bridge,
                                "firewall": config_data.get("data", {}).get("firewall", False)
                            }
                        })
                    # Active console sessions (VNC/SPICE)
                    consoles_data = self._make_request(f"/api2/json/nodes/{node_name}/vncwebsocket")
                    consoles = []
                    for session in consoles_data.get("data", []):
                        consoles.append({
                            "vmid": session.get("vmid", None),
                            "type": session.get("type", None),
                            "user": session.get("user", None),
                            "status": session.get("status", None)
                        })
                    result[node_name] = {"vms": vms, "containers": containers, "consoles": consoles}
                return result
    
    def show_help_and_troubleshooting(self) -> dict:
        
        """
        Returns a dictionary with available commands/features and troubleshooting tips for common errors.
        """
        features = [
            "list_cluster_vms_and_containers_grouped: List all VMs and containers with details (cluster-wide)",
            "list_cluster_nodes_health: List all nodes with status, resource usage, and details",
            "list_cluster_storage_and_backups: List all storage pools, attached devices, and recent backups",
            "list_cluster_tasks_and_events: List recent tasks and cluster events with logs/errors",
            "list_snapshots_and_templates: List VM/container snapshots and available templates",
            "list_users_and_permissions: List users, roles, permissions, and API tokens",
            "list_network_and_console_info: Show VM/container network info and active console sessions",
        ]
        troubleshooting = [
            "If IP addresses are missing, ensure the QEMU guest agent is installed and running for VMs, and containers are started.",
            "Templates and stopped containers do not have IPs assigned by Proxmox.",
            "Check API token permissions if you receive authentication errors.",
            "For SSL errors, set VERIFY_SSL to False in configuration if using self-signed certificates.",
            "If you see 'error' in output, check the Proxmox API endpoint and network connectivity.",
        ]
        return {
            "features": features,
            "troubleshooting": troubleshooting
        }