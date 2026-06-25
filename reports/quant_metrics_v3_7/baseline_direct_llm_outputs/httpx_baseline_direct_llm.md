## Architecture Summary

httpx is a mature, well-structured Python HTTP client library (v0.28.1) providing both synchronous and asynchronous APIs. The architecture follows a layered design:

- **Public API Layer** (`_api.py`): Top-level convenience functions (`get`, `post`, `request`, `stream`) that create ephemeral `Client` instances.
- **Client Layer** (`_client.py`): `Client` (sync) and `AsyncClient` share a `BaseClient` base class containing URL merging, header merging, redirect handling, and auth flow orchestration. Both use `ClientState` enum for lifecycle management.
- **Transport Layer** (`_transports/`): Abstract `BaseTransport`/`AsyncBaseTransport` base classes with concrete implementations — `HTTPTransport`/`AsyncHTTPTransport` (wrapping `httpcore`), `ASGITransport`, `WSGITransport`, and `MockTransport`.
- **Models Layer** (`_models.py`): `Request`, `Response`, `Headers`, and `Cookies` — the core data objects. `Response` handles content decoding, streaming, iteration, and encoding detection.
- **URL Layer** (`_urls.py`, `_urlparse.py`): Custom RFC 3986-compliant URL parser with IDNA support, percent-encoding, and immutable `URL`/`QueryParams` types.
- **Configuration** (`_config.py`): `Timeout`, `Limits`, `Proxy`, and SSL context creation.
- **Auth** (`_auth.py`): Generator-based auth flow pattern supporting `BasicAuth`, `DigestAuth`, `FunctionAuth`, and `NetRCAuth`.
- **Content Encoding** (`_content.py`, `_decoders.py`, `_multipart.py`): Request encoding (URL-encoded, multipart, JSON) and response decoding (gzip, deflate, brotli, zstd).
- **CLI** (`_main.py`): Click-based HTTP CLI with Rich output formatting, conditionally imported.
- **Exception Hierarchy** (`_exceptions.py`): Granular exception tree rooted at `HTTPError`, with transport, timeout, network, and stream error categories.

The design cleanly separates sync/async concerns while maximizing shared logic in `BaseClient`. The transport abstraction enables testing via `MockTransport` and alternative server frameworks (ASGI/WSGI).

## Code Smells

### 1. Massive Code Duplication Between `Client` and `AsyncClient`

**File:** `httpx/_client.py`

The `Client` and `AsyncClient` classes are nearly identical — over 800 lines each with identical method signatures, identical HTTP-method convenience wrappers (`get`, `post`, `put`, `patch`, `delete`, `options`, `head`), and identical redirect/auth flow logic. The only differences are `async`/`await` keywords and sync vs async stream types.

```python
# Lines ~530-800 (Client) mirror lines ~1400-1700 (AsyncClient) almost exactly
def get(self, url, *, params=..., headers=..., cookies=..., auth=..., ...):
    return self.request("GET", url, ...)

async def get(self, url, *, params=..., headers=..., cookies=..., auth=..., ...):
    return await self.request("GET", url, ...)
```

This applies to all 7 HTTP method wrappers in both classes, plus `send`, `_send_handling_auth`, `_send_handling_redirects`, `_send_single_request`, `stream`, `_init_transport`, `_init_proxy_transport`, `_transport_for_url`, `__enter__`/`__aenter__`, `__exit__`/`__aexit__`, and `close`/`aclose`.

### 2. Repetitive Module-Level HTTP Method Functions

**File:** `httpx/_api.py`

The functions `get`, `post`, `put`, `patch`, `delete`, `options`, `head` all duplicate the same parameter list and simply delegate to `request()` with a different method string. Each is ~20 lines of nearly identical code.

```python
def get(url, *, params=..., headers=..., cookies=..., auth=..., proxy=..., ...):
    return request("GET", url, params=params, headers=headers, ...)

def options(url, *, params=..., headers=..., cookies=..., auth=..., proxy=..., ...):
    return request("OPTIONS", url, params=params, headers=headers, ...)
```

### 3. Duplicated `_build_auth_header` in Auth Classes

**File:** `httpx/_auth.py`

`BasicAuth._build_auth_header` and `NetRCAuth._build_auth_header` contain identical implementations:

```python
# BasicAuth (line ~118)
def _build_auth_header(self, username, password):
    userpass = b":".join((to_bytes(username), to_bytes(password)))
    token = b64encode(userpass).decode()
    return f"Basic {token}"

# NetRCAuth (line ~144)
def _build_auth_header(self, username, password):
    userpass = b":".join((to_bytes(username), to_bytes(password)))
    token = b64encode(userpass).decode()
    return f"Basic {token}"
```

