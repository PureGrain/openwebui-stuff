"""
# ProxmoxWeaver - Proxmox OpenWebUI Tool
# Metadata for OpenWebUI compatibility
# Ensure this block is updated as per OpenWebUI guidelines
"""

import requests
import json
from typing import Optional, Dict, List, Any, Union
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        PROXMOX_HOST: str = Field(default="https://example.com")
        PROXMOX_USER: str = Field(default="root@pam")
        PROXMOX_TOKEN_ID: str = Field(default="default-token")
        PROXMOX_TOKEN_SECRET: str = Field(default="default-secret")
        VERIFY_SSL: bool = Field(default=False)

    def __init__(self):
        self.valves = self.Valves()

    def _make_request(self, endpoint: str, method: str = "GET") -> Any:
        import requests
        url = f"{self.valves.PROXMOX_HOST}{endpoint}"
        headers = {
            "Authorization": f"PVEAPIToken={self.valves.PROXMOX_USER}!{self.valves.PROXMOX_TOKEN_ID}={self.valves.PROXMOX_TOKEN_SECRET}"
        }
        try:
            response = requests.request(
                method, url, headers=headers, verify=self.valves.VERIFY_SSL
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    def get_storage_summary(self, node: Optional[str] = None, nas_only: bool = False) -> List[Dict[str, Any]]:
        """
        Returns storage summary for the cluster or a node.
        """
        if node:
            endpoint = f"/api2/json/nodes/{node}/storage"
        else:
            endpoint = "/api2/json/storage"
        data = self._make_request(endpoint)
        if "error" in data:
            return [{"error": data["error"]}]
        results = []
        for storage in data.get("data", []):
            # Filter NAS if requested (type: 'nfs', 'cifs', 'glusterfs', etc.)
            if nas_only and storage.get("type") not in ["nfs", "cifs", "glusterfs", "iscsi"]:
                continue
            total = storage.get("total", 0)
            used = storage.get("used", 0)
            avail = storage.get("avail", 0)
            percent = round((used / total * 100), 2) if total else None
            storage_name = storage.get("storage")
            storage_type = storage.get("type")
            # Get snapshot count
            snapshot_count = 0
            attached_nas = []
            # Try to get content for snapshot count and NAS device info
            if node and storage_name:
                content_endpoint = f"/api2/json/nodes/{node}/storage/{storage_name}/content"
                content_data = self._make_request(content_endpoint)
                if "data" in content_data:
                    snapshot_count = sum(1 for item in content_data["data"] if item.get("content") == "snapshot")
            # Try to get attached NAS device info from storage metadata
            # For NFS/iSCSI, the 'server' field may indicate NAS device
            if storage_type in ["nfs", "cifs", "iscsi"]:
                nas_server = storage.get("server")
                if nas_server:
                    attached_nas.append(nas_server)
            results.append({
                "Storage": storage_name,
                "Type": storage_type,
                "Total (GB)": round(total / 1024**3, 2) if total else None,
                "Used (GB)": round(used / 1024**3, 2) if used else 0,
                "Available (GB)": round(avail / 1024**3, 2) if avail else None,
                "Usage (%)": percent,
                "Snapshot Count": snapshot_count,
                "NAS Devices Attached": ", ".join(attached_nas) if attached_nas else "No"
            })
        return results
    def get_historical_stats(self, target: str, target_id: str, node: Optional[str] = None, timeframe: str = "hour") -> List[Dict[str, Any]]:
        """
        Returns historical stats for a VM or node.
        """
        # Valid timeframes: hour, day, week, month, year
        if target == "node":
            endpoint = f"/api2/json/nodes/{target_id}/rrddata?timeframe={timeframe}"
        elif target == "vm":
            if not node:
                return [{"error": "Node name required for VM historical stats."}]
            endpoint = f"/api2/json/nodes/{node}/qemu/{target_id}/rrddata?timeframe={timeframe}"
        else:
            return [{"error": "Invalid target type. Use 'vm' or 'node'."}]
        data = self._make_request(endpoint)
        if "error" in data:
            return [{"error": data["error"]}]
        results = []
        skipped = 0
        for point in data.get("data", []):
            cpu = point.get("cpu")
            mem = point.get("mem")
            disk = point.get("disk")
            if cpu is None or mem is None or disk is None:
                skipped += 1
                continue
            mem_mb = mem / 1024**2
            disk_mb = disk / 1024**2
            results.append({
                "timestamp": point.get("time"),
                "CPU": cpu,
                "Memory (MB)": round(mem_mb, 2),
                "Disk (MB)": round(disk_mb, 2)
            })
        if skipped > 0:
            results.append({"warning": f"{skipped} entries skipped due to missing data."})
        return results
    def get_help(self) -> str:
        """
        Returns a list of all available commands and usage examples for the ProxmoxWeaver tool.
        """
        return (
            "ProxmoxWeaver Tool - Available Commands:\n"
            "\n"
            "1. get_storage_summary\n"
            "   - Description: List all storage pools (including NAS devices) for the cluster or a node.\n"
            "   - Usage: get_storage_summary(node='proxmox-node1', nas_only=True)\n"
            "   - Example Prompt: Show me all storage pools for node 'proxmox-node1', including NAS devices.\n"
            "\n"
            "2. get_historical_stats\n"
            "   - Description: Fetch historical CPU, memory, and disk usage for a VM or node.\n"
            "   - Usage: get_historical_stats(target='vm', target_id='101', node='proxmox-node1', timeframe='day')\n"
            "   - Example Prompt: Get historical stats for VM 101 on node 'proxmox-node1' for the past day.\n"
            "\n"
            "General Usage:\n"
            "- You can call these commands directly or use natural language prompts in OpenWebUI.\n"
            "- For best results, specify node names, VM IDs, and timeframes as needed.\n"
            "\n"
            "Troubleshooting:\n"
            "- If you see an error, check your API credentials and network connectivity.\n"
            "- Ensure the class is named 'Tools' for compatibility.\n"
        )
    def list_nodes(self) -> List[Dict[str, Any]]:
        """
        Lists all nodes in the Proxmox cluster with their status and resource usage.
        """
        endpoint = "/api2/json/nodes"
        data = self._make_request(endpoint)
        if "error" in data:
            return [{"error": data["error"]}]

        results = []
        for node in data.get("data", []):
            results.append({
                "Node": node.get("node"),
                "Status": node.get("status"),
                "CPU Usage (%)": node.get("cpu", 0) * 100,
                "Memory Usage (%)": node.get("mem", 0) / node.get("maxmem", 1) * 100,
                "Disk Usage (%)": node.get("disk", 0) / node.get("maxdisk", 1) * 100,
            })
        return results

