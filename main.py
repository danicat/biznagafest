import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from dotenv import load_dotenv
import vertexai

# --- Agent Definition ---
# In a real project, you would import your agent from another file.
from v4.agent import root_agent

load_dotenv()

# Initialize Vertex AI
project_id = os.getenv("PROJECT_ID")
location = os.getenv("LOCATION")
vertexai.init(project=project_id, location=location)
# --- End Agent Definition ---


# --- Services and Runner Setup ---
session_service = InMemorySessionService()
runner = Runner(
    app_name="agents", agent=root_agent, session_service=session_service
)
app = FastAPI()


# --- Web Interface (HTML) ---
@app.get("/", response_class=HTMLResponse)
async def get_chat_ui():
    """Serves the simple HTML chat interface."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ADK Chat</title>
        <style>
            body { font-family: sans-serif; display: flex; justify-content: center; }
            #chat-container { width: 80%; max-width: 800px; border: 1px solid #ccc; padding: 20px; }
            #messages { height: 400px; overflow-y: scroll; border: 1px solid #eee; padding: 10px; margin-bottom: 10px; }
            #user-input { display: flex; }
            #user-input input { flex-grow: 1; padding: 8px; }
            #user-input button { padding: 8px 12px; }
            .user-message { text-align: right; color: blue; }
            .agent-message { color: green; }
        </style>
    </head>
    <body>
        <div id="chat-container">
            <h1>Agent Chat</h1>
            <div id="messages"></div>
            <form id="user-input" onsubmit="sendMessage(event)">
                <input type="text" id="message-text" autocomplete="off" placeholder="Type your message..."/>
                <button type="submit">Send</button>
            </form>
        </div>
        <script>
            const messagesDiv = document.getElementById('messages');
            const messageText = document.getElementById('message-text');

            async function sendMessage(event) {
                event.preventDefault();
                const query = messageText.value;
                if (!query) return;

                // Display user message
                const userMsgDiv = document.createElement('div');
                userMsgDiv.className = 'user-message';
                userMsgDiv.textContent = `You: ${query}`;
                messagesDiv.appendChild(userMsgDiv);
                messageText.value = '';

                // Create a container for the agent's response
                const agentMsgDiv = document.createElement('div');
                agentMsgDiv.className = 'agent-message';
                agentMsgDiv.textContent = 'Agent: ';
                messagesDiv.appendChild(agentMsgDiv);

                // Stream agent response
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value);
                    agentMsgDiv.textContent += chunk;
                    messagesDiv.scrollTop = messagesDiv.scrollHeight; // Auto-scroll
                }
            }
        </script>
    </body>
    </html>
    """


# --- API Endpoint for Chat Logic ---
@app.post("/chat")
async def chat_handler(request: Request):
    """Handles the chat logic, streaming the agent's response."""
    body = await request.json()
    query = body.get("query")
    user_id = "web_user"
    session_id = "web_session" # In a real app, you'd manage sessions per user

    # Ensure a session exists
    session = await session_service.get_session(app_name="agents", user_id=user_id, session_id=session_id)
    if not session:
        session = await session_service.create_session(app_name="agents", user_id=user_id, session_id=session_id)

    async def stream_generator():
        """Streams the agent's final text response chunks."""
        full_response = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=Content(role="user", parts=[Part.from_text(text=query)]),
        ):
            if event.is_final_response() and event.content and event.content.parts[0].text:
                new_text = event.content.parts[0].text
                # Yield only the new part of the text
                yield new_text[len(full_response):]
                full_response = new_text

    return StreamingResponse(stream_generator(), media_type="text/plain")

# To run this file:
# 1. Make sure you have fastapi and uvicorn installed: pip install fastapi uvicorn
# 2. Save the code as main.py
# 3. Run from your terminal: uvicorn main:app --reload
# 4. Open your browser to http://127.0.0.1:8000