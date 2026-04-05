"""
FastAPI entrypoint
==================
POST /api/leads/generate          → start job, returns job_id
GET  /api/leads/stream/{job_id}   → SSE live progress
GET  /api/leads/status/{job_id}   → JSON polling fallback
GET  /api/leads/download/{job_id} → file download (?format=csv|xlsx)
GET  /api/health                  → health check
"""
import os, uuid, asyncio, json, logging
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from app.agents.graph import lead_graph
from app.agents.state import LeadState

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Prompt-to-Leads API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store (swap for Redis in prod) ──────────────────────────────
jobs: dict[str, dict] = {}


# ── Pydantic models ───────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    query:       str
    max_results: int = 100
    max_retries: int = 3


class JobCreated(BaseModel):
    job_id:     str
    stream_url: str
    status_url: str


# ── Background task ───────────────────────────────────────────────────────────

async def _run_job(job_id: str, req: GenerateRequest):
    job = jobs[job_id]

    def push(node: str, **data):
        event = {"node": node, "ts": datetime.utcnow().isoformat(), **data}
        job["events"].append(event)

    try:
        job["status"] = "running"
        push("start", message=f'Starting: "{req.query}"')

        initial: LeadState = {
            "messages": [], "raw_query": req.query,
            "business_type": "", "location": "", "radius_km": 25.0,
            "enrichment_reqs": [], "max_results": req.max_results,
            "raw_businesses": [], "scrape_errors": [],
            "enriched_leads": [], "enrichment_errors": [],
            "verified_leads": [], "verification_errors": [],
            "scored_leads": [], "final_csv_path": "", "final_xlsx_path": "",
            "retry_count": 0, "max_retries": req.max_retries,
            "status": "running", "error_message": "",
        }

        loop = asyncio.get_event_loop()
        final = None

        # Run synchronous LangGraph in thread pool so we don't block
        def _run():
            return list(lead_graph.stream(initial, config={"configurable": {"thread_id": job_id}}))

        chunks = await loop.run_in_executor(None, _run)

        for chunk in chunks:
            for node_name, s in chunk.items():
                if node_name == "parse_query":
                    push("parse_query",
                         message="Query understood",
                         business_type=s.get("business_type"),
                         location=s.get("location"),
                         radius_km=s.get("radius_km"))

                elif node_name == "scrape_maps":
                    n = len(s.get("raw_businesses", []))
                    push("scrape_maps", message=f"Found {n} businesses on Google Maps", count=n)

                elif node_name == "enrich_websites":
                    n = len(s.get("enriched_leads", []))
                    push("enrich_websites", message=f"Enriched {n} businesses with emails", count=n)

                elif node_name == "verify_emails":
                    vl  = s.get("verified_leads", [])
                    ok  = sum(1 for l in vl if l.get("email_valid"))
                    push("verify_emails",
                         message=f"Verified {ok}/{len(vl)} emails as deliverable",
                         verified=ok, total=len(vl))

                elif node_name == "score_leads":
                    sl   = s.get("scored_leads", [])
                    high = sum(1 for l in sl if l.get("score", 0) >= 70)
                    push("score_leads",
                         message=f"Scored {len(sl)} leads — {high} high-quality",
                         total=len(sl), high_quality=high,
                         preview=[{k: l.get(k) for k in
                                   ("name","primary_email","score","rating","review_count")}
                                  for l in sl[:5]])

                elif node_name == "deliver":
                    push("deliver",
                         message="Files ready for download",
                         csv_url=f"/api/leads/download/{job_id}?format=csv",
                         xlsx_url=f"/api/leads/download/{job_id}?format=xlsx")
                    final = s

                elif node_name == "fail":
                    push("fail", message=s.get("error_message", "Pipeline failed"))
                    job["status"] = "failed"
                    return

        if final:
            job["status"]     = "done"
            job["csv_path"]   = final.get("final_csv_path", "")
            job["xlsx_path"]  = final.get("final_xlsx_path", "")
            job["lead_count"] = len(final.get("scored_leads", []))
            job["preview"]    = [{k: l.get(k) for k in
                                   ("name","primary_email","score","rating","review_count",
                                    "address","phone","email_verified","email_status","owner_name")}
                                  for l in final.get("scored_leads", [])[:20]]
            push("done",
                 message=f'{job["lead_count"]} verified leads ready!',
                 lead_count=job["lead_count"],
                 csv_url=f"/api/leads/download/{job_id}?format=csv",
                 xlsx_url=f"/api/leads/download/{job_id}?format=xlsx")

    except Exception as e:
        logger.exception(f"[job {job_id}] Fatal: {e}")
        job["status"] = "failed"
        job["events"].append({"node": "fail", "ts": datetime.utcnow().isoformat(),
                               "message": str(e)})


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/leads/generate", response_model=JobCreated)
async def generate(req: GenerateRequest, bg: BackgroundTasks):
    jid = str(uuid.uuid4())
    jobs[jid] = {"id": jid, "query": req.query, "status": "queued",
                  "events": [], "csv_path": "", "xlsx_path": "",
                  "lead_count": 0, "preview": [],
                  "created_at": datetime.utcnow().isoformat()}
    bg.add_task(_run_job, jid, req)
    return JobCreated(
        job_id=jid,
        stream_url=f"/api/leads/stream/{jid}",
        status_url=f"/api/leads/status/{jid}",
    )


@app.get("/api/leads/stream/{job_id}")
async def stream(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    async def gen() -> AsyncGenerator[str, None]:
        job, seen = jobs[job_id], 0
        while True:
            for ev in job["events"][seen:]:
                yield f"data: {json.dumps(ev)}\n\n"
                seen += 1
            if job["status"] in ("done", "failed"):
                yield f"data: {json.dumps({'node':'end','status':job['status']})}\n\n"
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/leads/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404)
    j = jobs[job_id]
    return {**j, "csv_url": f"/api/leads/download/{job_id}?format=csv" if j["status"] == "done" else None,
            "xlsx_url": f"/api/leads/download/{job_id}?format=xlsx" if j["status"] == "done" else None}


@app.get("/api/leads/download/{job_id}")
async def download(job_id: str, format: str = "csv"):
    if job_id not in jobs:
        raise HTTPException(404)
    j = jobs[job_id]
    if j["status"] != "done":
        raise HTTPException(400, f"Job not complete (status: {j['status']})")

    if format == "xlsx" and j.get("xlsx_path"):
        p = Path(j["xlsx_path"])
        if p.exists():
            return FileResponse(p, filename=p.name,
                                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    p = Path(j["csv_path"])
    if not p.exists():
        raise HTTPException(500, "File not found")
    return FileResponse(p, filename=p.name, media_type="text/csv")


@app.get("/api/health")
async def health():
    return {"status": "ok", "jobs_in_memory": len(jobs)}