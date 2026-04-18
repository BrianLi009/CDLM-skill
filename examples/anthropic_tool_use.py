"""
Wire the CDLM handlers into the Anthropic Claude API as tools.

Prereqs::

    pip install anthropic cdlm-skill
    export ANTHROPIC_API_KEY=sk-ant-...

Usage::

    python examples/anthropic_tool_use.py "Solve this 4x4 sudoku: ..."

The loop:
  1. Load SKILL.md as the system prompt (tells Claude how CDLM works).
  2. Expose the seven cdlm_* handlers as tools.
  3. Repeatedly call the model, execute any tool_use blocks via HANDLERS,
     and feed results back until the model stops requesting tools.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from cdlm.session import HANDLERS
from cdlm.schemas import ALL_SCHEMAS


MODEL = "claude-opus-4-7"
SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"


def build_tools():
    return [
        {
            "name": s["name"],
            "description": s["description"],
            "input_schema": s["parameters"],
        }
        for s in ALL_SCHEMAS
    ]


def run(problem: str, max_turns: int = 40) -> None:
    system = SKILL_MD.read_text()
    tools = build_tools()
    client = anthropic.Anthropic()

    messages = [{"role": "user", "content": problem}]

    for turn in range(max_turns):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        for block in resp.content:
            if block.type == "text" and block.text.strip():
                print(block.text)

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            # Model produced text only — it's done (or stuck).
            return

        results = []
        for tu in tool_uses:
            handler = HANDLERS.get(tu.name)
            if handler is None:
                content = f'{{"error": "unknown tool: {tu.name}"}}'
            else:
                try:
                    content = handler(**tu.input)
                except Exception as exc:
                    content = f'{{"error": "{type(exc).__name__}: {exc}"}}'
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": content,
            })
        messages.append({"role": "user", "content": results})

    print(f"\n[ran out of turns after {max_turns}]")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY to run this example.")

    problem = " ".join(sys.argv[1:]).strip() or (
        "Solve this 4x4 sudoku (each row, column, and 2x2 box contains 1-4 "
        "exactly once):\n"
        "[1, _, _, 4]\n"
        "[_, 3, _, _]\n"
        "[_, _, 2, _]\n"
        "[4, _, _, 1]"
    )
    run(problem)
