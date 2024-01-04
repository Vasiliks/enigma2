import os
from enigma import eAVControl, eDVBVolumecontrol
from Components.config import config, ConfigSelection, ConfigSubDict, ConfigYesNo, ConfigSubsection, ConfigInteger
from Components.SystemInfo import BoxInfo
from Components.About import about, getChipSetNumber, getChipSetString
from Tools.CList import CList
from Tools.Directories import fileReadLine, fileWriteLine

MODULE_NAME = __name__.split(".")[-1]
MODEL = BoxInfo.getItem("model")
BRAND = BoxInfo.getItem("brand")

config.av.edid_override = ConfigYesNo(default=False)


class VideoHardware:
	axis = {
		"480i": "0 0 719 479",
		"480p": "0 0 719 479",
		"576i": "0 0 719 575",
		"576p": "0 0 719 575",
		"720p": "0 0 1279 719",
		"1080i": "0 0 1919 1079",
		"1080p": "0 0 1919 1079",
		"2160p30": "0 0 3839 2159",
		"2160p": "0 0 3839 2159",
		"smpte": "0 0 4095 2159"
	}

	rates = {}  # High-level, use selectable modes.
	rates["PAL"] = {
		"50Hz": {50: "pal"},
		"60Hz": {60: "pal60"},
		"multi": {50: "pal", 60: "pal60"}
	}
	rates["NTSC"] = {
		"60Hz": {60: "ntsc"}
	}
	rates["Multi"] = {
		"multi": {50: "pal", 60: "ntsc"}
	}
	if BoxInfo.getItem("AmlogicFamily"):
		rates["480i"] = {
			"60Hz": {60: "480i60hz"}
		}
		rates["576i"] = {
			"50Hz": {50: "576i50hz"}
		}
		rates["480p"] = {
			"60Hz": {60: "480p60hz"}
		}
		rates["576p"] = {
			"50Hz": {50: "576p50hz"}
		}
		rates["720p"] = {
			"50Hz": {50: "720p50hz"},
			"60Hz": {60: "720p60hz"},
			"auto": {60: "720p60hz"}
		}
		rates["1080i"] = {
			"50Hz": {50: "1080i50hz"},
			"60Hz": {60: "1080i60hz"},
			"auto": {60: "1080i60hz"}
		}
		rates["1080p"] = {
			"50Hz": {50: "1080p50hz"},
			"60Hz": {60: "1080p60hz"},
			"30Hz": {30: "1080p30hz"},
			"25Hz": {25: "1080p25hz"},
			"24Hz": {24: "1080p24hz"},
			"auto": {60: "1080p60hz"}
		}
		rates["2160p"] = {
			"50Hz": {50: "2160p50hz"},
			"60Hz": {60: "2160p60hz"},
			"30Hz": {30: "2160p30hz"},
			"25Hz": {25: "2160p25hz"},
			"24Hz": {24: "2160p24hz"},
			"auto": {60: "2160p60hz"}
		}
		rates["2160p30"] = {
			"25Hz": {50: "2160p25hz"},
			"30Hz": {60: "2160p30hz"},
			"auto": {60: "2160p30hz"}
		}
	else:
		rates["480i"] = {"60Hz": {60: "480i"}}
		rates["576i"] = {"50Hz": {50: "576i"}}
		rates["480p"] = {"60Hz": {60: "480p"}}
		rates["576p"] = {"50Hz": {50: "576p"}}
		rates["720p"] = {
			"50Hz": {50: "720p50"},
			"60Hz": {60: "720p"},
			"multi": {50: "720p50", 60: "720p"},
			"auto": {50: "720p50", 60: "720p", 24: "720p24"}
		}
		rates["1080i"] = {
			"50Hz": {50: "1080i50"},
			"60Hz": {60: "1080i"},
			"multi": {50: "1080i50", 60: "1080i"},
			"auto": {50: "1080i50", 60: "1080i", 24: "1080i24"}
		}
		rates["1080p"] = {
			"50Hz": {50: "1080p50"},
			"60Hz": {60: "1080p"},
			"multi": {50: "1080p50", 60: "1080p"},
			"auto": {50: "1080p50", 60: "1080p", 24: "1080p24"}
		}
		rates["2160p"] = {
			"50Hz": {50: "2160p50"},
			"60Hz": {60: "2160p"},
			"multi": {50: "2160p50", 60: "2160p"},
			"auto": {50: "2160p50", 60: "2160p", 24: "2160p24"}
		}
		rates["2160p30"] = {
			"25Hz": {50: "2160p25"},
			"30Hz": {60: "2160p30"},
			"multi": {50: "2160p25", 60: "2160p30"},
			"auto": {50: "2160p25", 60: "2160p30", 24: "2160p24"}
		}

	rates["smpte"] = {
		"50Hz": {50: "smpte50hz"},
		"60Hz": {60: "smpte60hz"},
		"30Hz": {30: "smpte30hz"},
		"25Hz": {25: "smpte25hz"},
		"24Hz": {24: "smpte24hz"},
		"auto": {60: "smpte60hz"}
	}

	rates["PC"] = {
		"1024x768": {60: "1024x768"},
		"800x600": {60: "800x600"},  # also not possible
		"720x480": {60: "720x480"},
		"720x576": {60: "720x576"},
		"1280x720": {60: "1280x720"},
		"1280x720 multi": {50: "1280x720_50", 60: "1280x720"},
		"1920x1080": {60: "1920x1080"},
		"1920x1080 multi": {50: "1920x1080", 60: "1920x1080_50"},
		"1280x1024": {60: "1280x1024"},
		"1366x768": {60: "1366x768"},
		"1366x768 multi": {50: "1366x768", 60: "1366x768_50"},
		"1280x768": {60: "1280x768"},
		"640x480": {60: "640x480"}
	}
	modes = {}  # A list of (high-level) modes for a certain port.
	modes["Scart"] = [
		"PAL",
		"NTSC",
		"Multi"
	]
	# modes["DVI-PC"] = [  # This mode does not exist.
	# 	"PC"
	# ]

	if BoxInfo.getItem("AmlogicFamily"):
		modes["HDMI"] = ["720p", "1080p", "smpte", "2160p30", "2160p", "1080i", "576p", "576i", "480p", "480i"]
	elif getChipSetNumber() in ("7366", "7376", "5272s", "7444", "7445", "7445s", "72604"):
		modes["HDMI"] = ["720p", "1080p", "2160p", "1080i", "576p", "576i", "480p", "480i"]
		widescreen_modes = {"720p", "1080p", "1080i", "2160p"}
	elif getChipSetNumber() in ("7252", "7251", "7251S", "7252S", "7251s", "7252s", "7278", "7444s", "3798mv200", "3798mv200h", "3798cv200", "hi3798mv200", "hi3798mv200h", "hi3798cv200", "hi3798mv300", "3798mv300"):
		modes["HDMI"] = ["720p", "1080p", "2160p", "2160p30", "1080i", "576p", "576i", "480p", "480i"]
		widescreen_modes = {"720p", "1080p", "1080i", "2160p", "2160p30"}
	elif getChipSetNumber() in ("7241", "7358", "7362", "73625", "7346", "7356", "73565", "7424", "7425", "7435", "7552", "7581", "7584", "75845", "7585", "pnx8493", "7162", "7111", "3716mv410", "hi3716mv410", "hi3716mv430", "3716mv430"):
		modes["HDMI"] = ["720p", "1080p", "1080i", "576p", "576i", "480p", "480i"]
		widescreen_modes = {"720p", "1080p", "1080i"}
	else:
		modes["HDMI"] = ["720p", "1080i", "576p", "576i", "480p", "480i"]
		widescreen_modes = {"720p", "1080i"}

	modes["YPbPr"] = modes["HDMI"]
	if BoxInfo.getItem("scartyuv", False):
		modes["Scart-YPbPr"] = modes["HDMI"]
	# if "DVI-PC" in modes and not getModeList("DVI-PC"):
	# 	print "[AVSwitch] Remove DVI-PC because that mode does not exist."
	# 	del modes["DVI-PC"]
	if "YPbPr" in modes and not BoxInfo.getItem("yuv", False):
		del modes["YPbPr"]
	if "Scart" in modes and not BoxInfo.getItem("scart", False) and not BoxInfo.getItem("rca", False) and not BoxInfo.getItem("avjack", False):
		del modes["Scart"]

	if MODEL == "hd2400":
		mode = fileReadLine("/proc/stb/info/board_revision", default="", source=MODULE_NAME)
		if mode >= "2":
			del modes["YPbPr"]

	widescreenModes = tuple([x for x in modes["HDMI"] if x not in ("576p", "576i", "480p", "480i")])

	ASPECT_SWITCH_MSG = (_("16:9 reset to normal"),
			"1.85:1 %s" % _("Letterbox"),
			"2.00:1 %s" % _("Letterbox"),
			"2.21:1 %s" % _("Letterbox"),
			"2.35:1 %s" % _("Letterbox"))

	def __init__(self):
		self.last_modes_preferred = []
		self.on_hotplug = CList()
		self.current_mode = None
		self.current_port = None
		print("[AVSwitch] getAvailableModes:'%s'" % eAVControl.getInstance().getAvailableModes())
		self.is24hzAvailable()
		self.readPreferredModes()
		self.createConfig()

	def readAvailableModes(self):
		modes = eAVControl.getInstance().getAvailableModes()
		return modes.split()

	def is24hzAvailable(self):
		BoxInfo.setItem("have24hz", eAVControl.getInstance().has24hz())

	def readPreferredModes(self, saveMode=False, readOnly=False):
		modes = ""
		if config.av.edid_override.value is False:
			modes = eAVControl.getInstance().getPreferredModes(1)
			if saveMode:
				modes = modes.split()
				return modes if len(modes) > 1 else []

			print("[AVSwitch] getPreferredModes:'%s'" % modes)
			self.modes_preferred = modes.split()

		if len(modes) < 2:
			self.modes_preferred = self.readAvailableModes()
			print("[AVSwitch] used default modes:%s" % self.modes_preferred)

		if len(self.modes_preferred) <= 2:
			print("[AVSwitch] preferend modes not ok, possible driver failer, len=%s" % len(self.modes_preferred))
			self.modes_preferred = self.readAvailableModes()

		if readOnly:
			return self.modes_preferred

		if self.modes_preferred != self.last_modes_preferred:
			self.last_modes_preferred = self.modes_preferred
			self.on_hotplug("HDMI")  # must be HDMI

	def getWindowsAxis(self):
		port = config.av.videoport.value
		mode = config.av.videomode[port].value
		return self.axis[mode]

	def createConfig(self, *args):
		config.av.videomode = ConfigSubDict()
		config.av.autores_mode_sd = ConfigSubDict()
		config.av.autores_mode_hd = ConfigSubDict()
		config.av.autores_mode_fhd = ConfigSubDict()
		config.av.autores_mode_uhd = ConfigSubDict()
		config.av.videorate = ConfigSubDict()
		config.av.autores_rate_sd = ConfigSubDict()
		config.av.autores_rate_hd = ConfigSubDict()
		config.av.autores_rate_fhd = ConfigSubDict()
		config.av.autores_rate_uhd = ConfigSubDict()
		portList = []  # Create list of output ports.
		for port in self.getPortList():
			if "HDMI" in port:
				portList.insert(0, (port, port))
			else:
				portList.append((port, port))
			modes = self.getModeList(port)
			if len(modes):
				config.av.videomode[port] = ConfigSelection(choices=[mode for (mode, rates) in modes])
				config.av.autores_mode_sd[port] = ConfigSelection(choices=[mode for (mode, rates) in modes])
				config.av.autores_mode_hd[port] = ConfigSelection(choices=[mode for (mode, rates) in modes])
				config.av.autores_mode_fhd[port] = ConfigSelection(choices=[mode for (mode, rates) in modes])
				config.av.autores_mode_uhd[port] = ConfigSelection(choices=[mode for (mode, rates) in modes])
			for (mode, rates) in modes:
				rateList = []
				for rate in rates:
					if rate == "auto" and not BoxInfo.getItem("have24hz"):
						continue
					rateList.append((rate, rate))
				config.av.videorate[mode] = ConfigSelection(choices=rateList)
				config.av.autores_rate_sd[mode] = ConfigSelection(choices=rateList)
				config.av.autores_rate_hd[mode] = ConfigSelection(choices=rateList)
				config.av.autores_rate_fhd[mode] = ConfigSelection(choices=rateList)
				config.av.autores_rate_uhd[mode] = ConfigSelection(choices=rateList)
		config.av.videoport = ConfigSelection(choices=portList)

		defaults = (0,  # the preset values for the offset heights
				62,   # 1.85:1
				100,  # 2.00:1
				144,  # 2.21:1
				170)  # 2.35:1

		config.av.aspectswitch = ConfigSubsection()
		config.av.aspectswitch.enabled = ConfigYesNo(default=False)
		config.av.aspectswitch.offsets = ConfigSubDict()
		for aspect in range(5):
			config.av.aspectswitch.offsets[str(aspect)] = ConfigInteger(default=defaults[aspect], limits=(0, 170))

	def isPortAvailable(self, port):  # Fix me!
		return True

	def isModeAvailable(self, port, mode, rate, availableModes):  # Check if a high-level mode with a given rate is available.
		rate = self.rates[mode][rate]
		for mode in rate.values():
			if port != "HDMI":
				if mode not in availableModes:
					return False
			elif mode not in self.modes_preferred:
				return False
		return True

	def isPortUsed(self, port):
		if port == "HDMI":
			self.readPreferredModes()
			return len(self.modes_preferred) != 0
		else:
			return True

	def isWidescreenMode(self, port, mode):  # This is only used in getOutputAspect
		return mode in self.widescreenModes

	# TODO AML
	def getAspectRatioSetting(self):
		return {
			"4_3_letterbox": 0,
			"4_3_panscan": 1,
			"16_9": 2,
			"16_9_always": 3,
			"16_10_letterbox": 4,
			"16_10_panscan": 5,
			"16_9_letterbox": 6
		}.get(config.av.aspectratio.value, config.av.aspectratio.value)

	def getFramebufferScale(self):
		return (1, 1)

	def getModeList(self, port):  # Get a list with all modes, with all rates, for a given port.
		results = []
		availableModes = self.readAvailableModes()
		for mode in self.modes[port]:
			rates = [rate for rate in self.rates[mode] if self.isModeAvailable(port, mode, rate, availableModes)]  # List all rates which are completely valid.
			if len(rates):  # If at least one rate is OK then add this mode.
				results.append((mode, rates))
		return results

	def getPortList(self):
		return [port for port in self.modes if self.isPortAvailable(port)]

	def setAspect(self, configElement):
		eAVControl.getInstance().setAspect(configElement.value, 1)

	def setAspectRatio(self, value):
		if value < 100:
			eAVControl.getInstance().setAspectRatio(value)
		else:  # Aspect Switcher
			value -= 100
			offset = config.av.aspectswitch.offsets[str(value)].value
			newheight = 576 - offset
			newtop = offset // 2
			if value:
				newwidth = 720
			else:
				newtop = 0
				newwidth = 0
				newheight = 0

			eAVControl.getInstance().setAspectRatio(2)  # 16:9
			eAVControl.getInstance().setVideoSize(newtop, 0, newwidth, newheight)

	def setColorFormat(self, value):
		if not self.current_port:
			self.current_port = config.av.videoport.value
		if self.current_port in ("YPbPr", "Scart-YPbPr"):
			eAVControl.getInstance().setColorFormat("yuv")
		elif self.current_port == "RCA":
			eAVControl.getInstance().setColorFormat("cvbs")
		else:
			eAVControl.getInstance().setColorFormat(value)

	def setConfiguredMode(self):
		port = config.av.videoport.value
		if port in config.av.videomode:
			mode = config.av.videomode[port].value
			if mode in config.av.videorate:
				rate = config.av.videorate[mode].value
				self.setMode(port, mode, rate)
			else:
				print("[AVSwitch] Current mode not available, not setting video mode!")
		else:
			print("[AVSwitch] Current port not available, not setting video mode!")

	def setInput(self, input):
		eAVControl.getInstance().setInput(input, 1)

	def setVideoModeDirect(self, mode):
		if BoxInfo.getItem("AmlogicFamily"):
			rate = mode[-4:].replace("hz", "Hz")
			force = int(rate[:-2])
			mode = mode[:-4]
			self.setMode("HDMI", mode, rate, force)
		else:
			eAVControl.getInstance().setVideoMode(mode)

	def setMode(self, port, mode, rate, force=None):
		print("[AVSwitch] Setting mode for port '%s', mode '%s', rate '%s'." % (port, mode, rate))
		# config.av.videoport.value = port  # We can ignore "port".
		self.current_mode = mode
		self.current_port = port
		modes = self.rates[mode][rate]

		mode50 = modes.get(50)
		mode60 = modes.get(60)
		mode24 = modes.get(24)

		if mode50 is None or force == 60:
			mode50 = mode60
		if mode60 is None or force == 50:
			mode60 = mode50
		if mode24 is None or force:
			mode24 = mode60
			if force == 50:
				mode24 = mode50

		if BoxInfo.getItem("AmlogicFamily"):
			amlmode = list(modes.values())[0]
			oldamlmode = fileReadLine("/sys/class/display/mode", default="", source=MODULE_NAME)
			fileWriteLine("/sys/class/display/mode", amlmode, source=MODULE_NAME)
			print("[AVSwitch] Amlogic setting videomode to mode: %s" % amlmode)
			fileWriteLine("/etc/u-boot.scr.d/000_hdmimode.scr", "setenv hdmimode %s" % amlmode, source=MODULE_NAME)
			fileWriteLine("/etc/u-boot.scr.d/000_outputmode.scr", "setenv outputmode %s" % amlmode, source=MODULE_NAME)
			system("update-autoexec")
			fileWriteLine("/sys/class/ppmgr/ppscaler", "1", source=MODULE_NAME)
			fileWriteLine("/sys/class/ppmgr/ppscaler", "0", source=MODULE_NAME)
			fileWriteLine("/sys/class/video/axis", self.axis[mode], source=MODULE_NAME)
			stride = fileReadLine("/sys/class/graphics/fb0/stride", default="", source=MODULE_NAME)
			limits = [int(x) for x in self.axis[mode].split()]
			config.osd.dst_left = ConfigSelectionNumber(default=limits[0], stepwidth=1, min=limits[0] - 255, max=limits[0] + 255, wraparound=False)
			config.osd.dst_top = ConfigSelectionNumber(default=limits[1], stepwidth=1, min=limits[1] - 255, max=limits[1] + 255, wraparound=False)
			config.osd.dst_width = ConfigSelectionNumber(default=limits[2], stepwidth=1, min=limits[2] - 255, max=limits[2] + 255, wraparound=False)
			config.osd.dst_height = ConfigSelectionNumber(default=limits[3], stepwidth=1, min=limits[3] - 255, max=limits[3] + 255, wraparound=False)

			if oldamlmode != amlmode:
				config.osd.dst_width.setValue(limits[0])
				config.osd.dst_height.setValue(limits[1])
				config.osd.dst_left.setValue(limits[2])
				config.osd.dst_top.setValue(limits[3])
				config.osd.dst_left.save()
				config.osd.dst_width.save()
				config.osd.dst_top.save()
				config.osd.dst_height.save()
			print("[AVSwitch] Framebuffer mode:%s  stride:%s axis:%s" % (getDesktop(0).size().width(), stride, self.axis[mode]))
			return

		success = fileWriteLine("/proc/stb/video/videomode_50hz", mode50, source=MODULE_NAME)
		if success:
			success = fileWriteLine("/proc/stb/video/videomode_60hz", mode60, source=MODULE_NAME)
		if not success:  # Fallback if no possibility to setup 50/60 hz mode
			fileWriteLine("/proc/stb/video/videomode", mode50, source=MODULE_NAME)

		if BoxInfo.getItem("have24hz"):
			fileWriteLine("/proc/stb/video/videomode_24hz", mode24, source=MODULE_NAME)

		if BRAND == "gigablue":
			# use 50Hz mode (if available) for booting
			fileWriteLine("/etc/videomode", mode50, source=MODULE_NAME)

		self.setColorFormat(config.av.colorformat.value)

	def setPolicy43(self, configElement):
		eAVControl.getInstance().setPolicy43(configElement.value, 1)

	def setPolicy169(self, configElement):
		eAVControl.getInstance().setPolicy169(configElement.value, 1)

	def setWss(self, configElement):
		eAVControl.getInstance().setWSS(configElement.value, 1)

	def saveMode(self, port, mode, rate):
		config.av.videoport.value = port
		config.av.videoport.save()
		if port in config.av.videomode:
			config.av.videomode[port].value = mode
			config.av.videomode[port].save()
		if mode in config.av.videorate:
			config.av.videorate[mode].value = rate
			config.av.videorate[mode].save()


VIDEO = VideoHardware()
VIDEO.setConfiguredMode()
