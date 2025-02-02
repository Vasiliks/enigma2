# -*- coding: utf-8 -*-
from os import listdir
from os.path import basename, dirname, isdir, join as pathjoin, normpath, realpath, exists
from re import compile

from enigma import BT_SCALE, BT_VALIGN_CENTER, RT_HALIGN_LEFT, RT_VALIGN_CENTER, eListboxPythonMultiContent, eServiceCenter, eServiceReference, gFont

from skin import fonts, parameters
from Components.Harddisk import harddiskmanager
from Components.MenuList import MenuList
from Tools.Directories import SCOPE_GUISKIN, resolveFilename
from Tools.LoadPixmap import LoadPixmap

EXTENSIONS = {
	"dts": "music",
	"mp3": "music",
	"wav": "music",
	"wave": "music",
	"wv": "music",
	"oga": "music",
	"ogg": "music",
	"flac": "music",
	"m4a": "music",
	"mp2": "music",
	"m2a": "music",
	"wma": "music",
	"ac3": "music",
	"mka": "music",
	"aac": "music",
	"ape": "music",
	"alac": "music",
	"amr": "music",
	"au": "music",
	"mid": "music",
	"jpg": "picture",
	"png": "picture",
	"gif": "picture",
	"bmp": "picture",
	"jpeg": "picture",
	"jpe": "picture",
	"svg": "picture",
	"mpg": "movie",
	"vob": "movie",
	"m4v": "movie",
	"mkv": "movie",
	"avi": "movie",
	"divx": "movie",
	"dat": "movie",
	"flv": "movie",
	"mp4": "movie",
	"mov": "movie",
	"wmv": "movie",
	"asf": "movie",
	"3gp": "movie",
	"3g2": "movie",
	"mpeg": "movie",
	"mpe": "movie",
	"rm": "movie",
	"rmvb": "movie",
	"ogm": "movie",
	"ogv": "movie",
	"m2ts": "movie",
	"mts": "movie",
	"ts": "movie",
	"webm": "movie",
	"pva": "movie",
	"wtv": "movie"
}


def FileEntryComponent(name, absolute=None, isDir=False):
	res = [(absolute, isDir)]
	x, y, w, h = parameters.get("FileListName", (35, 0, 600, 20))
	res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, name))
	if isDir:
		png = LoadPixmap(cached=True, path=resolveFilename(SCOPE_GUISKIN, "extensions/directory.png"))
	else:
		extension = name.split(".")
		extension = extension[-1].lower()
		if extension in EXTENSIONS:
			png = LoadPixmap(cached=True, path=resolveFilename(SCOPE_GUISKIN, "extensions/%s.png" % EXTENSIONS[extension]))
		else:
			png = None
	if png is not None:
		x, y, w, h = parameters.get("FileListIcon", (10, 0, 20, 20))
		res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, x, y, w, h, png, None, None, BT_SCALE | BT_VALIGN_CENTER))
	return res


