from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import re
from typing import Optional, Dict, Any, List
import uuid
import json
import logging
import time
from ..database.connection import get_db
from ..database.models import AgroGPTConversation, AgroGPTMessage, AIContext, DiagnosisReport, User, Farm, FarmCrop, AgroGPTUsageLog, AgroGPTFeedback
from ..services.ai_service import generate_agro_gpt_response, stream_agro_gpt_response, generate_guarded_agro_gpt_response
from ..auth.deps import get_current_user, get_optional_current_user, get_authenticated_user
from ..auth.entitlements import check_and_consume_entitlement

logger = logging.getLogger(__name__)
router = APIRouter()

class DiagnosisContextRequest(BaseModel):
    report_id: str
    farmer_id: Optional[str] = None
    farm_id: Optional[str] = None

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)
    language: Optional[str] = "en"
    farmer_id: Optional[str] = None  # ignored: identity always comes from the verified token
    context: Optional[Dict[str, Any]] = None  # only whitelisted keys are ever read

def _safe_location(value) -> Optional[str]:
    """Client-supplied location is data: letters/digits/space/comma only, max 60 chars."""
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[^\w\s,\-]", "", value, flags=re.UNICODE).strip()[:60]
    return cleaned or None

@router.post("/context/diagnosis")
async def attach_diagnosis_context(req: DiagnosisContextRequest, db: Session = Depends(get_db), user: User = Depends(get_authenticated_user)):
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
async def agro_gpt_chat(req: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_authenticated_user)):
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
        try:
            db.commit()
        except Exception:
            db.rollback()

    # 2. Retrieve Farmer Context from DB or request context
    context_data = await fetch_farmer_context(db, farmer_id, req.context)
    
    # 3. Retrieve Previous Messages for Memory
    past_msgs = []
    try:
        past_msgs = db.query(AgroGPTMessage).filter(AgroGPTMessage.conversation_id == conversation_id).order_by(AgroGPTMessage.created_at.asc()).all()
    except Exception:
        pass
    message_history = [{"role": m.role, "content": m.content} for m in past_msgs]
    message_history.append({"role": "user", "content": req.message})

    # Save User Message to DB
    user_msg_id = str(uuid.uuid4())
    try:
        user_msg = AgroGPTMessage(
            id=user_msg_id,
            conversation_id=conversation_id,
            role="user",
            content=req.message,
            language=req.language or "en"
        )
        db.add(user_msg)
        db.commit()
    except Exception:
        db.rollback()

    # 4. Generate AI Response (routed + deterministic safety guard)
    request_id = str(uuid.uuid4())[:8]
    t0 = time.time()
    try:
        result = await generate_guarded_agro_gpt_response(message_history, context_data, req.language or "en")
    except Exception as e:
        logger.error(f"[{request_id}] Error in Agro GPT chat: {type(e).__name__}")
        from ..services.answer_guard import guard_reply
        from ..services.ai_service import get_contextual_gpt_reply
        fb = get_contextual_gpt_reply(message_history, context_data, req.language or "en")
        txt, flags = guard_reply(fb, req.language or "en", "rule_based_fallback")
        result = {"text": txt, "tier": "rule_based_fallback", "task": None, "model": None, "guard_flags": flags}
    latency_ms = int((time.time() - t0) * 1000)
    reply_text = result["text"]
    logger.info("[%s] agrogpt tier=%s task=%s model=%s flags=%s latency_ms=%d", request_id, result["tier"], result["task"],
                result["model"], result["guard_flags"], latency_ms)

    # Save telemetry (no raw prompt / no PII)
    try:
        from ..services.model_registry import model_for
        spec = model_for(result["task"] or "simple") if result["tier"] == "llm" else None
        db.add(AgroGPTUsageLog(
            id=str(uuid.uuid4()),
            request_id=request_id,
            user_id=user.id,
            task_category=result["task"],
            provider=spec.provider if spec else "local_fallback",
            model=result["model"] or "rule_based_fallback",
            source_tier=result["tier"],
            guard_flags=result["guard_flags"] or [],
            latency_ms=latency_ms,
        ))
        db.commit()
    except Exception:
        db.rollback()

    # Save Assistant Response to DB
    assistant_msg_id = str(uuid.uuid4())
    try:
        assistant_msg = AgroGPTMessage(
            id=assistant_msg_id,
            conversation_id=conversation_id,
            role="assistant",
            content=reply_text,
            language=req.language or "en",
            context_references={"active_diagnosis_id": context_data.get("latest_diagnosis", {}).get("report_id")}
        )
        db.add(assistant_msg)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "conversation_id": conversation_id,
        "message_id": assistant_msg_id,
        "request_id": request_id,
        "reply": reply_text,
        "response": reply_text,
        "language": req.language or "en",
        "context_used": bool(context_data),
        "source_tier": result["tier"],
        "ai_unavailable": result["tier"] == "rule_based_fallback",
        "guard_flags": result["guard_flags"],
    }


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str = Field(..., pattern=r"^(helpful|not_helpful)$")
    reason_tag: Optional[str] = Field(None, pattern=r"^(incorrect|not_relevant_to_crop|wrong_language|outdated|unsafe)$")
    comment: Optional[str] = Field(None, max_length=500)


