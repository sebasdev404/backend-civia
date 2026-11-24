from sqlalchemy import Column, String, Text, DateTime, Integer, func
from app.core.database import Base


class PublicationSource(Base):
    __tablename__ = "publication_sources"
    id = Column(String(80), primary_key=True)
    name = Column(String(160), nullable=False)
    url = Column(Text, nullable=False)
    graph_node = Column(String(160), nullable=True)
    status = Column(String(40), nullable=False, default="not_checked")
    detail = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), nullable=True)


class ObservedPost(Base):
    __tablename__ = "observed_posts"
    id = Column(String(150), primary_key=True)
    source_id = Column(String(80), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    cover_image = Column(Text, nullable=True)
    media_type = Column(String(40), nullable=True)
    permalink_url = Column(Text, nullable=True)
    created_time = Column(String(80), nullable=True, index=True)
    total_comments = Column(Integer, nullable=True)
    raw_comments_json = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PublicationSnapshot(Base):
    __tablename__ = "publication_snapshots"
    post_id = Column(String(150), primary_key=True)
    likes_count = Column(Integer, nullable=True)
    reactions_count = Column(Integer, nullable=True)
    shares_count = Column(Integer, nullable=True)
    reactions_json = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="not_checked")
    detail = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MetaSyncJob(Base):
    __tablename__ = "meta_sync_jobs"
    id = Column(String(36), primary_key=True)
    active_key = Column(String(200), unique=True, nullable=True)
    scope = Column(String(200), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued")
    progress_json = Column(Text, nullable=False, default="{}")
    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
