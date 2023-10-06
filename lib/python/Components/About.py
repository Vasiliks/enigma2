# -*- coding: utf-8 -*-
from os import stat
from binascii import hexlify
from locale import format_string
from os.path import isfile
from time import localtime, strftime
import re
from glob import glob
from sys import maxsize, modules, version_info
import socket, fcntl, struct
from subprocess import PIPE, Popen
from Components.SystemInfo import BoxInfo, SystemInfo
from Tools.Directories import fileExists, fileReadLine, fileReadLines

MODULE_NAME = __name__.split(".")[-1]

socfamily = BoxInfo.getItem("socfamily")
MODEL = BoxInfo.getItem("model")


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
		for k, v in infos.items():
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
	try:
		tm = localtime(stat("/boot").st_ctime)
		if tm.tm_year >= 2011:
			return strftime(_("%Y-%m-%d"), tm)
		else:
			return _("Unknown")
	except:
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
		gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer[0-9].[0-9].control")[0]) if x.startswith("Version:")][0]
		return "%s" % gst[1].split("+")[0].split("-")[0].replace("\n", "")
	except:
		try:
			from glob import glob
			print("[About] Read /var/lib/opkg/info/gstreamer.control")
			gst = [x.split("Version: ") for x in open(glob("/var/lib/opkg/info/gstreamer?.[0-9].control")[0]) if x.startswith("Version:")][0]
			return "%s" % gst[1].split("+")[0].replace("\n", "")
		except:
			return _("Not installed")


def getFFmpegVersionString():
	lines = fileReadLines("/var/lib/opkg/info/ffmpeg.control", source=MODULE_NAME)
	if lines:
		for line in lines:
			if line[0:8] == "Version:":
				return line[9:].split("+")[0]
	return _("Not Installed")


def getKernelVersionString():
	kernelversion = "unknown"
	try:
		with open("/proc/version") as f:
			kernelversion = f.read().split(" ", 4)[2].split("-", 2)[0]
			return kernelversion
	except:
		return kernelversion


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


def _getCPUSpeedMhz():
	if MODEL in ('hzero', 'h8', 'sfx6008', 'sfx6018'):
		return 1200
	elif MODEL in ('dreamone', 'dreamtwo', 'dreamseven'):
		return 1800
	elif MODEL in ('vuduo4k',):
		return 2100
	else:
		return 0


def getCPUInfoString():
	cpuCount = 0
	cpuSpeedStr = "-"
	cpuSpeedMhz = _getCPUSpeedMhz()
	processor = ""
	lines = fileReadLines("/proc/cpuinfo", source=MODULE_NAME)
	if lines:
		for line in lines:
			line = [x.strip() for x in line.strip().split(":", 1)]
			if not processor and line[0] in ("system type", "model name", "Processor"):
				processor = line[1].split()[0]
			elif not cpuSpeedMhz and line[0] == "cpu MHz":
				cpuSpeedMhz = float(line[1])
			elif line[0] == "processor":
				cpuCount += 1
		if processor.startswith("ARM") and isfile("/proc/stb/info/chipset"):
			processor = "%s (%s)" % (fileReadLine("/proc/stb/info/chipset", "", source=MODULE_NAME).upper(), processor)
		if not cpuSpeedMhz:
			cpuSpeed = fileReadLine("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", source=MODULE_NAME)
			if cpuSpeed:
				cpuSpeedMhz = int(cpuSpeed) / 1000
			else:
				try:
					cpuSpeedMhz = int(int(hexlify(open("/sys/firmware/devicetree/base/cpus/cpu@0/clock-frequency", "rb").read()), 16) / 100000000) * 100
				except:
					cpuSpeedMhz = "1500"

		temperature = None
		if isfile("/proc/stb/fp/temp_sensor_avs"):
			temperature = fileReadLine("/proc/stb/fp/temp_sensor_avs", source=MODULE_NAME)
		elif isfile("/proc/stb/power/avs"):
			temperature = fileReadLine("/proc/stb/power/avs", source=MODULE_NAME)
