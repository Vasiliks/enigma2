# -*- coding: utf-8 -*-
from hashlib import md5
from os import R_OK, access
from os.path import exists, isfile, join as pathjoin
from re import findall
from subprocess import PIPE, Popen

from enigma import Misc_Options, eAVControl, eDVBCIInterfaces, eDVBResourceManager, eGetEnigmaDebugLvl, eDBoxLCD

from process import ProcessList
from Tools.Directories import SCOPE_LIBDIR, SCOPE_SKIN, fileCheck, fileContains, fileReadLine, fileReadLines, fileExists, fileHas, pathExists, resolveFilename
from Tools.MultiBoot import MultiBoot
from Tools.StbHardware import getBoxProc

MODULE_NAME = __name__.split(".")[-1]

SystemInfo = {}


class BoxInformation:  # To maintain data integrity class variables should not be accessed from outside of this class!
	def __init__(self):
		self.immutableList = []
		self.boxInfo = {}
		self.enigmaInfoList = []
		self.enigmaConfList = []
		lines = fileReadLines(pathjoin(resolveFilename(SCOPE_LIBDIR), "enigma.info"), source=MODULE_NAME)
		if lines:
			modified = self.checkChecksum(lines)
			if modified:
				print("[SystemInfo] WARNING: Enigma information file checksum is incorrect!  File appears to have been modified.")
				self.boxInfo["checksumerror"] = True
			else:
				print("[SystemInfo] Enigma information file checksum is correct.")
				self.boxInfo["checksumerror"] = False
			for line in lines:
				if line.startswith("#") or line.strip() == "":
					continue
				if "=" in line:
					item, value = (x.strip() for x in line.split("=", 1))
					if item:
						self.immutableList.append(item)
						self.enigmaInfoList.append(item)
						self.boxInfo[item] = self.processValue(value)
			self.enigmaInfoList = sorted(self.enigmaInfoList)
			print("[SystemInfo] Enigma information file data loaded into BoxInfo.")
		else:
			print("[SystemInfo] ERROR: Enigma information file is not available!  The system is unlikely to boot or operate correctly.")
		filename = isfile(resolveFilename(SCOPE_LIBDIR, "enigma.conf"))
		if filename:
			lines = fileReadLines(pathjoin(resolveFilename(SCOPE_LIBDIR), "enigma.conf"), source=MODULE_NAME)
			print("[SystemInfo] Enigma config override file available and data loaded into BoxInfo.")
			self.boxInfo["overrideactive"] = True
			for line in lines:
				if line.startswith("#") or line.strip() == "":
					continue
				if "=" in line:
					item, value = (x.strip() for x in line.split("=", 1))
					if item:
						self.enigmaConfList.append(item)
						if item in self.boxInfo:
							print("[SystemInfo] Note: Enigma information value '%s' with value '%s' being overridden to '%s'." % (item, self.boxInfo[item], value))
						self.boxInfo[item] = self.processValue(value)
			self.enigmaConfList = sorted(self.enigmaConfList)
		else:
			self.boxInfo["overrideactive"] = False

	def checkChecksum(self, lines):
		value = "Undefined!"
		data = []
		for line in lines:
			if line.startswith("checksum"):
				item, value = (x.strip() for x in line.split("=", 1))
			else:
				data.append(line)
		data.append("")
		result = md5(bytearray("\n".join(data), "UTF-8", errors="ignore")).hexdigest()
		return value != result

	def processValue(self, value):
		valueTest = value.upper() if value else ""
		if (value.startswith("\"") or value.startswith("'")) and value.endswith(value[0]):
			value = value[1:-1]
		elif value.startswith("(") and value.endswith(")"):
			data = []
			for item in [x.strip() for x in value[1:-1].split(",")]:
				data.append(self.processValue(item))
			value = tuple(data)
		elif value.startswith("[") and value.endswith("]"):
			data = []
			for item in [x.strip() for x in value[1:-1].split(",")]:
				data.append(self.processValue(item))
			value = list(data)
		elif valueTest == "NONE":
			value = None
		elif valueTest in ("FALSE", "NO", "OFF", "DISABLED", "DISABLE"):
			value = False
		elif valueTest in ("TRUE", "YES", "ON", "ENABLED", "ENABLE"):
			value = True
		elif value.isdigit() or ((value[0:1] == "-" or value[0:1] == "+") and value[1:].isdigit()):
			value = int(value)
		elif valueTest.startswith("0X"):
			try:
				value = int(value, 16)
			except ValueError:
				pass
		elif valueTest.startswith("0O"):
			try:
				value = int(value, 8)
			except ValueError:
				pass
		elif valueTest.startswith("0B"):
			try:
				value = int(value, 2)
			except ValueError:
				pass
		else:
			try:
				value = float(value)
			except ValueError:
				pass
		return value

	def getEnigmaInfoList(self):
		return self.enigmaInfoList

	def getEnigmaConfList(self):
		return self.enigmaConfList

	def getItemsList(self):
		return sorted(list(self.boxInfo.keys()))

	def getItem(self, item, default=None):
		if item in self.boxInfo:
			value = self.boxInfo[item]
		elif item in SystemInfo:
			value = SystemInfo[item]
		else:
			value = default
		return value

	def setItem(self, item, value, immutable=False):
		if item in self.immutableList:
			print("[BoxInfo] Error: Item '%s' is immutable and can not be %s!" % (item, "changed" if item in self.boxInfo else "added"))
			return False
		if immutable:
			self.immutableList.append(item)
		self.boxInfo[item] = value
		SystemInfo[item] = value
		return True

	def deleteItem(self, item):
		if item in self.immutableList:
			print("[BoxInfo] Error: Item '%s' is immutable and can not be deleted!" % item)
		elif item in self.boxInfo:
			del self.boxInfo[item]
			return True
		return False


