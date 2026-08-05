from pydantic import BaseModel, field_validator


class QuestionnaireInput(BaseModel):
    sleep_schedule: str
    cleanliness_level: int
    guests: str
    noise_tolerance: int
    wfh: bool
    pets: bool
    budget: str

    @field_validator("cleanliness_level", "noise_tolerance")
    @classmethod
    def validate_range(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("must be between 1 and 10")
        return v
