# ui/bubble_widget.py

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QRect
from PyQt6.QtGui import QColor

# Import our styles and backend
from ui.styles import BUBBLE_STYLE, CHAT_STYLE
from core.ai_service import get_ai_response

class AssistantBubble(QWidget):
    def __init__(self):
        super().__init__()
        self.expanded = False
        self.initUI()

    def initUI(self):
        # Window setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Start as a small bubble
        self.setGeometry(100, 100, 80, 80) 
        self.move_to_bottom_right()

        # Layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # The Visual Content (Label)
        self.content_label = QLabel("AI", self)
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_label.setStyleSheet(BUBBLE_STYLE)
        self.layout.addWidget(self.content_label)

    def move_to_bottom_right(self):
        screen = self.screen().availableGeometry()
        self.move(screen.width() - 120, screen.height() - 150)

    # --- Mouse Events for Dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'oldPos'):
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        # Check if it was a click (not a drag)
        if hasattr(self, 'oldPos'):
            if (event.globalPosition().toPoint() - self.oldPos).manhattanLength() < 5:
                self.toggle_state()
            del self.oldPos

    # --- Logic to Switch Views ---
    def toggle_state(self):
        self.expanded = not self.expanded
        
        if self.expanded:
            # Change to Chat Mode
            self.resize(300, 400)
            self.content_label.setStyleSheet(CHAT_STYLE)
            
            # Example: Fetch data from backend
            response = get_ai_response("Hello")
            self.content_label.setText(f"Chat Mode\n\n{response}")
            
        else:
            # Change back to Bubble Mode
            self.resize(80, 80)
            self.content_label.setStyleSheet(BUBBLE_STYLE)
            self.content_label.setText("AI")