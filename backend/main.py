from fastapi import FastAPI, Depends, HTTPException, status, Request, Header, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import secrets
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
import traceback
import requests as http_requests
from datetime import datetime, timezone

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
ADMIN_LINE_USER_ID = os.getenv("ADMIN_LINE_USER_ID", "")  # 管理者のLINEユーザーIDまたはグループID
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
CLIENT_DISCORD_WEBHOOK_URL = os.getenv("CLIENT_DISCORD_WEBHOOK_URL", "")  # 顧客向け問い合わせ通知用

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Create DB tables

models.Base.metadata.create_all(bind=engine)

from sqlalchemy import text
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE inquiries ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE"))
except Exception:
    pass

try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE partners ADD COLUMN sort_order INTEGER DEFAULT 0"))
except Exception:
    pass


app = FastAPI(title="HubCargo Delivery API")

# Setup CORS - 本番環境のURLのみ許可
ALLOWED_ORIGINS = [
    "https://line-kaneme.vercel.app",  # 本番Vercel
    "http://localhost:3000",            # ローカル開発
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# --- HTML Serving Code ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Point to project root

def get_html_content(filename: str) -> str:
    filepath = os.path.join(BASE_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading {filename}: {e}")
        return "<h1>Error loading page</h1>"

import base64
security = HTTPBasic()

def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    admin_user = os.getenv("ADMIN_USER")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_user or not admin_password:
        logging.error("ADMIN_USER or ADMIN_PASSWORD environment variables are not set!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error. Authentication unavailable."
        )

    correct_username = secrets.compare_digest(credentials.username, admin_user)
    correct_password = secrets.compare_digest(credentials.password, admin_password)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic realm=\"HubCargo Admin Dashboard\""},
        )
    return credentials.username

def inject_admin_token(html: str, credentials: HTTPBasicCredentials) -> str:
    """Inject auth token + fetch interceptor into the HTML page."""
    token = base64.b64encode(f"{credentials.username}:{credentials.password}".encode()).decode()
    script = (
        '<script>'
        f'window.__ADMIN_TOKEN="Basic {token}";'
        'const _fetch=window.fetch;'
        'window.fetch=function(url,opts){'
        'opts=opts||{};'
        'if(window.__ADMIN_TOKEN&&typeof url==="string"&&url.includes("/api/")){'
        'opts.headers=Object.assign({},opts.headers,{"Authorization":window.__ADMIN_TOKEN});'
        '}return _fetch.call(this,url,opts);};'
        '</script>'
    )
    return html.replace('</head>', script + '\n</head>', 1)

