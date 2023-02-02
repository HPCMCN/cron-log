# -*- coding:utf-8 -*-
# author: HPCM
# time: 2023/2/1 15:56
# file: handlers.py
import re
import os
import io
import time
from datetime import datetime, timedelta
from logging.handlers import BaseRotatingHandler

from cron_log_1.trigger import CronTrigger


# noinspection PyUnresolvedReferences,PyPep8Naming,PyTypeChecker
class CronRotatingFileHandler(BaseRotatingHandler):
    """
    Handler for logging to a file, rotating the log file at certain timed
    intervals.

    If backupCount is > 0, when rollover is done, no more than backupCount
    files are kept - the oldest ones are deleted.
    """
    keep_mappings = {
        "d": "days",
        "w": "weeks",
        "m": "minutes",
        "h": "hours"
    }

    def __init__(self, filename, crontab, keepBackup=None, encoding=None, delay=False, utc=False, maxBytes=0,
                 errors=None):
        encoding = io.text_encoding(encoding)
        self.base_dir = os.path.dirname(os.path.abspath(filename))
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        BaseRotatingHandler.__init__(self, filename, 'a', encoding=encoding,
                                     delay=delay, errors=errors)
        self.crontab = crontab
        self.maxBytes = maxBytes
        self.utc = utc
        self.time_format = "%Y-%m-%d_%H-%M-%S"
        self.regex_format = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}"
        start_filename, last_suffix = os.path.splitext(os.path.basename(filename))

        # Rollover
        self.obs_filename = os.path.basename(start_filename)
        self.trigger = CronTrigger.from_crontab(crontab)
        self.suffix = start_filename + "-" + self.time_format + last_suffix if last_suffix else ""

        self.prev_time = datetime.now()
        self.next_time = self.trigger.get_next_fire_time(self.prev_time)

        # Delete
        self.keep_kwargs = None
        self.extMatch = None
        if keepBackup:
            try:
                self.keep_kwargs = {self.keep_mappings[keepBackup[-1].lower()]: int(keepBackup[0]) + 1}
            except KeyError:
                raise ValueError("Invalid rollover interval specified: %s" % keepBackup)
            self.extMatch = r"^%s-(%s)" % (start_filename, self.regex_format)
            self.extMatch = re.compile(self.extMatch, re.ASCII)

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        record is not used, as we are just comparing times, but it is needed so
        the method signatures are the same
        """
        # See bpo-45401: Never rollover anything other than regular files
        if os.path.exists(self.baseFilename) and not os.path.isfile(self.baseFilename):
            return False
        if time.time() >= self.next_time.timestamp():
            return True
        if self.maxBytes > 0:  # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  # due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return True
        return False

    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.

        More specific than the earlier method, which just used glob.glob().
        """
        result = []
        # See bpo-44753: Don't use the extension when computing the prefix.
        ct = datetime.now()
        for fileNames in os.walk(self.base_dir):
            for fileName in fileNames[-1]:
                if not fileName.startswith(self.obs_filename):
                    continue
                res = self.extMatch.match(fileName)
                if res and ct - timedelta(**self.keep_kwargs) > datetime.strptime(res.group(1), self.time_format):
                    result.append(os.path.join(fileNames[0], fileName))
        return result

    def doRollover(self):
        """
        do a rollover; in this case, a date/time stamp is appended to the filename
        when the rollover happens.  However, you want the file to be named for the
        start of the interval, not the current time.  If there is a backup count,
        then we have to get a list of matching filenames, sort them and remove
        the one with the oldest suffix.
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        dfn = self.rotation_filename(os.path.join(self.base_dir, self.prev_time.strftime(self.suffix)))
        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)
        if self.keep_kwargs is not None:
            for s in self.getFilesToDelete():
                os.remove(s)
        if not self.delay:
            self.stream = self._open()
        self.prev_time = datetime.now()
        self.next_time = self.trigger.get_next_fire_time(self.prev_time)
