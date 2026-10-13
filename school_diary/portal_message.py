"""Public welcome message and responsive Ayesha illustration."""
from pathlib import Path
import secrets
import html
import io
import os
import logging
import tempfile
from PIL import Image, ImageOps, UnidentifiedImageError
import streamlit as st
from sqlalchemy import Table, Column, Integer, String, Text, LargeBinary, text
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from db import metadata, engine, query
import service as svc
from diary_calendar import stretch

portal_settings = Table('portal_settings', metadata,
    Column('id', Integer, primary_key=True),
    Column('title', String(120), nullable=False),
    Column('message', Text, nullable=False),
    Column('enabled', Integer, nullable=False),
    Column('revision', String(32), nullable=False))
portal_picture = Table('portal_picture', metadata,
    Column('id', Integer, primary_key=True),
    Column('filename', String(32), nullable=False),
    Column('data', LargeBinary().with_variant(MEDIUMBLOB(),'mysql'), nullable=False))
DEFAULT = dict(title='Welcome to School Diary',
    message='Inspired by Aisha — bringing school and home closer, one diary entry at a time.',
    enabled=1,revision='welcome-v1')


@st.cache_data(ttl=30,show_spinner=False)
def public_message():
    rows = query('SELECT title,message,enabled,revision FROM portal_settings WHERE id=1')
    return rows[0] if rows else dict(DEFAULT)


def save_message(uid,title,message,enabled,picture_data=None):
    svc.clear_read_cache()
    svc.actor(uid,('admin',))
    title,message = svc.required(title,120),svc.required(message,1200)
    png=normalize_picture(picture_data) if picture_data is not None else None
    values=dict(t=title,m=message,e=int(bool(enabled)),r=secrets.token_hex(16))
    with engine.begin() as conn:
        insert = 'INSERT IGNORE' if engine.dialect.name=='mysql' else 'INSERT OR IGNORE'
        conn.execute(text(insert+''' INTO portal_settings(id,title,message,enabled,revision)
            VALUES(1,:t,:m,:e,:r)'''),values)
        conn.execute(text('''UPDATE portal_settings SET title=:t,message=:m,enabled=:e,revision=:r
            WHERE id=1'''),values)
        if png is not None:
            conn.execute(text(insert+" INTO portal_picture(id,filename,data) VALUES(1,'w_pic.png',:p)"),dict(p=png))
            conn.execute(text("UPDATE portal_picture SET filename='w_pic.png',data=:p WHERE id=1"),dict(p=png))
    if png is not None:
        write_picture_cache(png)
        uploaded_picture.clear()
    public_message.clear()
    svc._audit(uid,'Updated public welcome message')


def normalize_picture(data):
    if not data or len(data)>5*1024*1024:
        raise ValueError('Choose an image up to 5 MB.')
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in ('PNG','JPEG','WEBP') or original.width*original.height>16000000:
                raise ValueError('Choose a PNG, JPG or WebP image up to 16 megapixels.')
            image=ImageOps.exif_transpose(original).convert('RGBA')
            image.thumbnail((1600,1600))
            result=io.BytesIO()
            image.save(result,format='PNG',optimize=True)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        raise ValueError('This image could not be read. Choose a PNG, JPG or WebP image.') from exc
    png=result.getvalue()
    if len(png)>2*1024*1024:
        raise ValueError('Please choose a smaller image (the converted PNG must be under 2 MB).')
    return png


def write_picture_cache(data):
    # Aiven is durable; the fixed local filename is only a replaceable cache.
    target=Path(__file__).with_name('w_pic.png')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,suffix='.png',delete=False) as file:
            temporary=Path(file.name)
            file.write(data)
        os.replace(temporary,target)
    except OSError:
        logging.getLogger(__name__).warning('Welcome image cached in database; local picture cache unavailable.')
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


@st.cache_data(max_entries=4,show_spinner=False)
def uploaded_picture(revision=None):
    rows=query('SELECT data FROM portal_picture WHERE id=1')
    if rows:
        data=bytes(rows[0]['data'])
        write_picture_cache(data)
        return data
    return None


@st.cache_data(max_entries=4,show_spinner=False)
def local_picture(path,modified_ns,size):
    return Path(path).read_bytes()


