import ast
import base64
import pickle
from typing import Any, Union

from letta.constants import REQUEST_HEARTBEAT_DESCRIPTION, REQUEST_HEARTBEAT_PARAM, SEND_MESSAGE_TOOL_NAME
from letta.schemas.agent import AgentState
from letta.schemas.response_format import ResponseFormatType, ResponseFormatUnion
from letta.types import JsonDict, JsonValue


def parse_stdout_best_effort(text: Union[str, bytes]) -> tuple[Any, AgentState | None]:
    """
    Decode and unpickle the result from the function execution if possible.
    Returns (function_return_value, agent_state).
    """
    if not text:
        return None, None
    if isinstance(text, str):
        text = base64.b64decode(text)
    result = pickle.loads(text)
    agent_state = result["agent_state"]
    return result["results"], agent_state


def parse_function_arguments(source_code: str, tool_name: str):
    """Get arguments of a function from its source code"""
    tree = ast.parse(source_code)
    args = []
    for node in ast.walk(tree):
        # Handle both sync and async functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == tool_name:
            for arg in node.args.args:
                args.append(arg.arg)
    return args


def convert_param_to_str_value(param_type: str, raw_value: JsonValue) -> str:
    """
    Convert parameter to Python code representation based on JSON schema type.
    TODO (cliandy): increase sanitization checks here to fail at the right place
    """

    valid_types = {"string", "integer", "boolean", "number", "array", "object"}
    if param_type not in valid_types:
        raise TypeError(f"Unsupported type: {param_type}, raw_value={raw_value}")
    if param_type == "string":
        # Safely handle python string
        return repr(raw_value)
    if param_type == "integer":
        return str(int(raw_value))
    if param_type == "boolean":
        if isinstance(raw_value, bool):
            return str(raw_value)
        if isinstance(raw_value, int) and raw_value in (0, 1):
            return str(bool(raw_value))
        if isinstance(raw_value, str) and raw_value.strip().lower() in ("true", "false"):
            return raw_value.strip().lower().capitalize()
        raise ValueError(f"Invalid boolean value: {raw_value}")
    if param_type == "array":
        pass  # need more testing here
        # if isinstance(raw_value, str):
        #     if raw_value.strip()[0] != "[" or raw_value.strip()[-1] != "]":
        #         raise ValueError(f'Invalid array value: "{raw_value}"')
        #     return raw_value.strip()
    return str(raw_value)


def runtime_override_tool_json_schema(
    tool_list: list[JsonDict],
    response_format: ResponseFormatUnion | None,
    request_heartbeat: bool = True,
) -> list[JsonDict]:
    """Override the tool JSON schemas at runtime if certain conditions are met.

    Cases:
        1. We will inject `send_message` tool calls with `response_format` if provided
        2. Tools will have an additional `request_heartbeat` parameter added.
    """
    local_send_message_tool_name = SEND_MESSAGE_TOOL_NAME

    # Save locals for even cheaper inner-loop access
    response_format_is_non_text = response_format is not None and response_format.type != ResponseFormatType.text

    for tool_json in tool_list:
        tool_name = tool_json["name"]

        # Only access these once per tool for speed.
        parameters = tool_json["parameters"]
        properties = parameters["properties"]

        if tool_name == local_send_message_tool_name and response_format_is_non_text:
            # Avoid repeated nested dict lookups
            msg_type = response_format.type
            if msg_type == ResponseFormatType.json_schema:
                properties["message"] = response_format.json_schema["schema"]
            elif msg_type == ResponseFormatType.json_object:
                properties["message"] = _JSON_OBJECT_MESSAGE_SCHEMA

        # Combine nested ifs for heartbeat
        elif request_heartbeat:
            if tool_name != local_send_message_tool_name:
                properties[REQUEST_HEARTBEAT_PARAM] = _HEARTBEAT_PROPERTY
                required = parameters["required"]
                # Use set for O(1) presence check if large, otherwise list is fine
                if REQUEST_HEARTBEAT_PARAM not in required:
                    required.append(REQUEST_HEARTBEAT_PARAM)

    return tool_list


_JSON_OBJECT_MESSAGE_SCHEMA = {
    "type": "object",
    "description": "Message contents. All unicode (including emojis) are supported.",
    "additionalProperties": True,
    "properties": {},
}

_HEARTBEAT_PROPERTY = {
    "type": "boolean",
    "description": REQUEST_HEARTBEAT_DESCRIPTION,
}
