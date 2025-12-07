import os
import sys
import requests
from typing import Dict, Any
from pprint import pprint
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


#from langchain_google_genai import ChatGoogleGenerativeAI
#llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)

# from langchain_groq import ChatGroq
# llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)

from langchain_deepseek import ChatDeepSeek
llm = ChatDeepSeek(
    model="deepseek/deepseek-chat-v3.1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
    extra_body={"reasoning": {"enabled": True}},
)

# Tool Functions

BASE_URL = "https://api.clashofclans.com/v1"
TOKEN = os.getenv("CLASH_API_TOKEN")


def get_clan_details(clan_tag: str) -> Dict[str, Any]:
    """
    Fetch clan information by clan tag.
    
    Args:
        clan_tag (str): Clan tag (e.g., "#2YGRG9JCU")
    
    Returns:
        Dict[str, Any]: Clan information from the Clash of Clans API
    
    Raises:
        Exception: If API request fails (non-200 status code)
    """
    encoded_tag = clan_tag.replace("#", "%23")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/clans/{encoded_tag}", headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")
    
    return response.json()


def get_player_details(player_tag: str) -> Dict[str, Any]:
    """
    Fetch player information by player tag.
    
    Args:
        player_tag (str): Player tag (e.g., "#ABC123")
    
    Returns:
        Dict[str, Any]: Player information from the Clash of Clans API
    
    Raises:
        Exception: If API request fails (non-200 status code)
    """
    encoded_tag = player_tag.replace("#", "%23")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/players/{encoded_tag}", headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")
    
    return response.json()



tools = [get_clan_details, get_player_details]
llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=True)


from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition


CLASH_OF_CLANS_SYSTEM_PROMPT = """
You are a Clash of Clans assistant who helps users with their queries 
about clans and players.

You have access to two tools:
- get_clan_details
- get_player_details

Guidelines:
- Users will generally query based on clan tags or player tags.
- Always choose the correct tool based on what the user is asking for.
- After calling a tool, analyze the returned information and answer 
  the user’s query as accurately and clearly as possible.
"""

sys_msg = SystemMessage(content=CLASH_OF_CLANS_SYSTEM_PROMPT)


def coc_assistant(state: MessagesState):
    return {
        "messages": [
            llm_with_tools.invoke([sys_msg] + state["messages"])
        ]
    }



# Graph
builder = StateGraph(MessagesState)

# Define nodes: these do the work
builder.add_node("coc_assistant", coc_assistant)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "coc_assistant")

builder.add_conditional_edges(
    "coc_assistant",
    tools_condition,
)

builder.add_edge("tools", "coc_assistant")

coc_graph = builder.compile()
