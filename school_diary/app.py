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
[data-testid="stMetric"] {background:white;padding:18px;border-radius:14px;}
</style>''', unsafe_allow_html=True)
init_db()


def choose(label, rows, key, field='name'):
    return st.selectbox(label, [r['id'] for r in rows],
                        format_func=lambda x: next(r[field] for r in rows if r['id']==x), key=key)


def save(action):
    try:
        action()
        st.success('Saved successfully.')
    except IntegrityError:
        st.error('This record already exists, or a required linked record is missing.')
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))
    except SQLAlchemyError:
        st.error('The database could not save this change. Check the connection and try again.')


ddef login_screen():
    st.title('📖 School Diary')
    st.write('A daily connection between school and home.')
    _, middle, _ = st.columns([1,2,1])
    with middle:
        role_label = st.radio('Sign in as', ['Parent','Teacher','Super admin'], horizontal=True)
        role = {'Parent':'parent','Teacher':'teacher','Super admin':'admin'}[role_label]
        with st.form('login'):
            identifier = st.text_input('Student ID' if role=='parent' else 'Username')
            cnic = st.text_input('Parent CNIC', type='password', placeholder='00000-0000000-0') if role=='parent' else ''
            password = st.text_input('Password',type='password')
            submitted = st.form_submit_button('Sign in',use_container_width=True)
        if submitted:
            user = svc.login(role,identifier,password,cnic)
            if user:
                st.session_state.clear()
                st.session_state.user_id=user['id']
                st.session_state.last_activity=time.time()
                st.rerun()
            st.error('Sign-in failed. Check your details, or wait 5 minutes if your account is locked.')
        st.caption('Parents: use a linked child’s student ID, your registered CNIC, and your password.')
        if not query('SELECT id FROM users LIMIT 1'):
            st.info('First run: stop the app and run python setup.py --demo for sample data, or python setup.py for an empty school.')


def admin_panel(uid):
    st.header('School Administration')
    users=svc.directory(uid)
    classes=svc.allowed_classes(uid)
    students=query('SELECT id,student_code,name,class_id FROM students ORDER BY name')
    tabs=st.tabs(['Overview','People','Classes & students','Link accounts','Account access'])
    with tabs[0]:
        cols=st.columns(3)
        cols[0].metric('Students',len(students))
        cols[1].metric('Classes',len(classes))
        cols[2].metric('Teachers',sum(u['role']=='teacher' for u in users))
        st.subheader('School directory')
        st.dataframe(users,use_container_width=True,hide_index=True)
        st.caption('CNICs and password hashes are never displayed in this directory.')
    with tabs[1]:
        role=st.slectbox('New account type',['teacher','parent','admin'])
        with st.form('new_user',clear_on_submit=True)
        