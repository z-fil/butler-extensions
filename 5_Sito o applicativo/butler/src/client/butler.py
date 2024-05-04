import threading
from time import sleep
import socket
import getpass
from json.decoder import JSONDecodeError
from os.path import abspath, join
import sys
sys.path.append(abspath(join(sys.path[0],'..')))

from common.logger import Logger
from common import log
from common.argsParser import ArgsParser
from common.notificationBuilder import NotificationBuilder
from common.configParser import ConfigParser

from client.scriptManager import ScriptManager
from client.messenger import Messenger
from client.commandListener import CommandListener
from client.clientGUI import ClientGUI

from client.inventory import Inventory
from client.behaviour import Behaviour

class Butler():
	"""
	Questo programma rappresenta un modello astratto di Butler (maggiordomo).
	È un agent che rimane in ascolto dei comandi da parte di un server (definito
	in un file di configurazione apposito().
	"""

	RETRY_TIMER = 4
	NOTIFICATION_MODULE = 'notification'
	INVENTORY_MODULE = 'inventory'
	BEHAVIOUR_MODULE = 'behaviour'

	def __init__(self):
		"""
		Istanzia un Butler senza accettare attributi.
		Inizializza l'utente, lo stato della connessione e i dati della notifica
		"""
		self.user = getpass.getuser()
		self.connected = False
		self.notifData = ''
		self.behaviour = Behaviour()
	
	def start(self):
		"""
		Punto d'entrata del programma.
		- Legge le configurazioni da un file JSON
		- Cerca di contattare il server
		- Avvia l'icona sulla taskbar
		- Mostra le notifiche quando necessario
		"""

		params = [
			{'short': 'c', 'full': 'config', 'args': True, 'default': '.',
				'help': 'Usa il file di configurazione dal percorso specificato.\nSe non è dato nessun percorso, viene preso quello di avvio del programma.'},
		]
		# gestione degli argomenti da linea di comando e lettura il file di configurazione
		argsParser = ArgsParser(params)
		args = argsParser.parse()
		try:
			self.configs = ConfigParser().load_configs(args['config'])
		except FileNotFoundError as e:
			log.critical('Impossibile leggere il file di configurazione:\n{}'.format(e.__str__()))
			return
		except JSONDecodeError as e:
			log.critical('Errore nella decodifica del file di configurazione:\n{}'.format(e.__str__()))
			return

		Logger().start(**self.configs['logging'])
		self.modules = self.configs['modules']

		ip = self.configs['client']['ip']
		if ip == '':
			try:
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				# trova l'IP "principale" (molti altri metodi ritornerebbero 127.0.0.1).
				# In realtà non serve che l'IP sia raggiungibile
				s.connect((self.configs['server']['ip'], 80))
				ip = s.getsockname()[0]
			except Exception as e:
				ip = socket.gethostbyname(socket.gethostname())
				log.warning('Errore di socket: {}'.format(e.__str__()))
			finally:
				s.close()
			log.info('È usato l\'ip {}'.format(ip))
		self.addr = '{}:{}'.format(ip, self.configs['client']['port'])

		self.inventory = Inventory(ip)
		self.mac = self.inventory.get_mac()

		log.info('Avvio del Butler {}'.format(self.addr))

		if self.configs['automaticSendInterval'] >= 1:
			threading.Thread(target=self.check_details, args=[self.configs['automaticSendInterval']], daemon=True).start()

		# avvio dell'ascoltatore di comandi
		listener = CommandListener(ip, self.configs['client']['port'], self.configs['expireTime'],
			self.configs['ssl'], {'show_notif': self.show_notif,
			'revoke': self.revoke_notif, 'disconnect': self.disconnect,
			'validate_credentials': self.validate_credentials,
			'get_details': self.get_details, 'toggle_module': self.toggle_module,
			'toggle_phase': self.toggle_phase, 'update_model': self.update_model})
		threading.Thread(target=listener.start_api, daemon=True).start()
		#sleep(0.1)

		# preparazione del generatore di notifiche
		self.notifBuilder = NotificationBuilder(
			scriptManager=ScriptManager(self.configs['tempPath']),
			logoPath=self.configs['logoPath'], callback=self.interacted)

		# avvio della GUI e ascolto degli eventi sulla tray icon
		self.tray = ClientGUI(self.configs['logoPath'], self.get_server_status, self.configs['website'])
		self.tray.start_tray()

		sleep(3)
		# impostazione dell'ip del server e tentativo di connessione
		self.serverAddr = '{}://{}:{}'.format(
			self.configs['protocol'], self.configs['server']['ip'], self.configs['server']['port'])
		threading.Thread(target=self.connect, daemon=True).start()

		for event in self.tray.listen_tray():
			if self.notifData != '' and self.modules[self.NOTIFICATION_MODULE]:
				log.warning('Nuova notifica: "{}"'.format(self.notifData['name']))
				self.notifBuilder.interrupt = False
				self.notifBuilder.show_window(self.notifData)
				self.notifData = ''
			if event == self.tray.QUIT:
				log.info('Tentativo di spegnimento manuale')
				if self.msg.can_disconnect(self.addr):
					log.warning('Richiesta accettata. Disconnessione di {}'.format(self.addr))
					self.shutdown()
					break
				log.warning('Richiesta rifiutata')
			elif event == self.tray.CONNECT:
				log.info('Tentativo di connessione manuale')
				self.disconnect()
				threading.Thread(target=self.connect, daemon=True).start()
				pass
			elif event == self.tray.DISCONNECT:
				log.info('Tentativo di disconnessione manuale')
				# la procedura di disconnessione è avviata se il server lo permette
				# o se il Butler dovrebbe già essere disconnesso
				if not self.connected or self.msg.can_disconnect(self.addr):
					log.warning('Richiesta accettata. Disconnessione di {}'.format(self.addr))
					self.disconnect()
				else:
					log.warning('Richiesta rifiutata')
		log.info('Spegnimento del Butler {}'.format(self.addr))
		self.tray.stop()
		sys.exit()
		
	def connect(self):
		"""
		Cerca di connettersi al server specificato nelle configurazioni.
		Ripete l'operazione ad intervalli definiti dalla costante RETRY_TIMER.
		"""
		log.info('Connessione al server {}'.format(self.serverAddr))
		self.msg = Messenger(baseUrl=self.serverAddr, authCallback=self.authenticate)
		while not self.connected:
			self.connected = self.authenticate()
			sleep(self.RETRY_TIMER)

	def authenticate(self):
		"""
		Permette l'autenticazione al server. Non richiedendo altri parametri,
		può essere richiamata da ovunque senza dipendenze. 
		
		:return: True se la connessione è stata stabilita, altrimenti False.
		"""
		self.msg.baseUrl = self.serverAddr
		return self.msg.authenticate(mac=self.mac, addr=self.addr, user=self.user)

	def show_notif(self, data):
		"""
		Imposta i dati della notifica da mostrare come flag.
		La notifica non può essere mostrata in questa funzione poichè generalmente
		richiamata da thread secondarie, ma la gui richiede di essere avviata
		dalla main thread. Sarà quindi il loop principale ad accorgersi dei dati
		in sospeso da mostrare.
		
		:param data (dict): i dati della notifica da mostrare.
		"""
		if self.modules[self.NOTIFICATION_MODULE]:
			self.notifData = data
		
	def revoke_notif(self, name=''):
		"""
		Richiede la chiusura di una notifica in base al suo nome.
		È solitamente richiesta da remoto.
		
		:param name (str): il nome della notifica da chiudere.
			Default: ''.
		"""
		self.notifBuilder.stop(name)
		pass

	def interacted(self, name):
		"""
		Richiamato all'interazione con il pulsante della notifica da parte dell'utente.
		
		:param name (str): il nome della notifica con la quale l'utente ha interagito.
		"""
		self.msg.interacted(name=name)

	def disconnect(self):
		"""
		Disconnette il Butler resettando il messenger e impostando un flag.
		"""
		self.msg.disconnect()
		self.connected = False

	def shutdown(self):
		"""
		Spegne il Butler completamente interrompendo il messenger e il menu.
		"""
		self.disconnect()
		self.tray.stop()

	def get_server_status(self):
		"""
		Richiede lo stato al server e in base alla risposta
		ritorna alcune variabili rappresentati lo stato del Butler.
		
		:return: il nome utente, l'indirizzo IPv4 e la porta del Butler, l'indirizzo del server se connesso.
		"""
		if not self.msg.server_online(self.addr):
			self.disconnect()
			self.authenticate()
		return self.user, self.addr, self.serverAddr if self.connected else None

	def validate_credentials(self, addr, id):
		"""
		Controlla che le informazioni passate dal server corrispondano
		ad quelle del file di configurazione.
		
		:param addr (str): l'indirizzo e la porta del server.
		:param id (str): un identificativo del server.
		
		:return: True se le credenziali corrispondono.
		"""
		valid = addr == self.serverAddr and id == self.configs['server']['id']
		if not valid:
			log.warning('Credenziali del server {} non valide'.format(addr))
			self.msg.disconnect()
		return valid


	"""
	#####################################
	Funzioni aggiuntive butler-extensions
	#####################################
	"""

	def get_details(self):
		"""
		Prende i dettagli del client in base ai moduli attivi.

		:return: i dettagli dei moduli.
		"""
		details = {'mac': self.mac, 'modules': self.modules}
		if self.modules[self.INVENTORY_MODULE]:
			details['inventory'] = self.inventory.get_inventory()
		if self.modules[self.BEHAVIOUR_MODULE]:
			details['model'] = self.behaviour.get_model()
			details['phase'] = self.behaviour.phase
		return details

	def toggle_module(self, module):
		"""
		Cambia lo stato di un modulo in base ai parametri.

		:param module (str): l'identificativo del modulo.
		"""
		self.modules.update(module)
		
	def toggle_phase(self, phase):
		"""
		Cambia la fase del comportamento e aggiorna le connessioni.

		:param phase (bool): lo stato da applicare.
		"""
		if self.modules[self.BEHAVIOUR_MODULE]:
			self.behaviour.phase = phase
			self.behaviour.check_connections()

	def update_model(self, model):
		"""
		Aggiorna il modello delle connessioni.

		:param model (list): la lista delle nuove connessioni.
		"""
		if self.modules[self.BEHAVIOUR_MODULE]:
			self.behaviour.update_model(model)

	def check_details(self, interval):
		"""
		Contolla periodicamente le informazioni dell'host e, se sono
		cambiate dalle precedenti, le invia al server.
		Ripete l'operazione ad intervalli definiti dal parametro.
		È necessario mandare solo l'inventario e il modello delle connessioni.

		:param interval (int): il tempo tra un controllo e l'altro.
		"""
		while True:
			if self.connected:
				oldDetails = {
					'inventory': self.inventory.data,
					'model': self.behaviour.model}
				currentDetails = self.get_details()
				newDetails = {}

				# inventario e model potrebbero essere disattivati
				# quindi verifica anche che la chiave esista
				if 'inventory' in currentDetails and oldDetails['inventory'] != currentDetails['inventory']:
					newDetails['inventory'] = currentDetails['inventory']
				if 'model' in currentDetails and oldDetails['model'] != currentDetails['model']:
					for currentConn in currentDetails['model']:
						found = False
						for oldConn in oldDetails['model']:
							if self.behaviour.conn_match(oldConn, currentConn):
								found = True
								break
						if not found:
							if 'model' not in newDetails:
								newDetails['model'] = []
							newDetails['model'].append(currentConn)

				# invia solo se sono state trovate differenze
				if newDetails != {}:
					newDetails['mac'] = self.mac
					successful = self.msg.send_details(newDetails)
					log.info('Invio di alcuni dettagli al server: {}'.format([key for key in newDetails]))
					if not successful and not self.msg.server_online(self.addr):
						log.warning('I dettagli inviati non hanno raggiunto il server')
						self.disconnect()
			sleep(interval)

	"""
	##########################################
	Fine funzioni aggiuntive butler-extensions
	##########################################
	"""

if __name__ == '__main__':
	Butler().start()
