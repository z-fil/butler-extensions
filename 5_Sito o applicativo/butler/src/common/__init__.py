import sys
from os.path import abspath, join
sys.path.append(abspath(join(sys.path[0],'..')))

import logging

log = logging.getLogger('butler')
log.setLevel(logging.INFO)
