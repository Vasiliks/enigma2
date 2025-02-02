# -*- coding: utf-8 -*-
#
# Generic Screen to select a path/filename combination
#

# GUI (Screens)
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.InputBox import InputBox
from Screens.HelpMenu import HelpableScreen
from Screens.ChoiceBox import ChoiceBox

# Generic
from Tools.BoundFunction import boundFunction
from Tools.Directories import createDir as directories_createDir, removeDir as directories_removeDir
from Components.config import config
from os import sep, stat, statvfs
from os.path import isdir
import os

# Quickselect
from Tools.NumericalTextInput import NumericalTextInput

# GUI (Components)
from Components.ActionMap import NumberActionMap, HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Components.Button import Button
from Components.FileList import FileList
from Components.MenuList import MenuList

# Timer
from enigma import eTimer


DEFAULT_INHIBIT_DIRECTORIES = ("/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/picon", "/piconlcd", "/proc", "/run", "/sbin", "/share", "/sys", "/tmp", "/usr", "/var")
defaultInhibitDirs = list(DEFAULT_INHIBIT_DIRECTORIES)
DEFAULT_INHIBIT_DEVICES = []
for dir in DEFAULT_INHIBIT_DIRECTORIES + ("/", "/media"):
	if isdir(dir):
		device = stat(dir).st_dev
		if device not in DEFAULT_INHIBIT_DEVICES:
			DEFAULT_INHIBIT_DEVICES.append(device)
DEFAULT_INHIBIT_DEVICES = tuple(DEFAULT_INHIBIT_DEVICES)


