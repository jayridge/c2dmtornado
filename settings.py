import tornado.options
import logging

tornado.options.define("environment", default="dev", help="environment")

options = {
    'dev' : {
        'logging_level' : logging.DEBUG,
        'memcached' : ['127.0.0.1:11211'],
        'collapse_key' : 'Path',
        'c2dm_url' : 'https://android.apis.google.com/c2dm/send',
        'login_url' : 'https://www.google.com/accounts/ClientLogin',
        'login' : {
            'Email' : '',
            'Passwd' : '',
            'source' : '',
            'service' : 'ac2dm',
            'accountType' : 'HOSTED_OR_GOOGLE',
        }
    }, 
    'prod' : {
        'logging_level' : logging.DEBUG,
        'memcached' : ['127.0.0.1:11211'],
        'collapse_key' : 'Path',
        'c2dm_url' : 'https://android.apis.google.com/c2dm/send',
        'login_url' : 'https://www.google.com/accounts/ClientLogin',
        'login' : {
            'Email' : '',
            'Passwd' : '',
            'source' : '',
            'service' : 'ac2dm',
            'accountType' : 'HOSTED_OR_GOOGLE',
        }
    }
}

default_options = {
}

def env():
    return tornado.options.options.environment

def get(key):
    env = tornado.options.options.environment 
    if env not in options: 
        raise Exception("Invalid Environment (%s)" % env) 
    v = options.get(env).get(key) or default_options.get(key)
    if callable(v):
        return v()
    return v

