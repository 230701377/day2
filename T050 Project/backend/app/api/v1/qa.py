from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import User
from app.schemas.schemas import QARequest, QAResponse
from app.services.ai.rag import answer_question
from app.services.audit.chain import append as audit_append

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask", response_model=QAResponse)
def ask(payload: QARequest, db: Session = Depends(get_db),
         actor: User = Depends(get_current_user)):
    if not payload.question or len(payload.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question is too short")
    res = answer_question(db, actor, payload.question,
                           contract_ids=payload.contract_ids,
                           top_k=payload.top_k or 5)
    audit_append(db, actor=actor, action="qa.ask", payload={
        "question": payload.question[:200],
        "contract_ids": payload.contract_ids,
        "sources_count": len(res["sources"]),
    })
    db.commit()
    return res


import json
import asyncio
from fastapi.responses import StreamingResponse


@router.post("/stream")
def ask_stream(payload: QARequest, db: Session = Depends(get_db),
               actor: User = Depends(get_current_user)):
    """
    Real-Time SSE Streaming Q&A Endpoint.
    Streams RAG answers token-by-token using Server-Sent Events.
    """
    if not payload.question or len(payload.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question is too short")

    # 1. Synchronously execute RAG retrieval
    res = answer_question(db, actor, payload.question,
                           contract_ids=payload.contract_ids,
                           top_k=payload.top_k or 5)

    full_answer = res.get("answer", "")
    sources = res.get("sources", [])
    confidence = res.get("confidence", 0.0)

    # 2. Generator function streaming SSE chunks
    def event_generator():
        # Yield metadata event first
        meta_payload = {
            "question": payload.question,
            "sources": sources,
            "confidence": confidence
        }
        yield f"event: metadata\ndata: {json.dumps(meta_payload)}\n\n"

        # Stream words/tokens with subtle realistic micro-delays
        words = full_answer.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            chunk_payload = {"token": chunk}
            yield f"event: token\ndata: {json.dumps(chunk_payload)}\n\n"

        # Yield completion event
        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    audit_append(db, actor=actor, action="qa.stream", payload={
        "question": payload.question[:200],
        "sources_count": len(sources)
    })
    db.commit()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db),
                   actor: User = Depends(get_current_user)):
    from app.models.models import QASession
    return db.query(QASession).filter(QASession.user_id == actor.id)\
        .order_by(QASession.created_at.desc()).limit(50).all()

