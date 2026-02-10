# Hatchet MCP Server

MCP server for debugging and monitoring [Hatchet](https://hatchet.run) jobs from Claude Code or other MCP clients.

## Installation

```bash
git clone https://github.com/GJakobi/hatchet-mcp.git
cd hatchet-mcp
uv sync
```

## Configuration

Add to your `.mcp.json` (Claude Code) or MCP client config:

```json
{
  "mcpServers": {
    "hatchet": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/hatchet-mcp", "python", "-m", "hatchet_mcp.server"],
      "env": {
        "HATCHET_CLIENT_TOKEN": "your-hatchet-token"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_workflows` | List all registered Hatchet workflows |
| `list_runs` | List workflow runs with filters (workflow_name, status, since_hours, limit) |
| `get_run_status` | Get status of a specific run by ID |
| `get_run_result` | Get the output/result of a completed run |
| `get_queue_metrics` | Get job counts by status (queued, running, completed, failed) |
| `search_runs` | Search runs by metadata (e.g., audit_id, patient_id) |

## Example Usage

Once configured in Claude Code:

```
> List all Hatchet workflows
Uses: mcp__hatchet__list_workflows

> Show me runs that failed in the last 24 hours
Uses: mcp__hatchet__list_runs with status="failed"

> Find all runs for audit_id abc123
Uses: mcp__hatchet__search_runs with metadata_key="audit_id", metadata_value="abc123"

> What's the current queue depth?
Uses: mcp__hatchet__get_queue_metrics
```

## Status Values

- `queued` - Waiting to be processed
- `running` - Currently executing
- `completed` - Finished successfully
- `failed` - Finished with error
- `cancelled` - Manually cancelled

## License

MIT
