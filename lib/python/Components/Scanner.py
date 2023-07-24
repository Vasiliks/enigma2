# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Components.PluginComponent import plugins

import os
from mimetypes import guess_type, add_type


def getType(file):
	add_type("audio/aac", ".aac")
	add_type("audio/ac3", ".a52")
	add_type("audio/eac3", ".eac3")
	add_type("audio/amr", ".amr")
	add_type("audio/dsf", ".dsf")
	add_type("audio/dsp", ".dsp")
	add_type("audio/dsd", ".dsd")
	add_type("audio/dts", ".dts")
	add_type("audio/midi", ".mid")
	add_type("audio/midi", ".midi")
	add_type("audio/mp4", ".mp4")
	add_type("audio/m4b", ".m4b")
	add_type("audio/mp4", ".mp4a")
	add_type("audio/mpeg", ".mpga")
	add_type("audio/mpeg", ".m2a")
	add_type("audio/mpeg", ".m3a")
	add_type("audio/ogg", ".spx")
	add_type("audio/ogg", ".opus")
	add_type("audio/ogg", ".vorbis")
	add_type("audio/vorbis", ".vorbis")
	add_type("audio/wav", ".dff")
	add_type("audio/wav", ".dsf")
	add_type("audio/wav", ".imy")
	add_type("audio/webm", ".webma")
	add_type("audio/x-aac", ".aac")
	add_type("audio/x-ape", ".ape")
	add_type("audio/x-dsf", ".dsf")
	add_type("audio/x-dff", ".dff")
	add_type("audio/x-dsd", ".dsd")
	add_type("audio/x-flac", ".flac")
	add_type("audio/x-matroska", ".mka")
	add_type("audio/x-mpegurl", ".m3u")
	add_type("audio/x-mpegurl", ".m3u8")
	add_type("audio/x-monkeys-audio", ".ape")
	add_type("audio/x-musepack", ".mpc")
	add_type("audio/x-tta", ".tta")
	add_type("audio/x-ttafile", ".tta")
	add_type("audio/x-true-hd", ".mka")
	add_type("audio/x-wav", ".wav")
	add_type("audio/x-wav", ".wave")
	add_type("audio/x-wav", ".wv")
	add_type("audio/x-shorten", ".shn")
	add_type("audio/x-wavpack", ".wv")
	add_type("audio/x-wavpack-correction", ".wpc")
	add_type("audio/xsp", ".xsp")
	add_type("video/3gpp", ".3gp")
	add_type("video/3gpp2", ".3g2")
	add_type("video/mp4", ".mp4")
	add_type("video/avi", ".avi")
	add_type("video/divx", ".divx")
	add_type("video/dvd", ".vob")
	add_type("video/dvd", ".vro")
	add_type("video/h263", ".h263")
	add_type("video/h264", ".h264")
	add_type("video/h265", ".h265")
	add_type("video/mp2t", ".m2ts")
	add_type("video/mp2t", ".ts")
	add_type("video/mp4", ".mp4a")
	add_type("video/mp4", ".mp4s")
	add_type("video/mp4", ".mpg4")
	add_type("video/mpeg", ".mpg")
	add_type("video/mpeg", ".m1v")
	add_type("video/mpeg", ".m2v")
	add_type("video/mpeg", ".mts")
	add_type("video/mts", ".mts")
	add_type("video/quicktime", ".qt")
	add_type("video/quicktime", ".mov")
	add_type("video/x-dvd-iso", ".img")
	add_type("video/x-dvd-iso", ".iso")
	add_type("video/x-dvd-iso", ".nrg")
	add_type("video/x-dvd-iso", ".ifo")
	add_type("video/x-f4v", ".f4v")
	add_type("video/x-m4v", ".m4v")
	add_type("video/x-matroska", ".mk3d")
	add_type("video/x-matroska", ".mka")
	add_type("video/x-mpeg", ".dat")
	add_type("video/x-ms-asf", ".asf")
	add_type("video/x-msvideo", ".avi")
	add_type("video/x-ms-wvx", ".wvx")
	add_type("image/svg+xml", ".svg")
	add_type("image/svg+xml", ".svgz")
	add_type("image/tiff", ".tif")
	add_type("image/webp", ".webp")
	add_type("application/vnd.rn-realmedia-vbr", ".rmvb")
	add_type("application/vnd.rn-realmedia", ".rm")





	add_type("application/x-debian-package", ".ipk")
	add_type("application/x-debian-package", ".deb")
	add_type("application/x-debian-package", ".udeb")
	add_type("application/x-dream-package", ".dmpkg")
	add_type("application/x-dream-image", ".nfi")
	add_type("application/dash+xml", ".mpd")
	add_type("application/dash+xml", ".mdp")
	add_type("application/dash+xml", ".dash")
	add_type("application/x-mpegurl", ".hls")
	add_type("application/x-mpegurl", ".m3u8")
	add_type("application/x-mpegurl", ".m3u")
	add_type("application/ogg", ".ogg")
	add_type("application/ttml+xml", ".mpd")

	(type, _) = guess_type(file)
	if type is None:
		# Detect some unknown types
		if file[-12:].lower() == "video_ts.ifo":
			return "video/x-dvd"
		if file == "/media/audiocd/cdplaylist.cdpls":
			return "audio/x-cda"

		p = file.rfind('.')
		if p == -1:
			return None
		ext = file[p + 1:].lower()

		if ext == "dat" and file[-11:-6].lower() == "avseq":
			return "video/x-vcd"
	return type


