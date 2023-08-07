from enigma import eConsoleAppContainer, eDVBResourceManager, eGetEnigmaDebugLvl, eLabel, eTimer, getDesktop, ePoint, eSize
from os import listdir, popen, remove
from os.path import getmtime, isfile, join as pathjoin
from PIL import Image
import skin
import os
import re
from skin import parameters
from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen, ScreenSummary
from Screens.MessageBox import MessageBox

from Components.config import config
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Sources.StaticText import StaticText
from Components.Harddisk import harddiskmanager
from Components.NimManager import nimmanager
from Components.About import about
from Components.ScrollLabel import ScrollLabel
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.Console import Console
from Components.GUIComponent import GUIComponent
from Components.Pixmap import MultiPixmap, Pixmap
from Components.Network import iNetwork
from Components.SystemInfo import BoxInfo, SystemInfo

from Tools.Directories import SCOPE_PLUGINS, resolveFilename, fileExists, fileHas, pathExists, fileReadLines, fileWriteLine, isPluginInstalled
from Tools.Geolocation import geolocation
from Tools.StbHardware import getFPVersion, getProcInfoTypeTuner, getBoxProc
from Tools.LoadPixmap import LoadPixmap
from time import strftime


API_GITHUB = 0
API_GITLAB = 1

model = BoxInfo.getItem("model")
brand = BoxInfo.getItem("brand")
socfamily = BoxInfo.getItem("socfamily")
displaytype = BoxInfo.getItem("displaytype")
platform = BoxInfo.getItem("platform")

procmodel = getBoxProc()

MODULE_NAME = __name__.split(".")[-1]

INFO_COLORS = ["N", "H", "P", "V", "M"]
INFO_COLOR = {
	"B": None,
	"N": 0x00ffffff,  # Normal.
	"H": 0x00ffffff,  # Headings.
	"P": 0x00888888,  # Prompts.
	"V": 0x00888888,  # Values.
	"M": 0x00ffff00  # Messages.
}


def getTypeTuner():
	typetuner = {
		"00": _("OTT Model"),
		"10": _("Single"),
		"11": _("Twin"),
		"12": _("Combo"),
		"21": _("Twin Hybrid"),
		"22": _("Single Hybrid")
	}
	if getProcInfoTypeTuner():
		return "%s - %s" % (getProcInfoTypeTuner(), typetuner.get(getProcInfoTypeTuner()))


class InformationBase(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session, mandatoryWidgets=["information"])
		HelpableScreen.__init__(self)
		self.skinName = ["Information"]
		self["information"] = ScrollLabel()
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Refresh"))
		self["actions"] = HelpableActionMap(self, ["CancelSaveActions", "OkActions", "NavigationActions"], {
			"cancel": (self.keyCancel, _("Close the screen")),
			"close": (self.closeRecursive, _("Close the screen and exit all menus")),
			"save": (self.refreshInformation, _("Refresh the screen")),
			"ok": (self.refreshInformation, _("Refresh the screen")),
			"top": (self["information"].moveTop, _("Move to first line / screen")),
			"pageUp": (self["information"].pageUp, _("Move up a screen")),
			"up": (self["information"].pageUp, _("Move up a screen")),
			"down": (self["information"].pageDown, _("Move down a screen")),
			"pageDown": (self["information"].pageDown, _("Move down a screen")),
			"bottom": (self["information"].moveBottom, _("Move to last line / screen")),
			"right": self.displayInformation,
			"left": self.displayInformation,
		}, prio=0, description=_("Common Information Actions"))
		if isfile(resolveFilename(SCOPE_PLUGINS, pathjoin("boxes", "%s.png" % (model)))):
			self["key_info"] = StaticText(_("INFO"))
			self["infoActions"] = HelpableActionMap(self, ["InfoActions"], {
				"info": (self.showReceiverImage, _("Show receiver image(s)"))
			}, prio=0, description=_("Receiver Information Actions"))
		colors = parameters.get("InformationColors", (0x00ffffff, 0x00ffffff, 0x00888888, 0x00888888, 0x00ffff00))
		if len(colors) == len(INFO_COLORS):
			for index in range(len(colors)):
				INFO_COLOR[INFO_COLORS[index]] = colors[index]
		else:
			print("[Information] Warning: %d colors are defined in the skin when %d were expected!" % (len(colors), len(INFO_COLORS)))
		self["information"].setText(_("Loading information, please wait..."))
		self.onInformationUpdated = [self.displayInformation]
		self.onLayoutFinish.append(self.displayInformation)
		self.console = Console()
		self.informationTimer = eTimer()
		self.informationTimer.callback.append(self.fetchInformation)
		self.informationTimer.start(25)

	def showReceiverImage(self):
		self.session.openWithCallback(self.informationWindowClosed, InformationImage)

	def keyCancel(self):
		self.console.killAll()
		self.close()

	def closeRecursive(self):
		self.console.killAll()
		self.close(True)

	def informationWindowClosed(self, *retVal):
		if retVal and retVal[0]:
			self.close(True)

	def fetchInformation(self):
		self.informationTimer.stop()
		for callback in self.onInformationUpdated:
			callback()

	def refreshInformation(self):
		self.informationTimer.start(25)
		for callback in self.onInformationUpdated:
			callback()

	def displayInformation(self):
		pass

	def getSummaryInformation(self):
		pass

	def createSummary(self):
		return InformationSummary


def formatLine(style, left, right=None):
	styleLen = len(style)
	leftStartColor = "" if styleLen > 0 and style[0] == "B" else "\c%08x" % (INFO_COLOR.get(style[0], "P") if styleLen > 0 else INFO_COLOR["P"])
	leftEndColor = "" if leftStartColor == "" else "\c%08x" % INFO_COLOR["N"]
	leftIndent = "    " * int(style[1]) if styleLen > 1 and style[1].isdigit() else ""
	rightStartColor = "" if styleLen > 2 and style[2] == "B" else "\c%08x" % (INFO_COLOR.get(style[2], "V") if styleLen > 2 else INFO_COLOR["V"])
	rightEndColor = "" if rightStartColor == "" else "\c%08x" % INFO_COLOR["N"]
	rightIndent = "    " * int(style[3]) if styleLen > 3 and style[3].isdigit() else ""
	if right is None:
		colon = "" if styleLen > 0 and style[0] in ("M", "P", "V") else ""
		return "%s%s%s%s%s" % (leftIndent, leftStartColor, left, colon, leftEndColor)
	return "%s%s%s:%s|%s%s%s%s" % (leftIndent, leftStartColor, left, leftEndColor, rightIndent, rightStartColor, right, rightEndColor)


