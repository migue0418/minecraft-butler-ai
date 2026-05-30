from langgraph.graph import END, START, StateGraph

from app.features.butler.graph.nodes import (
    answer_question,
    classify_intent,
    move_action,
    retrieve_context,
    speak_action,
)
from app.features.butler.graph.routing import route_intent
from app.features.butler.graph.state import ButlerState


def compile_graph():
    builder = StateGraph(ButlerState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("answer_question", answer_question)
    builder.add_node("speak_action", speak_action)
    builder.add_node("move_action", move_action)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "retrieve_context": "retrieve_context",
            "speak_action": "speak_action",
            "move_action": "move_action",
        },
    )
    builder.add_edge("retrieve_context", "answer_question")
    builder.add_edge("answer_question", END)
    builder.add_edge("speak_action", END)
    builder.add_edge("move_action", END)

    return builder.compile()
