"""Public welcome message and responsive Ayesha illustration."""
from pathlib import Path
import secrets
import streamlit as st
from sqlalchemy import Table, Column, Integer, String, Text, text
from db import metadata, engine, query
import service as svc
from diary_calendar import stretch

portal_settings = Table('portal_settings', metadata,
    Column('id', Integer, primary_key=True),
    Column('title', String(120), nullable=False),
    Column('message', Text, nullable=False),
    Column('enabled', Integer, nullable=False),
    Column('revision', String(32), nullable=False))
DEFAULT = dict(title='Welcome to School Diary',
    message='Inspired by Ayesha — bringing school and home closer, one diary entry at a time.',
    enabled=1,revision='welcome-v1')


@st.cache_data(ttl=30,show_spinner=False)
def public_message():
    rows = query('SELECT title,message,enabled,revision FROM portal_settings WHERE id=1')
    return rows[0] if rows else dict(DEFAULT)


def save_message(uid,title,message,enabled):
    svc.actor(uid,('admin',))
    title,message = svc.required(title,120),svc.required(message,1200)
    values=dict(t=title,m=message,e=int(bool(enabled)),r=secrets.token_hex(16))
    with engine.begin() as conn:
        insert = 'INSERT IGNORE' if engine.dialect.name=='mysql' else 'INSERT OR IGNORE'
        conn.execute(text(insert+''' INTO portal_settings(id,title,message,enabled,revision)
            VALUES(1,:t,:m,:e,:r)'''),values)
        conn.execute(text('''UPDATE portal_settings SET title=:t,message=:m,enabled=:e,revision=:r
            WHERE id=1'''),values)
    public_message.clear()
    svc._audit(uid,'Updated public welcome message')


def picture(popup=False):
    path=Path(__file__).with_name('ayesha.png')
    if path.exists():
        key='ayesha_popup' if popup else 'ayesha_sidebar'
        height='min(32vh, 240px)' if popup else 'clamp(100px, 22vh, 210px)'
        st.markdown(f'<style>.st-key-{key} img {{width:100%;height:{height};object-fit:contain;}}</style>',unsafe_allow_html=True)
        with st.container(key=key):
            # Streamlit serves a reusable media URL, avoiding inline image data each rerun.
            st.image(str(path),**stretch(st.image))
    else:
        st.caption('Place ayesha.png beside app.py to display the illustration.')


@st.dialog('A message from school',width='small')
def message_dialog(settings):
    picture(popup=True)
    st.subheader(settings['title'])
    st.text(settings['message'])
    if st.button('Close message',key='close_welcome'):
        st.rerun()


def render_welcome():
    settings=public_message()
    with st.sidebar:
        st.title('📖 School Diary')
        visible=st.toggle('Show Ayesha',value=True,key='show_ayesha')
        if visible:
            picture()
            st.caption('Inspired by Ayesha')
        reopen=st.button('💬 School message',key='open_welcome') if settings['enabled'] else False
    # Dismissal survives page changes. A newly saved revision appears on next rerun.
    if settings['enabled'] and (reopen or st.session_state.get('welcome_seen')!=settings['revision']):
        st.session_state.welcome_seen=settings['revision']
        message_dialog(settings)


def message_editor(uid,run_action):
    svc.actor(uid,('admin',))
    settings=public_message()
    st.subheader('Welcome picture & message')
    st.caption('Public message: visible on the login screen and to all roles. Do not include private student details.')
    with st.form('edit_welcome'):
        title=st.text_input('Message title',value=settings['title'],max_chars=120)
        message=st.text_area('Welcome message',value=settings['message'],max_chars=1200,height=150)
        enabled=st.checkbox('Enable message popup',value=bool(settings['enabled']))
        if st.form_submit_button('Save welcome message',type='primary'):
            run_action(lambda:save_message(uid,title,message,enabled),'Welcome message updated.')
