from pydantic import BaseModel, field_validator


class VerdictObject(BaseModel):
    lifestyle_score: int
    communication_score: int
    conflict_score: int
    dealbreaker_score: int
    lifestyle_explanation: str
    communication_explanation: str
    conflict_explanation: str
    dealbreaker_explanation: str
    overall_summary: str

    @field_validator(
        "lifestyle_score", "communication_score", "conflict_score", "dealbreaker_score"
    )
    @classmethod
    def validate_range(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("must be between 1 and 10")
        return v
