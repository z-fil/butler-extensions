import logging

from common.configParser import ConfigParser

class Logger():
	"""
	Questa classe definisce lo stile dei log, sia a console che su file.
	"""

	def start(self, level='INFO', path='.'):
		"""
		Inizializza diversi attributi per il logging.
		
		level (str, opzionale): il livello minimo di gravità da loggare.
			Default: 'INFO'
		path (str, opzionale): il percorso del file di log.
			Default: '.'
		
		:return: un oggetto logger che permette il logging con lo stile personalizzato.
		"""
		# il logger è associato alla stringa identificativa 'butler',
		# riconosciuta da tutto il programma
		log = logging.getLogger('butler')
		logLevel = getattr(logging, level)
		log.setLevel(logLevel)

		# il formatter non è un parametro personalizzabile visto il complesso formato;
		# non è possibile far passare come variabile i valori %(...)s
		formatter = logging.Formatter(
			'%(asctime)s - %(levelname)s from %(filename)s (%(funcName)s): %(message)s')
		
		# definizione del formato per i log a terminale
		consoleHandler = logging.StreamHandler()
		consoleHandler.setLevel(logLevel)
		consoleHandler.setFormatter(formatter)
		log.addHandler(consoleHandler)

		# definizione dell formato per i log nei file
		fileHandler = logging.FileHandler(
			ConfigParser().get_valid_path(path, 'butler.log', force=True), encoding='UTF-8')
		fileHandler.setLevel(logLevel)
		fileHandler.setFormatter(formatter)
		log.addHandler(fileHandler)

		return log
