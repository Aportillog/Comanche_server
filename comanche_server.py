#!/usr/bin/python
import signal
import socket
import sys
import os
import select
import re
import os, time
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime

os.system('clear')

#Variables Globales
show_httpheader = 'off'
size_of_fragmentation = 12000
MimeMap = {}
ResponseMap = {}
ServerConfMap = {}
Key = {}
#------------- Clases -------------------#
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

#------------------------------------Funciones-------------------------------------#
#Funcion procesar archivos de configuracion, retorna un dicionario
def processConf(path):
	try:
		descriptor = open(path,'r')
		statinfo = os.stat(path)
		buff = descriptor.read(statinfo.st_size)
	except IOError as e:
		print 'I/O error ({0}):{1}'.format(e.errno,e.strerror)
		return 0
	rmap = {}
	data = buff.split("\n")
	for i in range(0,len(data)):
		key = data[i].split("=")[0]
		value = data[i].split("=")[1]
		rmap[key] = value
	return rmap
#Funcion CTRL+C, cierre controlado de los socket
def signal_handler(signal, frame):
	print(bcolors.WARNING + '\n>>>Se ha pulsado Ctrl+C. Se cierra el socket.' + bcolors.ENDC)
	for s in input:
		s.close()
	fd.close()
	fdc.close()
	sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)
#Funcion para procesar headers, retorna un dicionario
def processHeaders(request):
	rmap = {}
	localRequest = re.split('\r\n\r\n',str(request))
	header = localRequest[0].split("\r\n")
	rmap["HttpHeader"] = header[0].split()
	for i in range(1,len(header)):
		key = re.split('(:\s)',header[i])[0]
		value = re.split('(:\s)',header[i])[2]
		rmap[key] = value
	if str(rmap["HttpHeader"][0]) == 'POST':
		rmap["Date"]=localRequest[1]
	return rmap
#Funcion que retorna un dicionario en el cual se contiene los distintos campos para una respuesta al navegador
def setHeader(requestMap):
	localHeader = {}
	ifModSince = ''
	content_flag=0 #Flag para anadir cabeceras de contenido
	path = requestMap["HttpHeader"][1]
	#Cabecera principal (version,codigo,mensaje)
	if os.path.isfile(path): #Si existe el archivo requerido
		try:
			ifModSince = str(requestMap['If-Modified-Since'])
		except:
			pass
		#Testeamos entre mandar un mensaje 200 , o un 304.
		if (ifModSince == str(time.ctime(os.path.getmtime(path))) and ServerConfMap['If_Modified_Since'] == "YES"): #Fecha de modificacion mayor que la de la request
			localHeader["HttpHeader"] = (requestMap["HttpHeader"][2],"304",ResponseMap["304"])
			content_flag = 0
		else:
			localHeader["HttpHeader"] = (requestMap["HttpHeader"][2],"200",ResponseMap["200"])
			content_flag = 1
	else:
		localHeader["HttpHeader"] = (requestMap["HttpHeader"][2],"404",ResponseMap["404"])
		content_flag = 0
	#Cabeceras de contenido
	if content_flag:
		localHeader["Last-Modified"] = str(time.ctime(os.path.getmtime(path)))
		extension = '.'+requestMap["HttpHeader"][1].split('.')[1]
		localHeader["Content-Type"] = str(MimeMap[extension].replace('\r',''))
		statinfo = os.stat(path)
		localHeader["Content-Length"] = str(statinfo.st_size)
	#Cabecera nombre servidor
	localHeader["Server"] = "Comanche/1.0"
	#Cabecera de fecha
	now = datetime.now()
	stamp = mktime(now.timetuple())
	localHeader["Date"] = str(format_date_time(stamp))
	#Cabecera de tipo de conexion, testeamos si esta activamo la opcion persistente en el servidor, y que nos ha dicho el navegador
	if ServerConfMap['Keep_alive'] == 'YES' and requestMap['Connection'] == 'Keep_alive':
		localHeader["Connection"] = 'keep-alive'
	elif ServerConfMap['Keep_alive'] == 'NO':
		localHeader["Connection"] = 'close'
	return localHeader 
