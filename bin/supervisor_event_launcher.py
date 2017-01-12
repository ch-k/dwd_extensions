#!/usr/bin/env python
#
# based on http://stackoverflow.com/questions/27341846/using-supervisor-as-cron
#
# executes its first argument with any remaining arguments

import sys
import subprocess

# python 2.6 is missing check_output
# http://stackoverflow.com/a/13160748/3584189
#
# duck punch it in!
if "check_output" not in dir(subprocess):
    def f(*popenargs, **kwargs):
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, '
                             'it will be overridden.')
        process = subprocess.Popen(stdout=subprocess.PIPE,
                                   *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise subprocess.CalledProcessError(retcode, cmd)
        return output
    subprocess.check_output = f


def write_stdout(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def write_stderr(s):
    sys.stderr.write(s)
    sys.stderr.flush()


def main(args):
    while 1:
        # transition from ACKNOWLEDGED to READY
        write_stdout('READY\n')
        # read header line from stdin
        line = sys.stdin.readline()
        # print it out to stderr
        write_stderr(line)
        headers = dict([x.split(':') for x in line.split()])
        # read the event payload
        data = sys.stdin.read(int(headers['len']))
        # don't mess with real stdout
        subprocess.check_output(args, shell=True)
        write_stderr(data)
        # transition from READY to ACKNOWLEDGED
        write_stdout('RESULT 2\nOK')


if __name__ == '__main__':
    main(sys.argv[1:])
