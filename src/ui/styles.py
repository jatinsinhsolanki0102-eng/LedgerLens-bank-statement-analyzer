"""Global Streamlit styling for a clean fintech dashboard."""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
:root {
    --ll-navy: #102a43;
    --ll-navy-deep: #0b1f33;
    --ll-teal: #0f8b8d;
    --ll-teal-dark: #0b6e69;
    --ll-coral: #d96c5f;
    --ll-gold: #d9a441;
    --ll-ink: #1f2933;
    --ll-muted: #627d98;
    --ll-line: #dfe7ee;
    --ll-surface: #ffffff;
    --ll-canvas: #f4f7fa;
}

html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 100% 0%, rgba(15, 139, 141, 0.08), transparent 28rem),
        linear-gradient(180deg, #f7f9fb 0%, var(--ll-canvas) 100%);
    color: var(--ll-ink);
}

.block-container {
    max-width: 1360px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

#MainMenu, footer {
    visibility: hidden;
}

h1, h2, h3 {
    color: var(--ll-navy);
    letter-spacing: -0.02em;
}

p, li, label {
    color: var(--ll-ink);
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--ll-navy-deep) 0%, #102a43 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

section[data-testid="stSidebar"] * {
    color: #d9e2ec;
}

section[data-testid="stSidebar"] hr {
    border-color: rgba(255, 255, 255, 0.12);
}

.ll-brand {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.4rem 0 1.4rem 0;
}

.ll-brand-mark {
    width: 2.6rem;
    height: 2.6rem;
    border-radius: 0.85rem;
    display: grid;
    place-items: center;
    font-weight: 800;
    font-size: 0.95rem;
    color: #ffffff;
    background: linear-gradient(135deg, var(--ll-teal) 0%, #47b3a9 100%);
    box-shadow: 0 8px 22px rgba(15, 139, 141, 0.35);
}

.ll-brand-name {
    font-size: 1.18rem;
    font-weight: 750;
    color: #ffffff;
    line-height: 1.1;
}

.ll-brand-sub {
    font-size: 0.76rem;
    color: #9fb3c8;
    margin-top: 0.18rem;
}

section[data-testid="stSidebar"] div[role="radiogroup"] {
    gap: 0.35rem;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 0.62rem 0.8rem;
    border-radius: 0.65rem;
    transition: background 150ms ease, transform 150ms ease;
    font-weight: 600;
    font-size: 0.92rem;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background: rgba(255, 255, 255, 0.07);
    transform: translateX(2px);
}

section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: rgba(15, 139, 141, 0.28);
    border-left: 3px solid #5fd0c7;
}

.ll-sidebar-status {
    margin-top: 1.2rem;
    padding: 0.75rem 0.9rem;
    border-radius: 0.75rem;
    background: rgba(255, 255, 255, 0.055);
    border: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 0.78rem;
    line-height: 1.5;
    color: #bcccdc;
}

.ll-sidebar-status strong {
    color: #ffffff;
}

.ll-page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1.5rem;
    margin: 0 0 1.5rem 0;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--ll-line);
}

.ll-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.72rem;
    font-weight: 750;
    color: var(--ll-teal-dark);
    margin-bottom: 0.32rem;
}

.ll-page-title {
    font-size: 2rem;
    line-height: 1.15;
    font-weight: 780;
    letter-spacing: -0.035em;
    color: var(--ll-navy);
    margin: 0;
}

.ll-page-subtitle {
    margin-top: 0.4rem;
    color: var(--ll-muted);
    font-size: 0.95rem;
}

.ll-header-meta {
    text-align: right;
    color: var(--ll-muted);
    font-size: 0.8rem;
    white-space: nowrap;
}

.ll-header-meta strong {
    display: block;
    color: var(--ll-navy);
    font-size: 0.9rem;
}

.ll-card {
    background: var(--ll-surface);
    border: 1px solid var(--ll-line);
    border-radius: 1rem;
    padding: 1.15rem 1.2rem;
    box-shadow: 0 8px 24px rgba(16, 42, 67, 0.045);
}

.ll-section-title {
    font-size: 1.05rem;
    font-weight: 720;
    color: var(--ll-navy);
    margin: 0 0 0.25rem 0;
}

.ll-section-subtitle {
    font-size: 0.82rem;
    color: var(--ll-muted);
    margin-bottom: 0.65rem;
}

