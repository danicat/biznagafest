from google.adk.agents.llm_agent import Agent
from google.adk.tools import AgentTool, google_search

import json
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


google_search_agent = Agent(
    name="google_search",
    instruction="You are a google search agent.",
    tools=[google_search],
    model="gemini-2.5-flash",
)

google_search_tool = AgentTool(
    agent=google_search_agent
)

root_agent = Agent(
    model='gemini-2.5-flash',
    name='emergency_diagnostic_agent',
    description='The emergency diagnostic agent',
    instruction=f"""
    You are the emergency diagnostic agent.
    Execute diagnostic procedures and system health checks according to the user's request.
    If the user don't give you an immediate request, greet the user and say:
    "Please state the nature of the diagnostic emergency"

    The installed operating system is: {platform.uname()}
    The available osquery tables are: {TABLES}

    The predefined diagnostic procedures are:
    Level 1: basic system health check
    Level 2: advanced diagnostic check

    After running the investigation, only return to the user a brief summary of the findings.
    If the user requests more details, then show the complete data.
    """,
    tools=[
      run_osquery,
      google_search_tool,
    ]
)
