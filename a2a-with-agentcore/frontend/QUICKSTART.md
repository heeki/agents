# A2A Fitness System Frontend - Quick Start Guide

## 🎉 Your Strava-Inspired Fitness Dashboard is Ready!

The Streamlit frontend is now set up and connected to your local A2A agents.

## 🚀 Access the Frontend

Open your browser and navigate to:
```
http://localhost:8501
```

## 📋 What You Can Do

### 1. 🏋️ Create Workout Tab
Build customized workouts with an interactive form:
- Select fitness goal (strength, hypertrophy, cardio, etc.)
- Set duration (10-180 minutes)
- Choose location (Home, Gym, Outdoors, Traveling)
- Select available equipment
- Target specific muscle groups
- Add additional notes/preferences

**Example Workflow:**
1. Goal: "Upper body hypertrophy"
2. Duration: 45 minutes
3. Location: Home
4. Equipment: Dumbbells, Pull-up bar
5. Click "Generate Workout Plan"
6. View your personalized workout!

### 2. 📝 Custom Prompt Tab
Use natural language to request workouts:
- Type any workout request
- Submit and get instant results

**Example Prompts:**
- "I need a quick 30-minute upper body workout at home with just dumbbells"
- "Create a leg day workout for hypertrophy at the gym with about an hour"
- "Give me a 20-minute bodyweight workout I can do while traveling"

### 3. ℹ️ About Tab
- View system metrics
- Learn about the 3-agent architecture
- See design inspiration

## 🎨 Design Features

Your frontend includes:
- **Strava-inspired dark theme** with orange (#FC4C02) accents
- **Real-time agent status** indicator in sidebar
- **Clean workout display** with exercise cards
- **Responsive layout** that works on mobile and desktop
- **Interactive forms** with dropdowns and multi-select

## 🔧 Technical Details

### Architecture
```
Browser (Streamlit) → Orchestrator (8081) → Biomechanics Lab (8082)
                                          → Life Sync (8083)
```

### Agent Communication
- Uses A2A JSON-RPC protocol
- Sends tasks to orchestrator
- Orchestrator coordinates with sub-agents
- Returns validated, personalized workout plans

## 📱 Screenshots

### Main Interface
- Dark background (#0F0F0F)
- Orange accent color (#FC4C02)
- Three-tab layout

### Workout Builder
- Form-based input
- Dropdown selectors
- Multi-select for equipment
- Large orange "Generate Workout Plan" button

### Workout Display
- Structured exercise cards
- Clear exercise names in orange
- Sets, reps, rest times displayed
- Notes and form cues included

## 🛠️ Quick Commands

### Start Everything (from project root)
```bash
# Terminal 1 - Agents (or use docker-compose)
make local.orchestrator &
make local.biomechanics &
make local.lifesync &

# Terminal 2 - Frontend
make frontend.run
```

### Stop Everything
```bash
# Kill agents
pkill -f 'python.*app.py'
pkill -f 'npm run dev'

# Kill frontend
pkill -f streamlit
```

### Restart Frontend Only
```bash
pkill -f streamlit
make frontend.run
```

## 🔄 Updating Configuration

### Connect to Deployed Agents
When you deploy to AWS AgentCore:

1. Edit `frontend/.env`:
```bash
ORCHESTRATOR_URL=https://your-agentcore-endpoint.amazonaws.com
```

2. Restart frontend:
```bash
pkill -f streamlit
make frontend.run
```

## 🐛 Troubleshooting

### "Orchestrator Offline" in Sidebar
- Check agents are running: `curl http://localhost:8081/health`
- Restart agents if needed
- Check logs: `tail -f /tmp/orchestrator.log`

### Workout Request Hangs
- Check all 3 agents are healthy
- Review agent logs for errors
- Ensure AWS credentials are configured (for Bedrock)

### Styling Issues
- Clear browser cache (Cmd/Ctrl + Shift + R)
- Restart Streamlit
- Check browser console for errors

### Port Already in Use
```bash
# Find and kill process on port 8501
lsof -ti:8501 | xargs kill -9
```

## 📊 Test the System

Try these sample requests:

1. **Quick Home Workout**
   - Goal: Upper body strength
   - Duration: 30 minutes
   - Location: Home
   - Equipment: Dumbbells

2. **Gym Session**
   - Goal: Full body hypertrophy
   - Duration: 60 minutes
   - Location: Gym
   - Equipment: All equipment available

3. **Time-Constrained**
   - Custom prompt: "I only have 20 minutes but want an intense full body workout at home with no equipment"

## 🎯 Next Steps

1. **Test the Interface**: Try creating different workout types
2. **Customize Styling**: Edit `app.py` to adjust colors/layout
3. **Add Features**:
   - Workout history
   - Save/export functionality
   - Progress tracking
4. **Deploy**: Update `.env` when agents are deployed to AgentCore

## 📝 Notes

- Frontend runs on port 8501
- Connects to local orchestrator by default (8081)
- Agent status checked every page load
- Workouts stored in session state (cleared on refresh)

---

**Built with:**
- Streamlit 1.31.0
- Python 3.10+
- A2A Protocol
- AWS Bedrock (via agents)

**Inspired by:**
- Strava's clean, fitness-focused design
- Modern SaaS application UX
- Mobile-first responsive layouts
