from os.path import exists
from sys import maxsize
from twisted.internet import threads

from boxbranding import getDBoxLCD
from enigma import eActionMap, eDBoxLCD, eTimer

from Components.config import ConfigNothing, ConfigSelection, ConfigSlider, ConfigSubsection, ConfigYesNo, config
from Components.SystemInfo import SystemInfo, MODEL
from Screens.InfoBar import InfoBar
from Screens.Screen import Screen
from Screens.Standby import inTryQuitMainloop
from Tools.Directories import fileReadLine, fileWriteLine


class dummyScreen(Screen):
	skin = """
	<screen position="0,0" size="0,0" transparent="1">
		<widget source="session.VideoPicture" render="Pig" position="0,0" size="0,0" backgroundColor="transparent" zPosition="1" />
	</screen>"""

	def __init__(self, session, args=None):
		Screen.__init__(self, session)
		self.close()


def IconCheck(session=None, **kwargs):
	if exists("/proc/stb/lcd/symbol_network") or exists("/proc/stb/lcd/symbol_usb"):
		global networklinkpoller
		networklinkpoller = IconCheckPoller()
		networklinkpoller.start()


class IconCheckPoller:
	def __init__(self):
		self.timer = eTimer()

	def start(self):
		if self.iconcheck not in self.timer.callback:
			self.timer.callback.append(self.iconcheck)
		self.timer.startLongTimer(0)

	def stop(self):
		if self.iconcheck in self.timer.callback:
			self.timer.callback.remove(self.iconcheck)
		self.timer.stop()

	def iconcheck(self):
		try:
			threads.deferToThread(self.jobTask)
		except:
			pass
		self.timer.startLongTimer(30)

	def JobTask(self):
		LinkState = 0
		if exists("/sys/class/net/wlan0/operstate"):
			LinkState = open("/sys/class/net/wlan0/operstate").read()
			if LinkState != "down":
				LinkState = open("/sys/class/net/wlan0/operstate").read()
		elif exists("/sys/class/net/eth0/operstate"):
			LinkState = open("/sys/class/net/eth0/operstate").read()
			if LinkState != "down":
				LinkState = open("/sys/class/net/eth0/carrier").read()
		LinkState = LinkState[:1]
		if exists("/proc/stb/lcd/symbol_network") and config.lcd.mode.value == "1":
			f = open("/proc/stb/lcd/symbol_network", "w")
			f.write(str(LinkState))
			f.close()
		elif exists("/proc/stb/lcd/symbol_network") and config.lcd.mode.value == "0":
			f = open("/proc/stb/lcd/symbol_network", "w")
			f.write("0")
			f.close()
		# from sys import version_info
		# if version_info.major == 2:
			# from usb import busses
			# USBState = 0
			# busses = usb.busses()
			# for bus in busses:
				# devices = bus.devices
				# for dev in devices:
					# if dev.deviceClass != 9 and dev.deviceClass != 2 and dev.idVendor > 0:
		# if version_info.major == 2:
			# from usb import busses
			# USBState = 0
			# busses = usb.busses()
			# for bus in busses:
				# devices = bus.devices
				# for dev in devices:
					# if dev.deviceClass != 9 and dev.deviceClass != 2 and dev.idVendor > 0:
						# print ' '
						# print "Device:", dev.filename
						# print "  Number:", dev.deviceClass
						# print "  idVendor: %d (0x%04x)" % (dev.idVendor, dev.idVendor)
						# print "  idProduct: %d (0x%04x)" % (dev.idProduct, dev.idProduct)
						# USBState = 1
			# if exists("/proc/stb/lcd/symbol_usb") and config.lcd.mode.value == '1':
				# f = open("/proc/stb/lcd/symbol_usb", "w")
				# f.write(str(USBState))
				# f.close()
			# elif exists("/proc/stb/lcd/symbol_usb") and config.lcd.mode.value == '0':
				# f = open("/proc/stb/lcd/symbol_usb", "w")
				# f.write('0')
				# f.close()

			# self.timer.startLongTimer(30)