### 4. Mutable Class Attribute Manipulation at Import Time

**File:** `httpx/__init__.py`

The loop at the bottom of `__init__.py` mutates `__module__` on every exported object at import time, which is a code smell — it rewrites introspection metadata and uses a fragile `locals()` dance:

```python
__locals = locals()
for __name in __all__:
    if not __name.startswith("__"):
        setattr(__locals[__name], "__module__", "httpx")
```

### 5. `Timeout` Constructor Complexity

**File:** `httpx/_config.py`, `Timeout.__init__`

The `Timeout.__init__` has complex branching with `UnsetType` sentinels, tuple unpacking, and multiple assertions. The logic for combining a default timeout with individual overrides is non-obvious:

```python
def __init__(self, timeout=UNSET, *, connect=UNSET, read=UNSET, write=UNSET, pool=UNSET):
    if isinstance(timeout, Timeout):
        assert connect is UNSET
        ...
    elif isinstance(timeout, tuple):
        ...
    elif not (isinstance(connect, UnsetType) or ...):
        ...
    else:
        ...
```

### 6. Deprecated `data=` Parameter Support

**File:** `httpx/_content.py`, `encode_request`

The `data` parameter is deprecated for raw bytes but still accepted with a warning, creating a confusing dual-purpose `data` argument (also used for form data):

```python
if data is not None and not isinstance(data, Mapping):
    message = "Use 'content=<...>' to upload raw bytes/text content."
    warnings.warn(message, DeprecationWarning, stacklevel=2)
    return encode_content(data)
```

### 7. Global Mutable State in Exception Mapping

**File:** `httpx/_transports/default.py`

`HTTPCORE_EXC_MAP` is a module-level mutable dictionary populated lazily via `_load_httpcore_exceptions()`, with the loading check in `map_httpcore_exceptions()` not being thread-safe:

```python
HTTPCORE_EXC_MAP: dict[type[Exception], type[httpx.HTTPError]] = {}

def map_httpcore_exceptions():
    global HTTPCORE_EXC_MAP
    if len(HTTPCORE_EXC_MAP) == 0:
        HTTPCORE_EXC_MAP = _load_httpcore_exceptions()
    ...
```

## Maintainability Issues

### 1. `_client.py` at ~1700 Lines Is a Monolith

**File:** `httpx/_client.py`

This single file contains `BaseClient`, `Client`, `AsyncClient`, `BoundSyncStream`, `BoundAsyncStream`, `UseClientDefault`, `ClientState`, and multiple helper functions. At ~1700 lines, it is the largest file in the codebase and carries the highest cognitive load. Any change to redirect handling, auth flow, or request building risks merge conflicts and requires understanding the entire file.

### 2. `_models.py` at ~1100 Lines Combines Unrelated Concerns

**File:** `httpx/_models.py`

`Headers`, `Request`, `Response`, and `Cookies` are all defined in one file. `Response` alone is ~600 lines with sync/async streaming methods, encoding detection, content decoding, JSON parsing, cookie extraction, link header parsing, and raise_for_status. This makes the module difficult to navigate and test in isolation.

### 3. Test Files Mirror Source Structure Inconsistently

**Files:** `tests/client/`, `tests/models/`, `tests/`

Tests are split across `tests/` (top-level), `tests/client/`, and `tests/models/`, but the mapping is inconsistent. For example, `tests/test_auth.py` contains unit tests while `tests/client/test_auth.py` contains integration tests — but the filenames are identical. This creates confusion about which test file to edit or run.

### 4. Optional Dependency Handling Scattered Across Modules

**Files:** `httpx/_decoders.py`, `httpx/_transports/default.py`, `httpx/_client.py`, `httpx/__init__.py`

Optional dependencies (`brotli`, `brotlicffi`, `zstandard`, `h2`, `socksio`, `click`, `rich`, `pygments`) are handled with local try/except imports in multiple places. The patterns are inconsistent — some use `# pragma: no cover`, some raise `ImportError` with install instructions, some silently set to `None`.

### 5. `_main.py` Depends on Heavyweight Optional Dependencies

**File:** `httpx/_main.py`

The CLI module imports `click`, `rich.console`, `rich.progress`, `rich.syntax`, `rich.markup`, `rich.table`, and `pygments` at module level. Since `_main.py` is imported in `__init__.py` (inside a try/except), any import failure silently degrades the module's functionality, and the fallback `main()` function uses bare `sys.exit(1)`.

### 6. Pickle Support via `__getstate__`/`__setstate__` Is Fragile

**Files:** `httpx/_models.py` (`Request`, `Response`)

