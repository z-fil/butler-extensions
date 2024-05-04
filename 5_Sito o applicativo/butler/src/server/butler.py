from common import log
from server.butlerController import ButlerController

class Butler():
	"""
	Questa classe rappresenta un client Butler, salvando diversi attributi
	utili alla gestione e alla comunicazione.
	Il server può comunicare con questa classe come se si trattasse di un client
	reale, con la comunicazione gestita automaticamete.
	"""

	def __init__(self, protocol, mac, addr, user, serverAddr, serverId, canDisconnect=False):
		"""
		Istanzia un oggetto Butler definendone il protocollo da usare, l'indirizzo,
		il nome utente, l'indirizzo del server, l'id del server e il permesso di disconnessione.
		
		:param protocol (str): il protocollo (http o https) da usare nella comunicazione.
		:param mac (str): l'indirizzo MAC del Butler.
		:param addr (str): l'indirizzo IPV4 e la porta del Butler.
		:param user (str): il nome dell'utente.
		:param serverAddr (str): l'indirizzo e la porta del server. Specificandolo come attributo,
				è possibile ritentare l'autenticazione automaticamente.
		:param serverId (str): una stringa identificativa del server.
		:param canDisconnect (bool, opzionale): il permesso di disconnettersi manualmente.
			Default: False
		"""
		self.addr = addr
		self.ip, self.port = [val for val in addr.split(':')]
		self.mac = mac
		self.user = user
		self.serverAddr = serverAddr
		self.serverId = serverId
		self.canDisconnect = canDisconnect
		self.butlerController = ButlerController(protocol+'://'+addr, self.authenticate)
		log.info('Nuovo Butler su {}'.format(addr))

	def authenticate(self):
		"""
		Si autentica al Butler.
		Non necessita di altri parametri, quindi questa funzione è
		usata in modo automatico anche in caso di scadenza di un token.
		
		:return: True se l'autenticazione è avvenuta, altirmenti False.
		"""
		return self.butlerController.authenticate(self.serverAddr, self.serverId)

	def get_status(self):
		"""
		Controlla lo stato del Butler.
		
		:return: True se il Butler è attivo, altrimenti False.
		"""
		return self.butlerController.status()

	def send(self, data):
		"""
		Invia una notifica al Butler.
		
		:param data (dict): i dati della notifica.
		
		:return: True se il Butler ha ricevuto la notifica, altrimenti False.
		"""
		return self.butlerController.notify(data)

	def revoke(self, name):
		"""
		Richiede la chiusura della notifica.
		
		:param name (str): il nome della notifica da revocare.
		
		:return: True se il Butler ha ricevuto il comando, altrimenti False.
		"""
		return self.butlerController.revoke(name)

	def disconnect(self):
		"""
		Richiede la disconnessione.
		
		:return: True se il Butler ha ricevuto il comando, altrimenti False.
		"""
		return self.butlerController.disconnect()


	"""
	#####################################
	Funzioni aggiuntive butler-extensions
	#####################################
	"""

	def get_details(self):
		"""
		Richiede i dettagli al Butler.

		:return: i dati ricevuti.
		"""
		return self.butlerController.get_details()

	def edit(self, data, endpoint):
		"""
		Permette di modificare un parametro di un Butler.

		:param data (str): i dati modificati.
		:param endpoint (str, opzionale): l'endpoint del Butler.
		"""
		self.butlerController.edit(data, endpoint)
		
	def update_model(self, model):
		"""
		Permette di aggiornare il modello delle connessioni di un Butler.

		:param model (dict): il dizionario con i valori delle connessioni.
		"""
		self.butlerController.update_model(model)

	"""
	##########################################
	Fine funzioni aggiuntive butler-extensions
	##########################################
	"""
