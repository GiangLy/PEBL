#!/usr/bin/env python

"""
PEBL program by Giang Ly
A Program that enables connection to a Raspberry Pi via Bluetooth through
an Android Application. Takes user input and allows collection of environmental
data as well as customize LED output.
"""
from bluetooth import *
from subprocess import *
from neopixel import *
from re import *
from Adafruit_BME280 import *
from gps3 import gps3
import time
import sys
from threading import *
import RPi.GPIO as GPIO

"""
Global Variables to access accross multiple threads
"""
strip = Adafruit_NeoPixel(23, 18, 800000, 5, False, 255, 0, ws.SK6812_STRIP_RGBW)
setting = 'null'
color = Color(0,0,0,0)
client = 'null'

def wheel(pos):
	"""Generate rainbow colors across 0-255 positions."""
        if pos < 85:
                return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
                pos -= 85
                return Color(255 - pos * 3, 0, pos * 3)
        else:
                pos -= 170
                return Color(0, pos * 3, 255 - pos * 3)

def ColorThread():
	"""This is the thread for the LEDs"""
	global setting
	global color
	global strip
	#Begin the loop for thread.
	while 1:
		# Theater setting for LEDs that cycles LED on then Off.
		if setting == 'theater':
			for j in range(10):
				if setting == 'theater':
                			for q in range(3):
						if setting == 'theater':
                        				for i in range(0, strip.numPixels(), 3):
                                				strip.setPixelColor(i+q, color)
                        				strip.show()
                        				time.sleep(50/1000.0)
                        				for i in range(0, strip.numPixels(), 3):
                                				strip.setPixelColor(i+q, 0)
		# Bluetooth Lighting effect to indicate pairing is available
		elif setting == 'bluetooth':
			for i in range(strip.numPixels()):
				strip.setPixelColor(i,Color(0,0,255,0))
				strip.show()
				time.sleep(50/1000.0)
			for j in range(strip.numPixels()):
                                strip.setPixelColor(j,Color(0,0,0,0))
                                strip.show()
				time.sleep(50/1000.0)
		# Confirmation lighting effect when a connection is made.
		elif setting == 'connected':
			for i in range(3):
				for j in range(strip.numPixels()):
                                	strip.setPixelColor(j,Color(255,255,255,255))
                                	strip.show()
				time.sleep(200/1000.0)
				for k in range(strip.numPixels()):
                                	strip.setPixelColor(k,Color(0,0,0,0))
                                	strip.show()
				time.sleep(200/1000.0)
			setting = 'off'
		# Changes one LED at a time and cycles through rainbow spectrum.
		elif setting == 'rainbow1':
        		for j in range(256):
                		if setting == 'rainbow1':
					for i in range(strip.numPixels()):
                        			strip.setPixelColor(i, wheel((i+j) & 255))
                			strip.show()
                			time.sleep(20/1000.0)
		# Changes all LEDs concurrently to one same color throughout the rainbow spectrum.
		elif setting == 'rainbow2':
        		for j in range(256*5):
				if setting == 'rainbow2':
                			for i in range(strip.numPixels()):
                        			strip.setPixelColor(i, wheel(((i * 256 / strip.numPixels()) + j) & 255))
                			strip.show()
                			time.sleep(20/1000.0)
		elif setting == 'static':
			# Changes all LEDs to a single color
			for i in range(strip.numPixels()):
				strip.setPixelColor(i, color)
				strip.show()
		elif setting == 'off':
			# Turns off all LEDs
			for i in range(strip.numPixels()):
                                strip.setPixelColor(i, Color(0,0,0,0))
                                strip.show()
			time.sleep(1)
		else:
			pass
		

def ColorCommand(data):
	"""
	If the command from the bluetooth signal indicates a light command,
	get the color values from the color command.
	"""
	global setting
        global color
	result = search('(?<=LIGHTSTATUS:)\w+', data)
        print ("Light Status: {0}".format(result.group(0)))
	setting = result.group(0)
        result = search('((?<=values:)\d+)\|(\d+)\|(\d+)'  , data)
        red = int(result.group(1))
        green = int(result.group(2))
	blue = int(result.group(3))
        print ("Light Colors: red:{0} green:{1} blue:{2}".format(red,green,blue))
        color = Color(green,red,blue)

def GeoData(sensor, gps_socket, data_stream):
	"""
	If the command from bluetooth connections indicates a status request,
	send Temperature, Pressure, Humidity, and GPS data to mobile application.
	"""
	timeout = 0
	lat = '0'
	lon = '0'

	#Sensor data (Convert as required)
	degrees = sensor.read_temperature() * 1.8 + 32
	pascals = sensor.read_pressure()
	hectopascals = pascals / 100
	humidity = sensor.read_humidity()
	
	gps_socket.connect()
	gps_socket.watch()
	
	for new_data in gps_socket:
    		if new_data:
        		data_stream.unpack(new_data)
        		lat =  data_stream.TPV['lat']
        		lon =  data_stream.TPV['lon']
		elif timeout == 10000:
			break
		elif lat != '0' and lon != '0':
			break
		timeout = timeout + 1
	print ('Temp      = {0:0.3f} deg F'.format(degrees))
	print ('Pressure  = {0:0.2f} hPa'.format(hectopascals))
	print ('Humidity  = {0:0.2f} %'.format(humidity))
	print ('Latitude = {0}'.format(lat))
	print ('Longitude = {0}'.format(lon))

	# Configure response data with a header and information to be sent
	response = "<messageType:2;numArgs:5;/><TEMP:{0:0.3f};HUMIDITY:{1:0.2f};BAROPRESS:{2:0.2f};LATITUDE:{3};LONGITUDE:{4};/>".format(degrees,humidity,hectopascals,lat,lon)
	return response

