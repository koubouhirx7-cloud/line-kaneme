from linebot.v3.messaging.models import FlexContainer
inquiry_id = "123"
customer_name = "test"
phone_number = "090-1234-5678"
pickup_location = "Tokyo"
delivery_location = "Osaka"
detail = "fragile"

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
                "text": f"{customer_name} 様",
                "weight": "bold",
                "size": "xl",
                "wrap": True,
                "margin": "md"
            },
            {
                "type": "text",
                "text": f"☎ {phone_number} (タップで発信)",
                "color": "#2764E5",
                "weight": "bold",
                "size": "lg",
                "margin": "md",
                "action": {
                    "type": "uri",
                    "label": "電話をかける",
                    "uri": f"tel:{phone_number.replace('-', '')}"
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
                            {"type": "text", "text": f"{pickup_location}", "wrap": True, "color": "#111111", "size": "sm", "flex": 5}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "spacing": "sm",
                        "contents": [
                            {"type": "text", "text": "お荷物番号:", "color": "#777777", "size": "sm", "flex": 2},
                            {"type": "text", "text": f"{delivery_location}", "wrap": True, "color": "#111111", "size": "sm", "flex": 5}
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"詳細:\n{detail}",
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
                    "uri": f"https://line-kaneme.vercel.app/complete.html?id={inquiry_id}"
                },
                "color": "#06C755",
                "style": "primary"
            }
        ],
        "paddingAll": "20px"
    }
}
try:
    c = FlexContainer.from_dict(flex_dict)
    print("Flex payload is valid!")
except Exception as e:
    print("Error:", e)

