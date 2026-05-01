# Notifications and Dialogs

RimWorld communicates through several notification systems. Agents must monitor and respond to these to avoid stalled games.

## Notification Types

### Letters (bottom right)
Events, quests, raid warnings, deaths. Persistent until dismissed.
- `r.letters()` — read pending letters
- `r.open_letter(index)` — open for details
- `r.dismiss_letter(index)` — dismiss

### Messages (top center)
Ephemeral popups: "food rotted", "construction failed", "taming failed".
- `r.messages()` — read current messages
- Auto-dismiss after a few seconds
- Useful for detecting problems (food spoilage, build failures)

### Alerts (right side)
Persistent warnings: "need warm clothes", "colonist needs tending", "low food".
- `r.alerts()` — read active alerts
- Don't dismiss — they auto-clear when the issue is resolved
- Important alerts to watch: medical needs, starvation, temperature danger

### Dialogs (modal)
Popup windows that **block game time**. Most critical to handle.
- `r.dialogs()` — read open dialogs
- `r.choose_option(index)` — select a dialog option
- `r.close_dialog(dialog_type="...")` — close specific dialog

## Critical Dialogs

### Naming Dialog (game start)
`Dialog_NamePlayerFactionAndSettlement` — appears at game start, blocks all game time.
```python
r.close_dialog("Dialog_NamePlayerFactionAndSettlement",
               factionName="Colony", settlementName="Base")
```

### Research Complete
Non-blocking letter notification when research finishes. Dismiss via letters API.
```python
r.dismiss_letter(0)  # Dismiss the notification
```

### Quest Dialogs
Various quest offers. Can accept or decline.

## Monitoring Pattern

Check notifications regularly in the game loop:
```python
# After each pause, check for blocking dialogs
dialogs = r.dialogs()
if dialogs:
    for d in dialogs:
        r.close_dialog(dialog_type=d.get("type"))

# Check alerts for urgent issues
alerts = r.alerts()
for a in alerts:
    if "medical" in str(a).lower():
        r.unforbid_all()  # Ensure medicine is accessible
```

## ImmediateWindow Warning

Some dialogs are `ImmediateWindow` types that **regenerate** when closed generically. Always use `close_dialog(dialog_type="...")` to target specific dialogs rather than blindly closing all dialogs.