#Funcion enviar mensaje, en ella se construira el mensaje a mandar a partir de un dicionario
def send_file(des,requestMap, flagConf):
	buffToSend = ''
	contador_bytes = 0
	requestFile = str(requestMap["HttpHeader"][1])
	if (requestFile == "/"):
		if(flagConf):
			requestMap["HttpHeader"][1] = "comanche_config.html"
		else:
			requestMap["HttpHeader"][1] = ServerConfMap['Default_page'] #Cambio necesario para enviar html por defecto, definido en el conf
	if(not flagConf):
		path = requestMap["HttpHeader"][1] = str(ServerConfMap['Default_path']) + re.sub(r'^[\/]+?','',requestMap["HttpHeader"][1]) #Ignorar la primera "/" en una ruta y anadir la ruta por defecto
	else:
		path = requestMap["HttpHeader"][1] = str(ServerConfMap['Default_conf_path']) + re.sub(r'^[\/]+?','',requestMap["HttpHeader"][1])
	#Construir cabecera de respuesta
	ResponseHeader = setHeader(requestMap)
	#Enviar el mensaje
	buffToSend += ResponseHeader["HttpHeader"][0] + ' ' + ResponseHeader["HttpHeader"][1] + ' ' +ResponseHeader["HttpHeader"][2] + '\r\n' #Anadimos la cabecera con el codigo, para que sea la primera
	for i in ResponseHeader:
		if str(i) != "HttpHeader":
			buffToSend += str(i) +': ' +str(ResponseHeader[i]) + '\r\n'
	buffToSend += '\r\n' #Nos aseguramos de que la cabecera termine en \r\n\r\n
	if show_httpheader == 'on':
		print bcolors.OKBLUE+'------Se envia la siguiente respuesta mediante el descriptor '+str(des.fileno())+'------\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n' +buffToSend+'\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'+bcolors.ENDC###PETICION WEB###
	print bcolors.OKBLUE + '>>>Respuesta '+ResponseHeader["HttpHeader"][1]+' '+ResponseHeader["HttpHeader"][2]+' enviada por el descriptor '+ str(s.fileno())+'. Fichero: '+requestMap["HttpHeader"][1] +bcolors.ENDC
	#Enviamos la cabecera
	des.sendall(buffToSend)
	#Si el codigo es 200, el mensaje tiene contenido
	if str(ResponseHeader["HttpHeader"][1]) == "200":
		descriptor = open(path,'rb')
		statinfo = os.stat(path)
		try:
			while contador_bytes < statinfo.st_size:
				buffToSend = descriptor.read(size_of_fragmentation)
				des.sendall(buffToSend)
				contador_bytes += size_of_fragmentation
		except IOError:
			buffToSend = 'HTTP/1.1 500 Internal Server Error\nConnection: Close\r\n\r\n'
			print bcolors.FAIL + buffToSend +bcolors.ENDC
			print bcolors.FAIL + '>>>Respuesta 500 enviada al descriptor '+ str(newclient.fileno()) + bcolors.ENDC
			des.sendall(buffToSend)
	#Cerramos el socket de la peticion
	if ServerConfMap['Keep_alive'] == 'OFF':
		print bcolors.WARNING + '>>>Se CIERRA el descriptor '+ str(s.fileno())+ ' la conexion con '+str(List[s.fileno()][0])+':'+str(List[s.fileno()][1])+bcolors.ENDC
		del List[des.fileno()]
		input.remove(des)
		des.close()	
#Funcion para crear descriptores en los distintos puertos
def createDesc(port):
	try:
		fda = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	except socket.error, msg:
		print bcolors.FAIL +'\n-1-No se ha podido crear el socket.\nTipo de error: ' + msg[1]+ bcolors.ENDC
		sys.exit()
	try:
		fda.bind(('', int(port)))
	except socket.error, msg:
		print bcolors.FAIL +'\n-1-No se ha podido conectar el socket.\nTipo de error: ' + msg[1]+ bcolors.ENDC
		sys.exit()
	try:
		fda.listen(20)
	except socket.error, msg:
		print bcolors.FAIL +'\nNo se ha podido crear la cola.\nTipo de error: ' + msg[1]+ bcolors.ENDC
		s.close()
		sys.exit()
	return fda
#Funcion para modificar la configuracion
def changeConf(requestMap):
	changes = {}
	chan = requestMap.split('&')
	#Extraemos los datos en un dicionario
	for i in range(0,len(chan)):
		key = chan[i].split('=')[0]
		value = chan[i].split('=')[1]
		changes[key] = value
	#Modificara los ficheros
	if ((Key['Userid'] == changes ['Userid']) and (Key['Password'] == changes ['Password'])):
		for i in changes:
			if i != 'Userid' and i != 'Password':
				print i + ': ' + changes[i]
				modConf(i,changes[i],'comanche_server.conf') #Esta funcion nos modificara los ficheros
				ServerConfMap [i] = changes[i] #Cambio en caliente
	else:
		print bcolors.FAIL + 'Fallo de autentificacion con el usuario: ' + Key['Userid'] + bcolors.ENDC
#Funcion para modificar cualquier fichero con "key=value"
def modConf(key,value,path):
	conf = processConf(path)
	conf [key] = value
	os.remove(path)
	source = file(path,'w')
	cont = 0
	for i in conf:
		cont += 1
		if cont == len(conf):
			add = i+'='+conf[i]
		else:
			add = i+'='+conf[i]+'\n'
		source.write(add)
#-------------------------------------Programa principal----------------------------------#
if len(sys.argv) != 2:
	print bcolors.FAIL + '\nEL USO CORRECTO ES: python %s <Puerto>' % (sys.argv[0])  + bcolors.ENDC
	sys.exit()

