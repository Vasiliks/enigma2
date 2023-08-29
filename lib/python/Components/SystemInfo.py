# -*- coding: utf-8 -*-
from hashlib import md5
from os import R_OK, access
from os.path import exists, isfile, join as pathjoin
from re import findall
from subprocess import PIPE, Popen

from enigma import Misc_Options, eAVControl, eDVBCIInterfaces, eDVBResourceManager, eGetEnigmaDebugLvl, eDBoxLCD
from Tools.Directories import SCOPE_LIBDIR, SCOPE_SKIN, fileCheck, fileContains, fileReadLine, fileReadLines, fileExists, resolveFilename
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
		if value is None:
			pass
		elif (value.startswith("\"") or value.startswith("'")) and value.endswith(value[0]):
			value = value[1:-1]
		elif value.startswith("(") and value.endswith(")"):
			data = []
			for item in (x.strip() for x in value[1:-1].split(",")):
				data.append(self.processValue(item))
			value = tuple(data)
		elif value.startswith("[") and value.endswith("]"):
			data = []
			for item in (x.strip() for x in value[1:-1].split(",")):
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

from Tools.Multiboot import getMultibootStartupDevice, getMultibootslots  # This import needs to be here to avoid a SystemInfo load loop!

# Parse the boot commandline.
cmdline = fileReadLine("/proc/cmdline", source=MODULE_NAME)
cmdline = {k: v.strip('"') for k, v in findall(r'(\S+)=(".*?"|\S+)', cmdline)}


def getDemodVersion():
	version = None
	if exists("/proc/stb/info/nim_firmware_version"):
		version = fileReadLine("/proc/stb/info/nim_firmware_version")
	return version and version.strip()


def getNumVideoDecoders():
	numVideoDecoders = 0
	while exists("/dev/dvb/adapter0/video%d" % numVideoDecoders):
		numVideoDecoders += 1
	return numVideoDecoders


def countFrontpanelLEDs():
	numLeds = exists("/proc/stb/fp/led_set_pattern") and 1 or 0
	while exists("/proc/stb/fp/led%d_pattern" % numLeds):
		numLeds += 1
	return numLeds


def hassoftcaminstalled():
	from Tools.camcontrol import CamControl
	return len(CamControl("softcam").getList()) > 1


def getBootdevice():
	dev = ("root" in cmdline and cmdline["root"].startswith("/dev/")) and cmdline["root"][5:]
	while dev and not exists("/sys/block/%s" % dev):
		dev = dev[:-1]
	return dev


def getRCFile(ext):
	filename = resolveFilename(SCOPE_SKIN, pathjoin("rc_models", "%s.%s" % (BoxInfo.getItem("rcname"), ext)))
	if not isfile(filename):
		filename = resolveFilename(SCOPE_SKIN, pathjoin("rc_models", "dmm1.%s" % ext))
	return filename

def getChipsetString():
	if model in ("dm7080", "dm820"):
		return "7435"
	elif model in ("dm520", "dm525"):
		return "73625"
	elif model in ("dm900", "dm920", "et13000"):
		return "7252S"
	elif model in ("hd51", "vs1500", "h7"):
		return "7251S"
	elif model in ('dreamone', 'dreamonetwo', 'dreamseven'):
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


model = BoxInfo.getItem("model")
brand = BoxInfo.getItem("brand")
platform = BoxInfo.getItem("platform")
displaytype = BoxInfo.getItem("displaytype")
architecture = BoxInfo.getItem("architecture")
socfamily = BoxInfo.getItem("socfamily")
mtdkernel = BoxInfo.getItem("mtdkernel")
procModel = getBoxProc()


def getBoxName():
	box = MACHINE
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
	elif box.startswith('et') and not box in ('et8000', 'et8500', 'et8500s', 'et10000'):
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

BoxInfo.setItem("DebugLevel", eGetEnigmaDebugLvl())
BoxInfo.setItem("InDebugMode", eGetEnigmaDebugLvl() >= 4)
BoxInfo.setItem("ModuleLayout", getModuleLayout(), immutable=True)

