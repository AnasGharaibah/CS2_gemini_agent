# ui/styles.py

BUBBLE_STYLE = """
    QLabel {
        background-color: #2ecc71;
        color: white;
        border-radius: 40px; /* Half of width/height to make it circular */
        font-family: Arial;
        font-size: 24px;
        font-weight: bold;
    }
    QLabel:hover {
        background-color: #27ae60;
    }
"""

CHAT_STYLE = """
    QWidget {
        background-color: white;
        border: 1px solid #ddd;
        border-radius: 15px;
    }
    QLabel {
        color: #333;
        font-size: 14px;
        background-color: transparent;
    }
"""