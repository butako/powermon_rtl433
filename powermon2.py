#!/usr/bin/python3

import sys
import subprocess
import json
import time
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import traceback

def main():

	while True:
		print('INFO: Starting up!')
		popen = subprocess.Popen(['/usr/local/bin/rtl_433','-F','json','-M','utc'], stdout = subprocess.PIPE, universal_newlines=True)
		l_iter = iter(popen.stdout.readline, '')
		print('INFO: OK, waiting for data...')
		for line in l_iter:
			try:
				print('INFO: Data received:',line)
				m=json.loads(line)
				model=m['model']
				id=m['id']
				if model in ['CM180','WG-PB12V1']:
					if model=='CM180':
						id=1
						if "power_W" in m:
							# Sometimes receive very high impossible power values, so cap to a sensible max.
							m['power_W'] = max(int(m['power_W']), 5000)
					topic="homeassistant/sensor/{}/{}".format(model,id)
					print('INFO: Publishing on topic {} message {}'.format(topic, line))
					publish.single(topic,
								   line,
								   hostname="hassio.localnet",
								   protocol=mqtt.MQTTv311,
								   auth={'username':'homeassistant', 'password':''})
					print('INFO: Publish done.')
			except Exception as ex:
				print('ERROR: Problem during parsing data')
				traceback.print_exc()
		print('ERROR: rtl_433 exited!! Restarting in 60 seconds')
		time.sleep(60)



if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt as e:
		traceback.print_exc()
	except Exception as e:
		traceback.print_exc()

