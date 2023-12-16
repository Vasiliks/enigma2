from os import sys
from os.path import exists
from sys import maxsize
from twisted.internet import threads

from enigma import eActionMap, eDBoxLCD, eTimer

from Components.config import ConfigNothing, ConfigSelection, ConfigSlider, ConfigSubsection, ConfigOnOff, ConfigYesNo, config
from Components.SystemInfo import BoxInfo, SystemInfo
from Screens.InfoBar import InfoBar
from Screens.Screen import Screen
import Screens.Standby
from Tools.Directories import fileReadLine, fileWriteLine

model = BoxInfo.getItem("model")


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
		self.symbolNetwork = exists("/proc/stb/lcd/symbol_network")
		self.symbolUsb = exists("/proc/stb/lcd/symbol_usb")
		self.lcdMode = config.lcd.mode.value
		config.lcd.mode.addNotifier(self.setLCDmode)
		self.timer = eTimer()

	def setLCDmode(self, configElement):
		self.lcdMode = configElement.value

	def start(self):
		if self.iconcheck not in self.timer.callback:
			self.timer.callback.append(self.iconcheck)
		self.timer.startLongTimer(0)

	def stop(self):
		if self.iconcheck in self.timer.callback:
			self.timer.callback.remove(self.iconcheck)
		self.timer.stop()

	def iconcheck(self):
		threads.deferToThread(self.jobTask)

	def jobTask(self):
		if self.symbolNetwork and self.lcdMode:
			linkState = "0"
			if exists("/sys/class/net/wlan0/operstate"):
				linkState = fileReadLine("/sys/class/net/wlan0/operstate")
				if linkState != "down":
					linkState = fileReadLine("/sys/class/net/wlan0/carrier")
			elif exists("/sys/class/net/eth0/operstate"):
				linkState = fileReadLine("/sys/class/net/eth0/operstate")
				if linkState != "down":
					linkState = fileReadLine("/sys/class/net/eth0/carrier")
			fileWriteLine("/proc/stb/lcd/symbol_network", linkState)


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
		Screens.Standby.inStandby.onClose.append(self.leaveStandby)
		self.autoDimDownLCDTimer.stop()
		self.autoDimUpLCDTimer.stop()
		eActionMap.getInstance().unbindAction("", self.dimUpEvent)

	def leaveStandby(self):
		eActionMap.getInstance().bindAction("", -maxsize - 1, self.dimUpEvent)

	def dimUpEvent(self, key, flag):
		self.autoDimDownLCDTimer.stop()
		if not Screens.Standby.inTryQuitMainloop:
			if self.brightness is not None and not self.autoDimUpLCDTimer.isActive():
				self.autoDimUpLCDTimer.start(10, True)

	def autoDimDownLCD(self):
		if not Screens.Standby.inTryQuitMainloop:
			if self.dimBrightness is not None and self.currBrightness > self.dimBrightness:
				self.currBrightness = self.currBrightness - 1
				eDBoxLCD.getInstance().setLCDBrightness(self.currBrightness)
				self.autoDimDownLCDTimer.start(10, True)

	def autoDimUpLCD(self):
		if not Screens.Standby.inTryQuitMainloop:
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
			if exists("/proc/stb/lcd/symbol_hdd"):
				fileWriteLine("/proc/stb/lcd/symbol_hdd", "0")
			if exists("/proc/stb/lcd/symbol_hddprogress"):
				fileWriteLine("/proc/stb/lcd/symbol_hddprogress", "0")
			if exists("/proc/stb/lcd/symbol_network"):
				fileWriteLine("/proc/stb/lcd/symbol_network", "0")
			if exists("/proc/stb/lcd/symbol_signal"):
				fileWriteLine("/proc/stb/lcd/symbol_signal", "0")
			if exists("/proc/stb/lcd/symbol_timeshift"):
				fileWriteLine("/proc/stb/lcd/symbol_timeshift", "0")
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
		if exists("/proc/stb/fb/sd_detach"):
			print("[Lcd] setfblcddisplay='%s'." % value)
			fileWriteLine("/proc/stb/fb/sd_detach", value)

	def setRepeat(self, value):
		if exists("/proc/stb/lcd/scroll_repeats"):
			print("[Lcd] setLCDRepeat='%s'." % value)
			fileWriteLine("/proc/stb/lcd/scroll_repeats", value)

	def setScrollspeed(self, value):
		if exists("/proc/stb/lcd/scroll_delay"):
			print("[Lcd] setLCDScrollspeed='%s'." % value)
			fileWriteLine("/proc/stb/lcd/scroll_delay", value)

	def setLEDNormalState(self, value):
		eDBoxLCD.getInstance().setLED(value, 0)

	def setLEDDeepStandbyState(self, value):
		eDBoxLCD.getInstance().setLED(value, 1)

	def setLEDBlinkingTime(self, value):
		eDBoxLCD.getInstance().setLED(value, 2)