@app.get("/", response_class=HTMLResponse)
def serve_index_dashboard(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    authenticate_admin(credentials)
    return inject_admin_token(get_html_content("index.html"), credentials)

@app.get("/index.html", response_class=HTMLResponse)
def serve_index_dashboard_named(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    authenticate_admin(credentials)
    return inject_admin_token(get_html_content("index.html"), credentials)


@app.get("/admin.html", response_class=HTMLResponse)
def serve_admin_dashboard(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    authenticate_admin(credentials)
    return inject_admin_token(get_html_content("admin.html"), credentials)

@app.get("/system-admin.html", response_class=HTMLResponse)
def serve_system_admin(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    authenticate_admin(credentials)
    return inject_admin_token(get_html_content("system_admin.html"), credentials)

# --- Inquiry Endpoints ---

@app.post("/api/inquiries", response_model=schemas.InquiryResponse, status_code=status.HTTP_201_CREATED)
def create_inquiry(inquiry: schemas.InquiryCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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

    # 管理者へのLINE通知（ADMIN_LINE_USER_IDが設定されている場合のみ）
    if ADMIN_LINE_USER_ID and LINE_CHANNEL_ACCESS_TOKEN:
        try:
            background_tasks.add_task(
                send_admin_new_inquiry_notification,
                db_inquiry.id,
                db_inquiry.customer_name,
                db_inquiry.phone_number,
                db_inquiry.pickup_location,
                db_inquiry.delivery_location,
                db_inquiry.detail
            )
        except Exception as e:
            print(f"Failed to schedule admin notification: {e}")

    # 顧客向けDiscord通知
    if CLIENT_DISCORD_WEBHOOK_URL:
        try:
            background_tasks.add_task(
                send_client_discord_new_inquiry,
                db_inquiry.id,
                db_inquiry.customer_name,
                db_inquiry.phone_number,
                db_inquiry.pickup_location,
                db_inquiry.delivery_location,
                db_inquiry.detail
            )
        except Exception as e:
            print(f"Failed to schedule client Discord notification: {e}")

    return db_inquiry

@app.get("/api/inquiries", response_model=List[schemas.InquiryResponse])
def get_inquiries(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    inquiries = db.query(models.Inquiry).order_by(models.Inquiry.created_at.desc()).offset(skip).limit(limit).all()
    return inquiries

@app.get("/api/reports/completed", response_model=List[schemas.InquiryResponse])
def get_completed_reports(start_date: str, end_date: str, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    try:
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
        
    inquiries = db.query(models.Inquiry).filter(
        models.Inquiry.status == "completed",
        models.Inquiry.updated_at >= start_dt,
        models.Inquiry.updated_at <= end_dt
    ).order_by(models.Inquiry.updated_at.desc()).all()
    
    return inquiries

@app.delete("/api/inquiries/{inquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inquiry(inquiry_id: str, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    inquiry = db.query(models.Inquiry).filter(models.Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    db.delete(inquiry)
    db.commit()
    return {"ok": True}

@app.post("/api/inquiries/{inquiry_id}/dispatch", response_model=schemas.InquiryResponse)
def dispatch_inquiry(inquiry_id: str, request_data: schemas.DispatchRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
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
    
    # Send LINE message to partner's line_group_id (Must be synchronous on Vercel)
    line_status = "skipped"
    line_detail = ""
    
    if not LINE_CHANNEL_ACCESS_TOKEN:
        line_detail = "LINE_CHANNEL_ACCESS_TOKEN is empty"
        logging.warning(f"[DISPATCH] LINE送信スキップ: トークン未設定 (inquiry={inquiry_id})")
    elif not partner.line_group_id:
        line_detail = f"partner {partner.id} ({partner.name}) has no line_group_id"
        logging.warning(f"[DISPATCH] LINE送信スキップ: line_group_id未設定 (inquiry={inquiry_id}, partner={partner.name})")
    else:
        try:
            logging.info(f"[DISPATCH] LINE送信開始: to={partner.line_group_id}, inquiry={inquiry_id}, partner={partner.name}")
            send_line_push_message(partner.line_group_id, inquiry, partner)
            line_status = "sent"
            line_detail = f"sent to {partner.name} ({partner.line_group_id})"
            logging.info(f"[DISPATCH] LINE送信成功: {line_detail}")
        except Exception as e:
            line_status = "failed"
            line_detail = f"{type(e).__name__}: {str(e)}"
            logging.error(f"[DISPATCH] LINE送信失敗: {line_detail} (inquiry={inquiry_id}, to={partner.line_group_id})")
    
    # レスポンスにLINE送信状態をヘッダーで付与（デバッグ用）
    from fastapi.responses import JSONResponse
    response_data = schemas.InquiryResponse.model_validate(inquiry).model_dump()
    response_data["_line_status"] = line_status
    response_data["_line_detail"] = line_detail
    return JSONResponse(content=jsonable_encoder(response_data))

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
                        "text": f"☎ {inquiry.phone_number or '番号なし'} (タップで発信)",
                        "color": "#2764E5",
                        "weight": "bold",
                        "size": "lg",
                        "margin": "md",
                        "action": {
                            "type": "uri",
                            "label": "電話をかける",
                            "uri": f"tel:{(inquiry.phone_number or '0000000000').replace('-', '')}"
                        }
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "ご住所:", "color": "#777777", "size": "sm", "flex": 2},
                                    {"type": "text", "text": f"{inquiry.pickup_location or '未入力'}", "wrap": True, "color": "#111111", "size": "sm", "flex": 5}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "お荷物番号:", "color": "#777777", "size": "sm", "flex": 2},
                                    {"type": "text", "text": f"{inquiry.delivery_location or '未入力'}", "wrap": True, "color": "#111111", "size": "sm", "flex": 5}
                                ]
                            },
                            {
                                "type": "text",
                                "text": f"詳細:\n{inquiry.detail}",
                                "wrap": True,
                                "color": "#111111",
                                "size": "sm",
                                "margin": "lg"
                            }
                        ],
                        "backgroundColor": "#f4f6f9",
                        "paddingAll": "16px",
                        "cornerRadius": "8px",
                        "borderColor": "#d9e2ec",
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
                            "type": "uri",
                            "label": "✔ 完了報告する",
                            "uri": f"https://line-kaneme.vercel.app/complete.html?id={inquiry.id}"
                        },
                        "color": "#06C755",
                        "style": "primary"
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
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to send LINE message: {str(e)}")

from pydantic import BaseModel
from typing import Optional

class CompletePayload(BaseModel):
    note: Optional[str] = None

def send_admin_new_inquiry_notification(inquiry_id: str, customer_name: str, phone_number: str, pickup_location: str, delivery_location: str, detail: str):
    """顧客から新しいお問い合わせが届いた際に管理者へLINE通知を送る"""
    try:
        flex_dict = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [{"type": "text", "text": "🔔 新規お問い合わせ", "color": "#ffffff", "weight": "bold", "size": "md"}],
                "backgroundColor": "#2764E5",
                "paddingTop": "12px",
                "paddingBottom": "12px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": f"{customer_name} 様", "weight": "bold", "size": "lg", "wrap": True},
                    {"type": "text", "text": f"📞 {phone_number or '番号なし'}", "size": "sm", "color": "#2764E5"},
                    {"type": "text", "text": f"受付番号: {inquiry_id}", "size": "sm", "color": "#888888"},
                    {
                        "type": "box", "layout": "vertical", "margin": "md",
                        "backgroundColor": "#f4f6f9", "paddingAll": "12px", "cornerRadius": "8px",
                        "contents": [
                            {"type": "text", "text": f"住所: {pickup_location or '未入力'}", "size": "sm", "wrap": True, "color": "#333333"},
                            {"type": "text", "text": f"内容: {(detail or '')[:80]}", "size": "sm", "wrap": True, "color": "#555555", "margin": "sm"}
                        ]
                    }
                ],
                "paddingAll": "20px"
            },
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [{
                    "type": "button",
                    "action": {"type": "uri", "label": "管理画面で確認する", "uri": "https://line-kaneme.vercel.app/"},
                    "color": "#2764E5", "style": "primary"
                }],
                "paddingAll": "16px"
            }
        }
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            flex_container = FlexContainer.from_dict(flex_dict)
            flex_message = FlexMessage(
                alt_text=f"🔔 新規お問い合わせ: {customer_name} 様",
                contents=flex_container
            )
            line_bot_api.push_message(
                PushMessageRequest(to=ADMIN_LINE_USER_ID, messages=[flex_message])
            )
        print(f"Admin notification sent for {inquiry_id}")
    except Exception as e:
        print(f"Failed to send admin notification: {e}")

