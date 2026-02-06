"""Streamlit Frontend for Momentum Fitness - Modern Dark Design."""

import json
import os
import uuid
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8081")
ORCHESTRATOR_ARN = os.getenv("ORCHESTRATOR_RUNTIME_ARN", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "")
USE_AGENTCORE_BOTO3 = bool(ORCHESTRATOR_ARN and ORCHESTRATOR_ARN != "NOT_SET")

# Runtime/Session IDs and ARNs
ORCHESTRATOR_RUNTIME_ID = os.getenv("ORCHESTRATOR_RUNTIME_ID", "")
BIOMECHANICS_RUNTIME_ID = os.getenv("BIOMECHANICS_RUNTIME_ID", "")
LIFESYNC_RUNTIME_ID = os.getenv("LIFESYNC_RUNTIME_ID", "")

# Sub-agent ARNs (for deployment info)
BIOMECHANICS_ARN = os.getenv("BIOMECHANICS_RUNTIME_ARN", "")
LIFESYNC_ARN = os.getenv("LIFESYNC_RUNTIME_ARN", "")

# Stockpeers-inspired color palette
BG_DARK = "#1a2332"  # Dark navy background
BG_CARD = "#243447"  # Darker navy for cards
BORDER_DARK = "#2d3b4e"  # Subtle dark blue border
TEXT_PRIMARY = "#FFFFFF"  # White text
TEXT_SECONDARY = "#a8b2c1"  # Light gray secondary text
ACCENT_BLUE = "#5b6fff"  # Purple-blue accent
ACCENT_PURPLE = "#7c3aed"  # Deep purple
ACCENT_CYAN = "#22D3EE"  # Cyan
SUCCESS_GREEN = "#10b981"  # Green for positive indicators
ERROR_RED = "#ef4444"  # Red for negative indicators