class LCD:
	def __init__(self):
		eActionMap.getInstance().bindAction("", -maxsize - 1, self.dimUpEvent)
		self.autoDimDownLCDTimer = eTimer()
		self.autoDimDownLCDTimer.callback.append(self.autoDimDownLCD)
		self.autoDimUpLCDTimer = eTimer()
		self.autoDimUpLCDTimer.callback.append(self.autoDimUpLCD)
		self.currBrightness = self.dimBrightness = self.brightness = None
		self.dimDelay = 0
		config.misc.standbyCounter.addNotifier(self.standbyCounterChanged, initial_call=False)

	def standbyCounterChanged(self, configElement):
		from Screens.Standby import inStandby
		inStandby.onClose.append(self.leaveStandby)
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		eActionMap.getInstance().unbindAction("", self.dimUpEvent)

	def leaveStandby(self):
		eActionMap.getInstance().bindAction("", -maxsize - 1, self.dimUpEvent)

	def dimUpEvent(self, key, flag):
		self.autoDimDownLCDTimer.stop()
		if not inTryQuitMainloop:
			if self.brightness is not None and not self.autoDimUpLCDTimer.isActive():
				self.autoDimUpLCDTimer.start(10, True)

	def autoDimDownLCD(self):
		if not inTryQuitMainloop:
			if self.dimBrightness is not None and self.currBrightness > self.dimBrightness:
				self.currBrightness = self.currBrightness - 1
				eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
				self.autoDimDownLCDTimer.start(10, True)

	def autoDimUpLCD(self):
		if not inTryQuitMainloop:
			self.autoDimDownLCDTimer.stop()
			if self.currBrightness < self.brightness:
				self.currBrightness = self.currBrightness + 5
				if self.currBrightness >= self.brightness:
					self.currBrightness = self.brightness
				eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
				self.autoDimUpLCDTimer.start(10, True)
			else:
				if self.dimBrightness is not None and self.currBrightness > self.dimBrightness and self.dimDelay is not None and self.dimDelay > 0:
					self.autoDimDownLCDTimer.startLongTimer(self.dimDelay)

	def setBright(self, value):
		value *= 255
		value //= 10
		if value > 255:
			value = 255
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		self.currBrightness = self.brightness = value
		eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
		if self.dimBrightness is not None and self.currBrightness > self.dimBrightness:
			if self.dimDelay is not None and self.dimDelay > 0:
				self.autoDimDownLCDTimer.startLongTimer(self.dimDelay)

	def setStandbyBright(self, value):
		value *= 255
		value //= 10
		if value > 255:
			value = 255
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		self.brightness = value
		if self.dimBrightness is None:
			self.dimBrightness = value
		if self.currBrightness is None:
			self.currBrightness = value
		eDBoxLCD.getInstance().setLCDBrightness(self.brightness)

	def setDimBright(self, value):
		value *= 255
		value //= 10
		if value > 255:
			value = 255
		self.dimBrightness = value

	def setDimDelay(self, value):
		self.dimDelay = int(value)

	def setContrast(self, value):
		value *= 63
		value //= 20
		if value > 63:
			value = 63
		eDBoxLCD.getInstance().setLCDContrast(value)

	def setInverted(self, value):
		if value:
			value = 255
		eDBoxLCD.getInstance().setInverted(value)

	def setFlipped(self, value):
		eDBoxLCD.getInstance().setFlipped(value)

	def isOled(self):
		return eDBoxLCD.getInstance().isOled()

	def setMode(self, value):
		if exists("/proc/stb/lcd/show_symbols"):
			print("[Lcd] setLCDMode='%s'." % value)
			fileWriteLine("/proc/stb/lcd/show_symbols", value)
		if config.lcd.mode.value == "0":
			SystemInfo["SeekStatePlay"] = False
			SystemInfo["StatePlayPause"] = False
			if SystemInfo["LCDsymbol_hdd"]:
				fileWriteLine(SystemInfo["LCDsymbol_hdd"], "0")
			if exists("/proc/stb/lcd/symbol_hddprogress"):
				fileWriteLine("/proc/stb/lcd/symbol_hddprogress", "0")
			if exists("/proc/stb/lcd/symbol_network"):
				fileWriteLine("/proc/stb/lcd/symbol_network", "0")
			if exists("/proc/stb/lcd/symbol_signal"):
				fileWriteLine("/proc/stb/lcd/symbol_signal", "0")
			if SystemInfo["LCDsymbol_timeshift"]:
				fileWriteLine(SystemInfo["LCDsymbol_timeshift"], "0")
			if exists("/proc/stb/lcd/symbol_tv"):
				fileWriteLine("/proc/stb/lcd/symbol_tv", "0")
			if exists("/proc/stb/lcd/symbol_usb"):
				fileWriteLine("/proc/stb/lcd/symbol_usb", "0")

	def setPower(self, value):
		if exists("/proc/stb/power/vfd"):
			print("[Lcd] setLCDPower='%s'." % value)
			fileWriteLine("/proc/stb/power/vfd", value)
		elif exists("/proc/stb/lcd/vfd"):
			print("[Lcd] setLCDPower='%s'." % value)
			fileWriteLine("/proc/stb/lcd/vfd", value)

	def setShowoutputresolution(self, value):
		if exists("/proc/stb/lcd/show_outputresolution"):
			print("[Lcd] setLCDShowoutputresolution='%s'." % value)
			fileWriteLine("/proc/stb/lcd/show_outputresolution", value)

	def setfblcddisplay(self, value):
		print("[Lcd] setfblcddisplay='%s'." % value)
		fileWriteLine(SystemInfo["LcdLiveTV"], value)

	def setRepeat(self, value):
		if SystemInfo["VFD_scroll_repeats"]:
			print("[Lcd] setLCDRepeat='%s'." % value)
			fileWriteLine("/proc/stb/lcd/scroll_repeats", value)

	def setScrollspeed(self, value):
		if SystemInfo["VFD_scroll_delay"]:
			print("[Lcd] setLCDScrollspeed='%s'." % value)
			fileWriteLine("/proc/stb/lcd/scroll_delay", value)

	def setLEDNormalState(self, value):
		eDBoxLCD.getInstance().setLED(value, 0)

	def setLEDDeepStandbyState(self, value):
		eDBoxLCD.getInstance().setLED(value, 1)

	def setLEDBlinkingTime(self, value):
		eDBoxLCD.getInstance().setLED(value, 2)

	def setLCDMiniTVMode(self, value):
		if SystemInfo["LCDMiniTV"]:
			print("[Lcd] setLCDMiniTVMode='%s'." % value)
			fileWriteLine("/proc/stb/lcd/mode", value)

	def setLCDMiniTVPIPMode(self, value):
		print("[Lcd] setLCDMiniTVPIPMode='%s'." % value)
		# DEBUG: Should this be doing something?

	def setLCDMiniTVFPS(self, value):
		if exists("/proc/stb/lcd/fps"):
			print("[Lcd] setLCDMiniTVFPS='%s'." % value)
			fileWriteLine("/proc/stb/lcd/fps", value)


