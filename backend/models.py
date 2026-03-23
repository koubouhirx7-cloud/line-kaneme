from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, index=True)
    line_group_id = Column(String, nullable=True)
    icon_emoji = Column(String, default="🏢")
    is_active = Column(Boolean, default=True)
