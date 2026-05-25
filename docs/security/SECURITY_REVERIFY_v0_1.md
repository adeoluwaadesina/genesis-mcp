# Genesis MCP Security Re-Verification (v0.1)

**Date:** 2026-05-25
**Scope:** Re-attack F-01 and F-02 after the v0.1 fixes documented in
`SECURITY_FIXES_v0_1.md`.

## Executive summary

**F-01 and F-02 are closed under the adversarial payloads tested here.**

The patched validator rejects the original `__builtins__` import/eval PoCs and
all tested variants that try to reach `__builtins__`, `eval`, `__import__`, or
reflection helpers through aliases, defaults, class bodies, f-strings, walrus
assignment, unpacking, comprehensions, `vars()`, `locals()`, `globals()`, or
hex-escaped string constants.

One F-17-style object graph probe using `__class__`, `__base__`, and
`__subclasses__()` still passes validation. That is not a bypass of the F-01 /
F-02 patch because it does not use `__builtins__`, `getattr`, `eval`, or
`__import__`, and it is already documented as deferred F-17 work in
`SECURITY_FIXES_v0_1.md`. It remains a residual hardening gap for v0.2.

## Method

Each payload was wrapped in a complete generated-tool module with a valid
`TOOL_SCHEMA` and module-level `handler(arguments: dict) -> dict`, then passed
directly to:

```python
genesis.validator.validate(code, existing_names=set())
```

The results below are the exact `ValidationError` strings returned by the
patched validator.

## Part A results table - original PoCs

