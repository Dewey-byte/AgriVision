from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

def create_card(title):
    container = QWidget()
    layout = QVBoxLayout()
    container.setLayout(layout)

    container.setStyleSheet("""
        QWidget {
            background: #ffffff;
            border-radius: 12px;
            padding: 10px;
        }
    """)

    title_label = QLabel(title)
    title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

    layout.addWidget(title_label)

    return container, layout