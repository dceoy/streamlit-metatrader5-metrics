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


def create_df_entry(date_from, date_to, group=None, sqlite3_path=':memory:'):
    return _fetch_table_data(
        table='history_deals', date_from=date_from, date_to=date_to,
        group=group, sqlite3_path=sqlite3_path
    ).pipe(lambda d: d[d['entry'].gt(0)]).sort_values('time_msc')


def _fetch_table_data(table, date_from, date_to, group=None,
                      sqlite3_path=':memory:'):
    sql = (
        'SELECT * FROM {0} WHERE time >= {1} AND time <= {2}'.format(
            table, int(date_from.timestamp()), int(date_to.timestamp())
        ) + (
            '' if group == '*' or not group else
            ' AND symbol LIKE {}'.format(group.replace('*', '%'))
        )
    )
    with sqlite3.connect(sqlite3_path) as con:
        df = pd.read_sql(sql, con)
    return df


def fetch_table_names(sqlite3_path=':memory:'):
    with sqlite3.connect(sqlite3_path) as con:
        df = pd.read_sql(
            'SELECT name FROM sqlite_master WHERE type = \'table\';', con
        )
    return set(df['name'])


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
        dfs = _fetch_mt5_history(
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
        logger.info(f'Update DB data: {sqlite3_path}')
        cur = con.cursor()
        for t, d in dfs.items():
            d.to_sql(t, con, if_exists='append')
            logger.info(f'Table data updated: {t}')
            _drop_duplicates_in_sqlite3(cursor=cur, table=t, ids=d.index.names)
    finally:
        Mt5.shutdown()
        con.close()


def _drop_duplicates_in_sqlite3(cursor, table, ids):
    logger = logging.getLogger(__name__)
    drop_duplicates_sql = (
        f'DELETE FROM {table} WHERE ROWID NOT IN ('
        + f'SELECT MIN(ROWID) FROM {table} GROUP BY ' + ', '.join(ids) + ')'
    )
    logger.info(f'Drop duplicates: `{drop_duplicates_sql}`')
    cursor.execute(drop_duplicates_sql)


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


def _fetch_mt5_history(date_from, date_to, group=None, retry_count=0):
    logger = logging.getLogger(__name__)
    logger.info(f'date_from: {date_from}, date_to: {date_to}, group: {group}')
    res = {
        'history_deals_get': None, 'history_orders_get': None,
        'account_info': None
    }
    for i in range(1 + max(0, int(retry_count))):
        if all((v is not None) for v in res.values()):
            break
        elif i == 0:
            logger.info('Fetch MetaTrader5 data')
        elif i > 0:
            logger.warning('Retry fetching MetaTrader5 data')
            time.sleep(i)
        res = {
            'history_deals_get': Mt5.history_deals_get(
                date_from, date_to, **({'group': group} if group else dict())
            ),
            'history_orders_get': Mt5.history_orders_get(
                date_from, date_to, **({'group': group} if group else dict())
            ),
            'account_info': Mt5.account_info()
        }
    logger.debug(f'res: {res}')
    for k, v in res.items():
        if v is None:
            raise Mt5ResponseError(f'MetaTrader5.{k}() failed.')
    return {
        k: pd.DataFrame(
            list(res[f'{k}_get']),
            columns=res[f'{k}_get'][0]._asdict().keys()
        ).assign(
            login=res['account_info'].login,
            server=res['account_info'].server
        ).set_index(['login', 'ticket'])
        for k in ['history_deals', 'history_orders']
    }


def popen_mt5_app(path, seconds_to_wait=5):
    logger = logging.getLogger(__name__)
    if path:
        logger.info(f'Execute MetaTrader5 app: "{path}"')
        p = subprocess.Popen(args=[path])
        time.sleep(seconds_to_wait)
        return p
    else:
        logger.info('Skip executing MetaTrader5 app')
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