#-------Variables---------#
#Variables del programa
size = 16000
localPort = str(int(sys.argv[1]))
confPort = "8000"
requestMap = {}
input = [sys.stdin]
List = {}
timeout = 1
#Variables de configuracion
ServerConfMap = processConf('comanche_server.conf')
MimeMap = processConf('mime.dat')
ResponseMap = processConf('response.dat')
Key = processConf('key.dat')
#Crear un descriptor de referencia,para canalizar las nuevas conexiones
fd = createDesc(localPort)
input.append(fd)
fd.setblocking(0)
#Crear otro descriptor para la configuracion del server
fdc = createDesc(confPort)
input.append(fdc)
fdc.setblocking(0)
confPortList = [] #Esta lista de puertos sera utilizada para diferenciar entre la web y la pagina de configuracion
#----------------------- Mensajes de bienvenida del server --------------------------------------
print bcolors.HEADER + '------------>Bienvenido a Comanche Server 1.0<-----------------' + bcolors.ENDC
print bcolors.HEADER + '----->A la escucha de peticiones por el puerto '+ localPort +'<------------' + bcolors.ENDC
#------------------------------------------------------------------------------------------------
#Main loop
running = 1
while running:
	inputready,outputready,exceptready = select.select(input,[],[], timeout)
	for s in inputready:
		#Comandos desde la consola del servidor
		if s == sys.stdin:
			message = sys.stdin.readline()
			if message == 'debug on\n':
				print 'Se ha activado la opcion de mostrar las cabeceras de los mensajes HTTP.'
				show_httpheader = 'on'
			if message == 'debug off\n':
				print 'Se ha desactivado la opcion de mostrar las cabeceras de los mensajes HTTP.'
				show_httpheader = 'off'
			if message == 'quit\n':
				fd.close()
				fdc.close()
				for s in input:
					s.close()
				sys.exit(0)
			break
		#Nuevo cliente de configuracion
		if s==fdc:
			print bcolors.WARNING + '>>>Conexion de cliente a puerto 8000'+bcolors.ENDC
			newclient, addr = fdc.accept()
			List[newclient.fileno()]= addr
			input.append(newclient)
			confPortList.append(newclient)
			print bcolors.WARNING + '>>>Se CREA por el descriptor ' +str(newclient.fileno())+ ' la conexion con '+str(List[newclient.fileno()][0])+':'+str(List[newclient.fileno()][1])+bcolors.ENDC
			break
		#Nuevo cliente de pagina web
		if s==fd:
			#Creamos los socket. Los gestiaremos mediante el dicionario "List", y la tupla "input"
			newclient, addr = fd.accept()
			List[newclient.fileno()]= addr
			input.append(newclient)
			print bcolors.WARNING + '>>>Se CREA por el descriptor ' +str(newclient.fileno())+ ' la conexion con '+str(List[newclient.fileno()][0])+':'+str(List[newclient.fileno()][1])+bcolors.ENDC
			break
		#Configuracion web del servidor
		if s in confPortList:
			try:
				request = s.recvfrom(size)[0]
			except socket.error, msg:
				print bcolors.FAIL + '>>>Fallo en la recepcion.\nTipo de error: ' + msg[1] + bcolors.ENDC
				input.remove(s)
				confPortList.remove(s)
				s.close()
				break
			#Testeamos si recibimos 0 bytes para cierre
			if len(request) == 0:
				print bcolors.WARNING + '>>>Se CIERRA a peticion del navegador el descriptor '+ str(s.fileno())+ ' la conexion con '+str(List[s.fileno()][0])+':'+str(List[s.fileno()][1])+bcolors.ENDC
				del List[s.fileno()]
				input.remove(s)
				confPortList.remove(s)
				s.close()
				break
			requestMap = processHeaders(request) #Diccionario con la request
			if requestMap["HttpHeader"][0] == "POST":
				changeConf(requestMap['Date'])
				send_file(s,requestMap,1)
				break	
			else:
				send_file(s,requestMap,1)
				break
		#Peticiones web del navegador
		else:
			#Timeout de 1 segundos
			s.settimeout(1)
			try:
				request = s.recvfrom(size)[0]
			except socket.error, msg:
				print bcolors.FAIL + '>>>Fallo en la recepcion.\nTipo de error: ' + msg[1] + bcolors.ENDC
				input.remove(s)
				s.close()
				break
			if show_httpheader == 'on':#Testeo de lo que recibimos
				print bcolors.BOLD+'------Se recibe del navegador '+str(s.fileno())+'------\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n' +request+'\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'+bcolors.ENDC###PETICION WEB###
			#Testeamos si recibimos 0 bytes para cierre
			if len(request) == 0:
				print bcolors.WARNING + '>>>Se CIERRA a peticion del navegador el descriptor '+ str(s.fileno())+ ' la conexion con '+str(List[s.fileno()][0])+':'+str(List[s.fileno()][1])+bcolors.ENDC
				del List[s.fileno()]
				input.remove(s)
				s.close()
				break
			else:
				requestMap = processHeaders(request) #Diccionario con la request
				send_file(s,requestMap,0)
#Cerramos el socket principal
print bcolors.WARNING + '>>>Cerramos el socket.\n\n' + bcolors.ENDC
fd.close()
fdc.close()