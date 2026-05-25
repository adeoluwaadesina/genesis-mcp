from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional

import jsonschema

from genesis.config import get_config

_JSON_SCHEMA_META = {
    "type": "object",
    "required": ["name", "description", "inputSchema"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "inputSchema": {
            "type": "object",
            "required": ["type", "properties"],
            "properties": {
                "type": {"type": "string"},
                "properties": {"type": "object"},
            },
        },
    },
}

_FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "__import__",
}

_FORBIDDEN_ATTR_CALLS = {
    ("os", "system"), ("os", "popen"), ("os", "execv"), ("os", "execve"),
    ("os", "execvp"), ("os", "execvpe"), ("os", "spawnl"), ("os", "spawnle"),
    ("os", "spawnlp"), ("os", "spawnlpe"), ("os", "spawnv"), ("os", "spawnve"),
    ("os", "spawnvp"), ("os", "spawnvpe"), ("subprocess", "run"),
    ("subprocess", "call"), ("subprocess", "check_call"),
    ("subprocess", "check_output"), ("subprocess", "Popen"),
}

# F-01 / F-02 hardening: reflection primitives that allow indirect access
# to forbidden builtins (e.g. __builtins__["__import__"] or
# getattr(__builtins__, "eval")). A legitimate generated tool never needs
# any of these.
_FORBIDDEN_NAMES = {"__builtins__"}
_FORBIDDEN_DUNDER_ATTRS = {
    "__import__", "__builtins__", "__globals__",
    "__loader__", "__getattribute__",
}
_FORBIDDEN_REFLECTION_CALLS = {"getattr", "globals", "locals", "vars"}


@dataclass
class ValidationError:
    check: str
    reason: str
    line: Optional[int] = None

    def to_dict(self) -> dict:
        return {"check": self.check, "reason": self.reason, "line": self.line}


def validate(code: str, existing_names: set[str]) -> list[ValidationError]:
    """Run all validation checks on generated tool code. Return list of errors (empty = valid)."""
    errors: list[ValidationError] = []

    # 1 — Syntax
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [ValidationError("syntax", str(e), e.lineno)]

    # 2 — Import allowlist
    errors.extend(_check_imports(tree))
    if errors:
        return errors

    # 3 — Forbidden calls
    errors.extend(_check_forbidden_calls(tree))
    if errors:
        return errors

    # 4 — Forbidden names / reflection primitives (F-01, F-02 hardening)
    errors.extend(_check_forbidden_names(tree))
    if errors:
        return errors

    # 5 — Required structure
    errors.extend(_check_required_structure(tree))
    if errors:
        return errors

    # 6 — Schema validity (needs TOOL_SCHEMA extractable from AST)
    schema_errors, schema_value = _check_schema_validity(tree)
    errors.extend(schema_errors)
    if errors:
        return errors

    # 7 — Name uniqueness
    if schema_value is not None:
        errors.extend(_check_name_uniqueness(schema_value, existing_names))
        if errors:
            return errors

    # 8 — No top-level side effects
    errors.extend(_check_no_side_effects(tree))

    return errors


def _check_imports(tree: ast.Module) -> list[ValidationError]:
    allowlist = set(get_config().validator.import_allowlist)
    errors = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                # allow os only when importing os.path sub-module
                if alias.name in allowlist or alias.name.split(".")[0] + "." + ".".join(alias.name.split(".")[1:]) in allowlist:
                    continue
                if alias.name not in allowlist:
                    # special-case: os.path is allowed but os alone is not
                    if top == "os" and alias.name != "os":
                        continue
                    errors.append(ValidationError(
                        "import_allowlist",
                        f"Import '{alias.name}' is not in the allowlist.",
                        getattr(node, "lineno", None),
                    ))

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            if module in allowlist:
                continue
            # allow 'from os.path import ...' and 'from os import path'
            if module == "os.path" or (module == "os" and all(a.name == "path" for a in node.names)):
                continue
            if top not in allowlist and module not in allowlist:
                errors.append(ValidationError(
                    "import_allowlist",
                    f"Import 'from {module} import ...' is not in the allowlist.",
                    getattr(node, "lineno", None),
                ))

    return errors


