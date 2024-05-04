from os.path import exists, isfile, join, abspath, isdir
from os import strerror
import errno
import json
import sys

from common import log

class ConfigParser():
	"""
	Questa classe permette di leggere i dati del file di configurazione.
	"""

	def load_configs(self, inputpath):
		"""
		Legge i dati in formato JSON dal percorso passato come parametro e
		ritorna un dizionario con tutti i valori.
		
		:param inputpath (str): il percorso del file di configurazione.
		
		:return: il dizionario con i valori interpretati.
		"""
		filePath = self.get_valid_path(inputpath, 'config.json')

		with open(filePath) as json_file:
			self.configs = json.load(json_file)

		log.info('Il file di configurazione è nella cartella "{}"'.format(filePath))
		return self.configs

	def get_valid_path(self, inputpath, defaultFileName, force=False):
		"""
		Controlla che percorso sia o contenga il file dal nome passato come parametro.
		
		:param inputpath (str): il percorso (assoluto o relativo)
			nel quale esesrguire la ricerca.
		:param defaultFileName (str): il nome del file da cercare.
		:force (bool, opzionale): crea il file se non esiste.
			Default: False
		
		:return: ritorna il percorso assoluto valido interpretato.
		"""
		inputPath = abspath(join(sys.path[0],inputpath))
		fullPath = abspath(join(sys.path[0], inputpath, defaultFileName))

		if force and not isfile(fullPath):
			with open(fullPath, 'w') as f:
				pass
		if exists(fullPath):
			# aggiunge il nome del file di configurazione di default al percorso
			# solo se l'input è una directory valida,
			# altrimenti considera l'ultimo elemento del percorso come nome del file di configurazione
			return join(
				inputPath, defaultFileName) if isdir(inputPath) else inputPath
		else:
			raise FileNotFoundError(
				errno.ENOENT, strerror(errno.ENOENT), inputPath)