from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.models.questionnaire import QuestionnaireInput
from backend.models.persona import PersonaObject

load_dotenv()

_model = ChatAnthropic(model="claude-sonnet-5")
_structured_model = _model.with_structured_output(PersonaObject, method="json_schema")

SYSTEM_PROMPT = (
    "You are a behavioral persona analyst. Given a roommate questionnaire "
    "and a free-text self-description, produce a PersonaObject.\n\n"
    "Do not simply restate the questionnaire answers as traits or dealbreakers. "
    "Infer the underlying behavioral patterns, conflict tendencies, and "
    "communication habits implied by the combination of answers and the "
    "free-text description. Two people with the same sleep_schedule can have "
    "very different behavioral_traits depending on how they talk about it.\n\n"
    "Invent a short first-name label for this persona in the `name` field."
)


def construct_persona(questionnaire: QuestionnaireInput, free_text: str) -> PersonaObject:
    questionnaire_summary = "\n".join(
        f"{field}: {value}" for field, value in questionnaire.model_dump().items()
    )
    human_message = (
        f"Questionnaire answers:\n{questionnaire_summary}\n\n"
        f"Free-text description:\n{free_text}"
    )
    return _structured_model.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human_message)]
    )
