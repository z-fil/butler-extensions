import argparse

from common import log

class ArgsParser():
	"""
	Questa classe analizza i parametri forniti da linea di comando,
	mostra un breve testo guida all’uso dei parametri ("-h" o "--help")
	e ritorna un dizionario con tutti gli altri.
	"""

	def __init__(self, params=[], description=''):
		"""
		Istanzia un oggetto ArgsParser definendone i parametri accettati
		e il testo "help".
		
		params (list, opzionale): la lista di parametri specifici da ricercare.
				Il formato è:
				[{'short': '...',   # il parametro abbreviato
				'full': '...',      # il nome esteso
				'args': True/False, # indica se il programma deve aspettarsi ulteriori
									argomenti dopo quel parametro
				'default':'...',    # il valore di default
				'help':'...'},      # il testo da mostrare nella guida
				{...}]
				I nomi dei parametri sono da definire senza '-' iniziali.
			Default: [].
		description (str, opzionale): la descrizione del programma.
			Default: ''.
		"""
		self.params = params
		self.description = description

	def parse(self):
		"""
		Analizza i parametri e gli argomenti in base all'attributo params,
		e ritorna un dizionario con i valori trovati tra quelli richiesti.

		:return: il dizionario con i parametri e gli eventuali valori associati
			validi trovati.
		"""

		parser = argparse.ArgumentParser(
			description=self.description, formatter_class=argparse.RawTextHelpFormatter)
		for p in self.params:
			parser.add_argument('-'+p['short'], '--'+p['full'],
								action="store_true" if not p['args'] else None, default=p['default'], help=p['help'])
		args = parser.parse_known_args()
		log.info('Argomenti:',args)
		return args[0].__dict__
