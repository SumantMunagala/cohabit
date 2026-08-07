from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.llm import get_llm
from backend.models.questionnaire import QuestionnaireInput
from backend.models.persona import PersonaObject

load_dotenv()

_model = get_llm()
_structured_model = _model.with_structured_output(PersonaObject, method="json_schema")

SYSTEM_PROMPT = (
    "You are a behavioral persona analyst. Given a roommate questionnaire "
    "and a free-text self-description, produce a PersonaObject.\n\n"
    "Do not simply restate the questionnaire answers as traits or dealbreakers. "
    "Infer the underlying behavioral patterns, conflict tendencies, and "
    "communication habits implied by the combination of answers and the "
    "free-text description. Two people with the same sleep_schedule can have "
    "very different behavioral_traits depending on how they talk about it.\n\n"
    "Concrete example of the difference:\n"
    "- Restatement (do NOT do this): \"Prefers quiet evenings.\"\n"
    "- Inference (do this instead): \"Likely to use passive silence rather than "
    "direct confrontation when noise boundaries are crossed.\"\n\n"
    "This matters even when the input is simple or one-dimensional. If someone "
    "just says they're social and work from home, don't just restate "
    "\"comfortable with high noise levels\" or \"treats home as a social hub\" -- "
    "ask what that implies about how they'd behave in a conflict: would they "
    "notice a roommate's irritation, or miss it? Would they apologize and adjust, "
    "or assume it's not a big deal? Every trait and dealbreaker should describe a "
    "predicted behavior pattern, not a fact already present in the input.\n\n"
    "If the free-text description contains any tension or contradiction (e.g. "
    "someone describes themselves as easygoing but names a firm boundary), that "
    "contradiction is a strong signal -- infer what it reveals about how they'll "
    "actually behave when that boundary is tested.\n\n"
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
