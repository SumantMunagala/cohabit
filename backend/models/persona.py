from pydantic import BaseModel, Field


class PersonaObject(BaseModel):
    name: str
    sleep_schedule: str
    cleanliness_level: int
    conflict_style: str
    communication_style: str
    dealbreakers: list[str] = Field(
        description="A list of individual short dealbreaker phrases, each its own array item — never a single combined string."
    )
    behavioral_traits: list[str] = Field(
        description="A list of individual short behavioral trait phrases, each its own array item — never a single combined string."
    )
