import os
import sys
import requests
from dotenv import load_dotenv
from typing import Dict, Any

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd())

print(sys.path)
print(os.getcwd())

load_dotenv("/Users/paddy/Documents/Github/Dump-Truck/last-fm-spotify-agent/.env")

import os
from opentelemetry import trace as trace_api
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from phoenix.otel import HTTPSpanExporter
from arize.otel import register as arize_register
from openinference.instrumentation.langchain import LangChainInstrumentor

PHOENIX_COLLECTOR = "https://app.phoenix.arize.com/s/padmanabhan-rajendra/v1/traces"
PHOENIX_API_KEY = os.environ.get("PHOENIX_API_KEY")

# 1) Arize tracer provider + its default exporter
tracer_provider = arize_register(
    space_id=os.environ["ARIZE_SPACE_ID"],
    api_key=os.environ["ARIZE_API_KEY"],
    project_name="lastfm-spotify-app",
)

# 2) Add Phoenix exporter as an additional span processor
phoenix_exporter = HTTPSpanExporter(
    endpoint=PHOENIX_COLLECTOR,
    headers={"authorization": f"Bearer {PHOENIX_API_KEY}"},
)
phoenix_processor = BatchSpanProcessor(phoenix_exporter)

# Add the Phoenix processor to the existing tracer provider
tracer_provider.add_span_processor(phoenix_processor)

# If you ALSO want a local Phoenix target, you can add it:
local_exporter = HTTPSpanExporter(endpoint="http://127.0.0.1:6006/v1/traces")
local_processor = BatchSpanProcessor(local_exporter)
tracer_provider.add_span_processor(local_processor)

# 3) Set global + instrument LangChain
trace_api.set_tracer_provider(tracer_provider)
LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

print("LangChain instrumented → Arize + Phoenix (SaaS [+ local if enabled])")

from pprint import pprint
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


# from langchain_google_genai import ChatGoogleGenerativeAI
# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

# from langchain_groq import ChatGroq
# llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)

from langchain_deepseek import ChatDeepSeek
llm = ChatDeepSeek(
    model="deepseek/deepseek-v3.2",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
    extra_body={"reasoning": {"enabled": True}},
)

from lastfm_spotify_tools import (  # type: ignore
    get_lastfm_user_info,
    get_artist_info,
    get_track_info,
    search_artists_by_genre,
    get_artist_details,
    get_artist_top_tracks,
    get_artist_albums,
)

tools = [
    get_lastfm_user_info,
    get_artist_info,
    get_track_info,
    search_artists_by_genre,
    get_artist_details,
    get_artist_top_tracks,
    get_artist_albums,
]
llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=True)

from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition

LASTFM_SPOTIFY_SYSTEM_PROMPT = """
You are a music assistant who helps users with queries about artists, 
tracks, albums, and music listening habits using Last.fm and Spotify data.

You have access to these tools:

Last.fm tools:
- get_lastfm_user_info: Get user profile information
- get_artist_info: Get artist metadata from Last.fm
- get_track_info: Get track metadata from Last.fm

Spotify tools:
- search_artists_by_genre: Search for artists by genre
- get_artist_details: Get detailed artist information by Spotify ID
- get_artist_top_tracks: Get an artist's top tracks
- get_artist_albums: Get an artist's albums and releases

Guidelines:
- Choose the appropriate tool based on the user's query
- Use Last.fm for listening history and scrobble data
- Use Spotify for genre searches, artist discovery, and detailed track/album info
- Provide clear, helpful responses based on the tool results
"""

sys_msg = SystemMessage(content=LASTFM_SPOTIFY_SYSTEM_PROMPT)

def music_assistant(state: MessagesState):
    return {
        "messages": [
            llm_with_tools.invoke([sys_msg] + state["messages"])
        ]
    }

# Graph
builder = StateGraph(MessagesState)

# Define nodes: these do the work
builder.add_node("music_assistant", music_assistant)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "music_assistant")

builder.add_conditional_edges(
    "music_assistant",
    tools_condition,
)

builder.add_edge("tools", "music_assistant")

music_graph = builder.compile()