# Remote control related data.
#
BoxInfo.setItem("RCImage", getRCFile("png"))
BoxInfo.setItem("RCMapping", getRCFile("xml"))
BoxInfo.setItem("RemoteEnable", model in ("dm800", "azboxhd"))
if model in ("maram9", "axodin"):
	repeat = 400
elif model == "azboxhd":
	repeat = 150
else:
	repeat = 100
BoxInfo.setItem("RemoteRepeat", repeat)
BoxInfo.setItem("RemoteDelay", 200 if model in ("maram9", "axodin") else 700)
BoxInfo.setItem("have24hz", eAVControl.getInstance().has24hz())

BoxInfo.setItem("HDMI-PreEmphasis", fileCheck("/proc/stb/hdmi/preemphasis"))

try:
	branch = "?sha=" + "-".join(about.getEnigmaVersionString().split("-")[3:])
except:
	branch = ""
branch_e2plugins = "?sha=python3"
commitLogs = [
	("openPli Enigma2", "https://api.github.com/repos/68foxboris/my-py3/commits"),
	("Openpli Oe Core", "https://api.github.com/repos/openpli/openpli-oe-core/commits"),
	("Enigma2 Plugins", "https://api.github.com/repos/openpli/enigma2-plugins/commits"),
	("Aio Grab", "https://api.github.com/repos/openpli/aio-grab/commits"),
	("Plugin EPGImport", "https://api.github.com/repos/openpli/enigma2-plugin-extensions-epgimport/commits"),
	("Skin PLi HD", "https://api.github.com/repos/littlesat/skin-PLiHD/commits"),
	("OpenWebif", "https://api.github.com/repos/E2OpenPlugins/e2openplugin-OpenWebif/commits"),
	("Hans settings", "https://gitlab.openpli.org/api/v4/projects/5/repository/commits")
]
BoxInfo.setItem("InformationCommitLogs", commitLogs)