def _check_forbidden_calls(tree: ast.Module) -> list[ValidationError]:
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # bare calls: eval(...), exec(...)
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
                errors.append(ValidationError(
                    "forbidden_call",
                    f"Call to forbidden function '{node.func.id}'.",
                    getattr(node, "lineno", None),
                ))
            # attribute calls: os.system(...), subprocess.Popen(...)
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    pair = (node.func.value.id, node.func.attr)
                    if pair in _FORBIDDEN_ATTR_CALLS:
                        errors.append(ValidationError(
                            "forbidden_call",
                            f"Call to forbidden function '{node.func.value.id}.{node.func.attr}'.",
                            getattr(node, "lineno", None),
                        ))
    return errors


def _check_forbidden_names(tree: ast.Module) -> list[ValidationError]:
    """Reject reflection primitives used to bypass forbidden-call checks (F-01, F-02)."""
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            errors.append(ValidationError(
                "forbidden_name",
                f"Reference to '{node.id}' is not allowed (bypass primitive).",
                getattr(node, "lineno", None),
            ))
        elif isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_DUNDER_ATTRS:
            errors.append(ValidationError(
                "forbidden_name",
                f"Attribute access '.{node.attr}' is not allowed (bypass primitive).",
                getattr(node, "lineno", None),
            ))
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Name)
              and node.func.id in _FORBIDDEN_REFLECTION_CALLS):
            errors.append(ValidationError(
                "forbidden_name",
                f"Call to reflection builtin '{node.func.id}' is not allowed.",
                getattr(node, "lineno", None),
            ))
    return errors


def _check_required_structure(tree: ast.Module) -> list[ValidationError]:
    errors = []
    has_schema = False
    has_handler = False

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TOOL_SCHEMA":
                    has_schema = True
        if isinstance(node, ast.FunctionDef) and node.name == "handler":
            has_handler = True

    if not has_schema:
        errors.append(ValidationError("required_structure", "Missing module-level 'TOOL_SCHEMA' assignment."))
    if not has_handler:
        errors.append(ValidationError("required_structure", "Missing module-level 'handler' function."))

    return errors


def _check_schema_validity(tree: ast.Module) -> tuple[list[ValidationError], Optional[dict]]:
    """Extract TOOL_SCHEMA value and validate it. Returns (errors, schema_dict_or_None)."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TOOL_SCHEMA":
                    try:
                        schema_value = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        return [ValidationError(
                            "schema_validity",
                            "TOOL_SCHEMA must be a plain dict literal (no dynamic expressions).",
                            getattr(node, "lineno", None),
                        )], None

                    try:
                        jsonschema.validate(instance=schema_value, schema=_JSON_SCHEMA_META)
                    except jsonschema.ValidationError as e:
                        return [ValidationError(
                            "schema_validity",
                            f"TOOL_SCHEMA is not valid: {e.message}",
                            getattr(node, "lineno", None),
                        )], None

                    return [], schema_value

    return [], None


def _check_name_uniqueness(schema: dict, existing_names: set[str]) -> list[ValidationError]:
    name = schema.get("name", "")
    if name in existing_names:
        suggestion = f"{name}_2"
        i = 2
        while suggestion in existing_names:
            i += 1
            suggestion = f"{name}_{i}"
        return [ValidationError(
            "name_uniqueness",
            f"Tool name '{name}' already exists. Suggested alternative: '{suggestion}'.",
        )]
    return []


def _check_no_side_effects(tree: ast.Module) -> list[ValidationError]:
    errors = []
    allowed_top_level = (
        ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign,
        ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
        ast.Expr,  # docstrings / string literals
    )
    for node in tree.body:
        if not isinstance(node, allowed_top_level):
            errors.append(ValidationError(
                "no_side_effects",
                f"Unexpected top-level statement '{type(node).__name__}' — only imports, assignments, and function definitions are allowed.",
                getattr(node, "lineno", None),
            ))
        # bare Expr that isn't a string constant is a side effect
        elif isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
            errors.append(ValidationError(
                "no_side_effects",
                "Top-level expression that is not a string constant — possible side effect.",
                getattr(node, "lineno", None),
            ))
    return errors
