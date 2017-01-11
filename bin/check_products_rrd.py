#!/usr/bin/env python

import os
import stat
import fnmatch
from time import sleep
from os.path import basename
from os.path import splitext
from tempfile import mkstemp
from datetime import datetime
from datetime import timedelta
from optparse import OptionParser
from dwd_extensions.qm.sat_incidents.repository import AnnouncementImpactEnum
from dwd_extensions.qm.sat_incidents.service import SatDataAvailabilityService
import rrdtool as rrd

STATUS_OK = 0
STATUS_WARNING = 1
STATUS_CRITICAL = 2
STATUS_UNKNOWN = 3


def listfiles(d, pattern):
    """return list of files in directory"""
    return [os.path.join(d, o) for o in os.listdir(d)
            if os.path.isfile(os.path.join(d, o)) and
            fnmatch.fnmatch(o, pattern)]


def to_unix_seconds(dt):
    return int(dt.strftime("%s"))


def extract_prod_name(thefile):
    return splitext(basename(thefile))[0]


def check_rrds(rrddir, max_age_minutes, max_age_intervals=2.0,
               sat_availability_config=None, test_ref_datetime=None):
    """
    analyses the rrdtool files in the specified directory
    """
    old_prods = []
    new_prods = []
    all_prods = []
    old_prods_ok = []

    if sat_availability_config:
        sat_avail_service = SatDataAvailabilityService(
            config_yml_filename=sat_availability_config)
    else:
        sat_avail_service = None

    files = listfiles(rrddir, '*.rrd')
    for rrdfile in files:
        step = rrd.info(rrdfile)['step']
        if max_age_minutes is None:
            current_max_age_minutes = max_age_intervals * (step / 60.0)
        else:
            current_max_age_minutes = max_age_minutes

        if test_ref_datetime is None:
            # should be default
            reftime_dt = datetime.utcnow() - timedelta(
                seconds=current_max_age_minutes * 60)
        else:
            # only for debugging purposes
            reftime_dt = test_ref_datetime - timedelta(
                seconds=current_max_age_minutes * 60)

        reftime = to_unix_seconds(reftime_dt)
        name = extract_prod_name(rrdfile)
        last = rrd.last(rrdfile)
        # print "name: " + name + " reftime: " + str(reftime)
        # + " last: " + str(last) + " max_age_minutes: "
        # + str(current_max_age_minutes)
        #  + " steps: " + str(step) + " max_age_intervals: "
        #  + str(max_age_intervals)
        if last < reftime:
            if sat_avail_service:
                res = sat_avail_service.get_data_availability_error(reftime_dt,
                                                                    name)
                if res:
                    print "{} {} {}".format(res, reftime_dt, name)
                    old_prods_ok.append(name)
                else:
                    old_prods.append(name)
            else:
                old_prods.append(name)
        else:
            # retrieve last 3 datapoints
            # seems that fetch delivers one datapoint before and after required
            # start/end, so using "--start e-step*2 --end last-step" instead of
            # "--start e-step*3 --end last"
            data = rrd.fetch(rrdfile, 'MAX',
                             '--resolution', str(step),
                             '--start', 'e-' + str(step * 2),
                             '--end', str(last - step))
            lastvalues = [a for (a, _) in data[2]]
            if (lastvalues[-1] is not None and
                    (lastvalues[:-1] == [None] * (len(lastvalues) - 1))):
                new_prods.append(name)
        all_prods.append(name)

    return old_prods, new_prods, all_prods, old_prods_ok


def write_result_and_exit(code, message, cache_file):
    """
    writes the result code and message to a cache file (if not None),
    writes message to stdout and exits with code
    """
    if cache_file is not None:
        _, temp_file = mkstemp()
        try:
            with open(temp_file, 'w') as f:
                f.write(str(code) + '\n')
                if code == STATUS_OK:
                    f.write('OK - ')
                elif code == STATUS_WARNING:
                    f.write('WARNING - ')
                elif code == STATUS_CRITICAL:
                    f.write('CRITICAL - ')
                elif code == STATUS_UNKNOWN:
                    f.write('UNKNOWN - ')
                f.write(message)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.system('mv -f %s %s' % (temp_file, cache_file))
            # used mv to allow cross-device links
            # os.rename(temp_file, cache_file)
            # add read permissions for everyone
            os.chmod(cache_file,
                     os.stat(cache_file).st_mode | stat.S_IRGRP | stat.S_IROTH)
        except Exception as e:
            print e
            if os.path.exists(temp_file):
                os.remove(temp_file)
    print message
    exit(code)


