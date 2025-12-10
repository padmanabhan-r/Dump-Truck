import os
import sys

from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd())


print(sys.path)
print(os.getcwd())


load_dotenv("/Users/paddy/Documents/Github/Dump-Truck/last-fm-spotify-agent/.env")


import os

from arize.otel import register as arize_register
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace as trace_api
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from phoenix.otel import HTTPSpanExporter

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



from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)


# from langchain_groq import ChatGroq
# llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)


# from langchain_deepseek import ChatDeepSeek
# llm = ChatDeepSeek(
#     model="deepseek/deepseek-v3.2",
#     api_key=os.getenv("OPENROUTER_API_KEY"),
#     api_base="https://openrouter.ai/api/v1",
#     extra_body={"reasoning": {"enabled": True}},
# )


from lastfm_spotify_tools import (  # type: ignore
    get_artist_albums,
    get_artist_details,
    get_artist_details_by_name,
    get_artist_info,
    get_artist_top_tracks,
    get_lastfm_user_info,
    get_lastfm_user_top_artists,
    get_track_info,
    search_artist_by_name,
    search_artists_by_genre,
)

tools = [
    get_lastfm_user_info,
    get_lastfm_user_top_artists,
    get_artist_info,
    get_track_info,
    search_artists_by_genre,
    search_artist_by_name,
    get_artist_details,
    get_artist_details_by_name,
    get_artist_top_tracks,
    get_artist_albums,
]
llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=True)


from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

LASTFM_SPOTIFY_SYSTEM_PROMPT = """
You are a music assistant who helps users with queries about artists, 
tracks, albums, and music listening habits using Last.fm and Spotify data.

You have access to these tools:

Last.fm tools:
- get_lastfm_user_info: Get user profile information
- get_lastfm_user_top_artists: Get a user's top artists with playcount and time period filters (7day, 1month, 3month, 6month, 12month, overall)
- get_artist_info: Get artist metadata from Last.fm
- get_track_info: Get track metadata from Last.fm

Spotify tools:
- search_artists_by_genre: Search for artists by genre
- search_artist_by_name: Search for artists by name (returns list of matches)
- get_artist_details: Get detailed artist information by Spotify ID (includes followers, popularity, genres)
- get_artist_details_by_name: Get detailed artist information by name (convenience function that searches and returns top match)
- get_artist_top_tracks: Get an artist's top tracks for a specific market
- get_artist_albums: Get an artist's albums and releases

Guidelines:
- Choose the appropriate tool based on the user's query
- Use Last.fm for listening history, scrobble data, and user-specific top artists
- Use Spotify for genre searches, artist discovery, detailed track/album info, and artist statistics (followers, popularity)
- When users ask about artist stats by name, use get_artist_details_by_name for convenience
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
