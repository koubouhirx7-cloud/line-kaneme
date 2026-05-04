from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from database import Base

class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(String, primary_key=True, index=True)
    customer_name = Column(String, index=True)
    phone_number = Column(String)
    pickup_location = Column(String, nullable=True)
    delivery_location = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    status = Column(String, default="received")  # received, dispatched, completed
    dispatched_to_partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True)
    reminder_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, index=True)
    line_group_id = Column(String, nullable=True)
    icon_emoji = Column(String, default="🏢")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

class SystemErrorLog(Base):
    __tablename__ = "system_error_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    method = Column(String, nullable=True)       # GET / POST など
    url = Column(Text, nullable=True)            # リクエストURL
    error_type = Column(String, nullable=True)   # 例外クラス名
    error_message = Column(Text, nullable=True)  # 例外メッセージ
    traceback_text = Column(Text, nullable=True) # スタックトレース
    dismissed = Column(Boolean, default=False)   # 既読フラグ
    discord_notified = Column(Boolean, default=False)  # Discord通知済みフラグ
