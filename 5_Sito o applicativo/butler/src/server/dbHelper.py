from pymongo import MongoClient
from datetime import datetime

from common import log

class DbHelper():
	"""
	Questa classe permette di stabilire una connessione al database MongoDB
	e di eseguire varie operazioni di base sui documenti delle notifiche,
	dei buffer e delle informazioni dei computers.
	Si occupa anche di mantenere l’integrità dei dati:
	in particolare dei riferimenti dal buffer alle notifiche e la coerenza
	tra le connessioni del modello.
	"""

	IP = 0
	PORT = 1
	
	def login(self, ip, port, serverTimeout=500, queryTimeout=1500):
		"""
		Stabilisce una connessione al database in base ai parametri
		salvando i riferimenti alle tabelle notification e buffer.
		
		:param ip (str): l'ip del server MongoDB.
		:param port (int): la porta del server.
		"""
		connStr = 'mongodb://{}:{}'.format(ip, port)
		client = MongoClient(
			connStr, serverSelectionTimeoutMS=serverTimeout, connectTimeoutMS=queryTimeout)
		log.info('Connessione al database {}'.format(connStr))
		db = client["butler"]
		self.bufferColl = db['buffer']
		self.notifColl = db['notification']
		self.computerColl = db['computer']


	def get_notif(self, query={}, filter={}):
		"""
		Permette di ricavare una notifica in base ad una query.
		
		:param query (dict): la query in formato di dizionario.
		:return: il cursore per iterare i dati trovati.
		"""
		try:
			return [notif for notif in self.notifColl.find(query, filter) if 'name' not in notif or notif['name'] != '']
		except Exception as e:
			self.log_db_error(e)
		return []


	def get_notif_id(self, name):
		"""
		Permette di ricavare l’id di una notifica in base al nome.
		
		:param name (str): il nome della notifica.
		:return: None se il nome non ha una corrispondenza, altrimenti l'id trovato.
		"""
		try:
			result = self.notifColl.find_one({'name': name}, {'_id': 1})
		except Exception as e:
			self.log_db_error(e)
			return None
		return None if result is None else result['_id']

	def get_notif_data(self, name):
		"""
		Permette di ricavare i dati di una notifica in base al nome
		
		:param name (str): il nome ricercato.
		
		:return: i dati della notifica, senza ID.
		"""
		result = []
		try:
			result = self.notifColl.find_one({'name': name}, {'_id': 0})
		except Exception as e:
			self.log_db_error(e)
			return []
		return [] if result is None else result


	def upsert_notif(self, data):
		"""
		Aggiorna o crea la notifica in base al parametro data.
		
		:param data (dict): i nuovi dati nella notifica 
		:return: il documento della notifica modificata.
		"""
		try:
			return self.notifColl.find_one_and_update(
				{'name': data['name']},
				{'$set': data}, upsert=True
			) if 'name' in data else None
		except Exception as e:
			self.log_db_error(e)
		return []

	def delete_notif(self, notifName):
		"""
		Cancella la notifica e tutti i buffer che ne fanno riferimento in base al nome.
		
		:param notifName (str): il nome della notifica da cancellare.
		:return: True se è stata eliminata una notifica, altrimenti False.
		"""
		try:
			doc = self.notifColl.find_one_and_delete({'name': notifName})
			if doc is None:
				log.warning('Eliminazione di "{}" fallita: il nome non è stato trovato nel database)'.format(notifName))
				return False
			id = doc['_id']
			self.delete_buffer({'notification': id})
			return True
		except Exception as e:
			self.log_db_error(e)
		return False

	def get_buffer(self):
		"""
		Legge i buffer e unisce i dati in un array senza riferimenti ad ID.

		:return: i buffer con notifiche che vanno già consegnate.
		"""
		buffers = []
		try:
			self.clean_buffer()
			for b in self.bufferColl.find():
				if str(b['deliveryStart']) < (str(datetime.today())):
					buffers.append({
						'_id': b['_id'],
						'notification': self.get_notif(
							{'_id': b['notification']},
							{'_id': 0, 'name': 1})[0]['name'],
						'recipients': [r for r in b['recipients']],
						'excluded': [e for e in b['excluded']]
					})
		except Exception as e:
			self.log_db_error(e)
		return buffers

	def add_buffered_notif(self, notifName, recipients, deliveryStart=datetime.today()):
		"""
		Aggiunge un nuovo buffer per la notifica passata come parametro.

		:param notif_name (str): il nome della notifica per la quale creare il buffer.
		:param recipients (list): i destinatari ai quali andrà inviata la notifica
		:param deliveryStart (date, optional): . Defaults to datetime.today().

		:return: il risultato dell'operazione di inserimento se valido, altrimenti False.
		"""
		try:
			notifId = self.get_notif_id(notifName)
			if notifId is None or len(recipients) == 0:
				log.error('Aggiunta della notifica "{}" in un buffer fallita: il nome non è stato trovato nel database'.format(notifName))
				return False
			# è sempre inserito un nuovo buffer, mai sovrascritto uno vecchio
			return self.bufferColl.insert_one({
				'notification': notifId,
				'recipients': recipients,
				'excluded': [],
				'deliveryStart': deliveryStart
			})
		except Exception as e:
			self.log_db_error(e)
		return False

	def update_buffer(self, buffer):
		"""
		Aggiorna i destinatari di un buffer passato come parametro,
		o lo elimina se non ci sono più destinatari in sospeso da raggiungere.
		
		:param buffer (dict): il buffer dal quale sarà ricavato l'id.
		:return: il risultato dell'operazione.
		"""
		for addr in buffer['excluded']:
			# rimouve dalla lista i destinatari raggiunti
			if addr in buffer['recipients']:
				buffer['recipients'].remove(addr)
		try:
			if len(buffer['recipients']) > 0:
				return self.bufferColl.find_one_and_update(
					{'_id': buffer['_id']},
					{'$set': {'excluded': buffer['excluded'],
							'recipients': buffer['recipients']}}
				)
			else:
				return self.bufferColl.find_one_and_delete({'_id': buffer['_id']})
		except Exception as e:
			self.log_db_error(e)
		return None
	
	def delete_buffer(self, query):
		"""
		Cancella il buffer in base alla query.
		
		:param query (dict): la query sotto forma di dizionario.
		:return: il risultato dell'operazione di eliminazione.
		"""
		try:
			return self.bufferColl.delete_many(query).deleted_count
		except Exception as e:
			self.log_db_error(e)
		return None

	def clean_buffer(self):
		"""
		Cerca i buffer con notifiche che non esistono più e li elimina.
		"""
		try:
			for buffer in self.bufferColl.find({}, {'notification': 1}):
				if len(self.get_notif({'_id': buffer['notification']})) == 0:
					self.delete_buffer({'notification': buffer['notification']})
		except Exception as e:
			self.log_db_error(e)

	def log_db_error(self, e):
		"""
		Aggiunge ai log il messaggio dell'eccezione sollevata.
		
		:param e (obj): un oggetto con le informazioni sull'errore.
		"""
		log.error('Timeout nella richiesta al database: {}'.format(e))


	"""
	#####################################
	Funzioni aggiuntive butler-extensions
	#####################################
	"""
	
	def get_computer_data(self, mac):
		"""
		Legge dal database i dati di un computer.

		:param mac (str): l'indirizzo MAC del computer.

		:return: i dati del computer.
		"""
		result = {}
		try:
			result = self.computerColl.find_one({'mac': mac}, {'_id': 0, 'modules': 1, 'model': 1, 'phase': 1, 'inventory': 1})
		except Exception as e:
			self.log_db_error(e)
		return {} if result is None else result

	def upsert_details(self, data):
		"""
		Analizza i dati passati e li inserisce o li aggiorna nel database.

		:param data (dict): il dizionario con i vari elementi da inserire.
		"""
		try:
			if data is None or 'mac' not in data:
				return
			# verifica i dati per ogni attributo, dato che
			# necessitano di essere trattati in modo differente tra loro
			for attr in data:
				# il mac è sempre uguale; non va modificato
				if attr == 'mac':
					continue
				elif attr == 'model':
					# se è una lista, va verificato singolarmente ogni elemento
					if type(data[attr]) == list:
						for e in data[attr]:
							self.update_conn(data['mac'], e)
					else:
						self.update_conn(data['mac'], data[attr])
				else:
					# i dizionari necessitano di una chiave ulteriore
					if type(data[attr]) == dict and data[attr] != {}:
						for key in list(data[attr].keys()):
							self.update_value(data['mac'], data[attr][key], attr+'.'+key)
					else:
						self.update_value(data['mac'], data[attr], attr)
		except Exception as e:
			self.log_db_error(e)
		
	def update_conn(self, mac, conn):
		"""
		Inserisce o aggiorna una connessione del modello.

		:param mac (str): l'indirizzo MAC del computer.
		:param conn (dict): i dati da inserire.
		"""
		# "$elemMatch" trova l'elemento al quale "model.$" farà riferimento 
		result = self.computerColl.find_one_and_update(
			{'mac': mac, 'model': {'$elemMatch': {
				'proc': conn['proc'],
				'$or': [ 
					{'$and': [
						{'dest.{}'.format(self.IP): ''},
						{'dest.{}'.format(self.PORT): ''},
						{'dest.{}'.format(self.IP): conn['dest'][self.IP]},
						{'dest.{}'.format(self.PORT): conn['dest'][self.PORT]},
						{'source.{}'.format(self.IP): conn['source'][self.IP]},
						{'source.{}'.format(self.PORT): conn['source'][self.PORT]},
					]},
					{'$and': [
						{'dest.{}'.format(self.IP): {'$ne': ''}},
						{'dest.{}'.format(self.PORT): {'$ne': ''}},
						{'dest.{}'.format(self.IP): conn['dest'][self.IP]},
						{'dest.{}'.format(self.PORT): conn['dest'][self.PORT]},
						{'source.{}'.format(self.IP): conn['source'][self.IP]}
					]}
				]
			}}},
			{'$set': {'model.$': conn} }
		)

		# se la connessione non è presente, la aggiunge:
		# "upsert" non funziona con la condizione di $elemMatch
		if result is None:
			self.computerColl.find_one_and_update(
				{'mac': mac}, {'$addToSet': {'model': conn}})

	def update_value(self, mac, value, selector):
		"""
		Inserisce o aggiorna un dato generico nel database.

		:param mac (str): l'indirizzo MAC del computer.
		:param value (obj): il dato da inserire.
		:param selector (str): la chiave del dato da aggiornare.
		"""
		self.computerColl.find_one_and_update({'mac': mac},
			{'$set': {selector: value}}, upsert=True)

	"""
	##########################################
	Fine funzioni aggiuntive butler-extensions
	##########################################
	"""