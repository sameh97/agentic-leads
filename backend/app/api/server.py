"""
FastAPI Server
==============
Endpoints:
  POST /api/leads/generate   — start a lead generation job
  GET  /api/leads/stream/{job_id} — SSE stream of node-by-node progress
  GET  /api/leads/download/{job_id} — download the CSV/XLSX result
  GET  /api/leads/status/{job_id}  — check job status (JSON)
"""

import os
import uuid
import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncGenerator
from datetime import datetime

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from app.agents.graph import lead_graph, LeadState

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Prompt-to-Leads API",
    description="Natural Language → Verified Sales Leads via LangGraph",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", os.getenv("FRONTEND_URL", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (use Redis in production)
jobs: dict[str, dict] = {}


# ── Request / Response models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    query:       str
    max_results: int = 100
    max_retries: int = 3


class JobResponse(BaseModel):
    job_id:    str
    status:    str
    message:   str
    stream_url: str


# ── Background job runner ─────────────────────────────────────────────────────

async def run_lead_job(job_id: str, query: str, max_results: int, max_retries: int):
    """Runs the LangGraph pipeline and emits progress events."""
    job = jobs[job_id]

    def emit(node: str, data: dict):
        event = {
            "node":      node,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        }
        job["events"].append(event)
        logger.info(f"[job:{job_id}] {node}: {data}")

    try:
        emit("start", {"message": f"Starting pipeline for: {query}"})

        initial_state: LeadState = {
            "messages":          [],
            "raw_query":         query,
            "business_type":     "",
            "location":          "",
            "radius_km":         25.0,
            "enrichment_reqs":   [],
            "raw_businesses":    [],
            "scrape_errors":     [],
            "enriched_leads":    [],
            "enrichment_errors": [],
            "verified_leads":    [],
            "verification_errors": [],
            "scored_leads":      [],
            "final_csv_path":    "",
            "retry_count":       0,
            "max_retries":       max_retries,
            "status":            "running",
            "error_message":     "",
        }

        # Stream node-by-node updates
        loop = asyncio.get_event_loop()
        final_state = None

        # LangGraph streaming: yields (node_name, output_state) tuples
        for chunk in lead_graph.stream(
            initial_state,
            config={"configurable": {"thread_id": job_id}},
        ):
            for node_name, node_state in chunk.items():
                if node_name == "parse_query":
                    emit("parse_query", {
                        "message": "Query parsed",
                        "business_type": node_state.get("business_type"),
                        "location":      node_state.get("location"),
                        "radius_km":     node_state.get("radius_km"),
                    })
                elif node_name == "scrape_maps":
                    count = len(node_state.get("raw_businesses", []))
                    emit("scrape_maps", {
                        "message": f"Scraped {count} businesses from Google Maps",
                        "count": count,
                    })
                elif node_name == "enrich_websites":
                    count = len(node_state.get("enriched_leads", []))
                    emit("enrich_websites", {
                        "message": f"Enriched {count} businesses with email addresses",
                        "count": count,
                    })
                elif node_name == "verify_emails":
                    leads = node_state.get("verified_leads", [])
                    valid = sum(1 for l in leads if l.get("email_valid"))
                    emit("verify_emails", {
                        "message": f"Verified {valid}/{len(leads)} emails",
                        "verified_count": valid,
                        "total": len(leads),
                    })
                elif node_name == "score_leads":
                    leads = node_state.get("scored_leads", [])
                    high  = sum(1 for l in leads if l.get("score", 0) >= 70)
                    emit("score_leads", {
                        "message": f"Scored {len(leads)} leads — {high} high-quality",
                        "total":  len(leads),
                        "high_quality": high,
                    })
                elif node_name == "deliver":
                    emit("deliver", {
                        "message":    "Files ready for download",
                        "csv_path":   node_state.get("final_csv_path"),
                        "xlsx_path":  node_state.get("final_xlsx_path"),
                    })
                    final_state = node_state
                elif node_name == "fail":
                    emit("error", {
                        "message": node_state.get("error_message", "Pipeline failed"),
                    })
                    job["status"] = "failed"
                    return

        if final_state:
            job["status"]         = "done"
            job["csv_path"]       = final_state.get("final_csv_path", "")
            job["xlsx_path"]      = final_state.get("final_xlsx_path", "")
            job["lead_count"]     = len(final_state.get("scored_leads", []))
            job["final_state"]    = final_state
            emit("done", {
                "message":    f"Done! {job['lead_count']} verified leads ready.",
                "lead_count": job["lead_count"],
                "csv_url":    f"/api/leads/download/{job_id}?format=csv",
                "xlsx_url":   f"/api/leads/download/{job_id}?format=xlsx",
            })

    except Exception as e:
        logger.exception(f"[job:{job_id}] Unhandled error: {e}")
        job["status"] = "failed"
        job["events"].append({
            "node":      "error",
            "timestamp": datetime.utcnow().isoformat(),
            "message":   str(e),
        })


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/leads/generate", response_model=JobResponse)
async def generate_leads(req: GenerateRequest, background_tasks: BackgroundTasks):
    """Start a lead generation job. Returns job_id immediately."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id":      job_id,
        "query":   req.query,
        "status":  "queued",
        "events":  [],
        "csv_path": "",
        "xlsx_path": "",
        "lead_count": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    background_tasks.add_task(
        run_lead_job, job_id, req.query, req.max_results, req.max_retries
    )
    return JobResponse(
        job_id=job_id,
        status="queued",
        message="Job started. Connect to stream_url for live updates.",
        stream_url=f"/api/leads/stream/{job_id}",
    )


@app.get("/api/leads/stream/{job_id}")
async def stream_job(job_id: str):
    """Server-Sent Events stream — frontend polls this for live progress."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        job = jobs[job_id]
        last_idx = 0

        while True:
            events = job["events"][last_idx:]
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
                last_idx += 1

            if job["status"] in ("done", "failed"):
                yield f"data: {json.dumps({'node': 'end', 'status': job['status']})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/api/leads/status/{job_id}")
async def job_status(job_id: str):
    """Polling fallback for clients that don't support SSE."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    job = jobs[job_id]
    return {
        "job_id":     job_id,
        "status":     job["status"],
        "lead_count": job.get("lead_count", 0),
        "events":     job["events"],
        "csv_url":    f"/api/leads/download/{job_id}?format=csv"  if job["status"] == "done" else None,
        "xlsx_url":   f"/api/leads/download/{job_id}?format=xlsx" if job["status"] == "done" else None,
    }


@app.get("/api/leads/download/{job_id}")
async def download_leads(job_id: str, format: str = "csv"):
    """Download the final lead file."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(400, f"Job not complete (status: {job['status']})")

    if format == "xlsx" and job.get("xlsx_path"):
        path = Path(job["xlsx_path"])
        if path.exists():
            return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Default to CSV
    path = Path(job["csv_path"])
    if not path.exists():
        raise HTTPException(500, "Output file not found")

    return FileResponse(path, filename=path.name, media_type="text/csv")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}