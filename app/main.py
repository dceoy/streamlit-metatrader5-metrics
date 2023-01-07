#!/usr/bin/env python

import argparse
import logging
from datetime import date, datetime, time, timedelta

import MetaTrader5 as Mt5
import pandas as pd
import plotly.express as px
import streamlit as st
from util import (create_df_entry, fetch_table_names, kill_subprocess,
                  popen_mt5_app, update_mt5_metrics_db)

__version__ = 'v0.0.2'


def main():
    args = _parse_arguments()
    logger = logging.getLogger(__name__)
    logger.debug(f'__file__: {__file__}')
    if 'execution_count' not in st.session_state:
        st.session_state['execution_count'] = 1
        st.session_state['mt5_process'] = popen_mt5_app(path=args.mt5_exe)
    else:
        st.session_state['execution_count'] += 1
    logger.info(f'st.session_state: {st.session_state}')
    try:
        _execute_streamlit_app(args=args)
    except Exception as e:
        raise e
    finally:
        if args.cleanup and st.session_state['mt5_process']:
            kill_subprocess(process=st.session_state['mt5_process'])


def _execute_streamlit_app(args):
    today = date.today()
    st.set_page_config(
        page_title='MetaTrader 5 Trading History', page_icon='🧊',
        layout='wide', initial_sidebar_state='auto'
    )
    st.sidebar.header('MetaTrader 5 Trading History')
    with st.sidebar.form('condition'):
        st.header('Condition')
        st.session_state['date_from'] = st.date_input(
            'From:', value=(st.session_state.get('date_from') or today)
        )
        st.session_state['date_to'] = st.date_input(
            'To:', value=(st.session_state.get('date_to') or today)
        )
        st.session_state['group'] = st.text_input(
            'Filter for symbols:', value=(st.session_state.get('group') or '*')
        )
        submitted = st.form_submit_button('Submit')
    if st.session_state['date_from'] > st.session_state['date_to']:
        st.error('The date interval is invalid!', icon='🚨')
    elif submitted or 'deal' in fetch_table_names(sqlite3_path=args.sqlite3):
        date_from = datetime.combine(st.session_state['date_from'], time())
        date_to = datetime.combine(
            (st.session_state['date_to'] + timedelta(days=1)), time()
        )
        if submitted:
            update_mt5_metrics_db(
                sqlite3_path=args.sqlite3, login=args.mt5_login,
                password=args.mt5_password, server=args.mt5_server,
                retry_count=args.retry_count, date_from=date_from,
                date_to=date_to, group=st.session_state['group']
            )
        df_entry = create_df_entry(
            date_from=date_from, date_to=date_to,
            group=st.session_state['group'], sqlite3_path=args.sqlite3
        )
        if df_entry.size:
            df_pl = df_entry.assign(
                time_msc=lambda d: pd.to_datetime(d['time_msc'], unit='ms'),
                symbol_pl=lambda d: d.groupby('symbol')['profit'].cumsum(),
                total_pl=lambda d: d['profit'].cumsum(),
                deal_type=lambda d: d['type'].where(
                    d['type'].isin({Mt5.DEAL_TYPE_BUY, Mt5.DEAL_TYPE_SELL})
                ).mask(
                    d['type'] == Mt5.DEAL_TYPE_BUY, 'BUY'
                ).mask(
                    d['type'] == Mt5.DEAL_TYPE_SELL, 'SELL'
                )
            )
            st.subheader('Cumulative PL')
            fig1 = px.area(
                df_pl, x='time_msc', y='total_pl',
                labels={'time_msc': 'Time', 'total_pl': 'PL'}, title='Total PL'
            )
            fig1.update_layout(width=800, height=250)
            st.plotly_chart(fig1, theme='streamlit', use_container_width=True)
            fig2 = px.line(
                df_pl, x='time_msc', y='symbol_pl', color='symbol',
                labels={
                    'time_msc': 'Time', 'symbol_pl': 'PL', 'symbol': 'Symbol'
                },
                title='PL by Symbol'
            )
            fig2.update_layout(
                width=800, height=500,
                legend=dict(
                    orientation='h', yanchor='bottom', y=1.02,
                    xanchor='center', x=0.5
                )
            )
            st.plotly_chart(fig2, theme='streamlit', use_container_width=True)
            st.subheader('Entry Volume')
            fig3 = px.scatter(
                df_pl.dropna(subset=['deal_type']),
                x='time_msc', y='volume', facet_col='symbol', facet_col_wrap=1,
                color='symbol', symbol='deal_type',
                labels={
                    'time_msc': 'Time', 'volume': 'Volume', 'symbol': 'Symbol',
                    'deal_type': 'Deal'
                }
            )
            fig3.update_yaxes(matches=None)
            fig3.update_layout(
                width=800, height=(200 * df_pl['symbol'].nunique()),
                legend=dict(
                    orientation='h', yanchor='bottom', y=1.04,
                    xanchor='center', x=0.5
                )
            )
            for annotation in fig3['layout']['annotations']:
                annotation['textangle'] = 0
            st.plotly_chart(fig3, theme='streamlit', use_container_width=True)
            st.subheader('Data Frame')
            st.write(df_pl)
        else:
            st.warning('No data')


def _parse_arguments():
    parser = argparse.ArgumentParser(
        prog='streamlit-metatrader5-metrics',
        description='Streamlit Application for MetaTrader 5 Metrics'
    )
    parser.add_argument(
        '--version', action='version', version=f'%(prog)s {__version__}'
    )
    parser.add_argument(
        '--mt5-exe', action='store', type=str,
        help='specify a path to a MetaTrader 5 (MT5) exe file'
    )
    parser.add_argument(
        '--mt5-login', action='store', type=str,
        help='specify a MT5 trading account number'
    )
    parser.add_argument(
        '--mt5-password', action='store', type=str,
        help='specify a MT5 trading account password'
    )
    parser.add_argument(
        '--mt5-server', action='store', type=str,
        help='specify a MT5 trade server name'
    )
    parser.add_argument(
        '--cleanup', action='store_true', help='terminate a subprocess spawned'
    )
    parser.add_argument(
        '--retry-count', action='store', type=int, default=0,
        help='set the retry count due to API errors'
    )
    parser.add_argument(
        '--sqlite3', action='store', type=str, default=':memory:',
        help='specify a path to a SQLite3 database file'
    )
    return parser.parse_args()


if __name__ == '__main__':
    main()
