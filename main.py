import sys
import time
import mss
import mss.tools
import numpy as np
import cv2
import pygetwindow as gw
import requests
import base64
import io
import wave
import os
import json
import asyncio
import threading
import pygame
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, 
                             QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt
from pymongo import MongoClient
# --- Third Party Imports ---
from gtts import gTTS
import speech_recognition as sr
import uvicorn
from fastapi import FastAPI, Request

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QStackedWidget, QProgressBar,
                             QLineEdit, QTextEdit, QScrollArea, QFrame, QSizePolicy,
                             QComboBox)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, QUrl
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

# --- CS2 Imports (From Script B) ---
# Ensure the 'CS2' folder containing these modules exists in your directory
try:
    from CS2.quartermaster import Quartermaster
    from CS2.battle_buddy import BattleBuddy
    from CS2.agent_brain import AgentBrain
    from CS2.stt_listener import STTListener
    from CS2.DB import CSGOStorage
    # We comment out the GoogleTTS import from CS2 because Script A provides the class definition inline below
    # from CS2.google_tts import GoogleTTS 
except ImportError:
    print("Warning: CS2 modules not found. Ensure the 'CS2' directory exists.")
    # Mock classes to prevent crash if CS2 folder is missing (for standalone testing)
    class Quartermaster: analyze = lambda s, x: []
    class BattleBuddy: analyze = lambda s, x: []
    class AgentBrain: 
        reset_conversation = lambda s: None
        ask_coach = lambda s, q, l, m, sc: "Mock Response"
    class STTListener: listen_loop = lambda s, a, b: None
    class CSGOStorage: 
        save_round = lambda *a, **k: None
        save_match = lambda *a, **k: None
        save_history_snapshot = lambda *a, **k: None
        save_gsi_snapshot = lambda *a, **k: None


# ==========================================
# PART 1: SCRIPT A (GUI & CLIENT CLASSES)
# ==========================================

# 1. GOOGLE TTS IMPLEMENTATION
class GoogleTTS:
    """Text-to-Speech using Google TTS (gTTS)"""
    
    def __init__(self, language: str = 'en', slow: bool = False):
        self.language = language
        self.slow = slow
    
    def speak(self, text: str, output_path: str, language: Optional[str] = None, slow: Optional[bool] = None) -> str:
        if not text:
            # Avoid crashing on empty text
            print("Warning: TTS received empty text.")
            return ""
        
        lang = language or self.language
        is_slow = slow if slow is not None else self.slow
        
        print(f"Generating speech for: '{text[:30]}...'")
        
        # Create TTS object
        try:
            tts = gTTS(text=text, lang=lang, slow=is_slow)
            
            # Save to file
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save absolute path to ensure QMediaPlayer finds it
            abs_path = str(output_path.resolve())
            tts.save(abs_path)
            print(f"Audio saved to: {abs_path}")
            
            return abs_path
        except Exception as e:
            print(f"TTS Error: {e}")
            return ""

# 2. WORKER THREAD (Handles Video Capture)
class WindowCaptureWorker(QThread):
    frame_captured = pyqtSignal(QImage)

    def __init__(self, target_window_name):
        super().__init__()
        self.target_name = target_window_name
        self.running = True
        self.api_url = "http://192.168.56.1:3000/upload_frame" # Update to your server IP
        self.api_key = "YOUR_API_KEY_HERE"
        self.last_api_time = 0
        self.api_interval = 1.0

    def run(self):
        with mss.mss() as sct:
            while self.running:
                try:
                    # 1. Capture Logic
                    windows = gw.getWindowsWithTitle(self.target_name)
                    if not windows:
                        time.sleep(1)
                        continue
                    
                    window = windows[0]
                    if window.isMinimized or window.width <= 0:
                        time.sleep(1)
                        continue

                    monitor = {"top": window.top, "left": window.left, "width": window.width, "height": window.height}
                    img = sct.grab(monitor)
                    frame_np = np.array(img)
                    frame_bgr = cv2.cvtColor(frame_np, cv2.COLOR_BGRA2BGR)

                    # 2. Update GUI Preview
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame_rgb.shape
                    qt_image = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                    self.frame_captured.emit(qt_image)

                    # 3. API SEND LOGIC
                    if time.time() - self.last_api_time > self.api_interval:
                        # self.send_frame_to_api(frame_bgr) # Uncomment to enable API
                        self.last_api_time = time.time()
                    
                    time.sleep(0.03)

                except Exception as e:
                    print(f"Capture Loop Error: {e}")
                    break
    
    def stop(self):
        self.running = False
        self.wait()

    def send_frame_to_api(self, frame_bgr):
        try:
            resized_frame = cv2.resize(frame_bgr, (640, 480))
            _, buffer = cv2.imencode('.jpg', resized_frame)
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')

            payload = { "image": jpg_as_text, "timestamp": time.time() }
            headers = { "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json" }

            requests.post(self.api_url, json=payload, headers=headers, timeout=2)

        except Exception as e:
            print(f"API Send Error: {e}")