def apply_dark_styling():
    """Apply stockpeers-inspired dark navy styling."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        /* Dark navy background */
        .stApp {{
            background: {BG_DARK};
            color: {TEXT_PRIMARY};
            font-family: 'Inter', sans-serif;
        }}

        /* Center content with max width */
        .main .block-container {{
            max-width: 1200px;
            padding-left: 2rem;
            padding-right: 2rem;
            margin: 0 auto;
        }}

        /* Modern headers */
        h1 {{
            color: {TEXT_PRIMARY};
            font-size: 2.25rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 0.5rem;
        }}

        h2 {{
            color: {TEXT_PRIMARY};
            font-size: 1.5rem;
            font-weight: 600;
            letter-spacing: -0.01em;
            margin-top: 2rem;
        }}

        h3 {{
            color: {TEXT_PRIMARY};
            font-size: 1.25rem;
            font-weight: 600;
            margin-top: 1.5rem;
        }}

        /* Input labels white */
        .stTextInput > label,
        .stTextArea > label,
        .stNumberInput > label,
        .stSelectbox > label,
        .stMultiSelect > label {{
            color: {TEXT_PRIMARY} !important;
            font-weight: 500;
        }}

        /* Input fields dark mode */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stNumberInput > div > div > input,
        .stMultiSelect > div > div {{
            background-color: {BG_CARD};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_DARK};
            border-radius: 12px;
        }}

        /* Selectbox dark mode */
        .stSelectbox > div > div {{
            background-color: {BG_CARD} !important;
            color: {TEXT_PRIMARY} !important;
            border: 1px solid {BORDER_DARK};
            border-radius: 12px;
        }}

        /* Selectbox dropdown value text */
        .stSelectbox div[data-baseweb="select"] > div {{
            background-color: {BG_CARD} !important;
            color: {TEXT_PRIMARY} !important;
        }}

        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus,
        .stNumberInput > div > div > input:focus {{
            border-color: {ACCENT_BLUE};
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2);
        }}

        /* Modern buttons */
        .stButton > button {{
            background: {ACCENT_BLUE};
            color: {TEXT_PRIMARY};
            font-weight: 600;
            font-size: 1rem;
            padding: 0.875rem 2rem;
            border-radius: 12px;
            border: none;
            width: 100%;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        }}

        .stButton > button:hover {{
            background: {ACCENT_PURPLE} !important;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
            transform: translateY(-2px);
        }}

        .stButton > button:active {{
            background: {ACCENT_BLUE} !important;
            transform: translateY(0px);
        }}

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 1rem;
            background-color: transparent;
            border-bottom: 1px solid {BORDER_DARK};
        }}

        .stTabs [data-baseweb="tab"] {{
            background-color: transparent;
            color: {TEXT_SECONDARY};
            font-weight: 600;
            padding: 1rem 1.5rem;
            border-bottom: 2px solid transparent;
        }}

        .stTabs [aria-selected="true"] {{
            color: {ACCENT_BLUE};
            border-bottom: 2px solid {ACCENT_BLUE};
        }}

        /* Expanders */
        .streamlit-expanderHeader {{
            background-color: {BG_CARD};
            border: 1px solid {BORDER_DARK};
            border-radius: 12px;
            color: {TEXT_PRIMARY};
            font-weight: 600;
        }}

        .streamlit-expanderHeader:hover {{
            background-color: {BG_CARD};
            border-color: {ACCENT_BLUE};
        }}

        /* Alert boxes */
        .stAlert {{
            background-color: {BG_CARD};
            border: 1px solid {BORDER_DARK};
            border-radius: 12px;
            padding: 1rem;
        }}

        /* Code blocks */
        .stCodeBlock {{
            background-color: {BG_CARD};
            border: 1px solid {BORDER_DARK};
            border-radius: 12px;
        }}

        code {{
            background-color: {BG_CARD};
            color: {ACCENT_BLUE};
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }}

        /* Multiselect pills */
        .stMultiSelect [data-baseweb="tag"] {{
            background-color: {ACCENT_BLUE} !important;
            color: {TEXT_PRIMARY} !important;
            border-radius: 20px;
        }}

        /* Hide streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _get_agentcore_client():
    """Get boto3 AgentCore client."""
    if "agentcore_client" not in st.session_state:
        import boto3
        if AWS_PROFILE:
            session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
            st.session_state.agentcore_client = session.client("bedrock-agentcore")
        else:
            st.session_state.agentcore_client = boto3.client(
                "bedrock-agentcore", region_name=AWS_REGION
            )
    return st.session_state.agentcore_client


def send_workout_request(prompt: str) -> dict[str, Any]:
    """Send workout request to orchestrator."""
    task_id = f"workout-{uuid.uuid4().hex[:8]}"

    request_payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "tasks/send",
        "params": {
            "task": {
                "id": task_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": prompt}],
                },
            }
        },
    }

    if USE_AGENTCORE_BOTO3:
        try:
            client = _get_agentcore_client()
            response = client.invoke_agent_runtime(
                agentRuntimeArn=ORCHESTRATOR_ARN,
                qualifier="DEFAULT",
                contentType="application/json",
                accept="application/json",
                payload=json.dumps(request_payload),
            )

            # Capture session ID from the invoke_agent_runtime response
            session_id = response.get("sessionId")
            if session_id:
                st.session_state.orchestrator_session_id = session_id
                # Debug log
                print(f"Captured orchestrator session ID: {session_id}")
            else:
                print(f"No sessionId in response. Keys: {response.keys()}")

            response_body = response.get("response")
            raw = ""
            if response_body:
                for chunk in response_body:
                    raw += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk

            parsed_response = json.loads(raw)

            # Debug: show full response
            if "result" in parsed_response and "result" in parsed_response["result"]:
                result_parts = parsed_response["result"]["result"].get("parts", [])
                for part in result_parts:
                    if part.get("type") == "text":
                        full_text = part.get("text", "")
                        # Store for debugging
                        st.session_state.last_full_response = full_text

            return parsed_response
        except Exception as e:
            st.error(f"⚠️ Error: {e}")
            import traceback
            st.error(f"Traceback: {traceback.format_exc()}")
            return {}
    else:
        try:
            url = f"{ORCHESTRATOR_URL}/"
            response = requests.post(url, json=request_payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"⚠️ Error: {e}")
            return {}


def render_exercise_card(exercise: dict[str, Any], index: int):
    """Render a single exercise card."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {BG_CARD} 0%, {BG_DARK} 100%);
            border: 1px solid {BORDER_DARK};
            border-radius: 16px;
            padding: 2rem;
            margin: 1.5rem 0;
            transition: all 0.3s ease;
        ">
            <div style="color: {TEXT_PRIMARY}; font-size: 1.5rem; font-weight: 700; margin-bottom: 1rem;">
                {index}. {exercise.get('name', 'Exercise')}
            </div>
            <div style="color: {TEXT_SECONDARY}; font-size: 1rem; line-height: 1.8;">
                <div style="margin: 0.5rem 0;">💪 <strong>Muscle Group:</strong> {exercise.get('muscle_group', 'N/A')}</div>
                <div style="margin: 0.5rem 0;">🏋️ <strong>Equipment:</strong> {exercise.get('equipment', 'N/A')}</div>
                <div style="margin: 0.5rem 0;">📊 <strong>Sets:</strong> {exercise.get('sets', 'N/A')}</div>
                <div style="margin: 0.5rem 0;">🔄 <strong>Reps:</strong> {exercise.get('reps', 'N/A')}</div>
                <div style="margin: 0.5rem 0;">⏱️ <strong>Rest:</strong> {exercise.get('rest', 'N/A')}</div>
                {f'<div style="margin: 0.5rem 0;">⏰ <strong>Duration:</strong> {exercise.get("duration")}</div>' if exercise.get('duration') else ''}
                {f'<div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid {BORDER_DARK}; color: {ACCENT_BLUE}; font-style: italic;">💡 {exercise.get("notes")}</div>' if exercise.get('notes') else ''}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_time_slots(time_slots: list[str]):
    """Render time slots in a horizontal row."""
    slots_html = '<div style="display: flex; gap: 1rem; overflow-x: auto; padding: 1rem 0;">'

    for slot in time_slots:
        # Escape the slot value to prevent HTML issues
        safe_slot = str(slot).replace('<', '&lt;').replace('>', '&gt;')
        slots_html += f'<div style="background: linear-gradient(135deg, {BG_CARD} 0%, {BG_DARK} 100%); border: 1px solid {BORDER_DARK}; border-radius: 12px; padding: 1rem 1.5rem; min-width: 150px; text-align: center; color: {TEXT_PRIMARY}; font-weight: 600; flex-shrink: 0; transition: all 0.3s ease; cursor: pointer;" onmouseover="this.style.borderColor=\'{ACCENT_BLUE}\'; this.style.boxShadow=\'0 0 20px rgba(96, 165, 250, 0.3)\';" onmouseout="this.style.borderColor=\'{BORDER_DARK}\'; this.style.boxShadow=\'none\';">🕐 {safe_slot}</div>'

    slots_html += '</div>'
    st.markdown(slots_html, unsafe_allow_html=True)