SystemInfo["CommonInterface"] = model in ("h9combo", "h9combose", "pulse4kmini") and 1 or eDVBCIInterfaces.getInstance().getNumOfSlots() or model == "vuzero" and 0
SystemInfo["CommonInterfaceCIDelay"] = fileCheck("/proc/stb/tsmux/rmx_delay")
for cislot in range(BoxInfo.getItem("CommonInterface", 0)):
	SystemInfo["CI%dSupportsHighBitrates" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_tsclk" % cislot)
	SystemInfo["CI%dRelevantPidsRoutingSupport" % cislot] = fileCheck("/proc/stb/tsmux/ci%d_relevant_pids_routing" % cislot)
SystemInfo["HasFBCtuner"] = ["Vuplus DVB-C NIM(BCM3158)", "Vuplus DVB-C NIM(BCM3148)", "Vuplus DVB-S NIM(7376 FBC)", "Vuplus DVB-S NIM(45308X FBC)", "Vuplus DVB-S NIM(45208 FBC)", "DVB-S2 NIM(45208 FBC)", "DVB-S2X NIM(45308X FBC)", "DVB-S2 NIM(45308 FBC)", "DVB-C NIM(3128 FBC)", "BCM45208", "BCM45308X", "BCM3158"]
SystemInfo["HasSoftcamInstalled"] = hassoftcaminstalled()
SystemInfo["NumVideoDecoders"] = getNumVideoDecoders()
SystemInfo["PIPAvailable"] = BoxInfo.getItem("NumVideoDecoders", 0) > 1
SystemInfo["CanMeasureFrontendInputPower"] = eDVBResourceManager.getInstance().canMeasureFrontendInputPower()
SystemInfo["12V_Output"] = Misc_Options.getInstance().detected_12V_output()
SystemInfo["ZapMode"] = fileCheck("/proc/stb/video/zapmode") or fileCheck("/proc/stb/video/zapping_mode")
SystemInfo["NumFrontpanelLEDs"] = countFrontpanelLEDs()
SystemInfo["FrontpanelDisplay"] = fileExists("/dev/dbox/oled0") or fileExists("/dev/dbox/lcd0")
SystemInfo["LCDsymbol_circle_recording"] = fileCheck("/proc/stb/lcd/symbol_circle") or model in ("hd51", "vs1500") and fileCheck("/proc/stb/lcd/symbol_recording")
SystemInfo["LCDsymbol_timeshift"] = fileCheck("/proc/stb/lcd/symbol_timeshift")
SystemInfo["LCDshow_symbols"] = (model.startswith("et9") or model in ("hd51", "vs1500")) and fileCheck("/proc/stb/lcd/show_symbols")
SystemInfo["LCDsymbol_hdd"] = model in ("hd51", "vs1500") and fileCheck("/proc/stb/lcd/symbol_hdd")
SystemInfo["FrontpanelDisplayGrayscale"] = fileCheck("/dev/dbox/oled0")
SystemInfo["CanUse3DModeChoices"] = fileCheck("/proc/stb/fb/3dmode_choices")
SystemInfo["DeepstandbySupport"] = model != "dm800"
SystemInfo["Fan"] = BoxInfo.getItem("fan") or fileCheck("/proc/stb/fp/fan") or exists("/proc/fan") or procModel in ("ultra", "premium+")
SystemInfo["FanPWM"] = BoxInfo.getItem("Fan") and fileCheck("/proc/stb/fp/fan_pwm")
SystemInfo["PowerLED"] = fileCheck("/proc/stb/power/powerled") or model in ("gbue4k", "gbquad4k") and fileCheck("/proc/stb/fp/led1_pattern")
SystemInfo["StandbyLED"] = fileCheck("/proc/stb/power/standbyled") or model in ("gbue4k", "gbquad4k") and fileCheck("/proc/stb/fp/led0_pattern")
SystemInfo["SuspendLED"] = fileCheck("/proc/stb/power/suspendled") or fileCheck("/proc/stb/fp/enable_led")
SystemInfo["Display"] = SystemInfo["FrontpanelDisplay"] or SystemInfo["StandbyLED"] or model in ("one", "two")
SystemInfo["LedPowerColor"] = fileCheck("/proc/stb/fp/ledpowercolor")
SystemInfo["LedStandbyColor"] = fileCheck("/proc/stb/fp/ledstandbycolor")
SystemInfo["LedSuspendColor"] = fileCheck("/proc/stb/fp/ledsuspendledcolor")
SystemInfo["Power4x7On"] = fileCheck("/proc/stb/fp/power4x7on")
SystemInfo["Power4x7Standby"] = fileCheck("/proc/stb/fp/power4x7standby")
SystemInfo["Power4x7Suspend"] = fileCheck("/proc/stb/fp/power4x7suspend")
SystemInfo["PowerOffDisplay"] = model not in "formuler1" and fileCheck("/proc/stb/power/vfd") or fileCheck("/proc/stb/lcd/vfd")
SystemInfo["WakeOnLAN"] = fileCheck("/proc/stb/power/wol") or fileCheck("/proc/stb/fp/wol")
SystemInfo["HasExternalPIP"] = platform != "1genxt" and fileCheck("/proc/stb/vmpeg/1/external")
SystemInfo["VideoDestinationConfigurable"] = fileCheck("/proc/stb/vmpeg/0/dst_left")
SystemInfo["hasPIPVisibleProc"] = fileCheck("/proc/stb/vmpeg/1/visible")
SystemInfo["MaxPIPSize"] = platform in ("gfuturesbcmarm", "8100s", "h7") and (360, 288) or (540, 432)
SystemInfo["VFD_scroll_repeats"] = not model.startswith("et8500") and fileCheck("/proc/stb/lcd/scroll_repeats")
SystemInfo["VFD_scroll_delay"] = not model.startswith("et8500") and fileCheck("/proc/stb/lcd/scroll_delay")
SystemInfo["VFD_initial_scroll_delay"] = not model.startswith("et8500") and fileCheck("/proc/stb/lcd/initial_scroll_delay")
SystemInfo["VFD_final_scroll_delay"] = not model.startswith("et8500") and fileCheck("/proc/stb/lcd/final_scroll_delay")
SystemInfo["LcdLiveTV"] = fileCheck("/proc/stb/fb/sd_detach") or fileCheck("/proc/stb/lcd/live_enable")
SystemInfo["LcdLiveTVMode"] = fileCheck("/proc/stb/lcd/mode")
SystemInfo["LcdLiveDecoder"] = fileCheck("/proc/stb/lcd/live_decoder")
SystemInfo["LCDMiniTV"] = fileExists("/proc/stb/lcd/mode")
SystemInfo["ConfigDisplay"] = SystemInfo["FrontpanelDisplay"]
SystemInfo["DefaultDisplayBrightness"] = model in ("dm900", "dm920", "one", "two") and 8 or 5
SystemInfo["FastChannelChange"] = False
SystemInfo["3DMode"] = fileCheck("/proc/stb/fb/3dmode") or fileCheck("/proc/stb/fb/primary/3d")
SystemInfo["3DZNorm"] = fileCheck("/proc/stb/fb/znorm") or fileCheck("/proc/stb/fb/primary/zoffset")
SystemInfo["Blindscan_t2_available"] = fileCheck("/proc/stb/info/vumodel")
SystemInfo["RcTypeChangable"] = not (model in ("gbquad4k", "gbue4k", "et8500") or model.startswith("et7")) and fileCheck("/proc/stb/ir/rc/type")
SystemInfo["HasFullHDSkinSupport"] = model not in ("et4000", "et5000", "sh1", "hd500c", "hd1100", "xp1000", "lc")
SystemInfo["HasMMC"] = "root" in cmdline and cmdline["root"].startswith("/dev/mmcblk")
SystemInfo["HasTranscoding"] = BoxInfo.getItem("transcoding") or BoxInfo.getItem("multitranscoding") or fileCheck("/proc/stb/encoder/0") or fileCheck("/dev/bcm_enc0")
SystemInfo["HasH265Encoder"] = fileContains("/proc/stb/encoder/0/vcodec_choices", "h265")
SystemInfo["CanNotDoSimultaneousTranscodeAndPIP"] = model in ("vusolo4k", "gbquad4k", "gbue4k")
SystemInfo["HasFrontDisplayPicon"] = model in ("et8500", "vusolo4k", "vuuno4kse", "vuduo4k", "vuduo4kse", "vuultimo4k") or platform == "gb7252"
SystemInfo["Has24hz"] = fileCheck("/proc/stb/video/videomode_24hz")
SystemInfo["Has2160p"] = fileCheck("/proc/stb/video/videomode_preferred", "2160p50")
SystemInfo["HasHDMIin"] = model in ("sezammarvel", "xpeedlx3", "atemionemesis", "mbultra", "beyonwizt4", "hd2400", "dm7080", "et10000", "dreamone", "dreamtwo", "vuduo4k", "vuduo4kse", "vuultimo4k", "vuuno4kse", "gbquad4k", "hd2400", "et10000")
SystemInfo["HasHDMIinFHD"] = model in ("dm820", "dm900", "dm920", "vuultimo4k", "beyonwizu4", "et13000", "sf5008", "vuuno4kse", "vuduo4k", "gbquad4k")
SystemInfo["HDMIin"] = SystemInfo["HasHDMIin"] or SystemInfo["HasHDMIinFHD"]
SystemInfo["HasHDMIinPiP"] = SystemInfo["HasHDMIin"] and brand != "dreambox"
SystemInfo["HasHDMI-CEC"] = fileCheck("/dev/cec0") or fileCheck("/dev/hdmi_cec") or fileCheck("/dev/misc/hdmi_cec0")
SystemInfo["HasYPbPr"] = BoxInfo.getItem("yuv")
SystemInfo["HasScart"] = BoxInfo.getItem("scart")
SystemInfo["HasSVideo"] = BoxInfo.getItem("svideo")
SystemInfo["HasComposite"] = BoxInfo.getItem("rca")
SystemInfo["AmlogicFamily"] = model.startswith(("aml", "meson")) or fileCheck("/proc/device-tree/amlogic-dt-id") or fileExists("/usr/bin/amlhalt") or fileExists("/sys/module/amports")
SystemInfo["hasXcoreVFD"] = model in ("osmega", "spycat4k", "spycat4kmini", "spycat4kcombo") and fileCheck("/sys/module/brcmstb_%s/parameters/pt6302_cgram" % model)
SystemInfo["HasOfflineDecoding"] = model not in ("osmini", "osminiplus", "et7000mini", "et11000", "mbmicro", "mbtwinplus", "mbmicrov2", "et7000", "et8500")
SystemInfo["hasKexec"] = fileContains("/proc/cmdline", "kexec=1")
SystemInfo["canKexec"] = not SystemInfo["hasKexec"] and isfile("/usr/bin/kernel_auto.bin") and isfile("/usr/bin/STARTUP.cpio.gz") and (model in ("vuduo4k", "vuduo4kse") and ["mmcblk0p9", "mmcblk0p6"] or model in ("vusolo4k", "vuultimo4k", "vuuno4k", "vuuno4kse") and ["mmcblk0p4", "mmcblk0p1"] or model == "vuzero4k" and ["mmcblk0p7", "mmcblk0p4"])
SystemInfo["MultibootStartupDevice"] = getMultibootStartupDevice()
SystemInfo["canMode12"] = "%s_4.boxmode" % model in cmdline and cmdline["%s_4.boxmode" % model] in ("1", "12") and "192M"
SystemInfo["canMultiBoot"] = getMultibootslots()
SystemInfo["canDualBoot"] = fileCheck("/dev/block/by-name/flag")
SystemInfo["canFlashWithOfgwrite"] = model not in ("dm")
SystemInfo["CanProc"] = SystemInfo["HasMMC"] and not SystemInfo["Blindscan_t2_available"]
SystemInfo["CanChangeOsdAlpha"] = access("/proc/stb/video/alpha", R_OK) and True or False
SystemInfo["CanChangeOsdPlaneAlpha"] = access("/sys/class/graphics/fb0/osd_plane_alpha", R_OK) and True or False
SystemInfo["CanChangeOsdPositionAML"] = access('/sys/class/graphics/fb0/free_scale', R_OK) and True or False
SystemInfo["ScalerSharpness"] = fileCheck("/proc/stb/vmpeg/0/pep_scaler_sharpness")
SystemInfo["BootDevice"] = getBootdevice()
SystemInfo["NimExceptionVuSolo2"] = model == "vusolo2"
SystemInfo["NimExceptionVuDuo2"] = model == "vuduo2"
SystemInfo["NimExceptionDMM8000"] = model == "dm8000"
SystemInfo["FbcTunerPowerAlwaysOn"] = model in ("vusolo4k", "vuduo4k", "vuduo4kse", "vuultimo4k", "vuuno4k", "vuuno4kse")
SystemInfo["HasPhysicalLoopthrough"] = ["Vuplus DVB-S NIM(AVL2108)", "GIGA DVB-S2 NIM (Internal)"]
if model in ("et7500", "et8500"):
	SystemInfo["HasPhysicalLoopthrough"].append("AVL6211")
SystemInfo["HasFBCtuner"] = ["Vuplus DVB-C NIM(BCM3158)", "Vuplus DVB-C NIM(BCM3148)", "Vuplus DVB-S NIM(7376 FBC)", "Vuplus DVB-S NIM(45308X FBC)", "Vuplus DVB-S NIM(45208 FBC)", "DVB-S2 NIM(45208 FBC)", "DVB-S2X NIM(45308X FBC)", "DVB-S2 NIM(45308 FBC)", "DVB-C NIM(3128 FBC)", "BCM45208", "BCM45308X", "BCM3158"]
SystemInfo["HasHiSi"] = fileCheck("/proc/hisi")
SystemInfo["Autoresolution_proc_videomode"] = model in ("gbue4k", "gbquad4k") and "/proc/stb/video/videomode_50hz" or "/proc/stb/video/videomode"
SystemInfo["HaveCISSL"] = fileCheck("/etc/ssl/certs/customer.pem") and fileExists("/etc/ssl/certs/device.pem")
SystemInfo["OScamInstalled"] = isfile("/usr/bin/oscam") or isfile("/usr/bin/oscam-emu") or isfile("/usr/bin/oscam-smod")
SystemInfo["OScamIsActive"] = SystemInfo["OScamInstalled"] and fileCheck("/tmp/.oscam/oscam.version")
SystemInfo["NCamInstalled"] = isfile("/usr/bin/ncam")
SystemInfo["NCamIsActive"] = SystemInfo["NCamInstalled"] and fileCheck("/tmp/.ncam/ncam.version")
SystemInfo["OLDE2API"] = model == "dm800"
SystemInfo["7segment"] = displaytype == "7segment" or "7seg" in displaytype
SystemInfo["textlcd"] = displaytype == "textlcd" or "text" in displaytype
SystemInfo["HiSilicon"] = socfamily.startswith("hisi") or exists("/proc/hisi") or isfile("/usr/bin/hihalt") or exists("/usr/lib/hisilicon")
SystemInfo["DefineSat"] = platform in ("octagonhisil", "octagonhisilnew", "gbmv200", "uclanhisil") or model in ("beyonwizv2", "viper4k")
SystemInfo["AmlogicFamily"] = socfamily.startswith(("aml", "meson")) or fileCheck("/proc/device-tree/amlogic-dt-id") or isfile("/usr/bin/amlhalt") or exists("/sys/module/amports")
SystemInfo["RecoveryMode"] = fileCheck("/proc/stb/fp/boot_mode") and model not in ("hd51", "h7") or platform == "dmamlogic"
SystemInfo["AndroidMode"] = BoxInfo.getItem("RecoveryMode") and model == "multibox" or brand == "wetek" or platform == "dmamlogic"
SystemInfo["grautec"] = fileCheck("/tmp/usbtft")
SystemInfo["DreamBoxAudio"] = platform == "dm4kgen" or model in ("dm7080", "dm800")
SystemInfo["DreamBoxDVI"] = model in ("dm8000", "dm800")
SystemInfo["VFDRepeats"] = brand != "ixuss" and not BoxInfo.getItem("7segment")
SystemInfo["VFDSymbol"] = BoxInfo.getItem("vfdsymbol")
SystemInfo["ArchIsARM64"] = architecture == "aarch64" or "64" in architecture
SystemInfo["ArchIsARM"] = architecture.startswith(("arm", "cortex"))
SystemInfo["FirstCheckModel"] = model in ("tmtwin4k", "mbmicrov2", "revo4k", "force3uhd", "mbmicro", "e4hd", "e4hdhybrid", "valalinux", "lunix", "tmnanom3", "purehd", "force2nano", "purehdse") or brand in ("linkdroid", "wetek")
SystemInfo["SecondCheckModel"] = model in ("osninopro", "osnino", "osninoplus", "dm7020hd", "dm7020hdv2", "9910lx", "9911lx", "9920lx", "tmnanose", "tmnanoseplus", "tmnanosem2", "tmnanosem2plus", "tmnanosecombo", "force2plus", "force2", "force2se", "optimussos", "fusionhd", "fusionhdse", "force2plushv") or brand == "ixuss"
SystemInfo["SeekStatePlay"] = False
SystemInfo["StatePlayPause"] = False
SystemInfo["StandbyState"] = False
SystemInfo["FrontpanelLEDBlinkControl"] = fileCheck("/proc/stb/fp/led_blink")
SystemInfo["FrontpanelLEDBrightnessControl"] = fileCheck("/proc/stb/fp/led_brightness")
SystemInfo["FrontpanelLEDColorControl"] = fileCheck("/proc/stb/fp/led_color")
SystemInfo["FrontpanelLEDFadeControl"] = fileCheck("/proc/stb/fp/led_fade")
SystemInfo["FCCactive"] = False
SystemInfo["CanDownmixAC3"] = fileCheck("/proc/stb/audio/ac3_choices", "downmix")
SystemInfo["CanDownmixDTS"] = fileCheck("/proc/stb/audio/dts_choices", "downmix")
SystemInfo["CanDownmixAAC"] = fileCheck("/proc/stb/audio/aac_choices", "downmix")
SystemInfo["CanDownmixAACPlus"] = fileCheck("/proc/stb/audio/aacplus_choices", "downmix")
SystemInfo["HDMIAudioSource"] = fileCheck("/proc/stb/hdmi/audio_source")
SystemInfo["SCART"] = BoxInfo.getItem("scart") and procModel != "ultra"
SystemInfo["CanAC3Transcode"] = fileCheck("/proc/stb/audio/ac3plus_choices", "force_ac3")
SystemInfo["CanDTSHD"] = fileCheck("/proc/stb/audio/dtshd_choices", "downmix")
SystemInfo["CanAACTranscode"] = fileCheck("/proc/stb/audio/aac_transcode_choices", "off")
SystemInfo["CanWMAPRO"] = fileCheck("/proc/stb/audio/wmapro_choices", "downmix")
SystemInfo["CanAC3PlusTranscode"] = fileCheck("/proc/stb/audio/ac3plus_choices", "force_ac3")
SystemInfo["CanAudioDelay"] = fileCheck("/proc/stb/audio/audio_delay_pcm") or fileCheck("/proc/stb/audio/audio_delay_bitstream")
SystemInfo["CanSyncMode"] = fileCheck("/proc/stb/video/sync_mode_choices")
SystemInfo["CanBTAudio"] = fileCheck("/proc/stb/audio/btaudio_choices", "off")
SystemInfo["CanBTAudioDelay"] = fileCheck("/proc/stb/audio/btaudio_delay") or fileCheck("/proc/stb/audio/btaudio_delay_pcm")
SystemInfo["Has3DSurroundSoftLimiter"] = fileCheck("/proc/stb/audio/3dsurround_softlimiter_choices") and fileCheck("/proc/stb/audio/3dsurround_softlimiter")
SystemInfo["HasBypassEdidChecking"] = fileCheck("/proc/stb/hdmi/bypass_edid_checking")
SystemInfo["HasColordepth"] = fileCheck("/proc/stb/video/hdmi_colordepth")
SystemInfo["HasColorimetryChoices"] = fileCheck("/proc/stb/video/hdmi_colorimetry_choices")
SystemInfo["HasColorspace"] = fileCheck("/proc/stb/video/hdmi_colorspace")
SystemInfo["HasColorspaceSimple"] = SystemInfo["HasColorspace"] and model in ("vusolo4k", "vuuno4k", "vuuno4kse", "vuultimo4k", "vuduo4k", "vuduo4kse")
SystemInfo["HasHDMIpreemphasis"] = fileCheck("/proc/stb/hdmi/preemphasis")
SystemInfo["HasColorimetry"] = fileCheck("/proc/stb/video/hdmi_colorimetry")
SystemInfo["HasColorspaceChoices"] = fileCheck("/proc/stb/video/hdmi_colorspace_choices")
SystemInfo["HasColordepthChoices"] = fileCheck("/proc/stb/video/hdmi_colordepth_choices")
SystemInfo["HasHdrType"] = fileCheck("/proc/stb/video/hdmi_hdrtype")
SystemInfo["HasScaler_sharpness"] = fileCheck("/proc/stb/vmpeg/0/pep_scaler_sharpness")
SystemInfo["HasMultichannelPCM"] = fileCheck("/proc/stb/audio/multichannel_pcm")
SystemInfo["HDRSupport"] = fileCheck("/proc/stb/hdmi/hlg_support_choices") and fileCheck("/proc/stb/hdmi/hlg_support")
SystemInfo["HasAutoVolume"] = fileCheck("/proc/stb/audio/avl_choices") and fileCheck("/proc/stb/audio/avl")
SystemInfo["HasAutoVolumeLevel"] = fileCheck("/proc/stb/audio/autovolumelevel_choices") and fileCheck("/proc/stb/audio/autovolumelevel")
SystemInfo["Has3DSurround"] = fileCheck("/proc/stb/audio/3d_surround_choices") and fileCheck("/proc/stb/audio/3d_surround")
SystemInfo["Has3DSpeaker"] = fileCheck("/proc/stb/audio/3d_surround_speaker_position_choices") and fileCheck("/proc/stb/audio/3d_surround_speaker_position")
SystemInfo["Has3DSurroundSpeaker"] = fileCheck("/proc/stb/audio/3dsurround_choices") and fileCheck("/proc/stb/audio/3dsurround")
SystemInfo["SCART"] = BoxInfo.getItem("scart") and procModel != "ultra"
