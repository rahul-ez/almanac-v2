from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, SecretStr, StringConstraints, model_validator
from app.schemas.contracts import StrictModel

Username = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_.-]*$")]

class LoginRequest(StrictModel):
    username: Username
    password: SecretStr = Field(min_length=1, max_length=256)

class Identity(StrictModel):
    id: str
    username: str
    role: Literal["student", "admin"]
    session_expires_at: AwareDatetime

class CsrfResponse(StrictModel):
    csrf_token: str
    expires_at: AwareDatetime

class LoginResponse(StrictModel):
    user: Identity
    csrf_token: str

class LogoutResponse(StrictModel):
    message: Literal["Signed out"] = "Signed out"

class ProfilePatch(StrictModel):
    department_id: str | None = Field(default=None, max_length=80)
    year: int | None = Field(default=None, ge=1, le=4, strict=True)
    section: str | None = Field(default=None, max_length=16, pattern=r"^[A-Za-z0-9 -]+$")
    interests: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def distinct_interests(self):
        if len(self.interests) != len(set(self.interests)):
            raise ValueError("Interests must be unique")
        return self

class Profile(StrictModel):
    user_id: str
    department_id: str | None
    year: int | None
    section: str | None
    interests: list[str]

class ReferenceItem(StrictModel):
    id: str
    label: str

class ReferenceData(StrictModel):
    departments: list[ReferenceItem]
    buildings: list[ReferenceItem]
    topics: list[ReferenceItem]
    supported_years: list[int]
    demo: Literal[True] = True

class AdminAccess(StrictModel):
    user_id: str
    role: Literal["admin"] = "admin"
    message: str = "Admin access verified; campus record management arrives in later phases."