BoxInfo = BoxInformation()

ARCHITECTURE = BoxInfo.getItem("architecture")
BRAND = BoxInfo.getItem("brand")
MODEL = BoxInfo.getItem("model")
SOC_FAMILY = BoxInfo.getItem("socfamily")
DISPLAYTYPE = BoxInfo.getItem("displaytype")
MTDROOTFS = BoxInfo.getItem("mtdrootfs")
DISPLAYMODEL = BoxInfo.getItem("displaymodel")
DISPLAYBRAND = BoxInfo.getItem("displaybrand")
PLATFORM = BoxInfo.getItem("platform")
MACHINEBUILD = MODEL
mtdkernel = BoxInfo.getItem("mtdkernel")
procModel = getBoxProc()


def getBoxDisplayName():  # This function returns a tuple like ("BRANDNAME", "BOXNAME")
	return (DISPLAYBRAND, DISPLAYMODEL)


# Parse the boot commandline.
cmdline = fileReadLine("/proc/cmdline", source=MODULE_NAME)
cmdline = {k: v.strip('"') for k, v in findall(r'(\S+)=(".*?"|\S+)', cmdline)}


def getDemodVersion():
	version = None
	if fileExists("/proc/stb/info/nim_firmware_version"):
		version = fileReadLine("/proc/stb/info/nim_firmware_version")
	return version and version.strip()


def getRCFile(ext):
	filename = resolveFilename(SCOPE_SKIN, pathjoin("rc_models", "%s.%s" % (BoxInfo.getItem("rcname"), ext)))
	if not isfile(filename):
		filename = resolveFilename(SCOPE_SKIN, pathjoin("rc_models", "dmm1.%s" % ext))
	return filename


def getNumVideoDecoders():
	numVideoDecoders = 0
	while fileExists("/dev/dvb/adapter0/video%d" % numVideoDecoders):
		numVideoDecoders += 1
	return numVideoDecoders


def countFrontpanelLEDs():
	numLeds = fileExists("/proc/stb/fp/led_set_pattern") and 1 or 0
	while fileExists("/proc/stb/fp/led%d_pattern" % numLeds):
		numLeds += 1
	return numLeds


def hassoftcaminstalled():
	softcams = fileExists("/etc/init.d/softcam") or exists("/etc/init.d/cardserver")
	return softcams


def getBootdevice():
	dev = ("root" in cmdline and cmdline["root"].startswith("/dev/")) and cmdline["root"][5:]
	while dev and not fileExists("/sys/block/%s" % dev):
		dev = dev[:-1]
	return dev


def getChipsetString():
	if MODEL in ("dm7080", "dm820"):
		return "7435"
	elif MODEL in ("dm520", "dm525"):
		return "73625"
	elif MODEL in ("dm900", "dm920", "et13000"):
		return "7252S"
	elif MODEL in ("hd51", "vs1500", "h7"):
		return "7251S"
	elif MODEL in ('dreamone', 'dreamonetwo', 'dreamseven'):
		return "S922X"
	chipset = fileReadLine("/proc/stb/info/chipset", default=_("Undefined"), source=MODULE_NAME)
	return str(chipset.lower().replace("\n", "").replace("bcm", "").replace("brcm", "").replace("sti", ""))


def getModuleLayout():
	modulePath = BoxInfo.getItem("enigmamodule")
	if modulePath:
		process = Popen(("/sbin/modprobe", "--dump-modversions", modulePath), stdout=PIPE, stderr=PIPE, universal_newlines=True)
		stdout, stderr = process.communicate()
		if process.returncode == 0:
			for detail in stdout.split("\n"):
				if "module_layout" in detail:
					return detail.split("\t")[0]
	return None


