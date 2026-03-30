#!/usr/bin/env python3
"""Agentic tool-use harness for Qwen via OpenAI-compatible API.

Replaces `claude -p` — calls Qwen, parses tool calls, executes them,
feeds results back in a loop.

Usage:
  python3 agent_harness.py --model qwen-plus --system "prompt" --message "task" \
    --tools Bash,Read,Write --max-turns 20

Outputs stream-json-compatible format so runner extraction code works.

Env vars:
  DASHSCOPE_API_KEY — required
  DASHSCOPE_BASE_URL — defaults to https://dashscope-us.aliyuncs.com/compatible-mode/v1
"""
import argparse, json, os, subprocess, sys, time

# Unbuffered output so tee/tail see lines immediately
sys.stdout.reconfigure(line_buffering=True)

from openai import OpenAI

DEFAULT_BASE_URL = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"

# Tool definitions for Qwen function calling
TOOL_DEFS = {
    "Bash": {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Execute a bash command and return stdout+stderr",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to run"}
                },
                "required": ["command"]
            }
        }
    },
    "Read": {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read a file and return its contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file"}
                },
                "required": ["file_path"]
            }
        }
    },
    "Write": {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write content to a file (creates or overwrites)",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    "Grep": {
        "type": "function",
        "function": {
            "name": "Grep",
            "description": "Search for a pattern in files using grep",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "File or directory to search in"},
                    "flags": {"type": "string", "description": "Additional grep flags (e.g. -n -i -r)"}
                },
                "required": ["pattern", "path"]
            }
        }
    },
    "Glob": {
        "type": "function",
        "function": {
            "name": "Glob",
            "description": "Find files matching a glob pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"},
                    "path": {"type": "string", "description": "Base directory"}
                },
                "required": ["pattern"]
            }
        }
    },
}


def execute_tool(name, args):
    """Execute a tool call and return the result string."""
    try:
        if name == "Bash":
            cmd = args.get("command", "")
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            return output[:10000]  # cap output size

        elif name == "Read":
            path = args.get("file_path", "")
            with open(path) as f:
                content = f.read()
            return content[:10000]

        elif name == "Write":
            path = args.get("file_path", "")
            content = args.get("content", "")
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
            with open(path, "w") as f:
                f.write(content)
            return f"Written {len(content)} bytes to {path}"

        elif name == "Grep":
            pattern = args.get("pattern", "")
            path = args.get("path", ".")
            flags = args.get("flags", "-rn")
            result = subprocess.run(
                ["grep", flags, pattern, path],
                capture_output=True, text=True, timeout=30
            )
            return (result.stdout or "(no matches)")[:10000]

        elif name == "Glob":
            import glob
            pattern = args.get("pattern", "")
            path = args.get("path", ".")
            matches = glob.glob(os.path.join(path, pattern), recursive=True)
            return "\n".join(matches[:100]) or "(no matches)"

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Error: {e}"


def run_agent(model, system_prompt, user_message, allowed_tools, max_turns):
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("ERROR: DASHSCOPE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    base_url = os.environ.get("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL)
    client = OpenAI(api_key=api_key, base_url=base_url)

    # Build tool list
    tools = [TOOL_DEFS[t] for t in allowed_tools.split(",") if t.strip() in TOOL_DEFS]

    # Append thinking instruction to system prompt
    thinking_instruction = "\n\nIMPORTANT: Before EVERY tool call, you MUST write a text response explaining your reasoning — what you observed, what you plan to do, and why. Never make a tool call without text explanation first."
    messages = [
        {"role": "system", "content": system_prompt + thinking_instruction},
        {"role": "user", "content": user_message},
    ]

    total_input_tokens = 0
    total_output_tokens = 0
    turn = 0

    while turn < max_turns:
        turn += 1

        kwargs = {"model": model, "messages": messages, "max_tokens": 4096}
        if tools:
            kwargs["tools"] = tools

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            print(json.dumps({"type": "error", "error": str(e)}))
            break

        # Track tokens
        if resp.usage:
            total_input_tokens += resp.usage.prompt_tokens or 0
            total_output_tokens += resp.usage.completion_tokens or 0

        choice = resp.choices[0]
        msg = choice.message

        # Emit assistant message (stream-json compatible)
        content_blocks = []
        if msg.content:
            content_blocks.append({"type": "text", "text": msg.content})
        if msg.tool_calls:
            for tc in msg.tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments) if tc.function.arguments else {},
                })

        print(json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "content": content_blocks}
        }))

        # If no tool calls, we're done
        if not msg.tool_calls:
            break

        # Add assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        })

        # Execute each tool call and add results
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}

            result = execute_tool(tc.function.name, args)

            # Emit tool result (stream-json compatible)
            print(json.dumps({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result[:3000],
            }))

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # Emit final result
    final_text = ""
    for m in messages:
        if m.get("role") == "assistant" and m.get("content") and isinstance(m["content"], str):
            final_text = m["content"]

    print(json.dumps({
        "type": "result",
        "result": final_text,
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        },
        "num_turns": turn,
        "total_cost_usd": 0,  # TODO: compute from model pricing
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qwen agent harness")
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--system", default="You are a helpful assistant.")
    parser.add_argument("--message", required=True)
    parser.add_argument("--tools", default="Bash,Read,Write")
    parser.add_argument("--max-turns", type=int, default=20)
    args = parser.parse_args()

    run_agent(args.model, args.system, args.message, args.tools, args.max_turns)