@router.post("/feedback")
async def submit_agrogpt_feedback(
    req: FeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_authenticated_user),
):
    """Records farmer feedback on an AgroGPT assistant message (verified ownership)."""
    msg = db.query(AgroGPTMessage).filter(AgroGPTMessage.id == req.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail={"error": {"code": "MESSAGE_NOT_FOUND", "message": "Message not found."}})
    conv = db.query(AgroGPTConversation).filter(AgroGPTConversation.id == msg.conversation_id).first()
    if not conv or conv.farmer_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}})
    fb = AgroGPTFeedback(
        id=str(uuid.uuid4()),
        message_id=req.message_id,
        user_id=user.id,
        rating=req.rating,
        reason_tag=req.reason_tag,
        comment=req.comment,
    )
    db.add(fb)
    db.commit()
    return {"id": fb.id, "status": "recorded"}

@router.post("/chat/stream")
async def agro_gpt_chat_stream(req: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_authenticated_user)):
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
    if not conv:
        db.add(AgroGPTConversation(id=conversation_id, farmer_id=farmer_id, language=req.language or "en"))
        try:
            db.commit()
        except Exception:
            db.rollback()

    context_data = await fetch_farmer_context(db, farmer_id, req.context)
    past_msgs = db.query(AgroGPTMessage).filter(AgroGPTMessage.conversation_id == conversation_id).order_by(AgroGPTMessage.created_at.asc()).all()
    message_history = [{"role": m.role, "content": m.content} for m in past_msgs]
    message_history.append({"role": "user", "content": req.message})
    try:
        db.add(AgroGPTMessage(id=str(uuid.uuid4()), conversation_id=conversation_id, role="user",
                              content=req.message, language=req.language or "en"))
        db.commit()
    except Exception:
        db.rollback()

    async def event_generator():
        yield f"data: {json.dumps({'conversation_id': conversation_id, 'type': 'start'})}\n\n"
        # Safety first: the guard needs the whole answer, so generate, validate, then emit in chunks.
        try:
            result = await generate_guarded_agro_gpt_response(message_history, context_data, req.language or "en")
        except Exception as e:
            logger.error(f"Agro GPT stream error: {type(e).__name__}")
            from ..services.answer_guard import guard_reply
            from ..services.ai_service import get_contextual_gpt_reply
            txt, flags = guard_reply(get_contextual_gpt_reply(message_history, context_data, req.language or "en"),
                                     req.language or "en", "rule_based_fallback")
            result = {"text": txt, "tier": "rule_based_fallback", "guard_flags": flags}
        full_reply = result["text"]
        words = full_reply.split(" ")
        for i in range(0, len(words), 4):
            yield f"data: {json.dumps({'text': ' '.join(words[i:i+4]) + ' '})}\n\n"
        try:
            db.add(AgroGPTMessage(id=str(uuid.uuid4()), conversation_id=conversation_id, role="assistant",
                                  content=full_reply, language=req.language or "en"))
            db.commit()
        except Exception:
            db.rollback()
        yield f"data: {json.dumps({'type': 'end', 'full_text': full_reply, 'source_tier': result['tier'], 'guard_flags': result['guard_flags']})}\n\n"

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
    loc = ctx.get("village") or _safe_location(req_context.get("location") if req_context else None) or "Mandya"
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
    user: User = Depends(get_authenticated_user)
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