def leaveStandby():
	config.lcd.bright.apply()
	if MODEL == "vuultimo":
		config.lcd.ledbrightness.apply()
		config.lcd.ledbrightnessdeepstandby.apply()


def standbyCounterChanged(configElement):
	from Screens.Standby import inStandby
	inStandby.onClose.append(leaveStandby)
	config.lcd.standby.apply()
	config.lcd.ledbrightnessstandby.apply()
	config.lcd.ledbrightnessdeepstandby.apply()


def InitLcd():
	if getDBoxLCD() == "False":
		detected = False
	elif MODEL in ("pulse4kmini",):
		detected = True
	else:
		detected = eDBoxLCD.getInstance().detected()
	config.lcd = ConfigSubsection()
	if SystemInfo["LCDMiniTV"]:
		f = open(SystemInfo["LCDMiniTV"], "r")
		LCDMINITV = f.read().strip().split(" ")
		print("[LCD] LCDMiniTV", LCDMINITV)
		f.close()
	else:
		LCDMINITV = False
	if detected:
		ilcd = LCD()

		def setLCDbright(configElement):
			ilcd.setBright(configElement.value)

		def setLCDstandbybright(configElement):
			ilcd.setStandbyBright(configElement.value)

		def setLCDdimbright(configElement):
			ilcd.setDimBright(configElement.value)

		def setLCDdimdelay(configElement):
			ilcd.setDimDelay(configElement.value)

		def setLCDcontrast(configElement):
			ilcd.setContrast(configElement.value)

		def setLCDinverted(configElement):
			ilcd.setInverted(configElement.value)

		def setLCDflipped(configElement):
			ilcd.setFlipped(configElement.value)

		def setLCDmode(configElement):
			ilcd.setMode(configElement.value)

		def setLCDpower(configElement):
			ilcd.setPower(configElement.value)

		def setLCDshowoutputresolution(configElement):
			ilcd.setShowoutputresolution(configElement.value)

		def setLCDminitvmode(configElement):
			ilcd.setLCDMiniTVMode(configElement.value)

		def setLCDminitvpipmode(configElement):
			ilcd.setLCDMiniTVPIPMode(configElement.value)

		def setLCDminitvfps(configElement):
			ilcd.setLCDMiniTVFPS(configElement.value)

		def setLEDnormalstate(configElement):
			ilcd.setLEDNormalState(configElement.value)

		def setLEDdeepstandby(configElement):
			ilcd.setLEDDeepStandbyState(configElement.value)

		def setLEDblinkingtime(configElement):
			ilcd.setLEDBlinkingTime(configElement.value)

		def setPowerLEDstate(configElement):
			if SystemInfo["PowerLED"]:
				fileWriteLine(SystemInfo["PowerLED"], configElement.value)

		def setPowerLEDstate2(configElement):
			if SystemInfo["PowerLED2"]:
				fileWriteLine(SystemInfo["PowerLED2"], configElement.value)

		def setPowerLEDstanbystate(configElement):
			if SystemInfo["StandbyLED"]:
				fileWriteLine(SystemInfo["StandbyLED"], configElement.value)

		def setPowerLEDdeepstanbystate(configElement):
			if SystemInfo["SuspendLED"]:
				fileWriteLine(SystemInfo["SuspendLED"], configElement.value)

		def setLedPowerColor(configElement):
			if exists("/proc/stb/fp/ledpowercolor"):
				fileWriteLine("/proc/stb/fp/ledpowercolor", configElement.value)

		def setLedStandbyColor(configElement):
			if SystemInfo["LedStandbyColor"]:
				fileWriteLine(SystemInfo["LedStandbyColor"], configElement.value)

		def setLedSuspendColor(configElement):
			if SystemInfo["LedSuspendColor"]:
				fileWriteLine(SystemInfo["LedSuspendColor"], configElement.value)

		def setLedBlinkControlColor(configElement):
			if SystemInfo["FrontpanelLEDBlinkControl"]:
				fileWriteLine(SystemInfo["FrontpanelLEDBlinkControl"], configElement.value)

		def setLedBrightnessControl(configElement):
			if SystemInfo["FrontpanelLEDBrightnessControl"]:
				fileWriteLine(SystemInfo["FrontpanelLEDBrightnessControl"], configElement.value)

		def setLedColorControlColor(configElement):
			if SystemInfo["FrontpanelLEDColorControl"]:
				fileWriteLine(SystemInfo["FrontpanelLEDColorControl"], configElement.value)

		def setLedFadeControlColor(configElement):
			if SystemInfo["FrontpanelLEDFadeControl"]:
				fileWriteLine(SystemInfo["FrontpanelLEDFadeControl"], configElement.value)

		def setPower4x7On(configElement):
			if SystemInfo["Power4x7On"]:
				fileWriteLine(SystemInfo["Power4x7On"], configElement.value)

		def setPower4x7Standby(configElement):
			if SystemInfo["Power4x7Standby"]:
				fileWriteLine(SystemInfo["Power4x7Standby"], configElement.value)

		def setPower4x7Suspend(configElement):
			if SystemInfo["Power4x7Suspend"]:
				fileWriteLine(SystemInfo["Power4x7Suspend"], configElement.value)

		def setXcoreVFD(configElement):
			if exists("/sys/module/brcmstb_osmega/parameters/pt6302_cgram"):
				fileWriteLine("/sys/module/brcmstb_osmega/parameters/pt6302_cgram", configElement.value)
			if exists("/sys/module/brcmstb_spycat4k/parameters/pt6302_cgram"):
				fileWriteLine("/sys/module/brcmstb_spycat4k/parameters/pt6302_cgram", configElement.value)
			if exists("/sys/module/brcmstb_spycat4kmini/parameters/pt6302_cgram"):
				fileWriteLine("/sys/module/brcmstb_spycat4kmini/parameters/pt6302_cgram", configElement.value)
			if exists("/sys/module/brcmstb_spycat4kcombo/parameters/pt6302_cgram"):
				fileWriteLine("/sys/module/brcmstb_spycat4kcombo/parameters/pt6302_cgram", configElement.value)

		config.usage.vfd_xcorevfd = ConfigSelection(choices=[
			("0", _("12 character")),
			("1", _("8 character"))
		], default="0")
		config.usage.vfd_xcorevfd.addNotifier(setXcoreVFD)
		config.usage.lcd_powerled = ConfigSelection(choices=[
			("off", _("Off")),
			("on", _("On"))
		], default="on")
		config.usage.lcd_powerled.addNotifier(setPowerLEDstate)
		config.usage.lcd_powerled2 = ConfigSelection(choices=[
			("off", _("Off")),
			("on", _("On"))
		], default="on")
		config.usage.lcd_powerled2.addNotifier(setPowerLEDstate2)
		config.usage.lcd_standbypowerled = ConfigSelection(choices=[
			("off", _("Off")),
			("on", _("On"))
		], default="on")
		config.usage.lcd_standbypowerled.addNotifier(setPowerLEDstanbystate)
		config.usage.lcd_deepstandbypowerled = ConfigSelection(choices=[
			("off", _("Off")),
			("on", _("On"))
		], default="on")
		config.usage.lcd_deepstandbypowerled.addNotifier(setPowerLEDdeepstanbystate)
		config.lcd.ledpowercolor = ConfigSelection(choices=[
			("0", _("Off")),
			("1", _("Blue")),
			("2", _("Red")),
			("3", _("Violet"))
		], default="1")
		config.lcd.ledpowercolor.addNotifier(setLedPowerColor)
		config.lcd.ledstandbycolor = ConfigSelection(choices=[
			("0", _("Off")),
			("1", _("Blue")),
			("2", _("Red")),
			("3", _("Violet"))
		], default="3")
		config.lcd.ledstandbycolor.addNotifier(setLedStandbyColor)
		config.lcd.ledsuspendcolor = ConfigSelection(choices=[
			("0", _("Off")),
			("1", _("Blue")),
			("2", _("Red")),
			("3", _("Violet"))
		], default="2")
		config.lcd.ledsuspendcolor.addNotifier(setLedSuspendColor)
		colorsList = [
			("0xff0000", _("Red")),
			("0xff3333", _("Rose")),
			("0xff5500", _("Orange")),
			("0xdd9900", _("Yellow")),
			("0x99dd00", _("Lime")),
			("0x00ff00", _("Green")),
			("0x00ff99", _("Aqua")),
			("0x00bbff", _("Olympic blue")),
			("0x0000ff", _("Blue")),
			("0x6666ff", _("Azure")),
			("0x9900ff", _("Purple")),
			("0xff0066", _("Pink")),
			("0xffffff", _("White")),
		]
		config.lcd.ledblinkcontrolcolor = ConfigSelection(choices=colorsList, default="0xffffff")
		config.lcd.ledblinkcontrolcolor.addNotifier(setLedBlinkControlColor)
		config.lcd.ledbrightnesscontrol = ConfigSlider(default=0xff, increment=25, limits=(0, 0xff))
		config.lcd.ledbrightnesscontrol.addNotifier(setLedBrightnessControl)
		config.lcd.ledcolorcontrolcolor = ConfigSelection(choices=colorsList, default="0xffffff")
		config.lcd.ledcolorcontrolcolor.addNotifier(setLedColorControlColor)
		config.lcd.ledfadecontrolcolor = ConfigSelection(choices=colorsList, default="0xffffff")
		config.lcd.ledfadecontrolcolor.addNotifier(setLedFadeControlColor)
		config.lcd.power4x7on = ConfigSelection(choices=[
			("off", _("Off")),
			("on", _("On"))
		], default="on")
		config.lcd.power4x7on.addNotifier(setPower4x7On)
		config.lcd.power4x7standby = ConfigSelection(choices=[
			("off", _("Off")),
			("on", _("On"))
		], default="on")
		config.lcd.power4x7standby.addNotifier(setPower4x7Standby)
		config.lcd.power4x7suspend = ConfigSelection(choices=[
			("off", _("Off")),
			("on", _("On"))
		], default="on")
		config.lcd.power4x7suspend.addNotifier(setPower4x7Suspend)
		if MODEL in ("dm900", "dm920", "e4hdultra", "protek4k"):
			standby_default = 4
		elif MODEL in ("spycat4kmini", "osmega"):
			standby_default = 10
		else:
			standby_default = 1
		if not ilcd.isOled():
			config.lcd.contrast = ConfigSlider(default=5, limits=(0, 20))
			config.lcd.contrast.addNotifier(setLCDcontrast)
		else:
			config.lcd.contrast = ConfigNothing()

		max_limit = 10
		default_bright = 10

		if MODEL in ("novatwin", "novacombo", "zgemmas2s", "zgemmash1", "zgemmash2", "zgemmass", "zgemmahs", "zgemmah2s", "zgemmah2h", "spycat"):
			max_limit = 4
			default_bright = 4
		elif MODEL in ("spycat4kmini", "osmega"):
			default_bright = SystemInfo["DefaultDisplayBrightness"]

		config.lcd.standby = ConfigSlider(default=standby_default, limits=(0, max_limit))
		config.lcd.dimbright = ConfigSlider(default=standby_default, limits=(0, max_limit))
		config.lcd.bright = ConfigSlider(default=default_bright, limits=(0, max_limit))
		config.lcd.dimbright.addNotifier(setLCDdimbright)
		config.lcd.dimbright.apply = lambda: setLCDdimbright(config.lcd.dimbright)
		config.lcd.dimdelay = ConfigSelection(choices=[
			("5", "5 %s" % _("Seconds")),
			("10", "10 %s" % _("Seconds")),
			("15", "15 %s" % _("Seconds")),
			("20", "20 %s" % _("Seconds")),
			("30", "30 %s" % _("Seconds")),
			("60", "1 %s" % _("Miinute")),
			("120", "2 %s" % _("Minutes")),
			("300", "5 %s" % _("Minutes")),
			("0", _("Off"))
		], default="0")
		config.lcd.dimdelay.addNotifier(setLCDdimdelay)
		config.lcd.standby.addNotifier(setLCDstandbybright)
		config.lcd.standby.apply = lambda: setLCDstandbybright(config.lcd.standby)
		config.lcd.bright.addNotifier(setLCDbright)
		config.lcd.bright.apply = lambda: setLCDbright(config.lcd.bright)
		config.lcd.bright.callNotifiersOnSaveAndCancel = True
		config.lcd.invert = ConfigYesNo(default=False)
		config.lcd.invert.addNotifier(setLCDinverted)

		def PiconPackChanged(configElement):
			configElement.save()

		config.lcd.picon_pack = ConfigYesNo(default=False)
		config.lcd.picon_pack.addNotifier(PiconPackChanged)
		config.lcd.flip = ConfigYesNo(default=False)
		config.lcd.flip.addNotifier(setLCDflipped)

		if SystemInfo["VFD_scroll_repeats"]:
			def scroll_repeats(configElement):
				fileWriteLine(SystemInfo["VFD_scroll_repeats"], configElement.value)

			config.usage.vfd_scroll_repeats = ConfigSelection(choices=[
				("0", _("None")),
				("1", _("1X")),
				("2", _("2X")),
				("3", _("3X")),
				("4", _("4X")),
				("500", _("Continuous"))
			], default="3")
			config.usage.vfd_scroll_repeats.addNotifier(scroll_repeats, immediate_feedback=False)
		else:
			config.usage.vfd_scroll_repeats = ConfigNothing()
		if SystemInfo["VFD_scroll_delay"]:
			def scroll_delay(configElement):
				if SystemInfo["VFDDelay"]:
					fileWriteLine(SystemInfo["VFD_scroll_delay"], int(configElement.value))

			config.usage.vfd_scroll_delay = ConfigSlider(default=150, increment=10, limits=(0, 500))
			config.usage.vfd_scroll_delay.addNotifier(scroll_delay, immediate_feedback=False)
			config.lcd.hdd = ConfigYesNo(default=True)
		else:
			config.lcd.hdd = ConfigNothing()
			config.usage.vfd_scroll_delay = ConfigNothing()
		if SystemInfo["VFD_initial_scroll_delay"]:
			def initial_scroll_delay(configElement):
				if SystemInfo["VFDDelay"]:
					fileWriteLine(SystemInfo["VFD_initial_scroll_delay"], int(configElement.value))

			config.usage.vfd_initial_scroll_delay = ConfigSelection(choices=[
				("3000", "3 %s" % _("Seconds")),
				("5000", "5 %s" % _("Seconds")),
				("10000", "10 %s" % _("Seconds")),
				("20000", "20 %s" % _("Seconds")),
				("30000", "30 %s" % _("Seconds")),
				("0", _("No delay"))
			], default="10000")
			config.usage.vfd_initial_scroll_delay.addNotifier(initial_scroll_delay, immediate_feedback=False)
		else:
			config.usage.vfd_initial_scroll_delay = ConfigNothing()
		if SystemInfo["VFD_final_scroll_delay"]:
			def final_scroll_delay(configElement):
				if SystemInfo["VFDDelay"]:
					fileWriteLine(SystemInfo["VFD_final_scroll_delay"], int(configElement.value))

			config.usage.vfd_final_scroll_delay = ConfigSelection(choices=[
				("3000", "3 %s" % _("Seconds")),
				("5000", "5 %s" % _("Seconds")),
				("10000", "10 %s" % _("Seconds")),
				("20000", "20 %s" % _("Seconds")),
				("30000", "30 %s" % _("Seconds")),
				("0", _("No delay"))
			], default="10000")
			config.usage.vfd_final_scroll_delay.addNotifier(final_scroll_delay, immediate_feedback=False)
		else:
			config.usage.vfd_final_scroll_delay = ConfigNothing()
		if exists("/proc/stb/lcd/show_symbols"):
			config.lcd.mode = ConfigSelection(choices=[
				("0", _("No")),
				("1", _("Yes"))
			], default="1")
			config.lcd.mode.addNotifier(setLCDmode)
		else:
			config.lcd.mode = ConfigNothing()
		if exists("/proc/stb/power/vfd") or exists("/proc/stb/lcd/vfd"):
			config.lcd.power = ConfigSelection(choices=[
				("0", _("No")),
				("1", _("Yes"))
			], default="1")
			config.lcd.power.addNotifier(setLCDpower)
		else:
			config.lcd.power = ConfigNothing()
		if exists("/proc/stb/lcd/show_outputresolution"):
			config.lcd.showoutputresolution = ConfigSelection(choices=[
				("0", _("No")),
				("1", _("Yes"))
			], default="1")
			config.lcd.showoutputresolution.addNotifier(setLCDshowoutputresolution)
		else:
			config.lcd.showoutputresolution = ConfigNothing()
		config.lcd.scroll_speed = ConfigSelection(choices=[
			("500", _("slow")),
			("300", _("normal")),
			("100", _("fast"))
		], default="300")
		config.lcd.scroll_delay = ConfigSelection(choices=[
			("10000", "10 %s" % _("Seconds")),
			("20000", "20 %s" % _("Seconds")),
			("30000", "30 %s" % _("Seconds")),
			("60000", "1 %s" % _("Minute")),
			("300000", "5 %s" % _("Minutes")),
			("noscrolling", _("Off"))
		], default="10000")
		if SystemInfo["LcdLiveTV"]:
			config.lcd.minitvdisplay = ConfigYesNo(default=False)
			if "live_enable" in SystemInfo["LcdLiveTV"]:
				def setLiveTvDisplay(configElement):
					ilcd.setfblcddisplay("enable" if configElement.value else "disable")
				config.lcd.minitvdisplay.addNotifier(setLiveTvDisplay)
			else:
				def setLiveTvDisplay(configElement):
					ilcd.setfblcddisplay("1" if configElement.value else "0")
				config.lcd.minitvdisplay.addNotifier(setLiveTvDisplay)
		else:
			config.lcd.minitvdisplay = ConfigNothing()
		if SystemInfo["LCDMiniTV"] and MODEL not in ("gbquad", "gbquadplus", "gbquad4k", "gbue4k"):
			config.lcd.minitvmode = ConfigSelection([
				("0", _("normal")),
				("1", _("MiniTV")),
				("2", _("OSD")),
				("3", _("MiniTV with OSD")),
			], "0")
			config.lcd.minitvmode.addNotifier(setLCDminitvmode)
			config.lcd.minitvpipmode = ConfigSelection([
				("0", _("Off")),
				("5", _("PIP")),
				("7", _("PIP with OSD")),
			], "0")
			config.lcd.minitvpipmode.addNotifier(setLCDminitvpipmode)
			config.lcd.minitvfps = ConfigSlider(default=30, limits=(0, 30))
			config.lcd.minitvfps.addNotifier(setLCDminitvfps)
		elif LCDMINITV and MODEL in ("gbquad4k", "gbue4k"):
			#  (0:normal, 1:video0, 2:fb, 3:vide0+fb, 4:video1, 5:vide0+video1, 6:video1+fb, 7:video0+video1+fb)
			config.lcd.minitvmode = ConfigSelection(default="0", choices=[
					("0", _("normal")),
					("1", _("MiniTV") + _(" - video0")),
					("3", _("MiniTV with OSD") + _(" - video0")),
					("2", _("OSD")),
					("4", _("MiniTV") + _(" - video1")),
					("6", _("MiniTV with OSD") + _(" - video1")),
					("5", _("MiniTV") + _(" - video0+video1")),
					("7", _("MiniTV with OSD") + _(" - video0+video1"))])
			config.lcd.minitvmode.addNotifier(setLCDminitvmode)
			config.lcd.minitvpipmode = ConfigSelection(default="0", choices=[
					("0", _("off")),
					("4", _("PIP")),
					("6", _("PIP with OSD"))])
			config.lcd.minitvpipmode.addNotifier(setLCDminitvpipmode)
			config.lcd.minitvfps = ConfigSlider(default=30, limits=(0, 30))
			config.lcd.minitvfps.addNotifier(setLCDminitvfps)
		else:
			config.lcd.minitvmode = ConfigNothing()
			config.lcd.minitvpipmode = ConfigNothing()
			config.lcd.minitvfps = ConfigNothing()
		if SystemInfo["LCDMiniTV"]:
			def setLCDModeMinitTV(configElement):
				print("[Lcd] setLCDModeMinitTV='%s'." % configElement.value)
				fileWriteLine(SystemInfo["LCDMiniTV"], configElement.value)

			def setMiniTVFPS(configElement):
				print("[Lcd] setMiniTVFPS='%s'." % configElement.value)
				fileWriteLine("/proc/stb/lcd/fps", configElement.value)

			def setLCDModePiP(configElement):
				pass

			config.lcd.modepip = ConfigSelection(choices={
				"0": _("Off"),
				"5": _("PiP"),
				"7": _("PiP with OSD")
			}, default="0")
			config.lcd.modepip.addNotifier(setLCDModePiP)
			config.lcd.modeminitv = ConfigSelection(choices={
				"0": _("normal"),
				"1": _("MiniTV"),
				"2": _("OSD"),
				"3": _("MiniTV with OSD")
			}, default="0")
			config.lcd.fpsminitv = ConfigSlider(default=30, limits=(0, 30))
			config.lcd.modeminitv.addNotifier(setLCDModeMinitTV)
			config.lcd.fpsminitv.addNotifier(setMiniTVFPS)
		else:
			config.lcd.modeminitv = ConfigNothing()
			config.lcd.screenshot = ConfigNothing()
			config.lcd.fpsminitv = ConfigNothing()
		if MODEL == "vuultimo":
			config.lcd.ledblinkingtime = ConfigSlider(default=5, increment=1, limits=(0, 15))
			config.lcd.ledblinkingtime.addNotifier(setLEDblinkingtime)
			config.lcd.ledbrightnessdeepstandby = ConfigSlider(default=1, increment=1, limits=(0, 15))
			config.lcd.ledbrightnessdeepstandby.addNotifier(setLEDnormalstate)
			config.lcd.ledbrightnessdeepstandby.addNotifier(setLEDdeepstandby)
			config.lcd.ledbrightnessdeepstandby.apply = lambda: setLEDdeepstandby(config.lcd.ledbrightnessdeepstandby)
			config.lcd.ledbrightnessstandby = ConfigSlider(default=1, increment=1, limits=(0, 15))
			config.lcd.ledbrightnessstandby.addNotifier(setLEDnormalstate)
			config.lcd.ledbrightnessstandby.apply = lambda: setLEDnormalstate(config.lcd.ledbrightnessstandby)
			config.lcd.ledbrightness = ConfigSlider(default=3, increment=1, limits=(0, 15))
			config.lcd.ledbrightness.addNotifier(setLEDnormalstate)
			config.lcd.ledbrightness.apply = lambda: setLEDnormalstate(config.lcd.ledbrightness)
			config.lcd.ledbrightness.callNotifiersOnSaveAndCancel = True
		else:
			def doNothing():
				pass

			config.lcd.ledbrightness = ConfigNothing()
			config.lcd.ledbrightness.apply = lambda: doNothing()
			config.lcd.ledbrightnessstandby = ConfigNothing()
			config.lcd.ledbrightnessstandby.apply = lambda: doNothing()
			config.lcd.ledbrightnessdeepstandby = ConfigNothing()
			config.lcd.ledbrightnessdeepstandby.apply = lambda: doNothing()
			config.lcd.ledblinkingtime = ConfigNothing()
	else:
		def doNothing():
			pass

		config.lcd.contrast = ConfigNothing()
		config.lcd.bright = ConfigNothing()
		config.lcd.standby = ConfigNothing()
		config.lcd.bright.apply = lambda: doNothing()
		config.lcd.standby.apply = lambda: doNothing()
		config.lcd.power = ConfigNothing()
		config.lcd.minitvdisplay = ConfigNothing()
		config.lcd.mode = ConfigNothing()
		config.lcd.hdd = ConfigNothing()
		config.lcd.scroll_speed = ConfigSelection(choices=[
			("500", _("Slow")),
			("300", _("Normal")),
			("100", _("Fast"))
		], default="300")
		config.lcd.scroll_delay = ConfigSelection(choices=[
			("10000", "10 %s" % _("Seconds")),
			("20000", "20 %s" % _("Seconds")),
			("30000", "30 %s" % _("Seconds")),
			("60000", "1 %s" % _("Minute")),
			("300000", "5 %s" % _("Minutes")),
			("noscrolling", _("Off"))
		], default="10000")
		config.lcd.showoutputresolution = ConfigNothing()
		config.lcd.ledbrightness = ConfigNothing()
		config.lcd.ledbrightness.apply = lambda: doNothing()
		config.lcd.ledbrightnessstandby = ConfigNothing()
		config.lcd.ledbrightnessstandby.apply = lambda: doNothing()
		config.lcd.ledbrightnessdeepstandby = ConfigNothing()
		config.lcd.ledbrightnessdeepstandby.apply = lambda: doNothing()
		config.lcd.ledblinkingtime = ConfigNothing()
		config.lcd.picon_pack = ConfigNothing()
	config.misc.standbyCounter.addNotifier(standbyCounterChanged, initial_call=False)
