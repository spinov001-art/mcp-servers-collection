#!/usr/bin/env python3
"""
MCP Server Health Checker — Test if MCP servers are responding correctly.
Supports stdio and SSE transport. No dependencies beyond Python stdlib.
"""

import json
import subprocess
import sys
import time


def check_stdio_server(command: list, timeout: int = 10) -> dict:
    """Test an MCP server running over stdio transport."""
    # Send initialize request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-health-check", "version": "1.0.0"}
        }
    }

    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        message = json.dumps(request)
        header = f"Content-Length: {len(message)}\r\n\r\n"
        proc.stdin.write(header + message)
        proc.stdin.flush()

        # Read response with timeout
        start = time.time()
        output = ""
        while time.time() - start < timeout:
            line = proc.stdout.readline()
            if not line:
                break
            output += line
            if '"result"' in output or '"error"' in output:
                break

        proc.terminate()

        if '"result"' in output:
            return {"status": "healthy", "command": " ".join(command), "response": "initialize OK"}
        elif '"error"' in output:
            return {"status": "error", "command": " ".join(command), "response": output[:200]}
        else:
            return {"status": "timeout", "command": " ".join(command), "response": output[:200]}

    except FileNotFoundError:
        return {"status": "not_found", "command": " ".join(command), "error": "Command not found"}
    except Exception as e:
        return {"status": "error", "command": " ".join(command), "error": str(e)}


def check_sse_server(url: str, timeout: int = 10) -> dict:
    """Test an MCP server running over SSE transport."""
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read(500).decode("utf-8", errors="replace")

        if "event:" in data or "data:" in data:
            return {"status": "healthy", "url": url, "response": "SSE stream active"}
        else:
            return {"status": "unknown", "url": url, "response": data[:200]}

    except Exception as e:
        return {"status": "error", "url": url, "error": str(e)}


# Common MCP servers to check
KNOWN_SERVERS = {
    "filesystem": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    "memory": ["npx", "-y", "@modelcontextprotocol/server-memory"],
    "fetch": ["npx", "-y", "@modelcontextprotocol/server-fetch"],
    "github": ["npx", "-y", "@modelcontextprotocol/server-github"],
    "sqlite": ["npx", "-y", "@modelcontextprotocol/server-sqlite", ":memory:"],
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("MCP Server Health Checker")
        print("=" * 40)
        print("\nUsage:")
        print("  python mcp_health_check.py check <server-name>")
        print("  python mcp_health_check.py check-url <sse-url>")
        print("  python mcp_health_check.py check-cmd <command...>")
        print("  python mcp_health_check.py list")
        print(f"\nKnown servers: {', '.join(KNOWN_SERVERS.keys())}")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        for name, command in KNOWN_SERVERS.items():
            print(f"  {name}: {' '.join(command)}")

    elif cmd == "check" and len(sys.argv) > 2:
        name = sys.argv[2]
        if name in KNOWN_SERVERS:
            print(f"Checking {name}...")
            result = check_stdio_server(KNOWN_SERVERS[name])
            print(json.dumps(result, indent=2))
        else:
            print(f"Unknown server: {name}. Use 'list' to see available servers.")

    elif cmd == "check-url" and len(sys.argv) > 2:
        result = check_sse_server(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "check-cmd":
        result = check_stdio_server(sys.argv[2:])
        print(json.dumps(result, indent=2))
