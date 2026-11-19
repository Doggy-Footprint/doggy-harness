"""The doggy-workflow rules as one text: SKILL.md with each phase fragment put back where its
section stood, so a wording check finds a sentence wherever the skill delivers it."""
import json
from pathlib import Path

AFTER = {
    "# Spec": ["spec-format"],
    "# Memory": [
        "brief-purpose", "voice", "decision-sweep", "rounds-understanding", "rounds-decision", "rounds-approval",
        "quiz-rules", "quiz-completion-questions", "quiz-closing", "quiz-across-sessions", "closing-report",
        "stepped-cut", "stepped-held", "stepped-run", "stepped-end", "stepped-resume", "verification-design",
        "verification-evidence", "verification-fuzz", "verification-mutation-tool", "verification-audit-state",
        "subagent-model",
    ],
}
WORKFLOW = [
    "workflow-1-recover", "workflow-2-draft", "workflow-3-implement", "workflow-4-reconcile",
    "workflow-5-verify", "workflow-6-triage", "workflow-7-correct", "workflow-8-stop", "workflow-9-close",
]


def fragment_names() -> list[str]:
    return [name for names in AFTER.values() for name in names] + WORKFLOW


def phases(skill_md: Path) -> dict:
    return json.loads((Path(skill_md).parent / "phases.json").read_text(encoding="utf-8"))


def entry_name(entry) -> str:
    return entry if isinstance(entry, str) else entry["name"]


def whole(skill_md: Path) -> str:
    skill_md = Path(skill_md)
    text = skill_md.read_text(encoding="utf-8")
    fragments = skill_md.parent / "phases"
    if not fragments.is_dir():
        return text

    def read(name: str) -> str:
        return (fragments / f"{name}.md").read_text(encoding="utf-8").rstrip("\n")

    sections = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if line.startswith("# ") and not fenced or not sections:
            sections.append([])
        sections[-1].append(line)
    template = skill_md.parent / "spec-template.md"
    markers = json.loads((skill_md.parent / "markers.json").read_text(encoding="utf-8"))
    parts = []
    for lines in sections:
        parts.append("\n".join(lines).rstrip("\n"))
        for name in AFTER.get(lines[0], ()):
            parts.append(read(name))
            if name == "spec-format":
                parts.append("````\n" + template.read_text(encoding="utf-8") + "````")
        if lines[0] == "# Telemetry":
            parts.append("```sh\n" + "\n".join(markers["commands"].values()) + "\n```")
            parts.append(" ".join(sentence for _key, sentence in markers["rules"]))
    parts.append("# Workflow\n\n" + "\n".join(read(name) for name in WORKFLOW))
    return "\n\n".join(parts) + "\n"
