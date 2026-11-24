from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CommentReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    post_id: Identifier
    comment_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class ConsolidateComments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comments: list[CommentReference] = Field(min_length=1, max_length=100)
    target_case_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=255)] | None = None
