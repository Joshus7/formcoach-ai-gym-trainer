"""Dark / light themes as Qt stylesheets built from one set of colour tokens."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str
    surface: str
    surface2: str
    border: str
    text: str
    muted: str
    accent: str
    accent_text: str
    good: str
    warn: str
    bad: str


DARK = Palette(bg="#0f1115", surface="#171a21", surface2="#20242d", border="#2b303b", text="#e8eaf0",
               muted="#8b93a7", accent="#4f8cff", accent_text="#ffffff", good="#3ecf8e", warn="#ff9f43",
               bad="#ff5c5c")
LIGHT = Palette(bg="#f4f6fa", surface="#ffffff", surface2="#eef1f6", border="#d9dee8", text="#1b1f29",
                muted="#5f6880", accent="#2f6fed", accent_text="#ffffff", good="#16a36a", warn="#e07b00",
                bad="#d93636")

THEMES = {"dark": DARK, "light": LIGHT}


def palette(name: str) -> Palette:
    return THEMES.get(name, DARK)


def stylesheet(name: str) -> str:
    p = palette(name)
    return f"""
    QWidget {{ background: {p.bg}; color: {p.text}; font-size: 14px; }}
    QLabel {{ background: transparent; }}
    QFrame#Card, QFrame#Sidebar {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px; }}
    QFrame#Sidebar {{ border-radius: 0; border-width: 0 1px 0 0; }}
    QLabel#Title {{ font-size: 26px; font-weight: 700; }}
    QLabel#Subtitle {{ color: {p.muted}; font-size: 14px; }}
    QLabel#Section {{ font-size: 16px; font-weight: 600; }}
    QLabel#Muted {{ color: {p.muted}; }}
    QLabel#BigNumber {{ font-size: 72px; font-weight: 800; }}
    QLabel#StatValue {{ font-size: 28px; font-weight: 700; }}
    QLabel#StatLabel {{ color: {p.muted}; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
    QLabel#Feedback {{ font-size: 22px; font-weight: 700; padding: 10px 14px; border-radius: 10px;
                       background: {p.surface2}; }}
    QLabel#Brand {{ font-size: 20px; font-weight: 800; color: {p.accent}; }}
    QPushButton {{ background: {p.surface2}; border: 1px solid {p.border}; border-radius: 10px;
                   padding: 9px 16px; font-weight: 600; }}
    QPushButton:hover {{ border-color: {p.accent}; }}
    QPushButton:disabled {{ color: {p.muted}; }}
    QPushButton#Primary {{ background: {p.accent}; color: {p.accent_text}; border: none; font-size: 16px;
                           padding: 12px 22px; }}
    QPushButton#Danger {{ background: {p.bad}; color: #ffffff; border: none; }}
    QPushButton#Nav {{ text-align: left; background: transparent; border: none; padding: 10px 14px;
                       border-radius: 8px; }}
    QPushButton#Nav:checked {{ background: {p.surface2}; color: {p.accent}; }}
    QToolButton#ExerciseTile {{ background: {p.surface}; border: 2px solid {p.border}; border-radius: 14px;
                                padding: 12px; font-weight: 600; }}
    QToolButton#ExerciseTile:hover {{ border-color: {p.muted}; }}
    QToolButton#ExerciseTile:checked {{ border-color: {p.accent}; background: {p.surface2}; color: {p.accent}; }}
    QRadioButton::indicator, QCheckBox::indicator {{ width: 16px; height: 16px; border: 2px solid {p.muted};
        background: {p.surface2}; }}
    QRadioButton::indicator {{ border-radius: 10px; }}
    QCheckBox::indicator {{ border-radius: 4px; }}
    QRadioButton::indicator:checked, QCheckBox::indicator:checked {{ background: {p.accent};
        border-color: {p.accent}; }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {p.surface2}; border: 1px solid {p.border};
        border-radius: 8px; padding: 6px 8px; min-height: 22px; }}
    QComboBox QAbstractItemView {{ background: {p.surface}; selection-background-color: {p.accent}; }}
    QCheckBox, QRadioButton {{ background: transparent; spacing: 8px; }}
    QTableWidget, QTreeWidget {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px;
        gridline-color: {p.border}; }}
    QHeaderView::section {{ background: {p.surface2}; color: {p.muted}; border: none; padding: 6px; }}
    QTabWidget::pane {{ border: 1px solid {p.border}; border-radius: 10px; }}
    QTabBar::tab {{ background: {p.surface2}; padding: 8px 14px; border-top-left-radius: 8px;
                    border-top-right-radius: 8px; margin-right: 2px; }}
    QTabBar::tab:selected {{ background: {p.accent}; color: {p.accent_text}; }}
    QScrollArea {{ border: none; }}
    QSlider::groove:horizontal {{ height: 6px; background: {p.surface2}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {p.accent}; width: 16px; margin: -5px 0; border-radius: 8px; }}
    QToolTip {{ background: {p.surface2}; color: {p.text}; border: 1px solid {p.border}; }}
    """
