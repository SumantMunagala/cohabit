from dotenv import load_dotenv
from langchain_voyageai import VoyageAIEmbeddings

from backend.models.persona import PersonaObject

load_dotenv()

_embeddings = VoyageAIEmbeddings(model="voyage-3-lite")


def embed_persona(persona: PersonaObject) -> list[float]:
    text = " ".join(
        persona.behavioral_traits
        + [persona.conflict_style, persona.communication_style]
        + persona.dealbreakers
    )
    return _embeddings.embed_query(text)