@router.get("/conversations")
async def list_agro_gpt_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_authenticated_user)
):
    """
    GET /api/agro-gpt/conversations
    Returns past Agro GPT conversations for the authenticated farmer.
    """
    convs = (
        db.query(AgroGPTConversation)
        .filter(AgroGPTConversation.farmer_id == user.id)
        .order_by(AgroGPTConversation.created_at.desc())
        .limit(30)
        .all()
    )
    items = []
    for c in convs:
        first_msg = (
            db.query(AgroGPTMessage)
            .filter(AgroGPTMessage.conversation_id == c.id, AgroGPTMessage.role == "user")
            .order_by(AgroGPTMessage.created_at.asc())
            .first()
        )
        title = first_msg.content[:55] if first_msg and first_msg.content else "New conversation"
        items.append({
            "id": c.id,
            "title": title,
            "language": c.language or "en",
            "created_at": c.created_at.isoformat() + "Z" if c.created_at else None
        })
    return {"conversations": items}


@router.get("/conversations/{conversation_id}")
async def get_agro_gpt_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_authenticated_user)
):
    """
    GET /api/agro-gpt/conversations/{conversation_id}
    Returns all messages in a specific Agro GPT conversation.
    """
    conv = db.query(AgroGPTConversation).filter(AgroGPTConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.farmer_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}})
    msgs = (
        db.query(AgroGPTMessage)
        .filter(AgroGPTMessage.conversation_id == conversation_id)
        .order_by(AgroGPTMessage.created_at.asc())
        .all()
    )
    return {
        "conversation_id": conv.id,
        "language": conv.language,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() + "Z" if m.created_at else None
            }
            for m in msgs
        ]
    }