class FileList(MenuList):
	def __init__(self, directory, showDirectories=True, showFiles=True, showMountpoints=True, matchingPattern=None, useServiceRef=False, inhibitDirs=False, inhibitMounts=False, isTop=False, enableWrapAround=False, additionalExtensions=None):
		MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
		self.additional_extensions = additionalExtensions
		self.mountpoints = []
		self.current_directory = None
		self.current_mountpoint = None
		self.useServiceRef = useServiceRef
		self.showDirectories = showDirectories
		self.showMountpoints = showMountpoints
		self.showFiles = showFiles
		if isTop:
			self.topDirectory = directory
		else:
			self.topDirectory = "/"
		# example: matching .nfi and .ts files: "^.*\.(nfi|ts)"
		if matchingPattern:
			self.matchingPattern = compile(matchingPattern)
		else:
			self.matchingPattern = None
		self.inhibitDirs = inhibitDirs or []
		self.inhibitMounts = inhibitMounts or []

		self.refreshMountpoints()
		self.changeDir(directory)
		font = fonts.get("FileList", ("Regular", 18, 23))
		self.l.setFont(0, gFont(font[0], font[1]))
		self.l.setItemHeight(font[2])
		self.serviceHandler = eServiceCenter.getInstance()

	def refreshMountpoints(self):
		self.mountpoints = [pathjoin(p.mountpoint, "") for p in harddiskmanager.getMountedPartitions()]
		self.mountpoints.sort(reverse=True)

	def getMountpoint(self, file):
		file = pathjoin(realpath(file), "")
		for m in self.mountpoints:
			if file.startswith(m):
				return m
		return False

	def getMountpointLink(self, file):
		if realpath(file) == file:
			return self.getMountpoint(file)
		else:
			if file[-1] == "/":
				file = file[:-1]
			mp = self.getMountpoint(file)
			last = file
			file = dirname(file)
			while last != "/" and mp == self.getMountpoint(file):
				last = file
				file = dirname(file)
			return pathjoin(last, "")

	def getSelection(self):
		if self.l.getCurrentSelection() is None:
			return None
		return self.l.getCurrentSelection()[0]

	def getCurrentEvent(self):
		event = self.l.getCurrentSelection()
		if not event or event[0][1]:
			return None
		else:
			return self.serviceHandler.info(event[0][0]).getEvent(event[0][0])

	def getFileList(self):
		return self.list

	def inParentDirs(self, dir, parents):
		dir = realpath(dir)
		for p in parents:
			if dir.startswith(p):
				return True
		return False

	def changeDir(self, directory, select=None):
		self.list = []

		# if we are just entering from the list of mount points:
		if self.current_directory is None:
			if directory and self.showMountpoints:
				self.current_mountpoint = self.getMountpointLink(directory)
			else:
				self.current_mountpoint = None
		self.current_directory = directory
		directories = []
		files = []

		if directory is None and self.showMountpoints:  # present available mountpoints
			for p in harddiskmanager.getMountedPartitions():
				path = pathjoin(p.mountpoint, "")
				if path not in self.inhibitMounts and not self.inParentDirs(path, self.inhibitDirs):
					self.list.append(FileEntryComponent(name=p.description, absolute=path, isDir=True))
			files = []
			directories = []
		elif directory is None:
			files = []
			directories = []
		elif self.useServiceRef:
			# we should not use the 'eServiceReference(string)' constructor, because it doesn't allow ':' in the directoryname
			root = eServiceReference(2, 0, directory)
			if self.additional_extensions:
				root.setName(self.additional_extensions)
			serviceHandler = eServiceCenter.getInstance()
			list = serviceHandler.list(root)

			while True:
				s = list.getNext()
				if not s.valid():
					del list
					break
				if s.flags & s.mustDescent:
					directories.append(s.getPath())
				else:
					files.append(s)
			directories.sort()
			files.sort()
		else:
			if isdir(directory):
				try:
					files = listdir(directory)
				except:
					files = []
				files.sort()
				tmpfiles = files[:]
				for x in tmpfiles:
					if isdir(directory + x):
						directories.append(directory + x + "/")
						files.remove(x)

		if self.showDirectories:
			if directory:
				if self.showMountpoints and directory == self.current_mountpoint:
					self.list.append(FileEntryComponent(name="<" + _("List of storage devices") + ">", absolute=None, isDir=True))
				elif (directory != self.topDirectory) and not (self.inhibitMounts and self.getMountpoint(directory) in self.inhibitMounts):
					self.list.append(FileEntryComponent(name="<" + _("Parent directory") + ">", absolute='/'.join(directory.split('/')[:-2]) + '/', isDir=True))
			for x in directories:
				if not (self.inhibitMounts and self.getMountpoint(x) in self.inhibitMounts) and not self.inParentDirs(x, self.inhibitDirs):
					name = x.split('/')[-2]
					self.list.append(FileEntryComponent(name=name, absolute=x, isDir=True))

		if self.showFiles:
			for x in files:
				if self.useServiceRef:
					path = x.getPath()
					name = path.split('/')[-1]
				else:
					path = directory + x
					name = x

				if (self.matchingPattern is None) or self.matchingPattern.search(path):
					self.list.append(FileEntryComponent(name=name, absolute=x, isDir=False))

		if self.showMountpoints and len(self.list) == 0:
			self.list.append(FileEntryComponent(name=_("nothing connected"), absolute=None, isDir=False))

		self.l.setList(self.list)

		if select is not None:
			i = 0
			self.moveToIndex(0)
			for x in self.list:
				p = x[0][0]

				if isinstance(p, eServiceReference):
					p = p.getPath()

				if p == select:
					self.moveToIndex(i)
				i += 1

	def getCurrentDirectory(self):
		return self.current_directory

	def canDescent(self):
		if self.getSelection() is None:
			return False
		return self.getSelection()[1]

	def descent(self):
		if self.getSelection() is None:
			return
		self.changeDir(self.getSelection()[0], select=self.current_directory)

	def getFilename(self):
		if self.getSelection() is None:
			return None
		x = self.getSelection()[0]
		if isinstance(x, eServiceReference):
			x = x.getPath()
		return x

	def getServiceRef(self):
		if self.getSelection() is None:
			return None
		x = self.getSelection()[0]
		if isinstance(x, eServiceReference):
			return x
		return None

	def execBegin(self):
		harddiskmanager.on_partition_list_change.append(self.partitionListChanged)

	def execEnd(self):
		harddiskmanager.on_partition_list_change.remove(self.partitionListChanged)

	def refresh(self):
		self.changeDir(self.current_directory, self.getFilename())

	def partitionListChanged(self, action, device):
		self.refreshMountpoints()
		if self.current_directory is None:
			self.refresh()


