#!/usr/bin/python


"""
   PowerMon!
   A script to read power meter readings from a 433MHz energy sensor and write them to a RRD file.
   In my case, the power meter is an Owl CM180. 
   This script requires rtl_433 from https://github.com/merbanan/rtl_433, with a little hackery to
   make the output parseable.
   To be used by the accompanying powermon_web.py script which provides a HTTP server to generate
   graphs from the RRD database file.
"""

import sys
import subprocess
import re
import traceback
import logging
import logging.handlers
import argparse



def init(rrd_file):

# The buckets are:
#  1) 1:4320 = 1 reading every 10 seconds, 1 reading per sample, storing 4320 samples =  12 hours of recording. 
#  2) 6:1440 = 1 reading every 10 seconds, 6 readings per sample, storing 1440 samples = 24 hours of recording.
#  3) 60:1008 = 1 reading every 10 seconds, 60 readings per sample, storing 1008 samples = 7 days of recording.
	cmd = "rrdtool create {} --step 10 \
DS:watts:GAUGE:300:0:5000 \
RRA:LAST:0.5:1:60480 \
RRA:AVERAGE:0.5:1:4320 \
RRA:AVERAGE:0.5:6:1440 \
RRA:AVERAGE:0.5:60:1008 \
RRA:MIN:0.5:1:3600 \
RRA:MIN:0.5:6:1440 \
RRA:MIN:0.5:60:1008 \
RRA:MAX:0.5:1:3600 \
RRA:MAX:0.5:6:1440 \
RRA:MAX:0.5:60:1008 \
".format(rrd_file)


	logging.info("Initializing RRD with command: {} ".format(cmd))
	o = subprocess.check_output(cmd, stderr = subprocess.STDOUT, shell=True)
	logging.info("Completed init.")



def update_rrd(rrd_file, power, ts):
	cmd = "rrdtool update {} {}:{}".format(rrd_file, ts, power)
	logging.info("Updating rrd with command: {}".format(cmd))
	o = subprocess.check_output(cmd, stderr = subprocess.STDOUT, shell=True)


def run(rrd_file):
	popen = subprocess.Popen('rtl_433', stdout = subprocess.PIPE)
	l_iter = iter(popen.stdout.readline, b'')
	for line in l_iter:
		# Example line: Energy Sensor CM180, Id: 62a1, power: 577W, Time: 1452027145 
		if line.startswith('Energy Sensor CM180'):
			m = re.search(r"power: (\d+)", line)
			power = m.group(1)
			m = re.search(r"Time: (\d+)", line)
			ts = m.group(1)
			logging.info("Sensor reading {} watts at {} epoch seconds.".format(power, ts))
			update_rrd(rrd_file, power, ts)


# Run rtl_433 in subprocess reading stdout
# Parse each line into time and watts
# Insert into rrd.
def main():
	parser = argparse.ArgumentParser(description='Powermon')
	parser.add_argument('--log', help='Log file', default='powermon.log')
	parser.add_argument('--init', help='Initializes RRD database file', default=False, action='store_true')
	parser.add_argument('--rrd_file', help='RRD filename', default='power.rrd')

	args = parser.parse_args()

	logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
	rootLogger = logging.getLogger()
	fileHandler = logging.handlers.RotatingFileHandler(args.log, maxBytes=(1048576*5), backupCount=7)
	fileHandler.setFormatter(logFormatter)
	rootLogger.addHandler(fileHandler)

	consoleHandler = logging.StreamHandler(sys.stdout)
	consoleHandler.setFormatter(logFormatter)
	rootLogger.addHandler(consoleHandler)

	rootLogger.setLevel(logging.DEBUG)

	logging.info('Powermon started.')

	if args.init:
		init(args.rrd_file)
	else:
		run(args.rrd_file)


	logging.info('Powermon ending.')



if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt as e:
		traceback.print_exc()
	except Exception as e:
		traceback.print_exc()