def send_completion_push_message(to_id: str, inquiry: models.Inquiry, note: str):
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            
            note_text = note if note else "特になし"
            flex_dict = {
                "type": "bubble",
                "size": "kilo",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "✅ 報告受理完了", "color": "#ffffff", "weight": "bold", "size": "md"}
                    ],
                    "backgroundColor": "#29a329",
                    "paddingTop": "12px",
                    "paddingBottom": "12px"
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {"type": "text", "text": "完了報告を受け付けました！\nありがとうございます。", "weight": "bold", "size": "md", "wrap": True, "color": "#111111"},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "margin": "lg",
                            "contents": [
                                {"type": "text", "text": f"受付番号: {inquiry.id}", "size": "sm", "color": "#666666"},
                                {"type": "text", "text": f"顧客名: {inquiry.customer_name} 様", "size": "sm", "color": "#666666", "wrap": True},
                                {"type": "text", "text": f"特記事項: {note_text}", "size": "sm", "color": "#666666", "wrap": True}
                            ],
                            "backgroundColor": "#f4f6f9",
                            "paddingAll": "12px",
                            "cornerRadius": "8px"
                        }
                    ],
                    "paddingAll": "20px"
                }
            }
            
            line_bot_api.push_message(
                PushMessageRequest(
                    to=to_id,
                    messages=[FlexMessage(alt_text=f"✅ 報告受理: {inquiry.id}", contents=FlexContainer.from_dict(flex_dict))]
                )
            )
    except Exception as e:
        print(f"Failed to send complete push message: {e}")

