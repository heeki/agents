# A2A Fitness System - Streamlit Frontend

A Strava-inspired web interface for the A2A multi-agent fitness system.

## Features

- 🎨 Strava-inspired dark theme with orange accents
- 🏋️ Interactive workout builder with customizable parameters
- 📝 Custom prompt interface for natural language requests
- 🤖 Real-time agent status monitoring
- 💪 Clean, fitness-focused UI/UX

## Setup

### Prerequisites

- Python 3.12+
- uv (Python package manager)
- Running A2A agents (orchestrator, biomechanics-lab, life-sync)

### Installation

1. Create and activate virtual environment:
```bash
cd frontend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
uv pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env to set ORCHESTRATOR_URL if needed
```

## Running the Frontend

### Local Development

Make sure the agents are running first:
```bash
# From project root
make local.orchestrator  # Terminal 1
make local.biomechanics  # Terminal 2
make local.lifesync      # Terminal 3
```

Then start the Streamlit app:
```bash
cd frontend
streamlit run app.py
```

The app will open at http://localhost:8501

### Using the Makefile

From the project root:
```bash
make frontend.setup   # Setup virtual environment
make frontend.run     # Run the Streamlit app
```

## Usage

### Create Workout Tab
1. Select your fitness goal (strength, hypertrophy, etc.)
2. Set duration in minutes
3. Choose location (Home, Gym, Outdoors, Traveling)
4. Select available equipment
5. Optionally target specific muscle groups
6. Add any additional notes
7. Click "Generate Workout Plan"

### Custom Prompt Tab
1. Enter a natural language workout request
2. Click "Submit Custom Request"
3. View your personalized workout plan

### About Tab
- View system metrics
- Learn about the agent architecture
- Understand the design philosophy

## Configuration

### Environment Variables

- `ORCHESTRATOR_URL`: URL of the orchestrator agent (default: http://localhost:8081)

### Connecting to Deployed Agents

To connect to deployed AgentCore agents:
1. Update `.env` with your AgentCore endpoint URL
2. Restart the Streamlit app

## Design

The frontend uses a Strava-inspired design system:
- **Colors**: Orange (#FC4C02), Dark backgrounds (#0F0F0F, #1F1F1F)
- **Typography**: Bold headers, clean sans-serif fonts
- **Layout**: Wide layout with sidebar navigation
- **Components**: Card-based exercise display, metric cards

## Troubleshooting

### Agent Connection Issues
- Verify agents are running: `curl http://localhost:8081/health`
- Check ORCHESTRATOR_URL in `.env`
- Review agent logs

### Styling Issues
- Clear browser cache
- Restart Streamlit server
- Check browser console for errors

## Future Enhancements

- [ ] Workout history and tracking
- [ ] Save/export workout plans
- [ ] Progress tracking and analytics
- [ ] Social sharing features
- [ ] Mobile app version
- [ ] User authentication