| ID | Validator result | Exact `ValidationError` output |
|---|---|---|
| A1 - F-01 original PoC | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Call to reflection builtin 'getattr' is not allowed.`<br>`[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).`<br>`[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).`<br>`[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` |
| A2 - F-02 original PoC | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Call to reflection builtin 'getattr' is not allowed.`<br>`[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).`<br>`[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).`<br>`[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` |

### Part A exact payloads

**A1 - F-01 original PoC**

```python
TOOL_SCHEMA = {
    "name": "sys_info",
    "description": "audit payload",
    "inputSchema": {"type": "object", "properties": {"expr": {"type": "string"}}, "required": []}
}

def handler(arguments: dict) -> dict:
    bi = __builtins__["__import__"] if isinstance(__builtins__, dict) else getattr(__builtins__, "__import__")
    sp = bi("subprocess")
    r = sp.run(["cmd", "/c", "echo", "GENESIS_RCE"], capture_output=True, text=True)
    return {"status": "success", "data": r.stdout.strip(), "message": "ok"}
```

**A2 - F-02 original PoC**

```python
TOOL_SCHEMA = {
    "name": "calc",
    "description": "audit payload",
    "inputSchema": {"type": "object", "properties": {"expr": {"type": "string"}}, "required": []}
}

def handler(arguments: dict) -> dict:
    fn = __builtins__["eval"] if isinstance(__builtins__, dict) else getattr(__builtins__, "eval")
    return {"status": "success", "data": fn(arguments["expr"]), "message": "ok"}
```

## Part B results table - adversarial variants

| ID | Validator result | Exact `ValidationError` output | Severity if passed |
|---|---|---|---|
| B3 - `vars()` builtins import | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Call to reflection builtin 'vars' is not allowed.` | Would be RCE if it reached `subprocess`. |
| B4 - `locals()` builtins import | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Call to reflection builtin 'locals' is not allowed.` | Would be RCE if it reached `subprocess`. |
| B5 - `globals()` builtins import | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Call to reflection builtin 'globals' is not allowed.` | Would be RCE if it reached `subprocess`. |
| B6 - alias `__builtins__` first | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` | Would be RCE if it reached `subprocess`. |
| B7 - function default captures `__builtins__` | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` | Would be RCE if it reached `subprocess`. |
| B8 - class attribute captures `__builtins__` | REJECTED by `forbidden_name` | `[forbidden_name] line 9: Reference to '__builtins__' is not allowed (bypass primitive).` | Would be RCE if it reached `subprocess`. |
| B9 - f-string evaluation | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` | Would be RCE if it reached `subprocess`. |
| B10 - walrus operator | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` | Would be RCE if it reached `subprocess`. |
| B11 - star-unpacking builtins | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` | Would expose builtin names and could support follow-on bypasses. |
| B12 - dict comprehension over builtins | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` | Would expose builtin objects and could support RCE via recovered functions. |
| B13 - `type().__class__` / subclasses chain | PASSED | None. | Exact payload is introspection only. It can enumerate process classes and may be a building block for object-graph attacks or DoS, but it is not an F-01/F-02 bypass as tested. This is already-deferred F-17 territory. |
| B14 - hex-obfuscated `eval` name | REJECTED by `forbidden_name` | `[forbidden_name] line 8: Call to reflection builtin 'getattr' is not allowed.`<br>`[forbidden_name] line 8: Reference to '__builtins__' is not allowed (bypass primitive).` | Would be arbitrary Python execution if it reached `eval`. |
| B15 - `warnings.catch_warnings().__class__.__init_subclass__` | REJECTED by `import_allowlist` | `[import_allowlist] line 7: Import 'warnings' is not in the allowlist.` | Direct import path is blocked. A no-import object-graph variant belongs to F-17 hardening, not the F-01/F-02 patch. |

### Part B exact payloads

Each snippet below is the exact handler payload attempted. In the validator run,
each was preceded by the same valid `TOOL_SCHEMA` wrapper.

**B3 - `vars()["__builtins__"]["__import__"]("subprocess")`**

```python
def handler(arguments: dict) -> dict:
    sp = vars()["__builtins__"]["__import__"]("subprocess")
    return {"status": "success", "data": str(sp), "message": "ok"}
```

**B4 - `locals()["__builtins__"]["__import__"]("subprocess")`**

```python
def handler(arguments: dict) -> dict:
    sp = locals()["__builtins__"]["__import__"]("subprocess")
    return {"status": "success", "data": str(sp), "message": "ok"}
```

**B5 - `globals()["__builtins__"]["__import__"]("subprocess")`**

```python
def handler(arguments: dict) -> dict:
    sp = globals()["__builtins__"]["__import__"]("subprocess")
    return {"status": "success", "data": str(sp), "message": "ok"}
```

**B6 - assigning `__builtins__` to a different name first**

```python
def handler(arguments: dict) -> dict:
    bi = __builtins__
    sp = bi["__import__"]("subprocess")
    return {"status": "success", "data": str(sp), "message": "ok"}
```

**B7 - accessing through a function default**

```python
def handler(arguments: dict) -> dict:
    def f(x=__builtins__):
        return x["__import__"]("subprocess")
    sp = f()
    return {"status": "success", "data": str(sp), "message": "ok"}
```

**B8 - accessing through a class attribute**

```python
def handler(arguments: dict) -> dict:
    class C:
        b = __builtins__
    sp = C.b["__import__"]("subprocess")
    return {"status": "success", "data": str(sp), "message": "ok"}
```

**B9 - f-string evaluation**

```python
def handler(arguments: dict) -> dict:
    value = f"{__builtins__['__import__']('subprocess')}"
    return {"status": "success", "data": value, "message": "ok"}
```

**B10 - walrus operator**

```python
def handler(arguments: dict) -> dict:
    sp = (b := __builtins__)["__import__"]("subprocess")
    return {"status": "success", "data": str(sp), "message": "ok"}
```

**B11 - star-unpacking**

```python
def handler(arguments: dict) -> dict:
    names = [*__builtins__]
    return {"status": "success", "data": names[:5], "message": "ok"}
```

**B12 - dictionary comprehension over builtins**

```python
def handler(arguments: dict) -> dict:
    data = {k: v for k, v in __builtins__.items()}
    return {"status": "success", "data": str(len(data)), "message": "ok"}
```

**B13 - `type().__class__` chain**

```python
def handler(arguments: dict) -> dict:
    data = type(())().__class__.__base__.__subclasses__()
    return {"status": "success", "data": str(len(data)), "message": "ok"}
```

**B14 - numeric/hex obfuscation of forbidden name**

```python
def handler(arguments: dict) -> dict:
    fn = getattr(__builtins__, "\x65\x76\x61\x6c")
    return {"status": "success", "data": fn(arguments.get("expr", "1+1")), "message": "ok"}
```

**B15 - `warnings.catch_warnings().__class__.__init_subclass__`**

```python
import warnings

def handler(arguments: dict) -> dict:
    value = warnings.catch_warnings().__class__.__init_subclass__
    return {"status": "success", "data": str(value), "message": "ok"}
```

## New findings

No new F-01/F-02 bypass was found.

Residual previously documented issue:

```python
def handler(arguments: dict) -> dict:
    data = type(())().__class__.__base__.__subclasses__()
    return {"status": "success", "data": str(len(data)), "message": "ok"}
```

This still passes because `_FORBIDDEN_DUNDER_ATTRS` does not include
`__class__`, `__base__`, or `__subclasses__`. This matches the known deferred
F-17 item in `SECURITY_FIXES_v0_1.md`; it is not a newly discovered regression
in the F-01/F-02 fix.

## Final recommendation

**safe-to-ship** for the v0.1 F-01 / F-02 fix scope.

The validator now blocks the tested `__builtins__`, indirect `eval`,
indirect `__import__`, and reflection-helper routes. Public release should
still communicate the documented v0.1 limitations clearly: this is not a
general Python sandbox, and deferred items such as F-17 remain in scope for
v0.2 hardening.
