#!/usr/bin/python


"""
   PowerMon!
   A script to read power meter readings from a 433MHz energy sensor and write them to a RRD file.
   In my case, the power meter is an Owl CM180. 
   This script requires rtl_433 from https://github.com/merbanan/rtl_433, with a little hackery to
   make the output parseable.
"""

import sys
import subprocess
import re
import traceback
import logging
import logging.handlers
import argparse
import BaseHTTPServer
from urlparse import urlparse, parse_qs
import tempfile
import threading
import json


LAST_POWER_READ = 0
RRD_FILE = None

#####################
# Web Server
#####################

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
   
    def do_GET(s):
        """Respond to a GET request."""
        s.send_response(200)
        args = parse_qs(urlparse(s.path).query)

        if s.path == "/data":
        	# Return JSON representation
        	renderDataJSON(s)
        elif s.path.startswith("/denkimonconf"):
        	renderDenkiMonConf(s)
        elif "graph" not in args:
        	renderPowerGraphHTML(s)
        else:
        	renderGraphImage(s, args["graph"][0])


def renderDataJSON(s):
	s.send_header("Content-type", "application/json")
	s.end_headers()

	json.dump({ 'power_now' : LAST_POWER_READ }, s.wfile)


def renderDenkiMonConf(s):
	s.send_header("Content-type", "text/html")
	s.end_headers()

	with open('denkimondconf.html', 'r') as htmlf:
		s.wfile.write(htmlf.read())
        


def renderPowerGraphHTML(s):
	s.send_header("Content-type", "text/html")
	s.end_headers()

	s.wfile.write("""
<html>
<head>
<title>Power Consumption</title>
</head>
<body>
<h1>Previous 1 Hour</h1>
<img src="?graph=1h" border=0"/>
<h1>Previous 1 Hour Actual Values</h1>
<img src="?graph=1h_raw" border=0"/>
<h1>Previous 6 Hours</h1>
<img src="?graph=6h" border=0"/>
<h1>Previous 24 Hours</h1>
<img src="?graph=24h" border=0"/>
<h1>Previous 7 days</h1>
<img src="?graph=7d" border=0"/>
</body>
</html>
	""")
        


def renderGraphImage(s, graph_type):
	s.send_header("Content-type", "image/png")
	s.end_headers()

	(fh, tmpfile) = tempfile.mkstemp()

	rrdcmd = 'rrdtool graph {filename} --width 1200 --height 480  \
	--imgformat PNG \
	--start end-{duration} --end now \
	--slope-mode --vertical-label Watts \
	DEF:MinPower={rrd_file}:watts:MIN:step={step} \
	DEF:MaxPower={rrd_file}:watts:MAX:step={step} \
	DEF:Power={rrd_file}:watts:AVERAGE:step={step} \
	CDEF:Range=MaxPower,MinPower,-    \
	LINE1:MinPower#00FF00:"Min" \
	AREA:Range#8dadf5::STACK \
	LINE1:MaxPower#FF0000:"Max" \
	LINE2:Power#0000FF:"Average" \
	'

	rrdcmd_raw = 'rrdtool graph {filename} --width 1200 --height 480  \
	--imgformat PNG \
	--start end-{duration} --end now \
	--slope-mode --vertical-label Watts \
	DEF:Power={rrd_file}:watts:LAST:step={step} \
	LINE1:Power#0000FF:"Actual" \
	'


	if graph_type == "6h":
		rrdcmd = rrdcmd.format(filename = tmpfile, rrd_file = RRD_FILE, duration="6h", step="300") #"300")
	elif graph_type == "1h":
		rrdcmd = rrdcmd.format(filename = tmpfile, rrd_file = RRD_FILE, duration="1h", step="30") #"60")
	elif graph_type == "1h_raw":
		rrdcmd = rrdcmd_raw.format(filename = tmpfile, rrd_file = RRD_FILE, duration="1h", step="10") #"60")
	elif graph_type == "24h":
		rrdcmd = rrdcmd.format(filename = tmpfile, rrd_file = RRD_FILE, duration="24h", step="300") #"300")
	elif graph_type == "7d":
		rrdcmd = rrdcmd.format(filename = tmpfile, rrd_file = RRD_FILE, duration="7d", step="600") #"300")
	else:
		logging.error("Unexpected graph type.")
		return

	logging.info("Running rrd command: {} ".format(rrdcmd))

	try:
		o = subprocess.check_output(rrdcmd, stderr = subprocess.STDOUT, shell=True)
	except subprocess.CalledProcessError as e:
		logging.error("Ooops, rrdtool failed: {}".format(e.output))
	with open(tmpfile, 'rb') as imgfile:
		s.wfile.write(imgfile.read())



class HTTPThread (threading.Thread):
    def __init__(self, port):
        threading.Thread.__init__(self)
        self.port = port
    def run(self):
        logging.info( "Starting HTTP Thread" )
        run_http(self.port)
        logging.info("Exiting HTTP Thread" )

def run_http(port):
    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class(('', port), MyHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()




##########
# rtl_433 reader
##########



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
	global LAST_POWER_READ

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
			LAST_POWER_READ = power








# Run rtl_433 in subprocess reading stdout
# Parse each line into time and watts
# Insert into rrd.
def main():
	parser = argparse.ArgumentParser(description='Powermon')
	parser.add_argument('--log', help='Log file', default='powermon.log')
	parser.add_argument('--init', help='Initializes RRD database file', default=False, action='store_true')
	parser.add_argument('--rrd_file', help='RRD filename', default='power.rrd')
	parser.add_argument('--http_port', help='Port number of HTTP server', default=9000)


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

	global RRD_FILE
	RRD_FILE = args.rrd_file

	logging.info('Powermon started.')

	if args.init:
		init(args.rrd_file)
	else:
		t = HTTPThread(args.http_port)
		t.start()
		run(args.rrd_file)


	logging.info('Powermon ending.')



if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt as e:
		traceback.print_exc()
	except Exception as e:
		traceback.print_exc()



