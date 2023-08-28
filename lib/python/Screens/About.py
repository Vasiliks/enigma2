from datetime import datetime
from glob import glob
from json import loads
from locale import format_string
from os import listdir, popen, remove, statvfs
from os.path import getmtime, isfile, isdir, join, basename
from time import localtime, strftime, strptime
from urllib.request import urlopen
from enigma import eConsoleAppContainer, eDVBResourceManager, eGetEnigmaDebugLvl, eLabel, eTimer, getDesktop, ePoint, eSize
from skin import parameters
from Components.About import about, getChipSetString
from Components.ActionMap import ActionMap, HelpableActionMap

from Components.config import config
from Components.Console import Console
from Components.Sources.StaticText import StaticText
from Components.Harddisk import harddiskmanager
from Components.InputDevice import REMOTE_DISPLAY_NAME, REMOTE_NAME, REMOTE_RCTYPE, remoteControl
from Components.Label import Label
from Components.Network import iNetwork
from Components.NimManager import nimmanager
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Components.ProgressBar import ProgressBar
from Components.GUIComponent import GUIComponent
from Components.SystemInfo import BoxInfo, SystemInfo
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen, ScreenSummary

from Tools.Directories import SCOPE_PLUGINS, resolveFilename, fileExists, fileHas, pathExists, fileReadLine, fileReadLines, fileWriteLine, isPluginInstalled
from Tools.Geolocation import geolocation
from Tools.StbHardware import getFPVersion, getProcInfoTypeTuner, getBoxProc, getHWSerial, getBoxRCType, getBoxProcType, getDemodVersion
from Tools.LoadPixmap import LoadPixmap
from Tools.Conversions import scaleNumber, formatDate

MODULE_NAME = __name__.split(".")[-1]

model = BoxInfo.getItem("model")
brand = BoxInfo.getItem("brand")
socfamily = BoxInfo.getItem("socfamily")
displaytype = BoxInfo.getItem("displaytype")
platform = BoxInfo.getItem("platform")
DISPLAY_BRAND = BoxInfo.getItem("displaybrand")
DISPLAY_MODEL = BoxInfo.getItem("displaymodel")
rcname = BoxInfo.getItem("rcname")
procType = getBoxProcType()
procModel = getBoxProc()
fpVersion = getFPVersion()

