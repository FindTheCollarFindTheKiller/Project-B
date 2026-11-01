import ipaddress
import json
from urllib.error import URLError
from urllib.request import Request, urlopen


MCP_URL = "https://dataservice.accuweather.com/mcp"
PUBLIC_IP_URL = "https://api.ipify.org"


class LocationDetectionError(Exception):
    pass


def _mcp_post(api_key, payload, session_id=None, protocol_version=None):
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if protocol_version:
        headers["MCP-Protocol-Version"] = protocol_version
    request = Request(MCP_URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urlopen(request, timeout=10) as response:
        response_session_id = response.headers.get("Mcp-Session-Id") or session_id
        content_type = response.headers.get("Content-Type", "")
        content = response.read(1024 * 1024).decode("utf-8")

    if not content.strip():
        return None, response_session_id
    if "text/event-stream" in content_type:
        events = [line[5:].strip() for line in content.splitlines() if line.startswith("data:")]
        if not events:
            raise LocationDetectionError("Invalid MCP response")
        content = events[-1]
    result = json.loads(content)
    if not isinstance(result, dict) or result.get("error"):
        raise LocationDetectionError("MCP request failed")
    if "id" in payload and result.get("id") != payload["id"]:
        raise LocationDetectionError("Unexpected MCP response")
    return result.get("result"), response_session_id


def detect_location(api_key):
    try:
        with urlopen(PUBLIC_IP_URL, timeout=10) as response:
            public_ip = response.read(128).decode("ascii").strip()
        if not ipaddress.ip_address(public_ip).is_global:
            raise LocationDetectionError("Public IP address unavailable")
    except (URLError, OSError, UnicodeError, ValueError) as error:
        raise LocationDetectionError("Public IP address unavailable") from error

    initialized, session_id = _mcp_post(api_key, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "weather-app", "version": "1.0"},
        },
    })
    if not isinstance(initialized, dict) or not isinstance(initialized.get("protocolVersion"), str):
        raise LocationDetectionError("MCP initialization failed")
    protocol_version = initialized["protocolVersion"]
    _mcp_post(api_key, {"jsonrpc": "2.0", "method": "notifications/initialized"},
              session_id, protocol_version)
    result, _ = _mcp_post(api_key, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_location_by_ip",
            "arguments": {"body": {"ipAddress": public_ip}},
        },
    }, session_id, protocol_version)
    if not isinstance(result, dict) or result.get("isError"):
        raise LocationDetectionError("Location lookup failed")
    location = result.get("structuredContent")
    if location is None:
        content = result.get("content", [])
        text = next((item.get("text") for item in content if item.get("type") == "text"), None)
        if not text:
            raise LocationDetectionError("Location lookup returned no data")
        location = json.loads(text)
    if not isinstance(location, dict) or not location.get("Key"):
        raise LocationDetectionError("Location lookup returned no city")
    return location