.ll-formula {
    font-size: 0.82rem;
    color: var(--ll-muted);
}

.ll-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.32rem;
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    white-space: nowrap;
}

.ll-badge-neutral { background: #edf2f7; color: #486581; }
.ll-badge-success { background: #e3f5ef; color: #12715b; }
.ll-badge-warning { background: #fff4df; color: #8a5a13; }
.ll-badge-danger { background: #fdecea; color: #a52a20; }
.ll-badge-info { background: #e8f1ff; color: #225ea8; }

.ll-account-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.8rem;
    margin: 0.8rem 0 1.3rem 0;
}

.ll-account-item {
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid var(--ll-line);
    border-radius: 0.8rem;
    padding: 0.72rem 0.9rem;
}

.ll-account-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ll-muted);
    font-weight: 700;
}

.ll-account-value {
    color: var(--ll-navy);
    font-weight: 680;
    font-size: 0.9rem;
    margin-top: 0.2rem;
    overflow-wrap: anywhere;
}

.ll-empty {
    background: var(--ll-surface);
    border: 1px dashed #bcccdc;
    border-radius: 1.2rem;
    padding: 3.2rem 2rem;
    text-align: center;
    max-width: 46rem;
    margin: 4rem auto;
}

.ll-empty-mark {
    width: 3.2rem;
    height: 3.2rem;
    margin: 0 auto 1rem auto;
    border-radius: 1rem;
    background: #e6f5f3;
    color: var(--ll-teal-dark);
    font-weight: 800;
    display: grid;
    place-items: center;
    font-size: 1.05rem;
}

.ll-empty h2 {
    margin: 0 0 0.5rem 0;
    font-size: 1.35rem;
}

.ll-empty p {
    color: var(--ll-muted);
    max-width: 34rem;
    margin: 0 auto 1.2rem auto;
    line-height: 1.6;
}

.ll-privacy {
    background: #f0f7f6;
    border: 1px solid #cbe7e3;
    border-left: 4px solid var(--ll-teal);
    border-radius: 0.8rem;
    padding: 0.85rem 1rem;
    color: #295e5b;
    font-size: 0.84rem;
    line-height: 1.55;
    margin: 0.8rem 0 1rem 0;
}

.ll-note {
    color: var(--ll-muted);
    font-size: 0.8rem;
    line-height: 1.55;
}

.ll-mono {
    font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
    font-size: 0.78rem;
}

div[data-testid="stMetric"] {
    background: var(--ll-surface);
    border: 1px solid var(--ll-line);
    border-radius: 0.9rem;
    padding: 0.95rem 1rem;
    box-shadow: 0 6px 18px rgba(16, 42, 67, 0.04);
}

div[data-testid="stMetric"] label {
    color: var(--ll-muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
}

div[data-testid="stMetricValue"] {
    color: var(--ll-navy);
    font-size: 1.5rem;
    font-weight: 760;
    letter-spacing: -0.025em;
}

div[data-testid="stMetricDelta"] {
    font-size: 0.76rem;
}

.stButton > button, .stDownloadButton > button {
    border-radius: 0.65rem;
    border: 1px solid #cbd8e3;
    font-weight: 650;
    min-height: 2.5rem;
}

.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: var(--ll-teal-dark);
    border-color: var(--ll-teal-dark);
    color: #ffffff;
}

.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
    background: #095c58;
    border-color: #095c58;
}

div[data-testid="stFileUploaderDropzone"] {
    background: rgba(255, 255, 255, 0.8);
    border: 1.5px dashed #a9c3d4;
    border-radius: 0.9rem;
    padding: 1.3rem;
}

div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    border: 1px solid var(--ll-line);
    border-radius: 0.8rem;
    overflow: hidden;
}

div[data-testid="stExpander"] {
    background: rgba(255, 255, 255, 0.65);
    border: 1px solid var(--ll-line);
    border-radius: 0.8rem;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 0.35rem;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 0.55rem;
    padding: 0.45rem 0.8rem;
    font-weight: 600;
}

.stAlert {
    border-radius: 0.75rem;
}

hr {
    border-color: var(--ll-line);
}

@media (max-width: 760px) {
    .ll-page-header {
        flex-direction: column;
        align-items: flex-start;
    }
    .ll-header-meta {
        text-align: left;
    }
    .ll-page-title {
        font-size: 1.65rem;
    }
}
</style>
"""


def inject_global_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
