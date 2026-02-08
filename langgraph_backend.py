from langgraph.graph import StateGraph , START , END
from typing import TypedDict , Annotated
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages #reducer

checkpoint = InMemorySaver()

#state
class LLMState(TypedDict):
    message_history : Annotated[list[BaseMessage] , add_messages]

#graph
graph = StateGraph(LLMState)

llm = ChatOllama(model = 'llama3')

def chat(state : LLMState)-> LLMState:
    message = state['message_history']

    response = llm.invoke(message)

    return {'message_history' : [response]}


graph.add_node('chat' , chat)

graph.add_edge(START , 'chat')
graph.add_edge('chat' , END)

chatbot = graph.compile(checkpointer = checkpoint)