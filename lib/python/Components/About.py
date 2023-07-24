# -*- coding: utf-8 -*-
from os import stat
from os.path import isfile
from time import localtime, strftime
import re
from glob import glob
from sys import maxsize, modules, version_info
import socket, fcntl, struct
from subprocess import PIPE, Popen
from Components.SystemInfo import SystemInfo, ARCHITECTURE, MODEL
from Tools.HardwareInfo import HardwareInfo
from Tools.Directories import fileExists, fileReadLine, fileReadLines

MODULE_NAME = __name__.split(".")[-1]


def _ifinfo(sock, addr, ifname):
	iface = struct.pack('256s', bytes(ifname[:15], encoding="UTF-8"))
	info  = fcntl.ioctl(sock.fileno(), addr, iface)
	if addr == 0x8927:
		return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1].upper()
	else:
		return socket.inet_ntoa(info[20:24])


def getIfConfig(ifname):
	ifreq = {'ifname': ifname}
	infos = {}
	sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	# offsets defined in /usr/include/linux/sockios.h on linux 2.6
	infos['addr']    = 0x8915 # SIOCGIFADDR
	infos['brdaddr'] = 0x8919 # SIOCGIFBRDADDR
	infos['hwaddr']  = 0x8927 # SIOCSIFHWADDR
	infos['netmask'] = 0x891b # SIOCGIFNETMASK
	try:
		for k,v in infos.items():
			ifreq[k] = _ifinfo(sock, v, ifname)
	except:
		pass
	sock.close()
	return ifreq


def getIfTransferredData(ifname):
	lines = fileReadLines("/proc/net/dev", source=MODULE_NAME)
	if lines:
		for line in lines:
			if ifname in line:
				data = line.split("%s:" % ifname)[1].split()
				rx_bytes, tx_bytes = (data[0], data[8])
				return rx_bytes, tx_bytes


def getVersionString():
	return getImageVersionString()


def getImageVersionString():
	if isfile("/var/lib/opkg/status"):
		status = stat("/var/lib/opkg/status")
		tm = localtime(status.st_mtime)
		if tm.tm_year >= 2018:
			return strftime("%Y-%m-%d %H:%M:%S", tm)
	return _("Unavailable")


def getFlashDateString():
	return _("Unknown")


def getBuildDateString():
	version = fileReadLine("/etc/version", source=MODULE_NAME)
	if version is None:
		return _("Unknown")
	return "%s-%s-%s" % (version[:4], version[4:6], version[6:8])


def getUpdateDateString():
	if isfile("/proc/enigma/compiledate"):
		build = fileReadLine("/proc/enigma/compiledate", source=MODULE_NAME)
	elif isfile("/proc/enigma/compiledate"):
		build = fileReadLine("/proc/enigma/compiledate", source=MODULE_NAME)
	else:
		build = None
	if build is not None:
		build = build.strip()
		if build.isdigit():
			return "%s-%s-%s" % (build[:4], build[4:6], build[6:])
	return _("Unknown")


def getEnigmaVersionString():
	import enigma
	enigma_version = enigma.getEnigmaVersionString()
	if '-(no branch)' in enigma_version:
		enigma_version = enigma_version[:-12]
	return enigma_version


def getGStreamerVersionString():
	from glob import glob
	try:
		gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer[0-9].[0-9].control")[0], "r") if x.startswith("Version:")][0]
		return "%s" % gst[1].split("+")[0].split("-")[0].replace("\n", "")
	except:
		try:
			from glob import glob
			print("[About] Read /var/lib/opkg/info/gstreamer.control")
			gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer?.[0-9].control")[0], "r") if x.startswith("Version:")][0]
			return "%s" % gst[1].split("+")[0].replace("\n", "")
		except:
			return _("Not installed")


def getFFmpegVersionString():
	try:
		from glob import glob
		ffmpeg = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/ffmpeg.control")[0], "r") if x.startswith("Version:")][0]
		return "%s" % ffmpeg[1].split("-")[0].replace("\n", "")
	except:
		return _("Not Installed")