# 3. VOICE WORKER (Updated with GoogleTTS)
class VoiceWorker(QThread):
    status_update = pyqtSignal(str)      
    chat_update = pyqtSignal(str, bool)
   
    def __init__(self):
        super().__init__()
        self.running = True
        self.recognizer = sr.Recognizer()
        
        # --- CONFIGURATION ---
        self.WAKE_WORD = "google"
        self.API_URL = "http://192.168.56.1:3000/ask"
        
        # --- INITIALIZE GOOGLE TTS ---
        self.tts = GoogleTTS(language='en')

        # Audio Player Setup
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

    def run(self):
        self.status_update.emit(f"Say '{self.WAKE_WORD}' to start...")
        
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            while self.running:
                try:
                    print("Waiting for wake word...")
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    
                    try:
                        text = self.recognizer.recognize_google(audio).lower()
                        print(f"Heard: {text}")
                        
                        if self.WAKE_WORD in text:
                            self.trigger_active_mode(source)
                            
                    except sr.UnknownValueError:
                        pass
                        
                    except sr.WaitTimeoutError:
                        pass
                except Exception as e:
                    print(f"Voice Error: {e}")

    def trigger_active_mode(self, source):
        self.status_update.emit("Listening for command...")
        
        try:
            command_audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            self.status_update.emit("Processing...")
            
            wav_data = io.BytesIO()
            with wave.open(wav_data, "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(command_audio.sample_width)
                f.setframerate(command_audio.sample_rate)
                f.writeframes(command_audio.get_raw_data())
            wav_data.seek(0)
            
            self.send_to_api(wav_data)
            
        except sr.WaitTimeoutError:
            self.status_update.emit("Timed out. Say 'Google' again.")

    def send_to_api(self, audio_file):
        try:
            # 1. Convert the audio we just recorded into text using Google Speech Recognition
            with sr.AudioFile(audio_file) as source:
                audio_data = self.recognizer.record(source)
                user_text = self.recognizer.recognize_google(audio_data)
            
            self.chat_update.emit(user_text, True) # Show what you said in the UI

            # 2. Send that text to your FastAPI Coach
            payload = {"question": user_text}
            response = requests.post(self.API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                ai_text = data.get("response", "No response from coach.")
                
                # 3. Show and Speak the response
                self.chat_update.emit(ai_text, False)
                self.status_update.emit("Generating Speech...")
                audio_path = self.tts.speak(ai_text, "response.mp3")
                
                if audio_path:
                    self.play_audio(audio_path)
                
                self.status_update.emit(f"Say '{self.WAKE_WORD}'...")
            else:
                self.status_update.emit("Coach Server Error")
                
        except sr.UnknownValueError:
            self.status_update.emit("Could not understand audio")
        except Exception as e:
            self.status_update.emit("Connection Failed")
            print(f"Detailed Error: {e}")

    def play_audio(self, file_path):
        # Stop previous playback if any
        self.player.stop()
        
        # Load local file
        url = QUrl.fromLocalFile(file_path)
        self.player.setSource(url)
        self.player.play()

    def stop(self):
        self.running = False
        self.wait()

# Statistics Screen
class StatisticsScreen(QWidget):
    def __init__(self):
        super().__init__()
        # --- Database Configuration ---
        # Matches the default in your DB.py
        self.MONGO_URI = "mongodb://localhost:27017/" 
        self.DB_NAME = "CSGO" 
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_layout = QHBoxLayout()
        lbl_title = QLabel("📊 Performance Analysis")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setFixedSize(80, 30)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white; 
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.btn_refresh.clicked.connect(self.refresh_stats)
        
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_refresh)
        self.layout.addLayout(header_layout)
        
        # Stats Container
        self.stats_container = QFrame()
        self.stats_container.setStyleSheet("background-color: #f5f5f5; border-radius: 10px; padding: 15px;")
        self.stats_layout = QVBoxLayout(self.stats_container)
        
        self.layout.addWidget(self.stats_container)
        self.layout.addStretch()
        
        self.setLayout(self.layout)
        
        # Load data immediately on startup
        self.refresh_stats()

    def get_db_stats(self):
        """Connects to Mongo and aggregates data based on DB.py schema."""
        try:
            client = MongoClient(self.MONGO_URI, serverSelectionTimeoutMS=2000)
            db = client[self.DB_NAME]
            
            # Quick connection check
            client.server_info()
            
            matches_col = db["matches"]
            rounds_col = db["rounds"]

            # 1. Basic Counts
            total_matches = matches_col.count_documents({})
            total_rounds = rounds_col.count_documents({})
            
            if total_rounds == 0:
                return {"error": "No data found"}

            # 2. Win Rate 
            # save_round stores a boolean 'win' field directly
            wins = rounds_col.count_documents({"win": True})
            win_rate = (wins / total_rounds) * 100

            # 3. Kills Per Round (KPR)
            # Stats are stored inside the nested 'data' dictionary in DB.py
            pipeline_kills = [
                {"$group": {"_id": None, "avg_kills": {"$avg": "$data.round kills"}}}
            ]
            kpr_res = list(rounds_col.aggregate(pipeline_kills))
            avg_kills = kpr_res[0]['avg_kills'] if kpr_res else 0.0

            # 4. Survival Rate
            # 'died' is stored inside the 'data' dictionary
            deaths = rounds_col.count_documents({"data.died": True})
            survival_rate = ((total_rounds - deaths) / total_rounds) * 100

            return {
                "matches": total_matches,
                "rounds": total_rounds,
                "win_rate": round(win_rate, 1),
                "kpr": round(avg_kills, 2),
                "survival": round(survival_rate, 1)
            }

        except Exception as e:
            print(f"DB Error: {e}")
            return None
        finally:
            if 'client' in locals():
                client.close()

    def refresh_stats(self):
        """Updates the UI with fresh data."""
        # Clear previous widgets
        while self.stats_layout.count():
            child = self.stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        stats = self.get_db_stats()

        if stats is None:
            self.stats_layout.addWidget(QLabel("❌ Database Connection Failed"))
            self.stats_layout.addWidget(QLabel("Ensure MongoDB is running on localhost:27017"))
            return
        
        if "error" in stats:
            self.stats_layout.addWidget(QLabel("⚠️ No match data recorded yet."))
            self.stats_layout.addWidget(QLabel("Play a match with the bot running to generate stats."))
            return

        # Helper function for rows
        def add_stat_row(label, value, color="#333"):
            row = QHBoxLayout()
            lbl_name = QLabel(label)
            lbl_name.setStyleSheet("font-size: 14px; color: #555;")
            
            lbl_val = QLabel(str(value))
            lbl_val.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
            
            row.addWidget(lbl_name)
            row.addStretch()
            row.addWidget(lbl_val)
            
            w = QWidget()
            w.setLayout(row)
            self.stats_layout.addWidget(w)

        # Populate UI
        add_stat_row("Total Matches", stats['matches'])
        add_stat_row("Total Rounds", stats['rounds'])
        
        # Color code Win Rate
        wr_color = "#27ae60" if stats['win_rate'] >= 50 else "#c0392b"
        add_stat_row("Win Rate", f"{stats['win_rate']}%", wr_color)
        
        add_stat_row("Kills Per Round (KPR)", stats['kpr'])
        add_stat_row("Survival Rate", f"{stats['survival']}%")

# 4. CHAT SCREEN
class ChatScreen(QWidget):
    def __init__(self):
        super().__init__()
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.lbl_status = QLabel("Initializing Voice...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #666; font-style: italic; font-size: 12px; margin: 5px;")
        self.main_layout.addWidget(self.lbl_status)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none; background-color: #f9f9f9;")
        
        self.msg_container = QWidget()
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.addStretch()
        self.msg_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.msg_container)
        self.main_layout.addWidget(self.scroll_area)

        input_container = QWidget()
        input_container.setStyleSheet("background-color: white; border-top: 1px solid #ddd;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.setStyleSheet("border: 1px solid #ccc; border-radius: 15px; padding: 8px; background-color: #f0f0f0;")
        self.input_field.returnPressed.connect(self.send_message)

        self.btn_send = QPushButton("➤")
        self.btn_send.setFixedSize(35, 35)
        self.btn_send.setStyleSheet("background-color: #3498db; color: white; border-radius: 17px; font-weight: bold;")
        self.btn_send.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.btn_send)
        self.main_layout.addWidget(input_container)

        # Start Voice Thread
        self.voice_thread = VoiceWorker()
        self.voice_thread.status_update.connect(self.lbl_status.setText)
        self.voice_thread.chat_update.connect(self.add_bubble)
        self.voice_thread.start()

        self.add_bubble("Hello! Say 'Google' to speak to me.", is_user=False)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text: return
        self.add_bubble(text, is_user=True)
        self.input_field.clear()

    def add_bubble(self, text, is_user):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(10, 2, 10, 2)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(220)
        color = '#3498db' if is_user else '#e0e0e0'
        text_color = 'white' if is_user else 'black'
        lbl.setStyleSheet(f"background-color: {color}; color: {text_color}; border-radius: 10px; padding: 10px;")

        if is_user:
            row_layout.addStretch()
            row_layout.addWidget(lbl)
        else:
            row_layout.addWidget(lbl)
            row_layout.addStretch()

        self.msg_layout.addWidget(row_widget)
        QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

