"""Turn a run's stream-json events into one ordered timeline of main-agent and subagent actions."""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Item:
    index: int
    turn: int
    kind: str
    actor: str
    text: str = ""
    tool: str = ""
    tool_id: str = ""
    input: dict = field(default_factory=dict)
    is_error: bool = False
    raw: dict = field(default_factory=dict)


def _content(message: dict) -> list:
    content = message.get("content", [])
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def _result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content if isinstance(content, str) else ""


def _is_user_text(event: dict) -> bool:
    if event.get("type") != "user" or event.get("parent_tool_use_id") or event.get("isSynthetic"):
        return False
    blocks = _content(event.get("message", {}))
    return any(b.get("type") == "text" for b in blocks) and not any(b.get("type") == "tool_result" for b in blocks)


def load(run_dir: Path) -> list[Item]:
    items: list[Item] = []
    events = []
    for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    replayed = any(_is_user_text(e) for e in events)
    turn = 0 if replayed else 1
    agent_of_tool: dict[str, str] = {}
    for event in events:
        kind = event.get("type")
        parent = event.get("parent_tool_use_id")
        actor = agent_of_tool.get(parent, "subagent") if parent else "main"
        if kind == "user" and not parent:
            blocks = _content(event.get("message", {}))
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            if _is_user_text(event):
                turn += 1
                items.append(Item(len(items), turn, "user_message", "user", text="\n".join(texts), raw=event))
                continue
        if kind == "assistant":
            for block in _content(event.get("message", {})):
                if block.get("type") == "text" and block.get("text", "").strip():
                    items.append(Item(len(items), turn, "assistant_text", actor, text=block["text"], raw=event))
                elif block.get("type") == "tool_use":
                    tool_input = block.get("input") or {}
                    if block.get("name") in ("Agent", "Task"):
                        agent_of_tool[block.get("id", "")] = tool_input.get("subagent_type") or "general-purpose"
                    items.append(Item(len(items), turn, "tool_use", actor, tool=block.get("name", ""),
                                      tool_id=block.get("id", ""), input=tool_input, raw=event))
        elif kind == "user":
            for block in _content(event.get("message", {})):
                if block.get("type") == "tool_result":
                    items.append(Item(len(items), turn, "tool_result", actor, text=_result_text(block),
                                      tool_id=block.get("tool_use_id", ""), is_error=bool(block.get("is_error")),
                                      raw=event))
        elif kind == "system" and str(event.get("subtype", "")).startswith("hook"):
            items.append(Item(len(items), turn, "hook", "harness", text=json.dumps(event, ensure_ascii=False)[:4000],
                              tool=str(event.get("hook_event") or event.get("hook_name") or ""), raw=event))
        elif kind == "result":
            items.append(Item(len(items), turn, "result", "main", text=str(event.get("result", ""))[:2000], raw=event))
            if not replayed:
                turn += 1
    return items


def user_turn_starts(items: list[Item]) -> list[int]:
    return [item.index for item in items if item.kind == "user_message"]


def main_messages(items: list[Item]) -> list[dict]:
    """Group the main agent's visible text per user turn, as the user saw it."""
    messages: dict[int, list[str]] = {}
    for item in items:
        if item.kind == "assistant_text" and item.actor == "main":
            messages.setdefault(item.turn, []).append(item.text)
    return [{"turn": turn, "text": "\n\n".join(parts)} for turn, parts in sorted(messages.items())]


def bash_commands(items: list[Item], actor: str = "main") -> list[Item]:
    return [i for i in items if i.kind == "tool_use" and i.tool == "Bash" and i.actor == actor]


def result_of(items: list[Item], tool_use: Item) -> Item | None:
    return next((i for i in items if i.kind == "tool_result" and i.tool_id == tool_use.tool_id), None)


def dialogue_index(items: list[Item], dialogue: list[dict]) -> dict[int, int]:
    """Map each timeline item to the 1-based dialogue entry of the agent message it belongs to."""
    agent_entries = [k for k, entry in enumerate(dialogue, start=1) if entry["role"] == "assistant"]
    texts = {k: dialogue[k - 1]["text"] for k in agent_entries}
    pointer, mapping, pending = 0, {}, []
    for item in items:
        pending.append(item.index)
        if item.kind == "assistant_text" and item.actor == "main":
            snippet = item.text.strip()[:200]
            for j in range(pointer, len(agent_entries)):
                if snippet and snippet in texts[agent_entries[j]]:
                    pointer = j
                    break
            for index in pending:
                mapping[index] = agent_entries[pointer] if agent_entries else 0
            pending = []
    for index in pending:
        mapping[index] = agent_entries[pointer] if agent_entries else 0
    return mapping
