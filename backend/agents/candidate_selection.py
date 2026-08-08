from dotenv import load_dotenv
from sqlalchemy import select

from backend.agents.embeddings import embed_persona
from backend.db.models import User
from backend.db.session import async_session_factory
from backend.models.persona import PersonaObject

load_dotenv()

CANDIDATE_POOL_SIZE = 5
SELF_MATCH_SIMILARITY_THRESHOLD = 1 - 1e-6


async def find_top_matches(persona: PersonaObject) -> list[dict]:
    query_vector = embed_persona(persona)
    distance = User.embedding.cosine_distance(query_vector)
    stmt = (
        select(User, (1 - distance).label("similarity"))
        .order_by(distance)
        .limit(CANDIDATE_POOL_SIZE + 1)
    )
    async with async_session_factory() as session:
        result = await session.execute(stmt)
        rows = result.all()

    matches = [
        {"id": user.id, "persona": user.persona, "similarity": similarity}
        for user, similarity in rows
        if similarity < SELF_MATCH_SIMILARITY_THRESHOLD
    ]
    return matches[:CANDIDATE_POOL_SIZE]
