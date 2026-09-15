"""
backend/models/settings.py
---------------------------
Simple key/value store for application-wide settings that aren't tied to
a specific business object (e.g. where drawing/plan files are stored).
"""
from sqlalchemy import Column, String
from database import Base


class AppSetting(Base):
    __tablename__ = "app_setting"

    key   = Column(String(100), primary_key=True)
    value = Column(String(2000), nullable=True)
