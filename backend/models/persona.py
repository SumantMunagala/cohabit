from pydantic import BaseModel


class PersonaObject(BaseModel):
    name: str
    sleep_schedule: str
    cleanliness_level: int
    conflict_style: str
    communication_style: str
    dealbreakers: list[str]
    behavioral_traits: list[str]
