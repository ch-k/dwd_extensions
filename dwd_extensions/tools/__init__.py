"""
Created on 17.09.2015

@author: Christian Kliche <chk@ebp.de>
"""
import glob
import time


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