def getBoxName():
	box = MACHINEBUILD
	machinename = DISPLAYMODEL.lower()
	if box in ('uniboxhd1', 'uniboxhd2', 'uniboxhd3'):
		box = "ventonhdx"
	elif box == "odinm6":
		box = machinename
	elif box == "inihde" and machinename == "hd-1000":
		box = "sezam-1000hd"
	elif box == "ventonhdx" and machinename == "hd-5000":
		box = "sezam-5000hd"
	elif box == "ventonhdx" and machinename == "premium twin":
		box = "miraclebox-twin"
	elif box == "xp1000" and machinename == "sf8 hd":
		box = "sf8"
	elif box.startswith('et') and box not in ('et8000', 'et8500', 'et8500s', 'et10000'):
		box = box[0:3] + 'x00'
	elif box == "odinm9":
		box = "maram9"
	elif box.startswith('sf8008m'):
		box = "sf8008m"
	elif box.startswith('sf8008'):
		box = "sf8008"
	elif box.startswith('ustym4kpro'):
		box = "ustym4kpro"
	elif box.startswith('twinboxlcdci'):
		box = "twinboxlcd"
	elif box == "sfx6018":
		box = "sfx6008"
	elif box == "sx888":
		box = "sx88v2"
	return box


BoxInfo.setItem("BoxName", getBoxName())
BoxInfo.setItem("DebugLevel", eGetEnigmaDebugLvl())
BoxInfo.setItem("InDebugMode", eGetEnigmaDebugLvl() >= 4)
BoxInfo.setItem("ModuleLayout", getModuleLayout(), immutable=True)

BoxInfo.setItem("RCImage", getRCFile("png"))
BoxInfo.setItem("RCMapping", getRCFile("xml"))
BoxInfo.setItem("RemoteEnable", MODEL in ("dm800"))
if MODEL in ('maram9', 'classm', 'axodin', 'axodinc', 'starsatlx', 'genius', 'evo', 'galaxym6'):
	repeat = 400
else:
	repeat = 100
BoxInfo.setItem("RemoteRepeat", repeat)
BoxInfo.setItem("RemoteDelay", 200 if repeat == 400 else 700)
BoxInfo.setItem("have24hz", eAVControl.getInstance().has24hz())

BoxInfo.setItem("HDMI-PreEmphasis", fileCheck("/proc/stb/hdmi/preemphasis"))

try:
	branch = "?sha=" + "-".join(about.getEnigmaVersionString().split("-")[3:])
except:
	branch = ""
branch_e2plugins = "?sha=python3"
commitLogs = [
	("OpenPli Enigma2", "https://api.github.com/repos/68foxboris/enigma2/commits"),
	("Openpli OE Core", "https://api.github.com/repos/openpli/openpli-oe-core/commits"),
	("Enigma2 Plugins", "https://api.github.com/repos/openpli/enigma2-plugins/commits"),
	("Aio Grab", "https://api.github.com/repos/openpli/aio-grab/commits"),
	("Plugin EPGImport", "https://api.github.com/repos/openpli/enigma2-plugin-extensions-epgimport/commits"),
	("Skin PLi HD", "https://api.github.com/repos/68foxboris/skin-PLiHD/commits"),
	("OpenWebif", "https://api.github.com/repos/E2OpenPlugins/e2openplugin-OpenWebif/commits"),
	("Hans settings", "https://gitlab.openpli.org/api/v4/projects/5/repository/commits")
]
BoxInfo.setItem("InformationCommitLogs", commitLogs)

API_STREAMRELAY = ["oscam-emu",]  # add more cams

for cam in API_STREAMRELAY:
	streamrelay = str(ProcessList().named(cam)).strip("[]")
	BoxInfo.setItem("StreamRelay", streamrelay)  # items availables for streamrelay