class InformationImage(Screen, HelpableScreen):
	skin = """
	<screen name="InformationImage" title="Receiver Image" position="center,center" size="950,560">
		<widget name="name" position="10,10" size="e-20,25" font="Regular;20" horizontalAlignment="center" transparent="1" verticalAlignment="center" />
		<widget name="image" position="10,45" size="e-20,e-105" alphaTest="blend" scale="1" transparent="1" />
		<widget source="key_red" render="Label" position="10,e-50" size="180,40" backgroundColor="key_red" conditional="key_red" font="Regular;20" foregroundColor="key_text" horizontalAlignment="center" verticalAlignment="center">
			<convert type="ConditionalShowHide" />
		</widget>
		<widget source="key_green" render="Label" position="200,e-50" size="180,40" backgroundColor="key_green" conditional="key_green" font="Regular;20" foregroundColor="key_text" horizontalAlignment="center" verticalAlignment="center">
			<convert type="ConditionalShowHide" />
		</widget>
		<widget source="key_yellow" render="Label" position="390,e-50" size="180,40" backgroundColor="key_yellow" conditional="key_yellow" font="Regular;20" foregroundColor="key_text" horizontalAlignment="center" verticalAlignment="center">
			<convert type="ConditionalShowHide" />
		</widget>
		<widget source="key_help" render="Label" position="e-90,e-50" size="80,40" backgroundColor="key_back" conditional="key_help" font="Regular;20" foregroundColor="key_text" horizontalAlignment="center" verticalAlignment="center">
			<convert type="ConditionalShowHide" />
		</widget>
		<widget source="lab1" render="Label" position="0,0" size="0,0" conditional="lab1" font="Regular;22" transparent="1" />
		<widget source="lab2" render="Label" position="0,0" size="0,0" conditional="lab2" font="Regular;18" transparent="1" />
		<widget source="lab3" render="Label" position="0,0" size="0,0" conditional="lab3" font="Regular;18" transparent="1" />
		<widget source="lab4" render="Label" position="0,0" size="0,0" conditional="lab4" font="Regular;18" transparent="1" />
		<widget source="lab5" render="Label" position="0,0" size="0,0" conditional="lab5" font="Regular;18" transparent="1" />
		<widget source="lab6" render="Label" position="0,0" size="0,0" conditional="lab6" font="Regular;18" transparent="1" />
	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session, mandatoryWidgets=["name", "image"])
		HelpableScreen.__init__(self)
		self["name"] = Label()
		self["image"] = Pixmap()
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Prev Image"))
		self["key_yellow"] = StaticText(_("Next Image"))
		boxes = "Extensions/OpenWebif/public/images/boxes/"
		remotes = "Extensions/OpenWebif/public/images/remotes/"
		self["actions"] = HelpableActionMap(self, ["OkCancelActions", "ColorActions"], {
			"cancel": (self.keyCancel, _("Close the screen")),
			"close": (self.closeRecursive, _("Close the screen and exit all menus")),
			"ok": (self.nextImage, _("Show next image")),
			"red": (self.keyCancel, _("Close the screen")),
			"green": (self.prevImage, _("Show previous image")),
			"yellow": (self.nextImage, _("Show next image"))
		}, prio=0, description=_("Receiver Image Actions"))
		self.images = (
			(_("Front"), "%s%s.png", (boxes, model)),
			(_("Rear"), "%s%s-rear.png", (boxes, model)),
			(_("Remote Control"), "%s%s.png", (remotes, BoxInfo.getItem("rcname"))),
			(_("Flashing"), "%s%s-flashing.png", (boxes, model)),
			(_("Internal"), "%s%s-internal.png", (boxes, model))
		)
		self.imageIndex = 0
		self.widgetContext = None
		self.onLayoutFinish.append(self.layoutFinished)

	def keyCancel(self):
		self.close()

	def closeRecursive(self):
		self.close(True)

	def prevImage(self):
		self.imageIndex -= 1
		if self.imageIndex < 0:
			self.imageIndex = len(self.images) - 1
		while not isfile(resolveFilename(SCOPE_PLUGINS, self.images[self.imageIndex][1] % self.images[self.imageIndex][2])):
			self.imageIndex -= 1
			if self.imageIndex < 0:
				self.imageIndex = len(self.images) - 1
				break
		self.layoutFinished()

	def nextImage(self):
		self.imageIndex += 1
		while not isfile(resolveFilename(SCOPE_PLUGINS, self.images[self.imageIndex][1] % self.images[self.imageIndex][2])):
			self.imageIndex += 1
			if self.imageIndex >= len(self.images):
				self.imageIndex = 0
				break
		self.layoutFinished()

	def layoutFinished(self):
		if self.widgetContext is None:
			self.widgetContext = tuple(self["image"].getPosition() + self["image"].getSize())
			print(self.widgetContext)
		self["name"].setText("%s  -  %s %s" % (self.images[self.imageIndex][0], brand, displaytype))
		imagePath = resolveFilename(SCOPE_PLUGINS, self.images[self.imageIndex][1] % self.images[self.imageIndex][2])
		image = LoadPixmap(imagePath)
		if image:
			img = Image.open(imagePath)
			imageWidth, imageHeight = img.size
			scale = float(self.widgetContext[2]) / imageWidth if imageWidth >= imageHeight else float(self.widgetContext[3]) / imageHeight
			sizeW = int(imageWidth * scale)
			sizeH = int(imageHeight * scale)
			posX = self.widgetContext[0] + int(self.widgetContext[2] / 2.0 - sizeW / 2.0)
			posY = self.widgetContext[1] + int(self.widgetContext[3] / 2.0 - sizeH / 2.0)
			self["image"].instance.move(ePoint(posX, posY))
			self["image"].instance.resize(eSize(sizeW, sizeH))
			self["image"].instance.setPixmap(image)


def formatLine(style, left, right=None):
	styleLen = len(style)
	leftStartColor = "" if styleLen > 0 and style[0] == "B" else "\c%08x" % (INFO_COLOR.get(style[0], "P") if styleLen > 0 else INFO_COLOR["P"])
	leftEndColor = "" if leftStartColor == "" else "\c%08x" % INFO_COLOR["N"]
	leftIndent = "    " * int(style[1]) if styleLen > 1 and style[1].isdigit() else ""
	rightStartColor = "" if styleLen > 2 and style[2] == "B" else "\c%08x" % (INFO_COLOR.get(style[2], "V") if styleLen > 2 else INFO_COLOR["V"])
	rightEndColor = "" if rightStartColor == "" else "\c%08x" % INFO_COLOR["N"]
	rightIndent = "    " * int(style[3]) if styleLen > 3 and style[3].isdigit() else ""
	if right is None:
		colon = "" if styleLen > 0 and style[0] in ("M", "P", "V") else ""
		return "%s%s%s%s%s" % (leftIndent, leftStartColor, left, colon, leftEndColor)
	return "%s%s%s:%s|%s%s%s%s" % (leftIndent, leftStartColor, left, leftEndColor, rightIndent, rightStartColor, right, rightEndColor)


class InformationSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.parent = parent
		self["information"] = StaticText()
		parent.onInformationUpdated.append(self.updateSummary)
		# self.updateSummary()

	def updateSummary(self):
		# print("[Information] DEBUG: Updating summary.")
		self["information"].setText(self.parent.getSummaryInformation())


class About(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("About"))
		self["key_green"] = Button(_("Translations"))
		self["key_red"] = Button(_("Latest Commits"))
		self["key_yellow"] = Button(_("Dmesg Info"))
		self["key_blue"] = Button(_("Memory Info"))
		hddsplit = skin.parameters.get("AboutHddSplit", 1)

		AboutText = _("Hardware: ") + model + "\n"
		if platform != model:
			AboutText += _("Platform: ") + platform + "\n"
		if procmodel != model:
 			AboutText += _("Proc model: ") + procmodel + "\n"


		if fileExists("/proc/stb/info/sn"):
			hwserial = open("/proc/stb/info/sn", "r").read().strip()
			AboutText += _("Hardware serial: ") + hwserial + "\n"

		if fileExists("/proc/stb/info/release"):
			hwrelease = open("/proc/stb/info/release", "r").read().strip()
			AboutText += _("Factory release: ") + hwrelease + "\n"

		AboutText += _("Brand/Meta: ") + BoxInfo.getItem("brand") + "\n"

		if fileExists("/proc/stb/ir/rc/type"):
			rctype = open("/proc/stb/ir/rc/type", "r").read().strip()
			AboutText += _("RC type: ") + rctype + "\n"

		AboutText += "\n"
		cpu = about.getCPUInfoString()
		AboutText += _("CPU: ") + cpu + "\n"
		AboutText += _("CPU brand: ") + about.getCPUBrand() + "\n"

		AboutText += "\n"
		if BoxInfo.getItem("Display") or BoxInfo.getItem("7segment") or model != "gbip4k":
			AboutText += _("Type Display: ") + BoxInfo.getItem("displaytype") + "\n"
		else:
			AboutText += _("No Display") + "\n"
		EnigmaVersion = about.getEnigmaVersionString()
		EnigmaVersion = EnigmaVersion.rsplit("-", EnigmaVersion.count("-") - 2)
		if len(EnigmaVersion) == 3:
			EnigmaVersion = EnigmaVersion[0] + " (" + EnigmaVersion[2] + "-" + EnigmaVersion[1] + ")"
		else:
			EnigmaVersion = EnigmaVersion[0] + " (" + EnigmaVersion[1] + ")"
		EnigmaVersion = _("Enigma2 version: ") + EnigmaVersion
		self["EnigmaVersion"] = StaticText(EnigmaVersion)
		AboutText += "\n" + EnigmaVersion + "\n"
		AboutText += _("Build date: ") + about.getBuildDateString() + "\n"
		AboutText += _("Last update: ") + about.getUpdateDateString() + "\n"
		AboutText += _("Enigma2 (re)starts: %d\n") % config.misc.startCounter.value
		AboutText += _("Enigma2 debug level: %d\n") % eGetEnigmaDebugLvl()

		AboutText += "\n"
		AboutText += _("DVB driver version: ") + about.getDriverInstalledDate() + "\n"

		GStreamerVersion = _("GStreamer version: ") + about.getGStreamerVersionString().replace("GStreamer", "")
		self["GStreamerVersion"] = StaticText(GStreamerVersion)
		AboutText += "\n" + GStreamerVersion + "\n"

		FFmpegVersion = _("FFmpeg version: ") + about.getFFmpegVersionString()
		self["FFmpegVersion"] = StaticText(FFmpegVersion)
		AboutText += FFmpegVersion + "\n"

		AboutText += "\n"
		AboutText += _("Python version: ") + about.getPythonVersionString() + "\n"
		AboutText += _("GCC version: ") + about.getGccVersion() + "\n"
		AboutText += _("Glibc version: ") + about.getGlibcVersion() + "\n"
		AboutText += "\n"

		fp_version = getFPVersion()
		if fp_version is None or fp_version == "unknown":
 			fp_version = ""
		else:
			fp_version = _("Frontprocessor version: %s") % fp_version
			AboutText += fp_version
			self["FPVersion"] = StaticText(fp_version)

		if SystemInfo["HasHDMI-CEC"] and config.hdmicec.enabled.value:
			address = config.hdmicec.fixed_physical_address.value if config.hdmicec.fixed_physical_address.value != "0.0.0.0" else _("No fixed address set")
			AboutText += "\n" + _("HDMI-CEC Enabled") + ": " + address
		else:
			hdmicec_disabled = _("Disabled")
			AboutText += "\n" + _("HDMI-CEC %s") % hdmicec_disabled

		AboutText += "\n" + _('Skin & Resolution: %s (%sx%s)\n') % (config.skin.primary_skin.value.split('/')[0], getDesktop(0).size().width(), getDesktop(0).size().height())

		servicemp3 = _("ServiceMP3. IPTV recording (Yes).")
		servicehisilicon = _("ServiceHisilicon. IPTV recording (No). (Recommended ServiceMP3).")
		exteplayer3 = _("ServiceApp-ExtEplayer3. IPTV recording (No). (Recommended ServiceMP3).")
		gstplayer = _("ServiceApp-GstPlayer. IPTV recording (No). (Recommended ServiceMP3).")
		if isPluginInstalled("ServiceApp"):
			if isPluginInstalled("ServiceMP3"):
				if config.plugins.serviceapp.servicemp3.replace.value and config.plugins.serviceapp.servicemp3.player.value == "exteplayer3":
					player = "%s" % exteplayer3
				else:
					player = "%s" % gstplayer
				if not config.plugins.serviceapp.servicemp3.replace.value:
					player = "%s" % servicemp3
			elif isPluginInstalled("ServiceHisilicon"):
				if config.plugins.serviceapp.servicemp3.replace.value and config.plugins.serviceapp.servicemp3.player.value == "exteplayer3":
					player = "%s" % exteplayer3
				else:
					player = "%s" % gstplayer
				if not config.plugins.serviceapp.servicemp3.replace.value:
					player = "%s" % servicehisilicon
			else:
				player = _("Not installed")
		else:
			if isPluginInstalled("ServiceMP3"):
				player = "%s" % servicemp3
			elif isPluginInstalled("ServiceHisilicon"):
				player = "%s" % servicehisilicon
			else:
				player = _("Not installed")
		AboutText += _("Player: %s") % player

		AboutText += "\n"
		AboutText += _("Uptime: ") + about.getBoxUptime()

		self["AboutScrollLabel"] = ScrollLabel(AboutText)
		self["actions"] = ActionMap(["ColorActions", "SetupActions", "DirectionActions"], {
			"cancel": self.close,
			"ok": self.close,
			"red": self.showCommits,
			"green": self.showTranslationInfo,
			"blue": self.showMemoryInfo,
			"yellow": self.showTroubleshoot,
			"up": self["AboutScrollLabel"].pageUp,
			"down": self["AboutScrollLabel"].pageDown
		})

	def showTranslationInfo(self):
		self.session.open(TranslationInfo)

	def showCommits(self):
		self.session.open(CommitInfo)

	def showMemoryInfo(self):
		self.session.open(MemoryInfo)

	def showTroubleshoot(self):
		self.session.open(Troubleshoot)

	def doNothing(self):
		pass


class Geolocation(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Geolocation"))
		self.setTitle(_("Geolocation Information"))
		self["key_red"] = Button(_("Close"))
		GeolocationText = _("Information about your Geolocation data") + "\n"
		GeolocationText += "\n"

		try:
			geolocationData = geolocation.getGeolocationData(fields="continent,country,regionName,city,timezone,currency,lat,lon", useCache=True)
			continent = geolocationData.get("continent", None)
			if isinstance(continent, str):
				continent = str(continent)
			if continent != None:
				GeolocationText += _("Continent: ") + "\t" + continent + "\n"

			country = geolocationData.get("country", None)
			if isinstance(country, str):
				country = str(country)
			if country != None:
				GeolocationText += _("Country: ") + "\t" + country + "\n"

			state = geolocationData.get("regionName", None)
			if isinstance(state, str):
				state = str(state)
			if state != None:
				GeolocationText += _("State: ") + "\t" + state + "\n"

			city = geolocationData.get("city", None)
			if isinstance(city, str):
				city = str(city)
			if city != None:
				GeolocationText += _("City: ") + "\t" + city + "\n"

			GeolocationText += "\n"

			timezone = geolocationData.get("timezone", None)
			if isinstance(timezone, str):
				timezone = str(timezone)
			if timezone != None:
				GeolocationText += _("Timezone: ") + "\t" + timezone + "\n"

			currency = geolocationData.get("currency", None)
			if isinstance(currency, str):
				currency = str(currency)
			if currency != None:
				GeolocationText += _("Currency: ") + "\t" + currency + "\n"

			GeolocationText += "\n"

			latitude = geolocationData.get("lat", None)
			if str(float(latitude)) != None:
				GeolocationText += _("Latitude: ") + "\t" + str(float(latitude)) + "\n"

			longitude = geolocationData.get("lon", None)
			if str(float(longitude)) != None:
				GeolocationText += _("Longitude: ") + "\t" + str(float(longitude)) + "\n"
			self["AboutScrollLabel"] = ScrollLabel(GeolocationText)
		except Exception as err:
			self["AboutScrollLabel"] = ScrollLabel(_("Requires internet connection"))

		self["actions"] = ActionMap(["ColorActionsAbout", "SetupActions", "DirectionActions"], {
			"cancel": self.close,
			"ok": self.close,
			"up": self["AboutScrollLabel"].pageUp,
			"down": self["AboutScrollLabel"].pageDown
		})

	def doNothing(self):
		pass

class TunerInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Tuner Information"))
		self.skinName.insert(0, "TunerInformation")

	def displayInformation(self):
		info = []
		info.append(formatLine("H", _("Detected tuners")))
		info.append("")
		nims = nimmanager.nimList()
		descList = []
		curIndex = -1
		if fileExists("/usr/bin/dvb-fe-tool"):
			import time
			try:
				cmd = 'dvb-fe-tool > /tmp/dvbfetool.txt ; dvb-fe-tool -f 1 >> /tmp/dvbfetool.txt ; cat /proc/bus/nim_sockets >> /tmp/dvbfetool.txt'
				res = Console().ePopen(cmd)
				time.sleep(0.1)
			except:
				pass
		for count in range(len(nims)):
			data = nims[count].split(":")
			idx = data[0].strip("Tuner").strip()
			desc = data[1].strip()
			if descList and descList[curIndex]["desc"] == desc:
				descList[curIndex]["end"] = idx
			else:
				descList.append({
					"desc": desc,
					"start": idx,
					"end": idx
				})
				curIndex += 1
			count += 1
		for count in range(len(descList)):
			data = descList[count]["start"] if descList[count]["start"] == descList[count]["end"] else ("%s - %s" % (descList[count]["start"], descList[count]["end"]))
			info.append(formatLine("H", "Tuner %s:" % data))
			info.append(formatLine("", "%s" % descList[count]["desc"]))
		info.append(formatLine("H", _("Type Tuner"), "%s" % getTypeTuner())) if getTypeTuner() else ""
		# info.append("")
		# info.append(formatLine("H", _("Logical tuners")))  # Each tuner is a listed separately even if the hardware is common.
		# info.append("")
		# nims = nimmanager.nimListCompressed()
		# for count in range(len(nims)):
		# 	tuner, type = [x.strip() for x in nims[count].split(":", 1)]
		# 	info.append(formatLine("P1", tuner, type))
		info.append("")
		numSlots = 0
		dvbFeToolTxt = ""
		nimSlots = nimmanager.getSlotCount()
		for nim in range(nimSlots):
			dvbFeToolTxt += eDVBResourceManager.getInstance().getFrontendCapabilities(nim)
		dvbApiVersion = dvbFeToolTxt.splitlines()[0].replace("DVB API version: ", "").strip()
		info.append(formatLine("", _("DVB API"), _("New"))) if float(dvbApiVersion) > 5 else info.append(formatLine("", _("DVB API"), _("Old")))
		info.append(formatLine("", _("DVB API version"), dvbApiVersion))
		info.append("")
		info.append(formatLine("", _("Transcoding"), (_("Yes") if BoxInfo.getItem("transcoding") else _("No"))))
		info.append(formatLine("", _("MultiTranscoding"), (_("Yes") if BoxInfo.getItem("multitranscoding") else _("No"))))
		info.append("")
		if fileHas("/tmp/dvbfetool.txt", "Mode 2: DVB-S"):
			 info.append(formatLine("", _("DVB-S2/C/T2 Combined"), (_("Yes"))))

		info.append(formatLine("", _("DVB-S2X"), (_("Yes") if fileHas("/tmp/dvbfetool.txt", "DVB-S2X") or pathExists("/proc/stb/frontend/0/t2mi") or pathExists("/proc/stb/frontend/1/t2mi") else _("No"))))
		info.append(formatLine("", _("DVB-S"), (_("Yes") if "DVBS" in dvbFeToolTxt or "DVB-S" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("DVB-T"), (_("Yes") if "DVBT" in dvbFeToolTxt or "DVB-T" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("DVB-C"), (_("Yes") if "DVBC" in dvbFeToolTxt or "DVB-C" in dvbFeToolTxt else _("No"))))
		info.append("")
		info.append(formatLine("", _("Multistream"), (_("Yes") if "MULTISTREAM" in dvbFeToolTxt else _("No"))))
		info.append("")
		info.append(formatLine("", _("ANNEX-A"), (_("Yes") if "ANNEX_A" in dvbFeToolTxt or "ANNEX-A" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("ANNEX-B"), (_("Yes") if "ANNEX_B" in dvbFeToolTxt or "ANNEX-B" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("ANNEX-C"), (_("Yes") if "ANNEX_C" in dvbFeToolTxt or "ANNEX-C" in dvbFeToolTxt else _("No"))))
		self["information"].setText("\n".join(info))


class Devices(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		screentitle = _("Storage Devices")
		title = screentitle
		Screen.setTitle(self, title)
		self["HDDHeader"] = StaticText(_("Detected devices:"))
		self["MountsHeader"] = StaticText(_("Network servers:"))
		self["nims"] = StaticText()
		for count in (0, 1, 2, 3):
			self["Tuner" + str(count)] = StaticText("")
		self["hdd"] = StaticText()
		self["mounts"] = StaticText()
		self.list = []
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.populate2)
		self["key_red"] = Button(_("Close"))
		self["actions"] = ActionMap(["SetupActions", "ColorActionsAbout", "TimerEditActions"], {
			"cancel": self.close,
			"red": self.close,
			"save": self.close
		})
		self.onLayoutFinish.append(self.populate)

	def populate(self):
		self.mountinfo = ''
		self["actions"].setEnabled(False)
		scanning = _("Please wait while scanning for devices...")
		self["hdd"].setText(scanning)
		self['mounts'].setText(scanning)
		self.activityTimer.start(1)

	def populate2(self):
		self.activityTimer.stop()
		self.Console = Console()
		self.hddlist = harddiskmanager.HDDList()
		self.list = []
		if self.hddlist:
			for count in range(len(self.hddlist)):
				hdd = self.hddlist[count][1]
				hddp = self.hddlist[count][0]
				if "ATA" in hddp:
					hddp = hddp.replace('ATA', '')
					hddp = hddp.replace('Internal', 'ATA Bus ')
				free = hdd.Totalfree()
				if ((float(free) / 1024) / 1024) >= 1:
					freeline = _("Free: ") + str(round(((float(free) / 1024) / 1024), 2)) + _("TB")
				elif (free / 1024) >= 1:
					freeline = _("Free: ") + str(round((float(free) / 1024), 2)) + _("GB")
				elif free >= 1:
					freeline = _("Free: ") + str(free) + _("MB")
				elif "Generic(STORAGE" in hddp:
					continue
				else:
					freeline = _("Free: ") + _("full")
				line = "%s      %s" % (hddp, freeline)
				self.list.append(line)
		self.list = '\n'.join(self.list)
		self["hdd"].setText(self.list)

		self.Console.ePopen("df -mh | grep -v '^Filesystem'", self.Stage1Complete)

	def Stage1Complete(self, result, retval, extra_args=None):
		result = result.replace('\n                        ', ' ').split('\n')
		self.mountinfo = ""
		for line in result:
			self.parts = line.split()
			if line and self.parts[0] and (self.parts[0].startswith('192') or self.parts[0].startswith('//192')):
				line = line.split()
				ipaddress = line[0]
				mounttotal = line[1]
				mountfree = line[3]
				if self.mountinfo:
					self.mountinfo += "\n"
				self.mountinfo += "%s (%sB, %sB %s)" % (ipaddress, mounttotal, mountfree, _("free"))

		if self.mountinfo:
			self["mounts"].setText(self.mountinfo)
		else:
			self["mounts"].setText(_('none'))
		self["actions"].setEnabled(True)

	def doNothing(self):
		pass


class SystemNetworkInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		screentitle = _("Network")
		title = screentitle
		Screen.setTitle(self, title)
		self.skinName = ["SystemNetworkInfo", "WlanStatus"]
		self["LabelBSSID"] = StaticText()
		self["LabelESSID"] = StaticText()
		self["LabelQuality"] = StaticText()
		self["LabelSignal"] = StaticText()
		self["LabelBitrate"] = StaticText()
		self["LabelEnc"] = StaticText()
		self["BSSID"] = StaticText()
		self["ESSID"] = StaticText()
		self["quality"] = StaticText()
		self["signal"] = StaticText()
		self["bitrate"] = StaticText()
		self["enc"] = StaticText()

		self["IFtext"] = StaticText()
		self["IF"] = StaticText()
		self["Statustext"] = StaticText()
		self["statuspic"] = MultiPixmap()
		self["statuspic"].setPixmapNum(1)
		self["statuspic"].show()
		self["devicepic"] = MultiPixmap()
		self["AboutScrollLabel"] = ScrollLabel()
		self["key_red"] = StaticText(_("Close"))
		self["actions"] = ActionMap(["SetupActions", "ColorActionsAbout", "DirectionActions"], {
			"cancel": self.close,
			"ok": self.close,
			"up": self["AboutScrollLabel"].pageUp,
			"down": self["AboutScrollLabel"].pageDown,
		})

		self.iface = None
		self.createscreen()
		self.iStatus = None

		if iNetwork.isWirelessInterface(self.iface):
			try:
				from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus

				self.iStatus = iStatus
			except:
				pass
			self.resetList()
			self.onClose.append(self.cleanup)

		self.onLayoutFinish.append(self.updateStatusbar)

	def createscreen(self):
		self.AboutText = ""
		self.iface = "eth0"
		eth0 = about.getIfConfig('eth0')
		if 'addr' in eth0:
			self.AboutText += _("IP:") + "\t" + eth0['addr'] + "\n"
			if 'netmask' in eth0:
				self.AboutText += _("Netmask:") + "\t" + eth0['netmask'] + "\n"
			if 'hwaddr' in eth0:
				self.AboutText += _("MAC:") + "\t" + eth0['hwaddr'] + "\n"
			self.iface = 'eth0'

		eth1 = about.getIfConfig('eth1')
		if 'addr' in eth1:
			self.AboutText += _("IP:") + "\t" + eth1['addr'] + "\n"
			if 'netmask' in eth1:
				self.AboutText += _("Netmask:") + "\t" + eth1['netmask'] + "\n"
			if 'hwaddr' in eth1:
				self.AboutText += _("MAC:") + "\t" + eth1['hwaddr'] + "\n"
			self.iface = 'eth1'

		ra0 = about.getIfConfig('ra0')
		if 'addr' in ra0:
			self.AboutText += _("IP:") + "\t" + ra0['addr'] + "\n"
			if 'netmask' in ra0:
				self.AboutText += _("Netmask:") + "\t" + ra0['netmask'] + "\n"
			if 'hwaddr' in ra0:
				self.AboutText += _("MAC:") + "\t" + ra0['hwaddr'] + "\n"
			self.iface = 'ra0'

		wlan0 = about.getIfConfig('wlan0')
		if 'addr' in wlan0:
			self.AboutText += _("IP:") + "\t" + wlan0['addr'] + "\n"
			if 'netmask' in wlan0:
				self.AboutText += _("Netmask:") + "\t" + wlan0['netmask'] + "\n"
			if 'hwaddr' in wlan0:
				self.AboutText += _("MAC:") + "\t" + wlan0['hwaddr'] + "\n"
			self.iface = 'wlan0'

		wlan3 = about.getIfConfig('wlan3')
		if 'addr' in wlan3:
			self.AboutText += _("IP:") + "\t" + wlan3['addr'] + "\n"
			if 'netmask' in wlan3:
				self.AboutText += _("Netmask:") + "\t" + wlan3['netmask'] + "\n"
			if 'hwaddr' in wlan3:
				self.AboutText += _("MAC:") + "\t" + wlan3['hwaddr'] + "\n"
			self.iface = 'wlan3'

		rx_bytes, tx_bytes = about.getIfTransferredData(self.iface)
		self.AboutText += "\n"
		self.AboutText += _("Bytes received:") + "\t" + rx_bytes + "\n"
		self.AboutText += _("Bytes sent:") + "\t" + tx_bytes + "\n"

		geolocationData = geolocation.getGeolocationData(fields="isp,org,mobile,proxy,query", useCache=True)
		isp = geolocationData.get("isp", None)
		isporg = geolocationData.get("org", None)
		if isinstance(isp, str):
			isp = str(isp)
		if isinstance(isporg, str):
			isporg = str(isporg)
		self.AboutText += "\n"
		if isp != None:
			if isporg != None:
				self.AboutText += _("ISP: ") + "\t" + isp + " " + (isporg) + "\n"
			else:
				self.AboutText += "\n" + _("ISP: ") + "\t" + isp + "\n"

		mobile = geolocationData.get("mobile", False)
		if mobile:
			self.AboutText += _("Mobile: ") + "\t" + _("Yes") + "\n"
		else:
			self.AboutText += _("Mobile: ") + "\t" + _("No") + "\n"

		proxy = geolocationData.get("proxy", False)
		if proxy:
			self.AboutText += _("Proxy: ") + "\t" + _("Yes") + "\n"
		else:
			self.AboutText += _("Proxy: ") + "\t" + _("No") + "\n"

		publicip = geolocationData.get("query", None)
		if str(publicip) != "":
			self.AboutText += _("Public IP: ") + "\t" + str(publicip) + "\n" + "\n"


		self.console = Console()
		self.console.ePopen('ethtool %s' % self.iface, self.SpeedFinished)

	def SpeedFinished(self, result, retval, extra_args):
		result_tmp = str(result).split('\n')
		for line in result_tmp:
			if 'Speed:' in line:
				speed = line.split(': ')[1][:-4]
				self.AboutText += _("Speed:") + "\t" + speed + _('Mb/s')

		hostname = open('/proc/sys/kernel/hostname').read()
		self.AboutText += "\n" + _("Hostname:") + "\t" + hostname + "\n"

		self["AboutScrollLabel"].setText(self.AboutText)

	def cleanup(self):
		if self.iStatus:
			self.iStatus.stopWlanConsole()

	def resetList(self):
		if self.iStatus:
			self.iStatus.getDataForInterface(self.iface, self.getInfoCB)

	def getInfoCB(self, data, status):
		self.LinkState = None
		if data != None and data:
			if status != None:
# getDataForInterface()->iwconfigFinished() in
# Plugins/SystemPlugins/WirelessLan/Wlan.py sets fields to boolean False
# if there is no info for them, so we need to check that possibility
# for each status[self.iface] field...
#
				if self.iface == 'wlan0' or self.iface == 'wlan3' or self.iface == 'ra0':
# accesspoint is used in the "enc" code too, so we get it regardless
#
					if not status[self.iface]["accesspoint"]:
						accesspoint = _("Unknown")
					else:
						if status[self.iface]["accesspoint"] == "Not-Associated":
							accesspoint = _("Not-Associated")
							essid = _("No connection")
						else:
							accesspoint = status[self.iface]["accesspoint"]
					if 'BSSID' in self:
						self.AboutText += _('Accesspoint:') + '\t' + accesspoint + '\n'

					if 'ESSID' in self:
						if not status[self.iface]["essid"]:
							essid = _("Unknown")
						else:
							if status[self.iface]["essid"] == "off":
								essid = _("No connection")
							else:
								essid = status[self.iface]["essid"]
						self.AboutText += _('SSID:') + '\t' + essid + '\n'

					if 'quality' in self:
						if not status[self.iface]["quality"]:
							quality = _("Unknown")
						else:
							quality = status[self.iface]["quality"]
						self.AboutText += _('Link quality:') + '\t' + quality + '\n'

					if 'bitrate' in self:
						if not status[self.iface]["bitrate"]:
							bitrate = _("Unknown")
						else:
							if status[self.iface]["bitrate"] == '0':
								bitrate = _("Unsupported")
							else:
								bitrate = str(status[self.iface]["bitrate"]) + " Mb/s"
						self.AboutText += _('Bitrate:') + '\t' + bitrate + '\n'

					if 'signal' in self:
						if not status[self.iface]["signal"]:
							signal = _("Unknown")
						else:
							signal = status[self.iface]["signal"]
						self.AboutText += _('Signal strength:') + '\t' + str(signal) + '\n'

					if 'enc' in self:
						if not status[self.iface]["encryption"]:
							encryption = _("Unknown")
						else:
							if status[self.iface]["encryption"] == "off":
								if accesspoint == "Not-Associated":
									encryption = _("Disabled")
								else:
									encryption = _("Unsupported")
							else:
								encryption = _("Enabled")
						self.AboutText += _('Encryption:') + '\t' + encryption + '\n'

					if ((status[self.iface]["essid"] and status[self.iface]["essid"] == "off") or
						not status[self.iface]["accesspoint"] or
						status[self.iface]["accesspoint"] == "Not-Associated"):
						self.LinkState = False
						self["statuspic"].setPixmapNum(1)
						self["statuspic"].show()
					else:
						self.LinkState = True
						iNetwork.checkNetworkState(self.checkNetworkCB)
					self["AboutScrollLabel"].setText(self.AboutText)

	def exit(self):
		self.close(True)

	def updateStatusbar(self):
		self["IFtext"].setText(_("Network:"))
		self["IF"].setText(iNetwork.getFriendlyAdapterName(self.iface))
		self["Statustext"].setText(_("Link:"))
		if iNetwork.isWirelessInterface(self.iface):
			self["devicepic"].setPixmapNum(1)
			try:
				self.iStatus.getDataForInterface(self.iface, self.getInfoCB)
			except:
				self["statuspic"].setPixmapNum(1)
				self["statuspic"].show()
		else:
			iNetwork.getLinkState(self.iface, self.dataAvail)
			self["devicepic"].setPixmapNum(0)
		self["devicepic"].show()

	def dataAvail(self, data):
		self.LinkState = None
		for line in data.splitlines():
			line = line.strip()
			if 'Link detected:' in line:
				if "yes" in line:
					self.LinkState = True
				else:
					self.LinkState = False
		if self.LinkState:
			iNetwork.checkNetworkState(self.checkNetworkCB)
		else:
			self["statuspic"].setPixmapNum(1)
			self["statuspic"].show()

	def checkNetworkCB(self, data):
		try:
			if iNetwork.getAdapterAttribute(self.iface, "up") is True:
				if self.LinkState is True:
					if data <= 2:
						self["statuspic"].setPixmapNum(0)
					else:
						self["statuspic"].setPixmapNum(1)
				else:
					self["statuspic"].setPixmapNum(1)
			else:
				self["statuspic"].setPixmapNum(1)
			self["statuspic"].show()
		except:
			pass

	def doNothing(self):
		pass


class SystemMemoryInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		screentitle = _("Memory")
		title = screentitle
		Screen.setTitle(self, title)
		self.skinName = ["SystemMemoryInfo", "About"]
		self["AboutScrollLabel"] = ScrollLabel()
		self["key_red"] = Button(_("Close"))
		self["actions"] = ActionMap(["SetupActions", "ColorActionsAbout"], {
			"cancel": self.close,
			"ok": self.close,
			"red": self.close
		})

		out_lines = open("/proc/meminfo").readlines()
		self.AboutText = _("RAM") + '\n\n'
		RamTotal = "-"
		RamFree = "-"
		for lidx in range(len(out_lines) - 1):
			tstLine = out_lines[lidx].split()
			if "MemTotal:" in tstLine:
				MemTotal = out_lines[lidx].split()
				self.AboutText += _("Total memory:") + "\t" + MemTotal[1] + "\n"
			if "MemFree:" in tstLine:
				MemFree = out_lines[lidx].split()
				self.AboutText += _("Free memory:") + "\t" + MemFree[1] + "\n"
			if "Buffers:" in tstLine:
				Buffers = out_lines[lidx].split()
				self.AboutText += _("Buffers:") + "\t" + Buffers[1] + "\n"
			if "Cached:" in tstLine:
				Cached = out_lines[lidx].split()
				self.AboutText += _("Cached:") + "\t" + Cached[1] + "\n"
			if "SwapTotal:" in tstLine:
				SwapTotal = out_lines[lidx].split()
				self.AboutText += _("Total swap:") + "\t" + SwapTotal[1] + "\n"
			if "SwapFree:" in tstLine:
				SwapFree = out_lines[lidx].split()
				self.AboutText += _("Free swap:") + "\t" + SwapFree[1] + "\n\n"

		self["actions"].setEnabled(False)
		self.Console = Console()
		self.Console.ePopen("df -mh / | grep -v '^Filesystem'", self.Stage1Complete2)

	def Stage1Complete2(self, result, retval, extra_args=None):
		flash = str(result).replace('\n', '')
		flash = flash.split()
		RamTotal = flash[1]
		RamFree = flash[3]

		self.AboutText += _("Total:") + "\t" + RamTotal + "\n"
		self.AboutText += _("Free:") + "\t" + RamFree + "\n\n"

		self["AboutScrollLabel"].setText(self.AboutText)
		self["actions"].setEnabled(True)

	def doNothing(self):
		pass


class TranslationInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Translation"))
		# don't remove the string out of the _(), or it can't be "translated" anymore.

		# TRANSLATORS: Add here whatever should be shown in the "translator" about screen, up to 6 lines (use \n for newline)
		info = _("TRANSLATOR_INFO")

		if info == "TRANSLATOR_INFO":
			info = "(N/A)"

		infolines = _("").split("\n")
		infomap = {}
		for x in infolines:
			data = x.split(': ')
			if len(data) != 2:
				continue
			(type, value) = data
			infomap[type] = value
		print("[About] DEBUG: infomap=%s" % str(infomap))

		self["key_red"] = Button(_("Cancel"))
		self["TranslationInfo"] = StaticText(info)

		translator_name = infomap.get("Language-Team", "none")
		if translator_name == "none":
			translator_name = infomap.get("Last-Translator", "")

		self["TranslatorName"] = StaticText(translator_name)

		self["actions"] = ActionMap(["SetupActions"], {
			"cancel": self.close,
			"ok": self.close
		})


class CommitInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Latest Commits"))
		self.skinName = ["CommitInfo", "About"]
		self["AboutScrollLabel"] = ScrollLabel(_("Please wait"))
		self["actions"] = ActionMap(["SetupActions", "DirectionActions"], {
			"cancel": self.close,
			"ok": self.close,
			"up": self["AboutScrollLabel"].pageUp,
			"down": self["AboutScrollLabel"].pageDown,
			"left": self.left,
			"right": self.right
		})

		self["key_red"] = Button(_("Cancel"))

		# get the branch to display from the Enigma version
		try:
			branch = "?sha=" + "-".join(about.getEnigmaVersionString().split("-")[3:])
		except:
			branch = ""
		branch_e2plugins = "?sha=python3"

		self.project = 0
		self.projects = [
			("https://api.github.com/repos/68foxboris/my-py3/commits" + branch, "Enigma2", API_GITHUB),
			("https://api.github.com/repos/openpli/openpli-oe-core/commits" + branch, "Openpli Oe Core", API_GITHUB),
			("https://api.github.com/repos/openpli/enigma2-plugins/commits" + branch_e2plugins, "Enigma2 Plugins", API_GITHUB),
			("https://api.github.com/repos/openpli/aio-grab/commits", "Aio Grab", API_GITHUB),
			("https://api.github.com/repos/openpli/enigma2-plugin-extensions-epgimport/commits", "Plugin EPGImport", API_GITHUB),
			("https://api.github.com/repos/littlesat/skin-PLiHD/commits", "Skin PLi HD", API_GITHUB),
			("https://api.github.com/repos/E2OpenPlugins/e2openplugin-OpenWebif/commits", "OpenWebif", API_GITHUB),
			("https://gitlab.openpli.org/api/v4/projects/5/repository/commits", "Hans settings", API_GITLAB)
		]
		self.cachedProjects = {}
		self.Timer = eTimer()
		self.Timer.callback.append(self.readGithubCommitLogs)
		self.Timer.start(50, True)

	def readGithubCommitLogs(self):
		url = self.projects[self.project][0]
		commitlog = ""
		from datetime import datetime
		from json import loads
		from urllib.request import urlopen
		try:
			commitlog += 80 * '-' + '\n'
			commitlog += url.split('/')[-2] + '\n'
			commitlog += 80 * '-' + '\n'
			try:
				# OpenPli 5.0 uses python 2.7.11 and here we need to bypass the certificate check
				from ssl import _create_unverified_context
				log = loads(urlopen(url, timeout=5, context=_create_unverified_context()).read())
			except:
				log = loads(urlopen(url, timeout=5).read())

			if self.projects[self.project][2] == API_GITHUB:
				for c in log:
					creator = c['commit']['author']['name']
					title = c['commit']['message']
					date = datetime.strptime(c['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%x %X')
					commitlog += date + ' ' + creator + '\n' + title + 2 * '\n'
			elif self.projects[self.project][2] == API_GITLAB:
				for c in log:
					creator = c['author_name']
					title = c['title']
					date = datetime.strptime(c['committed_date'], '%Y-%m-%dT%H:%M:%S.000%z').strftime('%x %X')
					commitlog += date + ' ' + creator + '\n' + title + 2 * '\n'

			self.cachedProjects[self.projects[self.project][1]] = commitlog
		except Exception as e:
			commitlog += _("Currently the commit log cannot be retrieved - please try later again.")
		self["AboutScrollLabel"].setText(commitlog)

	def updateCommitLogs(self):
		if self.projects[self.project][1] in self.cachedProjects:
			self["AboutScrollLabel"].setText(self.cachedProjects[self.projects[self.project][1]])
		else:
			self["AboutScrollLabel"].setText(_("Please wait"))
			self.Timer.start(50, True)

	def left(self):
		self.project = self.project == 0 and len(self.projects) - 1 or self.project - 1
		self.updateCommitLogs()

	def right(self):
		self.project = self.project != len(self.projects) - 1 and self.project + 1 or 0
		self.updateCommitLogs()

	def doNothing(self):
		pass


class MemoryInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)

		self["actions"] = ActionMap(["SetupActions", "ColorActionsAbout"], {
			"cancel": self.close,
			"ok": self.getMemoryInfo,
			"green": self.getMemoryInfo,
			"blue": self.clearMemory
		})

		self["key_red"] = Label(_("Cancel"))
		self["key_green"] = Label(_("Refresh"))
		self["key_blue"] = Label(_("Clear"))
		self['lmemtext'] = Label()
		self['lmemvalue'] = Label()
		self['rmemtext'] = Label()
		self['rmemvalue'] = Label()
		self['pfree'] = Label()
		self['pused'] = Label()
		self["slide"] = ProgressBar()
		self["slide"].setValue(100)

		self["params"] = MemoryInfoSkinParams()

		self['info'] = Label(_("This info is for developers only.\nFor normal users it is not relevant.\nPlease don't panic if you see values displayed looking suspicious!"))

		self.setTitle(_("Memory Info"))
		self.onLayoutFinish.append(self.getMemoryInfo)

	def getMemoryInfo(self):
		try:
			ltext = rtext = ""
			lvalue = rvalue = ""
			mem = 1
			free = 0
			rows_in_column = self["params"].rows_in_column
			for i, line in enumerate(open('/proc/meminfo', 'r')):
				s = line.strip().split(None, 2)
				if len(s) == 3:
					name, size, units = s
				elif len(s) == 2:
					name, size = s
					units = ""
				else:
					continue
				if name.startswith("MemTotal"):
					mem = int(size)
				if name.startswith("MemFree") or name.startswith("Buffers") or name.startswith("Cached"):
					free += int(size)
				if i < rows_in_column:
					ltext += "".join((name, "\n"))
					lvalue += "".join((size, " ", units, "\n"))
				else:
					rtext += "".join((name, "\n"))
					rvalue += "".join((size, " ", units, "\n"))
			self['lmemtext'].setText(ltext)
			self['lmemvalue'].setText(lvalue)
			self['rmemtext'].setText(rtext)
			self['rmemvalue'].setText(rvalue)
			self["slide"].setValue(int(100.0 * (mem - free) / mem + 0.25))
			self['pfree'].setText("%.1f %s" % (100. * free / mem, '%'))
			self['pused'].setText("%.1f %s" % (100. * (mem - free) / mem, '%'))
		except Exception as e:
			print("[About] getMemoryInfo FAIL:", e)

	def clearMemory(self):
		eConsoleAppContainer().execute("sync")
		open("/proc/sys/vm/drop_caches", "w").write("3")
		self.getMemoryInfo()


class MemoryInfoSkinParams(GUIComponent):
	def __init__(self):
		GUIComponent.__init__(self)
		self.rows_in_column = 25

	def applySkin(self, desktop, screen):
		if self.skinAttributes != None:
			attribs = []
			for (attrib, value) in self.skinAttributes:
				if attrib == "rowsincolumn":
					self.rows_in_column = int(value)
			self.skinAttributes = attribs
			applySkin = GUIComponent
		return applySkin()

	GUI_WIDGET = eLabel


class Troubleshoot(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Troubleshoot"))
		self["AboutScrollLabel"] = ScrollLabel(_("Please wait"))
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = Button()

		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActionsAbout"], {
			"cancel": self.close,
			"up": self["AboutScrollLabel"].pageUp,
			"down": self["AboutScrollLabel"].pageDown,
			"moveUp": self["AboutScrollLabel"].homePage,
			"moveDown": self["AboutScrollLabel"].endPage,
			"left": self.left,
			"right": self.right,
			"red": self.red,
			"green": self.green
		})

		self.container = eConsoleAppContainer()
		self.container.appClosed.append(self.appClosed)
		self.container.dataAvail.append(self.dataAvail)
		self.commandIndex = 0
		self.updateOptions()
		self.onLayoutFinish.append(self.run_console)

	def left(self):
		self.commandIndex = (self.commandIndex - 1) % len(self.commands)
		self.updateKeys()
		self.run_console()

	def right(self):
		self.commandIndex = (self.commandIndex + 1) % len(self.commands)
		self.updateKeys()
		self.run_console()

	def red(self):
		if self.commandIndex >= self.numberOfCommands:
			self.session.openWithCallback(self.removeAllLogfiles, MessageBox, _("Do you want to remove all the crash logfiles"), default=False)
		else:
			self.close()

	def green(self):
		if self.commandIndex >= self.numberOfCommands:
			try:
				remove(self.commands[self.commandIndex][4:])
			except:
				pass
			self.updateOptions()
		self.run_console()

	def removeAllLogfiles(self, answer):
		if answer:
			for fileName in self.getLogFilesList():
				try:
					remove(fileName)
				except:
					pass
			self.updateOptions()
			self.run_console()

	def appClosed(self, retval):
		if retval:
			self["AboutScrollLabel"].setText(_("An error occurred - Please try again later"))

	def dataAvail(self, data):
		self["AboutScrollLabel"].appendText(data.decode())

	def run_console(self):
		self["AboutScrollLabel"].setText("")
		self.setTitle("%s - %s" % (_("Troubleshoot"), self.titles[self.commandIndex]))
		command = self.commands[self.commandIndex]
		if command.startswith("cat "):
			try:
				self["AboutScrollLabel"].setText(open(command[4:], "r").read())
			except:
				self["AboutScrollLabel"].setText(_("Logfile does not exist anymore"))
		else:
			try:
				if self.container.execute(command):
					raise Exception("failed to execute: " + command)
			except Exception as e:
				self["AboutScrollLabel"].setText("%s\n%s" % (_("An error occurred - Please try again later"), e))

	def cancel(self):
		self.container.appClosed.remove(self.appClosed)
		self.container.dataAvail.remove(self.dataAvail)
		self.container = None
		self.close()

	def getDebugFilesList(self):
		import glob
		return [x for x in sorted(glob.glob("/home/root/logs/enigma2_debug_*.log"), key=lambda x: isfile(x) and getmtime(x))]

	def getLogFilesList(self):
		import glob
		home_root = "/home/root/logs/enigma2_crash.log"
		tmp = "/tmp/enigma2_crash.log"
		return [x for x in sorted(glob.glob("/mnt/hdd/*.log"), key=lambda x: isfile(x) and getmtime(x))] + (isfile(home_root) and [home_root] or []) + (isfile(tmp) and [tmp] or [])

	def updateOptions(self):
		self.titles = ["dmesg", "ifconfig", "df", "top", "ps", "messages"]
		self.commands = ["dmesg", "ifconfig", "df -h", "top -n 1", "ps -l", "cat /var/volatile/log/messages"]
		install_log = "/home/root/autoinstall.log"
		if isfile(install_log):
				self.titles.append("%s" % install_log)
				self.commands.append("cat %s" % install_log)
		self.numberOfCommands = len(self.commands)
		fileNames = self.getLogFilesList()
		if fileNames:
			totalNumberOfLogfiles = len(fileNames)
			logfileCounter = 1
			for fileName in reversed(fileNames):
				self.titles.append("logfile %s (%s/%s)" % (fileName, logfileCounter, totalNumberOfLogfiles))
				self.commands.append("cat %s" % (fileName))
				logfileCounter += 1
		fileNames = self.getDebugFilesList()
		if fileNames:
			totalNumberOfLogfiles = len(fileNames)
			logfileCounter = 1
			for fileName in reversed(fileNames):
				self.titles.append("debug log %s (%s/%s)" % (fileName, logfileCounter, totalNumberOfLogfiles))
				self.commands.append("tail -n 2500 %s" % (fileName))
				logfileCounter += 1
		self.commandIndex = min(len(self.commands) - 1, self.commandIndex)
		self.updateKeys()

	def updateKeys(self):
		self["key_red"].setText(_("Cancel") if self.commandIndex < self.numberOfCommands else _("Remove all logfiles"))
		self["key_green"].setText(_("Refresh") if self.commandIndex < self.numberOfCommands else _("Remove this logfile"))
	def doNothing(self):
		pass
