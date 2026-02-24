"""
Digital Employee Swarm — Web Dashboard (FastAPI)
REST API + WebSocket 即時通訊
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
import json

from orchestrator.router import MasterOrchestrator
from harness.task_queue import TaskPriority
from harness.vector_store import VectorStore
from harness.hitl_manager import HITLManager, ApprovalAction
from web.auth import AuthManager, Role

# === 全域初始化 ===
orchestrator = MasterOrchestrator()
vector_store = VectorStore()
auth = AuthManager()
hitl = HITLManager()


@asynccontextmanager
async def _lifespan(app):
    yield
    orchestrator.task_queue.stop(graceful=True)


app = FastAPI(title="Digital Employee Swarm", version="2.0", lifespan=_lifespan)

# 索引知識庫
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sops_dir = os.path.join(project_root, "docs", "sops")
indexed = vector_store.index_directory(sops_dir)

# 靜態檔案
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# === Request/Response Models ===

class LoginRequest(BaseModel):
    username: str
    password: str


class DispatchRequest(BaseModel):
    prompt: str
    token: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class ResolveRequest(BaseModel):
    token: str
    resolved_by: str = "admin"
    note: str = ""


class QueueSubmitRequest(BaseModel):
    agent_name: str
    instruction: str
    priority: str = "NORMAL"
    callback_url: Optional[str] = None
    token: str


# === Helper: 驗證 Token ===

def verify_auth(token: str, action: str = "status"):
    payload = auth.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 無效或已過期")
    if not auth.check_permission(token, action):
        raise HTTPException(status_code=403, detail="權限不足")
    return payload


# === Routes ===

@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.post("/api/login")
async def login(req: LoginRequest):
    token = auth.authenticate(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    info = auth.get_user_info(token)
    return {"token": token, "user": info}


@app.get("/api/status")
async def get_status(token: str):
    verify_auth(token, "status")
    agents = {}
    for name, agent in orchestrator.agents.items():
        agents[name] = agent.get_status()
    return {
        "agents": agents,
        "llm": orchestrator.llm.get_status(),
        "mcp": orchestrator.mcp.health_check(),
        "a2a": {"registered": len(orchestrator.a2a.registry)},
        "skills": {"count": len(orchestrator.skill_registry.list_all())},
        "vector_store": vector_store.get_status(),
        "intent_mode": orchestrator.classifier.mode,
    }


@app.post("/api/dispatch")
async def dispatch(req: DispatchRequest):
    verify_auth(req.token, "dispatch")
    result = orchestrator.dispatch(req.prompt)
    return {"result": result, "prompt": req.prompt}


@app.get("/api/history")
async def get_history(token: str):
    verify_auth(token, "history")
    return {"history": orchestrator.dispatch_log[-20:]}


@app.get("/api/agents")
async def get_agents(token: str):
    verify_auth(token, "agents")
    agents = {}
    for name, agent in orchestrator.agents.items():
        status = agent.get_status()
        status["trigger_keywords"] = agent.trigger_keywords[:5]
        agents[name] = status
    return {"agents": agents}


@app.post("/api/search")
async def search_knowledge(req: SearchRequest):
    results = vector_store.search(req.query, top_k=req.top_k)
    return {"results": results, "query": req.query}


# === Approval API ===

def _approval_to_dict(req):
    return {
        "request_id": req.request_id,
        "agent": req.agent_name,
        "task": req.task,
        "risk_level": req.risk_level,
        "risk_reason": req.risk_reason,
        "status": req.status.value,
        "created_at": req.created_at,
        "resolved_at": req.resolved_at,
        "resolved_by": req.resolved_by,
        "resolution_note": req.resolution_note,
        "webhook_sent": req.webhook_sent,
        "timeout_hours": req.timeout_hours,
    }


@app.get("/api/approvals/pending")
async def get_pending_approvals(token: str):
    verify_auth(token, "approvals")
    requests = hitl.get_pending_requests()
    return {"requests": [_approval_to_dict(r) for r in requests]}


@app.get("/api/approvals/{request_id}")
async def get_approval(request_id: str, token: str):
    verify_auth(token, "approvals")
    req = hitl.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="審批請求不存在")
    return _approval_to_dict(req)


@app.post("/api/approvals/{request_id}/approve")
async def approve_request(request_id: str, body: ResolveRequest):
    verify_auth(body.token, "approvals")
    req = hitl.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="審批請求不存在")
    updated = hitl.resolve(
        request_id, ApprovalAction.APPROVE,
        resolved_by=body.resolved_by, note=body.note,
    )
    return _approval_to_dict(updated)


@app.post("/api/approvals/{request_id}/reject")
async def reject_request(request_id: str, body: ResolveRequest):
    verify_auth(body.token, "approvals")
    req = hitl.get_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="審批請求不存在")
    updated = hitl.resolve(
        request_id, ApprovalAction.REJECT,
        resolved_by=body.resolved_by, note=body.note,
    )
    return _approval_to_dict(updated)


@app.post("/api/approvals/expire")
async def expire_approvals(token: str):
    verify_auth(token, "approvals")
    expired = hitl.expire_timeouts()
    return {"expired_count": len(expired), "expired_ids": expired}


# === Queue API ===

def _task_to_dict(task):
    return {
        "task_id": task.task_id,
        "agent_name": task.agent_name,
        "instruction": task.instruction,
        "priority": task.priority.name,
        "status": task.status.value,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "result": task.result,
        "error": task.error,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "callback_url": task.callback_url,
        "metadata": task.metadata,
    }


@app.post("/api/queue/submit")
async def submit_task(req: QueueSubmitRequest):
    verify_auth(req.token, "dispatch")
    try:
        priority = TaskPriority[req.priority.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {req.priority}")
    task_id = orchestrator.submit(
        req.agent_name, req.instruction, priority, req.callback_url
    )
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/queue/tasks/{task_id}")
async def get_task_status(task_id: str, token: str):
    verify_auth(token, "status")
    task = orchestrator.task_queue.get_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_dict(task)


@app.post("/api/queue/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, token: str):
    verify_auth(token, "dispatch")
    cancelled = orchestrator.task_queue.cancel(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=400,
            detail="Task cannot be cancelled (not found or not in PENDING state)",
        )
    return {"task_id": task_id, "status": "cancelled"}


@app.get("/api/queue/stats")
async def get_queue_stats(token: str):
    verify_auth(token, "status")
    return orchestrator.task_queue.get_queue_stats()


@app.get("/api/queue/pending")
async def get_pending_tasks(token: str, agent_name: Optional[str] = None):
    verify_auth(token, "status")
    tasks = orchestrator.task_queue.get_pending_tasks(agent_name)
    return {"tasks": [_task_to_dict(t) for t in tasks]}


@app.get("/api/mcp")
async def get_mcp(token: str):
    verify_auth(token, "mcp")
    resources = {}
    for name, r in orchestrator.mcp.resources.items():
        resources[name] = r.to_dict()
    return {"resources": resources, "operations": len(orchestrator.mcp.operation_log)}


@app.get("/api/skills")
async def get_skills(token: str):
    verify_auth(token, "skills")
    skills = []
    for s in orchestrator.skill_registry.list_all():
        skills.append({
            "name": s.name,
            "description": s.description,
            "category": s.category,
            "tags": s.tags,
        })
    return {"skills": skills}


# === WebSocket ===

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "auth":
                token = auth.authenticate(
                    msg.get("username", ""), msg.get("password", "")
                )
                if token:
                    info = auth.get_user_info(token)
                    await ws.send_json({"type": "auth_ok", "token": token, "user": info})
                else:
                    await ws.send_json({"type": "auth_fail"})

            elif msg.get("type") == "dispatch":
                token = msg.get("token", "")
                if not auth.check_permission(token, "dispatch"):
                    await ws.send_json({"type": "error", "message": "權限不足"})
                    continue
                prompt = msg.get("prompt", "")
                await ws.send_json({"type": "processing", "prompt": prompt})
                result = orchestrator.dispatch(prompt)
                await ws.send_json({"type": "result", "result": result, "prompt": prompt})

            elif msg.get("type") == "status":
                agents = {n: a.get_status() for n, a in orchestrator.agents.items()}
                await ws.send_json({"type": "status", "agents": agents})

    except WebSocketDisconnect:
        pass
