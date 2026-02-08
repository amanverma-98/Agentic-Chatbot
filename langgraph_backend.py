from langgraph.graph import StateGraph , START , END
from typing import TypedDict , Annotated
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages #reducer

checkpoint = InMemorySaver()

#state
class LLMState(TypedDict):
    messages : Annotated[list[BaseMessage] , add_messages]

#graph
graph = StateGraph(LLMState)

llm = ChatOllama(model = 'llama3')

def chat(state : LLMState)-> LLMState:
    message = state['messages']

    response = llm.invoke(message)

    return {'messages' : [response]}


graph.add_node('chat' , chat)

graph.add_edge(START , 'chat')
graph.add_edge('chat' , END)

chatbot = graph.compile(checkpointer = checkpoint)