INFO_COLORS = ["N", "H", "S", "P", "V", "M", "F"]
INFO_COLOR = {
	"B": None,
	"N": 0x00ffffff,  # Normal.
	"H": 0x00ffffff,  # Headings.
	"S": 0x00ffffff,  # Subheadings.
	"P": 0x00cccccc,  # Prompts.
	"V": 0x00cccccc,  # Values.
	"M": 0x00ffff00,  # Messages.
	"F": 0x0000ffff  # Features.
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
		"00": _("OTT Model"),
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
		Screen.__init__(self, session)
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
			"up": (self["information"].moveUp, _("Move up a line")),
			"down": (self["information"].moveDown, _("Move down a line")),
			"pageDown": (self["information"].pageDown, _("Move down a screen")),
			"bottom": (self["information"].moveBottom, _("Move to last line / screen"))
		}, prio=0, description=_("Common Information Actions"))
		colors = parameters.get("InformationColors", (0x00ffffff, 0x00ffffff, 0x00ffffff, 0x00cccccc, 0x00cccccc, 0x00ffff00, 0x0000ffff))
		if len(colors) == len(INFO_COLORS):
			for index in range(len(colors)):
				INFO_COLOR[INFO_COLORS[index]] = colors[index]
		else:
			print("[Information] Warning: %d colors are defined in the skin when %d were expected!" % (len(colors), len(INFO_COLORS)))
		self["information"].setText(_("Loading information, please wait..."))
		self.extraSpacing = config.usage.informationExtraSpacing.value
		self.onInformationUpdated = [self.displayInformation]
		self.onLayoutFinish.append(self.displayInformation)
		self.console = Console()
		self.informationTimer = eTimer()
		self.informationTimer.callback.append(self.fetchInformation)
		self.informationTimer.start(25)

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
					with open(path) as fd:
						info = (x.strip() for x in fd.readlines())[-LOG_MAX_LINES:]
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
		info.append(formatLine("S", _("Enigma2 information")))
		if self.extraSpacing:
			info.append("")
		enigmaVersion = str(BoxInfo.getItem("imageversion"))
		enigmaVersion = enigmaVersion.rsplit("-", enigmaVersion.count("-") - 2)
		if len(enigmaVersion) == 3:
			enigmaVersion = "%s (%s-%s)" % (enigmaVersion[0], enigmaVersion[2], enigmaVersion[1].capitalize())
		elif len(enigmaVersion) == 1:
			enigmaVersion = "%s" % enigmaVersion[0]
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
		info.append(formatLine("S", _("Build information")))
		if self.extraSpacing:
			info.append("")
		info.append(formatLine("P1", _("Distribution"), BoxInfo.getItem("displaydistro")))
		info.append(formatLine("P1", _("Distribution build"), formatDate(BoxInfo.getItem("imagebuild"))))
		info.append(formatLine("P1", _("Distribution build date"), formatDate(about.getBuildDateString())))
		info.append(formatLine("P1", _("Distribution architecture"), BoxInfo.getItem("architecture")))
		if BoxInfo.getItem("imagedir"):
			info.append(formatLine("P1", _("Distribution folder"), BoxInfo.getItem("imagedir")))
		if BoxInfo.getItem("imagefs"):
			info.append(formatLine("P1", _("Distribution file system"), BoxInfo.getItem("imagefs").strip()))
		info.append(formatLine("P1", _("Feed URL"), BoxInfo.getItem("feedsurl")))
		info.append("")
		info.append(formatLine("S", _("Software information")))
		if self.extraSpacing:
			info.append("")
		info.append(formatLine("P1", _("GCC version"), about.getGccVersion()))
		info.append(formatLine("P1", _("Glibc version"), about.getGlibcVersion()))
		info.append(formatLine("P1", _("OpenSSL version"), about.getopensslVersionString()))
		info.append(formatLine("P1", _("Python version"), about.getPythonVersionString()))
		info.append(formatLine("P1", _("GStreamer version"), about.getGStreamerVersionString().replace("GStreamer ", "")))
		info.append(formatLine("P1", _("FFmpeg version"), about.getFFmpegVersionString()))
		info.append("")
		info.append(formatLine("S", _("Boot information")))
		if self.extraSpacing:
			info.append("")
		if BoxInfo.getItem("mtdbootfs"):
			info.append(formatLine("P1", _("MTD boot"), BoxInfo.getItem("mtdbootfs")))
		if BoxInfo.getItem("mtdkernel"):
			info.append(formatLine("P1", _("MTD kernel"), BoxInfo.getItem("mtdkernel")))
		if BoxInfo.getItem("mtdrootfs"):
			info.append(formatLine("P1", _("MTD root"), BoxInfo.getItem("mtdrootfs")))
		if BoxInfo.getItem("kernelfile"):
			info.append(formatLine("P1", _("Kernel file"), BoxInfo.getItem("kernelfile")))
		if BoxInfo.getItem("rootfile"):
			info.append(formatLine("P1", _("Root file"), BoxInfo.getItem("rootfile")))
		if BoxInfo.getItem("mkubifs"):
			info.append(formatLine("P1", _("MKUBIFS"), BoxInfo.getItem("mkubifs")))
		if BoxInfo.getItem("ubinize"):
			info.append(formatLine("P1", _("UBINIZE"), BoxInfo.getItem("ubinize")))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "OpenPli Information"


class GeolocationInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Geolocation Information"))
		self.skinName.insert(0, "GeolocationInformation")

	def displayInformation(self):
		info = []
		info.append(formatLine("H", _("Geolocation information")))
		info.append("")
		geolocationData = geolocation.getGeolocationData(fields="continent,country,regionName,city,lat,lon,timezone,currency,isp,org,mobile,proxy,query", useCache=False)
		if geolocationData.get("status", None) == "success":
			info.append(formatLine("S", _("Location information")))
			if self.extraSpacing:
				info.append("")
			continent = geolocationData.get("continent", None)
			if continent:
				info.append(formatLine("P1", _("Continent"), continent))
			country = geolocationData.get("country", None)
			if country:
				info.append(formatLine("P1", _("Country"), country))
			state = geolocationData.get("regionName", None)
			if state:
				# TRANSLATORS: "State" is location information and not condition based information.
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
			info.append(formatLine("S", _("Local information")))
			if self.extraSpacing:
				info.append("")
			timezone = geolocationData.get("timezone", None)
			if timezone:
				info.append(formatLine("P1", _("Timezone"), timezone))
			currency = geolocationData.get("currency", None)
			if currency:
				info.append(formatLine("P1", _("Currency"), currency))
			info.append("")
			info.append(formatLine("S", _("Connection information")))
			if self.extraSpacing:
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
			info.append(_("Access to geolocation information requires an Internet connection."))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "Geolocation Information"


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
		def formatNumber(number):
			number = number.strip()
			value, units = number.split(maxsplit=1) if " " in number else (number, None)
			if "." in value:
				format = "%.3f"
				value = float(value)
			else:
				format = "%d"
				value = int(value)
			return "%s %s" % (format_string(format, value, grouping=True), units) if units else format_string(format, value, grouping=True)

		info = []
		info.append(formatLine("H", _("Memory information")))
		info.append("")
		memInfo = fileReadLines("/proc/meminfo", source=MODULE_NAME)
		info.append(formatLine("S", _("RAM (Summary)")))
		if self.extraSpacing:
			info.append("")
		for line in memInfo:
			key, value = (x for x in line.split(maxsplit=1))
			if key == "MemTotal:":
				info.append(formatLine("P1", _("Total memory"), formatNumber(value)))
			elif key == "MemFree:":
				info.append(formatLine("P1", _("Free memory"), formatNumber(value)))
			elif key == "Buffers:":
				info.append(formatLine("P1", _("Buffers"), formatNumber(value)))
			elif key == "Cached:":
				info.append(formatLine("P1", _("Cached"), formatNumber(value)))
			elif key == "SwapTotal:":
				info.append(formatLine("P1", _("Total swap"), formatNumber(value)))
			elif key == "SwapFree:":
				info.append(formatLine("P1", _("Free swap"), formatNumber(value)))
		info.append("")
		info.append(formatLine("S", _("FLASH")))
		if self.extraSpacing:
			info.append("")
		stat = statvfs("/")
		diskSize = stat.f_blocks * stat.f_frsize
		diskFree = stat.f_bfree * stat.f_frsize
		diskUsed = diskSize - diskFree
		info.append(formatLine("P1", _("Total flash"), "%s  (%s)" % (scaleNumber(diskSize), scaleNumber(diskSize, "Iec"))))
		info.append(formatLine("P1", _("Used flash"), "%s  (%s)" % (scaleNumber(diskUsed), scaleNumber(diskUsed, "Iec"))))
		info.append(formatLine("P1", _("Free flash"), "%s  (%s)" % (scaleNumber(diskFree), scaleNumber(diskFree, "Iec"))))
		info.append("")
		info.append(formatLine("S", _("RAM (Details)")))
		if self.extraSpacing:
			info.append("")
		for line in memInfo:
			key, value = (x for x in line.split(maxsplit=1))
			info.append(formatLine("P1", key[:-1], formatNumber(value)))
		info.append("")
		info.append(formatLine("M1", _("The detailed information is intended for developers only.")))
		info.append(formatLine("M1", _("Please don't panic if you see values that look suspicious.")))
		self["information"].setText("\n".join(info))

	def clearMemoryInformation(self):
		self.console.ePopen(("/bin/sync", "/bin/sync"))
		fileWriteLine("/proc/sys/vm/drop_caches", "3")
		self.informationTimer.start(25)
		for callback in self.onInformationUpdated:
			callback()

	def getSummaryInformation(self):
		return "Memory Information Data"


class MultiBootInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("MultiBoot Information"))
		self.skinName.insert(0, "MultiBootInformation")

	def fetchInformation(self):
		self.informationTimer.stop()
		for callback in self.onInformationUpdated:
			callback()

	def displayInformation(self):
		info = []
		info.append(_("This screen is not yet available."))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "MultiBoot Information Data"


class NetworkInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Network Information"))
		self.skinName.insert(0, "NetworkInformation")
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
			info.append(formatLine("S", _("WAN connection information")))
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
			info.append(_("Access to geolocation information requires an Internet connection."))
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
			if isinstance(result, bytes):
				result = result.decode("UTF-8", "ignore")
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
			if isinstance(result, bytes):
				result = result.decode("UTF-8", "ignore")
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
			if isinstance(result, bytes):
				result = result.decode("UTF-8", "ignore")
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
		info.append(formatLine("H", _("Network information")))
		info.append("")
		hostname = fileReadLine("/proc/sys/kernel/hostname", source=MODULE_NAME)
		info.append(formatLine("S0S", _("Hostname"), hostname))
		for interface in sorted(self.interfaceData.keys()):
			info.append("")
			info.append(formatLine("S", _("Interface '%s'") % interface, iNetwork.getFriendlyAdapterName(interface)))
			if "up" in self.interfaceData[interface]:
				info.append(formatLine("P1", _("Status"), (_("Up / Active") if self.interfaceData[interface]["up"] else _("Down / Inactive"))))
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
							info.append(formatLine("P1", _("IPv6 address"), addr))
							info.append(formatLine("P3V2", _("Scope"), scope))
						info.append(formatLine("P1", _("IPv6 address"), "2003:0000:4021:4700:4270:0000:0000:8250/64"))
						info.append(formatLine("P3V2", _("Scope"), "Global"))
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
						info.append(formatLine("P1", _("Bitrate"), self.interfaceData[interface]["bitrate"]))
					if "signalQuality" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Signal quality"), self.interfaceData[interface]["signalQuality"]))
					if "signalStrength" in self.interfaceData[interface]:
						info.append(formatLine("P1", _("Signal strength"), self.interfaceData[interface]["signalStrength"]))
			if "rxBytes" in self.interfaceData[interface] or "txBytes" in self.interfaceData[interface]:
				info.append("")
				rxBytes = int(self.interfaceData[interface]["rxBytes"].split(" ")[0])
				txBytes = int(self.interfaceData[interface]["txBytes"].split(" ")[0])
				info.append(formatLine("P1", _("Bytes received"), "%d (%s)" % (rxBytes, scaleNumber(rxBytes, style="Iec", format="%.1f"))))
				info.append(formatLine("P1", _("Bytes sent"), "%d (%s)" % (txBytes, scaleNumber(txBytes, style="Iec", format="%.1f"))))
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
			"yellow": (self.showSystemInformation, _("Show system information")),
			"blue": (self.showDebugInformation, _("Show debug log information"))
		}, prio=0, description=_("Receiver Information Actions"))

	def showSystemInformation(self):
		self.session.openWithCallback(self.informationWindowClosed, SystemInformation)

	def showDebugInformation(self):
		self.session.openWithCallback(self.informationWindowClosed, DebugInformation)

	def displayInformation(self):
		def findPackageRevision(package, packageList):
			revision = None
			data = [x for x in packageList if "-%s" % package in x]
			if data:
				data = data[0].split("-")
				if len(data) >= 4:
					revision = data[3]
			return revision

		info = []
		info.append("")
		info.append(formatLine("S", _("Hardware information")))
		if self.extraSpacing:
			info.append("")
		platform = BoxInfo.getItem("platform")
		info.append(formatLine("P1", _("Build Model"), model))
		if platform != model:
			info.append(formatLine("P1", _("Platform"), platform))
		procModel = getBoxProc()
		if procModel != model:
			info.append(formatLine("P1", _("Proc model"), procModel))
		info.append(formatLine("P1", _("Hardware type"), getBoxProcTypeName().split("-")[0])) if getBoxProcTypeName() != _("Unknown") else ""
		hwSerial = getHWSerial() if getHWSerial() != "unknown" else None
		cpuSerial = about.getCPUSerial() if about.getCPUSerial() != "unknown" else None
		if hwSerial or cpuSerial:
			info.append(formatLine("P1", _("Hardware serial"), (hwSerial if hwSerial else cpuSerial)))
		hwRelease = fileReadLine("/proc/stb/info/release", source=MODULE_NAME)
		if hwRelease:
			info.append(formatLine("P1", _("Factory release"), hwRelease))
		displaytype = BoxInfo.getItem("displaytype")
		if not displaytype.startswith(" "):
			info.append(formatLine("P1", _("Display type"), displaytype))
		fpVersion = getFPVersion()
		if fpVersion and fpVersion != "unknown":
			info.append(formatLine("P1", _("Front processor version"), fpVersion))
		DemodVersion = getDemodVersion()
		if DemodVersion and DemodVersion != "unknown":
			info.append(formatLine("P1", _("Demod firmware version"), DemodVersion))
		transcoding = _("Yes") if BoxInfo.getItem("transcoding") else _("MultiTranscoding") if BoxInfo.getItem("multitranscoding") else _("No")
		info.append(formatLine("P1", _("Transcoding"), transcoding))
		temp = about.getSystemTemperature()
		if temp:
			info.append(formatLine("P1", _("System temperature"), temp))
		info.append("")
		info.append(formatLine("S", _("Processor information")))
		if self.extraSpacing:
			info.append("")
		cpu = about.getCPUInfoString()
		info.append(formatLine("P1", _("CPU"), cpu[0]))
		info.append(formatLine("P1", _("CPU speed/cores"), "%s %s" % (cpu[1], cpu[2])))
		if cpu[3]:
			info.append(formatLine("P1", _("CPU temperature"), cpu[3]))
		info.append(formatLine("P1", _("CPU brand"), about.getCPUBrand()))
		socFamily = BoxInfo.getItem("socfamily")
		if socFamily:
			info.append(formatLine("P1", _("SoC family"), socFamily))
		info.append(formatLine("P1", _("CPU architecture"), about.getCPUArch()))
		if BoxInfo.getItem("fpu"):
			info.append(formatLine("P1", _("FPU"), BoxInfo.getItem("fpu")))
		if BoxInfo.getItem("architecture") == "aarch64":
			info.append(formatLine("P1", _("MultiLib"), (_("Yes") if BoxInfo.getItem("multilib") else _("No"))))
		info.append("")
		info.append(formatLine("S", _("Remote control information")))
		if self.extraSpacing:
			info.append("")
		rcIndex = int(config.inputDevices.remotesIndex.value)
		info.append(formatLine("P1", _("RC identification"), "%s  (Index: %d)" % (remoteControl.remotes[rcIndex][REMOTE_DISPLAY_NAME], rcIndex)))
		rcName = remoteControl.remotes[rcIndex][REMOTE_NAME]
		info.append(formatLine("P1", _("RC selected name"), rcName))
		boxName = BoxInfo.getItem("rcname")
		if boxName != rcName:
			info.append(formatLine("P1", _("RC default name"), boxName))
		rcType = remoteControl.remotes[rcIndex][REMOTE_RCTYPE]
		info.append(formatLine("P1", _("RC selected type"), rcType))
		boxType = BoxInfo.getItem("rctype")
		if boxType != rcType:
			info.append(formatLine("P1", _("RC default type"), boxType))
		boxRcType = getBoxRCType()
		if boxRcType:
			if boxRcType == "unknown":
				if isfile("/usr/bin/remotecfg"):
					boxRcType = _("Amlogic remote")
				elif isfile("/usr/sbin/lircd"):
					boxRcType = _("LIRC remote")
			if boxRcType != rcType and boxRcType != "unknown":
				info.append(formatLine("P1", _("RC detected type"), boxRcType))
		customCode = fileReadLine("/proc/stb/ir/rc/customcode", source=MODULE_NAME)
		if customCode:
			info.append(formatLine("P1", _("RC custom code"), customCode))
		if BoxInfo.getItem("HasHDMI-CEC") and config.hdmicec.enabled.value:
			info.append("")
			address = config.hdmicec.fixed_physical_address.value if config.hdmicec.fixed_physical_address.value != "0.0.0.0" else _("N/A")
			info.append(formatLine("P1", _("HDMI-CEC address"), address))
		info.append("")
		info.append(formatLine("S", _("Driver and kernel information")))
		if self.extraSpacing:
			info.append("")
		info.append(formatLine("P1", _("Drivers version"), about.getDriverInstalledDate()))
		info.append(formatLine("P1", _("Kernel version"), about.getKernelVersionString()))
		deviceId = fileReadLine("/proc/device-tree/amlogic-dt-id", source=MODULE_NAME)
		if deviceId:
			info.append(formatLine("P1", _("Device id"), deviceId))
		givenId = fileReadLine("/proc/device-tree/le-dt-id", source=MODULE_NAME)
		if givenId:
			info.append(formatLine("P1", _("Given device id"), givenId))
		if BoxInfo.getItem("HiSilicon"):
			info.append("")
			info.append(formatLine("S", _("HiSilicon specific information")))
			if self.extraSpacing:
				info.append("")
			process = Popen(("/usr/bin/opkg", "list-installed"), stdout=PIPE, stderr=PIPE, universal_newlines=True)
			stdout, stderr = process.communicate()
			if process.returncode == 0:
				missing = True
				packageList = stdout.split("\n")
				revision = findPackageRevision("grab", packageList)
				if revision and revision != "r0":
					info.append(formatLine("P1", _("Grab"), revision))
					missing = False
				revision = findPackageRevision("hihalt", packageList)
				if revision:
					info.append(formatLine("P1", _("Halt"), revision))
					missing = False
				revision = findPackageRevision("libs", packageList)
				if revision:
					info.append(formatLine("P1", _("Libs"), revision))
					missing = False
				revision = findPackageRevision("partitions", packageList)
				if revision:
					info.append(formatLine("P1", _("Partitions"), revision))
					missing = False
				revision = findPackageRevision("reader", packageList)
				if revision:
					info.append(formatLine("P1", _("Reader"), revision))
					missing = False
				revision = findPackageRevision("showiframe", packageList)
				if revision:
					info.append(formatLine("P1", _("Showiframe"), revision))
					missing = False
				if missing:
					info.append(formatLine("P1", _("HiSilicon specific information not found.")))
			else:
				info.append(formatLine("P1", _("Package information currently not available!")))
		info.append("")
		info.append(formatLine("S", _("Tuner information")))
		if self.extraSpacing:
			info.append("")
		for count, nim in enumerate(nimmanager.nimListCompressed()):
			tuner, type = (x.strip() for x in nim.split(":", 1))
			info.append(formatLine("P1", tuner, type))
		info.append("")
		info.append(formatLine("S", _("Storage / Drive information")))
		if self.extraSpacing:
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
		info.append(formatLine("S", _("Network information")))
		if self.extraSpacing:
			info.append("")
		for x in about.GetIPsFromNetworkInterfaces():
			info.append(formatLine("P1", x[0], x[1]))
		info.append("")
		info.append(formatLine("S", _("Uptime"), about.getBoxUptime()))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "Receiver Information"


class StorageInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Storage / Disk Information"))
		self.skinName.insert(0, "StorageDiskInformation")
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
				path = join("/media/autofs", entry)
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
		info.append(formatLine("H", _("Storage / Disk information")))
		info.append("")
		partitions = sorted(harddiskmanager.getMountedPartitions(), key=lambda partitions: partitions.device or "")
		for partition in partitions:
			if partition.mountpoint == "/":
				info.append(formatLine("S1", "/dev/root", partition.description))
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
				info.append(formatLine("S1", hdd.getDeviceName(), hdd.bus()))
				info.append(formatLine("P2", _("Model"), hdd.model()))
				diskSize = hdd.diskSize() * 1000000
				info.append(formatLine("P2", _("Capacity"), "%s  (%s)" % (scaleNumber(diskSize), scaleNumber(diskSize, "Iec"))))
				info.append(formatLine("P2", _("Sleeping"), (_("Yes") if hdd.isSleeping() else _("No"))))
				for partition in partitions:
					if partition.device and join("/dev", partition.device).startswith(hdd.getDeviceName()):
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
			info.append(formatLine("S1", _("No storage or hard disks detected.")))
		info.append("")
		info.append(formatLine("H", _("Detected network servers")))
		info.append("")
		if self.mountInfo:
			count = 0
			for data in self.mountInfo:
				if count:
					info.append("")
				info.append(formatLine("S1", data[5]))
				if data[0]:
					info.append(formatLine("P2", _("Network address"), data[0]))
					info.append(formatLine("P2", _("Capacity"), data[1]))
					info.append(formatLine("P2", _("Used"), "%s  (%s)" % (data[2], data[4])))
					info.append(formatLine("P2", _("Free"), data[3]))
				else:
					info.append(formatLine("P2", _("Not currently mounted.")))
				count += 1
		else:
			info.append(formatLine("S1", _("No network storage detected.")))
		self["information"].setText("\n".join(info))


