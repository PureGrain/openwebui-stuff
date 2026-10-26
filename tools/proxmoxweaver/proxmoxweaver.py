"""
title: ProxmoxWeaver
author: PureGrain at SLA Ops, LLC
author_url: https://github.com/PureGrain
repo_url: https://github.com/PureGrain/openwebui-stuff/tree/main/tools/proxmoxweaver
funding_url: https://github.com/sponsors/PureGrain
version: 3.0.1
license: MIT
required_open_webui_version: 0.10.0
description: Proxmox VE monitoring and safe management. Async with no extra packages, keeps working when a node is down, finds guests by name, and reports health, IPs, backups, updates and usage history. Power actions and snapshots are optional and ask for confirmation.
"""

import asyncio
import html
import re
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field

Emitter = Optional[Callable[[dict], Awaitable[Any]]]

# Friendly names for the task types people care about. Anything else shows its raw type.
TASK_NAMES = {
    "vzdump": "backup",
    "qmstart": "VM start",
    "qmstop": "VM stop",
    "qmshutdown": "VM shutdown",
    "qmreboot": "VM reboot",
    "qmsnapshot": "VM snapshot",
    "qmdelsnapshot": "VM snapshot delete",
    "qmrollback": "VM snapshot rollback",
    "qmclone": "VM clone",
    "qmcreate": "VM create",
    "qmdestroy": "VM destroy",
    "qmigrate": "VM migrate",
    "qmconfig": "VM config change",
    "vzstart": "CT start",
    "vzstop": "CT stop",
    "vzshutdown": "CT shutdown",
    "vzreboot": "CT reboot",
    "vzsnapshot": "CT snapshot",
    "vzdelsnapshot": "CT snapshot delete",
    "vzrollback": "CT snapshot rollback",
    "vzcreate": "CT create",
    "vzdestroy": "CT destroy",
    "vzmigrate": "CT migrate",
    "aptupdate": "package list refresh",
    "startall": "start all guests",
    "stopall": "stop all guests",
    "resize": "disk resize",
    "download": "download",
    "srvrestart": "service restart",
    "srvreload": "service reload",
}

# Console sessions are noise in a task list.
CONSOLE_TASKS = {"vncproxy", "vncshell", "termproxy", "spiceproxy", "spiceshell"}

# Interfaces that only carry container or bridge traffic, not the guest's real address.
IGNORED_IFACES = ("lo", "docker", "br-", "veth", "virbr", "cni", "flannel")

SHARED_STORAGE_TYPES = {"pbs", "nfs", "cifs", "cephfs", "rbd", "glusterfs", "iscsi", "iscsidirect", "zfs"}

SNAPSHOT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,39}$")


class ProxmoxError(Exception):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


# ============= FORMATTING =============


def _size(num: Optional[float]) -> Optional[str]:
    if num is None:
        return None
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024 or unit == "TiB":
            return f"{value:.0f} {unit}" if unit in ("B", "KiB") else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"


def _rate(bytes_per_sec: Optional[float]) -> Optional[str]:
    if bytes_per_sec is None:
        return None
    return f"{_size(bytes_per_sec)}/s"


def _pct(used: Optional[float], total: Optional[float]) -> Optional[float]:
    if not total or used is None:
        return None
    return round(100.0 * float(used) / float(total), 1)


def _duration(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def _ago(epoch: Optional[float]) -> Optional[str]:
    if not epoch:
        return None
    return f"{_duration(max(0, time.time() - float(epoch)))} ago"


async def _emit(emitter: Emitter, text: str, done: bool = False) -> None:
    if emitter:
        try:
            await emitter({"type": "status", "data": {"description": text, "done": done}})
        except Exception:
            pass


def _parse_response(r: httpx.Response, path: str) -> Any:
    if r.status_code < 400:
        try:
            return r.json().get("data")
        except ValueError:
            return None
    message = r.reason_phrase or ""
    try:
        body = r.json()
        if isinstance(body, dict):
            if body.get("message"):
                message = str(body["message"]).strip()
            if isinstance(body.get("errors"), dict):
                message += " " + "; ".join(f"{k}: {v}" for k, v in body["errors"].items())
    except ValueError:
        if r.text:
            message = r.text.strip()[:300]
    hint = ""
    if r.status_code == 401:
        hint = (
            "The API token was rejected. Check PROXMOX_USER, PROXMOX_TOKEN_ID and "
            "PROXMOX_TOKEN_SECRET in the tool settings, and that the token still exists."
        )
    elif r.status_code == 403:
        hint = (
            "The token works but lacks permission for this. A token with privilege "
            "separation needs its own permissions under Datacenter > Permissions."
        )
    elif r.status_code == 595 or "no route to host" in message.lower():
        hint = "That node is offline or unreachable from the node answering the API."
    raise ProxmoxError(f"Proxmox returned {r.status_code} for {path}: {message}".strip(), hint)


class _Session:
    """One HTTP client per tool call. Tries each configured host until one answers."""

    def __init__(self, tools: "Tools"):
        self.tools = tools
        valves = tools.valves
        seconds = max(3, int(valves.TIMEOUT_SECONDS))
        self.client = httpx.AsyncClient(
            verify=valves.VERIFY_SSL,
            timeout=httpx.Timeout(seconds, connect=min(5, seconds)),
            headers=tools._auth_header(),
        )
        self._resources: Optional[list] = None

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.client.aclose()

    async def request(self, method: str, path: str, params: Optional[dict] = None, data: Optional[dict] = None) -> Any:
        failures = []
        for host in self.tools._hosts():
            url = f"https://{host}/api2/json{path}"
            try:
                response = await self.client.request(method, url, params=params, data=data)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                failures.append(f"{host} ({type(e).__name__})")
                continue
            except httpx.TransportError as e:
                if method == "GET":
                    failures.append(f"{host} ({type(e).__name__})")
                    continue
                # A write that timed out may still have run, so never repeat it on another host.
                raise ProxmoxError(
                    f"{method} {path} on {host} did not finish: {type(e).__name__}",
                    "The action may still have run. Check get_recent_tasks before trying again.",
                )
            self.tools._good_host = host
            return _parse_response(response, path)
        raise ProxmoxError(
            "Could not reach any Proxmox host: " + ", ".join(failures),
            "Check PROXMOX_HOST in the tool settings. List two or more nodes, comma separated, "
            "so another node can answer when one is down.",
        )

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, data: Optional[dict] = None) -> Any:
        return await self.request("POST", path, data=data)

    async def resources(self) -> list:
        """Everything in the cluster (nodes, guests, storage) from one call, cached for this tool call."""
        if self._resources is None:
            self._resources = await self.get("/cluster/resources") or []
        return self._resources

    async def attempt(self, coro: Awaitable) -> tuple:
        """Run a request and return (value, error_text) instead of raising."""
        try:
            return await coro, None
        except ProxmoxError as e:
            return None, str(e)


