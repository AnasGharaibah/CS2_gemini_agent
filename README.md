# CS2 AI Coach Assistant

An intelligent, real-time coaching assistant for Counter-Strike 2. This project leverages the Google Gemini 2.0 Flash model to provide tactical advice by analyzing live game state (GSI), screen captures, and match history. It features a PyQt6-based GUI with voice interaction and a FastAPI backend.

## 🚀 Features

- **Real-time Coaching**: Brief, high-level tactical advice based on live game events.
- **Multimodal Analysis**: Uses screen captures to analyze enemy positions, utility, and crosshair placement.
- **Voice Interaction**: Integrated Speech-to-Text (STT) and Text-to-Speech (TTS) for hands-free coaching.
- **Match History & Statistics**: Stores match data in MongoDB and provides a dashboard for performance review.
- **GSI Integration**: Listens to CS2 Game State Integration for precise game data.
- **Remote Access**: FastAPI backend allows external devices (like mobile tablets) to query the coach.

## 🛠 Tech Stack

- **Language**: Python 3.9+
- **GUI**: PyQt6
- **Backend**: FastAPI, Uvicorn
- **Database**: MongoDB (via `pymongo`)
- **AI/LLM**: Google Gemini API (`google-genai`)
- **Image Processing**: OpenCV, MSS, NumPy, PIL
- **Voice/Audio**: `speech_recognition`, `gTTS`, `pygame`, `QtMultimedia`

## 📋 Requirements

### Prerequisites
- [Python 3.9+](https://www.python.org/downloads/)
- [MongoDB](https://www.mongodb.com/try/download/community) (Running locally on default port 27017)
- [Counter-Strike 2](https://store.steampowered.com/app/730/CounterStrike_2/)
- [Google Gemini API Key](https://aistudio.google.com/app/apikey)

### Dependencies
Install the required Python packages:
```bash
pip install pyqt6 fastapi uvicorn pymongo google-genai python-dotenv mss numpy opencv-python pygetwindow requests pygame aiofiles gTTS SpeechRecognition Pillow
```

## ⚙️ Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd CS2_gemini_agent-main
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. **CS2 GSI Configuration**:
   To enable Game State Integration, create a file named `gamestate_integration_coach.cfg` in your CS2 cfg directory (e.g., `C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg`) with the following content:
   ```cfg
   "CS2 AI Coach"
   {
    "uri" "http://127.0.0.1:3000"
    "timeout" "1.1"
    "buffer"  "0.05"
    "throttle" "0.0.05"
    "data"
    {
      "map" "1"
      "round" "1"
      "player_id" "1"
      "player_state" "1"
      "player_match_stats"   "1"
      "player_weapons" "1"
      "allplayers_id" "1"
      "allplayers_state" "1"
      "allplayers_position" "1"
      "phase_countdowns" "1"
    }
   }
   ```

4. **Start MongoDB**: Ensure your MongoDB service is running on `localhost:27017`.

## 🏃 Run Commands
1. **Run CS2**
 
2. **Main Application**:
   Starts the GUI, FastAPI backend, and STT listener.
   ```bash
   python main.py
   ```

3. **Standalone Database Management**:
   Check or initialize the database.
   ```bash
   python database.py
   ```

4. **Verify Routes**:
   Verify that the FastAPI backend is correctly registered.
   ```bash
   python CS2/verify_routes.py
   ```

## 📂 Project Structure

```text
├── main.py               # Main entry point (GUI + Backend + Threads)
├── database.py           # MongoDB storage logic and schema
├── .env                  # Environment variables (API Keys)
├── CS2/
│   ├── agent_brain.py    # Gemini API integration and context building
│   ├── DB.py             # Alternative DB interface
│   ├── battle_buddy.py   # Analysis logic (placeholder/extension)
│   ├── quartermaster.py  # Economy/Loadout analysis
│   ├── stt_listener.py   # Speech-to-Text loop
│   ├── google_tts.py     # Text-to-Speech implementation
│   └── verify_routes.py  # Utility to check API routes
├── core/                 # Core AI service abstractions
├── ui/                   # PyQt6 UI components (widgets, styles)
└── assets/               # Icons and images
```

## 📡 API Endpoints (Port 3000)

- `POST /gsi`: Receives data from CS2 Game State Integration.
- `GET /status`: Returns current game status (map, score, etc.).
- `POST /ask`: Allows external queries to the coach.
  - Body: `{"question": "What should I buy?", "vision": true}`

## 🧪 Testing

- Run `python CS2/verify_routes.py` to ensure the backend is running correctly.
- Ensure CS2 is running and GSI is active by checking the logs in the console after starting `main.py`.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details (if available).

## Contributers
https://github.com/AnasGharaibah
https://github.com/MuradSalaytah
https://github.com/Enraged1
https://github.com/qusain2624