class StreamingInformation(InformationBase):
	def __init__(self, session):
		InformationBase.__init__(self, session)
		self.setTitle(_("Streaming Tuner Information"))
		self.skinName.insert(0, "StreamingInformation")
		self["key_yellow"] = StaticText(_("Stop Auto Refresh"))
		self["key_blue"] = StaticText()
		self["refreshActions"] = HelpableActionMap(self, ["ColorActions"], {
			"yellow": (self.toggleAutoRefresh, _("Toggle auto refresh On/Off"))
		}, prio=0, description=_("Streaming Information Actions"))
		self["streamActions"] = HelpableActionMap(self, ["ColorActions"], {
			"blue": (self.stopStreams, _("Stop streams"))
		}, prio=0, description=_("Streaming Information Actions"))
		self["streamActions"].setEnabled(False)
		self.autoRefresh = True

	def toggleAutoRefresh(self):
		self.autoRefresh = not self.autoRefresh
		self["key_yellow"].setText(_("Stop Auto Refresh") if self.autoRefresh else _("Start Auto Refresh"))

	def stopStreams(self):
		if eStreamServer.getInstance().getConnectedClients():
			eStreamServer.getInstance().stopStream()
		if eRTSPStreamServer.getInstance().getConnectedClients():
			eRTSPStreamServer.getInstance().stopStream()

	def displayInformation(self):
		info = []
		info.append(formatLine("H", _("Streaming tuner information for %s %s") % getBoxDisplayName()))
		info.append("")
		clientList = eStreamServer.getInstance().getConnectedClients() + eRTSPStreamServer.getInstance().getConnectedClients()
		if clientList:
			self["key_blue"].setText(_("Stop Streams"))
			self["streamActions"].setEnabled(True)
			for count, client in enumerate(clientList):
				# print("[Information] DEBUG: Client data '%s'." % str(client))
				if count:
					info.append("")
				info.append(formatLine("S", "%s  -  %d" % (_("Client"), count + 1)))
				info.append(formatLine("P1", _("Service reference"), client[1]))
				info.append(formatLine("P1", _("Service name"), ServiceReference(client[1]).getServiceName() or _("Unknown service!")))
				info.append(formatLine("P1", _("IP address"), client[0][7:] if client[0].startswith("::ffff:") else client[0]))
				info.append(formatLine("P1", _("Transcoding"), _("Yes") if client[2] else _("No")))
		else:
			self["key_blue"].setText("")
			self["streamActions"].setEnabled(False)
			info.append(formatLine("P1", _("No tuners are currently streaming.")))
		self["information"].setText("\n".join(info))
		if self.autoRefresh:
			self.informationTimer.start(AUTO_REFRESH_TIME)

	def getSummaryInformation(self):
		return "Streaming Tuner Information"


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
				with open(path) as fd:
					self.info = (x.strip() for x in fd.readlines())
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
		info.append("")
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
			translate = (x.strip() for x in translate.split(":", 1))
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
			data = descList[count]["start"] if descList[count]["start"] == descList[count]["end"] else ("%s-%s" % (descList[count]["start"], descList[count]["end"]))
			info.append(formatLine("P1", "Tuner %s:" % data))
			data = descList[count]["start"] if descList[count]["start"] == descList[count]["end"] else ("%s-%s" % (descList[count]["start"], descList[count]["end"]))
			info.append(formatLine("P2", "%s" % descList[count]["desc"]))
		info.append(formatLine("P1", _("Tuner type"), "%s" % getBoxProcTypeName().split("-")[1])) if getBoxProcTypeName() != _("Unknown") else ""
		# info.append("")
		# info.append(formatLine("H", _("Logical tuners")))  # Each tuner is a listed separately even if the hardware is common.
		# info.append("")
		# nims = nimmanager.nimListCompressed()
		# for count in range(len(nims)):
		# 	tuner, type = (x.strip() for x in nims[count].split(":", 1))
		# 	info.append(formatLine("P1", tuner, type))
		info.append("")
		info.append(formatLine("", _("DVB API"), about.getDVBAPI()))
		dvbFeToolTxt = ""
		for nim in range(nimmanager.getSlotCount()):
			dvbFeToolTxt += eDVBResourceManager.getInstance().getFrontendCapabilities(nim)
		dvbApiVersion = dvbFeToolTxt.splitlines()[0].replace("DVB API version: ", "").strip() if dvbFeToolTxt else _("N/A")
		info.append(formatLine("", _("DVB API version"), dvbApiVersion))
		info.append("")
		info.append(formatLine("", _("Transcoding"), (_("Yes") if BoxInfo.getItem("transcoding") else _("No"))))
		info.append(formatLine("", _("MultiTranscoding"), (_("Yes") if BoxInfo.getItem("multitranscoding") else _("No"))))
		info.append("")
		info.append(formatLine("", _("DVB-C"), (_("Yes") if "DVBC" in dvbFeToolTxt or "DVB-C" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("DVB-S"), (_("Yes") if "DVBS" in dvbFeToolTxt or "DVB-S" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("DVB-T"), (_("Yes") if "DVBT" in dvbFeToolTxt or "DVB-T" in dvbFeToolTxt else _("No"))))
		info.append("")
		info.append(formatLine("", _("Multistream"), (_("Yes") if "MULTISTREAM" in dvbFeToolTxt else _("No"))))
		info.append("")
		info.append(formatLine("", _("ANNEX-A"), (_("Yes") if "ANNEX_A" in dvbFeToolTxt or "ANNEX-A" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("ANNEX-B"), (_("Yes") if "ANNEX_B" in dvbFeToolTxt or "ANNEX-B" in dvbFeToolTxt else _("No"))))
		info.append(formatLine("", _("ANNEX-C"), (_("Yes") if "ANNEX_C" in dvbFeToolTxt or "ANNEX-C" in dvbFeToolTxt else _("No"))))
		self["information"].setText("\n".join(info))

	def getSummaryInformation(self):
		return "DVB Information"


class InformationSummary(ScreenSummary):
	def __init__(self, session, parent):
		ScreenSummary.__init__(self, session, parent=parent)
		self.parent = parent
		self["information"] = StaticText()
		parent.onInformationUpdated.append(self.updateSummary)
		# self.updateSummary()

	def updateSummary(self):
		self["information"].setText(self.parent.getSummaryInformation())