# 5. SCREEN SHARE SCREEN (Updated with Dropdown)
class ScreenShareScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel("🖥️ Window Share")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl)

        # --- SELECTION AREA ---
        select_layout = QHBoxLayout()
        
        # Dropdown for windows
        self.combo_windows = QComboBox()
        
        # ADD THIS STYLESHEET
        self.combo_windows.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: white; /* Main box background */
                color: black;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none; /* Optional: Uses default arrow if not set */
                border-left: 1px solid #ccc;
                width: 15px;
            }
            /* This specific part fixes the dropdown list transparency */
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ccc;
                selection-background-color: #3498db;
                color: black;
            }
        """)
        
        select_layout.addWidget(self.combo_windows)
        
        # Refresh button (small icon or text)
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedSize(30, 30)
        self.btn_refresh.setToolTip("Refresh Window List")
        self.btn_refresh.clicked.connect(self.populate_window_list)
        select_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(select_layout)

        # Start/Stop Button
        self.btn_toggle = QPushButton("Start Sharing")
        self.btn_toggle.clicked.connect(self.toggle_sharing)
        self.btn_toggle.setStyleSheet("background-color: #3498db; color: white; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.btn_toggle)

        # Video Feed
        self.video_label = QLabel("Select a window above")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white; border-radius: 10px;")
        
        self.video_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_label.setScaledContents(True)
        self.video_label.setMinimumHeight(200)
        self.video_label.setMaximumHeight(300)
        layout.addWidget(self.video_label)

        self.setLayout(layout)
        
        # Populate list on startup
        self.populate_window_list()

    def populate_window_list(self):
        """Fetches all visible window titles and adds them to the dropdown."""
        self.combo_windows.clear()
        windows = gw.getAllTitles()
        # Filter out empty strings and the app's own window
        clean_list = [w for w in windows if w.strip() and w != "AI Assistant"]
        self.combo_windows.addItems(sorted(clean_list))

    def toggle_sharing(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker = None
            self.btn_toggle.setText("Start Sharing")
            self.btn_toggle.setStyleSheet("background-color: #3498db; color: white; padding: 10px;")
            self.video_label.setText("Stopped")
            self.combo_windows.setEnabled(True) # Re-enable dropdown
            self.btn_refresh.setEnabled(True)
            return

        target_name = self.combo_windows.currentText()
        if not target_name:
            self.video_label.setText("No window selected!")
            return

        self.worker = WindowCaptureWorker(target_name)
        self.worker.frame_captured.connect(self.update_frame)
        self.worker.start()
        
        self.btn_toggle.setText(f"Stop Sharing ({target_name[:10]}...)")
        self.btn_toggle.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px;")
        
        # Disable selection while sharing to prevent errors
        self.combo_windows.setEnabled(False)
        self.btn_refresh.setEnabled(False)

    def update_frame(self, qt_image):
        self.video_label.setPixmap(QPixmap.fromImage(qt_image))

# 6. MAIN CONTROLLER
class SmartAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.is_bubble_mode = False
        self.old_geometry = None
        self.drag_start_point = None
        self.drag_offset = None
        
        self.initUI()
        
    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(380, 600)
        self.center_on_screen()

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # --- A. MAIN APP CONTAINER ---
        self.main_container = QWidget()
        self.main_container.setStyleSheet("QWidget#MainContainer { background-color: white; border-radius: 15px; border: 1px solid #999; }")
        self.main_container.setObjectName("MainContainer")
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 10, 10, 5)
        
        title = QLabel("AI Assistant")
        title.setStyleSheet("border: none; font-weight: bold; font-size: 14px; color: #333;")
        
        btn_minimize = QPushButton("—")
        btn_minimize.setFixedSize(30, 30)
        btn_minimize.setStyleSheet("background-color: #eee; border-radius: 15px; border: none; font-weight: bold;")
        btn_minimize.clicked.connect(self.switch_to_bubble)
        
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet("background-color: #ff5555; color: white; border-radius: 15px; border: none; font-weight: bold;")
        btn_close.clicked.connect(self.close)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(btn_minimize)
        header_layout.addWidget(btn_close)

        # Stacked Screens
        self.stack = QStackedWidget()
        self.stack.addWidget(StatisticsScreen())  # Index 0 (Restored)
        self.stack.addWidget(ChatScreen())        # Index 1
        self.stack.addWidget(ScreenShareScreen()) # Index 2
        
        self.stack.setCurrentIndex(1) # Start on Chat (Index 1)

        # Navigation Bar
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(10, 5, 10, 15)
        
        btn_stats = QPushButton("Stats")
        btn_stats.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        btn_chat = QPushButton("Chat")
        btn_chat.clicked.connect(lambda: self.stack.setCurrentIndex(1))

        btn_share = QPushButton("Share")
        btn_share.clicked.connect(lambda: self.stack.setCurrentIndex(2))

        for btn in [btn_stats, btn_chat, btn_share]:
            btn.setStyleSheet("padding: 8px; background-color: #f5f5f5; border-radius: 8px; font-weight: bold;")
            nav_layout.addWidget(btn)

        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addLayout(header_layout)
        container_layout.addWidget(self.stack)
        container_layout.addLayout(nav_layout)

        # --- B. BUBBLE CONTENT ---
        self.bubble = QLabel("AI")
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setStyleSheet("background-color: #2ecc71; color: white; border-radius: 30px; font-size: 18px; font-weight: bold; border: 2px solid white;")
        self.bubble.hide()

        self.layout.addWidget(self.main_container)
        self.layout.addWidget(self.bubble)
    
    # --- LOGIC ---
    def switch_to_bubble(self):
        self.is_bubble_mode = True
        self.old_geometry = self.geometry()
        self.main_container.hide()
        self.bubble.show()
        screen = self.screen().availableGeometry()
        self.setGeometry(screen.width() - 80, 60, 60, 60)

    def switch_to_normal(self):
        self.is_bubble_mode = False
        self.bubble.hide()
        self.main_container.show()
        if self.old_geometry:
            self.setGeometry(self.old_geometry)
        else:
            self.resize(380, 600)
            self.center_on_screen()

    def center_on_screen(self):
        screen = self.screen().availableGeometry()
        x = (screen.width() - 380) // 2
        y = (screen.height() - 600) // 2
        self.move(x, y)

    # --- DRAG LOGIC ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_point = event.globalPosition().toPoint()
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_offset:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.is_bubble_mode and event.button() == Qt.MouseButton.LeftButton:
            distance = (event.globalPosition().toPoint() - self.drag_start_point).manhattanLength()
            if distance < 5:
                self.switch_to_normal()


# ==========================================
# PART 2: SCRIPT B (BACKEND LOGIC)
# ==========================================

app = FastAPI()

# 1. Initialize AI Modules
brain = AgentBrain()
qm = Quartermaster()
bb = BattleBuddy()
db_storage = CSGOStorage()

# 2. Initialize Audio System
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()
# Using the GoogleTTS class defined in Part 1
tts_engine = GoogleTTS(language='en', slow=False)

# 3. Global State
current_match_file = None
latest_payload = None  
match_history = []    

def update_match_history(payload):
    """Parses and stores round results for the LLM context and DB."""
    global match_history, current_match_file
    
    round_data = payload.get("round", {})
    if round_data.get("phase") != "over":
        return

    player_state = payload.get("player", {}).get("state", {})
    team_side = payload.get("player", {}).get("team")
    map_name = payload.get("map", {}).get("name", "unknown")
    round_num = payload.get("map", {}).get("round", 0)
    
    round_summary = {
        "round": round_num,
        "result": round_data.get("win_team"),
        "reason": round_data.get("bomb"),     # e.g., 'exploded', 'defused'
        "died": player_state.get("health", 0) == 0,
        "round kills": player_state.get("round_kills", 0),
        "damage": player_state.get("round_totaldmg", 0),
        "team_at_time": team_side
    }
    
    # Avoid duplicate entries for the same round
    if not any(r['round'] == round_summary['round'] for r in match_history):
        match_history.append(round_summary)
        
        # Save to Database
        if current_match_file:
            match_id = current_match_file.replace(".jsonl", "")
            is_win = round_summary["result"] == team_side
            db_storage.save_round(match_id, round_num, round_summary, win=is_win)

        # Keep only the last 5 rounds to manage token context
        if len(match_history) > 5:
            match_history.pop(0)

def play_audio_thread(text):
    """Generates and plays TTS in a separate thread to prevent game lag."""
    try:
        filename = f"temp_tts_{datetime.now().strftime('%H%M%S%f')}.mp3"
        tts_engine.speak(text, filename)
        
        if os.path.exists(filename):
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            pygame.mixer.music.unload()
            os.remove(filename)
    except Exception as e:
        print(f"Audio Error: {e}")

def start_stt_listener():
    """Initializes the Push-to-Talk listener."""
    listener = STTListener(
        brain_instance=brain,
        tts_callback=play_audio_thread,
        trigger_key='v' # The key to hold down to talk
    )
    
    listener.listen_loop(
        get_latest_payload_func=lambda: latest_payload,
        get_match_history_func=lambda: match_history
    )

# COACH LOGIC
async def process_coach_logic(payload):
    """Orchestrates automated advice from hardcoded modules."""
    advice_list = []
    
    # 1. Quartermaster (Economy/Buy Phase)
    qm_advice = qm.analyze(payload)
    if qm_advice:
        advice_list.extend(qm_advice)

    # 2. Battle Buddy (Combat Alerts)
    if payload.get("round", {}).get("phase") == "live":
        bb_advice = bb.analyze(payload)
        if bb_advice:
            advice_list.extend(bb_advice)

    for message in advice_list:
        print(f"📢 COACH: {message}")
        threading.Thread(target=play_audio_thread, args=(message,), daemon=True).start()

@app.post("/")
async def gsi_listener(request: Request):
    global current_match_file, latest_payload
    
    try:
        payload = await request.json()
        latest_payload = payload  
    except Exception:
        return {"status": "error"}
    
    map_data = payload.get("map")
    if not map_data:
        return {"status": "ignored"}

    phase = map_data.get("phase")
    round_phase = payload.get("round", {}).get("phase")

    # Update Match History on round end
    if round_phase == "over":
        update_match_history(payload)

    # Logging and Coaching
    if phase == "live":
        if current_match_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            match_id = f"match_{timestamp}"
            current_match_file = f"{match_id}.jsonl"
            brain.reset_conversation() # Clear LLM history for new match
            
            # Save new match to DB
            db_storage.save_match(match_id, map_data.get("name", "unknown"), mode=map_data.get("mode", "unknown"))

        async with aiofiles.open(current_match_file, mode='a') as f:
            await f.write(json.dumps(payload) + "\n")
            
        # Optimized: Save structured history snapshot and raw GSI payload
        match_id = current_match_file.replace(".jsonl", "")
        round_num = map_data.get("round", 0)
        
        db_storage.save_history_snapshot(match_id, round_num, payload)
        db_storage.save_gsi_snapshot(match_id, payload)

        asyncio.create_task(process_coach_logic(payload))
        return {"status": "processed"}

    return {"status": "ok"}

@app.get("/status")
async def get_status():
    """Returns the current game status."""
    if not latest_payload:
        return {"status": "no_game_detected"}
    
    map_data = latest_payload.get("map", {})
    return {
        "status": "active",
        "map": map_data.get("name"),
        "mode": map_data.get("mode"),
        "round": map_data.get("round"),
        "score": {
            "ct": map_data.get("team_ct", {}).get("score"),
            "t": map_data.get("team_t", {}).get("score")
        }
    }

@app.post("/ask")
async def ask_coach_api(request: Request):
    """Allows external devices to ask the coach a question."""
    global latest_payload, match_history
    
    try:
        data = await request.json()
        question = data.get("question")
        include_vision = data.get("vision", True) # Default to True if not specified
    except Exception:
        return {"error": "Invalid JSON"}

    if not question:
        return {"error": "No question provided"}

    if not latest_payload:
        return {"error": "No game data available. Make sure CS2 is running and sending GSI data."}

    # Capture screen if vision is requested
    screenshot_data = None
    if include_vision:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                screenshot_data = mss.tools.to_png(sct_img.rgb, sct_img.size)
        except Exception as e:
            print(f"⚠️ Vision Error in API: {e}")

    # Use a thread to run the synchronous brain.ask_coach to avoid blocking FastAPI
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        brain.ask_coach,
        question,
        latest_payload,
        match_history,
        screenshot_data
    )

    return {"question": question, "response": response}


# ==========================================
# UNIFIED MAIN EXECUTION
# ==========================================
def run_fastapi_server():
    """Runs the FastAPI server in a separate thread."""
    # Changed host to 0.0.0.0 to allow access from other devices on the network
    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="error")

if __name__ == "__main__":
    # 1. Start the FastAPI Backend (Script B) in a daemon thread
    backend_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    backend_thread.start()
    
    # 2. Start the internal STT listener (Script B) in a daemon thread
    threading.Thread(target=start_stt_listener, daemon=True).start()
    
    print("🤖 AI Coach System Online (Backend running on port 3000).")
    
    # 3. Start the PyQt6 GUI (Script A) in the main thread
    # Renamed app to qt_app to avoid conflict with FastAPI app
    qt_app = QApplication(sys.argv)
    window = SmartAssistant()
    window.show()
    sys.exit(qt_app.exec())