# Wattio

AI agent for power electronics engineers. Like Claude Code, but for SMPS design.

Wattio lives in your project folder and helps with component search, simulation analysis, design review, and documentation from a single terminal.

## Quick start

```bash
# 1. Install (requires Python 3.10+)
cd 01-Wattio
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Set your API key
echo "OPENAI_API_KEY=sk-..." > .env

# 3. Run from your project folder
cd ~/projects/flyback-30w
wattio
```

## What it does

```
⚡ Find an OTS transformer for my flyback

  ⚙ list_files          ← discovers your .asc files
  ⚙ magnetic_suggest    ← calls magnetic-suggest CLI

Found 3 OTS flyback transformers for K1 (Lpri=560uH, N=23:1):

| # | Manufacturer | MPN       | Lpri  | Turns Ratio | Price |
|---|-------------|-----------|-------|-------------|-------|
| 1 | Wurth       | 750345131 | 500uH | 20:1        | $3.45 |
| 2 | Bourns      | SRF0905A  | 560uH | 22:1        | $4.12 |

⚡ Record this as a decision: we go with option 1

  ⚙ diary_note          ← saves to wattio/diary/2026-02-16.md
```

Everything is logged. A `.docx` is auto-exported when you exit.

## Configuration

Three layers (later overrides earlier):

1. **Defaults** — OpenAI gpt-4o, diary on
2. **User config** — `~/.config/wattio/config.toml`
3. **Project config** — `wattio/config.toml` (inside your project)

### LLM provider

OpenAI (default):
```
# .env
OPENAI_API_KEY=sk-...
```

Anthropic:
```
# .env
ANTHROPIC_API_KEY=sk-ant-...
```
```toml
# wattio/config.toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-5-20250929"
```

### Full config reference

```toml
# wattio/config.toml

[llm]
provider = "openai"              # "openai" or "anthropic"
model = "gpt-4o"                 # any model from the provider
temperature = 0.2
fallback_provider = "anthropic"  # optional: try this if primary fails
fallback_model = "claude-sonnet-4-5-20250929"

[diary]
enabled = true
auto_export_docx = false         # /export command always available
```

## Project structure (your project)

When you run `wattio` inside a project, it creates:

```
your-project/
├── wattio/
│   ├── config.toml              # project-level config (optional)
│   ├── diary/
│   │   ├── 2026-02-16.md        # today's session log
│   │   └── 2026-02-16.docx      # auto-exported on exit
│   └── knowledge/
│       └── curated/             # your design notes (see Knowledge)
│           ├── derating-rules.md
│           └── preferred-vendors.md
├── 01 - LTspice/
│   └── flyback/
│       └── circuit.asc
└── ...
```

## Tools

Wattio has 5 built-in tools the LLM can call:

| Tool | What it does |
|------|-------------|
| `list_files` | Browse directories, search by glob (`**/*.asc`) |
| `file_reader` | Read project files (.asc, .txt, .csv, .md, .json, ...) |
| `magnetic_suggest` | Search OTS magnetic components via the magnetic-suggest CLI |
| `knowledge_search` | Search your curated markdown notes |
| `diary_note` | Add decisions, TODOs, recommendations to the session diary |

### Adding a new tool

Create a Python file in `src/wattio/tools/` with one class:

```python
from wattio.tools.base import BaseTool
from wattio.models import ToolResult
from pathlib import Path
from typing import Any

class MyTool(BaseTool):
    name = "my_tool"
    description = "What it does (shown to the LLM)"
    parameters = {
        "type": "object",
        "properties": {
            "arg1": {"type": "string", "description": "..."},
        },
        "required": ["arg1"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        # do work
        return ToolResult(tool_call_id="", content="result text")
```

Restart Wattio. The tool is auto-discovered.

## Session diary

Every conversation is logged to `wattio/diary/YYYY-MM-DD.md`:

```markdown
# Wattio Session Diary — 2026-02-16

## Session 14:32 — flyback-30w

### 14:32 — User
Find an OTS transformer for my flyback

### 14:32 — Wattio
> **Tool call:** `magnetic_suggest`
> ```json
> {"schematic_path": "01 - LTspice/flyback/LT8316_DC.asc"}
> ```

> **Result:**
> ```
> K1 - Flyback Transformer (N=23.0:1, Lpri=560.00 uH)
>   #1  Wurth  750345131  ...
> ```

### 14:33 — Wattio
I found 2 OTS flyback transformers...

### 14:35 — ✅ DECISION
Option 1 (Wurth 750345131) — proposed to manager

---
## Session ended 15:47 (duration: 1h15m)
```

