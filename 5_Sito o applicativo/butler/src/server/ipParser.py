import ipaddress
import re

from common import log

class IPParser():
	"""
	Questa classe analizza liste di indirizzi IPv4 ed esegue alcune operazioni
	di verifica della loro validità.
	"""
	
	def sanitize_ips(self, s):
		"""
		Trova gli indirizzi IPv4 e le subnet valide nella stringa passata come parametro.
		
		:param s (str): la stringa con gli IP.
		
		:return: una lista con gli IP validi trovati.
		"""
		cleaned = s
		if not isinstance(s, list):
			raw = s.replace('\n', ',').strip(' \n,').replace(' ', ',').replace('-', ',').replace(',,', ',').split(',')
			cleaned = [ip for ip in raw if ip != '']
		ips = []
		pattern = r"((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)((\.)(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}((\/)(([1-2][0-9])|([3][0-2])|([0-9])))?)"
		for addr in cleaned:
			ip = ''
			try:
				ip = (re.findall(pattern, addr))[0][0]
				ipaddress.IPv4Network(ip, strict=False)
			except IndexError:
				continue
			except ValueError:
				continue
			ips.append(str(ip))
		return ips

	def include(self, range, userIp):
		"""
		Controlla se un range di IP contiene un indirizzo.
		
		:param range (str, list): la lista o la stringa con gli IP nei quali cercare.
		:param userIp (str): l'indirizzo da verificare.
		
		:return: True se userIp fa parte del range, altrimenti False.
		"""
		userIp = self.sanitize_ips(userIp)[0]
		range = self.sanitize_ips(range)
		for r in range:
			if ipaddress.IPv4Address(userIp) in ipaddress.IPv4Network(r, strict=False):
				log.info('{} appartiene al range {}'.format(userIp, r))
				return True
		return False