class Scanner:
	def __init__(self, name, mimetypes=[], paths_to_scan=[], description="", openfnc=None):
		self.mimetypes = mimetypes
		self.name = name
		self.paths_to_scan = paths_to_scan
		self.description = description
		self.openfnc = openfnc

	def checkFile(self, file):
		return True

	def handleFile(self, res, file):
		if (self.mimetypes is None or file.mimetype in self.mimetypes) and self.checkFile(file):
			res.setdefault(self, []).append(file)

	def __repr__(self):
		return "<Scanner " + self.name + ">"

	def open(self, list, *args, **kwargs):
		if self.openfnc is not None:
			self.openfnc(list, *args, **kwargs)


class ScanPath:
	def __init__(self, path, with_subdirs=False):
		self.path = path
		self.with_subdirs = with_subdirs

	def __repr__(self):
		return self.path + "(" + str(self.with_subdirs) + ")"

	# we will use this in a set(), so we need to implement __hash__ and __eq__
	def __hash__(self):
		return self.path.__hash__() ^ self.with_subdirs.__hash__()

	def __eq__(self, other):
		return self.path == other.path


class ScanFile:
	def __init__(self, path, mimetype=None, size=None, autodetect=True):
		self.path = path
		if mimetype is None and autodetect:
			self.mimetype = getType(path)
		else:
			self.mimetype = mimetype
		self.size = size

	def __repr__(self):
		return "<ScanFile " + self.path + " (" + str(self.mimetype) + ", " + str(self.size) + " MB)>"


def execute(option):
	print("[Scanner] execute", option)
	if option is None:
		return

	(_, scanner, files, session) = option
	scanner.open(files, session)


def scanDevice(mountpoint):
	scanner = []

	for p in plugins.getPlugins(PluginDescriptor.WHERE_FILESCAN):
		l = p.__call__()
		if not isinstance(l, list):
			l = [l]
		scanner += l

	print("[Scanner] ", scanner)

	res = {}

	# merge all to-be-scanned paths, with priority to
	# with_subdirs.

	paths_to_scan = set()

	# first merge them all...
	for s in scanner:
		paths_to_scan.update(set(s.paths_to_scan))

	# ...then remove with_subdir=False when same path exists
	# with with_subdirs=True
	for p in paths_to_scan.copy():
		if p.with_subdirs == True and ScanPath(path=p.path) in paths_to_scan:
			paths_to_scan.remove(ScanPath(path=p.path))

	from Components.Harddisk import harddiskmanager
	blockdev = mountpoint.rstrip("/").rsplit('/', 1)[-1]
	error, blacklisted, removable, is_cdrom, partitions, medium_found = harddiskmanager.getBlockDevInfo(blockdev)

	# now scan the paths
	for p in paths_to_scan:
		path = os.path.join(mountpoint, p.path)

		for root, dirs, files in os.walk(path):
			for f in files:
				path = os.path.join(root, f)
				if (is_cdrom and f.endswith(".wav") and f.startswith("track")) or f == "cdplaylist.cdpls":
					sfile = ScanFile(path, "audio/x-cda")
				else:
					sfile = ScanFile(path)
				for s in scanner:
					s.handleFile(res, sfile)

			# if we really don't want to scan subdirs, stop here.
			if not p.with_subdirs:
				del dirs[:]

	# res is a dict with scanner -> [ScanFiles]
	return res


def openList(session, files):
	if not isinstance(files, list):
		files = [files]

	scanner = []

	for p in plugins.getPlugins(PluginDescriptor.WHERE_FILESCAN):
		l = p.__call__()
		if not isinstance(l, list):
			scanner.append(l)
		else:
			scanner += l

	print("[Scanner] ", scanner)

	res = {}

	for file in files:
		for s in scanner:
			s.handleFile(res, file)

	choices = [(r.description, r, res[r], session) for r in res]
	Len = len(choices)
	if Len > 1:
		from Screens.ChoiceBox import ChoiceBox

		session.openWithCallback(
			execute,
			ChoiceBox,
			title="The following viewers were found...",
			list=choices
		)
		return True
	elif Len:
		execute(choices[0])
		return True

	return False


def openFile(session, mimetype, file):
	return openList(session, [ScanFile(file, mimetype)])