def main():
    """Main application."""
    st.set_page_config(
        page_title="Momentum Fitness",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    apply_dark_styling()

    # Hero section
    st.markdown(
        f"""
        <div style="margin: 2rem 0 3rem 0;">
            <h1 style="margin-bottom: 0.5rem;">⚡ Momentum Fitness</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: 1rem; margin-top: 0.5rem; font-weight: 400;">
                AI-powered workout planning that adapts to your life
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Tabs
    tab1, tab2, tab3 = st.tabs(["🏋️ Create Workout", "⚙️ Deployment Info", "📊 Observability Logs"])

    with tab1:
        st.markdown("## Build Your Workout")

        col1, col2 = st.columns(2)

        with col1:
            goal = st.selectbox(
                "Fitness Goal",
                ["Cardio endurance", "Upper body strength", "Lower body strength", "Full body strength",
                 "Upper body hypertrophy", "Lower body hypertrophy",
                 "General fitness", "Athletic performance"],
            )

            duration = st.number_input(
                "Duration (minutes)",
                min_value=10,
                max_value=180,
                value=45,
                step=5,
            )

            muscle_groups = st.multiselect(
                "Target Muscle Groups",
                ["Chest", "Back", "Shoulders", "Arms", "Legs", "Core", "Glutes", "Calves"],
                default=["Legs", "Core"]
            )

        with col2:
            exercise_types = st.multiselect(
                "Exercise Types",
                ["Compound", "Isolation", "Cardio", "Plyometric", "Isometric"],
                default=["Cardio"]
            )

            equipment = st.multiselect(
                "Available Equipment",
                ["Barbell", "Dumbbells", "Bench", "Squat Rack", "Pull-up Bar",
                 "Cables", "Machines", "Resistance Bands", "Kettlebells", "Treadmill",
                 "Bike", "Rowing Machine", "Bodyweight Only"],
                default=["Treadmill"]
            )

            additional_notes = st.text_area(
                "Additional Notes",
                placeholder="Any injuries, preferences, or special requirements...",
                height=100
            )

        # Build prompt from inputs
        if st.button("🚀 Generate Workout Plan", use_container_width=True):
            prompt_parts = [f"Create a {goal.lower()} workout"]

            if duration:
                prompt_parts.append(f"for {duration} minutes")

            if muscle_groups:
                prompt_parts.append(f"targeting {', '.join(muscle_groups).lower()}")

            if equipment:
                prompt_parts.append(f"using {', '.join(equipment).lower()}")
            elif not equipment:
                prompt_parts.append("with bodyweight only")

            if exercise_types:
                prompt_parts.append(f"with {', '.join(exercise_types).lower()} exercises")

            prompt = " ".join(prompt_parts) + "."

            if additional_notes:
                prompt += f" Note: {additional_notes}"

            # Show progress
            with st.status("🤖 Generating your workout plan...", expanded=True) as status:
                st.write("📤 Sending request to orchestrator...")
                st.write("🧬 Consulting Biomechanics Lab...")
                st.write("📅 Validating with Life Sync Agent...")

                response = send_workout_request(prompt)

                if response:
                    status.update(label="✅ Workout plan ready!", state="complete", expanded=False)
                else:
                    status.update(label="❌ Failed", state="error", expanded=True)

            # Render results
            if response and "result" in response:
                result = response["result"]

                if "result" in result:
                    parts = result["result"].get("parts", [])

                    structured_data = None
                    text_response = ""

                    for part in parts:
                        if part.get("type") == "text":
                            text_response = part.get("text", "")
                        elif part.get("type") == "data":
                            structured_data = part.get("data", {})

                    # Try to extract JSON from text if no structured data
                    if not structured_data and text_response:
                        import re
                        json_match = re.search(r'```json\s*\n?(.*?)\n?```', text_response, re.DOTALL)
                        if json_match:
                            try:
                                structured_data = json.loads(json_match.group(1).strip())
                            except:
                                pass

                    # Render workout
                    if structured_data and "workout" in structured_data:
                        workout = structured_data["workout"]

                        st.markdown("---")
                        st.markdown(f"## {workout.get('title', 'Your Workout Plan')}")

                        # Exercises
                        exercises = workout.get("exercises", [])
                        for idx, exercise in enumerate(exercises, 1):
                            render_exercise_card(exercise, idx)

                        # Schedule
                        if "schedule" in structured_data:
                            schedule = structured_data["schedule"]

                            st.markdown("---")
                            st.markdown("## 📅 Available Time Slots")

                            if schedule.get("message"):
                                st.markdown(f'<p style="color: {TEXT_PRIMARY}; font-size: 1rem; margin-bottom: 1rem;">{schedule["message"]}</p>', unsafe_allow_html=True)

                            if schedule.get("available_times"):
                                render_time_slots(schedule["available_times"])
                    else:
                        # Fallback to text display
                        st.markdown("### Response")
                        st.write(text_response)

                        # Show full response for debugging
                        if st.session_state.get("last_full_response"):
                            with st.expander("🔍 Debug: Full Agent Response"):
                                st.code(st.session_state.last_full_response, language="text")

                        with st.expander("🔍 Debug: Raw Response"):
                            st.json(response)

    with tab2:
        st.markdown("## Deployment Configuration")

        # Connection Status
        st.markdown("### 🔗 Connection Status")
        if USE_AGENTCORE_BOTO3:
            st.success("✅ Connected to AWS AgentCore")
        else:
            st.info("🔄 Using local HTTP mode")

        # Agent Details - Same card styling for all three agents
        st.markdown(f'<h3 style="color: {TEXT_PRIMARY}; margin-top: 2rem;">Agent Runtime Details</h3>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            <div style="background: {BG_CARD}; border: 1px solid {BORDER_DARK}; border-radius: 12px; padding: 1.5rem; height: 100%;">
                <div style="color: {ACCENT_BLUE}; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem;">🧠 Orchestrator</div>
                <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem; line-height: 1.8;">
                    <div style="margin-bottom: 0.75rem;">
                        <strong style="color: {TEXT_PRIMARY};">Runtime ARN:</strong><br/>
                        <span style="font-family: monospace; font-size: 0.75rem; color: {ACCENT_BLUE}; word-break: break-all;">
                            {ORCHESTRATOR_ARN or 'Not configured'}
                        </span>
                    </div>
                    <div><strong style="color: {TEXT_PRIMARY};">Region:</strong> {AWS_REGION}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background: {BG_CARD}; border: 1px solid {BORDER_DARK}; border-radius: 12px; padding: 1.5rem; height: 100%;">
                <div style="color: {ACCENT_BLUE}; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem;">🧬 Biomechanics Lab</div>
                <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem; line-height: 1.8;">
                    <div style="margin-bottom: 0.75rem;">
                        <strong style="color: {TEXT_PRIMARY};">Runtime ARN:</strong><br/>
                        <span style="font-family: monospace; font-size: 0.75rem; color: {ACCENT_BLUE}; word-break: break-all;">
                            {BIOMECHANICS_ARN or 'Not configured'}
                        </span>
                    </div>
                    <div><strong style="color: {TEXT_PRIMARY};">Region:</strong> {AWS_REGION}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="background: {BG_CARD}; border: 1px solid {BORDER_DARK}; border-radius: 12px; padding: 1.5rem; height: 100%;">
                <div style="color: {ACCENT_BLUE}; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem;">📅 Life Sync</div>
                <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem; line-height: 1.8;">
                    <div style="margin-bottom: 0.75rem;">
                        <strong style="color: {TEXT_PRIMARY};">Runtime ARN:</strong><br/>
                        <span style="font-family: monospace; font-size: 0.75rem; color: {ACCENT_BLUE}; word-break: break-all;">
                            {LIFESYNC_ARN or 'Not configured'}
                        </span>
                    </div>
                    <div><strong style="color: {TEXT_PRIMARY};">Region:</strong> {AWS_REGION}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f'<h3 style="color: {TEXT_PRIMARY}; margin-top: 2rem;">🔧 Environment Variables</h3>', unsafe_allow_html=True)
        with st.expander("View Configuration"):
            env_config = {
                "ORCHESTRATOR_URL": ORCHESTRATOR_URL,
                "ORCHESTRATOR_RUNTIME_ARN": ORCHESTRATOR_ARN or "Not set",
                "AWS_REGION": AWS_REGION,
                "AWS_PROFILE": AWS_PROFILE or "Not set",
                "USE_AGENTCORE_BOTO3": USE_AGENTCORE_BOTO3,
            }
            st.json(env_config)

    with tab3:
        st.markdown("## Live Observability Logs")

        if USE_AGENTCORE_BOTO3:
            # Agent selector - auto-loads logs when changed
            selected_agent = st.selectbox(
                "Select Agent",
                ["🧠 Orchestrator", "🧬 Biomechanics Lab", "📅 Life Sync"],
                key="agent_selector"
            )

            # Map selection to ARN
            agent_arn_map = {
                "🧠 Orchestrator": ORCHESTRATOR_ARN,
                "🧬 Biomechanics Lab": BIOMECHANICS_ARN,
                "📅 Life Sync": LIFESYNC_ARN
            }

            selected_arn = agent_arn_map.get(selected_agent)

            if selected_arn:
                try:
                    # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-name
                    runtime_name = selected_arn.split("/")[-1]
                    log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_name}-DEFAULT"

                    # Display log group name at top with white label
                    st.markdown(f'<p style="color: {TEXT_PRIMARY}; margin-bottom: 1rem;"><strong>Log Group:</strong> <code style="color: {ACCENT_BLUE};">{log_group_name}</code></p>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error parsing ARN: {e}")
                    selected_arn = None

            if selected_arn:
                try:
                    runtime_name = selected_arn.split("/")[-1]
                    log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_name}-DEFAULT"

                    # Auto-load logs (no button needed)
                    if True:
                        with st.spinner("Fetching logs from CloudWatch..."):
                            try:
                                import boto3
                                from datetime import datetime, timedelta

                                if AWS_PROFILE:
                                    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
                                    logs_client = session.client('logs')
                                else:
                                    logs_client = boto3.client('logs', region_name=AWS_REGION)

                                # Get logs from last 30 minutes
                                end_time = datetime.now()
                                start_time = end_time - timedelta(minutes=30)

                                # Get log streams
                                streams_response = logs_client.describe_log_streams(
                                    logGroupName=log_group_name,
                                    orderBy='LastEventTime',
                                    descending=True,
                                    limit=5
                                )

                                all_logs = []
                                for stream in streams_response.get('logStreams', []):
                                    stream_name = stream['logStreamName']

                                    # Get events from this stream
                                    events_response = logs_client.get_log_events(
                                        logGroupName=log_group_name,
                                        logStreamName=stream_name,
                                        startTime=int(start_time.timestamp() * 1000),
                                        endTime=int(end_time.timestamp() * 1000),
                                        limit=50
                                    )

                                    for event in events_response.get('events', []):
                                        timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                                        all_logs.append({
                                            'timestamp': timestamp,
                                            'message': event['message']
                                        })

                                # Sort by timestamp
                                all_logs.sort(key=lambda x: x['timestamp'], reverse=True)

                                if all_logs:
                                    st.success(f"✅ Fetched {len(all_logs)} log entries from last 30 minutes")

                                    # Display logs
                                    log_text = "\n".join([
                                        f"[{log['timestamp'].strftime('%H:%M:%S')}] {log['message']}"
                                        for log in all_logs[:100]  # Show last 100 entries
                                    ])

                                    st.code(log_text, language="log")
                                else:
                                    st.info("No logs found in the last 30 minutes")

                            except Exception as e:
                                st.error(f"❌ Error fetching logs: {e}")

                except Exception as e:
                    st.error(f"Error fetching logs: {e}")
            else:
                st.warning(f"ARN not configured for {selected_agent}")
        else:
            st.info("💡 Live logs are available when using AgentCore mode")


if __name__ == "__main__":
    main()
