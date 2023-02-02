# -*- coding:utf-8 -*-
# author: HPCM
# time: 2023/2/1 16:43
# file: trigger.py
import six
from tzlocal import get_localzone
from datetime import datetime, timedelta

from cron_log_1.util import datetime_ceil, astimezone, localize, normalize
from cron_log_1.fields import BaseField, MonthField, WeekField, DayOfMonthField, DayOfWeekField, DEFAULT_VALUES


class CronTrigger(object):
    """
    Triggers when current time matches all specified time constraints,
    similarly to how the UNIX cron_log scheduler works.

    :param int|str month: month (1-12)
    :param int|str day: day of month (1-31)
    :param int|str day_of_week: number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun)
    :param int|str hour: hour (0-23)
    :param int|str minute: minute (0-59)
    :param datetime.tzinfo|str timezone: time zone to use for the date/time calculations (defaults
        to scheduler timezone)

    .. note:: The first weekday is always **monday**.
    """

    FIELD_NAMES = ('year', 'month', 'day', 'week', 'day_of_week', 'hour', 'minute', 'second')
    FIELDS_MAP = {
        'year': BaseField,
        'month': MonthField,
        'week': WeekField,
        'day': DayOfMonthField,
        'day_of_week': DayOfWeekField,
        'hour': BaseField,
        'minute': BaseField,
        'second': BaseField
    }

    __slots__ = 'timezone', 'fields', 'jitter'

    def __init__(self, month=None, day=None, day_of_week=None, hour=None,
                 minute=None, timezone=None):
        self.jitter = None
        if timezone:
            self.timezone = astimezone(timezone)
        else:
            self.timezone = get_localzone()

        values = dict((key, value) for (key, value) in six.iteritems(locals())
                      if key in self.FIELD_NAMES and value is not None)
        self.fields = []
        assign_defaults = False
        for field_name in self.FIELD_NAMES:
            if field_name in values:
                exprs = values.pop(field_name)
                is_default = False
                assign_defaults = not values
            elif assign_defaults:
                exprs = DEFAULT_VALUES[field_name]
                is_default = True
            else:
                exprs = '*'
                is_default = True

            field_class = self.FIELDS_MAP[field_name]
            field = field_class(field_name, exprs, is_default)
            self.fields.append(field)

    @classmethod
    def from_crontab(cls, expr, timezone=None):
        """
        Create a :class:`~CronTrigger` from a standard crontab expression.

        See https://en.wikipedia.org/wiki/Cron for more information on the format accepted here.

        :param expr: minute, hour, day of month, month, day of week
        :param datetime.tzinfo|str timezone: time zone to use for the date/time calculations (
            defaults to scheduler timezone)
        :return: a :class:`~CronTrigger` instance

        """
        values = expr.split()
        if len(values) != 5:
            raise ValueError('Wrong number of fields; got {}, expected 5'.format(len(values)))

        return cls(minute=values[0], hour=values[1], day=values[2], month=values[3],
                   day_of_week=values[4], timezone=timezone)

    def _increment_field_value(self, dateval, fieldnum):
        """
        Increments the designated field and resets all less significant fields to their minimum
        values.

        :type dateval: datetime
        :type fieldnum: int
        :return: a tuple containing the new date, and the number of the field that was actually
            incremented
        :rtype: tuple
        """

        values = {}
        i = 0
        while i < len(self.fields):
            field = self.fields[i]
            if not field.REAL:
                if i == fieldnum:
                    fieldnum -= 1
                    i -= 1
                else:
                    i += 1
                continue

            if i < fieldnum:
                values[field.name] = field.get_value(dateval)
                i += 1
            elif i > fieldnum:
                values[field.name] = field.get_min(dateval)
                i += 1
            else:
                value = field.get_value(dateval)
                maxval = field.get_max(dateval)
                if value == maxval:
                    fieldnum -= 1
                    i -= 1
                else:
                    values[field.name] = value + 1
                    i += 1

        difference = datetime(**values) - dateval.replace(tzinfo=None)
        return normalize(dateval + difference), fieldnum

    def _set_field_value(self, dateval, fieldnum, new_value):
        values = {}
        for i, field in enumerate(self.fields):
            if field.REAL:
                if i < fieldnum:
                    values[field.name] = field.get_value(dateval)
                elif i > fieldnum:
                    values[field.name] = field.get_min(dateval)
                else:
                    values[field.name] = new_value

        return localize(datetime(**values), self.timezone)

    def get_next_fire_time(self, previous_fire_time):
        start_date = previous_fire_time + timedelta(microseconds=1)

        fieldnum = 0
        next_date = datetime_ceil(start_date).astimezone(self.timezone)
        while 0 <= fieldnum < len(self.fields):
            field = self.fields[fieldnum]
            curr_value = field.get_value(next_date)
            next_value = field.get_next_value(next_date)

            if next_value is None:
                # No valid value was found
                next_date, fieldnum = self._increment_field_value(next_date, fieldnum - 1)
            elif next_value > curr_value:
                # A valid, but higher than the starting value, was found
                if field.REAL:
                    next_date = self._set_field_value(next_date, fieldnum, next_value)
                    fieldnum += 1
                else:
                    next_date, fieldnum = self._increment_field_value(next_date, fieldnum)
            else:
                # A valid value was found, no changes necessary
                fieldnum += 1

        return next_date
