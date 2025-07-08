import ast
import builtins
import json
import typing
from typing import Dict, Optional, Tuple

from letta.errors import LettaToolCreateError
from letta.types import JsonDict


def resolve_type(annotation: str):
    """
    Resolve a type annotation string into a Python type.
    Previously, primitive support for int, float, str, dict, list, set, tuple, bool.

    Args:
        annotation (str): The annotation string (e.g., 'int', 'list[int]', 'dict[str, int]').

    Returns:
        type: The corresponding Python type.

    Raises:
        ValueError: If the annotation is unsupported or invalid.
    """
    # Use cache to avoid recomputation
    if annotation in _RESOLVE_TYPE_CACHE:
        return _RESOLVE_TYPE_CACHE[annotation]

    if annotation in _PYTHON_TYPES:
        typ = _PYTHON_TYPES[annotation]
        _RESOLVE_TYPE_CACHE[annotation] = typ
        return typ

    try:
        typ = eval(annotation, _PYTHON_TYPES)
        _RESOLVE_TYPE_CACHE[annotation] = typ
        return typ
    except Exception:
        raise ValueError(f"Unsupported annotation: {annotation}")


# TODO :: THIS MUST BE EDITED TO HANDLE THINGS
def get_function_annotations_from_source(source_code: str, function_name: str) -> Dict[str, str]:
    """
    Parse the source code to extract annotations for a given function name.

    Args:
        source_code (str): The Python source code containing the function.
        function_name (str): The name of the function to extract annotations for.

    Returns:
        Dict[str, str]: A dictionary of argument names to their annotation strings.

    Raises:
        ValueError: If the function is not found in the source code.
    """
    tree = ast.parse(source_code)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            annotations = {}
            for arg in node.args.args:
                if arg.annotation is not None:
                    annotation_str = ast.unparse(arg.annotation)
                    annotations[arg.arg] = annotation_str
            return annotations
    raise ValueError(f"Function '{function_name}' not found in the provided source code.")


# NOW json_loads -> ast.literal_eval -> typing.get_origin
def coerce_dict_args_by_annotations(function_args: JsonDict, annotations: Dict[str, str]) -> dict:
    # Avoid duplicating dict for every call if not needed; if function_args isn't going to be
    # mutated (pythonic way), shallow copy is fine and is already fastest.
    coerced_args = function_args.copy()
    # Pre-resolve types and origins for this function signature if there are many args
    _type_and_origin_cache = {}

    for arg_name, value in coerced_args.items():
        if arg_name in annotations:
            annotation_str = annotations[arg_name]
            # Use per-function-call cache to avoid repeated resolve_type and get_origin on same annotation
            try:
                cache_key = annotation_str
                type_and_origin = _type_and_origin_cache.get(cache_key)
                if not type_and_origin:
                    arg_type = resolve_type(annotation_str)
                    origin = _GET_ORIGIN(arg_type)
                    type_and_origin = (arg_type, origin)
                    _type_and_origin_cache[cache_key] = type_and_origin
                else:
                    arg_type, origin = type_and_origin

                # Be as fast as possible on string parsing:
                if isinstance(value, str):
                    # Try fast-path: Only call each parsing function once, avoid try/except unless truly necessary
                    loaded = False
                    try:
                        value = json.loads(value)
                        loaded = True
                    except json.JSONDecodeError:
                        pass
                    if not loaded:
                        try:
                            value = ast.literal_eval(value)
                        except (SyntaxError, ValueError) as e:
                            if arg_type is not str:
                                raise ValueError(f"Failed to coerce argument '{arg_name}' to {annotation_str}: {e}")

                # Handle origin fast
                if origin in (list, dict, tuple, set):
                    coerced_args[arg_name] = origin(value)
                else:
                    coerced_args[arg_name] = arg_type(value)

            except Exception as e:
                raise ValueError(f"Failed to coerce argument '{arg_name}' to {annotation_str}: {e}")

    return coerced_args


def get_function_name_and_docstring(source_code: str, name: Optional[str] = None) -> Tuple[str, str]:
    """Gets the name and docstring for a given function source code by parsing the AST.

    Args:
        source_code: The source code to parse
        name: Optional override for the function name

    Returns:
        Tuple of (function_name, docstring)
    """
    try:
        # Parse the source code into an AST
        tree = ast.parse(source_code)

        # Find the last function definition
        function_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_def = node

        if not function_def:
            raise LettaToolCreateError("No function definition found in source code")

        # Get the function name
        function_name = name if name is not None else function_def.name

        # Get the docstring if it exists
        docstring = ast.get_docstring(function_def)

        if not function_name:
            raise LettaToolCreateError("Could not determine function name")

        if not docstring:
            raise LettaToolCreateError("Docstring is missing")

        return function_name, docstring

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise LettaToolCreateError(f"Failed to parse function name and docstring: {str(e)}")


_PYTHON_TYPES = {**vars(typing), **vars(builtins)}

_RESOLVE_TYPE_CACHE = {}

_GET_ORIGIN = typing.get_origin
