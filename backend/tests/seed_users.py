import asyncio
import random
import time

from langchain_anthropic import ChatAnthropic

from backend.agents import persona_construction
from backend.agents.embeddings import embed_persona
from backend.db.models import User
from backend.db.session import async_session_factory
from backend.models.persona import PersonaObject
from backend.models.questionnaire import QuestionnaireInput

HAIKU_MODEL = "claude-haiku-4-5-20251001"
NUM_USERS = 75
EMBED_REQUEST_INTERVAL_SECONDS = 21

SLEEP_SCHEDULES = ["9pm", "10pm", "11pm", "12am", "1am", "2am"]
GUEST_LEVELS = ["never", "rarely", "occasionally", "frequently"]
BUDGETS = ["low", "medium", "high"]

ARCHETYPES = [
    {
        "name": "night_owl",
        "sleep_schedule": ["12am", "1am", "2am"],
        "cleanliness_level": (3, 7),
        "guests": ["occasionally", "frequently"],
        "noise_tolerance": (5, 9),
        "wfh": [True, False],
        "pets": [True, False],
        "budget": BUDGETS,
        "free_text": [
            "I do my best thinking after midnight and rarely wind down before {sleep_schedule}.",
            "Nights are when I come alive -- {sleep_schedule} is a normal bedtime for me.",
        ],
    },
    {
        "name": "early_bird",
        "sleep_schedule": ["9pm", "10pm"],
        "cleanliness_level": (5, 9),
        "guests": ["never", "rarely"],
        "noise_tolerance": (2, 5),
        "wfh": [True, False],
        "pets": [True, False],
        "budget": BUDGETS,
        "free_text": [
            "I'm up at dawn and asleep by {sleep_schedule} most nights, no exceptions.",
            "Mornings are sacred to me -- I try to be in bed by {sleep_schedule}.",
        ],
    },
    {
        "name": "social_butterfly",
        "sleep_schedule": SLEEP_SCHEDULES,
        "cleanliness_level": (2, 6),
        "guests": ["frequently"],
        "noise_tolerance": (7, 10),
        "wfh": [False, False, True],
        "pets": [True, False],
        "budget": BUDGETS,
        "free_text": [
            "My place is always open -- friends drop by constantly and I love a full house.",
            "I host often and don't mind noise or a bit of chaos when people are over.",
        ],
    },
    {
        "name": "introvert",
        "sleep_schedule": SLEEP_SCHEDULES,
        "cleanliness_level": (4, 8),
        "guests": ["never", "rarely"],
        "noise_tolerance": (1, 4),
        "wfh": [True, True, False],
        "pets": [True, False],
        "budget": BUDGETS,
        "free_text": [
            "I keep to myself and need quiet, low-key evenings to recharge.",
            "I'm not big on visitors -- I'd rather have a calm, predictable home.",
        ],
    },
    {
        "name": "neat_freak",
        "sleep_schedule": SLEEP_SCHEDULES,
        "cleanliness_level": (8, 10),
        "guests": GUEST_LEVELS,
        "noise_tolerance": (2, 7),
        "wfh": [True, False],
        "pets": [False, False, True],
        "budget": BUDGETS,
        "free_text": [
            "Everything has a place and I clean as I go -- a messy kitchen genuinely stresses me out.",
            "I'm particular about tidiness and expect shared spaces to stay spotless.",
        ],
    },
    {
        "name": "relaxed_cleanliness",
        "sleep_schedule": SLEEP_SCHEDULES,
        "cleanliness_level": (1, 4),
        "guests": GUEST_LEVELS,
        "noise_tolerance": (3, 8),
        "wfh": [True, False],
        "pets": [True, False],
        "budget": BUDGETS,
        "free_text": [
            "A little clutter doesn't bother me -- I'd rather relax than chase a spotless apartment.",
            "I'm pretty laid-back about mess; life's too short to stress over dishes.",
        ],
    },
]


def _generate_one(archetype: dict) -> tuple[QuestionnaireInput, str]:
    sleep_schedule = random.choice(archetype["sleep_schedule"])
    questionnaire = QuestionnaireInput(
        sleep_schedule=sleep_schedule,
        cleanliness_level=random.randint(*archetype["cleanliness_level"]),
        guests=random.choice(archetype["guests"]),
        noise_tolerance=random.randint(*archetype["noise_tolerance"]),
        wfh=random.choice(archetype["wfh"]),
        pets=random.choice(archetype["pets"]),
        budget=random.choice(archetype["budget"]),
    )
    base = random.choice(archetype["free_text"]).format(sleep_schedule=sleep_schedule)
    extras = []
    if questionnaire.wfh:
        extras.append("I work from home most days.")
    if questionnaire.pets:
        extras.append("I have a pet and it's part of the package.")
    if questionnaire.guests == "never":
        extras.append("I basically never have people over.")
    free_text = " ".join([base] + extras)
    return questionnaire, free_text


def generate_synthetic_users(n: int) -> list[tuple[QuestionnaireInput, str]]:
    return [_generate_one(ARCHETYPES[i % len(ARCHETYPES)]) for i in range(n)]


async def main() -> None:
    random.seed(42)
    synthetic_users = generate_synthetic_users(NUM_USERS)

    original_model = persona_construction._model
    original_structured_model = persona_construction._structured_model
    haiku = ChatAnthropic(model=HAIKU_MODEL, temperature=0.2)
    persona_construction._model = haiku
    persona_construction._structured_model = haiku.with_structured_output(PersonaObject, method="json_schema")

    try:
        for i, (questionnaire, free_text) in enumerate(synthetic_users, start=1):
            persona = persona_construction.construct_persona(questionnaire, free_text)
            embedding = embed_persona(persona)
            async with async_session_factory() as session:
                session.add(User(persona=persona.model_dump(), embedding=embedding))
                await session.commit()
            print(f"Seeded {i}/{NUM_USERS}")
            if i < NUM_USERS:
                time.sleep(EMBED_REQUEST_INTERVAL_SECONDS)
    finally:
        persona_construction._model = original_model
        persona_construction._structured_model = original_structured_model


if __name__ == "__main__":
    asyncio.run(main())
