#!/usr/bin/python

"""
   PowerMon Web Server!
   Runs a small web server on to serve graphs of power consumption from the RRD database file.
   To be used by the accompanying powermon.py script which reads an rtl_433 device and logs to RRD.
"""


import BaseHTTPServer
from urlparse import urlparse, parse_qs
import tempfile
import argparse
import traceback
import subprocess

RRD_FILE = None

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
   
    def do_GET(s):
        """Respond to a GET request."""
        s.send_response(200)
        args = parse_qs(urlparse(s.path).query)
        if "graph" not in args:
        	renderHTML(s)
        else:
        	renderGraphImage(s, args["graph"][0])

def renderHTML(s):
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
		print "ERROR, unexpected graph type."
		return

	print rrdcmd
	try:
		o = subprocess.check_output(rrdcmd, stderr = subprocess.STDOUT, shell=True)
	except subprocess.CalledProcessError as e:
		print "Ooops, rrdtool failed: ", e.output
		print e
	with open(tmpfile, 'rb') as imgfile:
		s.wfile.write(imgfile.read())



def run_http(port):
    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class(('', port), MyHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()


def main():
	parser = argparse.ArgumentParser(description='Powermon')
	parser.add_argument('--rrd_file', help='RRD filename', default='power.rrd')
	parser.add_argument('--http_port', help='Port number of HTTP server', default=9000)

	args = parser.parse_args()
	global RRD_FILE
	RRD_FILE = args.rrd_file
	run_http(args.http_port)



if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt as e:
		traceback.print_exc()
	except Exception as e:
		traceback.print_exc()