def BluetoothThread():
	"""
	Bluetooth socket thread that runs concurrent with main program.
	Enables BT discovery and allows for pairing with mobile devices.
	"""
	global setting
	global client

	# Bluetooth configuration
        #hostMACAddress = 'B8:27:EB:1F:AC:4C' # The MAC address of a Bluetooth adapter on the server. The server might have multiple Bluetooth adapters.
        port = 1
        backlog = 1
        size = 1024
	
	#Sensor and GPS Configuration
        try:
                sensor = BME280(t_mode=BME280_OSAMPLE_8, p_mode=BME280_OSAMPLE_8, h_mode=BME280_OSAMPLE_8)
        except IOError:
                print ("Cannot connect to sensor")
                sensor = 'NULL'
                pass

    gps_socket = gps3.GPSDSocket()
    data_stream = gps3.DataStream() 
	s = BluetoothSocket(RFCOMM)
	call(['sudo', 'hciconfig', 'hci0', 'piscan'])
    print("Making device discoverable...")
    s.bind(("",PORT_ANY))
    s.listen(backlog)
 	port = s.getsockname()[1]

        uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"

        advertise_service( s, "PEBL",
                           service_id = uuid,
                           service_classes = [ uuid, SERIAL_PORT_CLASS ],
                           profiles = [ SERIAL_PORT_PROFILE ], 
#                       protocols = [ OBEX_UUID ] 
                         )
	# Loop for thread execution.
	while 1:
	        print ("Starting Socket on port: {0}".format(port))
		
		# Waits for client device to connect.
		try:
                	client, clientInfo = s.accept()
        	except (KeyboardInterrupt,SystemExit):
                	s.close()
                	print("Closing socket")
                	print("Disabling Bluetooth")
                	print "disconnected"
                	call(['sudo', 'hciconfig', 'hci0', 'noscan'])
                	time.sleep(2)
                	setting = 'null'
        		break

        	print ('Connection Established!')

        	if setting == 'bluetooth':
			setting = 'connected'

		while 1:
			# Waits for client to send data (Blocking Mode)
			try:
                        	data = client.recv(size)
                        	if data:
                                	print (data)
                                	result = search('(?<=messageType:)\d+', data)
                               		print ("Message Type: {0}".format(result.group(0)))
                                	message_type = int(result.group(0))
                                	if message_type == 2:
                                        	if sensor != 'NULL':
                                                	client.send(GeoData(sensor, gps_socket, data_stream))
                                        	else:
                                                	client.send("<messageType:2;numArgs:5;/><TEMP:100;HUMIDITY:100;BAROPRESS:100;LATITUDE:n/a;LONGITUDE:n/a;/>")
                                	elif message_type == 3:
                                        	ColorCommand(data)
                                	elif message_type == 4:
						client.close()
                                       		print("Connection lost")
                                        	print("Closing socket")
                                        	print("Disabling Bluetooth")
                                       		print "disconnected"
						time.sleep(2)
                                        	break
					else:
                                        	pass

                	except IOError:
                        	pass
                
                	except AttributeError:
                        	pass

			except BluetoothError:
                        	client.close()
                        	print("Connection lost from client!")
                        	print("Closing socket")
                        	print("Disabling Bluetooth")
                        	print "disconnected"
                        	time.sleep(2)
                        	break 
		

def main():
	"""
	Main program thread. Loops indefinitely.
	"""
	global setting
    global color
    global strip
    global client

	# Pin configuration for push button (Reset Button)
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)
	counter = 0
	
	# Intialize the library (must be called once before other functions).
	strip.begin()

	if setting == 'null':
		# Start threads on start up.
		thread1 = Thread(target=ColorThread)
		thread2 = Thread(target=BluetoothThread)
		setting = 'bluetooth'
		thread1.start()
		thread2.start()

	while 1:
		# Checks to see if reset button is held for more than 6 seconds
		button = GPIO.input(23)
		try:
			if button == False:
        			counter = counter + 1
    			else:
        			counter = 0

    			print (counter)
			
			if counter > 6:
				# Close existing bluetooth connection and prepare unit for new connection
				setting = 'bluetooth'
				counter = 0
				client.shutdown(SHUT_RDWR)
				time.sleep(2)
				client.close()
				time.sleep(2)
			time.sleep(1)
    		except (KeyboardInterrupt,SystemExit):
				print "disconnected"
				thread1.join()
				thread2.join()
				sys.exit(1)
		


if __name__ == "__main__":
	main()
