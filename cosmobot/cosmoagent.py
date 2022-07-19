from twisted.internet import task, reactor
import pandas as pd
from binance.client import Client
from decimal import Decimal
import os
import json

# local imports
from utils import utils, trends, bintrade, dynamodb
from cosmobot import cosmomixins


#Staging
DEBUG = bool(int(os.getenv('COSMOBOT_DEBUG')))

# Binance variables
BIN_API_KEY = os.environ['BIN_API_KEY']
BIN_API_SECRET = os.environ['BIN_API_SECRET']
BIN_CLIENT = None
ALL_CRYPTO_PRICE = []

# AWS Dynamo
AWS_DYNAMO_SESSION = dynamodb.create_session()

# General vars
COSMOAGENT_CONFIG = {}


@utils.logger.catch
def load_config():
    utils.logger.info(f'Load Config dict')
   
    if DEBUG:
        return dynamodb.get_item(AWS_DYNAMO_SESSION, 'mm_cosmoagent', {'feature' : 'test_config'})
    else:
        return dynamodb.get_item(AWS_DYNAMO_SESSION, 'mm_cosmoagent', {'feature' : 'prod_config'})


@utils.logger.catch
def put_planet_trend_info(symbol, ptrend, mtrend, strend, pd_limit, pz_limit, pclose):

    cosmo_time = cosmomixins.get_cosmobot_time()
    cosmo_week = cosmo_time[0]
    cosmo_timestamp = cosmo_time[4]

    to_put = {  'week' : cosmo_week, 
                'timestamp' : cosmo_timestamp,
                'ptrend' : ptrend,
                'mtrend' : mtrend,
                'strend' : strend,
                'pclose' : pclose,
                'pd_limit' : pd_limit,
                'pz_limit' : pz_limit }

    item = json.loads(json.dumps(to_put), parse_float=Decimal)

    if DEBUG:
        dynamodb.put_item(AWS_DYNAMO_SESSION, f'mm_cosmobot_historical_{symbol}_test', item)
    else:
        dynamodb.put_item(AWS_DYNAMO_SESSION, f'mm_cosmobot_historical_{symbol}', item)


@utils.logger.catch
def get_planet_trend(symbol):
    utils.logger.info(f'Get Planet info for {symbol}')


    # 1day data
    trend_data = bintrade.get_chart_data(BIN_CLIENT, symbol, start='44 days ago', end='now', period=BIN_CLIENT.KLINE_INTERVAL_1DAY, df=True, decimal=True)
    ptrend, pclose, pd_limit, pz_limit = trends.planets_volume(trend_data)
    mtrend, mclose, md_limit, mz_limit = trends.planets_volume(trend_data, trend_type='mean')
    strend, sclose, sd_limit, mz_limit = trends.planets_volume(trend_data, trend_type='sum')
    
    # Execute
    put_planet_trend_info(symbol, ptrend, mtrend, strend, pd_limit, pz_limit, pclose)



@utils.logger.catch
def loop():
    global ALL_CRYPTO_PRICE
    global COSMOAGENT_CONFIG

	# Get all crypto assets price
    ALL_CRYPTO_PRICE = BIN_CLIENT.get_all_tickers()

	# Load config in loop
    COSMOAGENT_CONFIG = load_config()

    # loop crypto
    for symbol in COSMOAGENT_CONFIG['crypto_symbols']:
        get_planet_trend(symbol)


@utils.logger.catch
def launch():
    global COSMOAGENT_CONFIG
    global BIN_CLIENT
    
    print (utils.logger)
    # Load config
    COSMOAGENT_CONFIG = load_config()

    # Log path
    utils.logger_path(COSMOAGENT_CONFIG['log_path'])

    # Log config
    utils.logger.info(COSMOAGENT_CONFIG)

    #Binance
    utils.logger.info('AUTH BINANCE')
    BIN_CLIENT = Client(BIN_API_KEY, BIN_API_SECRET)

    if DEBUG:
        klines = bintrade.get_chart_data(BIN_CLIENT, 'SOLBUSD', start='1 day ago', end='now', period=BIN_CLIENT.KLINE_INTERVAL_1DAY, df=True, decimal=True)
        print(klines)

    loop_timeout = int(COSMOAGENT_CONFIG['loop_timeout'])
    loop_call = task.LoopingCall(loop)
    loop_call.start(loop_timeout)
    reactor.run()
    