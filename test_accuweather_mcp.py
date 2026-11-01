import ast
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import accuweather_mcp


class FakeResponse(io.BytesIO):
    def __init__(self, value, headers=None):
        super().__init__(value)
        self.headers = headers or {}


def json_response(value, headers=None):
    return FakeResponse(json.dumps(value).encode("utf-8"), headers)


class LocationDetectionTests(unittest.TestCase):
    def test_detect_location_uses_public_ip_and_mcp_session(self):
        location = {"Key": "123", "LocalizedName": "Test City"}
        responses = [
            FakeResponse(b"8.8.8.8"),
            json_response({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26"}},
                          {"Mcp-Session-Id": "test-session"}),
            FakeResponse(b""),
            json_response({"jsonrpc": "2.0", "id": 2, "result": {
                "content": [{"type": "text", "text": json.dumps(location)}], "isError": False
            }}),
        ]
        with patch.object(accuweather_mcp, "urlopen", side_effect=responses) as open_url:
            self.assertEqual(accuweather_mcp.detect_location("test-key"), location)

        self.assertEqual(open_url.call_count, 4)
        self.assertEqual(open_url.call_args_list[0].args[0], accuweather_mcp.PUBLIC_IP_URL)
        initialize = open_url.call_args_list[1].args[0]
        notification = open_url.call_args_list[2].args[0]
        call = open_url.call_args_list[3].args[0]
        self.assertEqual(initialize.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(notification.get_header("Mcp-session-id"), "test-session")
        self.assertEqual(call.get_header("Mcp-protocol-version"), "2025-03-26")
        payload = json.loads(call.data)
        self.assertEqual(payload["params"]["name"], "search_location_by_ip")
        self.assertEqual(payload["params"]["arguments"]["body"]["ipAddress"], "8.8.8.8")

    def test_invalid_ip_does_not_contact_mcp(self):
        with patch.object(accuweather_mcp, "urlopen", return_value=FakeResponse(b"127.0.0.1")) as open_url:
            with self.assertRaises(accuweather_mcp.LocationDetectionError):
                accuweather_mcp.detect_location("test-key")
        self.assertEqual(open_url.call_count, 1)

    def test_tool_error_does_not_return_a_location(self):
        responses = [
            FakeResponse(b"8.8.8.8"),
            json_response({"id": 1, "result": {"protocolVersion": "2025-03-26"}}),
            FakeResponse(b""),
            json_response({"id": 2, "result": {"isError": True, "content": []}}),
        ]
        with patch.object(accuweather_mcp, "urlopen", side_effect=responses):
            with self.assertRaises(accuweather_mcp.LocationDetectionError):
                accuweather_mcp.detect_location("test-key")

    def test_structured_content_and_sse_response(self):
        location = {"Key": "456", "LocalizedName": "Test City"}
        event = b'data: ' + json.dumps({"id": 2, "result": {"structuredContent": location}}).encode() + b'\n\n'
        responses = [
            FakeResponse(b"8.8.8.8"),
            json_response({"id": 1, "result": {"protocolVersion": "2025-03-26"}}),
            FakeResponse(b""),
            FakeResponse(event, {"Content-Type": "text/event-stream"}),
        ]
        with patch.object(accuweather_mcp, "urlopen", side_effect=responses):
            self.assertEqual(accuweather_mcp.detect_location("test-key"), location)


class GuiLocationTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name("Project_B.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "use_my_location")
        self.root = Mock()
        self.root.after.side_effect = lambda delay, callback: callback()
        self.messagebox = Mock()
        self.namespace = {
            "ensure_api_key": lambda: "test-key",
            "messagebox": self.messagebox,
            "root": self.root,
            "location_button": Mock(),
            "search_button": Mock(),
            "city_entry": Mock(),
            "detect_location": Mock(),
            "get_current_weather": Mock(),
            "show_weather": Mock(),
            "Queue": __import__("queue").Queue,
            "Empty": __import__("queue").Empty,
            "Thread": lambda target, daemon: SimpleNamespace(start=target),
            "HTTPError": __import__("urllib.error", fromlist=["HTTPError"]).HTTPError,
            "DISABLED": "disabled",
            "NORMAL": "normal",
            "END": "end",
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), "Project_B.py", "exec"), self.namespace)

    def test_cancel_does_not_detect_location(self):
        self.messagebox.askyesno.return_value = False
        self.namespace["use_my_location"]()
        self.namespace["detect_location"].assert_not_called()
        self.namespace["get_current_weather"].assert_not_called()

    def test_detected_location_is_used_directly(self):
        location = {"Key": "123", "LocalizedName": "Test City"}
        current = {"WeatherText": "Sunny"}
        self.messagebox.askyesno.return_value = True
        self.namespace["detect_location"].return_value = location
        self.namespace["get_current_weather"].return_value = current
        self.namespace["use_my_location"]()
        self.namespace["get_current_weather"].assert_called_once_with(location, "test-key")
        self.namespace["show_weather"].assert_called_once_with(location, current)
        self.namespace["city_entry"].insert.assert_called_once_with(0, "Test City")
        self.namespace["location_button"].configure.assert_called_with(state="normal", text="Use my location")
        self.namespace["search_button"].configure.assert_called_with(state="normal")

    def test_lookup_failure_restores_buttons(self):
        self.messagebox.askyesno.return_value = True
        self.namespace["detect_location"].side_effect = RuntimeError("sensitive details")
        self.namespace["use_my_location"]()
        self.messagebox.showerror.assert_called_once()
        self.assertNotIn("sensitive details", str(self.messagebox.showerror.call_args))
        self.namespace["location_button"].configure.assert_called_with(state="normal", text="Use my location")
        self.namespace["search_button"].configure.assert_called_with(state="normal")


class WeatherLookupTests(unittest.TestCase):
    def test_weather_uses_the_detected_location_key(self):
        source = Path(__file__).with_name("Project_B.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_current_weather")
        request = Mock(return_value=[{"WeatherText": "Sunny"}])
        namespace = {"accuweather_get": request, "quote": __import__("urllib.parse", fromlist=["quote"]).quote}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "Project_B.py", "exec"), namespace)
        result = namespace["get_current_weather"]({"Key": "123"}, "test-key")
        self.assertEqual(result, {"WeatherText": "Sunny"})
        request.assert_called_once_with("/currentconditions/v1/123", {"apikey": "test-key", "details": "true"})


if __name__ == "__main__":
    unittest.main()
