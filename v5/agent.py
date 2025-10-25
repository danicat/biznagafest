from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools import google_search
from google.protobuf.json_format import MessageToDict
from vertexai.preview import rag

import json
import os
import osquery
import platform

def run_osquery(query: str) -> str:
  """Runs a query using osquery.

  Args:
    query: The osquery query to run. Example: 'select * from battery'

  Returns:
    The query result as a JSON string.
    
    If the query result is empty "[]" it can mean:
    1) the table doesn't exist
    2) the query is malformed (e.g. a column doesn't exist)
    3) the table is empty
  """
  instance = osquery.SpawnInstance()
  instance.open()
  result = instance.client.query(query)
  return json.dumps(result.response)

TABLES=[row["name"] for row in json.loads(run_osquery("select name from osquery_registry where registry='table'"))]

from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag

schema_discovery = VertexAiRagRetrieval(
    name='schema_discovery',
    description=(
        'Use this tool to retrieve osquery table schema documentation,'
    ),
    rag_resources=[
        rag.RagResource(
            rag_corpus=os.environ.get("RAG_CORPORA_URI")
        )
    ],
    similarity_top_k=10,
    vector_distance_threshold=0.6,
)

query_planner = Agent(
    model="gemini-2.5-flash",
    name="query_planner",
    instruction=f"""
    You are a query planning agent designed to take an user request and 
    come up with a plan consisting of one or more queries that can help the
    investigation.
    
    The installed operating system is: {platform.uname()}
    The available osquery tables are: {TABLES}

    Avoid using SELECT * queries. You MUST Use schema discovery to retrieve 
    the EXACT table structure and be precise and SELECT only the columns
    necessary for the investigation.

    Return only the list of queries to be executed, with no other commentary.
    """,
    tools=[schema_discovery],
)

query_executor = Agent(
    model="gemini-2.5-flash",
    name="query_executor",
    instruction="""
    You are a query execution agent designed to take a list of queries
    and run them one by one using osquery. If a query return empty,
    it can mean the query is malformed (wrong column name, table doesn't exist),
    so whenever a query returns empty describe the table with PRAGMA and 
    correct the query if necessary.
    """,
    tools=[run_osquery],
)

data_analyser = Agent(
    model="gemini-2.5-flash",
    name="data_analyser",
    instruction="""
    You are a data analyser agent. You are given the resulting data from
    several diagnostic queries against operating system tables. Your goal
    is to summarise the data and highlight any abnormalities.

    Your summary should have no more than 2 paragraphs. Only highlight the
    most important data.
    """,
)

pipeline = SequentialAgent(
  name="diagnostic_pipeline_agent",
  sub_agents=[query_planner, query_executor, data_analyser]
)

root_agent = Agent(
    model='gemini-2.5-flash',
    name='coordinator',
    instruction=f"""
    You are the emergency diagnostic agent.
    Execute diagnostic procedures and system health checks according to the user's request.
    If the user don't give you an immediate request, greet the user and say:
    "Please state the nature of the diagnostic emergency"

    Delegate all diagnostic requests to the diagnostic pipeline agent.
    """,
    sub_agents=[pipeline]
)