def MultiFileSelectEntryComponent(name, absolute=None, isDir=False, selected=False):
	res = [(absolute, isDir, selected, name)]
	x, y, w, h = parameters.get("FileListMultiName", (55, 0, 600, 25))
	res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT, name))
	if isDir:
		png = LoadPixmap(cached=True, path=resolveFilename(SCOPE_GUISKIN, "extensions/directory.png"))
	else:
		extension = name.split('.')
		extension = extension[-1].lower()
		if extension in EXTENSIONS:
			png = LoadPixmap(resolveFilename(SCOPE_GUISKIN, "extensions/" + EXTENSIONS[extension] + ".png"))
		else:
			png = None
	if png is not None:
		x, y, w, h = parameters.get("FileListMultiIcon", (30, 2, 20, 20))
		res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, x, y, w, h, png))
	if not name.startswith('<'):
		if selected:
			icon = LoadPixmap(cached=True, path=resolveFilename(SCOPE_GUISKIN, "icons/lock_on.png"))
		else:
			icon = LoadPixmap(cached=True, path=resolveFilename(SCOPE_GUISKIN, "icons/lock_off.png"))
		x, y, w, h = parameters.get("FileListMultiLock", (2, 0, 25, 25))
		res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, x, y, w, h, icon))
	return res


