from langchain_core.messages import HumanMessage, SystemMessage

from config import LLM_MODEL
from llm_builder import build_llm
from prompts import CHAT_TITLE_PROMPT


def generate_chat_title(first_message: str, model: str = None) -> str:
    if not first_message or not first_message.strip():
        return "New chat"
    model = model or LLM_MODEL
    llm = build_llm(model, temperature=0.3)
    try:
        response = llm.invoke(
            [
                SystemMessage(content=CHAT_TITLE_PROMPT),
                HumanMessage(content=first_message[:2000]),
            ]
        )
        title = (response.content or "").strip()
        if not title:
            return "New chat"
        if len(title) > 80:
            title = title[:77] + "..."
        return title
    except Exception:
        return "New chat"
