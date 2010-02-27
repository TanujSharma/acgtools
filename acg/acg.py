from errors import *
from eeprom import *
from serio import serio
from tag import tag
import time

class acg:
	def __read_eeprom(self):
		eeprom = ''
		for i in range(0, EEPROM_BYTES):
			cmd = "rp%.2X"%i
			resp = self.__trancieve(cmd)
			if len(resp) != 2:
				raise ACG_BadResponse(cmd, resp)
			try:
				byte = int(resp, 16)
			except ValueError:
				raise ACG_BadResponse(cmd, resp)
			eeprom += chr(byte)
		return eeprom
	
	def __flash_eeprom(self, bin):
		assert(len(bin) == EEPROM_BYTES)
		bin = bin[EEPROM_READONLY:]
		for i in range(0, EEPROM_BYTES - EEPROM_READONLY):
			cmd = "wp%.2X%.2X"%(i + EEPROM_READONLY, ord(bin[i]))
			resp = self.__trancieve(cmd)

	def __hard_reset(self):
		# Startup message may be disabled in EEPROM
		self.__serio.tx("x")
		self.__banner = self.__serio.peekbuffer(0.25)

		# If device starts in continuous read mode then send a
		# command to abort that and retrieve the tag list
		self.__serio.tx(".")
		ret = self.__serio.rx()
		while len(ret) and ret != 'S' and ret != '?':
			ret = self.__serio.peekbuffer(0.15)
		self.__cont_read = False

		# Finally the device ought to be in a predictable state
		# phew

	def __init__(self, line="/dev/ttyUSB0", baud=460800, tracefile=None):
		self.__serio = serio(line, baud, tracefile)
		self.__cont_read = True
		self.__hard_reset()
		self.__eeprom = None

	def __trancieve(self, cmd):
		self.__serio.tx(cmd)
		ret = self.__serio.rx()
		if len(ret) == 0:
			raise ACG_IOError("Reader returned nothing")
		if len(ret) == 1:
			if ret[0] == '?':
				raise ACG_UnknownCommand(cmd[0])
			if ret[0] == 'C':
				raise ACG_Collision
			if ret[0] == 'F':
				raise ACG_CommandFail(cmd)
			if ret[0] == 'I':
				raise ACG_InvalidValue(cmd)
			if ret[0] == 'N':
				raise ACG_NoTagInField
			if ret[0] == 'O':
				raise ACG_OperationMode(cmd)
			if ret[0] == 'R':
				raise ACG_RangeError(cmd)
			if ret[0] == 'X':
				raise ACG_AuthFailure(cmd)
			if ret[0] == 'S':
				print "warn: interleaving commands with" + \
					"cont. read is dangerous"
				self.__cont_read = False
		return ret

	def dump_eeprom(self, filename):
		if not self.__eeprom:
			self.__eeprom = eeprom(self.__read_eeprom())
		f = open(filename, 'w')
		f.write(self.__eeprom.binary())
		f.close()

	def flash_eeprom(self, filename):
		f = open(filename, 'r')
		img = eeprom(f.read())
		f.close()
		self.__flash_eeprom(img.binary())
		self.__hard_reset()

	def get_eeprom(self):
		self.__eeprom = eeprom(self.__read_eeprom())
		return self.__eeprom

	def __to_bin(self, ascii):
		arr = []
		while len(ascii) >= 2:
			arr.append(chr(int(ascii[:2], 16)))
			ascii = ascii[2:]
		return bytearray(arr)

	def select(self):
		uid = self.__trancieve("s")
		bin = self.__to_bin(uid)
		return tag(bin)

	def continuous_read(self):
		if not self.__cont_read:
			self.__serio.tx("c")
			self.__cont_read = True

		uid = self.__serio.rx()
		if uid == 'S':
			self.__cont_read = False
			return None
		bin = self.__to_bin(uid)
		return tag(bin)
	
	def abort_continuous_read(self):
		if not self.__cont_read:
			return
		ret = self.__trancieve(".")
		while ret != 'S':
			print "additional tags after abort"
			ret = self.__serio.rx()
		self.__cont_read = False

	def mifare_readblock(self, rec):
		return self.__trancieve("r%.2x"%rec)

	def mifare_login(self, rec, k, keydata = None):
		cmd = 'l%.2x%.2x\r'%(rec, k)
		#print cmd
		try:
			ret = self.__trancieve(cmd)
		except ACG_NoTagInField:
			self.select()
			ret = self.__trancieve(cmd)
		if ret == 'L':
			return True
		else:
			return False
