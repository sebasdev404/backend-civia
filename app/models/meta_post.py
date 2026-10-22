from sqlalchemy import Column, String, Text, Integer, DateTime, func
from app.core.database import Base

class MetaPost(Base):
    __tablename__ = "meta_posts"

    id = Column(String(100), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    cover_image = Column(Text, nullable=True)
    media_type = Column(String(50), default="image")
    permalink_url = Column(Text, nullable=True)
    created_time = Column(String(50), nullable=True)
    published_at = Column(String(100), nullable=False)
    month_key = Column(String(50), nullable=True)
    total_comments = Column(Integer, default=0)
    cases_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    source = Column(String(50), default="Facebook")
    raw_comments_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

