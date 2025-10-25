from google.adk.agents.llm_agent import Agent

import osquery
import json

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

root_agent = Agent(
    model='gemini-2.5-flash',
    name='emergency_diagnostic_agent',
    description='The emergency diagnostic agent',
    instruction="""
    You are the emergency diagnostic agent.
    Execute diagnostic procedures and system health checks according to the user's request.
    If the user don't give you an immediate request, greet the user and say:
    "Please state the nature of the diagnostic emergency"
    """,
    tools=[run_osquery]
)