@app.post("/api/inquiries/{inquiry_id}/complete", response_model=schemas.InquiryResponse)
def complete_inquiry(inquiry_id: str, background_tasks: BackgroundTasks, payload: CompletePayload = None, db: Session = Depends(get_db)):
    # This endpoint can be used by the webhook or manually to mark as completed
    inquiry = db.query(models.Inquiry).filter(models.Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
        
    if payload and payload.note:
        if inquiry.detail is None:
            inquiry.detail = f"【完了報告】\n{payload.note}"
        else:
            inquiry.detail += f"\n\n【完了報告】\n{payload.note}"
        
    inquiry.status = "completed"

    # --- バグ修正 ---
    # DBコミット前に必要な値をプリミティブとして確保する。
    # SQLAlchemyオブジェクトをそのままバックグラウンドタスクに渡すと、
    # コミット後にセッションが変わりデータが別の問い合わせのものに差し替わる恐れがある。
    partner_group_id = None
    note_val = None
    # inquiry情報もプリミティブで確保
    snap = {
        "id": inquiry.id,
        "customer_name": inquiry.customer_name,
    }
    if inquiry.dispatched_to_partner_id:
        partner = db.query(models.Partner).filter(models.Partner.id == inquiry.dispatched_to_partner_id).first()
        if partner and partner.line_group_id and os.getenv("LINE_CHANNEL_ACCESS_TOKEN"):
            partner_group_id = partner.line_group_id  # ← ここでスナップショット
            note_val = (payload.note if payload and payload.note else "特になし")

    db.commit()
    db.refresh(inquiry)

    # コミット完了後にバックグラウンドタスクを登録（スナップショット済みの値を使用）
    if partner_group_id:
        background_tasks.add_task(send_completion_push_message, partner_group_id, inquiry, note_val)

    return inquiry

# --- Partner Endpoints ---

@app.post("/api/partners", response_model=schemas.PartnerResponse, status_code=status.HTTP_201_CREATED)
def create_partner(partner: schemas.PartnerCreate, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    db_partner = models.Partner(**partner.dict())
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    return db_partner

@app.get("/api/partners", response_model=List[schemas.PartnerResponse])
def get_partners(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    partners = db.query(models.Partner).filter(models.Partner.is_active == True).order_by(models.Partner.sort_order.asc(), models.Partner.id.asc()).offset(skip).limit(limit).all()
    return partners

@app.put("/api/partners/reorder")
def reorder_partners(payload: List[dict], db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    for item in payload:
        part_id = item.get("id")
        sort_order = item.get("sort_order")
        if part_id is not None and sort_order is not None:
            partner = db.query(models.Partner).filter(models.Partner.id == part_id).first()
            if partner:
                partner.sort_order = sort_order
    db.commit()
    return {"ok": True}

@app.delete("/api/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner(partner_id: int, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    partner = db.query(models.Partner).filter(models.Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # Soft delete
    partner.is_active = False
    db.commit()
    return {"ok": True}


@app.put("/api/partners/{partner_id}", response_model=schemas.PartnerResponse)
def update_partner(partner_id: int, partner: schemas.PartnerCreate, db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    db_partner = db.query(models.Partner).filter(models.Partner.id == partner_id).first()
    if not db_partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    db_partner.name = partner.name
    if partner.line_group_id is not None:
        db_partner.line_group_id = partner.line_group_id
    db.commit()
    db.refresh(db_partner)
    return db_partner

# --- Cron / Polling Reminders ---

from datetime import datetime, timedelta, timezone

def send_reminder_line_message(to_id: str, inquiry: models.Inquiry):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        reply_flex_dict = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "⚠️ 状況確認のお願い",
                        "color": "#ffffff",
                        "weight": "bold",
                        "size": "md"
                    }
                ],
                "backgroundColor": "#ffb822",
                "paddingTop": "12px",
                "paddingBottom": "12px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "手配から30分経過しました！状況はいかがでしょうか？",
                        "weight": "bold",
                        "size": "md",
                        "wrap": True,
                        "color": "#111111"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "margin": "lg",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"受付番号: {inquiry.id}",
                                "size": "sm",
                                "color": "#666666"
                            },
                            {
                                "type": "text",
                                "text": f"顧客名: {inquiry.customer_name} 様",
                                "size": "sm",
                                "color": "#666666",
                                "wrap": True
                            }
                        ],
                        "backgroundColor": "#fff4de",
                        "paddingAll": "12px",
                        "cornerRadius": "8px"
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
                            "type": "uri",
                            "label": "✔ 完了報告する",
                            "uri": f"https://line-kaneme.vercel.app/complete.html?id={inquiry.id}"
                        },
                        "color": "#ffb822",
                        "style": "primary"
                    }
                ],
                "paddingAll": "20px"
            }
        }
        
        try:
            flex_container = FlexContainer.from_dict(reply_flex_dict)
            flex_message = FlexMessage(alt_text=f"⚠️ {inquiry.customer_name}様 の件について: 状況確認のお願い", contents=flex_container)
            
            line_bot_api.push_message(
                PushMessageRequest(
                    to=to_id,
                    messages=[flex_message]
                )
            )
        except Exception as e:
            print(f"Failed to send LINE Reminder Flex message: {e}")

