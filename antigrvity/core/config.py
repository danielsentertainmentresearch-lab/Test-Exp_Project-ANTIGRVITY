"""Configuration models and loaders for Project ANTIGRVITY."""

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from antigrvity.core.exceptions import ConfigurationError


@dataclass
class AgentDefinition:
    """Specification for an agent in the multi-agent swarm."""
    id: str
    name: str
    role: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    priority: int = 50
    max_concurrency: int = 4
    is_critical: bool = False
    system_prompt: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmTopologyConfig:
    """Topology and member definitions of the swarm."""
    topology: str = "hierarchical-mesh"
    swarm_id: str = "antigrvity-default"
    version: str = "1.0.0"
    agents: List[AgentDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SwarmTopologyConfig":
        agents = [
            AgentDefinition(
                id=a["id"],
                name=a.get("name", a["id"]),
                role=a.get("role", "worker"),
                description=a.get("description", ""),
                capabilities=a.get("capabilities", []),
                priority=a.get("priority", 50),
                max_concurrency=a.get("max_concurrency", 4),
                is_critical=a.get("is_critical", False),
                system_prompt=a.get("system_prompt", ""),
                extra=a.get("extra", {})
            )
            for a in data.get("agents", [])
        ]
        return cls(
            topology=data.get("topology", "hierarchical-mesh"),
            swarm_id=data.get("swarm_id", "antigrvity-default"),
            version=data.get("version", "1.0.0"),
            agents=agents,
        )


@dataclass
class ColdStartPhaseConfig:
    """Individual phase configuration in the cold start sequence."""
    id: str
    name: str
    required: bool = True
    checks: List[str] = field(default_factory=list)


@dataclass
class ColdStartConfig:
    """Configuration for cold-start bootstrapping."""
    protocol_version: str = "2.0.0"
    environment: str = "production"
    timeouts: Dict[str, float] = field(default_factory=lambda: {
        "system_probe_sec": 5.0,
        "agent_handshake_sec": 8.0,
        "mcp_negotiation_sec": 10.0,
        "consensus_timeout_sec": 6.0,
        "total_bootstrap_budget_sec": 30.0,
    })
    phases: List[ColdStartPhaseConfig] = field(default_factory=list)
    resilience: Dict[str, Any] = field(default_factory=lambda: {
        "max_phase_retries": 2,
        "allow_graceful_degradation": True,
        "quarantine_unhealthy_agents": True,
        "min_critical_agents_ratio": 1.0,
        "min_optional_agents_ratio": 0.5,
    })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColdStartConfig":
        phases = [
            ColdStartPhaseConfig(
                id=p["id"],
                name=p.get("name", p["id"]),
                required=p.get("required", True),
                checks=p.get("checks", []),
            )
            for p in data.get("phases", [])
        ]
        return cls(
            protocol_version=data.get("protocol_version", "2.0.0"),
            environment=data.get("environment", "production"),
            timeouts=data.get("timeouts", {}),
            phases=phases,
            resilience=data.get("resilience", {}),
        )


@dataclass
class MCPServerConfig:
    """Configuration for an individual downstream MCP server."""
    id: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    description: str = ""
    auto_start: bool = True
    health_check_rpc: str = "ping"


@dataclass
class MCPBridgeConfig:
    """Configuration for the MCP Bridge multiplexer."""
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPBridgeConfig":
        servers_raw = data.get("mcpServers") or data.get("mcp_servers", {})
        servers = {}
        for s_id, s_conf in servers_raw.items():
            servers[s_id] = MCPServerConfig(
                id=s_id,
                command=s_conf.get("command"),
                args=s_conf.get("args", []),
                env=s_conf.get("env", {}),
                url=s_conf.get("url") or s_conf.get("serverUrl"),
                description=s_conf.get("description", ""),
                auto_start=s_conf.get("auto_start", s_conf.get("enabled", True)),
                health_check_rpc=s_conf.get("health_check_rpc", "ping"),
            )
        return cls(servers=servers)


def load_config_file(file_path: Path) -> Dict[str, Any]:
    """Helper to safely read and parse a JSON or TOML configuration file."""
    if not file_path.exists():
        raise ConfigurationError(f"Configuration file not found: {file_path}")
    try:
        if file_path.suffix.lower() == ".toml":
            with open(file_path, "rb") as f:
                return tomllib.load(f)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        raise ConfigurationError(f"Failed to parse config file {file_path}: {exc}") from exc


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Legacy alias for load_config_file."""
    return load_config_file(file_path)
