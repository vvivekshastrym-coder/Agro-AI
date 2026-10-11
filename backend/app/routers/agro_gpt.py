from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import json
import logging
from ..database.connection import get_db
from ..database.models import AgroGPTConversation, AgroGPTMessage, AIContext, DiagnosisReport, User, Farm, FarmCrop
from ..services.ai_service import generate_agro_gpt_response, stream_agro_gpt_response
from ..auth.deps import get_current_user
from ..auth.entitlements import check_and_consume_entitlement

logger = logging.getLogger(__name__)
router = APIRouter()

class DiagnosisContextRequest(BaseModel):
    report_id: str
    farmer_id: Optional[str] = None
    farm_id: Optional[str] = None

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    language: Optional[str] = "en"
    farmer_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

@router.post("/context/diagnosis")
async def attach_diagnosis_context(req: DiagnosisContextRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    POST /api/agro-gpt/context/diagnosis
    Stores a diagnosis report as active context for Agro GPT.
    """
    report = db.query(DiagnosisReport).filter(DiagnosisReport.id == req.report_id, DiagnosisReport.farmer_id == user.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnosis report not found")

    farmer_id = user.id
    
    ctx = db.query(AIContext).filter(AIContext.farmer_id == farmer_id).first()
    if not ctx:
        ctx = AIContext(farmer_id=farmer_id)
        db.add(ctx)
        
    ctx.active_diagnosis_id = report.id
    db.commit()
    
    return {"status": "success", "message": "Diagnosis context attached to Agro GPT", "report_id": report.id}

@router.post("/chat")
async def agro_gpt_chat(req: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    POST /api/agro-gpt/chat
    Main Agro GPT chat endpoint with full farmer DB context retrieval.
    """
    farmer_id = user.id
    conversation_id = req.conversation_id or str(uuid.uuid4())
    
    # 0. Enforce server-side entitlement
    check_and_consume_entitlement(db, user.id, "kisan_chat", consume=True)

    # 1. Get or create conversation in DB (never touch another user's conversation)
    conv = db.query(AgroGPTConversation).filter(AgroGPTConversation.id == conversation_id).first()
    if conv and conv.farmer_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}})
    if not conv:
        conv = AgroGPTConversation(id=conversation_id, farmer_id=farmer_id, language=req.language or "en")
        db.add(conv)
        db.commit()

    # 2. Retrieve Farmer Context from DB
    context_data = await fetch_farmer_context(db, farmer_id, req.context)
    
    # 3. Retrieve Previous Messages for Memory
    past_msgs = db.query(AgroGPTMessage).filter(AgroGPTMessage.conversation_id == conversation_id).order_by(AgroGPTMessage.created_at.asc()).all()
    message_history = [{"role": m.role, "content": m.content} for m in past_msgs]
    message_history.append({"role": "user", "content": req.message})

    # Save User Message to DB
    user_msg = AgroGPTMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=req.message,
        language=req.language or "en"
    )
    db.add(user_msg)
    db.commit()

    # 4. Generate AI Response
    try:
        reply_text = await generate_agro_gpt_response(message_history, context_data, req.language or "en")
    except Exception as e:
        logger.error(f"Error in Agro GPT chat: {e}")
        raise HTTPException(status_code=503, detail={"error": {"code": "ASSISTANT_UNAVAILABLE",
                            "message": "Kisan GPT is temporarily unavailable. Your message was saved; please retry.", "retryable": True}})

    # Save Assistant Response to DB
    assistant_msg = AgroGPTMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="assistant",
        content=reply_text,
        language=req.language or "en",
        context_references={"active_diagnosis_id": context_data.get("latest_diagnosis", {}).get("report_id")}
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "conversation_id": conversation_id,
        "message_id": assistant_msg.id,
        "reply": reply_text,
        "language": req.language or "en",
        "context_used": bool(context_data)
    }

