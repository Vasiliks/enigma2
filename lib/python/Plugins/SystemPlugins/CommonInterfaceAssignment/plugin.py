from os import remove, unlink
from os.path import exists
from xml.etree.ElementTree import parse

from enigma import eDVBCI_UI, eDVBCIInterfaces, eEnv, eServiceCenter, eServiceReference


from Components.ActionMap import ActionMap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.config import ConfigNothing
from Components.ConfigList import ConfigList
from Components.Label import Label
from Components.SelectionList import SelectionList
from Components.MenuList import MenuList
from Components.SystemInfo import SystemInfo
from Plugins.Plugin import PluginDescriptor
from Screens.ChannelSelection import *
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from ServiceReference import ServiceReference
from Tools.BoundFunction import boundFunction
from Tools.CIHelper import cihelper
from Tools.XMLTools import stringToXML


class CIselectMainMenu(Screen):
	skin = """
		<screen name="CIselectMainMenu" position="center,center" size="500,250" title="CI assignment" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphaTest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#1f771f" transparent="1" />
			<widget name="CiList" position="5,50" size="490,200" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, args=0):
		Screen.__init__(self, session)
		self.setTitle(_("CI assignment"))
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Edit"))
		self["actions"] = ActionMap(["ColorActions", "SetupActions"],
			{
				"green": self.greenPressed,
				"red": self.close,
				"ok": self.greenPressed,
				"cancel": self.close
		}, -1)

		NUM_CI = SystemInfo["CommonInterface"]

		print(f"[CI_Wizzard] FOUND {NUM_CI} CI Slots")

		self.dlg = None
		self.state = {}
		self.list = []
		if NUM_CI and NUM_CI > 0:
			for slot in range(NUM_CI):
				state = eDVBCI_UI.getInstance().getState(slot)
				if state != -1:
					appname = _("Slot %d") % (slot + 1) + " - "
					if state == 0:
						appname += _("no module found")
					elif state == 1:
						appname += _("init modules")
					elif state == 2:
						appname += eDVBCI_UI.getInstance().getAppName(slot)
					elif state == 3:
						appname += _("module disabled")
					else:
						appname += _("unknown error")
					self.list.append((appname, ConfigNothing(), 0, slot))
		else:
			self.list.append((_("no CI slots found"), ConfigNothing(), 1, -1))
		menuList = ConfigList(self.list)
		menuList.list = self.list
		menuList.l.setList(self.list)
		self["CiList"] = menuList

	def greenPressed(self):
		cur = self["CiList"].getCurrent()
		if cur and len(cur) > 2:
			action = cur[2]
			slot = cur[3]
			if action == 1:
				print("[CI_Wizzard] there is no CI Slot in your receiver")
			else:
				print(f"[CI_Wizzard] selected CI Slot : {slot}")
				if config.usage.setup_level.index > 1:  # advanced
					self.session.open(CIconfigMenu, slot)
				else:
					self.session.open(easyCIconfigMenu, slot)


class CIconfigMenu(Screen):
	skin = """
		<screen name="CIconfigMenu" position="center,center" size="560,440" title="CI assignment" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphaTest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;18" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;18" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;18" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#a08500" transparent="1" />
			<widget source="key_blue" render="Label" position="420,0" zPosition="1" size="140,40" font="Regular;18" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#18188b" transparent="1" />
			<widget source="CAidList_desc" render="Label" position="5,50" size="550,22" font="Regular;20"  backgroundColor="#25062748" transparent="1" />
			<widget source="CAidList" render="Label" position="5,80" size="550,45" font="Regular;20"  backgroundColor="#25062748" transparent="1" />
			<ePixmap pixmap="skin_default/div-h.png" position="0,125" zPosition="1" size="560,2" />
			<widget source="ServiceList_desc" render="Label" position="5,130" size="550,22" font="Regular;20" backgroundColor="#25062748" transparent="1"  />
			<widget name="ServiceList" position="5,160" size="550,250" zPosition="1" scrollbarMode="showOnDemand" />
			<widget source="ServiceList_info" render="Label" position="5,160" size="550,250" zPosition="2" font="Regular;20" backgroundColor="#25062748" transparent="1"  />
		</screen>"""

	def __init__(self, session, ci_slot="9"):

		Screen.__init__(self, session)
		self.setTitle(_("CI assignment"))
		self.ci_slot = ci_slot
		self.filename = eEnv.resolve("${sysconfdir}/enigma2/ci") + f"{self.ci_slot}.xml"

		self["key_red"] = StaticText(_("Delete"))
		self["key_green"] = StaticText(_("Add service"))
		self["key_yellow"] = StaticText(_("Add provider"))
		self["key_blue"] = StaticText(_("Select CAId"))
		self["CAidList_desc"] = StaticText(_("Assigned CAIds:"))
		self["CAidList"] = StaticText()
		self["ServiceList_desc"] = StaticText(_("Assigned services/provider:"))
		self["ServiceList_info"] = StaticText()

		self["actions"] = ActionMap(["ColorActions", "SetupActions", "MenuActions"],
			{
			"green": self.greenPressed,
			"red": self.redPressed,
			"yellow": self.yellowPressed,
			"blue": self.bluePressed,
			"menu": self.menuPressed,
			"cancel": self.cancel
		}, -1)

		print(f"[CI_Wizzard_Config] Configuring CI Slots : {self.ci_slot}")

		i = 0
		self.caidlist = []
		for caid in eDVBCIInterfaces.getInstance().readCICaIds(self.ci_slot):
			i += 1
			self.caidlist.append((str(hex(int(caid))), str(caid), i))

		print(f"[CI_Wizzard_Config_CI{self.ci_slot}] read following CAIds from CI: {self.caidlist}")

		self.selectedcaid = []
		self.servicelist = []
		self.caids = ""

		serviceList = ConfigList(self.servicelist)
		serviceList.list = self.servicelist
		serviceList.l.setList(self.servicelist)
		self["ServiceList"] = serviceList

		self.loadXML()
		# if config mode !=advanced autoselect any caid
		if config.usage.setup_level.index <= 1:  # advanced
			self.selectedcaid = self.caidlist
			self.finishedCAidSelection(self.selectedcaid)

	def redPressed(self):
		self.delete()

	def greenPressed(self):
		self.session.openWithCallback(self.finishedChannelSelection, myChannelSelection, None)

	def yellowPressed(self):
		self.session.openWithCallback(self.finishedProviderSelection, myProviderSelection, None)

	def bluePressed(self):
		self.session.openWithCallback(self.finishedCAidSelection, CAidSelect, self.caidlist, self.selectedcaid)

	def menuPressed(self):
		if exists(self.filename):
			self.session.openWithCallback(self.deleteXMLfile, MessageBox, _("Delete file") + f" {self.filename}?", MessageBox.TYPE_YESNO)

	def deleteXMLfile(self, answer):
		if answer:
			try:
				remove(self.filename)
			except OSError:
				print(f"[CI_Config_CI{self.ci_slot}] error remove xml...")
			else:
				self.session.openWithCallback(self.restartGui, MessageBox, _("Restart GUI now?"), MessageBox.TYPE_YESNO)

	def restartGui(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)

	def cancel(self):
		self.saveXML()
		cihelper.load_ci_assignment(force=True)
		self.close()

	def setServiceListInfo(self):
		if len(self.servicelist):
			self["ServiceList_info"].setText("")
		else:
			self["ServiceList_info"].setText(_("No services/providers selected"))

	def delete(self):
		cur = self["ServiceList"].getCurrent()
		if cur and len(cur) > 2:
			self.servicelist.remove(cur)
		self["ServiceList"].l.setList(self.servicelist)
		self.setServiceListInfo()

	def finishedChannelSelection(self, *args):
		item = len(args)
		if item > 0:
			if item > 2 and args[2]:
				for ref in args[0]:
					service_ref = ServiceReference(ref)
					service_name = service_ref.getServiceName()
					if len(service_name) and not find_in_list(self.servicelist, service_name, 0):
						str_service = service_ref.ref.toString()
						split_ref = str_service.split(":")
						if split_ref[0] == "1" and not str_service.startswith("1:134:") and "%3a//" not in str_service:
							self.servicelist.append((service_name, ConfigNothing(), 0, str_service))
				self["ServiceList"].l.setList(self.servicelist)
				self.setServiceListInfo()
			else:
				ref = args[0]
				if ref:
					service_ref = ServiceReference(ref)
					service_name = service_ref.getServiceName()
					if not find_in_list(self.servicelist, service_name, 0):
						str_service = service_ref.ref.toString()
						split_ref = str_service.split(":")
						if split_ref[0] == "1" and not str_service.startswith("1:134:") and "%3a//" not in str_service:
							self.servicelist.append((service_name, ConfigNothing(), 0, str_service))
							self["ServiceList"].l.setList(self.servicelist)
							self.setServiceListInfo()

	def finishedProviderSelection(self, *args):
		item = len(args)
		if item > 1:
			if item > 2 and args[2]:
				for ref in args[0]:
					service_ref = ServiceReference(ref)
					service_name = service_ref.getServiceName()
					if len(service_name) and not find_in_list(self.servicelist, service_name, 0):
						split_ref = service_ref.ref.toString().split(":")
						if split_ref[0] == "1":
							self.servicelist.append((service_name, ConfigNothing(), 0, service_ref.ref.toString()))
				self["ServiceList"].l.setList(self.servicelist)
				self.setServiceListInfo()
			else:
				name = args[0]
				dvbnamespace = args[1]
				if not find_in_list(self.servicelist, name, 0):
					self.servicelist.append((name, ConfigNothing(), 1, dvbnamespace))
					self["ServiceList"].l.setList(self.servicelist)
					self.setServiceListInfo()

	def finishedCAidSelection(self, *args):
		if len(args):
			self.selectedcaid = args[0]
			self.caids = ""
			if len(self.selectedcaid):
				for item in self.selectedcaid:
					if len(self.caids):
						self.caids += ", " + item[0]
					else:
						self.caids = item[0]
			else:
				self.selectedcaid = []
				self.caids = _("no CAId selected")
		else:
			self.selectedcaid = []
			self.caids = _("no CAId selected")
		self["CAidList"].setText(self.caids)

	def saveXML(self):
		try:
			with open(self.filename, "w") as fd:
				fd.write("<?xml version=\"1.0\" encoding=\"utf-8\" ?>\n")
				fd.write("<ci>\n")
				fd.write("\t<slot>\n")
				fd.write(f"\t\t<id>{self.ci_slot}</id>\n")
				for item in self.selectedcaid:
					fd.write("\t\t<caid id=\"%s\" />\n" % item[0])
				for item in self.servicelist:
					name = item[0].replace('<', '&lt;')
					name = name.replace('&', '&amp;')
					name = name.replace('>', '&gt;')
					name = name.replace('"', '&quot;')
					name = name.replace("'", '&apos;')
					if item[2] == 1:
						fd.write("\t\t<provider name=\"%s\" dvbnamespace=\"%s\" />\n" % (stringToXML(name), item[3]))
					else:
						fd.write("\t\t<service name=\"%s\" ref=\"%s\" />\n" % (stringToXML(name), ':'.join(item[3].split(':')[:11])))
				fd.write("\t</slot>\n")
				fd.write("</ci>\n")
		except OSError:
			print(f"[CI_Config_CI{self.ci_slot}] xml not written")
			unlink(self.filename)

	def loadXML(self):
		if not exists(self.filename):
			self.setServiceListInfo()
			return

		def getValue(definitions, default):
			Len = len(definitions)
			return Len > 0 and definitions[Len - 1].text or default
		self.read_services = []
		self.read_providers = []
		self.usingcaid = []
		self.ci_config = []
		try:
			tree = parse(self.filename).getroot()
			for slot in tree.findall("slot"):
				read_slot = getValue(slot.findall("id"), False)
				i = 0
				for caid in slot.findall("caid"):
					read_caid = caid.get("id")  # .encode("UTF-8")
					self.selectedcaid.append((str(read_caid), str(read_caid), i))
					self.usingcaid.append(int(read_caid, 16))
					i += 1

				for service in slot.findall("service"):
					# read_service_name = service.get("name")
					read_service_ref = service.get("ref")
					self.read_services.append(read_service_ref)

				for provider in slot.findall("provider"):
					read_provider_name = provider.get("name")
					read_provider_dvbname = provider.get("dvbnamespace")
					self.read_providers.append((read_provider_name, read_provider_dvbname))
				self.ci_config.append((int(read_slot), (self.read_services, self.read_providers, self.usingcaid)))
		except:
			print("[CI_Config_CI%d] error parsing xml..." % self.ci_slot)
			try:
				remove(self.filename)
			except OSError:
				print("[CI_Activate_Config_CI%d] error remove damaged xml..." % self.ci_slot)

		for item in self.read_services:
			if len(item):
				self.finishedChannelSelection(item)

		for item in self.read_providers:
			if len(item):
				self.finishedProviderSelection(item[0], item[1])

		self.finishedCAidSelection(self.selectedcaid)
		self["ServiceList"].l.setList(self.servicelist)
		self.setServiceListInfo()


class easyCIconfigMenu(CIconfigMenu):
	skin = """
		<screen name="easyCIconfigMenu" position="center,center" size="560,440" title="CI assignment" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphaTest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;19" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;19" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;19" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#a08500" transparent="1" />
			<widget source="ServiceList_desc" render="Label" position="5,50" size="550,22" font="Regular;20" backgroundColor="#25062748" transparent="1"  />
			<widget name="ServiceList" position="5,80" size="550,300" zPosition="1" scrollbarMode="showOnDemand" />
			<widget source="ServiceList_info" render="Label" position="5,80" size="550,300" zPosition="2" font="Regular;20" backgroundColor="#25062748" transparent="1"  />
		</screen>"""

	def __init__(self, session, ci_slot="9"):
		CIconfigMenu.__init__(self, session, ci_slot)
		self["actions"] = ActionMap(["ColorActions", "SetupActions", "MenuActions"],
			{
			"green": self.greenPressed,
			"red": self.redPressed,
			"yellow": self.yellowPressed,
			"menu": self.menuPressed,
			"cancel": self.cancel
		}, -1)


class CAidSelect(Screen):
	skin = """
		<screen name="CAidSelect" position="center,center" size="450,440" title="select CAId's" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphaTest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#1f771f" transparent="1" />
			<widget name="list" position="5,50" size="440,330" scrollbarMode="showOnDemand" />
			<ePixmap pixmap="skin_default/div-h.png" position="0,390" zPosition="1" size="450,2" />
			<widget source="introduction" render="Label" position="0,400" size="450,40" zPosition="10" font="Regular;21" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#25062748" transparent="1" />
		</screen>"""

	def __init__(self, session, list, selected_caids):

		Screen.__init__(self, session)
		self.setTitle(_("select CAId's"))

		self.list = SelectionList()
		self["list"] = self.list

		for listindex in range(len(list)):
			if find_in_list(selected_caids, list[listindex][0], 0):
				self.list.addSelection(list[listindex][0], list[listindex][1], listindex, True)
			else:
				self.list.addSelection(list[listindex][0], list[listindex][1], listindex, False)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["introduction"] = StaticText(_("Press OK to select/deselect a CAId."))

		self["actions"] = ActionMap(["ColorActions", "SetupActions"],
		{
			"ok": self.list.toggleSelection,
			"cancel": self.cancel,
			"green": self.greenPressed,
			"red": self.cancel
		}, -1)

	def greenPressed(self):
		list = self.list.getSelectionsList()
		self.close(list)

	def cancel(self):
		self.close()


class myProviderSelection(ChannelSelectionBase):
	skin = """
		<screen name="myProviderSelection" position="center,center" size="560,440" title="Select provider to add...">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphaTest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#a08500" transparent="1" />
			<widget source="key_blue" render="Label" position="420,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#18188b" transparent="1" />
			<widget name="list" position="5,50" size="550,330" scrollbarMode="showOnDemand" />
			<ePixmap pixmap="skin_default/div-h.png" position="0,390" zPosition="1" size="560,2" />
			<widget source="introduction" render="Label" position="0,400" size="560,40" zPosition="10" font="Regular;21" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#25062748" transparent="1" />
		</screen>"""

	def __init__(self, session, title):
		ChannelSelectionBase.__init__(self, session)
		self.setTitle(_("Select provider to add..."))
		self.onShown.append(self.showSatellites)
		self.bouquet_mark_edit = EDIT_BOUQUET

		self["actions"] = ActionMap(["OkCancelActions", "ChannelSelectBaseActions"],
			{
			"showFavourites": self.showFavourites,
			"showAllServices": self.showAllServices,
			"showProviders": self.showProviders,
			"showSatellites": boundFunction(self.showSatellites, changeMode=True),
			"cancel": self.cancel,
			"ok": self.channelSelected
		})
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText()
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["introduction"] = StaticText(_("Press OK to select a provider."))

	def showProviders(self):
		pass

	def showAllServices(self):
		self.close(None)

	def showFavourites(self):
		pass

	def channelSelected(self):  # just return selected service
		ref = self.getCurrentSelection()
		if ref is None:
			return
		if not (ref.flags & 64):
			splited_ref = ref.toString().split(":")
			if ref.flags == 7 and splited_ref[6] != "0":
				self.dvbnamespace = splited_ref[6]
				self.enterPath(ref)
			elif (ref.flags & 7) == 7 and 'provider' in ref.toString():
				menu = [(_("Provider"), "provider"), (_("All services provider"), "providerlist")]

				def addAction(choice):
					if choice is not None:
						if choice[1] == "provider":
							self.close(ref.getName(), self.dvbnamespace)
						elif choice[1] == "providerlist":
							serviceHandler = eServiceCenter.getInstance()
							servicelist = serviceHandler.list(ref)
							if servicelist:
								providerlist = []
								while True:
									service = servicelist.getNext()
									if not service.valid():
										break
									providerlist.append((service))
								if providerlist:
									self.close(providerlist, self.dvbnamespace, True)
								else:
									self.close(None)
				self.session.openWithCallback(addAction, ChoiceBox, title=_("Select action"), list=menu)

	def showSatellites(self, changeMode=False):
		if changeMode:
			return
		if not self.pathChangeDisabled:
			refstr = '%s FROM SATELLITES ORDER BY satellitePosition' % (self.service_types)
			if not self.preEnterPath(refstr):
				ref = eServiceReference(refstr)
				justSet = False
				prev = None

				if self.isBasePathEqual(ref):
					if self.isPrevPathEqual(ref):
						justSet = True
					prev = self.pathUp(justSet)
				else:
					currentRoot = self.getRoot()
					if currentRoot is None or currentRoot != ref:
						justSet = True
						self.clearPath()
						self.enterPath(ref, True)
				if justSet:
					serviceHandler = eServiceCenter.getInstance()
					servicelist = serviceHandler.list(ref)
					if servicelist:
						while True:
							service = servicelist.getNext()
							if not service.valid():  # check if end of list
								break
							unsigned_orbpos = service.getUnsignedData(4) >> 16
							orbpos = service.getData(4) >> 16
							if orbpos < 0:
								orbpos += 3600
							if service.getPath().find("FROM PROVIDER") != -1:
								service_type = _("Providers")
								try:
									# why we need this cast?
									service_name = str(nimmanager.getSatDescription(orbpos))
								except:
									if unsigned_orbpos == 0xFFFF:  # Cable
										service_name = _("Cable")
									elif unsigned_orbpos == 0xEEEE:  # Terrestrial
										service_name = _("Terrestrial")
									else:
										if orbpos > 1800:  # west
											orbpos = 3600 - orbpos
											h = _("W")
										else:
											h = _("E")
										service_name = ("%d.%d" + h) % (orbpos / 10, orbpos % 10)
								service.setName("%s - %s" % (service_name, service_type))
								self.servicelist.addService(service)
						self.servicelist.finishFill()
						if prev is not None:
							self.setCurrentSelection(prev)

	def cancel(self):
		self.close(None)


class myChannelSelection(ChannelSelectionBase):
	skin = """
		<screen name="myChannelSelection" position="center,center" size="560,440" title="Select service to add...">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphaTest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphaTest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#a08500" transparent="1" />
			<widget source="key_blue" render="Label" position="420,0" zPosition="1" size="140,40" font="Regular;20" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#18188b" transparent="1" />
			<widget name="list" position="5,50" size="550,330" scrollbarMode="showOnDemand" />
			<ePixmap pixmap="skin_default/div-h.png" position="0,390" zPosition="1" size="560,2" />
			<widget source="introduction" render="Label" position="0,400" size="560,40" zPosition="10" font="Regular;21" horizontalAlignment="center" verticalAlignment="center" backgroundColor="#25062748" transparent="1" />
		</screen>"""

	def __init__(self, session, title):
		ChannelSelectionBase.__init__(self, session)
		self.setTitle(_("Select service to add..."))
		self.onShown.append(self.__onExecCallback)
		self.bouquet_mark_edit = 0

		self["actions"] = ActionMap(["OkCancelActions", "TvRadioActions", "ChannelSelectBaseActions"],
			{
			"showProviders": self.showProviders,
			"showSatellites": boundFunction(self.showSatellites, changeMode=True),
			"showAllServices": self.showAllServices,
			"cancel": self.cancel,
			"ok": self.channelSelected,
			"keyRadio": self.setModeRadio,
			"keyTV": self.setModeTv
		})

		self["key_red"] = StaticText(_("All"))
		self["key_green"] = StaticText(_("Close"))
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText(_("Favorites"))
		self["introduction"] = StaticText(_("Press OK to select a service."))

	def __onExecCallback(self):
		self.setModeTv()
		self.isFavourites()

	def isFavourites(self):
		ref = self.getCurrentSelection()
		if ref:
			if (ref.flags & 7) == 7 and "FROM BOUQUET" in ref.toString():
				self["key_yellow"].setText(_("Add bouquet"))
				return True
			else:
				self["key_yellow"].setText("")
		return False

	def showFavourites(self):
		ChannelSelectionBase.showFavourites(self)
		self.isFavourites()

	def showProviders(self):
		if self.isFavourites():
			self.session.openWithCallback(self.addAllBouquet, MessageBox, _("Add services to this bouquet?"), MessageBox.TYPE_YESNO)

	def addAllBouquet(self, answer):
		ref = self.getCurrentSelection()
		if answer and ref:
			serviceHandler = eServiceCenter.getInstance()
			servicelist = serviceHandler.list(ref)
			if servicelist:
				providerlist = []
				while True:
					service = servicelist.getNext()
					if not service.valid():
						break
					providerlist.append((service))
				if providerlist:
					self.close(providerlist, None, True)
				else:
					self.close(None)

	def showAllServices(self):
		ChannelSelectionBase.showAllServices(self)
		self.isFavourites()

	def showSatellites(self, changeMode=False):
		if changeMode:
			self.close(None)

	def channelSelected(self):  # just return selected service
		ref = self.getCurrentSelection()
		if (ref.flags & 7) == 7:
			self.enterPath(ref)
			self.isFavourites()
		elif not (ref.flags & eServiceReference.isMarker):
			ref = self.getCurrentSelection()
			self.close(ref)

	def setModeTv(self):
		self.setTvMode()
		self.showFavourites()

	def setModeRadio(self):
		self.setRadioMode()
		self.showFavourites()

	def cancel(self):
		self.close(None)


def activate_all(session):
	cihelper.load_ci_assignment()


def find_in_list(list, search, listpos=0):
	for item in list:
		if item[listpos] == search:
			return True
	return False


def isModule():
	NUM_CI = SystemInfo["CommonInterface"]
	if NUM_CI and NUM_CI > 0:
		for slot in range(NUM_CI):
			state = eDVBCI_UI.getInstance().getState(slot)
			if state > 0:
				return True
	return False


global_session = None


def sessionstart(reason, session):
	global global_session
	global_session = session


def autostart(reason, **kwargs):
	global global_session
	if reason == 0:
		print("[CI_Assignment] activating ci configs:")
		activate_all(global_session)
	elif reason == 1:
		global_session = None


def main(session, **kwargs):
	session.open(CIselectMainMenu)


def menu(menuid, **kwargs):
	if menuid == "cam" and isModule():
		return [(_("Common Interface Assignment"), main, "ci_assign", 11)]
	return []


def Plugins(**kwargs):
	description = _("a gui to assign services/providers to common interface modules")
	if config.usage.setup_level.index > 1:
		description = _("a gui to assign services/providers/caids to common interface modules")
	return [PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, needsRestart=False, fnc=sessionstart),
			PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, needsRestart=False, fnc=autostart),
			PluginDescriptor(name=_("Common Interface assignment"), description=description, where=PluginDescriptor.WHERE_MENU, needsRestart=False, fnc=menu)]