class MultiFileSelectList(FileList):
	def __init__(self, preselectedFiles, directory, showMountpoints=False, matchingPattern=None, showDirectories=True, showFiles=True, useServiceRef=False, inhibitDirs=False, inhibitMounts=False, isTop=False, enableWrapAround=False, additionalExtensions=None):
		if preselectedFiles is None:
			self.selectedFiles = []
		else:
			self.selectedFiles = preselectedFiles
		FileList.__init__(self, directory, showMountpoints=showMountpoints, matchingPattern=matchingPattern, showDirectories=showDirectories, showFiles=showFiles, useServiceRef=useServiceRef, inhibitDirs=inhibitDirs, inhibitMounts=inhibitMounts, isTop=isTop, enableWrapAround=enableWrapAround, additionalExtensions=additionalExtensions)
		self.changeDir(directory)
		font = fonts.get("FileListMulti", ("Regular", 20, 25))
		self.l.setFont(0, gFont(font[0], font[1]))
		self.l.setItemHeight(font[2])
		self.onSelectionChanged = []

	def selectionChanged(self):
		for f in self.onSelectionChanged:
			f()

	def changeSelectionState(self):
		if len(self.list):
			idx = self.l.getCurrentSelectionIndex()
			newList = self.list[:]
			x = self.list[idx]
			if x and len(x[0]) > 2 and not x[0][3].startswith('<'):
				if x[0][1]:
					realPathname = x[0][0]
				else:
					realPathname = self.current_directory + x[0][0]
				if x[0][2]:
					SelectState = False
					try:
						self.selectedFiles.remove(realPathname)
					except:
						try:
							self.selectedFiles.remove(normpath(realPathname))
						except (IOError, OSError) as err:
							print("[FileList] Error %d: Can't remove '%s'!  (%s)" % (err.errno, realPathname, err.strerror))
				else:
					SelectState = True
					if (realPathname not in self.selectedFiles) and (normpath(realPathname) not in self.selectedFiles):
						self.selectedFiles.append(realPathname)
				newList[idx] = MultiFileSelectEntryComponent(name=x[0][3], absolute=x[0][0], isDir=x[0][1], selected=SelectState)
			self.list = newList
			self.l.setList(self.list)

	def getSelectedList(self):
		selectedFilesExist = []
		for x in self.selectedFiles:
			if exists(x):
				selectedFilesExist.append(x)
		return selectedFilesExist

	def changeDir(self, directory, select=None):
		self.list = []

		# if we are just entering from the list of mount points:
		if self.current_directory is None:
			if directory and self.showMountpoints:
				self.current_mountpoint = self.getMountpointLink(directory)
			else:
				self.current_mountpoint = None
		self.current_directory = directory
		directories = []
		files = []

		if directory is None and self.showMountpoints:  # present available mountpoints
			for p in harddiskmanager.getMountedPartitions():
				path = pathjoin(p.mountpoint, "")
				if path not in self.inhibitMounts and not self.inParentDirs(path, self.inhibitDirs):
					self.list.append(MultiFileSelectEntryComponent(name=p.description, absolute=path, isDir=True))
			files = []
			directories = []
		elif directory is None:
			files = []
			directories = []
		elif self.useServiceRef:
			root = eServiceReference("2:0:1:0:0:0:0:0:0:0:" + directory)
			if self.additional_extensions:
				root.setName(self.additional_extensions)
			serviceHandler = eServiceCenter.getInstance()
			list = serviceHandler.list(root)

			while True:
				s = list.getNext()
				if not s.valid():
					del list
					break
				if s.flags & s.mustDescent:
					directories.append(s.getPath())
				else:
					files.append(s)
			directories.sort()
			files.sort()
		else:
			if isdir(directory):
				try:
					files = listdir(directory)
				except:
					files = []
				files.sort()
				tmpfiles = files[:]
				for x in tmpfiles:
					if isdir(directory + x):
						directories.append(directory + x + "/")
						files.remove(x)

		if self.showDirectories:
			if directory:
				if self.showMountpoints and directory == self.current_mountpoint:
					self.list.append(FileEntryComponent(name="<" + _("List of storage devices") + ">", absolute=None, isDir=True))
				elif (directory != self.topDirectory) and not (self.inhibitMounts and self.getMountpoint(directory) in self.inhibitMounts):
					self.list.append(FileEntryComponent(name="<" + _("Parent directory") + ">", absolute='/'.join(directory.split('/')[:-2]) + '/', isDir=True))
			for x in directories:
				if not (self.inhibitMounts and self.getMountpoint(x) in self.inhibitMounts) and not self.inParentDirs(x, self.inhibitDirs):
					name = x.split('/')[-2]
					alreadySelected = (x in self.selectedFiles) or (normpath(x) in self.selectedFiles)
					self.list.append(MultiFileSelectEntryComponent(name=name, absolute=x, isDir=True, selected=alreadySelected))

		if self.showFiles:
			for x in files:
				if self.useServiceRef:
					path = x.getPath()
					name = path.split('/')[-1]
				else:
					path = directory + x
					name = x
				if (self.matchingPattern is None) or self.matchingPattern.search(path):
					alreadySelected = False
					for entry in self.selectedFiles:
						if self.useServiceRef and basename(entry) == x:
							alreadySelected = True
						elif entry == path:
							alreadySelected = True
					self.list.append(MultiFileSelectEntryComponent(name=name, absolute=x, isDir=False, selected=alreadySelected))

		self.l.setList(self.list)

		if select is not None:
			i = 0
			self.moveToIndex(0)
			for x in self.list:
				p = x[0][0]

				if isinstance(p, eServiceReference):
					p = p.getPath()

				if p == select:
					self.moveToIndex(i)
				i += 1
