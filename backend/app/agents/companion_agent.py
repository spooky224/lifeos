import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from app.graph.state import LifeOSState

load_dotenv()

_model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0.6,
)


def companion_agent(state: LifeOSState) -> LifeOSState:
    """Respond as LIFEOS's conversational companion without triggering actions."""
    history = state.get("conversation_history", [])[-12:]
    transcript = "\n".join(
        f"{turn.get('role', 'user').upper()}: {turn.get('content', '')}"
        for turn in history
        if turn.get("role") in {"user", "assistant"}
    )
    user_request = state.get("user_request", "")

    prompt = f"""
You are LIFEOS, a thoughtful, natural personal AI companion.
You are not a command parser, productivity coach that forces every topic
into a task, or a workflow status reporter. Talk with the user like a
capable, warm, honest conversational partner.

Guidelines:
- Respond to what the user actually said before suggesting anything.
- Be natural and concise; ask a follow-up only when it genuinely helps.
- Use the conversation transcript to understand references and continuity.
- Do not assume every emotion or idea is a request for action.
- Do not claim to have created, changed, scheduled, or remembered anything
  unless the system state in the conversation explicitly supports that.
- If the user clearly asks for an action, explain the next useful step
  conversationally; the orchestrator should route explicit actions to a
  domain capability rather than performing it from this node.
- Do not mention internal agents, routing, graph nodes, or implementation.

Recent conversation:
{transcript or '(No earlier conversation available.)'}

Current user message:
{user_request}

Reply directly to the user. Do not return JSON.
"""

    try:
        response = _model.invoke(prompt)
        reply = response.content if hasattr(response, "content") else str(response)
        if isinstance(reply, list):
            reply = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in reply
            )
        reply = str(reply).strip()
        if not reply:
            reply = "I'm here. Can you tell me a little more about what's on your mind?"
    except Exception:
        reply = (
            "I'm here with you, but I hit a temporary issue generating a reply. "
            "Could you try that once more?"
        )

    return {
        "final_response": reply,
        "messages": state.get("messages", []) + [
            {"role": "companion_agent", "content": reply}
        ],
    }