@app.get("/api/cron/reminders")
def check_reminders(db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return {"status": "skipped", "reason": "no token"}
        
    thirty_mins_ago = datetime.utcnow() - timedelta(minutes=30)
    
    overdue_inquiries = db.query(models.Inquiry).filter(
        models.Inquiry.status == "dispatched",
        models.Inquiry.reminder_sent == False
    ).all()
    
    count = 0
    for inquiry in overdue_inquiries:
        # Check time condition. Since updated_at is timezone-aware if created correctly, handling safely:
        if inquiry.updated_at:
            # naive comparison assuming UTC, or just simplistic comparison
            # SQLAlchemy datetime might be naive or aware.
            up_time = inquiry.updated_at.replace(tzinfo=None)
            if up_time < thirty_mins_ago:
                partner = db.query(models.Partner).filter(models.Partner.id == inquiry.dispatched_to_partner_id).first()
                if partner and partner.line_group_id:
                    send_reminder_line_message(partner.line_group_id, inquiry)
                    inquiry.reminder_sent = True
                    count += 1

    if count > 0:
        db.commit()

    return {"status": "ok", "reminders_sent": count}



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
                    
                    # Reply back via Messaging API using FlexMessage
                    reply_flex_dict = {
                        "type": "bubble",
                        "size": "kilo",
                        "header": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "✅ 報告受理完了",
                                    "color": "#ffffff",
                                    "weight": "bold",
                                    "size": "md"
                                }
                            ],
                            "backgroundColor": "#29a329",
                            "paddingTop": "12px",
                            "paddingBottom": "12px"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "md",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "連絡完了報告を受け付けました！\nありがとうございます。",
                                    "weight": "bold",
                                    "size": "md",
                                    "wrap": True,
                                    "color": "#111111"
                                },
                                {
                                    "type": "box",
                                    "layout": "vertical",
                                    "spacing": "sm",
                                    "margin": "lg",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": f"受付番号: {inquiry_id}",
                                            "size": "sm",
                                            "color": "#666666"
                                        },
                                        {
                                            "type": "text",
                                            "text": f"顧客名: {inquiry.customer_name} 様",
                                            "size": "sm",
                                            "color": "#666666",
                                            "wrap": True
                                        }
                                    ],
                                    "backgroundColor": "#f4f6f9",
                                    "paddingAll": "12px",
                                    "cornerRadius": "8px"
                                }
                            ],
                            "paddingAll": "20px"
                        }
                    }
                    
                    from linebot.v3.messaging import ReplyMessageRequest, FlexMessage, FlexContainer
                    with ApiClient(configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[FlexMessage(alt_text=f"✅ 報告受理: {inquiry_id}", contents=FlexContainer.from_dict(reply_flex_dict))]
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
import logging

logger = logging.getLogger("hubcargo")

# ───────────────────────────────────────────
# Discord エラー通知
# ───────────────────────────────────────────

def send_client_discord_new_inquiry(inquiry_id: str, customer_name: str, phone_number: str, pickup_location: str, delivery_location: str, detail: str) -> bool:
    """顧客のDiscordサーバーに新規問い合わせ通知を送信する"""
    if not CLIENT_DISCORD_WEBHOOK_URL:
        return False
    try:
        jst_now = datetime.now(timezone.utc).astimezone()
        timestamp_str = jst_now.strftime("%Y/%m/%d %H:%M")

        embed = {
            "title": "📦 新しい配送のお問い合わせ",
            "color": 0x2764E5,  # HubCargoブランドカラー
            "fields": [
                {"name": "🆔 受付番号", "value": f"`{inquiry_id}`", "inline": True},
                {"name": "⏰ 受付時刻", "value": timestamp_str, "inline": True},
                {"name": "👤 お客様名", "value": customer_name or "未入力", "inline": False},
                {"name": "📞 電話番号", "value": phone_number or "未入力", "inline": True},
                {"name": "📍 ご住所", "value": pickup_location or "未入力", "inline": True},
                {"name": "📋 お荷物番号", "value": delivery_location or "未入力", "inline": False},
                {"name": "💬 詳細", "value": (detail or "なし")[:500], "inline": False},
            ],
            "footer": {"text": "HubCargo 配送管理システム"},
            "timestamp": jst_now.isoformat(),
        }
        payload = {
            "content": "🔔 **新しいお問い合わせが届きました！** 管理画面をご確認ください。",
            "embeds": [embed]
        }
        resp = http_requests.post(CLIENT_DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        if resp.status_code in (200, 204):
            print(f"Client Discord notification sent for {inquiry_id}")
            return True
        else:
            print(f"Client Discord notification failed: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"Client Discord notification error: {e}")
        return False


def send_discord_error_notification(method: str, url: str, error_type: str, error_message: str, tb_text: str) -> bool:
    """Discord Webhook にエラー Embed を送信し、成功したら True を返す"""
    if not DISCORD_WEBHOOK_URL:
        return False
    try:
        jst_now = datetime.now(timezone.utc).astimezone()
        timestamp_str = jst_now.strftime("%Y-%m-%d %H:%M:%S JST")

        # スタックトレースは先頭1500文字まで
        tb_short = tb_text[-1500:] if len(tb_text) > 1500 else tb_text

        embed = {
            "title": "🚨 システムエラー検知",
            "color": 0xFF3333,
            "fields": [
                {"name": "エラー種別", "value": f"`{error_type}`", "inline": True},
                {"name": "発生箇所", "value": f"`{method} {url}`", "inline": True},
                {"name": "時刻", "value": timestamp_str, "inline": False},
                {"name": "メッセージ", "value": f"```{error_message[:500]}```", "inline": False},
                {"name": "スタックトレース", "value": f"```python\n{tb_short}\n```", "inline": False},
            ],
            "footer": {"text": "HubCargo System Monitor"},
            "timestamp": jst_now.isoformat(),
        }
        payload = {"embeds": [embed]}
        resp = http_requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.warning(f"Discord notification failed: {e}")
        return False


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb_text = traceback.format_exc()
    error_type = type(exc).__name__
    error_message = str(exc)
    method = request.method
    url_str = str(request.url)

    # サーバーログに記録
    logger.error(f"Unhandled exception on {method} {url_str}: {exc}", exc_info=True)

    # DBにエラーログを保存
    discord_ok = False
    try:
        from database import SessionLocal
        err_db = SessionLocal()
        try:
            err_log = models.SystemErrorLog(
                method=method,
                url=url_str,
                error_type=error_type,
                error_message=error_message,
                traceback_text=tb_text,
                dismissed=False,
                discord_notified=False,
            )
            err_db.add(err_log)
            err_db.commit()

            # Discord 通知
            discord_ok = send_discord_error_notification(method, url_str, error_type, error_message, tb_text)
            if discord_ok:
                err_log.discord_notified = True
                err_db.commit()
        finally:
            err_db.close()
    except Exception as log_err:
        logger.error(f"Failed to log error to DB: {log_err}")
        # DBに保存できなくても Discord には送る
        discord_ok = send_discord_error_notification(method, url_str, error_type, error_message, tb_text)

    return JSONResponse(
        status_code=500,
        content={"message": "内部エラーが発生しました。しばらく待ってから再試行してください。"}
    )


# ───────────────────────────────────────────
# システム管理 API
# ───────────────────────────────────────────

@app.get("/api/system/health")
def system_health(db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    """DBとLINE APIの基本的な接続確認"""
    db_ok = False
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    line_ok = bool(LINE_CHANNEL_ACCESS_TOKEN)
    discord_ok = bool(DISCORD_WEBHOOK_URL)
    client_discord_ok = bool(CLIENT_DISCORD_WEBHOOK_URL)

    undismissed_count = 0
    try:
        undismissed_count = db.query(models.SystemErrorLog).filter(
            models.SystemErrorLog.dismissed == False
        ).count()
    except Exception:
        pass

    return {
        "db": db_ok,
        "line_api": line_ok,
        "discord_webhook": discord_ok,
        "client_discord_webhook": client_discord_ok,
        "undismissed_errors": undismissed_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/system/errors")
def get_error_logs(
    skip: int = 0,
    limit: int = 50,
    show_dismissed: bool = False,
    db: Session = Depends(get_db),
    _ = Depends(authenticate_admin)
):
    """エラーログ一覧を返す（新しい順）"""
    query = db.query(models.SystemErrorLog)
    if not show_dismissed:
        query = query.filter(models.SystemErrorLog.dismissed == False)
    logs = query.order_by(models.SystemErrorLog.timestamp.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "method": log.method,
            "url": log.url,
            "error_type": log.error_type,
            "error_message": log.error_message,
            "traceback_text": log.traceback_text,
            "dismissed": log.dismissed,
            "discord_notified": log.discord_notified,
        }
        for log in logs
    ]


@app.post("/api/system/errors/{error_id}/dismiss")
def dismiss_error_log(
    error_id: int,
    db: Session = Depends(get_db),
    _ = Depends(authenticate_admin)
):
    """エラーログを既読にする"""
    log = db.query(models.SystemErrorLog).filter(models.SystemErrorLog.id == error_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Error log not found")
    log.dismissed = True
    db.commit()
    return {"ok": True}


@app.post("/api/system/errors/dismiss-all")
def dismiss_all_error_logs(db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    """全エラーログを既読にする"""
    db.query(models.SystemErrorLog).filter(
        models.SystemErrorLog.dismissed == False
    ).update({"dismissed": True})
    db.commit()
    return {"ok": True}


@app.post("/api/system/test-discord")
def test_discord_notification(_ = Depends(authenticate_admin)):
    """Discord Webhook の疎通テスト"""
    ok = send_discord_error_notification(
        method="TEST",
        url="/api/system/test-discord",
        error_type="TestNotification",
        error_message="これはテスト通知です。Discord Webhook が正常に動作しています。",
        tb_text="テスト通知のため、スタックトレースはありません。"
    )
    if ok:
        return {"ok": True, "message": "Discord 通知を送信しました ✅"}
    else:
        raise HTTPException(status_code=500, detail="Discord 通知の送信に失敗しました。Webhook URL を確認してください。")


@app.post("/api/system/test-error")
def trigger_test_error(_ = Depends(authenticate_admin)):
    """意図的にエラーを発生させて通知フローのテストを行う"""
    raise ValueError("これはシステム管理者によって手動でトリガーされたテストエラーです。")


@app.post("/api/system/test-line")
def test_line_push(db: Session = Depends(get_db), _ = Depends(authenticate_admin)):
    """LINE送信の全フェーズを診断する"""
    results = {
        "step1_token": False,
        "step2_partners": [],
        "step3_sdk_init": False,
        "step4_send_result": None,
    }
    
    # Step 1: トークン確認
    token = LINE_CHANNEL_ACCESS_TOKEN
    results["step1_token"] = bool(token)
    results["step1_token_length"] = len(token) if token else 0
    results["step1_token_preview"] = (token[:10] + "...") if token and len(token) > 10 else "(empty)"
    
    if not token:
        results["step4_send_result"] = "SKIP: トークンが空です"
        return results
    
    # Step 2: アクティブなパートナーとline_group_id
    partners = db.query(models.Partner).filter(models.Partner.is_active == True).all()
    for p in partners:
        results["step2_partners"].append({
            "id": p.id,
            "name": p.name,
            "line_group_id": p.line_group_id or "(NULL)",
            "has_group_id": bool(p.line_group_id),
        })
    
    # Step 3: SDK初期化テスト
    try:
        test_config = Configuration(access_token=token)
        with ApiClient(test_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            results["step3_sdk_init"] = True
    except Exception as e:
        results["step3_sdk_init"] = False
        results["step3_error"] = str(e)
        return results
    
    # Step 4: 最初のアクティブパートナーへテスト送信
    target = None
    for p in partners:
        if p.line_group_id:
            target = p
            break
    
    if not target:
        results["step4_send_result"] = "SKIP: line_group_idが設定されたアクティブパートナーがいません"
        return results
    
    try:
        with ApiClient(test_config) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=target.line_group_id,
                    messages=[TextMessage(text=f"🔧 LINE送信診断テスト\n送信先: {target.name}\nGroup ID: {target.line_group_id}\n時刻: {datetime.now(timezone.utc).isoformat()}")]
                )
            )
            results["step4_send_result"] = f"SUCCESS: {target.name} ({target.line_group_id}) に送信完了"
    except Exception as e:
        results["step4_send_result"] = f"FAIL: {type(e).__name__}: {str(e)}"
    
    return results
