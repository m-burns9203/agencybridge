# File: models.py
# Description: Defines validated request bodies and documented API responses.
# Author: Michael Burns <mdburnsjr@gmail.com>
# Created: 2026-10-08
# Last Modified: 2026-10-08 by Michael Burns
# Dependencies: pydantic, typing

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "medium", "high"]
ReferralStatus = Literal["pending", "accepted", "completed"]


class StrictRequest(BaseModel):
    """Reject unknown fields and strip whitespace before validating text."""

    # A client cannot quietly slip owner_agency_id into a create-case request.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CaseInput(StrictRequest):
    """Ownership comes from the demo user; clients supply only editable fields."""

    title: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=10, max_length=2000)
    priority: Priority


class CaseEdit(StrictRequest):
    """Only priority is editable in this small prototype."""

    priority: Priority


class ReferralInput(StrictRequest):
    to_agency_id: int = Field(gt=0)


class ReferralUpdate(StrictRequest):
    status: ReferralStatus


class AgencyResponse(BaseModel):
    id: int
    name: str


class UserResponse(BaseModel):
    id: int
    name: str
    agency_id: int
    agency_name: str


class CaseResponse(BaseModel):
    id: int
    title: str
    summary: str
    owner_agency_id: int
    agency_name: str
    priority: Priority
    created_at: str


class ReferralResponse(BaseModel):
    id: int
    case_id: int
    to_agency_id: int
    agency_name: str
    case_title: str
    from_agency_name: str
    status: ReferralStatus
    created_at: str


class AuditResponse(BaseModel):
    id: int
    actor_name: str
    agency_name: str
    action: str
    created_at: str


class CaseDetail(CaseResponse):
    referrals: list[ReferralResponse]
    events: list[AuditResponse]


class ReportRow(BaseModel):
    agency_id: int
    agency_name: str
    pending_referrals: int
