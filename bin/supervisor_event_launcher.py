#!/usr/bin/env python
#
# based on http://stackoverflow.com/questions/27341846/using-supervisor-as-cron
#
# executes its first argument with any remaining arguments

import sys
import subprocess


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
