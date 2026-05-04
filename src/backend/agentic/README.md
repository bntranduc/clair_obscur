# AI Agent

An AI agent that can execute tasks using tools and manage conversations.

## Features

### Core Functionality

- Interactive and single-run modes
- Streaming text responses
- Multi-turn conversations with tool calling
- Configurable model settings and temperature

### Built-in Tools (déploiement CLAIR OBSCUR)

- `classify_firewall_log`, pipeline S3/SQL (`fetch_normalized_logs_from_s3`, sous-agents, etc.) — voir `tools/registry.py`
- Sous-agent **remédiation IR** : `subagent_remediation_soc` — plan contain/eradicate/recover et vérifications, avec outils de lecture optionnels (`tools/remediation_subagent.py`)
- Classification firewall : règles déterministes BUG / ATTACK / NORMAL (port ESGI `cyber_agentic`)

### Built-in Tools (template générique)

- File operations: read, write, edit files
- Directory operations: list directories, search with glob patterns
- Text search: grep for pattern matching
- Shell execution: run shell commands
- Web access: search and fetch web content
- Memory: store and retrieve information
- Todo: manage task lists

### Context Management

- Automatic context compression when approaching token limits
- Tool output pruning to manage context size
- Token usage tracking

### Safety and Approval

- Multiple approval policies: on-request, auto, never, yolo
- Dangerous command detection and blocking
- Path-based safety checks
- User confirmation prompts for mutating operations

### Session Management

- Save and resume sessions
- Create checkpoints
- Persistent session storage

### MCP Integration

- Connect to Model Context Protocol servers
- Use tools from MCP servers
- Support for stdio and HTTP/SSE transports

### Subagents

- Specialized subagents for specific tasks
- Built-in subagents: codebase investigator, code reviewer
- Configurable subagent definitions with custom tools and limits

### Loop Detection

- Detects repeating actions
- Prevents infinite loops in agent execution

### Hooks System

- Execute scripts before/after agent runs
- Execute scripts before/after tool calls
- Error handling hooks
- Custom commands and scripts

### Configuration

- Configurable working directory
- Tool allowlisting
- Developer and user instructions
- Shell environment policies
- MCP server configuration

### User Interface

- Terminal UI with formatted output
- Command interface: /help, /config, /tools, /mcp, /stats, /save, /resume, /checkpoint, /restore
- Real-time tool call visualization
