"""A small calendar with entry dots, using only built-in Streamlit widgets."""
import calendar
import inspect
from datetime import date
import streamlit as st


def stretch(widget):
    """Support both the existing Streamlit 1.40 requirement and newer releases."""
    parameter = inspect.signature(widget).parameters.get('width')
    modern = parameter is not None and parameter.default in ('stretch', 'content')
    return {'width': 'stretch'} if modern else {'use_container_width': True}


def selection_after_click(start, end, waiting, chosen, is_range):
    """Pure date-selection logic, kept separate for easy testing."""
    if not is_range:
        return chosen, chosen, False
    if not waiting:
        return chosen, None, True
    return min(start, chosen), max(start, chosen), False


def pick_day(key, chosen, is_range):
    state = st.session_state[key]
    state['start'], state['end'], state['waiting'] = selection_after_click(
        state['start'], state['end'], state['waiting'], chosen, is_range)


def move_month(key, offset):
    month_key, year_key = key+'_month', key+'_year'
    index = st.session_state[year_key]*12 + st.session_state[month_key]-1 + offset
    year, month = divmod(index, 12)
    if 1900 <= year <= 2100:
        st.session_state[year_key], st.session_state[month_key] = year, month+1


def go_today(key, today):
    st.session_state[key] = dict(start=today, end=today, waiting=False)
    st.session_state[key+'_year'] = today.year
    st.session_state[key+'_month'] = today.month


def date_calendar(day_counts, today, key, is_range=False):
    """Return inclusive (start, end), or None while the range is incomplete.

    day_counts must already be scoped by service.diary_days to this user/child.
    A dot always means a posted diary entry, never an unrelated family's activity.
    """
    if key not in st.session_state:
        st.session_state[key] = dict(start=today, end=today, waiting=False)
    st.session_state.setdefault(key+'_month', today.month)
    st.session_state.setdefault(key+'_year', today.year)
    state = st.session_state[key]
    start, end = state['start'], state['end']
    st.caption('Posting date range' if is_range else 'Posting date')
    # Inline calendar: navigation fetches only the newly visible month.
    with st.container(border=True):
        st.markdown('<span class="diary-calendar-marker"></span>', unsafe_allow_html=True)
        st.caption('Pick a start date, then an end date.' if is_range else 'Pick a day to view its diary.')
        prev, month_col, year_col, nxt = st.columns([1, 3, 2, 1])
        with prev:
            st.button('‹', key=key+'_prev', help='Previous month', on_click=move_month, args=(key,-1),
                      disabled=st.session_state[key+'_year']==1900 and st.session_state[key+'_month']==1)
        with month_col:
            month = st.selectbox('Month', list(range(1,13)), key=key+'_month',
                                 format_func=lambda m: calendar.month_name[m], label_visibility='collapsed')
        with year_col:
            year = st.selectbox('Year', list(range(1900,2101)), key=key+'_year', label_visibility='collapsed')
        with nxt:
            st.button('›', key=key+'_next', help='Next month', on_click=move_month, args=(key,1),
                      disabled=year==2100 and month==12)
        if callable(day_counts):
            day_counts = day_counts(year, month)
        for col, weekday in zip(st.columns(7), ['M','T','W','T','F','S','S']):
            col.caption(weekday)
        for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year,month):
            for col, day in zip(st.columns(7),week):
                with col:
                    if not day:
                        st.write('')
                        continue
                    chosen = date(year,month,day)
                    count = day_counts.get(chosen.isoformat(),0)
                    selected = chosen==start or (end is not None and start<=chosen<=end)
                    label = f'{day} ●' if count else str(day)
                    help_text = f'{chosen:%d %B %Y}: {count} diary '+('entry' if count==1 else 'entries')
                    if chosen==today:
                        help_text += ' · Today'
                    st.button(label, key=key+'_day_'+chosen.isoformat(), help=help_text,
                              type='primary' if selected else 'secondary', **stretch(st.button),
                              on_click=pick_day, args=(key,chosen,is_range))
        st.caption('● Diary entries available · Purple = selected date(s)')
        if state['waiting']:
            st.info(f'Start: {start:%d %b %Y}. Now choose the end date; you can change months.')
        st.button('Jump to today', key=key+'_today', on_click=go_today, args=(key,today))
    if end is None:
        st.caption(f'From {start:%d %b %Y} — choose an end date in the calendar.')
        return None
    st.caption(f'{start:%d %b %Y} → {end:%d %b %Y}' if is_range else f'{start:%d %B %Y}')
    return start, end