Both `Request` and `Response` implement custom pickle serialization that excludes `extensions` and `stream` attributes. This creates a maintenance burden — if new attributes are added, they must be manually included/excluded. The `UnattachedStream` sentinel replaces the stream, making unpickled objects unusable for I/O.

### 7. `DigestAuth` Retains State Across Requests

**File:** `httpx/_auth.py`

`DigestAuth` stores `_last_challenge` and `_nonce_count` as instance state. If a single `DigestAuth` instance is reused across different hosts or if state corruption occurs, authentication will silently use wrong credentials. There is no mechanism to scope the state to a particular request target.

## Refactoring Suggestions

### 1. Extract Shared Client Logic Using a Mixin or Template Method Pattern

**Files:** `httpx/_client.py`

Extract the HTTP method convenience wrappers into a mixin class or use code generation. The 7 method wrappers (`get`, `post`, `put`, `patch`, `delete`, `options`, `head`) in both `Client` and `AsyncClient` are identical except for `await`. Consider a single definition that both classes inherit, or a factory that generates these methods:

```python
# Potential approach: generate method wrappers
def _make_http_method(method: str):
    def wrapper(self, url, **kwargs):
        return self.request(method, url, **kwargs)
    wrapper.__name__ = method.lower()
    return wrapper

for _method in ("GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"):
    setattr(Client, _method.lower(), _make_http_method(_method))
```

Alternatively, consider a `syncify` decorator that automatically generates sync wrappers from async implementations.

### 2. Consolidate `_build_auth_header` into `BasicAuth` Base or Utility

**File:** `httpx/_auth.py`

Move `_build_auth_header` into a shared base class or module-level function, since `NetRCAuth` simply produces a `Basic` auth header:

```python
def _build_basic_auth_header(username: str | bytes, password: str | bytes) -> str:
    userpass = b":".join((to_bytes(username), to_bytes(password)))
    token = b64encode(userpass).decode()
    return f"Basic {token}"
```

### 3. Split `_models.py` into Separate Modules

**File:** `httpx/_models.py`

Break `_models.py` into `httpx/_headers.py`, `httpx/_request.py`, `httpx/_response.py`, and `httpx/_cookies.py`. Each class has enough complexity to warrant its own file. Re-export from `_models.py` for backward compatibility:

```python
# httpx/_models.py (backward compat shim)
from ._headers import Headers
from ._request import Request
from ._response import Response
from ._cookies import Cookies
```

### 4. Make `Timeout` Constructor Simpler

**File:** `httpx/_config.py`

Replace the `UnsetType` sentinel pattern with a cleaner design. For example, use `None` for "no timeout" and a float/`Timeout` instance for explicit timeout, with the "use client default" logic handled in the client, not the `Timeout` class itself:

```python
class Timeout:
    def __init__(self, timeout=None, *, connect=_MISSING, read=_MISSING, write=_MISSING, pool=_MISSING):
        ...
```

Or use `dataclasses` with `field(default_factory=...)` to simplify the initialization logic.

### 5. Extract Redirect Handling into a Separate Mixin or Class

**Files:** `httpx/_client.py`

The redirect-related methods (`_redirect_method`, `_redirect_url`, `_redirect_headers`, `_redirect_stream`, `_build_redirect_request`) and the redirect-following loop (`_send_handling_redirects`) could be extracted into a `RedirectHandler` mixin or standalone class, reducing the size of `_client.py` and improving testability:

```python
class RedirectHandler:
    def build_redirect_request(self, request, response): ...
    def _redirect_method(self, request, response): ...
    def _redirect_url(self, request, response): ...
    def _redirect_headers(self, request, url, method): ...
    def _redirect_stream(self, request, method): ...
```

### 6. Consolidate Optional Dependency Handling

**Files:** `httpx/_decoders.py`, `httpx/_transports/default.py`, `httpx/_client.py`

Create a central `httpx/_compat.py` or `httpx/_optional.py` module that handles all optional dependency imports consistently:

```python
# httpx/_optional.py
def require_brotli():
    try:
        import brotli
        return brotli
    except ImportError:
        try:
            import brotlicffi as brotli
            return brotli
        except ImportError:
            raise ImportError("Install httpx[brotli] for Brotli support")
```

### 7. Remove the Module-Level `__init__.py` `__module__` Rewriting

**File:** `httpx/__init__.py`

The `setattr(__locals[__name], "__module__", "httpx")` loop at the bottom of `__init__.py` is fragile and non-standard. Consider using `__all__` exports and explicit re-exports in `__init__.py` instead, or simply accept the default module paths. If the goal is clean `help()` output, document the public API in docstrings or use `__dir__` overrides.