@router.delete("/conversations/{conversation_id}")
async def delete_agro_gpt_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_authenticated_user)
):
    """
    DELETE /api/agro-gpt/conversations/{conversation_id}
    Deletes an Agro GPT conversation and all associated messages for the authenticated owner.
    """
    conv = db.query(AgroGPTConversation).filter(AgroGPTConversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.farmer_id != user.id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Not permitted."}})

    db.query(AgroGPTMessage).filter(AgroGPTMessage.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()
    return {
        "status": "success",
        "message": "Conversation deleted successfully",
        "conversation_id": conversation_id
    }


KARNATAKA_CITIES_KN = {
    "Mandya": "ಮಂಡ್ಯ", "Bengaluru": "ಬೆಂಗಳೂರು", "Bangalore": "ಬೆಂಗಳೂರು",
    "Mysuru": "ಮೈಸೂರು", "Mysore": "ಮೈಸೂರು", "Kolar": "ಕೋಲಾರ",
    "Hassan": "ಹಾಸನ", "Tumakuru": "ತುಮಕೂರು", "Tumkur": "ತುಮಕೂರು",
    "Shivamogga": "ಶಿವಮೊಗ್ಗ", "Belagavi": "ಬೆಳಗಾವಿ", "Hubballi": "ಹುಬ್ಬಳ್ಳಿ",
    "Dharwad": "ಧಾರವಾಡ", "Ballari": "ಬಳ್ಳಾರಿ", "Vijayapura": "ವಿಜಯಪುರ",
    "Kalaburagi": "ಕಲಬುರಗಿ", "Chikkamagaluru": "ಚಿಕ್ಕಮಗಳೂರು", "Chitradurga": "ಚಿತ್ರದುರ್ಗ",
    "Davanagere": "ದಾವಣಗೆರೆ", "Udupi": "ಉಡುಪಿ", "Mangaluru": "ಮಂಗಳೂರು",
    "Bagalkote": "ಬಾಗಲಕೋಟೆ", "Gadag": "ಗದಗ", "Haveri": "ಹಾವೇರಿ",
    "Koppal": "ಕೊಪ್ಪಳ", "Raichur": "ರಾಯಚೂರು", "Yadgir": "ಯಾದಗಿರಿ",
    "Chamarajanagar": "ಚಾಮರಾಜನಗರ", "Ramanagara": "ರಾಮನಗರ", "Chikkaballapur": "ಚಿಕ್ಕಬಳ್ಳಾಪುರ",
    "Kodagu": "ಕೊಡಗು", "Uttara Kannada": "ಉತ್ತರ ಕನ್ನಡ"
}

CROPS_KN = {
    "Tomato": "ಟೊಮೆಟೊ", "Wheat": "ಗೋಧಿ", "Rice": "ಭತ್ತ", "Paddy": "ಭತ್ತ",
    "Rice / Paddy": "ಭತ್ತ", "Cotton": "ಹತ್ತಿ", "Sugarcane": "ಕಬ್ಬು",
    "Maize": "ಮೆಕ್ಕೆಜೋಳ", "Corn": "ಮೆಕ್ಕೆಜೋಳ", "Onion": "ಈರುಳ್ಳಿ",
    "Potato": "ಆಲೂಗಡ್ಡೆ", "Chilli": "ಮೆಣಸಿನಕಾಯಿ", "Chili": "ಮೆಣಸಿನಕಾಯಿ",
    "Groundnut": "ಕಡಲೆಕಾಯಿ", "Ragi": "ರಾಗಿ", "Other": "ಬೆಳೆ"
}

@router.get("/daily-report")
async def get_daily_farm_report(
    location: str = "Mandya",
    crop: str = "Tomato",
    language: str = "en",
    db: Session = Depends(get_db)
):
    """
    GET /api/agro-gpt/daily-report
    Generates a structured Daily Farm Report grounded in live weather and APMC data.
    Supports English (en), Kannada (kn), and Hindi (hi).
    """
    from datetime import datetime
    from .weather import get_current_weather
    from ..database.models import MarketPrice

    w_data = await get_current_weather(q=location)
    temp_max = w_data.get("temp_max") or w_data.get("temp") or 29
    humidity = w_data.get("humidity") or 65
    wind_speed = w_data.get("wind_speed") or 10
    condition = w_data.get("condition") or "partly cloudy"
    city_display = w_data.get("city") or location or "Mandya"
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Query latest local Mandi price if available (prefer farmer's state / Karnataka)
    latest_price = (
        db.query(MarketPrice)
        .filter(MarketPrice.commodity.ilike(f"%{crop}%"), MarketPrice.state.ilike("%Karnataka%"))
        .order_by(MarketPrice.price_date.desc())
        .first()
    )
    if not latest_price:
        latest_price = (
            db.query(MarketPrice)
            .filter(MarketPrice.commodity.ilike(f"%{crop}%"))
            .order_by(MarketPrice.price_date.desc())
            .first()
        )

    if language == "kn":
        city_kn = KARNATAKA_CITIES_KN.get(city_display, city_display)
        crop_kn = CROPS_KN.get(crop, crop)
        headline = f"{city_kn} ಜಿಲ್ಲೆಯ ನಮ್ಮ ಶ್ರಮಜೀವಿ ರೈತರಿಗೆ ಶುಭೋದಯ."
        summary = f"ಇಂದು ಜಿಲ್ಲೆಯಾದ್ಯಂತ ಸಾಧಾರಣ ತಾಪಮಾನದೊಂದಿಗೆ ಭಾಗಶಃ ಮೋಡ ಕವಿದ ವಾತಾವರಣ ನಿರೀಕ್ಷಿಸಲಾಗಿದೆ."
        weather_brief = f"ಮಧ್ಯಾಹ್ನದ ವೇಳೆಗೆ ಗರಿಷ್ಠ {temp_max}°C ತಾಪಮಾನ, {humidity}% ತೇವಾಂಶ ಮತ್ತು ಸಾಧಾರಣ ಗಾಳಿ ({wind_speed} ಕಿ.ಮೀ/ಗಂ) ಇರಲಿದೆ."
        if humidity > 75:
            pest_brief = f"ಹೆಚ್ಚಿನ ತೇವಾಂಶವು ನಿಮ್ಮ {crop_kn} ಬೆಳೆಯಲ್ಲಿ ಶಿಲೀಂಧ್ರ ರೋಗ ಮತ್ತು ಎಲೆ ಚುಕ್ಕೆ ರೋಗದ ಅಪಾಯವನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ."
        else:
            pest_brief = f"ಒಣ ಮತ್ತು ಗಾಳಿಯ ವಾತಾವರಣವು ನಿಮ್ಮ ನಿಂತ ಬೆಳೆಗಳ ಮೇಲೆ ಥ್ರಿಪ್ಸ್ (ನುಸಿ) ಮತ್ತು ಹೇನುಗಳ ಬಾಧೆಯ ಅಪಾಯವನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ."
        crop_action_brief = "ಹಗಲಿನ ಶಾಖದ ವಿರುದ್ಧ ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಕಾಪಾಡಿಕೊಳ್ಳಲು ಸಂಜೆಯ ಸಮಯದಲ್ಲಿ ಸೂಕ್ತ ನೀರಾವರಿ ಒದಗಿಸಿ."
        if latest_price:
            market_brief = f"{latest_price.market_name} ನಲ್ಲಿ {crop_kn} ಮಾದರಿ ದರ ₹{int(latest_price.modal_price)}/ಕ್ವಿಂಟಾಲ್ ಆಗಿದೆ. ಹೆಚ್ಚಿನ ಮಾಹಿತಿಗಾಗಿ ಮಂಡಿ ವಿಭಾಗ ನೋಡಿ."
        else:
            market_brief = "ಇತ್ತೀಚಿನ ಸ್ಥಳೀಯ ಬೆಳೆ ಬೆಲೆಗಳಿಗಾಗಿ, ದಯವಿಟ್ಟು ಅಪ್ಲಿಕೇಶನ್‌ನಲ್ಲಿರುವ ಮಂಡಿ ಟ್ಯಾಬ್ ಅನ್ನು ಪರಿಶೀಲಿಸಿ."
        quote = "ನಿಮ್ಮ ಪರಿಶ್ರಮವೇ ದೇಶಕ್ಕೆ ಅನ್ನ; ನಿಮ್ಮ ಪ್ರಯತ್ನದಷ್ಟೇ ನಿಮ್ಮ ಫಸಲು ಸಮೃದ್ಧವಾಗಿರಲಿ."
    elif language == "hi":
        headline = f"{city_display} के हमारे मेहनती किसान को सुप्रभात।"
        summary = "आज जिले भर में मध्यम तापमान के साथ आंशिक रूप से बादल छाए रहने की उम्मीद है।"
        weather_brief = f"दोपहर में अधिकतम {temp_max}°C तापमान, {humidity}% नमी और हल्की हवा ({wind_speed} किमी/घंटा) रहने की संभावना है।"
        if humidity > 75:
            pest_brief = f"अधिक नमी से आपकी खड़ी {crop} फसलों पर फफूंद और झुलसा रोग का खतरा बढ़ जाता है।"
        else:
            pest_brief = "शुष्क और हवादार परिस्थितियां आपकी खड़ी फसलों पर थ्रिप्स और माहू (एफिड्स) के जोखिम को बढ़ाती हैं।"
        crop_action_brief = "दिन की गर्मी के खिलाफ मिट्टी की नमी बनाए रखने के लिए शाम के समय पर्याप्त सिंचाई सुनिश्चित करें।"
        if latest_price:
            market_brief = f"{latest_price.market_name} में {latest_price.commodity} का मॉडल भाव ₹{int(latest_price.modal_price)}/क्विंटल है। अधिक भाव के लिए मंडी टैब देखें।"
        else:
            market_brief = "नवीनतम स्थानीय फसल कीमतों के लिए, कृपया एप्लिकेशन में मंडी (Mandi) टैब देखें।"
        quote = "आपका समर्पण राष्ट्र का पोषण करता है; आपकी फसल आपकी मेहनत जितनी ही समृद्ध हो।"
    else:
        headline = f"Good morning to our hardworking farmer in {city_display}."
        summary = f"{condition.capitalize()} skies with moderate temperatures are expected today across the district."
        weather_brief = f"Expect a high of {temp_max}°C with {humidity}% humidity and light breezes ({wind_speed} km/h) throughout the afternoon."
        if humidity > 75:
            pest_brief = f"Elevated humidity ({humidity}%) increases the risk of fungal blight and leaf spot on your standing {crop} crops."
        else:
            pest_brief = "Dry and windy conditions increase the risk of thrips and aphids on your standing crops."
        crop_action_brief = "Ensure adequate irrigation during the evening to maintain soil moisture levels against the daytime heat."
        if latest_price:
            market_brief = f"Latest verified {latest_price.commodity} modal price at {latest_price.market_name} is ₹{int(latest_price.modal_price)}/quintal. Check the Mandi tab for full directory."
        else:
            market_brief = "For the latest local crop prices, please check the Mandi tab in the application."
        quote = "Your dedication feeds the nation; may your harvest be as bountiful as your efforts."

    return {
        "available": True,
        "date": today_str,
        "location": city_display,
        "crop": crop,
        "language": language,
        "headline": headline,
        "summary": summary,
        "weather": weather_brief,
        "pest_disease": pest_brief,
        "crop_action": crop_action_brief,
        "market": market_brief,
        "quote": quote
    }


