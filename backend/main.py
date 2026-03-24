from fastapi import FastAPI, Depends, HTTPException, status, Request, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
from dotenv import load_dotenv

import models
import schemas
from database import engine, get_db

# LINE API Imports
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

load_dotenv()

# LINE Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="HubCargo Delivery API")

# Setup CORS to allow UI components to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to HubCargo Delivery API"}

# --- Inquiry Endpoints ---

@app.post("/api/inquiries", response_model=schemas.InquiryResponse, status_code=status.HTTP_201_CREATED)
def create_inquiry(inquiry: schemas.InquiryCreate, db: Session = Depends(get_db)):
    db_inquiry = models.Inquiry(
        id=f"YK-{str(uuid.uuid4()).split('-')[0].upper()}",
        customer_name=inquiry.customer_name,
        phone_number=inquiry.phone_number,
        pickup_location=inquiry.pickup_location,
        delivery_location=inquiry.delivery_location,
        detail=inquiry.detail,
        status="received"
    )
    db.add(db_inquiry)
    db.commit()
    db.refresh(db_inquiry)
    return db_inquiry

@app.get("/api/inquiries", response_model=List[schemas.InquiryResponse])
def get_inquiries(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    inquiries = db.query(models.Inquiry).order_by(models.Inquiry.created_at.desc()).offset(skip).limit(limit).all()
    return inquiries

@app.post("/api/inquiries/{inquiry_id}/dispatch", response_model=schemas.InquiryResponse)
def dispatch_inquiry(inquiry_id: str, request_data: schemas.DispatchRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    inquiry = db.query(models.Inquiry).filter(models.Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    partner = db.query(models.Partner).filter(models.Partner.id == request_data.partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
        
    inquiry.status = "dispatched"
    inquiry.dispatched_to_partner_id = request_data.partner_id
    db.commit()
    db.refresh(inquiry)
    
    # Send LINE message to partner's line_group_id asynchronously
    if partner.line_group_id and LINE_CHANNEL_ACCESS_TOKEN:
        background_tasks.add_task(send_line_push_message, partner.line_group_id, inquiry, partner)
    
    return inquiry

def send_line_push_message(to_id: str, inquiry: models.Inquiry, partner: models.Partner):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        flex_dict = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📞 お客様への連絡依頼",
                        "color": "#ffffff",
                        "align": "start",
                        "size": "md",
                        "weight": "bold"
                    }
                ],
                "backgroundColor": "#2764E5",
                "paddingTop": "12px",
                "paddingBottom": "12px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{inquiry.customer_name} 様",
                        "weight": "bold",
                        "size": "xl",
                        "wrap": True,
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": f"☎ {inquiry.phone_number}",
                        "color": "#2764E5",
                        "weight": "bold",
                        "size": "lg"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "引取:", "color": "#aaaaaa", "size": "sm", "flex": 1},
                                    {"type": "text", "text": f"{inquiry.pickup_location}", "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "納品:", "color": "#aaaaaa", "size": "sm", "flex": 1},
                                    {"type": "text", "text": f"{inquiry.delivery_location}", "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                                ]
                            },
                            {
                                "type": "text",
                                "text": f"詳細:\n{inquiry.detail}",
                                "wrap": True,
                                "color": "#666666",
                                "size": "sm",
                                "margin": "lg"
                            }
                        ],
                        "backgroundColor": "#f8f9fa",
                        "paddingAll": "12px",
                        "cornerRadius": "8px",
                        "borderColor": "#e9ecef",
                        "borderWidth": "1px"
                    }
                ],
                "paddingAll": "20px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "message",
                            "label": "✔ 完了報告する",
                            "text": f"完了 {inquiry.id}"
                        },
                        "color": "#e9ecef",
                        "style": "secondary"
                    }
                ],
                "paddingAll": "20px"
            }
        }
        
        try:
            flex_container = FlexContainer.from_dict(flex_dict)
            flex_message = FlexMessage(alt_text=f"📞 お客様への連絡依頼: {inquiry.customer_name} 様", contents=flex_container)
            
            line_bot_api.push_message(
                PushMessageRequest(
                    to=to_id,
                    messages=[flex_message]
                )
            )
        except Exception as e:
            print(f"Failed to send LINE Flex message: {e}")

@app.post("/api/inquiries/{inquiry_id}/complete", response_model=schemas.InquiryResponse)
def complete_inquiry(inquiry_id: str, db: Session = Depends(get_db)):
    # This endpoint can be used by the webhook or manually to mark as completed
    inquiry = db.query(models.Inquiry).filter(models.Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
        
    inquiry.status = "completed"
    db.commit()
    db.refresh(inquiry)
    return inquiry

# --- Partner Endpoints ---

@app.post("/api/partners", response_model=schemas.PartnerResponse, status_code=status.HTTP_201_CREATED)
def create_partner(partner: schemas.PartnerCreate, db: Session = Depends(get_db)):
    db_partner = models.Partner(**partner.dict())
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    return db_partner

@app.get("/api/partners", response_model=List[schemas.PartnerResponse])
def get_partners(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    partners = db.query(models.Partner).filter(models.Partner.is_active == True).offset(skip).limit(limit).all()
    return partners

@app.delete("/api/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner(partner_id: int, db: Session = Depends(get_db)):
    partner = db.query(models.Partner).filter(models.Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # Soft delete
    partner.is_active = False
    db.commit()
    return {"ok": True}

# --- Webhook Endpoint ---

@app.post("/webhook/line")
async def line_webhook(request: Request, x_line_signature: str = Header(None)):
    if not x_line_signature:
        raise HTTPException(status_code=400, detail="X-Line-Signature header required")

    body = await request.body()
    body_str = body.decode('utf-8')

    try:
        handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Please check your channel access token/channel secret.")
    
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # This is where we handle messages from Partners, like "完了" text to mark done, etc.
    user_id = event.source.user_id
    group_id = event.source.group_id if hasattr(event.source, "group_id") else None
    
    received_text = event.message.text
    print(f"Received message: {received_text} from {group_id or user_id}")
    
    # 完了報告の処理: 例 "完了 YK-1234"
    if "完了" in received_text and "YK-" in received_text:
        import re
        match = re.search(r'YK-\w+', received_text)
        if match:
            inquiry_id = match.group()
            
            # Since we are in an event handler (synchronous callback), we create a DB session manually
            from database import SessionLocal
            db = SessionLocal()
            try:
                # Find the inquiry
                inquiry = db.query(models.Inquiry).filter(models.Inquiry.id == inquiry_id).first()
                if inquiry and inquiry.status == "dispatched":
                    inquiry.status = "completed"
                    db.commit()
                    
                    # Reply back via Messaging API
                    reply_text = f"【報告受理】\n受付番号 {inquiry_id} (顧客: {inquiry.customer_name} 様) の連絡完了報告を受け付けました！ありがとうございました。"
                    
                    from linebot.v3.messaging import ReplyMessageRequest
                    with ApiClient(configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply_text)]
                            )
                        )
            except Exception as e:
                print(f"Error processing completion: {e}")
            finally:
                db.close()
    elif group_id:
        # 協力会社グループIDを取得するためのアナウンス（初回設定用）
        if "グループIDを確認" in received_text:
            reply_text = f"このグループのIDは以下です:\n{group_id}\n\nHubCargoの管理画面から、このIDを協力会社のLINEグループIDとして登録してください。"
            from linebot.v3.messaging import ReplyMessageRequest
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )

from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err = traceback.format_exc()
    return JSONResponse(status_code=500, content={"message": "Internal Crash", "trace": err})
