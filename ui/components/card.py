from typing import Tuple

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


def create_card(title: str) -> Tuple[QWidget, QVBoxLayout]:
    container = QWidget()
    container.setObjectName("dashboardCard")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(10)

    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    layout.addWidget(title_label)

    return container, layout