def read_result_and_exit(cache_file, max_cache_file_age_minutes):
    """
    read check age of cached file and read the cached result from file
    """
    if cache_file is not None:
        message = ("could not read monitoring cache file\n"
                   "please check if monitoring script is called at"
                   " least every %s minutes (cache file: %s)"
                   % (max_cache_file_age_minutes, cache_file))
        code = STATUS_CRITICAL

        # repeat if file is not accessible
        for i in range(5):
            try:
                t = os.path.getmtime(cache_file)
                age_minutes = (int(datetime.now().strftime("%s")) - t) / 60
                if age_minutes > max_cache_file_age_minutes:
                    message = ("monitoring cache file too old\n"
                               "please check if monitoring script is called at"
                               " least every %s minutes (cache file: %s)"
                               % (max_cache_file_age_minutes, cache_file))
                    code = STATUS_CRITICAL
                    break
                with open(cache_file, 'r') as f:
                    code = int(f.readline())
                    message = ''.join(f.readlines())
                break
            except:
                sleep(1)
                # try again (maybe file is written currently)
    print message
    exit(code)


def main():

    # override default formater to allow line breaks
    OptionParser.format_description = \
        lambda self, formatter: self.description
    OptionParser.format_epilog = \
        lambda self, formatter: self.epilog

    description = """\
This script can be used as Nagios plugin to check the product files created
by trollduction. The script iterates over the rrd files (created and updated by
trollductions postprocessor) in the specified directory.

IMPORTANT ASSUMPTIONS:

The performance data of each product is written into an own rrd file.

"""

    epilog = '''\

Results:
  The script returns with code "2" when an error was detected
  otherwise with code "0". Possible errors are:
    - a product's rrd file exists but it was not updated recently
    - there are no rrd files (and therefore it is assumed that there are no
      products)

'''

    parser = OptionParser(description=description, epilog=epilog)
    parser.add_option("-d", "--rrd-directory",
                      action="store",
                      type="string",
                      dest="rrddir",
                      metavar="PATH",
                      help="path to rrd files")

    parser.add_option("-a", "--max-age",
                      action="store",
                      type="int",
                      default=None,
                      dest="max_age_minutes",
                      metavar="MINUTES",
                      help="maximum allowed age of product files (in minutes)"
                      ", the time slot added by the last update of "
                      "corresponding rrd file")

    parser.add_option("-i", "--max-age-intervals",
                      action="store",
                      type="float",
                      default=2.0,
                      dest="max_age_intervals",
                      metavar="INTERVALS",
                      help="maximum allowed age of product files (number of intervals)"
                      ", the time slot added by the last update of "
                      "corresponding rrd file")

    parser.add_option("-w", "--write-cache-file",
                      action="store",
                      type="string",
                      default=None,
                      dest="writefile",
                      metavar="FILE",
                      help="writes the output to cache file")

    parser.add_option("-r", "--read-cache-file",
                      action="store",
                      type="string",
                      default=None,
                      dest="readfile",
                      metavar="FILE",
                      help="reads the output from cache file")

    parser.add_option("-c", "--max-cache-file-age",
                      action="store",
                      type="int",
                      default=15,
                      dest="max_cache_file_age_minutes",
                      metavar="MINUTES",
                      help="maximum allowed age of the cache file "
                      "(in minutes)")

    parser.add_option("-s", "--sat-data-availability-config",
                      action="store",
                      type="string",
                      default=None,
                      dest="sat_availability_config",
                      metavar="FILE",
                      help="path to configuration of "\
                      "satellite availability service")

    try:
        (options, _) = parser.parse_args()
    except:
        parser.print_help()
        exit(STATUS_UNKNOWN)

    if options.readfile is not None:
        read_result_and_exit(options.readfile,
                             options.max_cache_file_age_minutes)

    else:

        if not options.rrddir:
            parser.print_help()
            exit(STATUS_UNKNOWN)

        old_prods, new_prods, all_prods, old_prods_ok \
            = check_rrds(options.rrddir,
                         options.max_age_minutes,
                         options.max_age_intervals,
                         options.sat_availability_config,
                         test_ref_datetime=None)
                         # test_ref_datetime=datetime(2016,12,6,21,00))
        additional_info = ""
        if len(old_prods_ok) > 0:
            additional_info = "\n(Following products missing but matching "\
            "EUMETSAT UNS announcement found: {})".format(", ".join(old_prods_ok))

        if len(all_prods) == 0:
            write_result_and_exit(
                STATUS_CRITICAL,
                "no products generated",
                options.writefile)
        elif len(old_prods) > 0:
            write_result_and_exit(
                STATUS_CRITICAL,
                "recently created products missing or to old\n{}{}".format(
                    ", ".join(old_prods), additional_info),
                options.writefile)
        elif len(new_prods) > 0:
            write_result_and_exit(
                STATUS_OK,
                "new products found\n{}{}".format(
                    ", ".join(new_prods), additional_info),
                options.writefile)
        else:
            write_result_and_exit(
                STATUS_OK,
                "{} products generated{}".format(len(all_prods),
                                                 additional_info),
                options.writefile)

if __name__ == "__main__":
    main()
