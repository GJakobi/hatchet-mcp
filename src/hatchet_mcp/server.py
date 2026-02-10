"""
Hatchet MCP Server - Debug and monitor Hatchet jobs from Claude Code.

This server provides read-only tools for:
- Listing workflows and runs
- Getting run status and results
- Searching runs by metadata
- Viewing queue metrics

Requires HATCHET_CLIENT_TOKEN environment variable to be set.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from hatchet_sdk import Hatchet, V1TaskStatus
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("Hatchet Debug Server")


@lru_cache(maxsize=1)
def get_hatchet_client() -> Hatchet:
    """Lazy-load the Hatchet client to avoid initialization errors at import time."""
    return Hatchet(debug=False)


# Map string status names to V1TaskStatus enum
STATUS_MAP = {
    "queued": V1TaskStatus.QUEUED,
    "running": V1TaskStatus.RUNNING,
    "completed": V1TaskStatus.COMPLETED,
    "succeeded": V1TaskStatus.COMPLETED,
    "failed": V1TaskStatus.FAILED,
    "cancelled": V1TaskStatus.CANCELLED,
}


def _serialize_run(run: Any) -> dict:
    """Serialize a workflow run to a JSON-friendly dict."""
    metadata = run.metadata if hasattr(run, "metadata") else {}
    return {
        "id": metadata.id if hasattr(metadata, "id") else str(run),
        "workflow_id": run.workflow_id if hasattr(run, "workflow_id") else None,
        "workflow_name": run.workflow_name if hasattr(run, "workflow_name") else None,
        "status": run.status.value if hasattr(run, "status") else None,
        "created_at": str(run.created_at) if hasattr(run, "created_at") else None,
        "started_at": str(run.started_at) if hasattr(run, "started_at") else None,
        "finished_at": str(run.finished_at) if hasattr(run, "finished_at") else None,
        "additional_metadata": run.additional_metadata if hasattr(run, "additional_metadata") else {},
    }


def _serialize_workflow(workflow: Any) -> dict:
    """Serialize a workflow to a JSON-friendly dict."""
    metadata = workflow.metadata if hasattr(workflow, "metadata") else {}
    return {
        "id": metadata.id if hasattr(metadata, "id") else str(workflow),
        "name": workflow.name if hasattr(workflow, "name") else None,
        "description": workflow.description if hasattr(workflow, "description") else None,
        "version": workflow.version if hasattr(workflow, "version") else None,
    }


@mcp.tool()
async def list_workflows() -> list[dict]:
    """
    List all registered Hatchet workflows.

    Returns a list of workflows with their IDs, names, and descriptions.
    """
    try:
        hatchet = get_hatchet_client()
        workflows = await hatchet.workflows.aio_list()
        return [_serialize_workflow(w) for w in (workflows.rows or [])]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
async def list_runs(
    workflow_name: str | None = None,
    status: str | None = None,
    since_hours: int = 24,
    limit: int = 50,
) -> list[dict]:
    """
    List workflow runs with optional filters.

    Args:
        workflow_name: Filter by workflow name (e.g., 'qa-workflow', 'embed-workflow')
        status: Filter by status ('queued', 'running', 'completed', 'failed', 'cancelled')
        since_hours: How many hours back to search (default: 24)
        limit: Maximum number of runs to return (default: 50)

    Returns a list of runs with their status, metadata, and timing info.
    """
    try:
        hatchet = get_hatchet_client()
        # Build filter parameters
        params: dict[str, Any] = {
            "since": datetime.now(tz=timezone.utc) - timedelta(hours=since_hours),
            "limit": limit,
        }

        if status and status.lower() in STATUS_MAP:
            params["statuses"] = [STATUS_MAP[status.lower()]]

        if workflow_name:
            # Need to get workflow ID from name
            workflows = await hatchet.workflows.aio_list()
            workflow_ids = [
                w.metadata.id for w in (workflows.rows or [])
                if hasattr(w, "name") and w.name == workflow_name
            ]
            if workflow_ids:
                params["workflow_ids"] = workflow_ids

        runs = await hatchet.runs.aio_list(**params)
        return [_serialize_run(r) for r in (runs.rows or [])]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
async def get_run_status(run_id: str) -> dict:
    """
    Get the current status of a specific workflow run.

    Args:
        run_id: The ID of the workflow run

    Returns the run's current status and details.
    """
    try:
        hatchet = get_hatchet_client()
        status = await hatchet.runs.aio_get(run_id)
        return _serialize_run(status)
    except Exception as e:
        return {"error": str(e), "run_id": run_id}


@mcp.tool()
async def get_run_result(run_id: str) -> dict:
    """
    Get the result/output of a completed workflow run.

    Args:
        run_id: The ID of the workflow run

    Returns the run's output data if completed, or current status if still running.
    """
    try:
        hatchet = get_hatchet_client()
        result = await hatchet.runs.aio_get_result(run_id)
        return {"run_id": run_id, "result": result}
    except Exception as e:
        return {"error": str(e), "run_id": run_id}


@mcp.tool()
async def get_queue_metrics(workflow_name: str | None = None) -> dict:
    """
    Get queue depth and job counts by status.

    Args:
        workflow_name: Optional workflow name to filter metrics

    Returns counts of jobs in each status (queued, running, completed, failed).
    """
    try:
        hatchet = get_hatchet_client()
        # Get runs from the last 24 hours and count by status
        params: dict[str, Any] = {
            "since": datetime.now(tz=timezone.utc) - timedelta(hours=24),
            "limit": 1000,
        }

        if workflow_name:
            workflows = await hatchet.workflows.aio_list()
            workflow_ids = [
                w.metadata.id for w in (workflows.rows or [])
                if hasattr(w, "name") and w.name == workflow_name
            ]
            if workflow_ids:
                params["workflow_ids"] = workflow_ids

        runs = await hatchet.runs.aio_list(**params)

        # Count by status
        counts = {
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "total": 0,
        }

        for run in (runs.rows or []):
            counts["total"] += 1
            if hasattr(run, "status"):
                status_name = run.status.value.lower() if hasattr(run.status, "value") else str(run.status).lower()
                if status_name in counts:
                    counts[status_name] += 1

        return {
            "workflow_name": workflow_name or "all",
            "time_range_hours": 24,
            "counts": counts,
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def search_runs(
    metadata_key: str,
    metadata_value: str,
    status: str | None = None,
    since_hours: int = 24,
    limit: int = 50,
) -> list[dict]:
    """
    Search runs by metadata key-value pairs.

    Common metadata keys:
    - audit_id: The audit being processed
    - audit_type: Type of audit (e.g., 'standard', 'express')
    - patient_id: Patient being processed
    - application_id: Application ID
    - rule_id: Rule being processed

    Args:
        metadata_key: The metadata key to search (e.g., 'audit_id')
        metadata_value: The value to match
        status: Optional status filter
        since_hours: How many hours back to search (default: 24)
        limit: Maximum runs to return (default: 50)

    Returns matching runs with their full metadata.
    """
    try:
        hatchet = get_hatchet_client()
        params: dict[str, Any] = {
            "since": datetime.now(tz=timezone.utc) - timedelta(hours=since_hours),
            "limit": limit,
            "additional_metadata": {metadata_key: metadata_value},
        }

        if status and status.lower() in STATUS_MAP:
            params["statuses"] = [STATUS_MAP[status.lower()]]

        runs = await hatchet.runs.aio_list(**params)
        return [_serialize_run(r) for r in (runs.rows or [])]
    except Exception as e:
        return [{"error": str(e)}]


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