@st.cache_data(max_entries=4,show_spinner=False)
def display_picture(source):
    """Small transparent PNG for the existing 170px/260px display sizes.

    Keep the full-resolution w_pic.png and database original untouched.
    """
    with Image.open(io.BytesIO(source)) as original:
        image=ImageOps.exif_transpose(original).convert('RGBA')
        image.thumbnail((520,520),Image.Resampling.LANCZOS)
        buffer=io.BytesIO()
        image.save(buffer,format='PNG',optimize=True)
        return buffer.getvalue()


def picture(popup=False):
    source=uploaded_picture(public_message()['revision'])
    if source is None:
        path=Path(__file__).with_name('w_pic.png')
        if path.exists():
            stat=path.stat()
            source=local_picture(str(path),stat.st_mtime_ns,stat.st_size)
    if source is not None:
        key='ayesha_popup' if popup else 'ayesha_sidebar'
        height='min(35vh, 260px)' if popup else 'clamp(80px, 18vh, 170px)'
        st.html(f'<style>.st-key-{key} img {{width:100%;height:{height};object-fit:contain;object-position:left center;}}'
            f'.st-key-{key} {{min-height:{height};max-width:{"100%" if popup else "82%"};margin-left:0;}}</style>')
        with st.container(key=key):
            st.image(display_picture(source),**stretch(st.image))
    else:
        st.caption('Place w_pic.png beside app.py to display the illustration.')


@st.dialog('\u00a0',width='small')
def message_dialog(settings):
    st.html("""<style>
/* Streamlit versions differ: the painted panel may wrap the role=dialog node. */
[data-testid="stDialog"]:has(.welcome-bubble) > div,
[data-testid="stDialog"]:has(.welcome-bubble) [role="dialog"],
[role="dialog"]:has(.welcome-bubble) {
    background:transparent !important;
    box-shadow:none !important;
    border:0 !important;
}
/* Keep the bubble, illustration and dismissal controls fully opaque. */
[role="dialog"]:has(.welcome-bubble) [slot="title"],
[role="dialog"]:has(.welcome-bubble) h2 {display:none;}

.welcome-bubble {position:relative;background:#fff;color:#252033;border:2px solid #68408A;
    border-radius:24px;padding:18px 20px;margin:0 0 18px;white-space:pre-wrap;overflow-wrap:anywhere;}
.welcome-bubble:after {content:'';position:absolute;bottom:-12px;left:35px;width:20px;height:20px;
    background:#fff;border-right:2px solid #68408A;border-bottom:2px solid #68408A;transform:rotate(45deg);}
</style>""")
    st.html('<div class="welcome-bubble">'+html.escape(settings['message'])+'</div>')
    picture(popup=True)
    if st.button('Close message',key='close_welcome'):
        st.rerun()


def render_welcome():
    settings=public_message()
    with st.sidebar:
        picture()
        st.caption('Inspired by Aisha')
        reopen=st.button('💬 School message',key='open_welcome') if settings['enabled'] and 'user_id' in st.session_state else False
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
        save_col,picture_col=st.columns(2)
        with save_col:
            save=st.form_submit_button('Save welcome message',type='primary')
        with picture_col:
            with st.container(key='choose_welcome_picture'):
                st.html("""<style>
.st-key-choose_welcome_picture [data-testid="stFileUploaderDropzoneInstructions"] {display:none;}
.st-key-choose_welcome_picture [data-testid="stFileUploaderDropzone"] {padding:0;border:0;background:transparent;}
.st-key-choose_welcome_picture [data-testid="stFileUploaderDropzone"] button {font-size:0;}
.st-key-choose_welcome_picture [data-testid="stFileUploaderDropzone"] button:after {content:'Choose Picture';font-size:14px;}
</style>""")
                uploaded=st.file_uploader('Choose Picture',type=['png','jpg','jpeg','webp'],
                    key='welcome_picture_upload',label_visibility='collapsed',
                    help='Choose an image, then Save welcome message. Stored as w_pic.png.')
        if save:
            run_action(lambda:save_message(uid,title,message,enabled,
                uploaded.getvalue() if uploaded is not None else None),'Welcome message updated.')



