import os

with open("backend/main.py", "r") as f:
    content = f.read()

# Make sure not to append multiple times
if "/api/cron/reminders" not in content:
    reminder_code = """

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
def check_reminders(db: Session = Depends(get_db)):
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

"""

    # We insert it right before the webhook endpoint or just at the end.
    # Searching for `# --- Webhook Endpoint ---`
    if "# --- Webhook Endpoint ---" in content:
        content = content.replace("# --- Webhook Endpoint ---", reminder_code + "\n\n# --- Webhook Endpoint ---")
    else:
        content += reminder_code

    with open("backend/main.py", "w") as f:
        f.write(content)

