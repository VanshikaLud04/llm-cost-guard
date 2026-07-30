from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
import time

Base = declarative_base()

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    plan_tier = Column(String, default="free")

    users = relationship("User", back_populates="organization")
    policies = relationship("Policy", back_populates="organization")

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    role = Column(String, default="member")
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)

    organization = relationship("Organization", back_populates="users")
    api_keys = relationship("ApiKey", back_populates="user")

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(Float, default=time.time)
    revoked_at = Column(Float, nullable=True)

    user = relationship("User", back_populates="api_keys")

class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    role = Column(String, nullable=True)
    allowed_models = Column(ARRAY(String), nullable=False)
    token_limits = Column(JSONB, nullable=False)
    priority = Column(Integer, default=0)

    organization = relationship("Organization", back_populates="policies")

class UsageRecord(Base):
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    org_id = Column(String, ForeignKey("organizations.id"), index=True, nullable=True)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=False, default=0.0)
    timestamp = Column(Float, index=True, default=time.time)

# We use a string fallback for Vector if pgvector is not installed yet
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_TYPE = Vector(384)
except ImportError:
    VECTOR_TYPE = String

class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id = Column(String, primary_key=True, index=True)
    org_id = Column(String, ForeignKey("organizations.id"), index=True, nullable=False)
    prompt = Column(String, nullable=False)
    prompt_embedding = Column(VECTOR_TYPE, nullable=True)
    response = Column(String, nullable=False)
    model = Column(String, nullable=True)
    ttl_expires_at = Column(Float, nullable=True)
    hit_count = Column(Integer, default=0)