A `.docx` version is auto-exported when the session ends.

You can also export manually:
```
⚡ /export
```

## Curated knowledge

Put markdown files in `wattio/knowledge/curated/` inside your project. Wattio searches them when answering technical questions.

Example — `wattio/knowledge/curated/derating-rules.md`:
```markdown
# Capacitor Derating Rules

- Ceramic (MLCC): derate voltage by 50% minimum
- Electrolytic: derate voltage by 20%, temperature by 10C
- Use X7R or X5R for power paths, never Y5V
```

When you ask "what are our derating rules?", Wattio finds and cites this file instead of using generic LLM knowledge.

## REPL commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/export` | Export today's diary to .docx |
| `/clear` | Clear conversation history |
| `/config` | Show current LLM and diary settings |
| `Ctrl+D` | Exit (auto-exports diary) |

## Dependencies

| Package | Purpose |
|---------|---------|
| prompt-toolkit | Terminal REPL with history |
| rich | Formatted terminal output |
| pydantic | Data models and validation |
| httpx | Async HTTP for LLM APIs (no SDK) |
| python-dotenv | Load .env files |
| python-docx | Diary .docx export |

No LangChain. No OpenAI SDK. No Anthropic SDK. Raw httpx to both providers.

## External tools

| Tool | How Wattio uses it | Install independently |
|------|-------------------|----------------------|
| magnetic-suggest | Subprocess call (`magnetic-suggest <file.asc>`) | `pip install magnetic-suggest` |

Zero coupling. Update external tools independently of Wattio.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (no API keys needed — uses mock LLM)
pytest

# Run tests verbose
pytest -v
```

## Architecture

```
User input (terminal)
    │
    ▼
┌──────────────┐
│   cli.py     │  prompt-toolkit REPL + Rich output
│              │  Slash commands: /help, /export, /clear, /config
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  agent.py    │────▶│  diary/      │  Auto-logs every interaction
│  (Agent Loop)│     │  writer.py   │  to wattio/diary/YYYY-MM-DD.md
└──────┬───────┘     │  export.py   │  Auto-exports .docx on exit
       │             └──────────────┘
       │
       ├──────────────────────┐
       ▼                      ▼
┌──────────────┐     ┌───────────────┐
│  llm/        │     │  tools/       │
│  openai.py   │     │  registry.py  │  Auto-discovers tools
│  anthropic.py│     ├───────────────┤
│  router.py   │     │  list_files   │  Browse project directories
│              │     │  file_reader  │  Read .asc, .txt, .csv, ...
└──────────────┘     │  magnetic_    │  Subprocess: magnetic-suggest
                     │  suggest      │
                     │  knowledge_   │  Search curated .md files
                     │  search       │
                     │  diary_note   │  Record decisions & TODOs
                     └───────────────┘
```

## Source layout

```
src/wattio/
├── __init__.py          # version
├── __main__.py          # python -m wattio
├── cli.py               # REPL + slash commands
├── config.py            # TOML config loading (3 layers)
├── models.py            # Pydantic models (messages, tool calls, config)
├── agent.py             # Core agent loop (~80 lines)
├── llm/
│   ├── base.py          # Abstract LLMClient
│   ├── openai.py        # OpenAI via httpx
│   ├── anthropic.py     # Anthropic via httpx
│   └── router.py        # Provider selection + fallback
├── tools/
│   ├── base.py          # BaseTool ABC (plugin contract)
│   ├── registry.py      # Auto-discovery
│   ├── list_files.py    # Directory listing + glob
│   ├── file_reader.py   # Read project files
│   ├── magnetic_suggest.py  # OTS magnetics subprocess
│   ├── knowledge_search.py  # Curated knowledge search
│   └── diary_note.py    # Explicit diary entries
├── diary/
│   ├── writer.py        # Markdown diary writer
│   └── export.py        # Markdown → docx
├── knowledge/
│   ├── curated.py       # Keyword search over .md files
│   └── policy.py        # Question type classification
└── prompts/
    └── system.md        # System prompt template
```
