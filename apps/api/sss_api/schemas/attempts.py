"""Strict install-attempt schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sss_core import Decision

from sss_api.services.attempts import InstallAttempt, new_attempt


class InstallAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1, max_length=128)
    manager: str = Field(min_length=1, max_length=32)
    arguments: tuple[str, ...] = Field(min_length=1, max_length=64)
    agent_family: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    decision: Decision
    child_started: bool

    @model_validator(mode="after")
    def block_cannot_start_child(self) -> InstallAttemptRequest:
        if self.decision is Decision.BLOCK and self.child_started:
            raise ValueError("a blocked attempt cannot start a child process")
        return self

    def to_domain(self) -> InstallAttempt:
        return new_attempt(
            decision_id=self.decision_id,
            manager=self.manager,
            arguments=self.arguments,
            agent_family=self.agent_family,
            project_id=self.project_id,
            decision=self.decision,
            child_started=self.child_started,
        )


class InstallAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    manager: str
    arguments: tuple[str, ...]
    agent_family: str
    project_id: str
    decision: Decision
    child_started: bool
    attempted_at: datetime

    @classmethod
    def from_domain(cls, attempt: InstallAttempt) -> InstallAttemptResponse:
        return cls(
            decision_id=attempt.decision_id,
            manager=attempt.manager,
            arguments=attempt.arguments,
            agent_family=attempt.agent_family,
            project_id=attempt.project_id,
            decision=attempt.decision,
            child_started=attempt.child_started,
            attempted_at=attempt.attempted_at,
        )


class InstallAttemptListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[InstallAttemptResponse, ...]