class Tools:
    class Valves(BaseModel):
        PROXMOX_HOST: str = Field(
            default="192.168.1.10:8006",
            description="Proxmox node as host:port. List several nodes, comma separated, so the tool keeps working when one is down.",
        )
        PROXMOX_USER: str = Field(default="root@pam", description="User that owns the API token, for example root@pam")
        PROXMOX_TOKEN_ID: str = Field(
            default="",
            description="API token name (the part after the !). The full user@realm!name also works.",
        )
        PROXMOX_TOKEN_SECRET: str = Field(
            default="",
            description="API token secret",
            json_schema_extra={"input": {"type": "password"}},
        )
        VERIFY_SSL: bool = Field(default=False, description="Verify the TLS certificate. Leave off for the default self-signed certificate.")
        TIMEOUT_SECONDS: int = Field(default=15, description="Seconds to wait for each Proxmox API request")
        TIMEZONE: str = Field(
            default="",
            description="Time zone for times shown, for example America/New_York. Empty uses the chat user's time zone, then UTC.",
        )
        STORAGE_WARN_PERCENT: int = Field(default=85, description="Flag storage and disks fuller than this percentage")
        BACKUP_MAX_AGE_DAYS: int = Field(default=7, description="Flag guests whose newest backup is older than this many days")
        ENABLE_ACTIONS: bool = Field(
            default=False,
            description="Allow start, shutdown, reboot, stop and snapshots. Off by default. Use a token with only the permissions you want the AI to have.",
        )
        ACTIONS_ADMIN_ONLY: bool = Field(default=True, description="Only Open WebUI admins can run actions")
        CONFIRM_ACTIONS: bool = Field(default=True, description="Ask the user to confirm every action in the chat before it runs")

    def __init__(self):
        self.valves = self.Valves()
        self._good_host: Optional[str] = None

    # ============= HELPERS =============

    def _hosts(self) -> list:
        hosts = []
        for raw in self.valves.PROXMOX_HOST.split(","):
            host = raw.strip()
            for prefix in ("https://", "http://"):
                if host.startswith(prefix):
                    host = host[len(prefix):]
            host = host.split("/")[0]
            if not host:
                continue
            if ":" not in host.rsplit("]", 1)[-1]:
                host += ":8006"
            hosts.append(host)
        if self._good_host in hosts:
            hosts.remove(self._good_host)
            hosts.insert(0, self._good_host)
        return hosts

    def _auth_header(self) -> dict:
        token_id = self.valves.PROXMOX_TOKEN_ID.strip()
        secret = self.valves.PROXMOX_TOKEN_SECRET.strip()
        if not self._hosts() or not token_id or not secret:
            raise ProxmoxError(
                "ProxmoxWeaver is not set up yet.",
                "Fill in PROXMOX_HOST, PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET under Workspace > Tools > ProxmoxWeaver > Valves.",
            )
        full_id = token_id if "!" in token_id else f"{self.valves.PROXMOX_USER.strip()}!{token_id}"
        return {"Authorization": f"PVEAPIToken={full_id}={secret}"}

    def _zone(self, user: Optional[dict]) -> Any:
        for name in (self.valves.TIMEZONE, (user or {}).get("timezone")):
            if name:
                try:
                    return ZoneInfo(str(name))
                except Exception:
                    continue
        return timezone.utc

    def _when(self, epoch: Optional[float], zone: Any) -> Optional[str]:
        if not epoch:
            return None
        return datetime.fromtimestamp(float(epoch), zone).strftime("%Y-%m-%d %H:%M %Z")

    async def _run(self, emitter: Emitter, label: str, work: Callable[[_Session], Awaitable[Any]]) -> Any:
        await _emit(emitter, f"{label}...")
        try:
            async with _Session(self) as session:
                result = await work(session)
            await _emit(emitter, label, done=True)
            return result
        except ProxmoxError as e:
            await _emit(emitter, f"{label} failed", done=True)
            out = {"error": str(e)}
            if e.hint:
                out["hint"] = e.hint
            return out
        except Exception as e:
            await _emit(emitter, f"{label} failed", done=True)
            return {"error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def _kind(resource: dict) -> str:
        return "vm" if resource.get("type") == "qemu" else "ct"

    @staticmethod
    def _api_type(resource: dict) -> str:
        return "qemu" if resource.get("type") == "qemu" else "lxc"

    def _guest_summary(self, r: dict) -> dict:
        kind = self._kind(r)
        out = {
            "vmid": r.get("vmid"),
            "name": r.get("name") or f"{kind}-{r.get('vmid')}",
            "type": kind,
            "node": r.get("node"),
            "status": r.get("status"),
        }
        if r.get("template"):
            out["template"] = True
        out["cores"] = r.get("maxcpu")
        if r.get("status") == "running":
            out["cpu_pct"] = round(float(r.get("cpu") or 0) * 100, 1)
            out["memory"] = f"{_size(r.get('mem'))} of {_size(r.get('maxmem'))}"
            out["memory_pct"] = _pct(r.get("mem"), r.get("maxmem"))
            out["uptime"] = _duration(r.get("uptime"))
            # Proxmox only knows real disk usage for containers (and VMs with a guest agent).
            if r.get("disk") and r.get("maxdisk"):
                out["disk"] = f"{_size(r.get('disk'))} of {_size(r.get('maxdisk'))}"
                out["disk_pct"] = _pct(r.get("disk"), r.get("maxdisk"))
            else:
                out["disk_size"] = _size(r.get("maxdisk"))
        else:
            out["memory"] = _size(r.get("maxmem"))
            out["disk_size"] = _size(r.get("maxdisk"))
        if r.get("tags"):
            out["tags"] = [t for t in re.split(r"[;, ]+", r["tags"]) if t]
        if r.get("lock"):
            out["lock"] = r["lock"]
        if r.get("hastate"):
            out["ha"] = r["hastate"]
        if r.get("status") == "unknown":
            out["note"] = "Its node is offline, so the real status is unknown."
        return {k: v for k, v in out.items() if v is not None}

    async def _guests(self, s: _Session, include_templates: bool = True) -> list:
        res = await s.resources()
        return [
            r
            for r in res
            if r.get("type") in ("qemu", "lxc") and (include_templates or not r.get("template"))
        ]

    async def _resolve_guest(self, s: _Session, query: Any) -> dict:
        text = str(query or "").strip()
        if not text:
            raise ProxmoxError("No guest given.", "Pass a guest name or VMID.")
        guests = await self._guests(s)
        match = re.fullmatch(r"(?:vm|ct|lxc|qemu)?\s*[/#-]?\s*(\d+)", text, re.IGNORECASE)
        if match:
            vmid = int(match.group(1))
            for g in guests:
                if int(g.get("vmid", -1)) == vmid:
                    return g
            raise ProxmoxError(f"No VM or container has VMID {vmid}.", "Use list_guests to see what exists.")
        lowered = text.lower()
        exact = [g for g in guests if str(g.get("name", "")).lower() == lowered]
        if len(exact) == 1:
            return exact[0]
        partial = exact or [g for g in guests if lowered in str(g.get("name", "")).lower()]
        if len(partial) == 1:
            return partial[0]
        if not partial:
            raise ProxmoxError(f"No VM or container is named like '{text}'.", "Use list_guests to see the names.")
        options = ", ".join(f"{g.get('name')} ({g.get('vmid')})" for g in partial[:10])
        raise ProxmoxError(f"'{text}' matches several guests: {options}.", "Ask again with the exact name or the VMID.")

    async def _resolve_node(self, s: _Session, query: str) -> dict:
        nodes = [r for r in await s.resources() if r.get("type") == "node"]
        text = str(query or "").strip().lower()
        names = ", ".join(sorted(n["node"] for n in nodes))
        if not text:
            raise ProxmoxError("No node given.", f"Nodes are: {names}.")
        exact = [n for n in nodes if n["node"].lower() == text]
        partial = exact or [n for n in nodes if text in n["node"].lower()]
        if len(partial) == 1:
            return partial[0]
        if not partial:
            raise ProxmoxError(f"No node is named like '{query}'.", f"Nodes are: {names}.")
        raise ProxmoxError(f"'{query}' matches several nodes.", f"Nodes are: {names}.")

    async def _guest_ips(self, s: _Session, g: dict) -> tuple:
        if g.get("status") != "running":
            return [], "not running"
        node, vmid = g["node"], g["vmid"]
        try:
            ips = []
            if g.get("type") == "qemu":
                data = await s.get(f"/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces")
                for iface in (data or {}).get("result", []):
                    if str(iface.get("name", "")).startswith(IGNORED_IFACES):
                        continue
                    ips += [a.get("ip-address") for a in iface.get("ip-addresses", [])]
            else:
                for iface in await s.get(f"/nodes/{node}/lxc/{vmid}/interfaces") or []:
                    if str(iface.get("name", "")).startswith(IGNORED_IFACES):
                        continue
                    for key in ("inet", "inet6"):
                        for addr in str(iface.get(key) or "").split():
                            ips.append(addr.split("/")[0])
            ips = [ip for ip in ips if ip and not ip.lower().startswith(("127.", "::1", "fe80"))]
            return ips, None if ips else "no address reported"
        except ProxmoxError as e:
            text = str(e).lower()
            if "agent" in text:
                return [], "QEMU guest agent not running or not enabled, so the VM's IP is unknown"
            return [], str(e)

    async def _backup_index(self, s: _Session) -> tuple:
        """Newest-first backups per VMID from every storage that holds backups."""
        config, _ = await s.attempt(s.get("/storage"))
        res = await s.resources()
        holds_backups = {}
        for c in config or []:
            if "backup" in str(c.get("content", "")) and not c.get("disable"):
                holds_backups[c["storage"]] = c
        targets, seen = [], set()
        for r in res:
            if r.get("type") != "storage" or r.get("status") != "available":
                continue
            name = r.get("storage")
            cfg = holds_backups.get(name)
            if cfg is None and not (config is None and "backup" in str(r.get("content", ""))):
                continue
            shared = bool(r.get("shared")) or (cfg or {}).get("type") in SHARED_STORAGE_TYPES
            key = name if shared else f"{r.get('node')}/{name}"
            if key in seen:
                continue
            seen.add(key)
            targets.append((r.get("node"), name))

        async def fetch(node: str, store: str) -> tuple:
            items, err = await s.attempt(s.get(f"/nodes/{node}/storage/{store}/content", {"content": "backup"}))
            return store, items or [], err

        index, errors = {}, []
        for store, items, err in await asyncio.gather(*(fetch(n, st) for n, st in targets)):
            if err:
                errors.append(f"{store}: {err}")
            for b in items:
                vmid = b.get("vmid")
                if vmid is None:
                    found = re.search(r"/(?:vm|ct)/(\d+)/|vzdump-(?:qemu|lxc)-(\d+)-", str(b.get("volid", "")))
                    vmid = next((x for x in (found.groups() if found else ()) if x), None)
                if vmid is None:
                    continue
                index.setdefault(int(vmid), []).append(
                    {
                        "storage": store,
                        "time": b.get("ctime"),
                        "size": b.get("size"),
                        "verified": (b.get("verification") or {}).get("state"),
                        "protected": bool(b.get("protected")),
                        "notes": b.get("notes"),
                    }
                )
        for backups in index.values():
            backups.sort(key=lambda x: x.get("time") or 0, reverse=True)
        return index, errors, sorted({t[1] for t in targets})

    async def _check_action_allowed(self, user: Optional[dict]) -> None:
        if not self.valves.ENABLE_ACTIONS:
            raise ProxmoxError(
                "Actions are turned off in ProxmoxWeaver.",
                "An admin can turn on ENABLE_ACTIONS in the tool's Valves. Until then the tool is read-only.",
            )
        if self.valves.ACTIONS_ADMIN_ONLY and (user or {}).get("role") != "admin":
            raise ProxmoxError("Only Open WebUI admins can run Proxmox actions.")

    async def _confirm(self, event_call: Any, title: str, message: str) -> bool:
        if not self.valves.CONFIRM_ACTIONS:
            return True
        if event_call is None:
            raise ProxmoxError(
                "Cannot ask for confirmation here.",
                "Run this from a chat in the browser, or turn off CONFIRM_ACTIONS.",
            )
        answer = await event_call({"type": "confirmation", "data": {"title": title, "message": message}})
        if isinstance(answer, dict) and answer.get("error"):
            raise ProxmoxError(f"Could not get confirmation: {answer['error']}")
        return answer is True

    async def _wait_task(self, s: _Session, node: str, upid: str, seconds: int = 45) -> Optional[str]:
        path = f"/nodes/{node}/tasks/{quote(str(upid), safe='')}/status"
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            status, _ = await s.attempt(s.get(path))
            if status and status.get("status") == "stopped":
                return status.get("exitstatus") or "unknown"
            await asyncio.sleep(2)
        return None

    # ============= CLUSTER =============

    async def get_cluster_overview(self, __event_emitter__: Emitter = None) -> dict:
        """
        Cluster health at a glance: every node (online or offline, CPU, memory, disk, uptime), guest counts, storage use and warnings. Start here for "how is the cluster" questions.
        """

        async def work(s: _Session) -> dict:
            (status, _), res, (version, _) = await asyncio.gather(
                s.attempt(s.get("/cluster/status")), s.resources(), s.attempt(s.get("/version"))
            )
            status = status or []
            cluster = next((x for x in status if x.get("type") == "cluster"), {})
            ips = {x.get("name"): x.get("ip") for x in status if x.get("type") == "node"}
            warn = self.valves.STORAGE_WARN_PERCENT
            nodes, warnings = [], []
            cores = used_cpu = mem = mem_total = 0.0
            for n in sorted((r for r in res if r.get("type") == "node"), key=lambda r: r["node"]):
                entry = {"name": n["node"], "status": n.get("status"), "ip": ips.get(n["node"])}
                if n.get("status") == "online":
                    entry.update(
                        {
                            "cpu_pct": round(float(n.get("cpu") or 0) * 100, 1),
                            "cores": n.get("maxcpu"),
                            "memory": f"{_size(n.get('mem'))} of {_size(n.get('maxmem'))}",
                            "memory_pct": _pct(n.get("mem"), n.get("maxmem")),
                            "root_disk_pct": _pct(n.get("disk"), n.get("maxdisk")),
                            "uptime": _duration(n.get("uptime")),
                        }
                    )
                    cores += n.get("maxcpu") or 0
                    used_cpu += float(n.get("cpu") or 0) * (n.get("maxcpu") or 0)
                    mem += n.get("mem") or 0
                    mem_total += n.get("maxmem") or 0
                    if (entry["memory_pct"] or 0) >= 90:
                        warnings.append(f"Node {n['node']} memory is at {entry['memory_pct']}%.")
                    if (entry["root_disk_pct"] or 0) >= warn:
                        warnings.append(f"Node {n['node']} root disk is at {entry['root_disk_pct']}%.")
                else:
                    warnings.append(f"Node {n['node']} is {n.get('status') or 'offline'}.")
                nodes.append(entry)

            counts = {"vms": {}, "containers": {}, "templates": 0}
            for g in (r for r in res if r.get("type") in ("qemu", "lxc")):
                if g.get("template"):
                    counts["templates"] += 1
                    continue
                bucket = counts["vms" if g["type"] == "qemu" else "containers"]
                bucket[g.get("status", "unknown")] = bucket.get(g.get("status", "unknown"), 0) + 1

            storage, seen = [], set()
            for st in sorted((r for r in res if r.get("type") == "storage"), key=lambda r: r.get("storage", "")):
                shared = bool(st.get("shared"))
                key = st["storage"] if shared else f"{st.get('node')}/{st['storage']}"
                if key in seen or st.get("status") != "available" or not st.get("maxdisk"):
                    continue
                seen.add(key)
                pct = _pct(st.get("disk"), st.get("maxdisk"))
                storage.append({"name": st["storage"], "where": "shared" if shared else st.get("node"), "used_pct": pct, "free": _size((st.get("maxdisk") or 0) - (st.get("disk") or 0))})
                if (pct or 0) >= warn:
                    warnings.append(f"Storage {key} is {pct}% full.")

            online = sum(1 for n in nodes if n["status"] == "online")
            return {
                "cluster": cluster.get("name") or "standalone node",
                "quorate": bool(cluster.get("quorate")) if cluster else None,
                "proxmox_version": (version or {}).get("version"),
                "nodes_online": f"{online} of {len(nodes)}",
                "cluster_cpu_pct": round(100 * used_cpu / cores, 1) if cores else None,
                "cluster_memory": f"{_size(mem)} of {_size(mem_total)} ({_pct(mem, mem_total)}%)",
                "nodes": nodes,
                "guests": counts,
                "storage": storage,
                "warnings": warnings or ["none"],
            }

        return await self._run(__event_emitter__, "Checking the cluster", work)

    async def get_health_report(self, __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Full health check that flags problems: offline nodes, quorum, full storage, failing disks, failed tasks in the last 24 hours, stuck locks, pending updates, and guests with no recent backup. Use for "anything wrong?" or "flag issues" questions.
        """
        zone = self._zone(__user__)

        async def work(s: _Session) -> dict:
            issues = []

            def flag(severity: str, what: str, detail: str) -> None:
                issues.append({"severity": severity, "what": what, "detail": detail})

            res = await s.resources()
            (status, _), (tasks, task_err) = await asyncio.gather(
                s.attempt(s.get("/cluster/status")), s.attempt(s.get("/cluster/tasks"))
            )
            cluster = next((x for x in status or [] if x.get("type") == "cluster"), None)
            if cluster is not None and not cluster.get("quorate"):
                flag("critical", "cluster", "The cluster has lost quorum. Guests cannot be started or changed until it is back.")

            warn = self.valves.STORAGE_WARN_PERCENT
            nodes = sorted((r for r in res if r.get("type") == "node"), key=lambda r: r["node"])
            online = [n["node"] for n in nodes if n.get("status") == "online"]
            for n in nodes:
                if n.get("status") != "online":
                    guests = [g for g in res if g.get("type") in ("qemu", "lxc") and g.get("node") == n["node"] and not g.get("template")]
                    flag("critical", f"node {n['node']}", f"Offline. {len(guests)} guest(s) on it are unreachable.")
                    continue
                mem_pct = _pct(n.get("mem"), n.get("maxmem")) or 0
                cpu_pct = round(float(n.get("cpu") or 0) * 100, 1)
                root_pct = _pct(n.get("disk"), n.get("maxdisk")) or 0
                if mem_pct >= 90:
                    flag("warning", f"node {n['node']}", f"Memory at {mem_pct}%.")
                if cpu_pct >= 90:
                    flag("warning", f"node {n['node']}", f"CPU at {cpu_pct}%.")
                if root_pct >= warn:
                    flag("warning", f"node {n['node']}", f"Root disk at {root_pct}%.")

            seen = set()
            for st in (r for r in res if r.get("type") == "storage"):
                key = st["storage"] if st.get("shared") else f"{st.get('node')}/{st['storage']}"
                if key in seen or st.get("node") not in online:
                    continue
                seen.add(key)
                if st.get("status") != "available":
                    flag("warning", f"storage {key}", f"Status is {st.get('status')}.")
                    continue
                pct = _pct(st.get("disk"), st.get("maxdisk"))
                if pct is not None and pct >= warn:
                    flag("critical" if pct >= 95 else "warning", f"storage {key}", f"{pct}% full, {_size((st.get('maxdisk') or 0) - (st.get('disk') or 0))} free.")

            for g in (r for r in res if r.get("type") in ("qemu", "lxc")):
                if g.get("lock"):
                    flag("warning", f"{self._kind(g)} {g.get('vmid')} {g.get('name')}", f"Locked ({g['lock']}). A stuck lock blocks changes; clear it only if no task is running.")

            names = {int(g["vmid"]): g.get("name") for g in res if g.get("type") in ("qemu", "lxc")}
            cutoff = time.time() - 86400
            if task_err:
                flag("info", "tasks", f"Could not read the task list: {task_err}")
            for t in tasks or []:
                if (t.get("starttime") or 0) < cutoff or t.get("type") in CONSOLE_TASKS:
                    continue
                result = t.get("status")
                if result and result != "OK" and not str(result).startswith("WARNINGS"):
                    target = t.get("id") or ""
                    label = f"{target} {names.get(int(target), '')}".strip() if str(target).isdigit() else target
                    flag("warning", f"task {TASK_NAMES.get(t.get('type'), t.get('type'))} {label}".strip(), f"Failed on {t.get('node')} at {self._when(t.get('starttime'), zone)}: {result}")

            async def node_checks(node: str) -> None:
                (updates, _), (disks, _) = await asyncio.gather(
                    s.attempt(s.get(f"/nodes/{node}/apt/update")), s.attempt(s.get(f"/nodes/{node}/disks/list"))
                )
                if updates:
                    pve = sum(1 for u in updates if str(u.get("Package", "")).startswith(("pve-", "proxmox-", "qemu-server", "lxc-pve")))
                    flag("info", f"node {node}", f"{len(updates)} package update(s) waiting" + (f", {pve} of them Proxmox packages." if pve else "."))
                for d in disks or []:
                    health = str(d.get("health") or "").upper()
                    if health and health not in ("PASSED", "OK", "UNKNOWN"):
                        flag("critical", f"disk {node}:{d.get('devpath')}", f"SMART health is {health} ({d.get('model')}). Replace it soon.")

            await asyncio.gather(*(node_checks(n) for n in online))

            index, backup_errors, _ = await self._backup_index(s)
            max_age = self.valves.BACKUP_MAX_AGE_DAYS * 86400
            never, stale = [], []
            for g in res:
                # Guests on an offline node are already covered by the node flag above.
                if g.get("type") not in ("qemu", "lxc") or g.get("template") or g.get("status") == "unknown":
                    continue
                newest = (index.get(int(g["vmid"])) or [{}])[0].get("time")
                label = f"{g.get('name') or self._kind(g)} ({g.get('vmid')})"
                if not newest:
                    never.append(label)
                elif time.time() - newest > max_age:
                    stale.append(f"{label}, last {_ago(newest)}")
            if never:
                flag("warning", "backups", "No backup found for: " + ", ".join(never))
            if stale:
                flag("warning", "backups", f"Newest backup older than {self.valves.BACKUP_MAX_AGE_DAYS} days: " + "; ".join(stale))
            for err in backup_errors:
                flag("info", "backups", f"Could not read a backup storage: {err}")

            order = {"critical": 0, "warning": 1, "info": 2}
            issues.sort(key=lambda i: order[i["severity"]])
            worst = issues[0]["severity"] if issues else "ok"
            return {
                "overall": {"critical": "CRITICAL", "warning": "WARNING"}.get(worst, "OK"),
                "issue_count": sum(1 for i in issues if i["severity"] != "info"),
                "issues": issues or [{"severity": "ok", "what": "cluster", "detail": "No problems found."}],
                "checked": f"{len(nodes)} nodes, {len(seen)} storages, quorum, disks, updates, tasks from the last 24 hours, backups",
            }

        return await self._run(__event_emitter__, "Running health checks", work)

    async def get_storage(self, node: str = "", __event_emitter__: Emitter = None) -> dict:
        """
        Storage pools with type, used and free space, and what they hold. Shared storage (NFS, PBS) is listed once.
        :param node: Only this node's storage. Leave empty for the whole cluster.
        """

        async def work(s: _Session) -> dict:
            res = await s.resources()
            only = (await self._resolve_node(s, node))["node"] if node.strip() else None
            warn = self.valves.STORAGE_WARN_PERCENT
            pools, seen = [], set()
            for st in sorted((r for r in res if r.get("type") == "storage"), key=lambda r: (r.get("storage", ""), r.get("node", ""))):
                if only and st.get("node") != only:
                    continue
                shared = bool(st.get("shared"))
                key = st["storage"] if shared else f"{st.get('node')}/{st['storage']}"
                if key in seen:
                    continue
                seen.add(key)
                pct = _pct(st.get("disk"), st.get("maxdisk"))
                pools.append(
                    {
                        "name": st["storage"],
                        "where": "shared" if shared else st.get("node"),
                        "type": st.get("plugintype"),
                        "status": st.get("status"),
                        "used": f"{_size(st.get('disk'))} of {_size(st.get('maxdisk'))}" if st.get("maxdisk") else None,
                        "used_pct": pct,
                        "free": _size((st.get("maxdisk") or 0) - (st.get("disk") or 0)) if st.get("maxdisk") else None,
                        "holds": st.get("content"),
                        "warning": bool(pct is not None and pct >= warn),
                    }
                )
            return {"count": len(pools), "storage": pools}

        return await self._run(__event_emitter__, "Reading storage", work)

    async def get_recent_tasks(
        self,
        hours: int = 24,
        errors_only: bool = False,
        node: str = "",
        limit: int = 25,
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Recent cluster tasks (backups, starts, stops, snapshots, migrations) with result and duration, newest first.
        :param hours: How far back to look, in hours.
        :param errors_only: Only tasks that failed or are still running.
        :param node: Only tasks on this node. Leave empty for all nodes.
        :param limit: Most tasks to return.
        """
        zone = self._zone(__user__)

        async def work(s: _Session) -> dict:
            tasks = await s.get("/cluster/tasks") or []
            res = await s.resources()
            names = {int(g["vmid"]): g.get("name") for g in res if g.get("type") in ("qemu", "lxc")}
            only = (await self._resolve_node(s, node))["node"] if node.strip() else None
            cutoff = time.time() - max(1, int(hours)) * 3600
            out = []
            for t in sorted(tasks, key=lambda x: x.get("starttime") or 0, reverse=True):
                if (t.get("starttime") or 0) < cutoff or t.get("type") in CONSOLE_TASKS:
                    continue
                if only and t.get("node") != only:
                    continue
                running = not t.get("endtime")
                result = "running" if running else (t.get("status") or "unknown")
                if errors_only and result == "OK":
                    continue
                target = str(t.get("id") or "")
                entry = {
                    "when": self._when(t.get("starttime"), zone),
                    "ago": _ago(t.get("starttime")),
                    "task": TASK_NAMES.get(t.get("type"), t.get("type")),
                    "target": f"{target} {names.get(int(target), '')}".strip() if target.isdigit() else target or None,
                    "node": t.get("node"),
                    "user": t.get("user"),
                    "result": result,
                }
                if not running:
                    entry["took"] = _duration((t.get("endtime") or 0) - (t.get("starttime") or 0))
                out.append(entry)
                if len(out) >= max(1, int(limit)):
                    break
            return {"hours": hours, "count": len(out), "tasks": out or ["No matching tasks."]}

        return await self._run(__event_emitter__, "Reading recent tasks", work)

    # ============= NODES =============

    async def get_node_details(self, node: str, __event_emitter__: Emitter = None) -> dict:
        """
        One node in depth: CPU model, load, memory, kernel and Proxmox version, pending package updates, physical disks with SMART health, and its storage.
        :param node: Node name. Part of the name works, for example "host01".
        """

        async def work(s: _Session) -> dict:
            n = await self._resolve_node(s, node)
            name = n["node"]
            if n.get("status") != "online":
                return {"node": name, "status": n.get("status") or "offline", "note": "The node is not answering, so no details are available."}
            (status, status_err), (updates, upd_err), (disks, disk_err) = await asyncio.gather(
                s.attempt(s.get(f"/nodes/{name}/status")),
                s.attempt(s.get(f"/nodes/{name}/apt/update")),
                s.attempt(s.get(f"/nodes/{name}/disks/list")),
            )
            status = status or {}
            cpu = status.get("cpuinfo") or {}
            memory = status.get("memory") or {}
            swap = status.get("swap") or {}
            rootfs = status.get("rootfs") or {}
            out = {
                "node": name,
                "status": "online",
                "proxmox_version": status.get("pveversion"),
                "kernel": (status.get("current-kernel") or {}).get("release") or status.get("kversion"),
                "cpu_model": cpu.get("model"),
                "cpu": f"{cpu.get('cpus')} threads, {cpu.get('sockets')} socket(s)" if cpu else None,
                "cpu_pct": round(float(n.get("cpu") or 0) * 100, 1),
                "load_average": status.get("loadavg"),
                "memory": f"{_size(memory.get('used'))} of {_size(memory.get('total'))}" if memory else None,
                "memory_pct": _pct(memory.get("used"), memory.get("total")),
                "swap": f"{_size(swap.get('used'))} of {_size(swap.get('total'))}" if swap.get("total") else "none",
                "root_disk": f"{_size(rootfs.get('used'))} of {_size(rootfs.get('total'))} ({_pct(rootfs.get('used'), rootfs.get('total'))}%)" if rootfs else None,
                "uptime": _duration(status.get("uptime") or n.get("uptime")),
                "boot_mode": (status.get("boot-info") or {}).get("mode"),
            }
            if status_err:
                out["status_error"] = status_err
            if upd_err:
                out["updates"] = f"Could not read: {upd_err}"
            else:
                updates = updates or []
                out["updates"] = {
                    "count": len(updates),
                    "packages": [f"{u.get('Package')} {u.get('OldVersion')} -> {u.get('Version')}" for u in updates[:20]],
                }
                if len(updates) > 20:
                    out["updates"]["more"] = len(updates) - 20
            if disk_err:
                out["disks"] = f"Could not read: {disk_err}"
            else:
                out["disks"] = [
                    {
                        "device": d.get("devpath"),
                        "model": d.get("model"),
                        "type": d.get("type"),
                        "size": _size(d.get("size")),
                        "smart_health": d.get("health"),
                        "wearout": d.get("wearout"),
                        "used_for": d.get("used"),
                    }
                    for d in disks or []
                ]
            res = await s.resources()
            out["storage"] = [
                {"name": st["storage"], "type": st.get("plugintype"), "used_pct": _pct(st.get("disk"), st.get("maxdisk")), "status": st.get("status")}
                for st in res
                if st.get("type") == "storage" and st.get("node") == name
            ]
            return out

        return await self._run(__event_emitter__, f"Reading node {node}", work)

    # ============= GUESTS =============

    async def list_guests(
        self,
        guest_type: Literal["all", "vm", "ct"] = "all",
        status: Literal["any", "running", "stopped"] = "any",
        search: str = "",
        node: str = "",
        include_templates: bool = False,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        List virtual machines and LXC containers across the whole cluster with status, CPU, memory and disk. Works even when a node is offline.
        :param guest_type: "vm" for virtual machines, "ct" for containers, or "all".
        :param status: "running", "stopped", or "any".
        :param search: Part of a name, or a VMID, to filter on. Leave empty for all.
        :param node: Only guests on this node. Leave empty for all nodes.
        :param include_templates: Also list templates.
        """

        async def work(s: _Session) -> dict:
            guests = await self._guests(s, include_templates)
            only = (await self._resolve_node(s, node))["node"] if node.strip() else None
            text = search.strip().lower()
            out = []
            for g in sorted(guests, key=lambda r: (r.get("node", ""), int(r.get("vmid", 0)))):
                if guest_type != "all" and self._kind(g) != guest_type:
                    continue
                if status != "any" and g.get("status") != status:
                    continue
                if only and g.get("node") != only:
                    continue
                if text and text not in str(g.get("name", "")).lower() and text != str(g.get("vmid")):
                    continue
                out.append(self._guest_summary(g))
            result = {"count": len(out), "guests": out}
            offline = sorted({g["node"] for g in out if g.get("status") == "unknown"})
            if offline:
                result["note"] = f"Node(s) {', '.join(offline)} are offline; their guests show status unknown."
            return result

        return await self._run(__event_emitter__, "Listing guests", work)

    async def get_guest_details(self, name_or_id: str, __event_emitter__: Emitter = None) -> dict:
        """
        Everything about one VM or container: status and usage, IP addresses, CPU, memory, disks, network cards, boot settings, snapshots and description. No node needed.
        :param name_or_id: Guest name (part of it works) or VMID, for example "open-webui" or "116".
        """

        async def work(s: _Session) -> dict:
            g = await self._resolve_guest(s, name_or_id)
            out = self._guest_summary(g)
            if g.get("status") == "unknown":
                return out
            base = f"/nodes/{g['node']}/{self._api_type(g)}/{g['vmid']}"
            (config, cfg_err), (snaps, _), (ips, ip_note) = await asyncio.gather(
                s.attempt(s.get(f"{base}/config")),
                s.attempt(s.get(f"{base}/snapshot")),
                self._guest_ips(s, g),
            )
            out["ip_addresses"] = ips or ip_note
            if cfg_err:
                out["config_error"] = cfg_err
                return out
            config = config or {}
            disks, nics = [], []
            disk_key = re.compile(r"^(scsi|virtio|sata|ide|efidisk|tpmstate|rootfs|mp|unused)\d*$")
            for key in sorted(config):
                value = str(config[key])
                if disk_key.match(key):
                    if "media=cdrom" in value:
                        if not value.startswith("none"):
                            disks.append({"slot": key, "cd": value.split(",")[0]})
                        continue
                    size = re.search(r"size=([^,]+)", value)
                    disks.append({"slot": key, "volume": value.split(",")[0], "size": size.group(1) if size else None})
                elif re.match(r"^net\d+$", key):
                    parts = dict(p.split("=", 1) for p in value.split(",") if "=" in p)
                    nic = {"slot": key, "bridge": parts.get("bridge"), "firewall": parts.get("firewall") == "1"}
                    if g.get("type") == "lxc":
                        nic.update({"name": parts.get("name"), "mac": parts.get("hwaddr"), "ip_config": parts.get("ip")})
                    else:
                        model = next((m for m in ("virtio", "e1000", "e1000e", "rtl8139", "vmxnet3") if m in parts), None)
                        nic.update({"model": model, "mac": parts.get(model) if model else None})
                    if parts.get("tag"):
                        nic["vlan"] = parts["tag"]
                    nics.append(nic)
            out.update(
                {
                    "os_type": config.get("ostype"),
                    "cores": config.get("cores") or out.get("cores"),
                    "sockets": config.get("sockets"),
                    "memory_mb": config.get("memory"),
                    "balloon_mb": config.get("balloon"),
                    "swap_mb": config.get("swap"),
                    "disks": disks,
                    "network": nics,
                    "start_at_boot": bool(config.get("onboot")),
                    "boot_order": config.get("boot") or config.get("startup"),
                    "guest_agent": config.get("agent") if g.get("type") == "qemu" else None,
                    "protected": bool(config.get("protection")),
                    "unprivileged": bool(config.get("unprivileged")) if g.get("type") == "lxc" else None,
                    "features": config.get("features"),
                    "description": " ".join(re.sub(r"<[^>]+>", " ", str(config.get("description") or "")).split())[:400] or None,
                }
            )
            snaps = [x for x in snaps or [] if x.get("name") != "current"]
            out["snapshots"] = [x.get("name") for x in sorted(snaps, key=lambda x: x.get("snaptime") or 0)] or "none"
            return {k: v for k, v in out.items() if v not in (None, [], "")}

        return await self._run(__event_emitter__, f"Reading {name_or_id}", work)

    async def get_guest_ips(self, name_or_id: str = "", __event_emitter__: Emitter = None) -> dict:
        """
        IP addresses of running VMs and containers, read live from the guests. VMs need the QEMU guest agent. Use to find where a service is reachable.
        :param name_or_id: One guest's name or VMID. Leave empty for every running guest.
        """

        async def work(s: _Session) -> dict:
            if name_or_id.strip():
                targets = [await self._resolve_guest(s, name_or_id)]
            else:
                targets = [g for g in await self._guests(s, False) if g.get("status") == "running"]
            gate = asyncio.Semaphore(8)

            async def one(g: dict) -> dict:
                async with gate:
                    ips, note = await self._guest_ips(s, g)
                entry = {"vmid": g.get("vmid"), "name": g.get("name"), "type": self._kind(g), "node": g.get("node")}
                if ips:
                    entry["ips"] = ips
                if note:
                    entry["note"] = note
                return entry

            results = await asyncio.gather(*(one(g) for g in sorted(targets, key=lambda r: int(r.get("vmid", 0)))))
            return {"count": len(results), "guests": list(results)}

        return await self._run(__event_emitter__, "Looking up IP addresses", work)

    async def get_backup_status(self, name_or_id: str = "", __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Backup coverage: scheduled backup jobs, guests not in any job, and each guest's newest backup with its age. Flags guests with no recent backup.
        :param name_or_id: One guest's name or VMID to list its backups. Leave empty for the whole cluster.
        """
        zone = self._zone(__user__)

        async def work(s: _Session) -> dict:
            max_age = self.valves.BACKUP_MAX_AGE_DAYS * 86400
            index, errors, storages = await self._backup_index(s)
            if name_or_id.strip():
                g = await self._resolve_guest(s, name_or_id)
                backups = index.get(int(g["vmid"]), [])
                newest = backups[0]["time"] if backups else None
                return {
                    "guest": f"{g.get('name')} ({g.get('vmid')})",
                    "backup_count": len(backups),
                    "newest": self._when(newest, zone),
                    "newest_age": _ago(newest),
                    "stale": (not newest) or (time.time() - newest > max_age),
                    "backups": [
                        {
                            "when": self._when(b["time"], zone),
                            "storage": b["storage"],
                            "size": _size(b["size"]),
                            "verified": b["verified"],
                            "protected": b["protected"] or None,
                            "notes": b["notes"],
                        }
                        for b in backups[:10]
                    ],
                    "storages_checked": storages,
                    "errors": errors or None,
                }

            (jobs, jobs_err), (uncovered, _) = await asyncio.gather(
                s.attempt(s.get("/cluster/backup")), s.attempt(s.get("/cluster/backup-info/not-backed-up"))
            )
            job_list = []
            for j in jobs or []:
                if j.get("all"):
                    selection = "all guests" + (f" except {j['exclude']}" if j.get("exclude") else "")
                elif j.get("pool"):
                    selection = f"pool {j['pool']}"
                else:
                    selection = f"VMIDs {j.get('vmid')}"
                job_list.append(
                    {
                        "id": j.get("id"),
                        "enabled": j.get("enabled", 1) not in (0, "0", False),
                        "schedule": j.get("schedule") or j.get("starttime"),
                        "next_run": self._when(j.get("next-run"), zone),
                        "storage": j.get("storage"),
                        "guests": selection,
                        "node": j.get("node") or "any",
                        "mode": j.get("mode"),
                    }
                )
            # Guests on an offline node have no name in the cluster resources, but this list does.
            known = {int(u["vmid"]): u.get("name") for u in uncovered or [] if u.get("vmid") is not None}
            guests, stale, never, offline = [], 0, [], []
            for g in sorted(await self._guests(s, False), key=lambda r: int(r.get("vmid", 0))):
                backups = index.get(int(g["vmid"]), [])
                newest = backups[0] if backups else None
                label = f"{g.get('name') or known.get(int(g['vmid'])) or self._kind(g)} ({g.get('vmid')})"
                if not newest:
                    (offline if g.get("status") == "unknown" else never).append(label)
                    continue
                is_stale = time.time() - (newest["time"] or 0) > max_age
                stale += is_stale
                guests.append(
                    {
                        "vmid": g.get("vmid"),
                        "name": g.get("name"),
                        "newest": self._when(newest["time"], zone),
                        "age": _ago(newest["time"]),
                        "copies": len(backups),
                        "storage": newest["storage"],
                        "verified": newest["verified"],
                        "stale": is_stale,
                    }
                )
            return {
                "jobs": job_list or (f"Could not read jobs: {jobs_err}" if jobs_err else "No backup jobs are scheduled."),
                "not_in_any_job": [f"{u.get('name')} ({u.get('vmid')})" for u in uncovered or []] or "none",
                "never_backed_up": never or "none",
                "no_backup_and_node_offline": offline or None,
                "stale_count": stale,
                "max_age_days": self.valves.BACKUP_MAX_AGE_DAYS,
                "guests": guests,
                "storages_checked": storages,
                "errors": errors or None,
            }

        return await self._run(__event_emitter__, "Checking backups", work)

    async def list_snapshots(self, name_or_id: str, __user__: Optional[dict] = None, __event_emitter__: Emitter = None) -> dict:
        """
        Snapshots of one VM or container, oldest first, with time and description.
        :param name_or_id: Guest name or VMID.
        """
        zone = self._zone(__user__)

        async def work(s: _Session) -> dict:
            g = await self._resolve_guest(s, name_or_id)
            snaps = await s.get(f"/nodes/{g['node']}/{self._api_type(g)}/{g['vmid']}/snapshot") or []
            snaps = sorted((x for x in snaps if x.get("name") != "current"), key=lambda x: x.get("snaptime") or 0)
            return {
                "guest": f"{g.get('name')} ({g.get('vmid')})",
                "count": len(snaps),
                "snapshots": [
                    {
                        "name": x.get("name"),
                        "when": self._when(x.get("snaptime"), zone),
                        "age": _ago(x.get("snaptime")),
                        "description": (x.get("description") or "").strip() or None,
                        "includes_ram": bool(x.get("vmstate")),
                    }
                    for x in snaps
                ]
                or "none",
            }

        return await self._run(__event_emitter__, f"Listing snapshots of {name_or_id}", work)

    async def get_usage_history(
        self,
        name: str,
        timeframe: Literal["hour", "day", "week", "month", "year"] = "day",
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
    ) -> dict:
        """
        Average and peak CPU, memory, network and disk activity over time for a node or a guest, with when the peak happened. Use for "was it busy overnight" questions.
        :param name: Node name, guest name, or VMID.
        :param timeframe: "hour", "day", "week", "month", or "year".
        """
        zone = self._zone(__user__)

        async def work(s: _Session) -> dict:
            nodes = [r for r in await s.resources() if r.get("type") == "node"]
            text = name.strip().lower()
            node_match = [n for n in nodes if n["node"].lower() == text] or [n for n in nodes if text and text in n["node"].lower()]
            if len(node_match) == 1:
                target = node_match[0]
                label, kind = target["node"], "node"
                path = f"/nodes/{target['node']}/rrddata"
            else:
                target = await self._resolve_guest(s, name)
                label, kind = f"{target.get('name')} ({target.get('vmid')})", self._kind(target)
                path = f"/nodes/{target['node']}/{self._api_type(target)}/{target['vmid']}/rrddata"
            avg_points, peak_points = await asyncio.gather(
                s.get(path, {"timeframe": timeframe, "cf": "AVERAGE"}), s.get(path, {"timeframe": timeframe, "cf": "MAX"})
            )
            avg_points, peak_points = avg_points or [], peak_points or []

            def series(points: list, fn: Callable[[dict], Optional[float]]) -> list:
                out = []
                for p in points:
                    try:
                        value = fn(p)
                    except (TypeError, ZeroDivisionError, KeyError):
                        value = None
                    if value is not None:
                        out.append((p.get("time"), value))
                return out

            metrics = {
                "cpu_pct": (lambda p: p["cpu"] * 100, "%"),
                "memory_pct": (
                    (lambda p: 100 * p["memused"] / p["memtotal"]) if kind == "node" else (lambda p: 100 * p["mem"] / p["maxmem"]),
                    "%",
                ),
                "net_in": (lambda p: p["netin"], "rate"),
                "net_out": (lambda p: p["netout"], "rate"),
            }
            if kind == "node":
                metrics["load_average"] = (lambda p: p["loadavg"], "")
                metrics["io_wait_pct"] = (lambda p: p["iowait"] * 100, "%")
            else:
                metrics["disk_read"] = (lambda p: p["diskread"], "rate")
                metrics["disk_write"] = (lambda p: p["diskwrite"], "rate")

            def show(value: float, unit: str) -> Any:
                if unit == "rate":
                    return _rate(value)
                return round(value, 1) if unit == "%" else round(value, 2)

            out = {"target": label, "kind": kind, "timeframe": timeframe}
            times = [p.get("time") for p in avg_points if p.get("time")]
            if times:
                out["from"] = self._when(min(times), zone)
                out["to"] = self._when(max(times), zone)
            for key, (fn, unit) in metrics.items():
                avg = series(avg_points, fn)
                peak = series(peak_points, fn) or avg
                if not avg:
                    continue
                when, top = max(peak, key=lambda x: x[1])
                out[key] = {
                    "average": show(sum(v for _, v in avg) / len(avg), unit),
                    "peak": show(top, unit),
                    "peak_at": self._when(when, zone),
                }
            if len(out) <= 5:
                out["note"] = "No history recorded for this timeframe yet."
            return out

        return await self._run(__event_emitter__, f"Reading usage history for {name}", work)

    # ============= ACCESS AND CONNECTION =============

    async def get_access_overview(self, __event_emitter__: Emitter = None) -> dict:
        """
        Security overview: Proxmox users, API tokens (with privilege separation and expiry), groups, custom roles, and whether the cluster firewall is on.
        """

        async def work(s: _Session) -> dict:
            (users, users_err), (groups, _), (roles, _), (firewall, _) = await asyncio.gather(
                s.attempt(s.get("/access/users", {"full": 1})),
                s.attempt(s.get("/access/groups")),
                s.attempt(s.get("/access/roles")),
                s.attempt(s.get("/cluster/firewall/options")),
            )
            if users_err:
                raise ProxmoxError(users_err, "Reading users needs the User.Modify or Sys.Audit permission on /access.")
            notes = []
            user_list = []
            for u in users or []:
                tokens = []
                for t in u.get("tokens") or []:
                    full = not t.get("privsep")
                    tokens.append(
                        {
                            "token": f"{u.get('userid')}!{t.get('tokenid')}",
                            "full_user_permissions": full,
                            "expires": datetime.fromtimestamp(t["expire"], timezone.utc).strftime("%Y-%m-%d") if t.get("expire") else "never",
                            "comment": t.get("comment"),
                        }
                    )
                    if full and str(u.get("userid")) == "root@pam":
                        notes.append(f"Token {u.get('userid')}!{t.get('tokenid')} has full root access.")
                user_list.append(
                    {
                        "user": u.get("userid"),
                        "enabled": u.get("enable", 1) not in (0, "0", False),
                        "expires": datetime.fromtimestamp(u["expire"], timezone.utc).strftime("%Y-%m-%d") if u.get("expire") else "never",
                        "groups": u.get("groups") or [],
                        "tokens": tokens or None,
                    }
                )
            return {
                "cluster_firewall": "on" if (firewall or {}).get("enable") else "off",
                "users": user_list,
                "groups": [{"group": g.get("groupid"), "members": [m for m in str(g.get("users") or "").split(",") if m]} for g in groups or []],
                "custom_roles": [r.get("roleid") for r in roles or [] if not r.get("special")] or "none",
                "notes": notes or None,
            }

        return await self._run(__event_emitter__, "Reading users and permissions", work)

    async def check_connection(self, __event_emitter__: Emitter = None) -> dict:
        """
        Test the connection to each configured Proxmox host and the API token. Use when other Proxmox tools fail.
        """
        await _emit(__event_emitter__, "Testing Proxmox connection...")
        try:
            headers = self._auth_header()
        except ProxmoxError as e:
            await _emit(__event_emitter__, "Proxmox is not set up", done=True)
            return {"error": str(e), "hint": e.hint}
        seconds = max(3, int(self.valves.TIMEOUT_SECONDS))
        results = []
        async with httpx.AsyncClient(verify=self.valves.VERIFY_SSL, timeout=httpx.Timeout(seconds, connect=min(5, seconds)), headers=headers) as client:
            for host in self._hosts():
                entry = {"host": host}
                try:
                    r = await client.get(f"https://{host}/api2/json/version")
                    data = _parse_response(r, "/version") or {}
                    entry.update({"reachable": True, "token_accepted": True, "proxmox_version": data.get("version")})
                except ProxmoxError as e:
                    entry.update({"reachable": True, "token_accepted": False, "error": str(e), "hint": e.hint})
                except httpx.HTTPError as e:
                    entry.update({"reachable": False, "error": f"{type(e).__name__}: {e}"})
                results.append(entry)
        working = [r["host"] for r in results if r.get("token_accepted")]
        await _emit(__event_emitter__, "Proxmox connection tested", done=True)
        return {
            "status": "connected" if working else "failed",
            "using": working[0] if working else None,
            "hosts": results,
            "actions_enabled": self.valves.ENABLE_ACTIONS,
        }

    # ============= ACTIONS (off unless ENABLE_ACTIONS is on) =============

    async def guest_power(
        self,
        name_or_id: str,
        action: Literal["start", "shutdown", "reboot", "stop"],
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
        __event_call__: Any = None,
    ) -> dict:
        """
        Start, shut down, reboot or force stop a VM or container. Only works when an admin has turned actions on, and the user confirms each one.
        :param name_or_id: Guest name or VMID.
        :param action: "start", "shutdown" (clean), "reboot", or "stop" (hard power off, last resort).
        """

        async def work(s: _Session) -> dict:
            await self._check_action_allowed(__user__)
            g = await self._resolve_guest(s, name_or_id)
            label = f"{self._kind(g).upper()} {g.get('vmid')} ({g.get('name') or 'no name'}) on {g.get('node')}"
            state = g.get("status")
            if g.get("template"):
                raise ProxmoxError(f"{label} is a template and cannot be powered on or off.")
            if state == "unknown":
                raise ProxmoxError(f"{label} is on an offline node.", "Nothing can be done until the node is back.")
            if action == "start" and state == "running":
                return {"result": f"{label} is already running."}
            if action in ("shutdown", "reboot", "stop") and state == "stopped":
                return {"result": f"{label} is already stopped."}
            if g.get("lock"):
                raise ProxmoxError(f"{label} is locked ({g['lock']}).", "Wait for the running task to finish.")
            warning = " This is a hard power off, like pulling the plug." if action == "stop" else ""
            if not await self._confirm(__event_call__, f"Proxmox: {action} {g.get('name')}?", f"{action.capitalize()} {label}.{warning}"):
                return {"result": f"Cancelled. {label} was not changed."}
            upid = await s.post(f"/nodes/{g['node']}/{self._api_type(g)}/{g['vmid']}/status/{action}")
            await _emit(__event_emitter__, f"Waiting for {action} of {g.get('name')}...")
            outcome = await self._wait_task(s, g["node"], upid, 90 if action in ("shutdown", "reboot") else 45)
            if outcome is None:
                return {"result": f"{action} of {label} is still running.", "hint": "Check get_recent_tasks in a minute."}
            return {"result": f"{action} of {label}: {outcome}", "success": outcome == "OK"}

        return await self._run(__event_emitter__, f"{action.capitalize()} {name_or_id}", work)

    async def create_snapshot(
        self,
        name_or_id: str,
        snapshot_name: str = "",
        description: str = "",
        __user__: Optional[dict] = None,
        __event_emitter__: Emitter = None,
        __event_call__: Any = None,
    ) -> dict:
        """
        Take a snapshot of a VM or container, for example before an upgrade. Only works when an admin has turned actions on, and the user confirms it.
        :param name_or_id: Guest name or VMID.
        :param snapshot_name: Letters, numbers, - and _, starting with a letter. Leave empty for an automatic name with the date.
        :param description: Why the snapshot was taken.
        """

        async def work(s: _Session) -> dict:
            await self._check_action_allowed(__user__)
            g = await self._resolve_guest(s, name_or_id)
            label = f"{self._kind(g).upper()} {g.get('vmid')} ({g.get('name') or 'no name'}) on {g.get('node')}"
            if g.get("status") == "unknown":
                raise ProxmoxError(f"{label} is on an offline node.")
            name = snapshot_name.strip() or datetime.now(self._zone(__user__)).strftime("owui-%Y%m%d-%H%M")
            if not SNAPSHOT_NAME.match(name):
                raise ProxmoxError(
                    f"'{name}' is not a valid snapshot name.",
                    "Use 2 to 40 letters, numbers, - or _, starting with a letter.",
                )
            if not await self._confirm(__event_call__, f"Proxmox: snapshot {g.get('name')}?", f"Create snapshot '{name}' of {label}."):
                return {"result": f"Cancelled. No snapshot of {label} was taken."}
            data = {"snapname": name}
            if description.strip():
                data["description"] = description.strip()
            upid = await s.post(f"/nodes/{g['node']}/{self._api_type(g)}/{g['vmid']}/snapshot", data)
            await _emit(__event_emitter__, f"Waiting for snapshot of {g.get('name')}...")
            outcome = await self._wait_task(s, g["node"], upid, 120)
            if outcome is None:
                return {"result": f"Snapshot '{name}' of {label} is still being taken.", "hint": "Check list_snapshots in a minute."}
            return {"result": f"Snapshot '{name}' of {label}: {outcome}", "success": outcome == "OK"}

        return await self._run(__event_emitter__, f"Snapshot of {name_or_id}", work)

    # ============= VISUAL =============

    async def show_cluster_dashboard(self, __event_emitter__: Emitter = None) -> Any:
        """
        Show a visual dashboard in the chat: node cards with CPU, memory and disk bars, warnings, and a table of every VM and container. Use when the user wants to see the cluster.
        """

        async def work(s: _Session) -> Any:
            from fastapi.responses import HTMLResponse

            res = await s.resources()
            (status, _), (version, _) = await asyncio.gather(s.attempt(s.get("/cluster/status")), s.attempt(s.get("/version")))
            cluster = next((x for x in status or [] if x.get("type") == "cluster"), {})
            esc = html.escape

            def bar(pct: Optional[float]) -> str:
                pct = pct or 0
                level = "crit" if pct >= 90 else "warn" if pct >= self.valves.STORAGE_WARN_PERCENT else "ok"
                return f'<div class="bar"><span class="{level}" style="width:{min(pct, 100):.0f}%"></span></div><small>{pct:.0f}%</small>'

            cards, warnings = [], []
            nodes = sorted((r for r in res if r.get("type") == "node"), key=lambda r: r["node"])
            for n in nodes:
                if n.get("status") != "online":
                    warnings.append(f"Node {n['node']} is offline")
                    cards.append(f'<div class="card off"><h3>{esc(n["node"])}</h3><p class="bad">offline</p></div>')
                    continue
                cpu = float(n.get("cpu") or 0) * 100
                mem = _pct(n.get("mem"), n.get("maxmem"))
                disk = _pct(n.get("disk"), n.get("maxdisk"))
                cards.append(
                    f'<div class="card"><h3>{esc(n["node"])}</h3><p class="good">online, up {esc(_duration(n.get("uptime")) or "")}</p>'
                    f"<label>CPU</label>{bar(cpu)}<label>Memory</label>{bar(mem)}<label>Root disk</label>{bar(disk)}</div>"
                )
            seen = set()
            for st in (r for r in res if r.get("type") == "storage" and r.get("status") == "available"):
                key = st["storage"] if st.get("shared") else f"{st.get('node')}/{st['storage']}"
                pct = _pct(st.get("disk"), st.get("maxdisk"))
                if key not in seen and pct is not None and pct >= self.valves.STORAGE_WARN_PERCENT:
                    warnings.append(f"Storage {key} is {pct}% full")
                seen.add(key)

            rows = []
            guests = sorted(await self._guests(s, False), key=lambda r: (r.get("node", ""), int(r.get("vmid", 0))))
            for g in guests:
                summary = self._guest_summary(g)
                state = g.get("status") or "unknown"
                rows.append(
                    f'<tr><td>{g.get("vmid")}</td><td>{esc(str(summary["name"]))}</td><td>{summary["type"].upper()}</td>'
                    f'<td>{esc(str(g.get("node")))}</td><td><span class="dot {esc(state)}"></span>{esc(state)}</td>'
                    f'<td>{summary.get("cpu_pct", "")}{"%" if "cpu_pct" in summary else ""}</td><td>{esc(str(summary.get("memory") or ""))}</td></tr>'
                )
            running = sum(1 for g in guests if g.get("status") == "running")
            title = esc(cluster.get("name") or "Proxmox")
            quorum = "" if not cluster else ('<span class="good">quorate</span>' if cluster.get("quorate") else '<span class="bad">NO QUORUM</span>')
            warn_html = "".join(f"<li>{esc(w)}</li>" for w in warnings) or "<li>No warnings</li>"
            page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
:root {{ --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --card:#f6f8fa; --line:#d0d7de; --ok:#2da44e; --warn:#d4a72c; --crit:#cf222e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --card:#161b22; --line:#30363d; }} }}
body {{ margin:0; padding:14px; font:14px system-ui,sans-serif; background:var(--bg); color:var(--fg); }}
h2 {{ margin:0 0 4px; font-size:18px; }} .sub {{ color:var(--muted); margin-bottom:12px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); gap:10px; margin-bottom:12px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px; }}
.card.off {{ border-color:var(--crit); }} .card h3 {{ margin:0 0 4px; font-size:15px; }} .card p {{ margin:0 0 6px; font-size:12px; }}
label {{ display:block; font-size:11px; color:var(--muted); margin-top:4px; }}
.bar {{ display:inline-block; width:75%; height:8px; background:var(--line); border-radius:4px; overflow:hidden; vertical-align:middle; }}
.bar span {{ display:block; height:100%; }} .ok {{ background:var(--ok); }} .warn {{ background:var(--warn); }} .crit {{ background:var(--crit); }}
small {{ margin-left:6px; font-size:11px; }} .good {{ color:var(--ok); }} .bad {{ color:var(--crit); font-weight:600; }}
ul {{ margin:0 0 12px; padding-left:18px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ text-align:left; padding:5px 6px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); font-weight:600; }} .dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; background:var(--muted); }}
.dot.running {{ background:var(--ok); }} .dot.stopped {{ background:var(--line); }} .dot.unknown {{ background:var(--crit); }}
</style></head><body>
<h2>{title} {quorum}</h2>
<div class="sub">Proxmox {esc(str((version or {}).get("version") or ""))} &middot; {sum(1 for n in nodes if n.get("status") == "online")} of {len(nodes)} nodes online &middot; {running} of {len(guests)} guests running</div>
<div class="cards">{"".join(cards)}</div>
<ul>{warn_html}</ul>
<table><tr><th>ID</th><th>Name</th><th>Type</th><th>Node</th><th>Status</th><th>CPU</th><th>Memory</th></tr>{"".join(rows)}</table>
<script>
function reportHeight() {{ parent.postMessage({{ type: 'iframe:height', height: document.documentElement.scrollHeight }}, '*'); }}
window.addEventListener('load', reportHeight); new ResizeObserver(reportHeight).observe(document.body);
</script></body></html>"""
            context = {
                "shown": "The cluster dashboard (node cards, warnings, guest table) is already on the user's screen.",
                "instructions": "Do not repeat this data, and never print it as JSON, code or tags. In one or two plain sentences, point out anything that needs attention from the warnings, then offer to dig deeper.",
                "nodes_online": f"{sum(1 for n in nodes if n.get('status') == 'online')} of {len(nodes)}",
                "guests_running": f"{running} of {len(guests)}",
                "warnings": warnings or ["none"],
            }
            return HTMLResponse(content=page, headers={"Content-Disposition": "inline"}), context

        return await self._run(__event_emitter__, "Building the cluster dashboard", work)