BoxInfo.setItem("12V_Output", Misc_Options.getInstance().detected_12V_output())
BoxInfo.setItem("3DMode", fileCheck("/proc/stb/fb/3dmode") or fileCheck("/proc/stb/fb/primary/3d"))
BoxInfo.setItem("3DZNorm", fileCheck("/proc/stb/fb/znorm") or fileCheck("/proc/stb/fb/primary/zoffset"))
BoxInfo.setItem("7segment", DISPLAYTYPE in ("7segment",))
BoxInfo.setItem("AmlogicFamily", SOC_FAMILY.startswith(("aml", "meson")) or exists("/proc/device-tree/amlogic-dt-id") or exists("/usr/bin/amlhalt") or exists("/sys/module/amports"))
BoxInfo.setItem("AndroidMode", BoxInfo.getItem("RecoveryMode") and MODEL == "multibox" or BRAND == "wetek" or PLATFORM == "dmamlogic")
BoxInfo.setItem("ArchIsARM64", ARCHITECTURE == "aarch64" or "64" in ARCHITECTURE)
BoxInfo.setItem("ArchIsARM", ARCHITECTURE.startswith(("arm", "cortex")))
BoxInfo.setItem("Autoresolution_proc_videomode", MODEL in ("gbue4k", "gbquad4k") and "/proc/stb/video/videomode_50hz" or "/proc/stb/video/videomode")
BoxInfo.setItem("Blindscan_t2_available", fileCheck("/proc/stb/info/vuMODEL") and MODEL.startswith("vu"))
BoxInfo.setItem("BoxName", getBoxName())
BoxInfo.setItem("BootDevice", getBootdevice())
BoxInfo.setItem("canFlashWithOfgwrite", not (MODEL.startswith("dm")))
BoxInfo.setItem("CanMeasureFrontendInputPower", eDVBResourceManager.getInstance().canMeasureFrontendInputPower())
BoxInfo.setItem("canDualBoot", fileExists("/dev/block/by-name/flag"))
BoxInfo.setItem("canMultiBoot", MultiBoot.getBootSlots())
BoxInfo.setItem("Display", BoxInfo.getItem("FrontpanelDisplay") or BoxInfo.getItem("StandbyLED"))
BoxInfo.setItem("HasKexecMultiboot", fileHas("/proc/cmdline", "kexec=1"))
BoxInfo.setItem("CanChangeOsdAlpha", access("/proc/stb/video/alpha", R_OK) and True or False)
BoxInfo.setItem("CanChangeOsdPlaneAlpha", access("/sys/class/graphics/fb0/osd_plane_alpha", R_OK) and True or False)
BoxInfo.setItem("CanChangeOsdPositionAML", access('/sys/class/graphics/fb0/free_scale', R_OK) and True or False)
BoxInfo.setItem("canMode12", "%s_4.boxmode" % MODEL in cmdline and cmdline["%s_4.boxmode" % MODEL] in ("1", "12") and "192M")
BoxInfo.setItem("cankexec", BoxInfo.getItem("kexecmb") and fileExists("/usr/bin/kernel_auto.bin") and fileExists("/usr/bin/STARTUP.cpio.gz") and not BoxInfo.getItem("HasKexecMultiboot"))
BoxInfo.setItem("CanNotDoSimultaneousTranscodeAndPIP", MODEL in ("vusolo4k", "gbquad4k", "gbue4k"))
BoxInfo.setItem("CanProc", BoxInfo.getItem("HasMMC") and not BoxInfo.getItem("Blindscan_t2_available"))
BoxInfo.setItem("CanUse3DModeChoices", fileExists("/proc/stb/fb/3dmode_choices") and True or False)
BoxInfo.setItem("CIPlusHelper", fileExists("/usr/bin/ciplushelper"))
BoxInfo.setItem("DeepstandbySupport", MODEL != 'dm800')
BoxInfo.setItem("DefineSat", MODEL in ("ustym4kpro", "beyonwizv2", "viper4k", "sf8008", "gbtrio4k", "gbtrio4kplus", "gbip4k", "qviart5"))
BoxInfo.setItem("DefaultDisplayBrightness", MODEL in ("dm900", "dm920") and 8 or 5)
BoxInfo.setItem("DreamBoxAudio", MODEL in ("dm7080", "dm800", "dm900", "dm920", "dreamone", "dreamtwo"))
BoxInfo.setItem("DreamBoxDVI", MODEL in ("dm8000", "dm800"))
BoxInfo.setItem("Fan", fileCheck("/proc/stb/fp/fan"))
BoxInfo.setItem("FanPWM", BoxInfo.getItem("Fan") and fileCheck("/proc/stb/fp/fan_pwm"))
BoxInfo.setItem("FbcTunerPowerAlwaysOn", MODEL in ("vusolo4k", "vuduo4k", "vuduo4kse", "vuultimo4k", "vuuno4k", "vuuno4kse"))
BoxInfo.setItem("FirstCheckModel", MODEL in ("tmtwin4k", "mbmicrov2", "revo4k", "force3uhd", "mbmicro", "e4hd", "e4hdhybrid", "valalinux", "lunix", "tmnanom3", "purehd", "force2nano", "purehdse") or BRAND in ("linkdroid", "wetek"))
BoxInfo.setItem("FrontpanelDisplay", fileExists("/dev/dbox/oled0") or fileExists("/dev/dbox/lcd0"))
BoxInfo.setItem("FrontpanelDisplayGrayscale", fileExists("/dev/dbox/oled0"))
BoxInfo.setItem("grautec", fileExists("/tmp/usbtft"))
BoxInfo.setItem("HasExternalPIP", MODEL not in ("et9x00", "et6x00", "et5x00") and fileCheck("/proc/stb/vmpeg/1/external"))
BoxInfo.setItem("HasFullHDSkinSupport", MODEL not in ("et4000", "et5000", "sh1", "hd500c", "hd1100", "xp1000", "lc"))
BoxInfo.setItem("HasHiSi", pathExists("/proc/hisi"))
BoxInfo.setItem("hasPIPVisibleProc", fileCheck("/proc/stb/vmpeg/1/visible"))
BoxInfo.setItem("HasGPT", MODEL in ("dreamone", "dreamtwo") and pathExists("/dev/mmcblk0p7"))
BoxInfo.setItem("HasMMC", fileHas("/proc/cmdline", "root=/dev/mmcblk") or MultiBoot.canMultiBoot() and fileHas("/proc/cmdline", "root=/dev/sda"))
BoxInfo.setItem("HasSoftcamInstalled", hassoftcaminstalled())
BoxInfo.setItem("HaveCISSL", fileCheck("/etc/ssl/certs/customer.pem") and fileCheck("/etc/ssl/certs/device.pem"))
BoxInfo.setItem("HasFBCtuner", ["Vuplus DVB-C NIM(BCM3158)", "Vuplus DVB-C NIM(BCM3148)", "Vuplus DVB-S NIM(7376 FBC)", "Vuplus DVB-S NIM(45308X FBC)", "Vuplus DVB-S NIM(45208 FBC)", "DVB-S2 NIM(45208 FBC)", "DVB-S2X NIM(45308X FBC)", "DVB-S2 NIM(45308 FBC)", "DVB-C NIM(3128 FBC)", "BCM45208", "BCM45308X", "BCM3158"])
BoxInfo.setItem("HasPhysicalLoopthrough", ["Vuplus DVB-S NIM(AVL2108)", "GIGA DVB-S2 NIM (Internal)"])
if MODEL in ("et7500", "et8500"):
	BoxInfo.setItem("HasPhysicalLoopthrough", BoxInfo.getItem("HasPhysicalLoopthrough") + ["AVL6211"])
