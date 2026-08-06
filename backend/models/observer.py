from pydantic import BaseModel, Field


class ObserverNotes(BaseModel):
    scenario_index: int
    friction_points: list[str] = Field(
        description="Specific moments of tension, each citing a direct quote or clear paraphrase from the transcript — never vague commentary like 'there was tension'."
    )
    dealbreaker_violations: list[str] = Field(
        description="Specific instances where a persona's stated dealbreaker was directly implicated, naming which dealbreaker and quoting/paraphrasing the relevant exchange. Empty list if none occurred."
    )
    tone_shifts: list[str] = Field(
        description="Points where a speaker's tone noticeably changed, citing the quote/paraphrase before and after."
    )
    concessions: list[str] = Field(
        description="Specific moments where a speaker conceded, compromised, or adjusted their position, citing what was said."
    )
