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

    if param_type not in _VALID_TYPES:
        raise TypeError(f"Unsupported type: {param_type}, raw_value={raw_value}")

    if param_type == "string":
        # Safely handle python string
        return repr(raw_value)
    elif param_type == "integer":
        return str(int(raw_value))
    elif param_type == "boolean":
        # Optimize bool handling to minimize repeated stripping/lowering/conversions
        if type(raw_value) is bool:
            return "True" if raw_value else "False"
        elif type(raw_value) is int and raw_value in (0, 1):
            return "True" if raw_value == 1 else "False"
        elif type(raw_value) is str:
            stripped = raw_value.strip().lower()
            if stripped in _BOOL_STR_TABLE:
                return _BOOL_STR_TABLE[stripped]
        raise ValueError(f"Invalid boolean value: {raw_value}")
    # No change to array/object/number handling; falls through to str()
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
    for tool_json in tool_list:
        if tool_json["name"] == SEND_MESSAGE_TOOL_NAME and response_format and response_format.type != ResponseFormatType.text:
            if response_format.type == ResponseFormatType.json_schema:
                tool_json["parameters"]["properties"]["message"] = response_format.json_schema["schema"]
            if response_format.type == ResponseFormatType.json_object:
                tool_json["parameters"]["properties"]["message"] = {
                    "type": "object",
                    "description": "Message contents. All unicode (including emojis) are supported.",
                    "additionalProperties": True,
                    "properties": {},
                }
        if request_heartbeat:
            # TODO (cliandy): see support for tool control loop parameters
            if tool_json["name"] != SEND_MESSAGE_TOOL_NAME:
                tool_json["parameters"]["properties"][REQUEST_HEARTBEAT_PARAM] = {
                    "type": "boolean",
                    "description": REQUEST_HEARTBEAT_DESCRIPTION,
                }
                if REQUEST_HEARTBEAT_PARAM not in tool_json["parameters"]["required"]:
                    tool_json["parameters"]["required"].append(REQUEST_HEARTBEAT_PARAM)

    return tool_list


_VALID_TYPES = {"string", "integer", "boolean", "number", "array", "object"}

_BOOL_STR_TABLE = {"true": "True", "false": "False"}
