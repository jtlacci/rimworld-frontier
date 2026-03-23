#!/usr/bin/env python3
"""Formats agent_live.jsonl stream into color-coded terminal output.

Handles both stream-json (JSON events) and stream-text (raw text) formats.
Hot-reloaded by listen.sh when this file changes.
"""
import sys, json, os

# ANSI colors
COLORS = {
    'runner':     '\033[0;32m',  # green
    'overseer':   '\033[0;34m',  # blue
    'monitor':    '\033[0;33m',  # yellow
    'auditor':    '\033[0;31m',  # red
    'trainer':    '\033[0;35m',  # magenta
    'challenger': '\033[0;36m',  # cyan
}
DIM = '\033[2m'
BOLD = '\033[1m'
RESET = '\033[0m'

current_agent = None

# Strip both possible repo paths for cleaner output
FRONTIER_DIR = os.environ.get('FRONTIER_DIR', '')
AGENT_REPO = os.environ.get('AGENT_REPO', '')

def shorten(path):
    if FRONTIER_DIR:
        path = path.replace(FRONTIER_DIR + '/', '')
    if AGENT_REPO:
        path = path.replace(AGENT_REPO + '/', 'agent/')
    return path

def agent_color():
    return COLORS.get(current_agent, DIM)

def print_header(agent):
    global current_agent
    if agent != current_agent:
        if current_agent:
            print()  # blank line between agents
        current_agent = agent
        c = agent_color()
        print(f'{c}{BOLD}● {agent.upper()}{RESET}')

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    # tail -f prefixes lines with '==> filename <==' on file switches — skip those
    if line.startswith('==>') and line.endswith('<=='):
        continue

    # Handle tagged lines from runner log() function: [runner] msg
    if line.startswith('['):
        try:
            tag_end = line.index(']')
            tag = line[1:tag_end].lower()
            msg = line[tag_end+1:].strip()
            if 'runner' in tag or 'frontier' in tag:
                print_header('runner')
                print(f'{agent_color()}  {msg}{RESET}')
            elif 'monitor' in tag:
                print_header('monitor')
                print(f'{agent_color()}  {msg}{RESET}')
            elif 'auditor' in tag:
                print_header('auditor')
                print(f'{agent_color()}  {msg}{RESET}')
            elif 'trainer' in tag:
                print_header('trainer')
                print(f'{agent_color()}  {msg}{RESET}')
            elif 'challenger' in tag:
                print_header('challenger')
                print(f'{agent_color()}  {msg}{RESET}')
            else:
                print(f'{DIM}  {line}{RESET}')
            sys.stdout.flush()
            continue
        except ValueError:
            pass

    # Try to parse as JSON (agent_start markers, legacy stream-json)
    try:
        event = json.loads(line)
        etype = event.get('type', '')

        # Agent start marker from run_*.sh scripts
        if etype == 'agent_start' and '_agent' in event:
            print_header(event['_agent'])
            print(f'{agent_color()}  started{RESET}')
            sys.stdout.flush()
            continue

        # Legacy stream-json: assistant events
        if etype == 'assistant':
            for block in event.get('message', {}).get('content', []):
                if not isinstance(block, dict):
                    continue
                btype = block.get('type', '')
                if btype == 'thinking':
                    text = block.get('thinking', '').strip()
                    if text:
                        c = agent_color()
                        for tl in text.split('\n'):
                            tl = tl.strip()
                            if tl:
                                print(f'{c}{DIM}  💭 {tl}{RESET}')

                elif btype == 'text':
                    text = block['text'].strip()
                    if text:
                        c = agent_color()
                        for tl in text.split('\n')[:5]:
                            tl = tl.strip()
                            if tl:
                                print(f'{c}  {tl[:140]}{RESET}')
                elif btype == 'tool_use':
                    name = block.get('name', '?')
                    inp = block.get('input', {})
                    c = agent_color()
                    if name == 'Read':
                        fp = shorten(inp.get('file_path', ''))
                        extra = f' (L{inp["offset"]})' if 'offset' in inp else ''
                        print(f'{c}{DIM}  [{name}] {fp[:80]}{extra}{RESET}')
                    elif name in ('Edit', 'Write'):
                        fp = shorten(inp.get('file_path', ''))
                        print(f'{c}  >> {name} {fp[:70]}{RESET}')
                    elif name == 'Bash':
                        cmd = inp.get('command', '')[:80]
                        print(f'{c}{DIM}  $ {cmd}{RESET}')
                    else:
                        print(f'{c}{DIM}  [{name}]{RESET}')
            sys.stdout.flush()
            continue

        if etype == 'result':
            cost = event.get('total_cost_usd', 0)
            turns = event.get('num_turns', 0)
            print(f'{BOLD}  ━━━ Done ({turns} turns, ${cost:.4f}) ━━━{RESET}')
            print()
            current_agent = None
            sys.stdout.flush()
            continue

        # Skip other JSON event types (system, user, rate_limit_event)
        if etype in ('system', 'user', 'rate_limit_event'):
            continue

    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    # Plain text line (stream-text output) — show with agent color
    if current_agent:
        c = agent_color()
        print(f'{c}  {line[:160]}{RESET}')
    else:
        print(f'{DIM}  {line[:160]}{RESET}')

    sys.stdout.flush()