BoxInfo.setItem("HasFBCtuner", ["Vuplus DVB-C NIM(BCM3158)", "Vuplus DVB-C NIM(BCM3148)", "Vuplus DVB-S NIM(7376 FBC)", "Vuplus DVB-S NIM(45308X FBC)", "Vuplus DVB-S NIM(45208 FBC)", "DVB-S2 NIM(45208 FBC)", "DVB-S2X NIM(45308X FBC)", "DVB-S2 NIM(45308 FBC)", "DVB-C NIM(3128 FBC)", "BCM45208", "BCM45308X", "BCM3158"])
BoxInfo.setItem("HasHDMI-CEC", fileExists("/dev/hdmi_cec") or fileExists("/dev/misc/hdmi_cec0"))
BoxInfo.setItem("HDMIAudioSource", fileCheck("/proc/stb/hdmi/audio_source"))
BoxInfo.setItem("HDMIin", BoxInfo.getItem("HasHDMIinFHD") or BoxInfo.getItem("HasHDMIin"))
BoxInfo.setItem("HDMIinPiP", BoxInfo.getItem("HDMIin") and BRAND != "dreambox")
BoxInfo.setItem("HasHDMIin", MODEL in ("sezammarvel", "xpeedlx3", "atemionemesis", "mbultra", "beyonwizt4", "hd2400", "dm7080", "et10000", "dreamone", "dreamtwo", "vuduo4k", "vuduo4kse", "vuultimo4k", "vuuno4kse", "gbquad4k", "hd2400", "et10000"))
BoxInfo.setItem("HasHDMIinFHD", MODEL in ("dm820", "dm900", "dm920", "vuultimo4k", "beyonwizu4", "et13000", "sf5008", "vuuno4kse", "vuduo4k", "gbquad4k"))
BoxInfo.setItem("HasFrontDisplayPicon", MODEL in ("et8500", "vusolo4k", "vuuno4kse", "vuduo4k", "vuduo4kse", "vuultimo4k", "gbquad4k", "gbue4k"))
BoxInfo.setItem("Has24hz", fileCheck("/proc/stb/video/videomode_24hz"))
BoxInfo.setItem("Has2160p", fileHas("/proc/stb/video/videomode_preferred", "2160p50"))
BoxInfo.setItem("HasH265Encoder", fileHas("/proc/stb/encoder/0/vcodec_choices", "h265"))
BoxInfo.setItem("HasYPbPr", MODEL in ("dm8000", "et5000", "et6000", "et6500", "et9000", "et9200", "et9500", "et10000", "formuler1", "mbtwinplus", "spycat", "vusolo", "vuduo", "vuduo2", "vuultimo"))
BoxInfo.setItem("HasScart", MODEL in ("dm8000", "et4000", "et6500", "et8000", "et9000", "et9200", "et9500", "et10000", "formuler1", "hd1100", "hd1200", "hd1265", "hd2400", "vusolo", "vusolo2", "vuduo", "vuduo2", "vuultimo", "vuuno", "xp1000"))
BoxInfo.setItem("HasSVideo", MODEL in ("dm8000"))
BoxInfo.setItem("HasComposite", MODEL not in ("i55", "gbquad4k", "gbue4k", "hd1500", "osnino", "osninoplus", "purehd", "purehdse", "revo4k", "vusolo4k", "vuzero4k", "vuduo4k", "vuduo4kse", "vuuno4k", "vuuno4kse", "vuultimo4k"))
BoxInfo.setItem("hasXcoreVFD", MODEL in ("osmega", "spycat4k", "spycat4kmini", "spycat4kcombo") and fileCheck("/sys/module/brcmstb_%s/parameters/pt6302_cgram" % MODEL))
BoxInfo.setItem("HasOfflineDecoding", MODEL not in ("osmini", "osminiplus", "et7000mini", "et11000", "mbmicro", "mbtwinplus", "mbmicrov2", "et7000", "et8500"))
BoxInfo.setItem("HasTranscoding", pathExists("/proc/stb/encoder/0") or fileCheck("/dev/bcm_enc0"))
BoxInfo.setItem("HiSilicon", SOC_FAMILY.startswith("hisi") or exists("/proc/hisi") or exists("/usr/bin/hihalt") or exists("/usr/lib/hisilicon"))
BoxInfo.setItem("LcdLiveTV", fileCheck("/proc/stb/fb/sd_detach") or fileCheck("/proc/stb/lcd/live_enable"))
BoxInfo.setItem("LcdLiveTVPiP", fileCheck("/proc/stb/lcd/live_decoder"))
BoxInfo.setItem("LCDMiniTV", fileExists("/proc/stb/lcd/mode"))
BoxInfo.setItem("LCDMiniTVPiP", BoxInfo.getItem("LCDMiniTV") and MODEL not in ("gb800ueplus", "gbquad4k", "gbue4k"))
BoxInfo.setItem("LcdLiveTVMode", fileCheck("/proc/stb/lcd/mode"))
BoxInfo.setItem("LcdLiveDecoder", fileCheck("/proc/stb/lcd/live_decoder"))
BoxInfo.setItem("LCDsymbol_circle_recording", fileCheck("/proc/stb/lcd/symbol_circle") or MODEL in ("hd51", "vs1500") and fileCheck("/proc/stb/lcd/symbol_recording"))
BoxInfo.setItem("LCDsymbol_timeshift", fileCheck("/proc/stb/lcd/symbol_timeshift"))
BoxInfo.setItem("LCDshow_symbols", (MODEL.startswith("et9") or MODEL in ("hd51", "vs1500")) and fileCheck("/proc/stb/lcd/show_symbols"))
BoxInfo.setItem("LCDsymbol_hdd", MODEL in ("hd51", "vs1500") and fileCheck("/proc/stb/lcd/symbol_hdd"))
BoxInfo.setItem("LEDColorControl", fileExists("/proc/stb/fp/led_color"))
BoxInfo.setItem("LEDPowerColor", fileExists("/proc/stb/fp/ledpowercolor"))
BoxInfo.setItem("LEDStandbyColor", fileExists("/proc/stb/fp/ledstandbycolor"))
BoxInfo.setItem("LEDSuspendColor", fileExists("/proc/stb/fp/ledsuspendledcolor"))
BoxInfo.setItem("MaxPIPSize", MODEL in ("hd51", "h7", "vs1500", "e4hd") and (360, 288) or (540, 432))
BoxInfo.setItem("NimExceptionVuSolo2", MODEL == "vusolo2")
BoxInfo.setItem("NimExceptionVuDuo2", MODEL == "vuduo2")
BoxInfo.setItem("NimExceptionDMM8000", MODEL == "dm8000")
BoxInfo.setItem("NumFrontpanelLEDs", countFrontpanelLEDs())
BoxInfo.setItem("NumVideoDecoders", getNumVideoDecoders())
BoxInfo.setItem("NCamInstalled", fileExists("/usr/bin/ncam"))
BoxInfo.setItem("NCamIsActive", BoxInfo.getItem("NCamInstalled") and fileExists("/tmp/.ncam/ncam.version"))
BoxInfo.setItem("OLDE2API", MODEL in ("dm800"))
BoxInfo.setItem("OScamInstalled", fileExists("/usr/bin/oscam") or fileExists("/usr/bin/oscam-emu") or fileExists("/usr/bin/oscam-smod"))
BoxInfo.setItem("OScamIsActive", BoxInfo.getItem("OScamInstalled") and fileExists("/tmp/.oscam/oscam.version"))
BoxInfo.setItem("PIPAvailable", BoxInfo.getItem("NumVideoDecoders", 1) > 1)
BoxInfo.setItem("Power4x7On", fileExists("/proc/stb/fp/power4x7on"))
BoxInfo.setItem("Power4x7Standby", fileExists("/proc/stb/fp/power4x7standby"))
BoxInfo.setItem("Power4x7Suspend", fileExists("/proc/stb/fp/power4x7suspend"))
BoxInfo.setItem("PowerLed", fileExists("/proc/stb/power/powerled"))
BoxInfo.setItem("PowerLed2", fileExists("/proc/stb/power/powerled2"))
BoxInfo.setItem("PowerOffDisplay", MODEL not in "formuler1" and fileCheck("/proc/stb/power/vfd") or fileCheck("/proc/stb/lcd/vfd"))
BoxInfo.setItem("RecoveryMode", fileCheck("/proc/stb/fp/boot_mode") or MODEL in ("dreamone", "dreamtwo"))
BoxInfo.setItem("RcTypeChangable", not (MODEL in ("gbquad4k", "gbue4k", "et8500") or MODEL in "et7") and pathExists("/proc/stb/ir/rc/type"))
BoxInfo.setItem("ScalerSharpness", fileCheck("/proc/stb/vmpeg/0/pep_scaler_sharpness"))
BoxInfo.setItem("SCART", BoxInfo.getItem("scart") and procModel != "ultra")
BoxInfo.setItem("SecondCheckModel", MODEL in ("osninopro", "osnino", "osninoplus", "dm7020hd", "dm7020hdv2", "9910lx", "9911lx", "9920lx", "tmnanose", "tmnanoseplus", "tmnanosem2", "tmnanosem2plus", "tmnanosecombo", "force2plus", "force2", "force2se", "optimussos", "fusionhd", "fusionhdse", "force2plushv") or BRAND == "ixuss")
BoxInfo.setItem("StandbyLED", fileCheck("/proc/stb/power/standbyled") or MODEL in ("gbue4k", "gbquad4k") and fileCheck("/proc/stb/fp/led0_pattern"))
BoxInfo.setItem("SuspendLED", fileCheck("/proc/stb/power/suspendled") or fileCheck("/proc/stb/fp/enable_led"))
BoxInfo.setItem("StandbyPowerLed", fileExists("/proc/stb/power/standbyled"))
BoxInfo.setItem("SuspendPowerLed", fileExists("/proc/stb/power/suspendled"))
BoxInfo.setItem("VFD_scroll_repeats", eDBoxLCD.getInstance().get_VFD_scroll_repeats())
BoxInfo.setItem("VFD_scroll_delay", eDBoxLCD.getInstance().get_VFD_scroll_delay())
BoxInfo.setItem("VFD_initial_scroll_delay", eDBoxLCD.getInstance().get_VFD_initial_scroll_delay())
BoxInfo.setItem("VFD_final_scroll_delay", eDBoxLCD.getInstance().get_VFD_final_scroll_delay())
BoxInfo.setItem("VideoDestinationConfigurable", fileExists("/proc/stb/vmpeg/0/dst_left"))
BoxInfo.setItem("WakeOnLAN", not MODEL.startswith("et8000") and fileCheck("/proc/stb/power/wol") or fileCheck("/proc/stb/fp/wol"))
BoxInfo.setItem("ZapMode", fileCheck("/proc/stb/video/zapmode") or fileCheck("/proc/stb/video/zapping_mode"))

