#!/usr/bin/env python

import logging
import sqlite3
import subprocess
import sys
import time

import MetaTrader5 as Mt5
import pandas as pd


class Mt5ResponseError(RuntimeError):
    pass


def update_mt5_metrics_db(sqlite3_path=':memory:', **kwargs):
    logger = logging.getLogger(__name__)
    con = sqlite3.connect(sqlite3_path)
    try:
        _initialize_mt5(
            **{
                k: v for k, v in kwargs.items()
                if k in {'login', 'password', 'server', 'retry_count'}
            }
        )
        df_deal = _fetch_mt5_history_deals(
            **{
                k: v for k, v in kwargs.items()
                if k in {'date_from', 'date_to', 'group', 'retry_count'}
            }
        )
    except Mt5ResponseError as e:
        logger.error('Mt5.last_error(): {}'.format(Mt5.last_error()))
        raise e
    except Exception as e:
        logger.info('Mt5.last_error(): {}'.format(Mt5.last_error()))
        raise e
    else:
        df_deal.to_sql('deal', con, if_exists='append')
        logger.info(f'DB updated: {sqlite3_path}')
    finally:
        Mt5.shutdown()
        con.close()
    return df_deal


def _initialize_mt5(login=None, password=None, server=None, retry_count=0):
    logger = logging.getLogger(__name__)
    initialize_kwargs = {
        **({'login': int(login)} if login else dict()),
        **({'password': password} if password else dict()),
        **({'server': server} if server else dict())
    }
    res = None
    for i in range(1 + max(0, int(retry_count))):
        if res:
            break
        elif i == 0:
            logger.info('Initialize MetaTrader5')
        elif i > 0:
            logger.warning('Retry MetaTrader5.initialize()')
            time.sleep(i)
        res = Mt5.initialize(**initialize_kwargs)
    if not res:
        raise Mt5ResponseError('MetaTrader5.initialize() failed.')


def _fetch_mt5_history_deals(date_from, date_to, group=None, retry_count=0):
    logger = logging.getLogger(__name__)
    logger.info(f'date_from: {date_from}, date_to: {date_to}, group: {group}')
    res = {'account_info': None, 'history_deals_get': None}
    for i in range(1 + max(0, int(retry_count))):
        if all((v is not None) for v in res.values()):
            break
        elif i == 0:
            logger.info('Fetch MetaTrader5 deals')
        elif i > 0:
            logger.warning(
                'Retry MetaTrader5.account_info()'
                ' and MetaTrader5.history_deals_get()'
            )
            time.sleep(i)
        res = {
            'account_info': Mt5.account_info(),
            'history_deals_get': Mt5.history_deals_get(
                date_from, date_to, **({'group': group} if group else dict())
            )
        }
    logger.debug(f'res: {res}')
    for k, v in res.items():
        if v is None:
            raise Mt5ResponseError(f'MetaTrader5.{k}() failed.')
    df_deal = pd.DataFrame(
        list(res['history_deals_get']),
        columns=res['history_deals_get'][0]._asdict().keys()
    ).assign(
        login=res['account_info'].login
    ).set_index(['login', 'ticket'])
    logger.debug(f'df_deal.shape: {df_deal.shape}')
    return df_deal


def popen_mt5_app(path, seconds_to_wait=5):
    logger = logging.getLogger(__name__)
    if path:
        logger.info(f'Execute MetaTrader5 app: "{path}"')
        p = subprocess.Popen(args=[path])
        time.sleep(seconds_to_wait)
        return p
    else:
        logger.warning('Skip executing MetaTrader5 app')
        return None


def kill_subprocess(process):
    logger = logging.getLogger(__name__)
    process.kill()
    stdout, stderr = process.communicate()
    logger.debug(f'stdout: {stdout}, stderr: {stderr}')
    if stdout:
        sys.stdout(stdout)
    if stderr:
        sys.stderr(stderr)
