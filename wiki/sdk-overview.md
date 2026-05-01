# SDK Overview

The Python SDK (`sdk/rimworld.py`) provides a fully-typed interface to control RimWorld via TCP. All 140+ methods have type annotations with return types from `sdk/rtypes.py` (174 TypedDicts).

## Connection

```python
from rimworld import RimClient, RimError

with RimClient(host="127.0.0.1", port=9900, timeout=30) as r:
    print(r.colonists())
    r.build("Wall", 120, 135, stuff="BlocksGranite")
```

| Method | Description |
|--------|-------------|
| `RimClient(host, port, timeout, log_path)` | Connect to game. Default port 9900. |
| `send(command, **kwargs)` | Send raw TCP command, raise `RimError` on failure |
| `send_batch(commands)` | Send multiple commands, fail on first error |
| `send_batch_lenient(commands)` | Send batch, skip errors, return `(successes, error_count)` |
| `close()` | Close TCP connection |
| `restart_game(save=, timeout=120)` | Kill RimWorld, relaunch, reconnect |

## Caching

Read queries are cached with a 2-second TTL. Write commands auto-invalidate relevant caches. This means:
- Calling `colonists()` twice in 2s returns the same data (no TCP round-trip)
- After `set_priority()`, the work priorities cache is cleared
- After `build()`, the buildings cache is cleared

## Error Handling

All commands raise `RimError` on failure. The overseer catches and prints these:
```python
try:
    r.build("Wall", x, z, stuff="BlocksGranite")
except RimError as e:
    print(f"FAILED: {e}")
```

`send_batch_lenient` skips errors and returns the count — useful for bulk operations where some failures are expected (e.g., floor placement on occupied cells).

## Command Logging

Every SDK call can be logged to JSONL for post-run analysis:

```python
# Via env var (set by runner.sh):
export RIM_SDK_LOG="/path/to/command_log.jsonl"

# Via constructor:
with RimClient(log_path="/path/to/log.jsonl") as r:
    r.colonists()  # logged
```

Each line: `{"ts": epoch, "id": msg_id, "cmd": "command", "args": {...}, "ok": true/false, "ms": response_time}`

## Key Gotchas

- `build(blueprint, x, z)` — use positional args or `z=` keyword, NOT `y=`
- `colonists()` returns `{'colonists': [...]}` not a flat list
- `buildings()` returns `{'buildings': [...], 'rooms': [...]}` not a flat list
- `scan()` auto-pages regions > 50x50 (server-side cap)
- Protocol param names differ from SDK (e.g., `thingDef` vs `thing_def` — SDK handles conversion)
