from enigma import eConsoleAppContainer, eDVBResourceManager, eGetEnigmaDebugLvl, eLabel, eTimer, getDesktop, ePoint, eSize
from os import listdir, popen, remove, statvfs
from os.path import getmtime, isfile, isdir, join as pathjoin, join, basename
from datetime import datetime
from glob import glob
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

from Tools.Directories import SCOPE_PLUGINS, resolveFilename, fileExists, fileHas, pathExists, fileReadLine, fileReadLines, fileWriteLine, isPluginInstalled
from Tools.Geolocation import geolocation
from Tools.StbHardware import getFPVersion, getProcInfoTypeTuner, getBoxProc, getBoxRCType
from Tools.LoadPixmap import LoadPixmap
from Tools.Conversions import scaleNumber, formatDate
from time import localtime, strftime, strptime

MODULE_NAME = __name__.split(".")[-1]

API_GITHUB = 0
API_GITLAB = 1

model = BoxInfo.getItem("model")
brand = BoxInfo.getItem("brand")
socfamily = BoxInfo.getItem("socfamily")
displaytype = BoxInfo.getItem("displaytype")
platform = BoxInfo.getItem("platform")
DISPLAY_BRAND = BoxInfo.getItem("displaybrand")
DISPLAY_MODEL = BoxInfo.getItem("displaymodel")

rcname = BoxInfo.getItem("rcname")
procModel = getBoxProc()
fpVersion = getFPVersion()

MODULE_NAME = __name__.split(".")[-1]

INFO_COLORS = ["N", "H", "P", "V", "M"]
INFO_COLOR = {
	"B": None,
	"N": 0x00ffffff,  # Normal.
	"H": 0x00ffffff,  # Headings.
	"P": 0x00cccccc,  # Prompts.
	"V": 0x00cccccc,  # Values.
	"M": 0x00ffff00  # Messages.
}
LOG_MAX_LINES = 10000  # Maximum number of log lines to be displayed on screen.
AUTO_REFRESH_TIME = 5000  # Streaming auto refresh timer (in milliseconds).


def getTypeTuner():
	typetuner = {
		"00": _("OTT Model"),
		"10": _("Single"),
		"11": _("Twin"),
		"12": _("Combo"),
		"21": _("Twin Hybrid"),
		"22": _("Single Hybrid")
	}


def getBoxProcTypeName():
	boxProcTypes = {
		"00": _("OTT"),
		"10": _("Single Tuner"),
		"11": _("Twin Tuner"),
		"12": _("Combo Tuner"),
		"21": _("Twin Hybrid"),
		"22": _("Hybrid Tuner")
	}
	if procType == "unknown":
		return _("Unknown")
	return "%s - %s" % (procType, boxProcTypes.get(procType, _("Unknown")))


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
		colon = "" if styleLen > 0 and style[0] in ("M", "P", "V") else ":"
		return "%s%s%s%s%s" % (leftIndent, leftStartColor, left, colon, leftEndColor)
	return "%s%s%s:%s|%s%s%s%s" % (leftIndent, leftStartColor, left, leftEndColor, rightIndent, rightStartColor, right, rightEndColor)


class CommitInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Commit Log Information"))
		self.baseTitle = _("Commit Log")
		self.skinName.insert(0, "CommitInformation")
		self["key_menu"] = StaticText(_("MENU"))
		self["key_yellow"] = StaticText(_("Previous Log"))
		self["key_blue"] = StaticText(_("Next Log"))
		self["commitActions"] = HelpableActionMap(self, ["MenuActions", "ColorActions", "NavigationActions"], {
			"menu": (self.showCommitMenu, _("Show selection menu for commit logs")),
			"yellow": (self.previousCommitLog, _("Show previous commit log")),
			"blue": (self.nextCommitLog, _("Show next commit log")),
			"left": (self.previousCommitLog, _("Show previous commit log")),
			"right": (self.nextCommitLog, _("Show next commit log"))
		}, prio=0, description=_("Commit Information Actions"))
		self.commitLogs = BoxInfo.getItem("InformationCommitLogs", [("Unavailable", None)])
		self.commitLogIndex = 0
		self.commitLogMax = len(self.commitLogs)
		self.cachedCommitInfo = {}

	def showCommitMenu(self):
		choices = [(commitLog[0], index) for index, commitLog in enumerate(self.commitLogs)]
		self.session.openWithCallback(self.showCommitMenuCallBack, MessageBox, text=_("Select a repository commit log to view:"), list=choices, windowTitle=self.baseTitle)

	def showCommitMenuCallBack(self, selectedIndex):
		if isinstance(selectedIndex, int):
			self.commitLogIndex = selectedIndex
			self.displayInformation()
			self.informationTimer.start(25)

	def previousCommitLog(self):
		self.commitLogIndex = (self.commitLogIndex - 1) % self.commitLogMax
		self.displayInformation()
		self.informationTimer.start(25)

	def nextCommitLog(self):
		self.commitLogIndex = (self.commitLogIndex + 1) % self.commitLogMax
		self.displayInformation()
		self.informationTimer.start(25)

	def fetchInformation(self):  # Should we limit the number of fetches per minute?
		self.informationTimer.stop()
		name = self.commitLogs[self.commitLogIndex][0]
		url = self.commitLogs[self.commitLogIndex][1]
		if url is None:
			info = [_("There are no repositories defined so commit logs are unavailable!")]
		else:
			try:
				log = []
				with urlopen(url, timeout=10) as fd:
					log = loads(fd.read())
				info = []
				for data in log:
					date = datetime.strptime(data["commit"]["committer"]["date"], "%Y-%m-%dT%H:%M:%SZ").strftime("%s %s" % (config.usage.date.daylong.value, config.usage.time.long.value))
					author = data["commit"]["author"]["name"]
					# committer = data["commit"]["committer"]["name"]
					message = [x.rstrip() for x in data["commit"]["message"].split("\n")]
					if info:
						info.append("")
					# info.append(_("Date: %s   Author: %s   Commit by: %s") % (date, author, committer))
					info.append(_("Date: %s   Author: %s") % (date, author))
					info.extend(message)
				if not info:
					info = [_("The '%s' commit log contains no information.") % name]
			except Exception as err:
				info = str(err)
		self.cachedCommitInfo[name] = info
		for callback in self.onInformationUpdated:
			callback()

	def refreshInformation(self):  # Should we limit the number of fetches per minute?
		self.cachedCommitInfo = {}
		InformationBase.refreshInformation(self)

	def displayInformation(self):
		name = self.commitLogs[self.commitLogIndex][0]
		self.setTitle("%s: %s" % (self.baseTitle, name))
		self["key_yellow"].setText(self.commitLogs[(self.commitLogIndex - 1) % self.commitLogMax][0])
		self["key_blue"].setText(self.commitLogs[(self.commitLogIndex + 1) % self.commitLogMax][0])
		if name in self.cachedCommitInfo:
			info = self.cachedCommitInfo[name]
			if isinstance(info, str):
				err = info
				info = []
				info.append(_("Error '%s' encountered retrieving the '%s' commit log!") % (err, name))
				info.append("")
				info.append(_("The '%s' commit log can't be retrieved, please try again later.") % name)
				info.append("")
				info.append(_("(Access to the '%s' commit log requires an Internet connection.)") % name)
		else:
			info = [_("Retrieving '%s' commit log, please wait...") % name]
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "Commit Log Information"


class GeolocationInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Geolocation Information"))
		self.skinName.insert(0, "GeolocationInformation")

	def displayInformation(self):
		info = []
		geolocationData = geolocation.getGeolocationData(fields="continent,country,regionName,city,lat,lon,timezone,currency,isp,org,mobile,proxy,query", useCache=False)
		if geolocationData.get("status", None) == "success":
			info.append(formatLine("H", _("Location information")))
			info.append("")
			continent = geolocationData.get("continent", None)
			if continent:
				info.append(formatLine("P1", _("Continent"), continent))
			country = geolocationData.get("country", None)
			if country:
				info.append(formatLine("P1", _("Country"), country))
			state = geolocationData.get("regionName", None)
			if state:
				info.append(formatLine("P1", _("State"), state))
			city = geolocationData.get("city", None)
			if city:
				info.append(formatLine("P1", _("City"), city))
			latitude = geolocationData.get("lat", None)
			if latitude:
				info.append(formatLine("P1", _("Latitude"), latitude))
			longitude = geolocationData.get("lon", None)
			if longitude:
				info.append(formatLine("P1", _("Longitude"), longitude))
			info.append("")
			info.append(formatLine("H", _("Local information")))
			info.append("")
			timezone = geolocationData.get("timezone", None)
			if timezone:
				info.append(formatLine("P1", _("Timezone"), timezone))
			currency = geolocationData.get("currency", None)
			if currency:
				info.append(formatLine("P1", _("Currency"), currency))
			info.append("")
			info.append(formatLine("H", _("Connection information")))
			info.append("")
			isp = geolocationData.get("isp", None)
			if isp:
				ispOrg = geolocationData.get("org", None)
				if ispOrg:
					info.append(formatLine("P1", _("ISP"), "%s  (%s)" % (isp, ispOrg)))
				else:
					info.append(formatLine("P1", _("ISP"), isp))
			mobile = geolocationData.get("mobile", None)
			info.append(formatLine("P1", _("Mobile connection"), (_("Yes") if mobile else _("No"))))
			proxy = geolocationData.get("proxy", False)
			info.append(formatLine("P1", _("Proxy detected"), (_("Yes") if proxy else _("No"))))
			publicIp = geolocationData.get("query", None)
			if publicIp:
				info.append(formatLine("P1", _("Public IP"), publicIp))
		else:
			info.append(_("Geolocation information cannot be retrieved, please try again later."))
			info.append("")
			info.append(_("Access to geolocation information requires an internet connection."))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "Geolocation Information"


class DebugInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Debug Log Information"))
		self.baseTitle = _("Log")
		self.skinName.insert(0, "DebugInformation")
		self["key_menu"] = StaticText()
		self["key_info"] = StaticText(_("INFO"))
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["debugActions"] = HelpableActionMap(self, ["MenuActions", "InfoActions", "ColorActions", "NavigationActions"], {
			"menu": (self.showLogMenu, _("Show selection menu for debug log files")),
			"info": (self.showLogSettings, _("Show the Logs Settings screen")),
			"yellow": (self.deleteLog, _("Delete the currently displayed log file")),
			"blue": (self.deleteAllLogs, _("Delete all log files")),
			"left": (self.previousDebugLog, _("Show previous debug log file")),
			"right": (self.nextDebugLog, _("Show next debug log file"))
		}, prio=0, description=_("Debug Log Information Actions"))
		self["debugActions"].setEnabled(False)
		self.debugLogs = []
		self.debugLogIndex = 0
		self.debugLogMax = 0
		self.cachedDebugInfo = {}

	def showLogMenu(self):
		choices = [(_("Log file: '%s'  (%s)") % (debugLog[0], debugLog[1]), index) for index, debugLog in enumerate(self.debugLogs)]
		self.session.openWithCallback(self.showLogMenuCallBack, MessageBox, text=_("Select a debug log file to view:"), list=choices, default=self.debugLogIndex, windowTitle=self.baseTitle)

	def showLogMenuCallBack(self, selectedIndex):
		if isinstance(selectedIndex, int):
			self.debugLogIndex = selectedIndex
			self.displayInformation()
			self.informationTimer.start(25)

	def showLogSettings(self):
		self.setTitle(_("Debug Log Information"))
		self.session.openWithCallback(self.showLogSettingsCallback, Setup, "Logs")

	def showLogSettingsCallback(self, *retVal):
		if retVal and retVal[0]:
			self.close(True)

	def deleteLog(self):
		name, sequence, path = self.debugLogs[self.debugLogIndex]
		self.session.openWithCallback(self.deleteLogCallback, MessageBox, "%s\n\n%s" % (_("Log file: '%s'  (%s)") % (name, sequence), _("Do you want to delete this log file?")), default=False)

	def deleteLogCallback(self, answer):
		if answer:
			name, sequence, path = self.debugLogs[self.debugLogIndex]
			try:
				remove(path)
				del self.cachedDebugInfo[path]
				self.session.open(MessageBox, _("Log file '%s' deleted.") % name, type=MessageBox.TYPE_INFO, timeout=5, close_on_any_key=True, windowTitle=self.baseTitle)
				self.debugLogs = []
			except OSError as err:
				self.session.open(MessageBox, _("Error %d: Log file '%s' not deleted!  (%s)") % (err.errno, name, err.strerror), type=MessageBox.TYPE_ERROR, timeout=5, windowTitle=self.baseTitle)
			self.informationTimer.start(25)

	def deleteAllLogs(self):
		self.session.openWithCallback(self.deleteAllLogsCallback, MessageBox, _("Do you want to delete all the log files?"), default=False)

	def deleteAllLogsCallback(self, answer):
		if answer:
			log = []
			type = MessageBox.TYPE_INFO
			close = True
			for name, sequence, path in self.debugLogs:
				try:
					remove(path)
					log.append(((_("Log file '%s' deleted.") % name), None))
				except OSError as err:
					type = MessageBox.TYPE_ERROR
					close = False
					log.append(((_("Error %d: Log file '%s' not deleted!  (%s)") % (err.errno, name, err.strerror)), None))
			self.session.open(MessageBox, _("Results of the delete all logs:"), type=type, list=log, timeout=5, close_on_any_key=close, windowTitle=self.baseTitle)
			self.debugLogs = []
			self.cachedDebugInfo = {}
			self.informationTimer.start(25)

	def previousDebugLog(self):
		self.debugLogIndex = (self.debugLogIndex - 1) % self.debugLogMax
		self.displayInformation()
		self.informationTimer.start(25)

	def nextDebugLog(self):
		self.debugLogIndex = (self.debugLogIndex + 1) % self.debugLogMax
		self.displayInformation()
		self.informationTimer.start(25)

	def fetchInformation(self):
		self.informationTimer.stop()
		if not self.debugLogs:
			self.debugLogs = self.findLogFiles()
			self.debugLogIndex = 0
			self.debugLogMax = len(self.debugLogs)
		if self.debugLogs:
			self["key_menu"].setText(_("MENU"))
			self["key_yellow"].setText(_("Delete log"))
			self["key_blue"].setText(_("Delete all logs"))
			self["debugActions"].setEnabled(True)
			name, sequence, path = self.debugLogs[self.debugLogIndex]
			if path in self.cachedDebugInfo:
				info = self.cachedDebugInfo[path]
			else:
				try:
					with open(path, "r") as fd:
						info = [x.strip() for x in fd.readlines()][-LOG_MAX_LINES:]
				except OSError as err:
					info = "%s,%s" % (err.errno, err.strerror)
			self.cachedDebugInfo[path] = info
		else:
			self["key_menu"].setText("")
			self["key_yellow"].setText("")
			self["key_blue"].setText("")
			self["debugActions"].setEnabled(False)
			name = "Unavailable"
			self.debugLogs = [(name, name, name)]
			self.cachedDebugInfo[name] = "0,%s" % _("No log files found so debug logs are unavailable!")
		for callback in self.onInformationUpdated:
			callback()

	def findLogFiles(self):
		debugLogs = []
		installLog = "/home/root/autoinstall.log"
		if isfile(installLog):
			debugLogs.append((_("Auto install log"), _("Install 1/1"), installLog))
		crashLog = "/tmp/enigma2_crash.log"
		if isfile(crashLog):
			debugLogs.append((_("Current crash log"), _("Current 1/1"), crashLog))
		paths = [x for x in sorted(glob("/mnt/hdd/*.log"), key=lambda x: isfile(x) and getmtime(x))]
		if paths:
			countLogs = len(paths)
			for index, path in enumerate(reversed(paths)):
				debugLogs.append((basename(path), _("Log %d/%d") % (index + 1, countLogs), path))
		logPath = config.crash.debug_path.value
		paths = [x for x in sorted(glob(join(logPath, "*-enigma2-crash.log")), key=lambda x: isfile(x) and getmtime(x))]
		paths += [x for x in sorted(glob(join(logPath, "enigma2_crash*.log")), key=lambda x: isfile(x) and getmtime(x))]
		if paths:
			countLogs = len(paths)
			for index, path in enumerate(reversed(paths)):
				debugLogs.append((basename(path), _("Crash %d/%d") % (index + 1, countLogs), path))
		paths = [x for x in sorted(glob(join(logPath, "*-enigma2-debug.log")), key=lambda x: isfile(x) and getmtime(x))]
		paths += [x for x in sorted(glob(join(logPath, "Enigma2-debug*.log")), key=lambda x: isfile(x) and getmtime(x))]
		if paths:
			countLogs = len(paths)
			for index, path in enumerate(reversed(paths)):
				debugLogs.append((basename(path), _("Debug %d/%d") % (index + 1, countLogs), path))
		return debugLogs

	def refreshInformation(self):  # Should we limit the number of fetches per minute?
		self.debugLogs = []
		self.debugLogIndex = 0
		self.cachedDebugInfo = {}
		InformationBase.refreshInformation(self)

	def displayInformation(self):
		if self.debugLogs:
			name, sequence, path = self.debugLogs[self.debugLogIndex]
			self.setTitle(_("Debug Log Information") if sequence == "Unavailable" else "%s: '%s' (%s)" % (self.baseTitle, name, sequence))
			if path in self.cachedDebugInfo:
				info = self.cachedDebugInfo[path]
				if isinstance(info, str):
					errno, strerror = info.split(",", 1)
					info = []
					if errno == "0":
						info.append(strerror)
					else:
						info.append(_("Error %s: Unable to retrieve the '%s' file!  (%s)") % (errno, path, strerror))
						info.append("")
						info.append(_("The '%s' file can't be retrieved, please try again later.") % path)
			else:
				info = [_("Retrieving '%s' log, please wait...") % name]
		else:
			info = [_("Finding available log files, please wait...")]


		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "Debug Log Information"


class ImageInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("OpenPli Information"))
		self.skinName.insert(0, "ImageInformation")
		self["key_yellow"] = StaticText(_("Commit Logs"))
		self["key_blue"] = StaticText(_("Translation"))
		self["receiverActions"] = HelpableActionMap(self, ["ColorActions"], {
			"yellow": (self.showCommitLogs, _("Show latest commit log information")),
			"blue": (self.showTranslation, _("Show translation information"))
		}, prio=0, description=_("OpenPli Information Actions"))
		self.copyright = str("\xc2\xb0")
		self.resolutions = {
			480: _("NTSC"),
			576: _("PAL"),
			720: _("HD"),
			1080: _("FHD"),
			2160: _("4K"),
			4320: _("8K"),
			8640: _("16K")
		}

	def showCommitLogs(self):
		self.session.openWithCallback(self.informationWindowClosed, CommitInformation)

	def showTranslation(self):
		self.session.openWithCallback(self.informationWindowClosed, TranslationInformation)

	def displayInformation(self):
		info = []
		info.append(formatLine("P1", _("Soft MultiBoot"), _("Yes") if BoxInfo.getItem("multiboot", False) else _("No")))
		info.append(formatLine("P1", _("Flash type"), about.getFlashType()))
		xResolution = getDesktop(0).size().width()
		yResolution = getDesktop(0).size().height()
		info.append(formatLine("P1", _("Skin & Resolution"), "%s  (%s  -  %s x %s)" % (config.skin.primary_skin.value.split('/')[0], self.resolutions.get(yResolution, "Unknown"), xResolution, yResolution)))
		info.append("")
		info.append(formatLine("H", _("Enigma2 information")))
		info.append("")
		enigmaVersion = about.getEnigmaVersionString()
		enigmaVersion = enigmaVersion.rsplit("-", enigmaVersion.count("-") - 2)
		if len(enigmaVersion) == 3:
			enigmaVersion = "%s (%s-%s)" % (enigmaVersion[0], enigmaVersion[2], enigmaVersion[1].capitalize())
		else:
			enigmaVersion = "%s (%s)" % (enigmaVersion[0], enigmaVersion[1].capitalize())
		info.append(formatLine("P1", _("Enigma2 version"), enigmaVersion))
		compiledate = str(BoxInfo.getItem("compiledate"))
		info.append(formatLine("P1", _("Last update"), formatDate("%s%s%s" % (compiledate[:4], compiledate[4:6], compiledate[6:]))))
		info.append(formatLine("P1", _("Enigma2 (re)starts"), config.misc.startCounter.value))
		info.append(formatLine("P1", _("Enigma2 debug level"), eGetEnigmaDebugLvl()))
		if isPluginInstalled("ServiceHisilicon") and not isPluginInstalled("ServiceMP3"):
			mediaService = "ServiceHisilicon"
		elif isPluginInstalled("ServiceMP3") and not isPluginInstalled("ServiceHisilicon"):
			mediaService = "ServiceMP3"
		else:
			mediaService = _("Unknown")
		info.append(formatLine("P1", _("Media service player"), "%s") % mediaService)
		if isPluginInstalled("ServiceApp"):
			extraService = "ServiceApp"
			info.append(formatLine("P1", _("Extra service player"), "%s") % extraService)
		info.append("")
		info.append(formatLine("H", _("Software information")))
		info.append("")
		info.append(formatLine("P1", _("GCC version"), about.getGccVersion()))
		info.append(formatLine("P1", _("Glibc version"), about.getGlibcVersion()))
		info.append(formatLine("P1", _("OpenSSL version"), about.getopensslVersionString()))
		info.append(formatLine("P1", _("Python version"), about.getPythonVersionString()))
		info.append(formatLine("P1", _("GStreamer version"), about.getGStreamerVersionString().replace("GStreamer ", "")))
		info.append(formatLine("P1", _("FFmpeg version"), about.getFFmpegVersionString()))
		bootId = fileReadLine("/proc/sys/kernel/random/boot_id", source=MODULE_NAME)
		if bootId:
			info.append(formatLine("P1", _("Boot ID"), bootId))
		uuId = fileReadLine("/proc/sys/kernel/random/uuid", source=MODULE_NAME)
		if uuId:
			info.append(formatLine("P1", _("UUID"), uuId))
		info.append("")
		if BoxInfo.getItem("HiSilicon"):
			info.append("")
			info.append(formatLine("H", _("HiSilicon specific information")))
			info.append("")
			process = Popen(("/usr/bin/opkg", "list-installed"), stdout=PIPE, stderr=PIPE, universal_newlines=True)
			stdout, stderr = process.communicate()
			if process.returncode == 0:
				missing = True
				packageList = stdout.split("\n")
				revision = self.findPackageRevision("grab", packageList)
				if revision and revision != "r0":
					info.append(formatLine("P1", _("Grab"), revision))
					missing = False
				revision = self.findPackageRevision("hihalt", packageList)
				if revision:
					info.append(formatLine("P1", _("Halt"), revision))
					missing = False
				revision = self.findPackageRevision("libs", packageList)
				if revision:
					info.append(formatLine("P1", _("Libs"), revision))
					missing = False
				revision = self.findPackageRevision("partitions", packageList)
				if revision:
					info.append(formatLine("P1", _("Partitions"), revision))
					missing = False
				revision = self.findPackageRevision("reader", packageList)
				if revision:
					info.append(formatLine("P1", _("Reader"), revision))
					missing = False
				revision = self.findPackageRevision("showiframe", packageList)
				if revision:
					info.append(formatLine("P1", _("Showiframe"), revision))
					missing = False
				if missing:
					info.append(formatLine("P1", _("HiSilicon specific information not found.")))
			else:
				info.append(formatLine("P1", _("Package information currently not available!")))
		self["information"].setText("\n".join(info))

	def findPackageRevision(self, package, packageList):
		revision = None
		data = [x for x in packageList if "-%s" % package in x]
		if data:
			data = data[0].split("-")
			if len(data) >= 4:
				revision = data[3]
		return revision

	def getSummaryInformation(self):
		return "OpenPli Information"


class MemoryInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Memory Information"))
		self.skinName.insert(0, "MemoryInformation")
		self["clearActions"] = HelpableActionMap(self, ["ColorActions"], {
			"yellow": (self.clearMemoryInformation, _("Clear the virtual memory caches"))
		}, prio=0, description=_("Memory Information Actions"))
		self["key_yellow"] = StaticText(_("Clear"))

	def displayInformation(self):
		info = []
		memInfo = fileReadLines("/proc/meminfo", source=MODULE_NAME)
		info.append(formatLine("H", _("RAM (Summary)")))
		info.append("")
		for line in memInfo:
			key, value, units = [x for x in line.split()]
			if key == "MemTotal:":
				info.append(formatLine("P1", _("Total memory"), "%s %s" % (value, units)))
			if key == "MemFree:":
				info.append(formatLine("P1", _("Free memory"), "%s %s" % (value, units)))
			if key == "Buffers:":
				info.append(formatLine("P1", _("Buffers"), "%s %s" % (value, units)))
			if key == "Cached:":
				info.append(formatLine("P1", _("Cached"), "%s %s" % (value, units)))
			if key == "SwapTotal:":
				info.append(formatLine("P1", _("Total swap"), "%s %s" % (value, units)))
			if key == "SwapFree:":
				info.append(formatLine("P1", _("Free swap"), "%s %s" % (value, units)))
		info.append("")
		info.append(formatLine("H", _("FLASH")))
		info.append("")
		stat = statvfs("/")
		diskSize = stat.f_blocks * stat.f_frsize
		diskFree = stat.f_bfree * stat.f_frsize
		diskUsed = diskSize - diskFree
		info.append(formatLine("P1", _("Total flash"), "%s  (%s)" % (scaleNumber(diskSize), scaleNumber(diskSize, "Iec"))))
		info.append(formatLine("P1", _("Used flash"), "%s  (%s)" % (scaleNumber(diskUsed), scaleNumber(diskUsed, "Iec"))))
		info.append(formatLine("P1", _("Free flash"), "%s  (%s)" % (scaleNumber(diskFree), scaleNumber(diskFree, "Iec"))))
		info.append("")
		info.append(formatLine("H", _("RAM (Details)")))
		info.append("")

		for line in memInfo:
			key, value, units = [x for x in line.split()]
			info.append(formatLine("P1", key[:-1], "%s %s" % (value, units)))
		info.append("")
		info.append(formatLine("P1", _("The detailed information is intended for developers only.")))
		info.append(formatLine("P1", _("Please don't panic if you see values that look suspicious.")))
		self["information"].setText("\n".join(info).encode("UTF-8", "ignore") if PY2 else "\n".join(info))

	def clearMemoryInformation(self):
		eConsoleAppContainer().execute(*["/bin/sync", "/bin/sync"])
		fileWriteLine("/proc/sys/vm/drop_caches", "3")
		self.informationTimer.start(25)
		for callback in self.onInformationUpdated:
			callback()

	def getSummaryInformation(self):
		return "Memory Information Data"


class NetworkInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Network Information"))
		self.skinName = ["NetworkInformation", "WlanStatus"]
		self["key_yellow"] = StaticText(_("WAN Geolocation"))
		self["geolocationActions"] = HelpableActionMap(self, ["ColorActions"], {
			"yellow": (self.useGeolocation, _("Use geolocation to get WAN information")),
		}, prio=0, description=_("Network Information Actions"))
		self.interfaceData = {}
		self.geolocationData = []
		self.ifconfigAttributes = {
			"Link encap": "encapsulation",
			"HWaddr": "mac",
			"inet addr": "addr",
			"Bcast": "brdaddr",
			"Mask": "nmask",
			"inet6 addr": "addr6",
			"Scope": "scope",
			"MTU": "mtu",
			"Metric": "metric",
			"RX packets": "rxPackets",
			"rxerrors": "rxErrors",
			"rxdropped": "rxDropped",
			"rxoverruns": "rxOverruns",
			"rxframe": "rxFrame",
			"TX packets": "txPackets",
			"txerrors": "txErrors",
			"txdropped": "txDropped",
			"txoverruns": "txOverruns",
			"collisions": "txCollisions",
			"txqueuelen": "txQueueLen",
			"RX bytes": "rxBytes",
			"TX bytes": "txBytes"
		}
		self.iwconfigAttributes = {
			"interface": "interface",
			"standard": "standard",
			"ESSID": "ssid",
			"Mode": "mode",
			"Frequency": "frequency",
			"Access Point": "accessPoint",
			"Bit Rate": "bitrate",
			"Tx-Power": "transmitPower",
			"Retry short limit": "retryLimit",
			"RTS thr": "rtsThrottle",
			"Fragment thr": "fragThrottle",
			"Encryption key": "encryption",
			"Power Management": "powerManagement",
			"Link Quality": "signalQuality",
			"Signal level": "signalStrength",
			"Rx invalid nwid": "rxInvalidNwid",
			"Rx invalid crypt": "rxInvalidCrypt",
			"Rx invalid frag": "rxInvalidFrag",
			"Tx excessive retries": "txExcessiveReties",
			"Invalid misc": "invalidMisc",
			"Missed beacon": "missedBeacon"
		}
		self.ethtoolAttributes = {
			"Speed": "speed",
			"Duplex": "duplex",
			"Transceiver": "transceiver",
			"Auto-negotiation": "autoNegotiation",
			"Link detected": "link"
		}

	def useGeolocation(self):
		geolocationData = geolocation.getGeolocationData(fields="isp,org,mobile,proxy,query", useCache=False)
		info = []
		if geolocationData.get("status", None) == "success":
			info.append("")
			info.append(formatLine("H", _("WAN connection information")))
			isp = geolocationData.get("isp", None)
			if isp:
				ispOrg = geolocationData.get("org", None)
				if ispOrg:
					info.append(formatLine("P1", _("ISP"), "%s  (%s)" % (isp, ispOrg)))
				else:
					info.append(formatLine("P1", _("ISP"), isp))
			mobile = geolocationData.get("mobile", None)
			info.append(formatLine("P1", _("Mobile connection"), (_("Yes") if mobile else _("No"))))
			proxy = geolocationData.get("proxy", False)
			info.append(formatLine("P1", _("Proxy detected"), (_("Yes") if proxy else _("No"))))
			publicIp = geolocationData.get("query", None)
			if publicIp:
				info.append(formatLine("P1", _("Public IP"), publicIp))
		else:
			info.append(_("Geolocation information cannot be retrieved, please try again later."))
			info.append("")
			info.append(_("Access to geolocation information requires an internet connection."))
		self.geolocationData = info
		for callback in self.onInformationUpdated:
			callback()

	def fetchInformation(self):
		self.informationTimer.stop()
		for interface in sorted([x for x in listdir("/sys/class/net") if not self.isBlacklisted(x)]):
			self.interfaceData[interface] = {}
			self.console.ePopen(("/sbin/ifconfig", "/sbin/ifconfig", interface), self.ifconfigInfoFinished, extra_args=interface)
			if iNetwork.isWirelessInterface(interface):
				self.console.ePopen(("/sbin/iwconfig", "/sbin/iwconfig", interface), self.iwconfigInfoFinished, extra_args=interface)
			else:
				self.console.ePopen(("/usr/sbin/ethtool", "/usr/sbin/ethtool", interface), self.ethtoolInfoFinished, extra_args=interface)
		for callback in self.onInformationUpdated:
			callback()

	def isBlacklisted(self, interface):
		for type in ("lo", "wifi", "wmaster", "sit", "tun", "sys", "p2p"):
			if interface.startswith(type):
				return True
		return False

	def ifconfigInfoFinished(self, result, retVal, extraArgs):  # This temporary code borrowed and adapted from the new but unreleased Network.py!
		if retVal == 0:
			capture = False
			data = ""
			for line in result.split("\n"):
				if line.startswith("%s " % extraArgs):
					capture = True
					if "HWaddr " in line:
						line = line.replace("HWaddr ", "HWaddr:")
					data += line
					continue
				if capture and line.startswith(" "):
					if " Scope:" in line:
						line = line.replace(" Scope:", " ")
					elif "X packets:" in line:
						pos = line.index("X packets:")
						direction = line[pos - 1:pos].lower()
						line = "%s%s" % (line[0:pos + 10], line[pos + 10:].replace(" ", "  %sx" % direction))
					elif " txqueuelen" in line:
						line = line.replace(" txqueuelen:", "  txqueuelen:")
					data += line
					continue
				if line == "":
					break
			data = list(filter(None, [x.strip().replace("=", ":", 1) for x in data.split("  ")]))
			data[0] = "interface:%s" % data[0]
			# print("[Network] DEBUG: Raw network data %s." % data)
			for item in data:
				if ":" not in item:
					flags = item.split()
					self.interfaceData[extraArgs]["up"] = True if "UP" in flags else False
					self.interfaceData[extraArgs]["status"] = "up" if "UP" in flags else "down"  # Legacy status flag.
					self.interfaceData[extraArgs]["running"] = True if "RUNNING" in flags else False
					self.interfaceData[extraArgs]["broadcast"] = True if "BROADCAST" in flags else False
					self.interfaceData[extraArgs]["multicast"] = True if "MULTICAST" in flags else False
					continue
				key, value = item.split(":", 1)
				key = self.ifconfigAttributes.get(key, None)
				if key:
					value = value.strip()
					if value.startswith("\""):
						value = value[1:-1]
					if key == "addr6":
						if key not in self.interfaceData[extraArgs]:
							self.interfaceData[extraArgs][key] = []
						self.interfaceData[extraArgs][key].append(value)
					else:
						self.interfaceData[extraArgs][key] = value
		for callback in self.onInformationUpdated:
			callback()

	def iwconfigInfoFinished(self, result, retVal, extraArgs):  # This temporary code borrowed and adapted from the new but unreleased Network.py!
		if retVal == 0:
			capture = False
			data = ""
			for line in result.split("\n"):
				if line.startswith("%s " % extraArgs):
					capture = True
					data += line
					continue
				if capture and line.startswith(" "):
					data += line
					continue
				if line == "":
					break
			data = list(filter(None, [x.strip().replace("=", ":", 1) for x in data.split("  ")]))
			data[0] = "interface:%s" % data[0]
			data[1] = "standard:%s" % data[1]
			for item in data:
				if ":" not in item:
					continue
				key, value = item.split(":", 1)
				key = self.iwconfigAttributes.get(key, None)
				if key:
					value = value.strip()
					if value.startswith("\""):
						value = value[1:-1]
					self.interfaceData[extraArgs][key] = value
			if "encryption" in self.interfaceData[extraArgs]:
				self.interfaceData[extraArgs]["encryption"] = _("Disabled or WPA/WPA2") if self.interfaceData[extraArgs]["encryption"] == "off" else _("Enabled")
			if "standard" in self.interfaceData[extraArgs] and "no wireless extensions" in self.interfaceData[extraArgs]["standard"]:
				del self.interfaceData[extraArgs]["standard"]
				self.interfaceData[extraArgs]["wireless"] = False
			else:
				self.interfaceData[extraArgs]["wireless"] = True
			if "ssid" in self.interfaceData[extraArgs]:
				self.interfaceData[extraArgs]["SSID"] = self.interfaceData[extraArgs]["ssid"]
		for callback in self.onInformationUpdated:
			callback()

	def ethtoolInfoFinished(self, result, retVal, extraArgs):  # This temporary code borrowed and adapted from the new but unreleased Network.py!
		if retVal == 0:
			for line in result.split("\n"):
				if "Speed:" in line:
					self.interfaceData[extraArgs]["speed"] = line.split(":")[1][:-4].strip()
				if "Duplex:" in line:
					self.interfaceData[extraArgs]["duplex"] = _(line.split(":")[1].strip().capitalize())
				if "Transceiver:" in line:
					self.interfaceData[extraArgs]["transeiver"] = _(line.split(":")[1].strip().capitalize())
				if "Auto-negotiation:" in line:
					self.interfaceData[extraArgs]["autoNegotiation"] = line.split(":")[1].strip().lower() == "on"
				if "Link detected:" in line:
					self.interfaceData[extraArgs]["link"] = line.split(":")[1].strip().lower() == "yes"
		for callback in self.onInformationUpdated:
			callback()

	def displayInformation(self):
		info = []
		hostname = fileReadLine("/proc/sys/kernel/hostname", source=MODULE_NAME)
		info.append(formatLine("H0H", _("Hostname"), hostname))
		for interface in sorted(list(self.interfaceData.keys())):
			info.append("")
			info.append(formatLine("H", _("Interface '%s'") % interface, iNetwork.getFriendlyAdapterName(interface)))
			if "up" in self.interfaceData[interface]:
				info.append(formatLine("P1", _("Status"), (_("Up") if self.interfaceData[interface]["up"] else _("Down"))))
				if self.interfaceData[interface]["up"]:
					if "addr" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("IP address"), self.interfaceData[interface]["addr"]))
					if "nmask" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Netmask"), self.interfaceData[interface]["nmask"]))
					if "brdaddr" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Broadcast address"), self.interfaceData[interface]["brdaddr"]))
					if "addr6" in self.interfaceData[interface]:
						for addr6 in self.interfaceData[interface]["addr6"]:
							addr, scope = addr6.split()
							info.append(formatLine("P1", _("IPv6 address"), _("%s  -  Scope: %s") % (addr, scope)))
					if "mac" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("MAC address"), self.interfaceData[interface]["mac"]))
					if "speed" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Speed"), "%s Mbps" % self.interfaceData[interface]["speed"]))
					if "duplex" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Duplex"), self.interfaceData[interface]["duplex"]))
					if "mtu" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("MTU"), self.interfaceData[interface]["mtu"]))
					if "link" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Link detected"), (_("Yes") if self.interfaceData[interface]["link"] else _("No"))))
					if "ssid" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("SSID"), self.interfaceData[interface]["ssid"]))
					if "standard" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Standard"), self.interfaceData[interface]["standard"]))
					if "encryption" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Encryption"), self.interfaceData[interface]["encryption"]))
					if "frequency" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Frequency"), self.interfaceData[interface]["frequency"]))
					if "accessPoint" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Access point"), self.interfaceData[interface]["accessPoint"]))
					if "bitrate" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Bit rate"), self.interfaceData[interface]["bitrate"]))
					if "signalQuality" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Signal quality"), self.interfaceData[interface]["signalQuality"]))
					if "signalStrength" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Signal strength"), self.interfaceData[interface]["signalStrength"]))
			if "rxBytes" in self.interfaceData[interface] or "txBytes" in self.interfaceData[interface]:
				info.append("")
				info.append(formatLine("P1", _("Bytes received"), self.interfaceData[interface]["rxBytes"]))
				info.append(formatLine("P1", _("Bytes sent"), self.interfaceData[interface]["txBytes"]))
		info += self.geolocationData
		self["information"].setText("\n".join(info))


class ReceiverInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Receiver Information"))
		self.skinName.insert(0, "ReceiverInformation")
		self["key_yellow"] = StaticText(_("System"))
		self["key_blue"] = StaticText(_("Debug Information"))
		self["receiverActions"] = HelpableActionMap(self, ["InfoActions", "ColorActions"], {
			"yellow": (self.showSystem, _("Show system information")),
			"blue": (self.showDebugInformation, _("Show debug log information"))
		}, prio=0, description=_("Receiver Information Actions"))

	def showSystem(self):
		self.session.openWithCallback(self.informationWindowClosed, SystemInformation)

	def showDebugInformation(self):
		self.session.openWithCallback(self.informationWindowClosed, DebugInformation)

	def displayInformation(self):
		info = []
		info.append(formatLine("H", _("Hardware information")))
		info.append("")
		info.append(formatLine("P1", _("Build Brand"), BoxInfo.getItem("brand")))
		platform = BoxInfo.getItem("platform")
		info.append(formatLine("P1", _("Build Model"), model))
		if platform != model:
			info.append(formatLine("P1", _("Platform"), platform))
		if procModel != model and procModel != "unknown":
			info.append(formatLine("P1", _("Proc model"), procModel))
		hwRelease = fileReadLine("/proc/stb/info/release", source=MODULE_NAME)
		if hwRelease:
			info.append(formatLine("P1", _("Factory release"), hwRelease))
		displaytype = BoxInfo.getItem("displaytype").startswith(" ")
		if displaytype and not displaytype.startswith(" "):
			info.append(formatLine("P1", _("Display type"), displaytype))
		fpVersion = getFPVersion()
		if fpVersion and fpVersion != "unknown":
			info.append(formatLine("P1", _("Front processor version"), fpVersion))
		transcoding = _("Yes") if BoxInfo.getItem("transcoding") else _("MultiTranscoding") if BoxInfo.getItem("multitranscoding") else _("No")
		info.append(formatLine("P1", _("Transcoding"), transcoding))
		info.append("")
		info.append(formatLine("H", _("Processor information")))
		info.append("")
		info.append(formatLine("P1", _("CPU"), about.getCPUInfoString()))
		info.append(formatLine("P1", _("CPU brand"), about.getCPUBrand()))
		socfamily = BoxInfo.getItem("socfamily")
		if socfamily:
			info.append(formatLine("P1", _("SoC family"), socfamily))
		info.append(formatLine("P1", _("CPU architecture"), about.getCPUArch()))
		fpu = BoxInfo.getItem("fpu")
		if fpu:
			info.append(formatLine("P1", _("FPU"), fpu))
		if BoxInfo.getItem("architecture") == "aarch64":
			info.append(formatLine("P1", _("MultiLib"), (_("Yes") if BoxInfo.getItem("multilib") else _("No"))))
		info.append("")
		info.append(formatLine("H", _("Remote control information")))
		info.append("")
		rcIndex = int(config.inputDevices.remotesIndex.value)
		info.append(formatLine("P1", _("RC selected name"), rcname))
		if rcname != rcname:
			info.append(formatLine("P1", _("RC default name"), rcname))
		boxRcType = getBoxRCType()
		if boxRcType:
			if boxRcType == "unknown":
				if isfile("/usr/bin/remotecfg"):
					boxRcType = _("Amlogic remote")
				elif isfile("/usr/sbin/lircd"):
					boxRcType = _("LIRC remote")
		info.append(formatLine("P1", _("RC detected type"), boxRcType))
		customCode = fileReadLine("/proc/stb/ir/rc/customcode", source=MODULE_NAME)
		if customCode:
			info.append(formatLine("P1", _("RC custom code"), customCode))
		if BoxInfo.getItem("HasHDMI-CEC") and config.hdmicec.enabled.value:
			info.append("")
			address = config.hdmicec.fixed_physical_address.value if config.hdmicec.fixed_physical_address.value != "0.0.0.0" else _("N/A")
			info.append(formatLine("P1", _("HDMI-CEC address"), address))
		info.append("")
		info.append(formatLine("H", _("Driver and kernel information")))
		info.append("")
		kernel = BoxInfo.getItem("kernel")
		driverdate = BoxInfo.getItem("driverdate")
		if driverdate != kernel:
			info.append(formatLine("P1", _("Drivers version"), driverdate))
		info.append(formatLine("P1", _("Kernel version"), kernel))
		deviceId = fileReadLine("/proc/device-tree/amlogic-dt-id", source=MODULE_NAME)
		if deviceId:
			info.append(formatLine("P1", _("Device id"), deviceId))
		givenId = fileReadLine("/proc/device-tree/le-dt-id", source=MODULE_NAME)
		if givenId:
			info.append(formatLine("P1", _("Given device id"), givenId))
		info.append("")
		info.append(formatLine("H", _("Tuner information")))
		info.append("")
		nims = nimmanager.nimListCompressed()
		for count in range(len(nims)):
			tuner, type = [x.strip() for x in nims[count].split(":", 1)]
			info.append(formatLine("P1", tuner, type))
		info.append("")
		info.append(formatLine("H", _("Storage information")))
		info.append("")
		stat = statvfs("/")
		diskSize = stat.f_blocks * stat.f_frsize
		info.append(formatLine("P1", _("Internal flash"), "%s  (%s)" % (scaleNumber(diskSize), scaleNumber(diskSize, "Iec"))))
		# hddList = storageManager.HDDList()
		hddList = harddiskmanager.HDDList()
		if hddList:
			for hdd in hddList:
				hdd = hdd[1]
				capacity = hdd.diskSize() * 1000000
				info.append(formatLine("P1", hdd.model(), "%s  (%s)" % (scaleNumber(capacity), scaleNumber(capacity, "Iec"))))
		else:
			info.append(formatLine("H", _("No hard disks detected.")))
		info.append("")
		info.append(formatLine("H", _("Network information")))
		info.append("")
		for x in about.GetIPsFromNetworkInterfaces():
			info.append(formatLine("P1", x[0], x[1]))
		info.append("")
		info.append(formatLine("H", _("Uptime"), about.getBoxUptime()))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "Receiver Information"


class StorageInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Storage Information"))
		self.skinName.insert(0, "StorageInformation")
		self["information"].setText(_("Retrieving network server information, please wait..."))
		self.mountInfo = []

	def fetchInformation(self):
		self.informationTimer.stop()
		self.console.ePopen("df -mh | grep -v '^Filesystem'", self.fetchComplete)
		for callback in self.onInformationUpdated:
			callback()

	def fetchComplete(self, result, retVal, extraArgs=None):
		result = result.replace("\n                        ", " ").split("\n")
		self.mountInfo = []
		for line in result:
			line = line.strip()
			if not line:
				continue
			data = line.split()
			if data[0].startswith("192") or data[0].startswith("//192"):
				# data[0] = ipAddress, data[1] = mountTotal, data[2] = mountUsed, data[3] = mountFree, data[4] = percetageUsed, data[5] = mountPoint.
				self.mountInfo.append(data)
		if isdir("/media/autofs"):
			for entry in sorted(listdir("/media/autofs")):
				path = pathjoin("/media/autofs", entry)
				keep = True
				for data in self.mountInfo:
					if data[5] == path:
						keep = False
						break
				if keep:
					self.mountInfo.append(["", 0, 0, 0, "N/A", path])
		for callback in self.onInformationUpdated:
			callback()

	def displayInformation(self):
		info = []
		info.append(formatLine("H", _("Detected storage devices")))
		info.append("")
		partitions = sorted(harddiskmanager.getMountedPartitions(), key=lambda partitions: partitions.device or "")
		for partition in partitions:
			if partition.mountpoint == "/":
				info.append(formatLine("H1", "/dev/root", partition.description))
				stat = statvfs("/")
				diskSize = stat.f_blocks * stat.f_frsize
				diskFree = stat.f_bfree * stat.f_frsize
				diskUsed = diskSize - diskFree
				info.append(formatLine("P2", _("Mountpoint"), partition.mountpoint))
				info.append(formatLine("P2", _("Capacity"), "%s  (%s)" % (scaleNumber(diskSize), scaleNumber(diskSize, "Iec"))))
				info.append(formatLine("P2", _("Used"), "%s  (%s)" % (scaleNumber(diskUsed), scaleNumber(diskUsed, "Iec"))))
				info.append(formatLine("P2", _("Free"), "%s  (%s)" % (scaleNumber(diskFree), scaleNumber(diskFree, "Iec"))))
				break
		# hddList = storageManager.HDDList()
		hddList = harddiskmanager.HDDList()
		if hddList:
			for hdd in hddList:
				hdd = hdd[1]
				info.append("")
				info.append(formatLine("H1", hdd.getDeviceName(), hdd.bus()))
				info.append(formatLine("P2", _("Model"), hdd.model()))
				diskSize = hdd.diskSize() * 1000000
				info.append(formatLine("P2", _("Capacity"), "%s  (%s)" % (scaleNumber(diskSize), scaleNumber(diskSize, "Iec"))))
				info.append(formatLine("P2", _("Sleeping"), (_("Yes") if hdd.isSleeping() else _("No"))))
				for partition in partitions:
					if partition.device and pathjoin("/dev", partition.device).startswith(hdd.getDeviceName()):
						info.append(formatLine("P2", _("Partition"), partition.device))
						stat = statvfs(partition.mountpoint)
						diskSize = stat.f_blocks * stat.f_frsize
						diskFree = stat.f_bfree * stat.f_frsize
						diskUsed = diskSize - diskFree
						info.append(formatLine("P3", _("Mountpoint"), partition.mountpoint))
						info.append(formatLine("P3", _("Capacity"), "%s  (%s)" % (scaleNumber(diskSize), scaleNumber(diskSize, "Iec"))))
						info.append(formatLine("P3", _("Used"), "%s  (%s)" % (scaleNumber(diskUsed), scaleNumber(diskUsed, "Iec"))))
						info.append(formatLine("P3", _("Free"), "%s  (%s)" % (scaleNumber(diskFree), scaleNumber(diskFree, "Iec"))))
		else:
			info.append("")
			info.append(formatLine("H1", _("No hard disks detected.")))
		info.append("")
		info.append(formatLine("H", _("Detected network servers")))
		if self.mountInfo:
			for data in self.mountInfo:
				info.append("")
				info.append(formatLine("H1", data[5]))
				if data[0]:
					info.append(formatLine("P2", _("Network address"), data[0]))
					info.append(formatLine("P2", _("Capacity"), data[1]))
					info.append(formatLine("P2", _("Used"), "%s  (%s)" % (data[2], data[4])))
					info.append(formatLine("P2", _("Free"), data[3]))
				else:
					info.append(formatLine("P2", _("Not currently mounted.")))
		else:
			info.append("")
			info.append(formatLine("P1", _("No network servers detected.")))
		self["information"].setText("\n".join(info))


class SystemInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.baseTitle = _("System Information")
		self.setTitle(self.baseTitle)
		self.skinName.insert(0, "SystemInformation")
		self["key_yellow"] = StaticText(_("Previous"))
		self["key_blue"] = StaticText(_("Next"))
		self["systemActions"] = HelpableActionMap(self, ["MenuActions", "ColorActions", "NavigationActions"], {
			"menu": (self.showSystemMenu, _("Show selection for system information screen")),
			"yellow": (self.previousSystem, _("Show previous system information screen")),
			"blue": (self.nextSystem, _("Show next system information screen")),
			"left": (self.previousSystem, _("Show previous system information screen")),
			"right": (self.nextSystem, _("Show next system information screen"))
		}, prio=0, description=_("System Information Actions"))
		self.systemCommands = [
			("CPU", None, "/proc/cpuinfo"),
			("Top Processes", ("/usr/bin/top", "/usr/bin/top", "-b", "-n", "1"), None),
			("Current Processes", ("/bin/ps", "/bin/ps", "-l"), None),
			("Kernel Modules", None, "/proc/modules"),
			("Kernel Messages", ("/bin/dmesg", "/bin/dmesg"), None),
			("System Messages", None, "/var/volatile/log/messages"),
			("Network Interfaces", ("/sbin/ifconfig", "/sbin/ifconfig"), None),
			("Disk Usage", ("/bin/df", "/bin/df", "-h"), None),
			("Mounted Volumes", ("/bin/mount", "/bin/mount"), None),
			("Partition Table", None, "/proc/partitions")
		]
		if BoxInfo.getItem("HAVEEDIDDECODE"):
			self.systemCommands.append(("EDID", ("/usr/bin/edid-decode", "/usr/bin/edid-decode", "/proc/stb/hdmi/raw_edid"), None))
		self.systemCommandsIndex = 0
		self.systemCommandsMax = len(self.systemCommands)
		self.info = None

	def showSystemMenu(self):
		choices = [(systemCommand[0], index) for index, systemCommand in enumerate(self.systemCommands)]
		self.session.openWithCallback(self.showSystemMenuCallBack, MessageBox, text=_("Select system information to view:"), list=choices, windowTitle=self.baseTitle)

	def showSystemMenuCallBack(self, selectedIndex):
		if isinstance(selectedIndex, int):
			self.systemCommandsIndex = selectedIndex
			self.displayInformation()
			self.informationTimer.start(25)

	def previousSystem(self):
		self.systemCommandsIndex = (self.systemCommandsIndex - 1) % self.systemCommandsMax
		self.displayInformation()
		self.informationTimer.start(25)

	def nextSystem(self):
		self.systemCommandsIndex = (self.systemCommandsIndex + 1) % self.systemCommandsMax
		self.displayInformation()
		self.informationTimer.start(25)

	def fetchInformation(self):
		self.informationTimer.stop()
		name, command, path = self.systemCommands[self.systemCommandsIndex]
		self.info = None
		if command:
			self.console.ePopen(command, self.fetchInformationCallback)
		elif path:
			try:
				with open(path, "r") as fd:
					self.info = [x.strip() for x in fd.readlines()]
			except OSError as err:
				self.info = [_("Error %d: System information file '%s' can't be read!  (%s)") % (err.errno, path, err.strerror)]
			for callback in self.onInformationUpdated:
				callback()

	def fetchInformationCallback(self, result, retVal, extraArgs):
		self.info = [x.rstrip() for x in result.split("\n")]
		for callback in self.onInformationUpdated:
			callback()

	def displayInformation(self):
		name, command, path = self.systemCommands[self.systemCommandsIndex]
		self.setTitle("%s: %s" % (self.baseTitle, name))
		self["key_yellow"].setText(self.systemCommands[(self.systemCommandsIndex - 1) % self.systemCommandsMax][0])
		self["key_blue"].setText(self.systemCommands[(self.systemCommandsIndex + 1) % self.systemCommandsMax][0])
		info = [_("Retrieving '%s' information, please wait...") % name] if self.info is None else self.info
		if info == [""]:
			info = [_("There is no information to show for '%s'.") % name]
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "System Information"


class TranslationInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Translation Information"))
		self.skinName.insert(0, "TranslationInformation")

	def displayInformation(self):
		info = []
		translateInfo = _("TRANSLATOR_INFO")
		if translateInfo != "TRANSLATOR_INFO":
			info.append(formatLine("H", _("Translation information")))
			info.append("")
			translateInfo = translateInfo.split("\n")
			for translate in translateInfo:
				info.append(formatLine("P1", translate))
			info.append("")
		translateInfo = _("").split("\n")  # This is deliberate to dump the translation information.
		for translate in translateInfo:
			if not translate:
				continue
			translate = [x.strip() for x in translate.split(":", 1)]
			if len(translate) == 1:
				translate.append("")
			info.append(formatLine("P1", translate[0], translate[1]))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "Translation Information"


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
		self.setTitle(_("About Information"))
		hddsplit = parameters.get("AboutHddSplit", 1)

		model = BoxInfo.getItem("model")
		brand = BoxInfo.getItem("brand")
		socfamily = BoxInfo.getItem("socfamily")
		displaytype = BoxInfo.getItem("displaytype")
		platform = BoxInfo.getItem("platform")

		procmodel = getBoxProc()

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
		if socfamily is not None:
			AboutText += _("SoC family: ") + BoxInfo.getItem("socfamily") + "\n"

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

		self["TunerHeader"] = StaticText(_("Detected NIMs:"))
		AboutText += "\n" + _("Detected NIMs:") + "\n"

		nims = nimmanager.nimListCompressed()
		for count in range(len(nims)):
			if count < 4:
				self["Tuner" + str(count)] = StaticText(nims[count])
			else:
				self["Tuner" + str(count)] = StaticText("")
			AboutText += nims[count] + "\n"

		self["HDDHeader"] = StaticText(_("Detected storage devices:"))
		AboutText += "\n" + _("Detected storage devices:") + "\n"

		hddlist = harddiskmanager.HDDList()
		hddinfo = ""
		if hddlist:
			formatstring = hddsplit and "%s:%s, %.1f %s %s" or "%s\n(%s, %.1f %s %s)"
			for count in range(len(hddlist)):
				if hddinfo:
					hddinfo += "\n"
				hdd = hddlist[count][1]
				if int(hdd.free()) > 1024:
					hddinfo += formatstring % (hdd.model(), hdd.capacity(), hdd.free() / 1024.0, _("GB"), _("free"))
				else:
					hddinfo += formatstring % (hdd.model(), hdd.capacity(), hdd.free(), _("MB"), _("free"))
		else:
			hddinfo = _("none")
		self["hddA"] = StaticText(hddinfo)
		AboutText += hddinfo + "\n\n" + _("Network Info:")
		for x in about.GetIPsFromNetworkInterfaces():
			AboutText += "\n" + x[0] + ": " + x[1]

		self["AboutScrollLabel"] = ScrollLabel(AboutText)
		self["key_green"] = Button(_("Translations"))
		self["key_red"] = Button(_("Latest Commits"))
		self["key_yellow"] = Button(_("Dmesg Info"))
		self["key_blue"] = Button(_("Memory Info"))

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


class Devices(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		screentitle = _("Device Information")
		title = screentitle
		Screen.setTitle(self, title)
		self["TunerHeader"] = StaticText(_("Detected tuners:"))
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
		self["actions"] = ActionMap(["SetupActions", "ColorActions", "TimerEditActions"], {
			"cancel": self.close,
			"red": self.close,
			"save": self.close
		})
		self.onLayoutFinish.append(self.populate)

	def populate(self):
		self.mountinfo = ''
		self["actions"].setEnabled(False)
		scanning = _("Please wait while scanning for devices...")
		self["nims"].setText(scanning)
		for count in (0, 1, 2, 3):
			self["Tuner" + str(count)].setText(scanning)
		self["hdd"].setText(scanning)
		self['mounts'].setText(scanning)
		self.activityTimer.start(1)

	def populate2(self):
		self.activityTimer.stop()
		self.Console = Console()
		niminfo = ""
		nims = nimmanager.nimListCompressed()
		for count in range(len(nims)):
			if niminfo:
				niminfo += "\n"
			niminfo += nims[count]
		self["nims"].setText(niminfo)

		nims = nimmanager.nimList()
		if len(nims) <= 4 :
			for count in (0, 1, 2, 3):
				if count < len(nims):
					self["Tuner" + str(count)].setText(nims[count])
				else:
					self["Tuner" + str(count)].setText("")
		else:
			desc_list = []
			count = 0
			cur_idx = -1
			while count < len(nims):
				data = nims[count].split(":")
				idx = data[0].strip('Tuner').strip()
				desc = data[1].strip()
				if desc_list and desc_list[cur_idx]['desc'] == desc:
					desc_list[cur_idx]['end'] = idx
				else:
					desc_list.append({'desc' : desc, 'start' : idx, 'end' : idx})
					cur_idx += 1
				count += 1

			for count in (0, 1, 2, 3):
				if count < len(desc_list):
					if desc_list[count]['start'] == desc_list[count]['end']:
						text = "Tuner %s: %s" % (desc_list[count]['start'], desc_list[count]['desc'])
					else:
						text = "Tuner %s-%s: %s" % (desc_list[count]['start'], desc_list[count]['end'], desc_list[count]['desc'])
				else:
					text = ""

				self["Tuner" + str(count)].setText(text)

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
		except Exception as err:
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
		except Exception as err:
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

		self["actions"] = ActionMap(["SetupActions", "ColorActions"], {
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
		except Exception as err:
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
		self["key_red"] = Button()
		self["key_green"] = Button()

		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions"], {
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
			except (IOError, OSError) as err:
				pass
			self.updateOptions()
		self.run_console()

	def removeAllLogfiles(self, answer):
		if answer:
			for fileName in self.getLogFilesList():
				try:
					remove(fileName)
				except (IOError, OSError) as err:
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
			except Exception as err:
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
