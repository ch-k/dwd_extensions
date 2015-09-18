"""
Created on 17.09.2015

@author: Christian Kliche <chk@ebp.de>
"""
import glob
import time


def wait_until_exists(pattern, timeout_sec, wait_after_found_sec):
    """ waits for files matching the given pattern with
    """
    waited = 0
    wait_period = 5

    while waited < timeout_sec:
        if glob.glob(pattern):
            time.sleep(wait_after_found_sec)
            return True
        time.sleep(wait_period)
        waited += wait_period

    return False


def eval_default(expression, default_res=None):
    """Calls eval on expression and returns default_res if it throws
    exceptions
    """
    if default_res is None:
        default_res = expression
    try:
        return eval(expression)
    except:
        pass
    return default_res