BoxInfo.setItem("CanAACTranscode", fileHas("/proc/stb/audio/aac_transcode_choices", "off"))
BoxInfo.setItem("CanAC3Transcode", fileHas("/proc/stb/audio/ac3plus_choices", "force_ac3"))
BoxInfo.setItem("CanAC3plusTranscode", fileExists("/proc/stb/audio/ac3plus_choices"))
BoxInfo.setItem("CanAudioDelay", fileCheck("/proc/stb/audio/audio_delay_pcm") or fileCheck("/proc/stb/audio/audio_delay_bitstream"))
BoxInfo.setItem("CanDownmixAC3", fileHas("/proc/stb/audio/ac3_choices", "downmix"))
BoxInfo.setItem("CanDownmixDTS", fileHas("/proc/stb/audio/dts_choices", "downmix"))
BoxInfo.setItem("CanDownmixAAC", fileHas("/proc/stb/audio/aac_choices", "downmix"))
BoxInfo.setItem("CanProc", BoxInfo.getItem("HasMMC") and not BoxInfo.getItem("Blindscan_t2_available"))
BoxInfo.setItem("CanDTSHD", fileHas("/proc/stb/audio/dtshd_choices", "downmix"))
BoxInfo.setItem("CanDownmixAACPlus", fileHas("/proc/stb/audio/aacplus_choices", "downmix"))
BoxInfo.setItem("CanBTAudio", fileHas("/proc/stb/audio/btaudio_choices", "off"))
BoxInfo.setItem("CanBTAudioDelay", fileCheck("/proc/stb/audio/btaudio_delay") or fileCheck("/proc/stb/audio/btaudio_delay_pcm"))
BoxInfo.setItem("CanSyncMode", fileExists("/proc/stb/video/sync_mode_choices"))
BoxInfo.setItem("HasColordepth", fileCheck("/proc/stb/video/hdmi_colordepth"))
BoxInfo.setItem("HasMultichannelPCM", fileCheck("/proc/stb/audio/multichannel_pcm"))
BoxInfo.setItem("HasAutoVolume", fileExists("/proc/stb/audio/avl_choices") and fileCheck("/proc/stb/audio/avl"))
BoxInfo.setItem("HasAutoVolumeLevel", fileExists("/proc/stb/audio/autovolumelevel_choices") and fileCheck("/proc/stb/audio/autovolumelevel"))
BoxInfo.setItem("HasBypassEdidChecking", fileCheck("/proc/stb/hdmi/bypass_edid_checking"))
BoxInfo.setItem("HasColorimetry", fileCheck("/proc/stb/video/hdmi_colorimetry"))
BoxInfo.setItem("HasColorspace", fileCheck("/proc/stb/video/hdmi_colorspace"))
BoxInfo.setItem("HasColorspaceSimple", BoxInfo.getItem("HasColorspace") and BoxInfo.getItem("HasMMC") and BoxInfo.getItem("Blindscan_t2_available"))
BoxInfo.setItem("HasColorimetryChoices", fileCheck("/proc/stb/video/hdmi_colorimetry_choices"))
BoxInfo.setItem("HasColorspaceChoices", fileCheck("/proc/stb/video/hdmi_colorspace_choices"))
BoxInfo.setItem("HasColordepthChoices", fileCheck("/proc/stb/video/hdmi_colordepth_choices"))
BoxInfo.setItem("Has3DSurround", fileExists("/proc/stb/audio/3d_surround_choices") and fileCheck("/proc/stb/audio/3d_surround"))
BoxInfo.setItem("Has3DSpeaker", fileExists("/proc/stb/audio/3d_surround_speaker_position_choices") and fileCheck("/proc/stb/audio/3d_surround_speaker_position"))
BoxInfo.setItem("Has3DSurroundSpeaker", fileExists("/proc/stb/audio/3dsurround_choices") and fileCheck("/proc/stb/audio/3dsurround"))
BoxInfo.setItem("Has3DSurroundSoftLimiter", fileExists("/proc/stb/audio/3dsurround_softlimiter_choices") and fileCheck("/proc/stb/audio/3dsurround_softlimiter"))
BoxInfo.setItem("HasHdrType", fileCheck("/proc/stb/video/hdmi_hdrtype"))
BoxInfo.setItem("HasHDMIpreemphasis", fileCheck("/proc/stb/hdmi/preemphasis"))
BoxInfo.setItem("HDRSupport", fileExists("/proc/stb/hdmi/hlg_support_choices") and fileCheck("/proc/stb/hdmi/hlg_support"))
BoxInfo.setItem("HDMIAudioSource", fileCheck("/proc/stb/hdmi/audio_source"))
BoxInfo.setItem("CanWMAPRO", fileHas("/proc/stb/audio/wmapro_choices", "downmix"))

# dont't sort
SystemInfo["SeekStatePlay"] = False
SystemInfo["StatePlayPause"] = False
SystemInfo["StandbyState"] = False
SystemInfo["FastChannelChange"] = False
SystemInfo["FCCactive"] = False

SystemInfo["CommonInterface"] = eDVBCIInterfaces.getInstance().getNumOfSlots()
SystemInfo["CommonInterfaceCIDelay"] = fileCheck("/proc/stb/tsmux/rmx_delay")
for cislot in range(0, SystemInfo["CommonInterface"]):
	SystemInfo["CI%dSupportsHighBitrates" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_tsclk" % cislot)
	SystemInfo["CI%dRelevantPidsRoutingSupport" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_relevant_pids_routing" % cislot)
