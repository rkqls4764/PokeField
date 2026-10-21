"""Explicit integration boundary. No invented retrieval or answers."""
import re
from typing import TypedDict

class RagState(TypedDict, total=False):
    pokemon_id: int
    generation: int
    question: str
    sources: list[dict]
    answer: str

def cited_sources(answer, sources):
    numbers = {int(n) for group in re.findall(r'\[근거\s*([\d,\s]+)\]', answer) for n in group.split(',') if n.strip().isdigit()}
    return [(i,s) for i,s in enumerate(sources,1) if i in numbers]

def build_graph(retrieve, generate):
    """Inject real adapters after collection/indexing are implemented."""
    from langgraph.graph import StateGraph, START, END
    graph = StateGraph(RagState)
    graph.add_node('retrieve',retrieve); graph.add_node('generate',generate)
    graph.add_edge(START,'retrieve'); graph.add_edge('retrieve','generate'); graph.add_edge('generate',END)
    return graph.compile()
