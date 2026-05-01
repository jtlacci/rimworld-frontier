# Overseer Skills

Small, focused Python scripts the overseer calls directly via Bash. Each skill handles one task reliably.

## Rules
- **Max 50 lines** per skill (excluding imports/comments)
- **One task per skill** — "hunt all wildlife", not "set up entire colony"
- **Takes CLI args** — `python3 skills/hunt_all.py $SDK_PATH`
- **Prints result** — structured output the overseer can read
- **Handles errors** — try/except, prints FAILED, never crashes
- **No strategy** — skills execute, they don't decide. The overseer decides WHEN to call them.

## Creating Skills
The overseer or trainer creates skills by extracting working code from successful executor runs. If an executor solved a task, the working code becomes a skill.

## Available Skills
Skills are listed by filename. Run `ls skills/*.py` to see what's available.
