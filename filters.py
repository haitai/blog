import datetime
import hashlib,urllib#,md5

#from django.template.defaultfilters import timesince
from django.conf import settings
import urllib
from markupsafe import Markup
UTC_OFFSET = getattr(settings, "UTC_OFFSET", 0)
def bettertimesince(dt):
    #delta = datetime.datetime.utcnow() - dt
    delta = datetime.datetime.utcnow() - dt + datetime.timedelta(hours=UTC_OFFSET)
    #local_dt = dt + datetime.timedelta(hours=UTC_OFFSET)
    local_dt = dt
    if delta.days == 0:
        #return timesince(dt) + " ago"
        fudge = 1.25
        delta = delta.seconds
        if delta < (1 * fudge):
            return 'about a second ago'
        elif delta < (60 * (1/fudge)):
            return 'about %d seconds ago' % (delta)
        elif delta < (60 * fudge):
            return 'about a minute ago'
        elif delta < (60 * 60 * (1/fudge)):
            return 'about %d minutes ago' % (delta / 60)
        elif delta < (60 * 60 * fudge):
            return 'about an hour ago'
        else:
            return 'about %d hours ago' % (delta / (60 * 60))
        
    elif delta.days == 1:
        return "Yesterday" + local_dt.strftime(" at %I:%M %p")
    elif delta.days < 5:
        return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][local_dt.weekday()] + local_dt.strftime(" at %I:%M %p")
    elif delta.days < 365:
        return local_dt.strftime("%B %d at %I:%M %p")
    else:
        return local_dt.strftime("%B %d, %Y")

def contentshortor(c, n):
    if len(c) > int(n):
        return c[:n] + "..."
    else:
        return c

def localelist(tags):
    parts = []
    for tag in tags:
        parts.append('<a href="/tag/%s">%s</a>' %(tag,tag))
    if len(parts) == 0:
        return ""
    if len(parts) == 1:
        return parts[0]
    comma = u", "
    if len(parts) == 2:
        return "%s and %s" %(parts[0],parts[1])
    return "%s and %s" % (comma.join(parts[:-1]),parts[len(parts) - 1])

def restrict_to_max(value,max):
    if int(value) <= int(max):
        return value
    else:
        return max

def gravatar(email,size):
    imgurl = "http://www.gravatar.com/avatar/"
    imgurl +=hashlib.md5(email).hexdigest()+"?"+ urllib.urlencode({'s':str(size),'r':'G'})
    return imgurl
    
def date(value,format):
    return value.strftime(format)
def urlencode_filter(s):
    if type(s) == 'Markup':
        s = s.unescape()
    s = s.encode('utf8')
    s = urllib.quote_plus(s)
    return Markup(s)