#		elif isfile("/proc/stb/fp/temp_sensor"):
#			temperature = fileReadLine("/proc/stb/fp/temp_sensor", source=MODULE_NAME)
#		elif isfile("/proc/stb/sensors/temp0/value"):
#			temperature = fileReadLine("/proc/stb/sensors/temp0/value", source=MODULE_NAME)
#		elif isfile("/proc/stb/sensors/temp/value"):
#			temperature = fileReadLine("/proc/stb/sensors/temp/value", source=MODULE_NAME)
		elif isfile("/sys/devices/virtual/thermal/thermal_zone0/temp"):
			temperature = fileReadLine("/sys/devices/virtual/thermal/thermal_zone0/temp", source=MODULE_NAME)
			if temperature:
				temperature = int(temperature) / 1000
		elif isfile("/sys/class/thermal/thermal_zone0/temp"):
			temperature = fileReadLine("/sys/class/thermal/thermal_zone0/temp", source=MODULE_NAME)
			if temperature:
				temperature = int(temperature) / 1000
		elif isfile("/proc/hisi/msp/pm_cpu"):
			lines = fileReadLines("/proc/hisi/msp/pm_cpu", source=MODULE_NAME)
			if lines:
				for line in lines:
					if "temperature = " in line:
						temperature = int(line.split("temperature = ")[1].split()[0])

		if cpuSpeedMhz and cpuSpeedMhz >= 1000:
			cpuSpeedStr = _("%s GHz") % format_string("%.1f", cpuSpeedMhz / 1000)
		else:
			cpuSpeedStr = _("%d MHz") % int(cpuSpeedMhz)

		if temperature:
			degree = "\u00B0"
			if not isinstance(degree, str):
				degree = degree.encode("UTF-8", errors="ignore")
			if isinstance(temperature, float):
				temperature = format_string("%.1f", temperature)
			else:
				temperature = str(temperature)
			return (processor, cpuSpeedStr, ngettext("%d core", "%d cores", cpuCount) % cpuCount, "%s%s C" % (temperature, degree))
			#return ("%s %s MHz (%s) %s%sC") % (processor, cpuSpeed, ngettext("%d core", "%d cores", cpuCount) % cpuCount, temperature, degree)
		return (processor, cpuSpeedStr, ngettext("%d core", "%d cores", cpuCount) % cpuCount, "")
		#return ("%s %s MHz (%s)") % (processor, cpuSpeed, ngettext("%d core", "%d cores", cpuCount) % cpuCount)


def getSystemTemperature():
	temperature = ""
	if isfile("/proc/stb/sensors/temp0/value"):
		temperature = fileReadLine("/proc/stb/sensors/temp0/value", source=MODULE_NAME)
	elif isfile("/proc/stb/sensors/temp/value"):
		temperature = fileReadLine("/proc/stb/sensors/temp/value", source=MODULE_NAME)
	elif isfile("/proc/stb/fp/temp_sensor"):
		temperature = fileReadLine("/proc/stb/fp/temp_sensor", source=MODULE_NAME)
	if temperature:
		return "%s%s C" % (temperature, "\u00B0")
	return temperature


def getChipSetString():
	try:
		chipset = open("/proc/stb/info/chipset").read()
		return str(chipset.lower().replace('\n', ''))
	except IOError:
		return _("undefined")


def getChipSetNumber():
	try:
		f = open('/proc/stb/info/chipset')
		chipset = f.read()
		f.close()
		return str(chipset.lower().replace('\n', '').replace('brcm', '').replace('bcm', ''))
	except IOError:
		return _("unavailable")


def getCPUBrand():
	if BoxInfo.getItem("AmlogicFamily"):
		return _("Amlogic")
	elif BoxInfo.getItem("HiSilicon"):
		return _("HiSilicon")
	elif socfamily.startswith("smp"):
		return _("Sigma Designs")
	elif socfamily.startswith("bcm") or BoxInfo.getItem("brand") == "rpi":
		return _("Broadcom")
	print("[About] No CPU brand?")
	return _("Undefined")


def getCPUArch():
	if BoxInfo.getItem("ArchIsARM64"):
		return _("ARM64")
	elif BoxInfo.getItem("ArchIsARM"):
		return _("ARM")
	return _("Mipsel")


def getFlashType():
	if BoxInfo.getItem("SmallFlash"):
		return _("Small - Tiny image")
	elif BoxInfo.getItem("MiddleFlash"):
		return _("Middle - Lite image")
	return _("Normal - Standard image")


def getDVBAPI():
	return _("Old") if BoxInfo.getItem("OLDE2API") else _("New")


def getDriverInstalledDate():
	try:
		from glob import glob
		try:
			if MODEL in ("dm800", "dm8000"):
				driver = [x.split("-")[-2:-1][0][-9:] for x in open(glob("/var/lib/opkg/info/*-dvb-modules-*.control")[0]) if x.startswith("Version:")][0]
				return "%s-%s-%s" % (driver[:4], driver[4:6], driver[6:])
			else:
				driver = [x.split("-")[-2:-1][0][-8:] for x in open(glob("/var/lib/opkg/info/*-dvb-modules-*.control")[0]) if x.startswith("Version:")][0]
				return "%s-%s-%s" % (driver[:4], driver[4:6], driver[6:])
		except:
			try:
				driver = [x.split("Version:") for x in open(glob("/var/lib/opkg/info/*-dvb-proxy-*.control")[0]) if x.startswith("Version:")][0]
				return "%s" % driver[1].replace("\n", "")
			except:
				driver = [x.split("Version:") for x in open(glob("/var/lib/opkg/info/*-platform-util-*.control")[0]) if x.startswith("Version:")][0]
				return "%s" % driver[1].replace("\n", "")
	except:
		return _("unknown")


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
		days = secs // 86400
		secs = secs % 86400
		times.append(ngettext("%d Day", "%d Days", days) % days)
	h = secs // 3600
	m = (secs % 3600) // 60
	times.append(ngettext("%d Hour", "%d Hours", h) % h)
	times.append(ngettext("%d Minute", "%d Minutes", m) % m)
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


def getopensslVersionString():
	lines = fileReadLines("/var/lib/opkg/info/openssl.control", source=MODULE_NAME)
	if lines:
		for line in lines:
			if line[0:8] == "Version:":
				return line[9:].split("+")[0]
	return _("Not Installed")


# For modules that do "from About import about"
about = modules[__name__]
