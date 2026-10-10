"""Pure ISO calendar functions, safe to embed after other setup statements.

Invalid or unsupported inputs return None (predicates return False). No wall clock,
file access, or network access. The compiler reads this source on the build machine.
Speech extraction supplies structured expressions; this module does not parse speech.
"""
import datetime
import json
import re


def _date(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return None
        return datetime.date.fromisoformat(value)
    except Exception:
        return None


def _calendar(holidays, business_days):
    try:
        if not isinstance(holidays, (list, tuple, set)) or not isinstance(business_days, (list, tuple, set)):
            return None
        if not business_days or any(type(x) is not int or x < 0 or x > 6 for x in business_days):
            return None
        if any(_date(x) is None for x in holidays):
            return None
        return set(holidays), set(business_days)
    except Exception:
        return None


def parse_now(value):
    """Return (ISO date, HH:MM) from a valid ISO local timestamp, else None.

    Offset-bearing timestamps retain their supplied local date/time; never convert
    to the machine timezone. Seconds, if supplied, must be zero to avoid truncation.
    """
    try:
        if not isinstance(value, str) or not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', value):
            return None
        dt = datetime.datetime.fromisoformat(value)
        if dt.second or dt.microsecond:
            return None
        return dt.date().isoformat(), dt.strftime('%H:%M')
    except Exception:
        return None


def is_business_day(day, holidays, business_days):
    d, cal = _date(day), _calendar(holidays, business_days)
    return bool(d is not None and cal is not None and d.weekday() in cal[1] and day not in cal[0])


def next_business_day(day, holidays, business_days, inclusive=True):
    try:
        d, cal = _date(day), _calendar(holidays, business_days)
        if d is None or cal is None or type(inclusive) is not bool:
            return None
        if not inclusive:
            d += datetime.timedelta(days=1)
        # Each holiday can exclude at most one weekly candidate; finite bound.
        for _ in range(7 * (len(cal[0]) + 1)):
            if d.weekday() in cal[1] and d.isoformat() not in cal[0]:
                return d.isoformat()
            d += datetime.timedelta(days=1)
    except Exception:
        pass
    return None


def nth_business_day_after(today, n, holidays, business_days):
    try:
        d, cal = _date(today), _calendar(holidays, business_days)
        if d is None or cal is None or type(n) is not int or n < 1:
            return None
        # Jump whole weeks, then compensate for excluded business-day holidays.
        weeks, remainder = divmod(n - 1, len(cal[1]))
        result = d + datetime.timedelta(days=weeks * 7)
        remaining = remainder + 1
        remaining += sum(d < _date(h) <= result and _date(h).weekday() in cal[1] for h in cal[0])
        while remaining:
            result = _date(next_business_day(result.isoformat(), holidays, business_days, False))
            if result is None:
                return None
            remaining -= 1
        return result.isoformat()
    except Exception:
        return None


add_business_days = nth_business_day_after


def last_business_day_of_week(day, holidays, business_days):
    try:
        d = _date(day)
        if d is None or _calendar(holidays, business_days) is None:
            return None
        monday = d - datetime.timedelta(days=d.weekday())
        for offset in range(6, -1, -1):
            candidate = (monday + datetime.timedelta(days=offset)).isoformat()
            if is_business_day(candidate, holidays, business_days):
                return candidate
    except Exception:
        pass
    return None


def _month_end(d):
    if d.month == 12:
        return datetime.date(d.year, 12, 31)
    return datetime.date(d.year, d.month + 1, 1) - datetime.timedelta(days=1)


def last_business_day_of_month(day, holidays, business_days):
    try:
        d = _date(day)
        if d is None or _calendar(holidays, business_days) is None:
            return None
        end = _month_end(d)
        for offset in range(end.day):
            candidate = (end - datetime.timedelta(days=offset)).isoformat()
            if is_business_day(candidate, holidays, business_days):
                return candidate
    except Exception:
        pass
    return None


def deadline(today, rule, holidays, business_days):
    """Non-business deadlines require explicit adjustment: none, following, preceding.

    end_of_month also requires basis=calendar or business. Never infer these choices.
    """
    try:
        d = _date(today)
        if d is None or not isinstance(rule, dict) or _calendar(holidays, business_days) is None:
            return None
        kind = rule.get('kind')
        if kind == 'nth_business_day':
            return nth_business_day_after(today, rule.get('n'), holidays, business_days)
        adjustment = rule.get('adjustment')
        if adjustment not in ('none', 'following', 'preceding'):
            return None
        if kind == 'calendar_days':
            n = rule.get('n')
            if type(n) is not int or n < 0:
                return None
            target = (d + datetime.timedelta(days=n)).isoformat()
        elif kind == 'fixed_date':
            target = rule.get('date')
        elif kind == 'end_of_month':
            if rule.get('basis') == 'business':
                target = last_business_day_of_month(today, holidays, business_days)
            elif rule.get('basis') == 'calendar':
                target = _month_end(d).isoformat()
            else:
                return None
        else:
            return None
        target_day = _date(target)
        if target_day is None:
            return None
        if adjustment == 'none':
            return target
        if adjustment == 'following':
            return next_business_day(target, holidays, business_days)
        for _ in range(7 * (len(holidays) + 1)):
            if is_business_day(target_day.isoformat(), holidays, business_days):
                return target_day.isoformat()
            target_day -= datetime.timedelta(days=1)
    except Exception:
        pass
    return None


def attempt_date(today, source, deadline_day, holidays, business_days):
    try:
        if _date(today) is None or _calendar(holidays, business_days) is None:
            return None
        if source == 'last_business_day_this_week_or_next':
            result = last_business_day_of_week(today, holidays, business_days)
            if result == today:
                return last_business_day_of_week((_date(today) + datetime.timedelta(days=7)).isoformat(), holidays, business_days)
            # A week already over cannot supply a future offer without a policy rule.
            return result if result and result >= today else None
        if source == 'deadline':
            return deadline_day if _date(deadline_day) else None
        if source == 'today':
            return today
        if source == 'next_business_day':
            return next_business_day(today, holidays, business_days, False)
    except Exception:
        pass
    return None


def resolve_date_expr(today, expr, calendar):
    """Structured expression -> ISO date, 'vague', or None.

    weekday is Monday=0. Missing year/month require missing_date_parts='next_occurrence'.
    Explicit past dates remain past for downstream validation. No holiday adjustment.
    """
    try:
        d = _date(today)
        if d is None or not isinstance(expr, dict) or not isinstance(calendar, dict):
            return None
        if set(expr) - set(('weekday', 'relative', 'day', 'month', 'year', 'keyword')):
            return None
        if 'keyword' in expr:
            if len(expr) != 1:
                return None
            key = expr['keyword']
            if key == 'vague':
                return 'vague'
            if key in ('today', 'tomorrow'):
                return (d + datetime.timedelta(days=int(key == 'tomorrow'))).isoformat()
            return None
        if 'weekday' in expr:
            if set(expr) - set(('weekday', 'relative')):
                return None
            wd, rel = expr['weekday'], expr.get('relative')
            if type(wd) is not int or not 0 <= wd <= 6 or rel not in ('this', 'next'):
                return None
            if rel == 'this':
                delta = wd - d.weekday()
            else:
                following = calendar.get('next_weekday_means_following_week')
                if type(following) is not bool:
                    return None
                delta = wd - d.weekday() + 7 if following else (wd - d.weekday()) % 7 or 7
            return (d + datetime.timedelta(days=delta)).isoformat()
        if 'relative' in expr or type(expr.get('day')) is not int:
            return None
        day, month, year = expr['day'], expr.get('month'), expr.get('year')
        if not 1 <= day <= 31 or (month is not None and (type(month) is not int or not 1 <= month <= 12)):
            return None
        if year is not None:
            if type(year) is not int or month is None:
                return None
            return datetime.date(year, month, day).isoformat()
        if calendar.get('missing_date_parts') != 'next_occurrence':
            return None
        # At most one Gregorian 400-year cycle; includes leap-day edge cases.
        for y in range(d.year, min(d.year + 401, 10000)):
            for m in ([month] if month is not None else range(1, 13)):
                try:
                    candidate = datetime.date(y, m, day)
                except ValueError:
                    continue
                if candidate >= d:
                    return candidate.isoformat()
    except Exception:
        pass
    return None


def _time(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{2}:\d{2}', value):
            return None
        return datetime.time.fromisoformat(value)
    except Exception:
        return None


def callback_ok(now, date, time, policy):
    """Validate an extracted ISO date/HH:MM. Does not interpret 'around eleven'."""
    try:
        parsed = parse_now(now)
        if parsed is None or not isinstance(policy, dict):
            return False
        today, current = parsed
        day, clock = _date(date), _time(time)
        start, end = _time(policy.get('start')), _time(policy.get('end'))
        holidays, business_days = policy.get('holidays'), policy.get('business_days')
        if day is None or clock is None or start is None or end is None or start > end:
            return False
        if _calendar(holidays, business_days) is None or not start <= clock <= end:
            return False
        after = policy.get('must_be_after_now')
        if type(after) is not bool:
            return False
        if date < today or (after and date == today and clock <= _time(current)):
            return False
        next_day = next_business_day(today, holidays, business_days, False)
        rule = policy.get('days')
        if rule == 'today':
            return date == today
        if rule == 'next_business_day':
            return date == next_day
        if rule == 'today_or_next_business_day':
            return date in (today, next_day)
    except Exception:
        pass
    return False


# Compatibility helpers for the handoff API. These intentionally recognize a small
# explicit grammar; ambiguous speech is left unresolved for the extractor to clarify.
_UNITS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
_TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
_ORDINALS = dict(zip('first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth thirtieth'.split(), list(range(1, 21)) + [30]))
_MONTHS = 'january february march april may june july august september october november december'.split()
_WEEKDAYS = 'monday tuesday wednesday thursday friday saturday sunday'.split()


def _words_number(text):
    try:
        tokens = text.lower().replace('-', ' ').split()
        if not tokens or len(tokens) > 40:
            return None
        total, group, previous = 0, 0, ''
        for word in tokens:
            if word == 'and':
                continue
            if word in _UNITS or word in _TENS or word in _ORDINALS:
                value = _UNITS.get(word, _TENS.get(word, _ORDINALS.get(word)))
                # Adjacent unit words are not a cardinal number.
                if previous in _UNITS or previous in _ORDINALS:
                    return None
                if previous in _TENS and value >= 10:
                    return None
                group += value
            elif word == 'hundred' and 0 < group < 10:
                group *= 100
            elif word == 'thousand' and 0 < group < 1000 and total == 0:
                total, group = group * 1000, 0
            else:
                return None
            previous = word
        return total + group
    except Exception:
        return None


def normalize_digits(text, n):
    try:
        if not isinstance(text, str) or type(n) is not int or n < 1:
            return None
        parts = re.split(r'[\s-]+', text.strip().lower())
        digits = ''
        for part in parts:
            if re.fullmatch(r'[0-9]+', part):
                digits += part
            elif part in _UNITS and _UNITS[part] < 10:
                digits += str(_UNITS[part])
            else:
                return None
        return digits if len(digits) == n else None
    except Exception:
        return None


def parse_amount(text):
    try:
        if not isinstance(text, str):
            return None
        value = text.strip().lower()
        if re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?', value):
            number = float(value.replace(',', ''))
            return number if number < float('inf') else None
        if ' point ' in value:
            whole, frac = value.split(' point ')
            integer = _words_number(whole)
            fractional = _words_number(frac)
            digits = normalize_digits(frac, 2)
            if integer is None or (digits is None and (fractional is None or not 0 <= fractional <= 99)):
                return None
            # 'point ten' = .10; 'point five' = .5; 'point zero five' = .05.
            if digits is None:
                digits = str(fractional)
            return float(str(integer) + '.' + digits)
        # Explicit colloquial cents form; reject other adjacent cardinal numbers.
        tokens = value.replace('-', ' ').split()
        if len(tokens) > 2 and tokens[-1] in _TENS and tokens[-2] in _UNITS:
            whole = _words_number(' '.join(tokens[:-1]))
            if whole is not None and whole >= 100:
                return whole + _TENS[tokens[-1]] / 100
        integer = _words_number(value)
        if integer is not None:
            return float(integer)
    except Exception:
        pass
    return None


def _year(text):
    if re.fullmatch(r'\d{4}', text):
        return int(text)
    tokens = text.replace('-', ' ').split()
    if tokens and tokens[0] in ('nineteen', 'eighteen', 'seventeen', 'twenty') and len(tokens) > 1:
        high = _words_number(tokens[0])
        low = _words_number(' '.join(tokens[1:]))
        if low is not None and 0 <= low < 100:
            return high * 100 + low
    result = _words_number(text)
    return result if result is not None and 1000 <= result <= 9999 else None


def normalize_date_answer(text, numeric_order='dmy'):
    try:
        if not isinstance(text, str) or numeric_order not in ('dmy', 'mdy'):
            return None
        text = text.strip().lower()
        if _date(text):
            return text
        match = re.fullmatch(r'(\d{1,2})[/.\s]+(\d{1,2})[/.\s]+(\d{4})', text)
        if match:
            a, b, year = map(int, match.groups())
            day, month = (a, b) if numeric_order == 'dmy' else (b, a)
            return datetime.date(year, month, day).isoformat()
        for month, name in enumerate(_MONTHS, 1):
            match = re.fullmatch(r'(.*?)\s+' + name + r'\s+(.+)', text)
            if match:
                day_text = re.sub(r'^(the )| of$', '', match[1]).strip()
                day_text = re.sub(r'(\d+)(st|nd|rd|th)$', r'\1', day_text)
                day = int(day_text) if day_text.isdigit() else _words_number(day_text)
                year = _year(match[2])
                if day is not None and year is not None:
                    return datetime.date(year, month, day).isoformat()
    except Exception:
        pass
    return None


def resolve_date_expression(expr, today, holidays, business_days, numeric_order='dmy', next_weekday_means_following_week=True):
    """Legacy small-grammar adapter; production extraction should use resolve_date_expr."""
    try:
        if not isinstance(expr, str) or _calendar(holidays, business_days) is None:
            return dict(status='unreadable')
        text = expr.strip().lower()
        calendar = dict(next_weekday_means_following_week=next_weekday_means_following_week, missing_date_parts='next_occurrence')
        structured = None
        if text in ('next week', 'end of the month', 'in two weeks', 'when my salary comes', 'the week after next'):
            structured = dict(keyword='vague')
        elif text in ('today', 'tomorrow'):
            structured = dict(keyword=text)
        elif text == 'day after tomorrow':
            return dict(status='ok', date=(_date(today) + datetime.timedelta(days=2)).isoformat())
        elif _date(text):
            return dict(status='ok', date=text)
        else:
            for index, name in enumerate(_WEEKDAYS):
                if text in (name, 'this ' + name, 'next ' + name):
                    structured = dict(weekday=index, relative='next' if text.startswith('next ') else 'this')
            if structured is None:
                text = re.sub(r'^(?:' + '|'.join(_WEEKDAYS) + r')\s+', '', text)
                text = re.sub(r'^the\s+', '', text)
                text = text.replace(' of ', ' ')
                text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text)
                numeric = re.fullmatch(r'(\d{1,2})[/.](\d{1,2})(?:[/.](\d{4}))?', text)
                if numeric:
                    if numeric_order not in ('dmy', 'mdy'):
                        return dict(status='unreadable')
                    a, b = int(numeric[1]), int(numeric[2])
                    structured = dict(day=a if numeric_order == 'dmy' else b, month=b if numeric_order == 'dmy' else a)
                    if numeric[3]:
                        structured['year'] = int(numeric[3])
                else:
                    for month, name in enumerate(_MONTHS, 1):
                        if text.endswith(' ' + name) or text.startswith(name + ' '):
                            day_text = text.replace(name, '').strip()
                            day = int(day_text) if day_text.isdigit() else _words_number(day_text)
                            structured = dict(day=day, month=month)
                            break
                    if structured is None:
                        day = int(text) if text.isdigit() else _words_number(text)
                        structured = dict(day=day)
        result = resolve_date_expr(today, structured, calendar)
        if result == 'vague':
            return dict(status='vague')
        return dict(status='ok', date=result) if result else dict(status='unreadable')
    except Exception:
        return dict(status='unreadable')


def callback_slot(today, now_time, day_expr, time_expr, window_start, window_end, days_rule, holidays, business_days):
    try:
        # Explicitly strip a part-of-day qualifier; it does not supply the hour.
        day_expr = re.sub(r'\s+(morning|afternoon|evening)$', '', day_expr.strip().lower())
        resolved = resolve_date_expression(day_expr, today, holidays, business_days)
        raw = re.sub(r'^around\s+', '', time_expr.strip().lower())
        suffix = re.search(r'(am|pm)$', raw)
        if suffix:
            raw = raw[:-2].strip()
        if _time(raw):
            clock = raw
        else:
            hour = int(raw) if raw.isdigit() else _words_number(raw)
            if hour is None or not 0 <= hour <= 23:
                return dict(status='unreadable')
            if suffix:
                if not 1 <= hour <= 12:
                    return dict(status='unreadable')
                hour = hour % 12 + (12 if suffix[1] == 'pm' else 0)
            clock = '%02d:00' % hour
        if resolved.get('status') != 'ok':
            return dict(status='unreadable')
        policy = dict(start=window_start, end=window_end, days=days_rule, must_be_after_now=True, holidays=holidays, business_days=business_days)
        if callback_ok(today + 'T' + now_time, resolved['date'], clock, policy):
            return dict(status='ok', date=resolved['date'], time=clock)
        return dict(status='outside')
    except Exception:
        return dict(status='unreadable')


def validate_proposal(today, deadline_day, proposed_date, date_status, proposed_amount, floor, full, holidays, business_days):
    try:
        if _date(today) is None or _date(deadline_day) is None or _calendar(holidays, business_days) is None:
            return dict(verdict='unreadable')
        amount = full if proposed_amount is None else proposed_amount
        if any(type(v) not in (int, float) or not 0 <= v < float('inf') for v in (amount, floor, full)) or floor > full:
            return dict(verdict='unreadable')
        result = dict(verdict='ok', date=proposed_date or '', amount='%.2f' % amount, offer_date='', offer_amount='')
        if date_status in ('vague', 'unreadable'):
            result['verdict'] = date_status
        elif date_status != 'ok' or _date(proposed_date) is None:
            result['verdict'] = 'unreadable'
        elif proposed_date < today:
            result['verdict'] = 'past'
        elif proposed_date > deadline_day:
            result.update(verdict='after_deadline', offer_date=deadline_day)
        elif not is_business_day(proposed_date, holidays, business_days):
            rolled = next_business_day(proposed_date, holidays, business_days)
            if rolled is None:
                result['verdict'] = 'unreadable'
            elif rolled > deadline_day:
                result.update(verdict='after_deadline', offer_date=deadline_day)
            else:
                result.update(verdict='roll_forward', offer_date=rolled)
        elif amount < floor:
            result.update(verdict='below_floor', offer_amount='%.2f' % floor)
        elif amount > full:
            result.update(verdict='above_full', offer_amount='%.2f' % full)
        return result
    except Exception:
        return dict(verdict='unreadable')
