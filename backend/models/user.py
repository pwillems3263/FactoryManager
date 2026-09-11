import hashlib
import os
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from database import Base


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    h, _ = hash_password(password, salt)
    return h == hashed


hash_pin   = hash_password
verify_pin = verify_password


class User(Base):
    __tablename__ = "user"

    id_user       = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(100), nullable=False, unique=True)
    full_name     = Column(String(200), nullable=True)
    password_hash = Column(String(64),  nullable=False)
    password_salt = Column(String(32),  nullable=False)
    pin_hash             = Column(String(64),  nullable=True)
    pin_salt             = Column(String(32),  nullable=True)
    kiosk_blocked_until  = Column(DateTime,    nullable=True)
    niveau        = Column(Integer, nullable=False, default=1)
    actif         = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime, server_default=func.now())

    NIVEAU_LABELS = {1: "Operator", 2: "Coordinator", 3: "Manager", 4: "Administrator"}
    NIVEAU_COLORS = {1: "#27ae60", 2: "#3498db", 3: "#e67e22", 4: "#e74c3c"}

    def niveau_label(self): return self.NIVEAU_LABELS.get(self.niveau, "Unknown")
    def niveau_color(self): return self.NIVEAU_COLORS.get(self.niveau, "#999")
    def has_pin(self): return bool(self.pin_hash and self.pin_salt)

    def is_kiosk_blocked(self):
        from datetime import datetime, timezone
        if not self.kiosk_blocked_until: return False
        bu = self.kiosk_blocked_until
        if bu.tzinfo is None: bu = bu.replace(tzinfo=timezone.utc)
        return bu > datetime.now(timezone.utc)

    def can(self, action: str) -> bool:
        perms = {
            # Level 1 — Operator
            "production":      self.niveau >= 1,
            "time_tracking":   self.niveau >= 1,
            # Level 2 — Coordinator and above
            "dashboard":       self.niveau >= 2,
            "planning":        self.niveau >= 2,
            "scrap":           self.niveau >= 2,
            "components":      self.niveau >= 2,
            "assemblies":      self.niveau >= 2,
            "orders":          self.niveau >= 2,
            "work_orders":     self.niveau >= 2,
            "production_track": self.niveau >= 2,
            # Level 3 — Manager and above
            "machines":        self.niveau >= 3,
            "materials":       self.niveau >= 3,
            "services":        self.niveau >= 3,
            "external_parts":  self.niveau >= 3,
            # Level 4 — Administrator only
            "users":           self.niveau >= 4,
        }
        return perms.get(action, False)
