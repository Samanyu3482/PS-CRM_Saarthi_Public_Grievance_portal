# app/services/agent_service.py

import os
import httpx
from typing import Optional, Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# ─── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")


def get_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ─── Graph State ────────────────────────────────────────────────────────────────
# This is the single source of truth passed between every node in the graph.
# add_messages means new messages are appended, not overwritten.

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    token: str                        # JWT token threaded through all tool calls
    final_response: Optional[str]     # Plain text output sent to Tavus


# ─── Tool 1: File a Complaint ───────────────────────────────────────────────────

def make_file_complaint_tool(token: str):
    @tool
    def file_complaint(
        title: str,
        description: str,
        address: str,
        city: str,
        state: str,
        pincode: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> str:
        """
        File a new public service complaint on behalf of the user.
        Use this when the user describes a civic problem they want to formally
        report — roads, water, electricity, sanitation, drainage, or any
        public infrastructure issue.

        Args:
            title: Short one-line summary of the complaint (under 10 words)
            description: Detailed description of the issue
            address: Street address where the issue exists
            city: City name
            state: State name
            pincode: 6-digit pincode
            lat: Optional GPS latitude
            lng: Optional GPS longitude
        """
        payload = {
            "title": title,
            "description": description,
            "address": address,
            "city": city,
            "state": state,
            "pincode": pincode,
            "lat": lat,
            "lng": lng,
            "images": [],
        }
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{BASE_URL}/complaints/",
                    json=payload,
                    headers=get_headers(token),
                    timeout=10,
                )
            if response.status_code == 200:
                data = response.json()
                complaint_id = data.get("_id") or data.get("id", "unknown")
                return (
                    f"Complaint filed successfully. "
                    f"Complaint ID is {complaint_id}."
                )
            else:
                return (
                    f"Failed to file complaint. "
                    f"Server returned status {response.status_code}."
                )
        except Exception as e:
            return f"Connection error while filing complaint: {str(e)}"

    return file_complaint


# ─── Tool 2: Check Complaint Status ────────────────────────────────────────────

def make_check_status_tool(token: str):
    @tool
    def check_complaint_status(complaint_id: str) -> str:
        """
        Check the current status of an existing complaint using its complaint ID.
        Use this when the user asks about progress, updates, or current state
        of a previously filed complaint.

        Args:
            complaint_id: The unique ID of the complaint to look up
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{BASE_URL}/complaints/{complaint_id}",
                    headers=get_headers(token),
                    timeout=10,
                )
            if response.status_code == 200:
                data = response.json()

                status       = data.get("status", "unknown")
                title        = data.get("title", "your complaint")
                priority     = data.get("priority", "medium")
                department   = data.get("department") or "not yet assigned"
                ministry     = data.get("ministry") or "not yet assigned"
                assigned_to  = data.get("assigned_to") or "not yet assigned"
                sla_deadline = data.get("sla_deadline") or "not set"
                category     = data.get("category") or "under review"

                status_descriptions = {
                    "submitted":   "has been received and is awaiting review",
                    "classified":  "has been reviewed and classified by our team",
                    "assigned":    "has been assigned to the relevant department",
                    "in_progress": "is currently being actively worked on",
                    "resolved":    "has been resolved",
                    "closed":      "has been closed",
                }
                status_text = status_descriptions.get(status, f"is currently {status}")

                return (
                    f"Complaint titled '{title}' {status_text}. "
                    f"Priority: {priority}. Category: {category}. "
                    f"Ministry: {ministry}. Department: {department}. "
                    f"Assigned officer: {assigned_to}. "
                    f"Resolution deadline: {sla_deadline}."
                )
            elif response.status_code == 404:
                return f"No complaint found with ID {complaint_id}. Please verify the ID."
            else:
                return f"Could not retrieve complaint. Server returned {response.status_code}."
        except Exception as e:
            return f"Connection error while checking status: {str(e)}"

    return check_complaint_status


# ─── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful public service assistant for IndiaInnovate Smart Public Service CRM.

You help citizens with two tasks:
1. File complaints about civic issues — roads, water, electricity, sanitation, drainage, or any public infrastructure problem.
2. Check the status of a previously filed complaint using a complaint ID.

When filing a complaint:
- You need: title, description, address, city, state, and pincode.
- If any detail is missing, ask for it clearly before calling the tool.
- Build a formal title under 10 words and a clear description from what the user tells you.

When checking status:
- Ask for the complaint ID if the user has not provided one.
- Translate the raw status into warm plain English for the user.

Output rules — your response is read aloud by a text-to-speech engine:
- Plain text only. No markdown, no bullet points, no asterisks, no symbols.
- Natural spoken sentences only.
- Never expose JSON, field names, or technical terms.
- Be concise, warm, and clear.
- LANGUAGE MATCHING: Respond in the exact same language and script the user uses.
  - If English -> reply in English.
  - If Hindi (Devanagari) -> reply in Hindi.
  - CRITICAL: If the user speaks in "Hinglish" (Hindi words written in the English alphabet, e.g., "hi tu kaisi hai", "mera pani"), you MUST reply in "Hinglish" text (e.g., "Main theek hu, kya main aapki complaint file karu?"). Do NOT use Devanagari script for Hinglish inputs.
- Always close with: Is there anything else I can help you with today?
"""