def leaveStandby():
	config.lcd.bright.apply()
	if model == "vuultimo":
		config.lcd.ledbrightness.apply()
		config.lcd.ledbrightnessdeepstandby.apply()


def standbyCounterChanged(configElement):
	Screens.Standby.inStandby.onClose.append(leaveStandby)
	config.lcd.standby.apply()
	config.lcd.ledbrightnessstandby.apply()
	config.lcd.ledbrightnessdeepstandby.apply()


def InitLcd():
	detected = eDBoxLCD.getInstance().detected()
	SystemInfo["Display"] = detected
	config.lcd = ConfigSubsection()
	if exists("/proc/stb/lcd/mode"):
		can_lcdmodechecking = fileReadLine("/proc/stb/lcd/mode")
	else:
		can_lcdmodechecking = False
	SystemInfo["LCDMiniTV"] = can_lcdmodechecking
	if detected:
		ilcd = LCD()
		if can_lcdmodechecking:
			def setLCDModeMinitTV(configElement):
				print(f"[Lcd] setLCDModeMinitTV='{configElement.value}'.")
				fileWriteLine("/proc/stb/lcd/mode", configElement.value)

			def setMiniTVFPS(configElement):
				print("[Lcd] setMiniTVFPS='%s'." % configElement.value)
				fileWriteLine("/proc/stb/lcd/fps", configElement.value)

			def setLCDModePiP(configElement):
				pass  # DEBUG: Should this be doing something?

			config.lcd.modepip = ConfigSelection(choices={
				"0": _("Off"),
				"5": _("PIP"),
				"7": _("PIP with OSD")
			}, default="0")
			config.lcd.modepip.addNotifier(setLCDModePiP)
			config.lcd.modeminitv = ConfigSelection(choices={
				"0": _("Normal"),
				"1": _("MiniTV"),
				"2": _("OSD"),
				"3": _("MiniTV with OSD")
			}, default="0")
			config.lcd.fpsminitv = ConfigSlider(default=30, limits=(0, 30))
			config.lcd.modeminitv.addNotifier(setLCDModeMinitTV)
			config.lcd.fpsminitv.addNotifier(setMiniTVFPS)
		else:
			config.lcd.modeminitv = ConfigNothing()
			config.lcd.fpsminitv = ConfigNothing()
		config.lcd.scroll_speed = ConfigSelection(choices=[
			("500", _("Slow")),
			("300", _("Normal")),
			("100", _("Fast"))
		], default="300")
		config.lcd.scroll_delay = ConfigSelection(choices=[
			("10000", "10 %s" % _("seconds")),
			("20000", "20 %s" % _("seconds")),
			("30000", "30 %s" % _("seconds")),
			("60000", "1 %s" % _("minute")),
			("300000", "5 %s" % _("minutes")),
			("noscrolling", _("Off"))
		], default="10000")

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

		def setfblcddisplay(configElement):
			ilcd.setfblcddisplay(configElement.value)

		def setLCDshowoutputresolution(configElement):
			ilcd.setShowoutputresolution(configElement.value)

		def setLEDnormalstate(configElement):
			ilcd.setLEDNormalState(configElement.value)

		def setLEDdeepstandby(configElement):
			ilcd.setLEDDeepStandbyState(configElement.value)

		def setLEDblinkingtime(configElement):
			ilcd.setLEDBlinkingTime(configElement.value)

		def setLedPowerColor(configElement):
			fileWriteLine("/proc/stb/fp/ledpowercolor", configElement.value)

		def setLedStandbyColor(configElement):
			fileWriteLine("/proc/stb/fp/ledstandbycolor", configElement.value)

		def setLedSuspendColor(configElement):
			fileWriteLine("/proc/stb/fp/ledsuspendledcolor", configElement.value)

		def setLedBlinkControlColor(configElement):
			if exists("/proc/stb/fp/led_blink"):
				fileWriteLine("/proc/stb/fp/led_blink", configElement.value)

		def setLedBrightnessControl(configElement):
			if exists("/proc/stb/fp/led_brightness"):
				fileWriteLine("/proc/stb/fp/led_brightness", configElement.value)

		def setLedColorControlColor(configElement):
			if exists("/proc/stb/fp/led_color"):
				fileWriteLine("/proc/stb/fp/led_color", configElement.value)

		def setLedFadeControlColor(configElement):
			if exists("/proc/stb/fp/led_fade"):
				fileWriteLine("/proc/stb/fp/led_fade", configElement.value)

		def setPower4x7On(configElement):
			fileWriteLine("/proc/stb/fp/power4x7on", "on" if configElement.value else "off")

		def setPower4x7Standby(configElement):
			fileWriteLine("/proc/stb/fp/power4x7standby", "on" if configElement.value else "off")

		def setPower4x7Suspend(configElement):
			fileWriteLine("/proc/stb/fp/power4x7suspend", "on" if configElement.value else "off")

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

		choices = [("0", _("off")), ("1", _("blue"))] if model == "dual" else [("0", _("Off")), ("1", _("blue")), ("2", _("red")), ("3", _("violet"))]

		config.usage.lcd_ledpowercolor = ConfigSelection(default="1", choices=choices)
		if exists("/proc/stb/fp/ledpowercolor"):
			config.usage.lcd_ledpowercolor.addNotifier(setLedPowerColor)
		config.usage.lcd_ledstandbycolor = ConfigSelection(default="1" if model == "dual" else "3", choices=choices)
		if exists("/proc/stb/fp/ledstandbycolor"):
			config.usage.lcd_ledstandbycolor.addNotifier(setLedStandbyColor)
		config.usage.lcd_ledsuspendcolor = ConfigSelection(default="1" if model == "dual" else "2", choices=choices)
		if exists("/proc/stb/fp/ledsuspendledcolor"):
			config.usage.lcd_ledsuspendcolor.addNotifier(setLedSuspendColor)

		config.usage.lcd_power4x7on = ConfigOnOff(default=True)
		if exists("/proc/stb/fp/power4x7on"):
			config.usage.lcd_power4x7on.addNotifier(setPower4x7On)

		config.usage.lcd_power4x7standby = ConfigOnOff(default=True)
		if exists("/proc/stb/fp/power4x7standby"):
			config.usage.lcd_power4x7standby.addNotifier(setPower4x7Standby)

		config.usage.lcd_power4x7suspend = ConfigOnOff(default=True)
		if exists("/proc/stb/fp/power4x7suspend"):
			config.usage.lcd_power4x7suspend.addNotifier(setPower4x7Suspend)

		if model in ('dm900', 'dm920'):
			standby_default = 4
		else:
			standby_default = 1
		if not ilcd.isOled():
			config.lcd.contrast = ConfigSlider(default=5, limits=(0, 20))
			config.lcd.contrast.addNotifier(setLCDcontrast)
		else:
			config.lcd.contrast = ConfigNothing()
		config.lcd.standby = ConfigSlider(default=standby_default, limits=(0, 10))
		config.lcd.dimbright = ConfigSlider(default=standby_default, limits=(0, 10))
		config.lcd.bright = ConfigSlider(default=SystemInfo["DefaultDisplayBrightness"], limits=(0, 10))
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
		LcdLiveTV = SystemInfo["LcdLiveTV"]
		if LcdLiveTV:
			def lcdLiveTvChanged(configElement):
				if "live_enable" in LcdLiveTV:
					fileWriteLine(LcdLiveTV, configElement.value and "enable" or "disable")
				else:
					fileWriteLine(LcdLiveTV, configElement.value and "0" or "1")
				try:
					InfoBarInstance = InfoBar.instance
					InfoBarInstance and InfoBarInstance.session.open(dummyScreen)
				except Exception:
					pass

			config.lcd.showTv = ConfigYesNo(default=False)
			config.lcd.showTv.addNotifier(lcdLiveTvChanged)

		VFD_scroll_repeats = SystemInfo["VFD_scroll_repeats"]
		if VFD_scroll_repeats:
			def scroll_repeats(configElement):
				eDBoxLCD.getInstance().set_VFD_scroll_repeats(int(configElement.value))

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
		VFD_scroll_delay = SystemInfo["VFD_scroll_delay"]
		if VFD_scroll_delay:
			def scroll_delay(configElement):
				eDBoxLCD.getInstance().set_VFD_scroll_delay(int(configElement.value))

			config.usage.vfd_scroll_delay = ConfigSlider(default=150, increment=10, limits=(0, 500))
			config.usage.vfd_scroll_delay.addNotifier(scroll_delay, immediate_feedback=False)
			config.lcd.hdd = ConfigYesNo(default=True)
		else:
			config.lcd.hdd = ConfigNothing()
			config.usage.vfd_scroll_delay = ConfigNothing()
		VFD_initial_scroll_delay = SystemInfo["VFD_initial_scroll_delay"]
		if VFD_initial_scroll_delay:
			def initial_scroll_delay(configElement):
				eDBoxLCD.getInstance().set_VFD_initial_scroll_delay(int(configElement.value))

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
		VFD_final_scroll_delay = SystemInfo["VFD_final_scroll_delay"]
		if VFD_final_scroll_delay:
			def final_scroll_delay(configElement):
				eDBoxLCD.getInstance().set_VFD_final_scroll_delay(int(configElement.value))

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
		if exists("/proc/stb/fb/sd_detach"):
			config.lcd.fblcddisplay = ConfigSelection(choices=[
				("1", _("No")),
				("0", _("Yes"))
			], default="1")
			config.lcd.fblcddisplay.addNotifier(setfblcddisplay)
		else:
			config.lcd.fblcddisplay = ConfigNothing()
		if exists("/proc/stb/lcd/show_outputresolution"):
			config.lcd.showoutputresolution = ConfigSelection(choices=[
				("0", _("No")),
				("1", _("Yes"))
			], default="1")
			config.lcd.showoutputresolution.addNotifier(setLCDshowoutputresolution)
		else:
			config.lcd.showoutputresolution = ConfigNothing()
		if model == "vuultimo":
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
		config.lcd.dimbright = ConfigNothing()
		config.lcd.dimdelay = ConfigNothing()
		config.lcd.standby = ConfigNothing()
		config.lcd.bright.apply = lambda: doNothing()
		config.lcd.standby.apply = lambda: doNothing()
		config.lcd.power = ConfigNothing()
		config.lcd.fblcddisplay = ConfigNothing()
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

	def setPowerLEDstate(configElement):
		fileWriteLine("/proc/stb/power/powerled", "on" if configElement.value else "off")

	def setPowerLEDstate2(configElement):
		fileWriteLine("/proc/stb/power/powerled2", "on" if configElement.value else "off")

	def setPowerLEDstanbystate(configElement):
		fileWriteLine("/proc/stb/power/standbyled", "on" if configElement.value else "off")

	def setPowerLEDdeepstanbystate(configElement):
		fileWriteLine("/proc/stb/power/suspendled", "on" if configElement.value else "off")

	if BoxInfo.getItem("PowerLed"):
		config.usage.lcd_powerled = ConfigOnOff(default=True)
		config.usage.lcd_powerled.addNotifier(setPowerLEDstate)
	if BoxInfo.getItem("PowerLed2"):
		config.usage.lcd_powerled2 = ConfigOnOff(default=True)
		config.usage.lcd_powerled2.addNotifier(setPowerLEDstate2)
	if BoxInfo.getItem("StandbyPowerLed"):
		config.usage.lcd_standbypowerled = ConfigOnOff(default=True)
		config.usage.lcd_standbypowerled.addNotifier(setPowerLEDstanbystate)
	if BoxInfo.getItem("SuspendPowerLed"):
		config.usage.lcd_deepstandbypowerled = ConfigOnOff(default=True)
		config.usage.lcd_deepstandbypowerled.addNotifier(setPowerLEDdeepstanbystate)

	config.misc.standbyCounter.addNotifier(standbyCounterChanged, initial_call=False)