def getKernelVersionString():
	version = fileReadLine("/proc/version", source=MODULE_NAME)
	if version is None:
		return _("Unknown")
	return version.split(" ", 4)[2].split("-", 2)[0]

def getHardwareTypeString():
	return HardwareInfo().get_device_string()


def getImageTypeString():
	try:
		image_type = open("/etc/issue").readlines()[-2].strip()[:-6]
		return image_type.capitalize()
	except:
		return _("undefined")


def getCPUSerial():
	lines = fileReadLines("/proc/cpuinfo", source=MODULE_NAME)
	if lines:
		for line in lines:
			if line[0:6] == "Serial":
				return line[10:26]
	return _("Undefined")


def getCPUInfoString():
	try:
		cpu_count = 0
		cpu_speed = 0
		processor = ""
		for line in open("/proc/cpuinfo").readlines():
			line = [x.strip() for x in line.strip().split(":")]
			if not processor and line[0] in ("system type", "model name", "Processor"):
				processor = line[1].split()[0]
			elif not cpu_speed and line[0] == "cpu MHz":
				cpu_speed = "%1.0f" % float(line[1])
			elif line[0] == "processor":
				cpu_count += 1
		if processor.startswith("ARM") and isfile("/proc/stb/info/chipset"):
			processor = "%s (%s)" % (open("/proc/stb/info/chipset").readline().strip().upper(), processor)
		if not cpu_speed:
			try:
				cpu_speed = int(open("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq").read()) // 1000
			except:
				try:
					import binascii
					cpu_speed = int(int(binascii.hexlify(open('/sys/firmware/devicetree/base/cpus/cpu@0/clock-frequency', 'rb').read()), 16) // 100000000) * 100
				except:
					cpu_speed = "-"

		temperature = None
		freq = _("MHz")
		if isfile('/proc/stb/fp/temp_sensor_avs'):
			temperature = open("/proc/stb/fp/temp_sensor_avs").readline().replace('\n', '')
		elif isfile('/proc/stb/power/avs'):
			temperature = open("/proc/stb/power/avs").readline().replace('\n', '')
		elif isfile('/proc/stb/fp/temp_sensor'):
			temperature = open("/proc/stb/fp/temp_sensor").readline().replace('\n', '')
		elif isfile("/sys/devices/virtual/thermal/thermal_zone0/temp"):
			try:
				temperature = int(open("/sys/devices/virtual/thermal/thermal_zone0/temp").read().strip()) // 1000
			except:
				pass
		elif isfile("/proc/hisi/msp/pm_cpu"):
			try:
				temperature = re.search('temperature = (\d+) degree', open("/proc/hisi/msp/pm_cpu").read()).group(1)
			except:
				pass
		if temperature:
			return "%s %s %s (%s) %s\xb0C" % (processor, cpu_speed, freq, ngettext("%d core", "%d cores", cpu_count) % cpu_count, temperature)
		return "%s %s %s (%s)" % (processor, cpu_speed, freq, ngettext("%d core", "%d cores", cpu_count) % cpu_count)
	except:
		return _("undefined")


def getChipSetString():
	try:
		chipset = open("/proc/stb/info/chipset", "r").read()
		return str(chipset.lower().replace('\n', ''))
	except IOError:
		return _("undefined")


def getChipSetNumber():
	try:
		f = open('/proc/stb/info/chipset', 'r')
		chipset = f.read()
		f.close()
		return str(chipset.lower().replace('\n', '').replace('brcm', '').replace('bcm', ''))
	except IOError:
		return _("unavailable")


def getCPUBrand():
	if SystemInfo["HiSilicon"]:
		return _("HiSilicon")
	else:
		return _("Broadcom")


def getCPUArch():
	if SystemInfo["ArchIsARM64"]:
		return _("ARM64")
	elif SystemInfo["ArchIsARM"]:
		return _("ARM")
	else:
		return _("Mipsel")


def getDriverInstalledDate():
	filenames = glob("/var/lib/opkg/info/*dvb-modules*.control")
	if filenames:
		lines = fileReadLines(filenames[0], source=MODULE_NAME)
		if lines:
			for line in lines:
				if line[0:8] == "Version:":
					driver = line.split("-")[-2:11][0][-8:]
					return "%s-%s-%s" % (driver[:4], driver[4:6], driver[6:])
	filenames = glob("/var/lib/opkg/info/*dvb-proxy*.control")
	if filenames:
		lines = fileReadLines(filenames[0], source=MODULE_NAME)
		if lines:
			for line in lines:
				if line[0:8] == "Version:":
					return line.split("-")[-2:-1][0][-8:]
	filenames = glob("/var/lib/opkg/info/*platform-util*.control")
	if filenames:
		lines = fileReadLines(filenames[0], source=MODULE_NAME)
		if lines:
			for line in lines:
				if line[0:8] == "Version:":
					return line.split("-")[-2:-1][0][-8:]
	return _("Unknown")


def getPythonVersionString():
	return "%s.%s.%s" % (version_info.major, version_info.minor, version_info.micro)


def GetIPsFromNetworkInterfaces():
	import socket
	import fcntl
	import struct
	import array
	is_64bits = maxsize > 2**32
	struct_size = 40 if is_64bits else 32
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	max_possible = 8 # initial value
	while True:
		_bytes = max_possible * struct_size
		names = array.array('B')
		for i in range(0, _bytes):
			names.append(0)
		outbytes = struct.unpack('iL', fcntl.ioctl(
			s.fileno(),
			0x8912,  # SIOCGIFCONF
			struct.pack('iL', _bytes, names.buffer_info()[0])
		))[0]
		if outbytes == _bytes:
			max_possible *= 2
		else:
			break
	namestr = names.tobytes()
	ifaces = []
	for i in range(0, outbytes, struct_size):
		iface_name = bytes.decode(namestr[i:i + 16]).split('\0', 1)[0]
		if iface_name != 'lo':
			iface_addr = socket.inet_ntoa(namestr[i + 20:i + 24])
			ifaces.append((iface_name, iface_addr))
	return ifaces


def getBoxUptime():
	upTime = fileReadLine("/proc/uptime", source=MODULE_NAME)
	if upTime is None:
		return "-"
	secs = int(upTime.split(".")[0])
	times = []
	if secs > 86400:
		days = secs / 86400
		secs = secs % 86400
		times.append(ngettext("%d day", "%d days", days) % days)
	h = secs / 3600
	m = (secs % 3600) / 60
	times.append(ngettext("%d hour", "%d hours", h) % h)
	times.append(ngettext("%d minute", "%d minutes", m) % m)
	return " ".join(times)


def getGlibcVersion():
	process = Popen(("/lib/libc.so.6"), stdout=PIPE, stderr=PIPE, universal_newlines=True)
	stdout, stderr = process.communicate()
	if process.returncode == 0:
		for line in stdout.split("\n"):
			if line.startswith("GNU C Library"):
				data = line.split()[-1]
				if data.endswith("."):
					data = data[0:-1]
				return data
	print("[About] Get glibc version failed.")
	return _("Unknown")


def getGccVersion():
	process = Popen(("/lib/libc.so.6"), stdout=PIPE, stderr=PIPE, universal_newlines=True)
	stdout, stderr = process.communicate()
	if process.returncode == 0:
		for line in stdout.split("\n"):
			if line.startswith("Compiled by GNU CC version"):
				data = line.split()[-1]
				if data.endswith("."):
					data = data[0:-1]
				return data
	print("[About] Get gcc version failed.")
	return _("Unknown")


def getOpenSSLVersion():
	process = Popen(("/usr/bin/openssl", "version"), stdout=PIPE, stderr=PIPE, universal_newlines=True)
	stdout, stderr = process.communicate()
	if process.returncode == 0:
		data = stdout.strip().split()
		if len(data) > 1 and data[0] == "OpenSSL":
			return data[1]
	print("[About] Get OpenSSL version failed.")
	return _("Unknown")

# For modules that do "from About import about"
about = modules[__name__]