class LocationBox(Screen, NumericalTextInput, HelpableScreen):
	"""Simple Class similar to MessageBox / ChoiceBox but used to choose a folder/pathname combination"""

	skin = """<screen name="LocationBox" position="100,75" size="540,460" >
			<widget name="text" position="0,2" size="540,22" font="Regular;22" />
			<widget name="target" position="0,23" size="540,22" verticalAlignment="center" font="Regular;22" />
			<widget name="filelist" position="0,55" zPosition="1" size="540,210" scrollbarMode="showOnDemand" selection="1" />
			<widget name="textbook" position="0,272" size="540,22" font="Regular;22" />
			<widget name="booklist" position="5,302" zPosition="2" size="535,100" scrollbarMode="showOnDemand" />
			<widget name="red" position="0,415" zPosition="1" size="135,40" pixmap="buttons/red.png" transparent="1" alphaTest="on" />
			<widget name="key_red" position="0,415" zPosition="2" size="135,40" horizontalAlignment="center" verticalAlignment="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
			<widget name="green" position="135,415" zPosition="1" size="135,40" pixmap="buttons/green.png" transparent="1" alphaTest="on" />
			<widget name="key_green" position="135,415" zPosition="2" size="135,40" horizontalAlignment="center" verticalAlignment="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
			<widget name="yellow" position="270,415" zPosition="1" size="135,40" pixmap="buttons/yellow.png" transparent="1" alphaTest="on" />
			<widget name="key_yellow" position="270,415" zPosition="2" size="135,40" horizontalAlignment="center" verticalAlignment="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
			<widget name="blue" position="405,415" zPosition="1" size="135,40" pixmap="buttons/blue.png" transparent="1" alphaTest="on" />
			<widget name="key_blue" position="405,415" zPosition="2" size="135,40" horizontalAlignment="center" verticalAlignment="center" font="Regular;22" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		</screen>"""

	def __init__(self, session, text="", filename="", currDir=None, bookmarks=None, userMode=False, windowTitle=None, minFree=None, autoAdd=False, editDir=False, inhibitDirs=[], inhibitMounts=[]):
		# Init parents
		Screen.__init__(self, session)
		NumericalTextInput.__init__(self, handleTimeout=False)
		HelpableScreen.__init__(self)

		# Set useable chars
		self.setUseableChars('1234567890abcdefghijklmnopqrstuvwxyz')

		# Quickselect Timer
		self.qs_timer = eTimer()
		self.qs_timer.callback.append(self.timeout)
		self.qs_timer_type = 0

		# Initialize Quickselect
		self.curr_pos = -1
		self.quickselect = ""

		# Set Text
		self["text"] = Label(text)
		self["textbook"] = Label(_("Bookmarks") if bookmarks else '')

		# Save parameters locally
		self.text = text
		self.filename = filename
		self.minFree = minFree
		self.realBookmarks = bookmarks
		self.bookmarks = bookmarks and bookmarks.value[:] or []
		self.userMode = userMode
		self.autoAdd = autoAdd
		self.editDir = editDir
		self.inhibitDirs = inhibitDirs

		# Initialize FileList
		self["filelist"] = FileList(currDir, showDirectories=True, showFiles=False, inhibitMounts=inhibitMounts, inhibitDirs=inhibitDirs)

		# Initialize BookList
		self["booklist"] = MenuList(self.bookmarks)

		# Buttons
		self["key_green"] = Button(_("OK"))
		self["key_red"] = Button(_("Cancel"))
		self["key_yellow"] = StaticText(_("Rename"))
		self["key_blue"] = StaticText(_("Remove bookmark") if self.realBookmarks else '')
		self["key_menu"] = StaticText(_("MENU"))

		# Background for Buttons
		self["green"] = Pixmap()
		self["yellow"] = Pixmap()
		self["blue"] = Pixmap()
		self["red"] = Pixmap()

		# Initialize Target
		self["target"] = Label()

		if self.userMode:
			self.usermodeOn()

		# Custom Action Handler
		class LocationBoxActionMap(HelpableActionMap):
			def __init__(self, parent, context, actions={}, prio=0):
				HelpableActionMap.__init__(self, parent, context, actions, prio)
				self.box = parent

			def action(self, contexts, action):
				# Reset Quickselect
				self.box.timeout(force=True)

				return HelpableActionMap.action(self, contexts, action)

		# Actions that will reset quickselect
		self["WizardActions"] = LocationBoxActionMap(self, "WizardActions",
			{
				"left": self.left,
				"right": self.right,
				"up": self.up,
				"down": self.down,
				"ok": (self.ok, _("Select")),
				"back": (self.cancel, _("Cancel")),
			}, -2)

		self["ColorActions"] = LocationBoxActionMap(self, "ColorActions",
			{
				"red": self.cancel,
				"green": self.select,
				"yellow": self.changeName,
				"blue": self.addRemoveBookmark,
			}, -2)

		self["EPGSelectActions"] = LocationBoxActionMap(self, "EPGSelectActions",
			{
				"prevBouquet": (self.switchToBookList, _("Switch to bookmarks")),
				"nextBouquet": (self.switchToFileList, _("Switch to filelist")),
			}, -2)

		self["MenuActions"] = LocationBoxActionMap(self, "MenuActions",
			{
				"menu": (self.showMenu, _("Menu")),
			}, -2)

		# Actions used by quickselect
		self["NumberActions"] = NumberActionMap(["NumberActions"],
		{
			"1": self.keyNumberGlobal,
			"2": self.keyNumberGlobal,
			"3": self.keyNumberGlobal,
			"4": self.keyNumberGlobal,
			"5": self.keyNumberGlobal,
			"6": self.keyNumberGlobal,
			"7": self.keyNumberGlobal,
			"8": self.keyNumberGlobal,
			"9": self.keyNumberGlobal,
			"0": self.keyNumberGlobal
		})

		# Run some functions when shown
		if windowTitle is None:
			windowTitle = _("Select location")
		self.onShown.extend((
			boundFunction(self.setTitle, windowTitle),
			self.updateTarget,
			self.showHideRename,
		))

		self.onLayoutFinish.append(self.switchToFileListOnStart)

		# Make sure we remove our callback
		self.onClose.append(self.disableTimer)

	def switchToFileListOnStart(self):
		if self.realBookmarks and self.realBookmarks.value:
			self.currList = "booklist"
			currDir = self["filelist"].current_directory
			if currDir in self.bookmarks:
				self["booklist"].moveToIndex(self.bookmarks.index(currDir))
		else:
			self.switchToFileList()

	def disableTimer(self):
		self.qs_timer.callback.remove(self.timeout)

	def showHideRename(self):
		# Don't allow renaming when filename is empty
		if not self.filename:
			self["key_yellow"].setText("")

	def switchToFileList(self):
		if not self.userMode:
			self.currList = "filelist"
			self["filelist"].selectionEnabled(1)
			self["booklist"].selectionEnabled(0)
			self["key_blue"].setText(_("Add bookmark" if self.realBookmarks else None))
			self.updateTarget()

	def switchToBookList(self):
		if not self.realBookmarks:
			return
		self.currList = "booklist"
		self["filelist"].selectionEnabled(0)
		self["booklist"].selectionEnabled(1)
		self["key_blue"].setText(_("Remove bookmark"))
		self.updateTarget()

	def addRemoveBookmark(self):
		if not self.realBookmarks:
			return
		if self.currList == "filelist":
			# add bookmark
			folder = self["filelist"].getSelection()[0]
			if folder is not None and not folder in self.bookmarks:
				self.bookmarks.append(folder)
				if self.bookmarks != self.realBookmarks.value:
					self.realBookmarks.value = self.bookmarks
					self.realBookmarks.save()
				self.bookmarks.sort()
				self["booklist"].setList(self.bookmarks)
		else:
			# remove bookmark
			if not self.userMode:
				name = self["booklist"].getCurrent()
				self.session.openWithCallback(
					boundFunction(self.removeBookmark, name),
					MessageBox,
					_("Do you really want to remove your bookmark of %s?") % (name),
				)

	def removeBookmark(self, name, ret):
		if not ret:
			return
		if name in self.bookmarks:
			self.bookmarks.remove(name)
			if self.bookmarks != self.realBookmarks.value:
				self.realBookmarks.value = self.bookmarks
				self.realBookmarks.save()
			self["booklist"].setList(self.bookmarks)

	def updateBookmarks(self):
		if self.realBookmarks:
			self.realBookmarks.load()
			self.bookmarks = self.realBookmarks and self.realBookmarks.value[:] or []
			self["booklist"].setList(self.bookmarks)

	def createDir(self):
		if self["filelist"].current_directory is not None:
			self.session.openWithCallback(
				self.createDirCallback,
				InputBox,
				title=_("Please enter name of the new directory"),
				text=self.filename
			)

	def createDirCallback(self, res):
		if res:
			path = os.path.join(self["filelist"].current_directory, res)
			if not os.path.exists(path):
				if not directories_createDir(path):
					self.session.open(
						MessageBox,
						_("Creating directory %s failed.") % (path),
						type=MessageBox.TYPE_ERROR,
						timeout=5
					)
				self["filelist"].refresh()
			else:
				self.session.open(
					MessageBox,
					_("The path %s already exists.") % (path),
					type=MessageBox.TYPE_ERROR,
					timeout=5
				)

	def removeDir(self):
		sel = self["filelist"].getSelection()
		if sel and os.path.exists(sel[0]):
			self.session.openWithCallback(
				boundFunction(self.removeDirCallback, sel[0]),
				MessageBox,
				_("Do you really want to remove directory %s from the disk?") % (sel[0]),
				type=MessageBox.TYPE_YESNO
			)
		else:
			self.session.open(
				MessageBox,
				_("Invalid directory selected: %s") % (sel[0]),
				type=MessageBox.TYPE_ERROR,
				timeout=5
			)

	def removeDirCallback(self, name, res):
		if res:
			if not directories_removeDir(name):
				self.session.open(
					MessageBox,
					_("Removing directory %s failed. (Maybe not empty.)") % (name),
					type=MessageBox.TYPE_ERROR,
					timeout=5
				)
			else:
				self["filelist"].refresh()
				self.removeBookmark(name, True)
				val = self.realBookmarks and self.realBookmarks.value
				if val and name in val:
					val.remove(name)
					self.realBookmarks.value = val
					self.realBookmarks.save()

	def up(self):
		self[self.currList].up()
		self.updateTarget()

	def down(self):
		self[self.currList].down()
		self.updateTarget()

	def left(self):
		self[self.currList].pageUp()
		self.updateTarget()

	def right(self):
		self[self.currList].pageDown()
		self.updateTarget()

	def ok(self):
		if self.currList == "filelist":
			if self["filelist"].canDescent():
				self["filelist"].descent()
				self.updateTarget()
		else:
			self.select()

	def cancel(self):
		self.close(None)

	def getPreferredFolder(self):
		if self.currList == "filelist":
			# XXX: We might want to change this for parent folder...
			return self["filelist"].getSelection()[0]
		else:
			return self["booklist"].getCurrent()

	def selectConfirmed(self, ret):
		if ret:
			ret = ''.join((self.getPreferredFolder(), self.filename))
			if self.realBookmarks:
				if self.autoAdd and not ret in self.bookmarks:
					if self.getPreferredFolder() not in self.bookmarks:
						self.bookmarks.append(self.getPreferredFolder())
						self.bookmarks.sort()

				if self.bookmarks != self.realBookmarks.value:
					self.realBookmarks.value = self.bookmarks
					self.realBookmarks.save()

				if self.filename and not os.path.exists(ret):
					menu = [(_("Create new folder and exit"), "folder"), (_("Save and exit"), "exit")]
					text = _("Select action")

					def dirAction(choice):
						if choice:
							if choice[1] == "folder":
								if not directories_createDir(ret):
									self.session.open(MessageBox, _("Creating directory %s failed.") % (ret), type=MessageBox.TYPE_ERROR)
									return
							self.close(ret)
						else:
							self.cancel()
					self.session.openWithCallback(dirAction, ChoiceBox, title=text, list=menu)
					return

			self.close(ret)

	def select(self):
		currentFolder = self.getPreferredFolder()
		# Do nothing unless current Directory is valid
		if currentFolder is not None:
			# Check if we need to have a minimum of free Space available
			if self.minFree is not None:
				# Try to read fs stats
				try:
					s = os.statvfs(currentFolder)
					if (s.f_bavail * s.f_bsize) / 1000000 > self.minFree:
						# Automatically confirm if we have enough free disk Space available
						return self.selectConfirmed(True)
				except OSError:
					pass

				# Ask User if he really wants to select this folder
				self.session.openWithCallback(
					self.selectConfirmed,
					MessageBox,
					_("There might not be enough Space on the selected Partition.\nDo you really want to continue?"),
					type=MessageBox.TYPE_YESNO
				)
			# No minimum free Space means we can safely close
			else:
				self.selectConfirmed(True)

	def changeName(self):
		if self.filename != "":
			# TODO: Add Information that changing extension is bad? disallow?
			self.session.openWithCallback(
				self.nameChanged,
				InputBox,
				title=_("Please enter a new filename"),
				text=self.filename
			)

	def nameChanged(self, res):
		if res is not None:
			if len(res):
				self.filename = res
				self.updateTarget()
			else:
				self.session.open(
					MessageBox,
					_("An empty filename is illegal."),
					type=MessageBox.TYPE_ERROR,
					timeout=5
				)

	def updateTarget(self):
		# Write Combination of Folder & Filename when Folder is valid
		currFolder = self.getPreferredFolder()
		if currFolder is not None:
			self["target"].setText(''.join((currFolder, self.filename)))
		# Display a Warning otherwise
		else:
			self["target"].setText(_("Invalid location"))

	def showMenu(self):
		if not self.userMode and self.realBookmarks:
			if self.currList == "filelist":
				menu = [
					(_("Switch to bookmarks"), self.switchToBookList),
					(_("Add bookmark"), self.addRemoveBookmark),
					(_("Update bookmarks"), self.updateBookmarks)
				]
				if self.editDir:
					menu.extend((
						(_("Create directory"), self.createDir),
						(_("Remove directory"), self.removeDir)
					))
			else:
				menu = (
					(_("Switch to filelist"), self.switchToFileList),
					(_("Remove bookmark"), self.addRemoveBookmark),
					(_("Update bookmarks"), self.updateBookmarks)
				)

			self.session.openWithCallback(
				self.menuCallback,
				ChoiceBox,
				title="",
				list=menu
			)

	def menuCallback(self, choice):
		if choice:
			choice[1]()

	def usermodeOn(self):
		self.switchToBookList()
		self["filelist"].hide()
		self["key_blue"].SetText("")

	def keyNumberGlobal(self, number):
		# Cancel Timeout
		self.qs_timer.stop()

		# See if another key was pressed before
		if number != self.lastKey:
			# Reset lastKey again so NumericalTextInput triggers its keychange
			self.nextKey()

			# Try to select what was typed
			self.selectByStart()

			# Increment position
			self.curr_pos += 1

		# Get char and append to text
		char = self.getKey(number)
		self.quickselect = self.quickselect[:self.curr_pos] + str(char)

		# Start Timeout
		self.qs_timer_type = 0
		self.qs_timer.start(1000, 1)

	def selectByStart(self):
		# Don't do anything on initial call
		if not self.quickselect:
			return

		# Don't select if no dir
		if self["filelist"].getCurrentDirectory():
			# TODO: implement proper method in Components.FileList
			files = self["filelist"].getFileList()

			# Initialize index
			idx = 0

			# We select by filename which is absolute
			lookfor = self["filelist"].getCurrentDirectory() + self.quickselect

			# Select file starting with generated text
			for file in files:
				if file[0][0] and file[0][0].lower().startswith(lookfor):
					self["filelist"].instance.moveSelectionTo(idx)
					break
				idx += 1

	def timeout(self, force=False):
		# Timeout Key
		if not force and self.qs_timer_type == 0:
			# Try to select what was typed
			self.selectByStart()

			# Reset Key
			self.lastKey = -1

			# Change type
			self.qs_timer_type = 1

			# Start timeout again
			self.qs_timer.start(1000, 1)
		# Timeout Quickselect
		else:
			# Eventually stop Timer
			self.qs_timer.stop()

			# Invalidate
			self.lastKey = -1
			self.curr_pos = -1
			self.quickselect = ""

	def __repr__(self):
		return str(type(self)) + "(" + self.text + ")"


def MovieLocationBox(session, text, dir, filename="", minFree=None):
	return LocationBox(session, text=text, filename=filename, currDir=dir, bookmarks=config.movielist.videodirs, autoAdd=config.movielist.add_bookmark.value, editDir=True, inhibitDirs=defaultInhibitDirs, minFree=minFree)


class TimeshiftLocationBox(LocationBox):
	def __init__(self, session):
		LocationBox.__init__(
				self,
				session,
				text=_("Where to save temporary timeshift recordings?"),
				currDir=config.usage.timeshift_path.value,
				bookmarks=config.usage.allowed_timeshift_paths,
				autoAdd=True,
				editDir=True,
				inhibitDirs=defaultInhibitDirs,
				minFree=1024  # the same requirement is hardcoded in servicedvb.cpp
		)
		self.skinName = "LocationBox"

	def cancel(self):
		config.usage.timeshift_path.cancel()
		LocationBox.cancel(self)

	def selectConfirmed(self, ret):
		if ret:
			config.usage.timeshift_path.value = self.getPreferredFolder()
			config.usage.timeshift_path.save()
			LocationBox.selectConfirmed(self, ret)
