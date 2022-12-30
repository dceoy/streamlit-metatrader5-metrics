#!/usr/bin/env python

import argparse
import logging
from datetime import date, datetime, time, timedelta

import streamlit as st
from util import kill_subprocess, popen_mt5_app, update_mt5_metrics_db

__version__ = 'v0.0.1'


def main():
    args = _parse_arguments()
    logger = logging.getLogger(__name__)
    logger.debug(f'__file__: {__file__}')
    if 'mt5_process' not in st.session_state:
        st.session_state['mt5_process'] = popen_mt5_app(path=args.mt5_exe)
    try:
        _execute_streamlit_app(args=args)
    except Exception as e:
        raise e
    finally:
        if args.cleanup and st.session_state['mt5_process']:
            kill_subprocess(process=st.session_state['mt5_process'])


def _execute_streamlit_app(args):
    st.set_page_config(layout='wide')
    st.header('MetaTrader 5 Trading History')
    st.sidebar.header('Condition')
    today = date.today()
    date_from = st.sidebar.date_input('From:', value=today)
    date_to = st.sidebar.date_input('To:', value=today)
    group = st.sidebar.text_input('Filter for symbols:', value='*')
    if st.sidebar.button('Submit'):
        if date_from > date_to:
            st.error('The date interval is invalid!', icon='🚨')
        else:
            df_deal = update_mt5_metrics_db(
                sqlite3_path=args.sqlite3, login=args.mt5_login,
                password=args.mt5_password, server=args.mt5_server,
                retry_count=args.retry_count,
                date_from=datetime.combine(date_from, time()),
                date_to=(
                    datetime.combine(date_to, time()) + timedelta(days=1)
                ),
                group=group
            )
            st.subheader('Updated Data Frame')
            st.write(df_deal)
    else:
        pass


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