# ─── Graph Nodes ────────────────────────────────────────────────────────────────

def make_agent_node(llm_with_tools):
    """The main reasoning node — calls the LLM and decides whether to use a tool or respond."""
    def agent_node(state: AgentState) -> AgentState:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {
            "messages": [response],
            "token": state["token"],
            "final_response": None,
        }
    return agent_node


def make_response_node():
    """Extracts the final plain text response and stores it in state for FastAPI to return."""
    def response_node(state: AgentState) -> AgentState:
        last_message = state["messages"][-1]
        final_text = last_message.content if hasattr(last_message, "content") else str(last_message)
        return {
            "messages": state["messages"],
            "token": state["token"],
            "final_response": final_text,
        }
    return response_node


# ─── Routing Logic ───────────────────────────────────────────────────────────────
# After the agent node runs, decide: did the LLM call a tool, or is it done?

def should_use_tool(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "respond"


# ─── Graph Builder ───────────────────────────────────────────────────────────────

def build_graph(token: str) -> StateGraph:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        openai_api_key=OPENAI_API_KEY,
    )

    tools = [
        make_file_complaint_tool(token),
        make_check_status_tool(token),
    ]

    llm_with_tools = llm.bind_tools(tools)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    agent_node    = make_agent_node(llm_with_tools)
    tool_node     = ToolNode(tools)               # LangGraph built-in tool executor
    response_node = make_response_node()

    # ── Build graph ────────────────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    graph.add_node("agent",   agent_node)
    graph.add_node("tools",   tool_node)
    graph.add_node("respond", response_node)

    # ── Edges ──────────────────────────────────────────────────────────────────
    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_use_tool,
        {
            "tools":   "tools",     # LLM wants to call a tool → execute it
            "respond": "respond",   # LLM has a final answer → extract and return
        }
    )

    graph.add_edge("tools", "agent")    # after tool runs → back to agent to process result
    graph.add_edge("respond", END)      # final response → done

    return graph.compile()


# ─── Main callable for FastAPI ──────────────────────────────────────────────────

def run_agent(
    user_message: str,
    token: str,
    chat_history: Optional[list[BaseMessage]] = None,
) -> tuple[str, list[BaseMessage]]:
    """
    Call this from your FastAPI route.

    Args:
        user_message:  The user's raw input text
        token:         JWT bearer token of the authenticated user
        chat_history:  Previous messages for multi-turn context (optional)

    Returns:
        Tuple of (plain_text_response, updated_chat_history)
        Pass plain_text_response directly to Tavus.
        Store updated_chat_history and pass it back on the next turn.
    """
    history = chat_history or []
    new_message = HumanMessage(content=user_message)
    all_messages = history + [new_message]

    graph = build_graph(token)

    final_state = graph.invoke({
        "messages": all_messages,
        "token": token,
        "final_response": None,
    })

    response_text = final_state["final_response"] or "I was unable to process your request. Please try again."
    updated_history = final_state["messages"]

    return response_text, updated_history


# ─── Pretty printer ─────────────────────────────────────────────────────────────

def print_response(user_msg: str, agent_response: str):
    print("\n" + "─" * 60)
    print(f"  YOU   : {user_msg}")
    print(f"  AGENT : {agent_response}")
    print("─" * 60)


# ─── Main (testing) ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # Replace with a real token from POST /auth/login
    TEST_TOKEN = "your_jwt_token_here"

    # Persisted across turns — this is what replaces LangChain memory
    chat_history: list[BaseMessage] = []

    TEST_CONVERSATIONS = [
        # Scenario 1: Full complaint info given upfront
        (
            "There is a huge pothole on MG Road near the bus stop in "
            "Bangalore, Karnataka, pincode 560001. It has been there for "
            "2 weeks and caused two accidents already. Please file a complaint."
        ),
        # Scenario 2: Check status — swap in a real ID after scenario 1 runs
        "Can you check the status of my complaint? The ID is 64f1a2b3c4d5e6f7a8b9c0d1",

        # Scenario 3: Vague complaint — agent should ask follow-up
        "The street lights are not working.",

        # Scenario 4: Follow-up to vague complaint
        "It is on Nehru Street, Pune, Maharashtra, 411001.",
    ]

    print("\n" + "=" * 60)
    print("   COMPLAINT AGENT (LangGraph) — TEST SESSION")
    print("=" * 60)

    print("\n[ Running predefined test scenarios ]\n")

    for message in TEST_CONVERSATIONS:
        try:
            response, chat_history = run_agent(
                user_message=message,
                token=TEST_TOKEN,
                chat_history=chat_history,
            )
            print_response(message, response)
        except Exception as e:
            print(f"\n  ERROR during scenario: {str(e)}\n")

    print("\n" + "=" * 60)
    print("   INTERACTIVE MODE — type your message or 'quit' to exit")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("  YOU   : ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("\n  Ending test session. Goodbye!\n")
                break

            response, chat_history = run_agent(
                user_message=user_input,
                token=TEST_TOKEN,
                chat_history=chat_history,
            )
            print_response(user_input, response)

        except KeyboardInterrupt:
            print("\n\n  Session interrupted. Goodbye!\n")
            break
        except Exception as e:
            print(f"\n  ERROR: {str(e)}\n")