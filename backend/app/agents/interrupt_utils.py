import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.types import interrupt as _interrupt
from pydantic import BaseModel, Field

load_dotenv()

_classifier_model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)


class AnswerClassification(BaseModel):
    is_new_request: bool = Field(
        description=(
            "True if the reply is actually a new/different request, "
            "changing topic, or abandoning the current question. "
            "False if it directly answers the question asked."
        )
    )


_classifier = _classifier_model.with_structured_output(
    AnswerClassification,
    method="json_mode",
)

_QUICK_ABANDON_SIGNALS = (
    "never mind",
    "nevermind",
    "forget it",
    "forget that",
    "cancel that",
    "actually,",
    "actually let",
    "instead let",
    "let's do",
    "lets do",
    "scratch that",
)


class TopicSwitchDetected(Exception):
    """
    Raised by ask() when the user's reply to a pending question is
    actually a new, unrelated request rather than an answer. Callers
    should let this propagate to the top of their node function and
    hand control back to the Personal Agent for fresh classification
    instead of forcing the reply through the original parser.
    """

    def __init__(self, new_request: str):
        self.new_request = new_request
        super().__init__(new_request)


def ask(question: str) -> str:
    """
    Pause the graph and ask the user `question` (same underlying
    mechanism as approval interrupts). If the reply looks like the
    user changing topic rather than answering, raises
    TopicSwitchDetected instead of returning it.
    """

    answer = _interrupt(question)
    lowered = str(answer).lower().strip()

    if any(signal in lowered for signal in _QUICK_ABANDON_SIGNALS):
        raise TopicSwitchDetected(answer)

    # Short, direct answers (numbers, times, single words/phrases)
    # are almost certainly real answers -- skip the LLM call.
    if len(lowered.split()) <= 4:
        return answer

    try:
        result = _classifier.invoke(f"""
The user was just asked:
"{question}"

They replied:
"{answer}"

Is this reply actually answering the question, or is the user
changing topic / asking for something else entirely instead?

Return ONLY valid JSON:
{{"is_new_request": false}}
""")

        if result.is_new_request:
            raise TopicSwitchDetected(answer)

    except TopicSwitchDetected:
        raise

    except Exception:
        # Classifier hiccup shouldn't block a legitimate answer --
        # fail open and treat it as a direct answer.
        pass

    return answer