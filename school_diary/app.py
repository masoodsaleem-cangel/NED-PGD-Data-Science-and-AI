""" To run, be on root: python -m streamlit run app.py """
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import service as svc
from db import init_db, query

st.set_page_config(page_title='School Diary',page_icon='📖', layout='wide')
st.markdown('''<style>
.stApp {background:#f6f7fb;}
h1,h2,h3 {color:#44305d;}
[data-testid="stMetric"] {background:white;padding:18px;border-radius:14px;}</style>''', unsafe_allow_html=True)
init_db()