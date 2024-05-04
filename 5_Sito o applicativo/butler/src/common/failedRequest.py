from common import log

class FailedRequest():
	"""
	Rappresenta una richiesta HTTP fallita.
	Contiene la logica di base per essere interpretata come il risultato
	della funzione "requests.get/.post /…", e traduce le risposte non positive
	in un formato unificato.
	"""

	def __init__(self, ok=False, message='', error='', *args, **kwargs):
		"""
		Istanzia un oggetto FailedRequest permettendo di definirne stato, messaggio,
		contenuto specifico dell'errore e altri eventuali argomenti.
		
		ok (bool, opzionale): lo stato della richiesta. Trattandosi di una
				richiesta fallita, dovrebbe sempre essere False.
			Default: False
		message (str, opzionale): una descrizione user-friendly dell'errore.
			Default: ''.
		error (str, opzionale): la rappresentazione dell'errore generato.
			Default: ''.
		"""

		self.ok = ok
		self.status_code = ok
		self.text = {'message': message, 'error': error}
		for key in kwargs:
			self.tex[key] = kwargs['key']
		
		if message != 'Errore di connessione':
			log.warning('{}: {}'.format(message, error))

	def json(self):
		"""
		Emula la funzione omonima dell'oggetto request.
		
		:return: il contenuto del messaggio.
		"""
		return self.text
