"""
Agent Brain Module
Handles LLM Context Construction, API Communication, and Conversation Memory.
"""
import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
import PIL.Image
import io

# Load environment variables
load_dotenv()

class AgentBrain:
    def __init__(self):
        # 1. API KEY SETUP
        self.api_key = os.getenv("GEMINI_API_KEY") 

        if not self.api_key:
            print("⚠️ CRITICAL ERROR: GEMINI_API_KEY is missing!")
            
        self.client = genai.Client(api_key=self.api_key)
        
        self._min_request_interval = 4.0  
        self._timestamp_file = ".last_api_call"
        
        self._enforce_startup_cooldown()

        self.system_instruction = """
        You are an expert Counter-Strike 2 (CS2) Coach. 
        Your goal is to provide brief, high-level tactical and strategic advice based on live game state, match history, and visual information (screenshots).

        GUIDELINES:
        - Be concise (1-2 sentences). 
        - Use 'RECENT HISTORY' to spot patterns.
        - Analyze 'Reason' for round losses.
        - If a screenshot is provided, analyze enemy positions, crosshair placement, utility (smokes/flashes), and radar.
        - Use a professional, calm, and supportive coaching tone.
        """
        
        self.chat_session = self.client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.7
            )
        )
        print("🧠 Agent Brain Initialized (with Persistent Memory).")

    def _wait_for_cooldown(self):
        """Internal helper to wait if rate limited."""
        last_time = self._get_last_call_time()
        current_time = time.time()
        time_since_last = current_time - last_time
        
        if time_since_last < self._min_request_interval:
            wait_time = self._min_request_interval - time_since_last
            print(f"⏳ Throttling: Cooling down for {wait_time:.1f}s...")
            time.sleep(wait_time)

    def _get_last_call_time(self):
        """Reads the last API call timestamp from disk."""
        if os.path.exists(self._timestamp_file):
            try:
                with open(self._timestamp_file, 'r') as f:
                    return float(f.read().strip())
            except:
                return 0.0
        return 0.0

    def _save_last_call_time(self):
        """Writes the current timestamp to disk."""
        try:
            with open(self._timestamp_file, 'w') as f:
                f.write(str(time.time()))
        except Exception as e:
            print(f"⚠️ Could not save timestamp: {e}")

    def _enforce_startup_cooldown(self):
        """Checks disk memory on startup to prevent restart spam."""
        last_time = self._get_last_call_time()
        time_since = time.time() - last_time
        
        if time_since < self._min_request_interval:
            wait_needed = self._min_request_interval - time_since
            print(f"🛑 Startup Safety: Cooling down from previous run for {wait_needed:.1f}s...")
            time.sleep(wait_needed + 0.5) 

    def build_context(self, payload, history=None):
        """Compresses the GSI JSON + Match History into a clean text summary."""
        if not payload or "map" not in payload:
            return "Game state unknown (Main Menu or Loading)."

        map_data = payload.get("map", {})
        player = payload.get("player", {})
        
        map_name = map_data.get("name", "Unknown Map")
        score_ct = map_data.get("team_ct", {}).get("score", 0)
        score_t = map_data.get("team_t", {}).get("score", 0)
        round_phase = payload.get("round", {}).get("phase", "unknown")
        
        team_side = player.get("team", "Spectator")
        money = player.get("state", {}).get("money", 0)
        health = player.get("state", {}).get("health", 0)
        stats = player.get("match_stats", {})
        kills = stats.get("kills", 0)
        deaths = stats.get("deaths", 0)
        
        weapons_list = []
        weapons = player.get("weapons", {})
        for k, w in weapons.items():
            name = w.get("name", "unknown").replace("weapon_", "")
            if w.get("type") in ['Rifle', 'SniperRifle', 'Pistol', 'Submachine Gun', 'Shotgun', 'Machine Gun', 'Grenade']:
                weapons_list.append(name)
        
        history_text = "No previous round history available."
        if history:
            history_lines = []
            for r in history:
                impact_str = f"{r.get('kills')}k | {r.get('damage')}dmg"
                result_str = "Won" if r.get('result') == team_side else "Lost"
                line = f"- Rd {r.get('round')}: {result_str} via {r.get('reason', 'Elimination')}. Stats: {impact_str}."
                history_lines.append(line)
            history_text = "\n".join(history_lines)

        context = f"""
        CURRENT MATCH CONTEXT:
        - Map: {map_name}
        - Score: CT {score_ct} - T {score_t}
        - Round Phase: {round_phase}
        - Player: {team_side} Side | HP: {health} | Money: ${money}
        - K/D Ratio: {kills}/{deaths}
        - Loadout: {', '.join(weapons_list)}
        
        RECENT HISTORY (Last 3 Rounds):
        {history_text}
        """
        return context

    def ask_coach(self, user_query, gsi_payload, match_history=None, image_data=None):
        """Sends user query to the chat with Persistent Rate Limiting."""
        
        # 1. ENFORCE COOLDOWN (Wait instead of blocking if possible)
        self._wait_for_cooldown()

        if not user_query or len(user_query.strip()) < 2:
            return "I didn't catch that."


        current_game_context = self.build_context(gsi_payload, match_history)
        full_prompt = f"""
        [SYSTEM UPDATE: CURRENT GAME STATE]
        {current_game_context}
        [END SYSTEM UPDATE]

        USER QUESTION: {user_query}
        """
        
        # Prepare content list for multimodal support
        content = [full_prompt]
        if image_data:
            try:
                img = PIL.Image.open(io.BytesIO(image_data))
                content.append(img)
            except Exception as e:
                print(f"⚠️ Image processing error: {e}")

        try:
            self._save_last_call_time() 
            response = self.chat_session.send_message(content)
            return response.text
            
        except Exception as e:
            print(f"❌ Gemini API Error: {e}")
            # Handle Rate Limiting (429)
            if "429" in str(e):
                print("⚠️ 429 Too Many Requests detected. Increasing cooldown and waiting...")
                time.sleep(5) # Extra wait on top of interval
                return "My brain is a bit tired from too many questions. Give me a few seconds."

            # If we get a 409 or similar session error, resetting might help next time
            if "409" in str(e):
                print("🔄 409 Conflict detected. Attempting to reset conversation session...")
                self.reset_conversation()
            return "My brain is overloaded. Give me a second."

    def reset_conversation(self):
        print("🧹 Resetting Coach Conversation Memory...")
        self.chat_session = self.client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.7
            )
        )