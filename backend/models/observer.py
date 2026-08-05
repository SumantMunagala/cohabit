from pydantic import BaseModel


class ObserverNotes(BaseModel):
    scenario_index: int
    friction_points: list[str]
    dealbreaker_violations: list[str]
    tone_shifts: list[str]
    concessions: list[str]
