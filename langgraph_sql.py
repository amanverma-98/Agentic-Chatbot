from langgraph.graph import StateGraph , START , END
from typing import TypedDict , Annotated
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages #reducer
import sqlite3

conn = sqlite3.connect(database = 'chatbot.db' , check_same_thread = False)  #setted it false because sqlite does not support multi-threading

checkpointer = SqliteSaver(conn = conn)


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

chatbot = graph.compile(checkpointer = checkpointer)


def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])

    return list(all_threads)