@router.post("/chat/stream")
async def agro_gpt_chat_stream(req: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    POST /api/agro-gpt/chat/stream
    Streams Agro GPT response via SSE (Server-Sent Events).
    """
    farmer_id = user.id
    conversation_id = req.conversation_id or str(uuid.uuid4())
    
    # Enforce server-side entitlement
    check_and_consume_entitlement(db, user.id, "kisan_chat", consume=True)

    conv = db.query(AgroGPTConversation).filter(AgroGPTConversation.id == conversation_id).first()
    if conv and conv.farmer_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}})

    context_data = await fetch_farmer_context(db, farmer_id, req.context)
    past_msgs = db.query(AgroGPTMessage).filter(AgroGPTMessage.conversation_id == conversation_id).order_by(AgroGPTMessage.created_at.asc()).all()
    message_history = [{"role": m.role, "content": m.content} for m in past_msgs]
    message_history.append({"role": "user", "content": req.message})

    async def event_generator():
        yield f"data: {json.dumps({'conversation_id': conversation_id, 'type': 'start'})}\n\n"
        full_reply = ""
        async for chunk in stream_agro_gpt_response(message_history, context_data, req.language or "en"):
            full_reply += chunk
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'end', 'full_text': full_reply})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def fetch_farmer_context(db: Session, farmer_id: str, req_context: Optional[dict] = None) -> dict:
    """Helper to pull genuine farmer profile, farm, crop, and latest diagnosis context from DB."""
    ctx = {}
    
    # 1. User/Farmer Profile
    user = db.query(User).filter(User.id == farmer_id).first()
    if user:
        ctx["farmer_name"] = user.full_name
        ctx["language"] = user.preferred_language

    # 2. Farm & Crop details
    farm = db.query(Farm).filter(Farm.user_id == farmer_id).first()
    if farm:
        ctx["farm_size"] = farm.total_acres
        ctx["village"] = farm.village
        ctx["district"] = farm.district
        ctx["state"] = farm.state
        crop = db.query(FarmCrop).filter(FarmCrop.farm_id == farm.id).first()
        if crop:
            ctx["current_crop"] = crop.crop_name

    # 3. Latest Diagnosis Report
    report_id = None
    if req_context and req_context.get("diagnosis_report_id"):
        report_id = req_context.get("diagnosis_report_id")
    else:
        ai_ctx = db.query(AIContext).filter(AIContext.farmer_id == farmer_id).first()
        if ai_ctx and ai_ctx.active_diagnosis_id:
            report_id = ai_ctx.active_diagnosis_id

    if report_id:
        diag = db.query(DiagnosisReport).filter(DiagnosisReport.id == report_id, DiagnosisReport.farmer_id == farmer_id).first()
        if diag:
            ctx["latest_diagnosis"] = {
                "report_id": diag.id,
                "crop": diag.crop,
                "disease": diag.disease,
                "severity": diag.severity,
                "organic_treatment": diag.organic_treatment or [],
                "chemical_treatment": diag.chemical_treatment or []
            }

    # 4. Fetch Live Weather for Farmer's Location
    loc = ctx.get("village") or (req_context.get("location") if req_context else None) or "Mandya"
    try:
        from .weather import get_current_weather
        w_data = await get_current_weather(q=loc)
        if w_data.get("available"):
            ctx["weather"] = w_data
    except Exception as e:
        logger.warning(f"Could not load weather for farmer context: {e}")

    return ctx



@router.get("/daily-digest")
async def get_daily_digest(
    farmer_id: Optional[str] = None,
    language: str = "en",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    GET /api/agro-gpt/daily-digest
    Generates a short personalized AI morning farm summary for the home dashboard.
    Uses farmer profile, crops, and last diagnosis for context.
    """
    from datetime import datetime
    import json

    farmer_id = user.id  # query param ignored
    context_data = await fetch_farmer_context(db, farmer_id)

    # Build a concise digest prompt
    hour = datetime.now().hour
    greeting_time = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"

    lang_name = {"en": "English", "hi": "Hindi", "kn": "Kannada", "te": "Telugu", "ta": "Tamil", "mr": "Marathi"}.get(language, language)

    farmer_name = context_data.get("farmer_name", "Farmer")
    crop = context_data.get("current_crop", "your crops")
    village = context_data.get("village", "your village")
    diag = context_data.get("latest_diagnosis")

    prompt = f"""You are Agro GPT, a friendly AI farm companion for Indian farmers.
Generate a short, warm, practical morning farm digest (4-6 bullet points) in {lang_name} for this farmer.
IMPORTANT: Respond ONLY in {lang_name}.

Farmer: {farmer_name}
Location: {village}
Current Crop: {crop}
{f"Recent Diagnosis: {diag['crop']} has {diag['disease']} ({diag['severity']} severity)" if diag else "No recent crop diagnosis."}

Guidelines:
- Be encouraging and practical
- Mention 1 seasonal tip for {crop}
- Mention the importance of checking weather before spraying
- If there was a recent diagnosis, remind about treatment
- Keep it under 6 bullet points
- Use relevant farming emojis
- Do NOT fabricate specific prices or weather numbers"""

    try:
        reply = await generate_agro_gpt_response(
            [{"role": "user", "content": prompt}],
            {},
            language
        )
        return {
            "digest": reply,
            "farmer_id": farmer_id,
            "language": language,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Daily digest generation failed: {e}")
        raise HTTPException(status_code=503, detail={"error": {"code": "DIGEST_UNAVAILABLE",
                            "message": "Daily digest is unavailable right now.", "retryable": True}})

