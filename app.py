"""Entry point for Streamlit — defines navigation with icons and titles."""
import streamlit as st

pg = st.navigation([
    st.Page("dashboard.py",              title="Dashboard",     icon=":material/dashboard:"),
    st.Page("pages/1_YouTube.py",        title="YouTube",       icon=":material/smart_display:"),
    st.Page("pages/2_Reddit.py",         title="Reddit",        icon=":material/forum:"),
    st.Page("pages/3_Web_and_Trends.py", title="Web & Trends",  icon=":material/travel_explore:"),
])
pg.run()
