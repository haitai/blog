# -*- coding: utf-8 -*-

import xml.etree.ElementTree as et
import functools
import hashlib
import logging
import os
import re
import uuid
import urllib
import datetime
import time
import string
import urlparse
from email.header import decode_header
#from email.utils import parseaddr
import difflib

from lib import BeautifulSoup,markdown2,textile
from lib import feedparser
from lib.plainhtml import convertWebIntelligentPlainTextToHtml


from django.template.defaultfilters import slugify
from django.utils import feedgenerator
from django.utils import simplejson

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.api import mail

from google.appengine.ext import db
#from google.appengine.ext import webapp
from wtforms_appengine.db import model_form
from wtforms import Form, TextField, widgets
#from google.appengine.ext.webapp import template
#from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
import webapp2
from webapp2_extras import jinja2
import filters

LINKS = [
    {"url": "https://www.huhaitai.com", "value": "www"},
    {"url":"https://t.huhaitai.com","value":"micro blog"},
]

def jinja2_factory(app):
    j = jinja2.Jinja2(app)
    j.environment.filters.update({
        'bettertimesince':filters.bettertimesince,
        'contentshortor':filters.contentshortor,
        'localelist':filters.localelist,
        'restrict_to_max':filters.restrict_to_max,
        'gravatar':filters.gravatar,
        'date':filters.date,
        'urlencode ':filters.urlencode_filter,
        'bettermonth':filters.bettermonth,
        'hidenickname':filters.hidenickname,
    })
    j.environment.globals.update({
        'uri_for': webapp2.uri_for,
    })
    return j
def admin(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        user = users.get_current_user()
        if not user:
            if self.request.method == "GET":
                return self.redirect(users.create_login_url(self.request.uri))
            return self.error(403)
        elif not users.is_current_user_admin():
            return self.error(403)
        else:
            return method(self, *args, **kwargs)
    return wrapper

def to_html(body,body_format):
    if body_format == 'markdown':
        body_html = markdown2.markdown(body)
    elif body_format == 'textile':
        body_html = textile.textile(body).decode('utf-8')
    elif body_format == 'txt':
        body_html = convertWebIntelligentPlainTextToHtml(body).decode('utf-8')
    else:
        #import cgi
        #body = cgi.escape(body)
        body_html = body
    return body_html

def urldecode(value):
    return  urllib.unquote(urllib.unquote(value)).decode('utf8')

class MediaRSSFeed(feedgenerator.Atom1Feed):
    def root_attributes(self):
        attrs = super(MediaRSSFeed, self).root_attributes()
        attrs["xmlns:media"] = "http://search.yahoo.com/mrss/"
        return attrs

    def add_root_elements(self, handler):
        super(MediaRSSFeed, self).add_root_elements(handler)
        handler.addQuickElement(u"link", "", {u"rel": u"hub", u"href": "http://pubsubhubbub.appspot.com/"})

    def add_item_elements(self, handler, item):
        super(MediaRSSFeed, self).add_item_elements(handler, item)
        self.add_thumbnails_element(handler, item)

    def add_thumbnail_element(self, handler, item):
        thumbnail = item.get("thumbnail", None)
        if thumbnail:
            if thumbnail["title"]:
                handler.addQuickElement("media:title", title)
            handler.addQuickElement("media:thumbnail", "", {
                "url": thumbnail["url"],
            })

    def add_thumbnails_element(self, handler, item):
        thumbnails = item.get("thumbnails", [])
        for thumbnail in thumbnails:
            handler.startElement("media:group", {})
            if thumbnail["title"]:
                handler.addQuickElement("media:title", thumbnail["title"])
            handler.addQuickElement("media:thumbnail", "", thumbnail)
            handler.endElement("media:group")

def show_diff(seqm):
    output= []
    for opcode, a0, a1, b0, b1 in seqm.get_opcodes():
        if opcode == 'equal':
            output.append(seqm.a[a0:a1])
        elif opcode == 'insert':
            output.append("<ins>" + seqm.b[b0:b1] + "</ins>")
        elif opcode == 'delete':
            output.append("<del>" + seqm.a[a0:a1] + "</del>")
        elif opcode == 'replace':
            output.append( "<del>"+ seqm.a[a0:a1] + "</del><ins>" + seqm.b[b0:b1] + "</ins>" )
        else:
            raise RuntimeError, "unexpected opcode"
    return ''.join(output)
class Blogentry(db.Model):
    author = db.UserProperty()
    title = db.StringProperty()
    slug = db.StringProperty()
    source = db.StringProperty(required=False)
    to_url = db.StringProperty()
    to_title = db.StringProperty()
    body = db.TextProperty()
    body_html = db.TextProperty()
    body_format = db.StringProperty(required=True, default='html', indexed=True)
    published = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now_add=True)
    tags = db.ListProperty(db.Category)
    koment = db.BooleanProperty(default=True) #allow comment
    entrytype = db.StringProperty(multiline=False,default='post',choices=['post','comment','status','page'])
    #is_published = db.BooleanProperty(default="True")
    _relatepost=None

    @property
    def year(self):
        return self.published.strftime('%Y')
    @property
    def month(self):
        return self.published.strftime('%m')
    @property
    def day(self):
        return self.published.strftime('%d')
    @property
    def link(self):
        if self.entrytype == 'post':
            return '/' + self.year +'/' + self.month +'/' +self.slug
        elif self.entrytype == 'comment':
            return '/comment/' + str(self.key().id())
        elif self.entrytype == 'status':
            return '/saying/' + str(self.key().id())
        else:
            return '/page/' + self.slug

    @property
    def body_excerpt(self):
        return self.get_body_excerpt(('Read more...').decode('utf8'))

    def get_body_excerpt(self,more='..more'):
        sc=self.body_html.split('<!--more-->')
        if len(sc)>1:
            return sc[0]+u' <p class="more"><a href="%s#more">%s</a></p>'%(self.link,more)
        else:
            return sc[0]

    @property
    def next(self):
        return db.GqlQuery("SELECT * FROM Blogentry WHERE entrytype =:1 and published <:2 ORDER BY published DESC","post",self.published).fetch(1)

    @property
    def prev(self):
        return db.GqlQuery("SELECT * FROM Blogentry WHERE entrytype =:1 and published >:2 ORDER BY published ASC","post",self.published).fetch(1)

    @property
    def relateposts(self):
        if  self._relatepost:
            return self._relatepost
        else:
            if self.tags:
                self._relatepost= Blogentry.gql("WHERE tags IN :1 and published!=:2 order by published desc ",self.tags,self.published).fetch(5)
            else:
                self._relatepost= []
            return self._relatepost
    @property
    def comments_count(self):
        to_url=self.link
        self._pagecomments= db.Query(Blogentry).filter('entrytype =','comment').filter('to_url',to_url).order("-published").fetch(999)
        return len(self._pagecomments)
    @property
    def replycomments(self):
        if self.entrytype == 'comment':
            to_url=self.link
            replycomments= db.Query(Blogentry).filter('entrytype =','comment').filter('to_url',to_url).order("-published").fetch(999)
            return replycomments

class BlogConfig(db.Model):
    TITLE = db.StringProperty(default="jot")
    NAME = db.StringProperty(default="Hu Haitai")
    EMAIL = db.EmailProperty(default="huhaitai@huhaitai.com")
    SYNC_MAIL = db.EmailProperty()
    BASEURL = db.StringProperty(default="http://jot.huhaitai.com") #ended without the slash
    FEED_SMITH = db.StringProperty()
    NUM_MAIN = db.IntegerProperty(default=13)
    NUM_RECENT = db.IntegerProperty(default=5)
    NUM_COMMENTS = db.IntegerProperty(default=19)
    NUM_STATUSES = db.IntegerProperty(default=21)
    UTC_OFFSET = db.IntegerProperty(default=+8)
    RPC_USERNAME = db.StringProperty()
    PRC_PASSWORD = db.StringProperty()
    WEBMASTER_VERIFICATION_CONTENT =  db.StringProperty()
    ANALYTICS =  db.StringProperty()
    SHOW_ENTRYCOUNT = db.BooleanProperty(default=False)
    INDEXED_ALLOWED = db.BooleanProperty(default=True)


blogconfig=BlogConfig.get_by_key_name("default")
if not blogconfig:
    blogconfig = BlogConfig(key_name = 'default')

BlogentryForm=model_form(Blogentry,exclude=('to_url', 'to_title','body_format','entrytype','body_html'))
BlogconfigForm=model_form(BlogConfig)
class Archive(db.Model):
    monthyear = db.StringProperty(multiline=False) #September 2008
    year = db.StringProperty(multiline=False) #2008
    month = db.StringProperty(multiline=False) #09
    entrycount = db.IntegerProperty(default=0)
    date = db.DateTimeProperty(auto_now_add=True)
    def link(self):
        return '/' + self.year + '/' + self.month

    @property
    def entries(self):
        firstday=datetime.datetime(int(self.year),int(self.month),1)
        if int(self.month)!=12:
            lastday=datetime.datetime(int(self.year),int(self.month)+1,1)
        else:
            lastday=datetime.datetime(int(self.year)+1,1,1)
        entries=db.GqlQuery("SELECT * FROM Blogentry WHERE published > :1 AND published <:2 AND entrytype =:3 ORDER BY published DESC",firstday,lastday,'post')
        return entries

class Tag(db.Model):
    name = db.StringProperty(multiline=False)
    entrycount = db.IntegerProperty(default=0)
    def link(self):
        return '/tag/' + self.name
    @classmethod
    def add(cls,value):
        if value:
            tag= Tag.get_by_key_name(value)
            if not tag:
                tag=Tag(key_name=value)
                tag.name=value
            tag.entrycount+=1
            tag.put()
            return tag
        else:
            return None
    @classmethod
    def remove(cls,value):
        if value:
            tag= Tag.get_by_key_name(value)
            if tag:
                if tag.entrycount>1:
                    tag.entrycount-=1
                    tag.put()
                else:
                    tag.delete()
    @property
    def entries(self):
        tag = urldecode(self.name)
        entries = db.Query(Blogentry).filter('entrytype =','post').filter("tags =", tag).order("-published")
        return entries

class Media(db.Model):
    name =db.StringProperty()
    mtype=db.StringProperty()
    bits=db.BlobProperty()
    date=db.DateTimeProperty(auto_now_add=True)

class BaseRequestHandler(webapp2.RequestHandler):
    def initialize(self, request, response):
        webapp2.RequestHandler.initialize(self, request, response)
        if request.path.endswith("/") and not request.path == "/":
            redirect = request.path[:-1]
            if request.query_string:
                redirect += "?" + request.query_string
            return self.redirect(redirect, permanent=True)

    def head(self, *args, **kwargs):
        pass

    def raise_error(self, code):
        self.error(code)
        self.render("%i.html" % code)

    def get_last_updated(self):
        key = "time/last_updated"
        last_updated = memcache.get(key)
        if not last_updated:
            last_updated_entries=db.Query(Blogentry).order("-updated").fetch(1)
            if len(last_updated_entries) >0:
                last_updated = last_updated_entries[0].updated
                memcache.set(key, last_updated)
        return last_updated

    def get_main_page_entries(self, num=blogconfig.NUM_MAIN,order=0):
        if order:
            key = "entries/main/order/%d" % num
        else:
            key = "entries/main/%d" % num
        entries = memcache.get(key)
        if not entries:
            if order:
                entries = db.Query(Blogentry).order("published").fetch(limit=num)
            else:
                entries = db.Query(Blogentry).order("-published").fetch(limit=num)
            memcache.set(key, list(entries))
        return entries

    def get_archive_entries(self,meta):
        if meta == 'sitemap':
            key = "entries/meta/sitemap"
        if meta == 'recent':
            key = "entries/meta/recent/%s" %blogconfig.NUM_RECENT
        if meta == 'archive':
            key = "entries/meta/archive"
        if meta == 'feed':
            key = "entries/meta/feed/%s" %blogconfig.NUM_MAIN
        entries = memcache.get(key)
        if not entries:
            if meta == 'sitemap':
                entries = db.Query(Blogentry).order("-published").fetch(999)
            if meta == 'archive':
                entries = db.Query(Blogentry).filter('entrytype =','post').order("-published").fetch(999)
            if meta == 'recent':
                entries = db.Query(Blogentry).filter('entrytype =','post').order("-published").fetch(limit=blogconfig.NUM_RECENT)
            if meta == 'feed':
                entries = db.Query(Blogentry).filter('entrytype =','post').order("-published").fetch(limit=blogconfig.NUM_MAIN)
            memcache.set(key, list(entries))
        return entries

    def get_items(self,entrytype):
        key = "%s/archive" %entrytype
        entries = memcache.get(key)
        if not entries:
            if entrytype == 'comment':
                entries = db.Query(Blogentry).filter('entrytype =',entrytype).order("-published").fetch(blogconfig.NUM_COMMENTS)
            elif entrytype == 'status':
                entries = db.Query(Blogentry).filter('entrytype =',entrytype).order("-published").fetch(blogconfig.NUM_STATUSES)
            else:
                entries = db.Query(Blogentry).filter('entrytype =',entrytype).order("-published").fetch(999)
            memcache.set(key, list(entries))
        return entries

    def get_entries_tags(self):
        key = "entries/meta/tags"
        tags = memcache.get(key)
        if not tags:
            tags = Tag.all()#db.Query(Tag)
            tags = set(tags)
            memcache.set(key, list(tags))
        return tags

    def get_entries_months(self):
        key = "entries/meta/months"
        months = memcache.get(key)
        if not months:
            months = Archive.all().order("-date")#db.Query(Archive).order("-date")
            #months = set(months)
            memcache.set(key, list(months))
        return months

    def get_entry_from_slug(self, slug):
        key = "entry/slug/%s" % slug
        entry = memcache.get(key)
        if not entry:
            entry = db.Query(Blogentry).filter("slug =", slug).get()
            if entry:
                memcache.set(key, entry)
        return entry

    def get_entry_from_id(self, id):
        key = "entry/id/%s" % id
        entry = memcache.get(key)
        if not entry:
            entry = Blogentry.get_by_id(int(id))
            if entry:
                memcache.set(key, entry)
        return entry

    def get_tagged_entries(self, tag):
        tag = urldecode(tag)
        key = "entries/tag/%s" % tag
        entries = memcache.get(key)
        if not entries:
            entries = db.Query(Blogentry).filter('entrytype =','post').filter("tags =", tag).order("-published")
            memcache.set(key, list(entries))
        return entries

    def get_monthly_entries(self, month, year):
        key = "entries/month/%s/%s" % (year,month)
        entries = memcache.get(key)
        if not entries:
            firstday=datetime.datetime(int(year),int(month),1)
            if int(month)!=12:
                lastday=datetime.datetime(int(year),int(month)+1,1)
            else:
                lastday=datetime.datetime(int(year)+1,1,1)
            entries=db.GqlQuery("SELECT * FROM Blogentry WHERE published > :1 AND published <:2 AND entrytype =:3 ORDER BY published DESC",firstday,lastday,'post')
            memcache.set(key, list(entries))
        return entries

    def get_yearly_entries(self, year):
        key = "entries/year/%s" % (year)
        entries = memcache.get(key)
        if not entries:
            firstday=datetime.datetime(int(year),1,1)
            lastday=datetime.datetime(int(year)+1,1,1)
            entries=db.GqlQuery("SELECT * FROM Blogentry WHERE published > :1 AND published <:2 AND entrytype =:3 ORDER BY published DESC",firstday,lastday,'post')
            memcache.set(key, list(entries))
        return entries

    def kill_entries_cache(self, slug=None, tags=[], month=None, year=None):
        memcache.delete("time/last_updated")
        memcache.delete("entries/main/order/%d" %blogconfig.NUM_MAIN)
        memcache.delete("entries/main/%d" % blogconfig.NUM_MAIN)
        memcache.delete("entries/meta/sitemap")
        memcache.delete("entries/meta/recent/%s" %blogconfig.NUM_RECENT)
        memcache.delete("entries/meta/archive")
        memcache.delete("entries/meta/feed/%s" %blogconfig.NUM_MAIN)
        memcache.delete("page/archive")
        memcache.delete("entries/meta/tags")
        memcache.delete("entries/meta/months")

        if slug:
            memcache.delete("entry/slug/%s" % slug)
        for tag in tags:
            memcache.delete("entries/tag/%s" % tag)
        if month:
            memcache.delete("entries/month/%s" % month)
        if year:
            memcache.delete("entries/year/%s" % year)

    def update_tags_and_archives(self,entry,values=None,add=False,edit=False,remove=False,update_time=None):
        monthyear=entry.published.strftime('%B %Y')
        sy = entry.published.strftime('%Y')
        sm = entry.published.strftime('%m')
        archive = Archive.get_by_key_name(monthyear)
        if remove:
            if archive.entrycount > 1:
                archive.entrycount -= 1
                if update_time:
                    archive.date = update_time
                archive.put()
            else:
                archive.delete()
            for tag in entry.tags:
                Tag.remove(tag)
        if add:
            if not archive:
                archive=Archive(key_name=monthyear,monthyear=monthyear,year=sy,month=sm)
            archive.entrycount += 1
            if update_time:
                archive.date = update_time
            archive.put()
            for tag in entry.tags:
                Tag.add(tag)
        if edit:
            if values:
                if type(values)==type([]):
                    tags=values
                else:
                    tags=values.split(',')
                if not entry.tags:
                    removelist=[]
                    addlist=tags
                else:
                    removelist=[n for n in entry.tags if n not in tags]
                    addlist=[n for n in tags if n not in entry.tags]
                for v in removelist:
                    Tag.remove(v)
                for v in addlist:
                    Tag.add(v)
                entry.tags=tags

    def get_integer_argument(self, name, default):
        try:
            return int(self.request.get(name, default))
        except (TypeError, ValueError):
            return default

    def fetch_headers(self, url):
        key = "headers/" + url
        headers = memcache.get(key)
        if not headers:
            try:
                response = urlfetch.fetch(url, method=urlfetch.HEAD)
                if response.status_code == 200:
                    headers = response.headers
                    memcache.set(key, headers)
            except urlfetch.DownloadError:
                pass
        return headers

    def find_enclosure(self, html):
        soup = BeautifulSoup.BeautifulSoup(html)
        img = soup.find("img")
        if img:
            headers = self.fetch_headers(img["src"])
            if headers:
                enclosure = feedgenerator.Enclosure(img["src"],
                    headers["Content-Length"], headers["Content-Type"])
                return enclosure
        return None

    def find_thumbnails(self, html):
        soup = BeautifulSoup.BeautifulSoup(html)
        imgs = soup.findAll("img")
        thumbnails = []
        for img in imgs:
            if "nomediarss" in img.get("class", "").split():
                continue
            thumbnails.append({
                "url": img["src"],
                "title": img.get("title", img.get("alt", "")),
                "width": img.get("width", ""),
                "height": img.get("height", ""),
            })
        return thumbnails


    def getrelatedcomments(self):
        self.to_url=self.request.path
        key = "comments_to_url/%s/short" %str(self.to_url)
        self._relatedcomments = memcache.get(key)
        if not self._relatedcomments:
            self._relatedcomments= db.Query(Blogentry).filter('entrytype =','comment').filter('to_url',self.to_url).order("-published").fetch(5)
            memcache.set(key,self._relatedcomments)
        return self._relatedcomments

    def getpagecomments(self):
        self.to_url=self.request.path
        key = "comments_to_url/%s/all" %str(self.to_url)
        self._relatedcomments = memcache.get(key)
        if not self._relatedcomments:
            self._pagecomments= db.Query(Blogentry).filter('entrytype =','comment').filter('to_url',self.to_url).order("-published").fetch(999)
            memcache.set(key,self._relatedcomments)
        return self._pagecomments

    def render_feed(self, entries):
        f = MediaRSSFeed(
            title=blogconfig.TITLE,
            link="http://" + self.request.host + "/",
            description=blogconfig.TITLE,
            language="en",
        )
        for entry in entries[:10]:
            f.add_item(
                title=entry.title,
                link=self.entry_link(entry, absolute=True),
                description=entry.body,
                author_name=entry.author.nickname() if entry.author else blogconfig.RPC_USERNAME,
                pubdate=entry.published,
                categories=entry.tags,
                thumbnails=self.find_thumbnails(entry.body),
            )
        data = f.writeString("utf-8")
        self.response.headers["Content-Type"] = "application/atom+xml"
        self.response.out.write(data)

    def render_comments_feed(self, comments):
        f = MediaRSSFeed(
            title=blogconfig.TITLE + ' Comments',
            link="http://" + self.request.host + "/comments",
            description='Comments from'+ blogconfig.TITLE,
            language="en",
        )
        for comment in comments[:10]:
            if comment.body:
                comment_body = comment.body
            else:
                comment_body = '<i>This comment content removed by the blog administrator.</i>'
            f.add_item(
                title=comment.to_title if comment.to_title else r"[NO TITLE]",
                link="http://" + self.request.host + comment.to_url + '#' + str(comment.key().id()),
                description=comment_body,
                author_name=comment.author.nickname(),
                pubdate=comment.published,
            )
        data = f.writeString("utf-8")
        self.response.headers["Content-Type"] = "application/atom+xml"
        self.response.out.write(data)

    def render_statuses_feed(self, statuses):
        f = MediaRSSFeed(
            title=blogconfig.TITLE + ' Statuses',
            link="http://" + self.request.host + "/saying",
            description='Statuses from'+ blogconfig.TITLE,
            language="en",
        )
        for status in statuses[:10]:
            f.add_item(
                title=status.body,
                link="http://" + self.request.host + '/saying/' + str(status.key().id()),
                description=status.body,
                author_name=status.author.nickname(),
                pubdate=status.published,
            )
        data = f.writeString("utf-8")
        self.response.headers["Content-Type"] = "application/atom+xml"
        self.response.out.write(data)

    def render_json(self, entries):
        json_entries = [{
            "title": entry.title,
            "slug": entry.slug,
            "body": entry.body,
            "author": entry.author.nickname() if entry.author else blogconfig.RPC_USERNAME,
            "published": entry.published.isoformat(),
            "updated": entry.updated.isoformat(),
            "tags": entry.tags,
            "link": self.entry_link(entry, absolute=True),
        } for entry in entries]
        json = {"entries": json_entries}
        self.response.headers["Content-Type"] = "text/javascript"
        self.response.out.write(simplejson.dumps(json, sort_keys=True,
            indent=self.get_integer_argument("pretty", None)))
    @webapp2.cached_property
    def jinja2(self):
        return jinja2.get_jinja2(factory=jinja2_factory)
    def render(self, template_file, extra_context={}):
        format = self.request.get("format", None)
        type = self.request.get("type", None)
        if format == "atom":
            if type == 'comments':
                comments = self.get_items(entrytype='comment')
                return self.render_comments_feed(comments)
            elif type == 'statuses':
                statuses = self.get_items(entrytype='status')
                return self.render_statuses_feed(statuses)
            else:
                if "feed_entries" in extra_context:
                    return self.render_feed(extra_context["feed_entries"])
        if format == "json":
            if "feed_entries" in extra_context:
                return self.render_json(extra_context["feed_entries"])
        extra_context["request"] = self.request
        extra_context["curturl"] = self.request.path
        extra_context["admin"] = users.is_current_user_admin()
        extra_context["logined"] = users.get_current_user()
        extra_context["config"] = blogconfig
        extra_context["recent_entries"] = self.get_archive_entries(meta='recent')
        show_comments = self.request.get("show_comments", False)
        extra_context["show_comments"] = show_comments
        if show_comments:
            extra_context["relatedcomments"] = self.getpagecomments()
        else:
            extra_context["relatedcomments"] = self.getrelatedcomments()
        extra_context["pagecomments"] = self.getpagecomments()
        extra_context["all_tags"] = self.get_entries_tags()
        extra_context["pages"] = self.get_items(entrytype='page')
        extra_context["all_months"] = self.get_entries_months()
        extra_context["last_updated"] = self.get_last_updated()
        extra_context["localit"] = os.environ['SERVER_SOFTWARE']
        extra_context["LINKS"] = LINKS
        extra_context["diff"] = self.request.get("diff")               

        rv = self.jinja2.render_template(template_file, **extra_context)
        self.response.write(rv)

    def entry_link(self, entry, query_args={}, absolute=False):
        url =  entry.link
        if absolute:
            url = "http://" + self.request.host + url
        if query_args:
            url += "?" + urllib.urlencode(query_args)
        return url

    def translate(self,sl, tl, phrase):
        base_uri = "https://translate.googleapis.com/translate_a/single"
        #another translate api "https://translate.google.so/translate_a/t?client=any_client_id_works&sl=auto&tl=ru&q=wrapper&tbb=1&ie=UTF-8&oe=UTF-8"
        default_params = {'client': 'gtx','dt':'t'}

        args = default_params.copy()
        args.update({
            'sl':sl,
            'tl':tl,
            'q': urllib.quote_plus(phrase.encode('utf-8')),
        })
        argstring = '%s' % ('&'.join(['%s=%s' % (k,v) for (k,v)in args.iteritems()]))
        url = base_uri + '?'+ argstring
        # url = https://translate.googleapis.com/translate_a/single?client=gtx&sl=zh_CN&tl=en&dt=t&q=测试
        try:
            resp = simplejson.loads(urlfetch.fetch(url).content)
            return resp[0][0][0]
        except:
            return phrase

class ArchivePageHandler(BaseRequestHandler):
    '''all posts'''
    def get(self):
        extra_context = {
            "on_archive": True,
            "entries": self.get_archive_entries(meta='archive'),
            "comment_title":"All entries",
        }
        self.render("archive.html", extra_context)

class ArchivesPageHandler(BaseRequestHandler):
    def get(self):
        extra_context = {
            "on_archive": True,
            "entries": self.get_archive_entries(meta='archive'),
            "pages": self.get_items(entrytype='page'),
            "comment_title":"Archives",
        }
        self.render("archives.html", extra_context)

class DeleteBlogentryHandler(BaseRequestHandler):
    @admin
    def post(self):
        key = self.request.get("key")
        try:
            entry = db.get(key)
            self.update_tags_and_archives(entry,remove=True)
            entry.delete()
            self.kill_entries_cache(slug=entry.slug, tags=entry.tags, month=entry.published.strftime('%Y/%m'), year=entry.published.strftime('%Y'))
            data = {"success": True}
        except db.BadKeyError:
            data = {"success": False}
        json = simplejson.dumps(data)
        self.response.out.write(json)

class DeleteItemHandler(BaseRequestHandler):
    @admin
    def post(self):
        key = self.request.get("key")
        try:
            item = db.get(key)
            memcache.delete("entries/meta/sitemap")
            memcache.delete("time/last_updated")
            memcache.delete("entries/main/%d" % blogconfig.NUM_MAIN)
            memcache.delete("comment/archive")
            memcache.delete("status/archive")
            memcache.delete("page/archive")
            memcache.delete("entry/id/%s" %item.key().id())
            memcache.delete("entry/slug/%s" %item.slug)
            if item.entrytype == "comment":
                item.body = ''
                item.put()
            else:
                item.delete()
            data = {"success": True}
        except db.BadKeyError:
            data = {"success": False}
        json = simplejson.dumps(data)
        self.response.out.write(json)

class BlogentryPageHandler(BaseRequestHandler):
    def head(self, slug):
        entry = self.get_entry_from_slug(slug=slug)
        if not entry:
            self.error(404)

    def get(self,year,month, slug):
        entry = self.get_entry_from_slug(slug=slug)
        if not entry:
            return self.raise_error(404)
        if entry.entrytype == "page":
            return self.redirect(self.entry_link(entry,absolute=True),permanent=True)
        extra_context = {
            "entries": [entry], # So we can use the same template for everything
            "entry": entry, # To easily pull out the title
            "month": entry.published.strftime('%B'),
            #"year":  entry.published.strftime('%Y'),
            #"m":  entry.published.strftime('%m'),
            "invalid": self.request.get("invalid", False),
            "on_entry": True,
            "comment_title":entry.title,
        }
        self.render("entry.html", extra_context)

class SingelPagePageHandler(BaseRequestHandler):
    def head(self, slug):
        page = self.get_entry_from_slug(slug=slug)
        if not page:
            self.error(404)

    def get(self,slug):
        page = self.get_entry_from_slug(slug=slug)
        if not page:
            return self.raise_error(404)
        if page.entrytype == "post":
            return self.redirect(self.entry_link(page,absolute=True),permanent=True)
        extra_context = {
            "entries": [page], # So we can use the same template for everything
            "entry": page, # To easily pull out the title
            "comment_title":page.slug,
            "on_page":True,
        }
        self.render("page.html", extra_context)

class SingelCommentPageHandler(BaseRequestHandler):
    def head(self, id):
        comment = self.get_entry_from_id(id=id)
        if not comment:
            self.error(404)

    def get(self,id):
        comment = self.get_entry_from_id(id=id)
        if not comment:
            return self.raise_error(404)
        extra_context = {
            "comments": [comment], # So we can use the same template for everything
            "comment": comment, # To easily pull out the title
            "comment_title":"comment #%s" %comment.key().id(),
            "on_comment":True,
        }
        self.render("comment.html", extra_context)

class SingelStatusPageHandler(BaseRequestHandler):
    def head(self, id):
        status = self.get_entry_from_id(id=id)
        if not status:
            self.error(404)

    def get(self,id):
        status = self.get_entry_from_id(id=id)
        if not status:
            return self.raise_error(404)
        extra_context = {
            "statuses": [status], # So we can use the same template for everything
            "status": status, # To easily pull out the title
            "comment_title":"status #%s" %status.key().id(),
            "on_status":True,
        }
        self.render("status.html", extra_context)

class FeedRedirectHandler(BaseRequestHandler):
    def get(self,type=None):
        if type:
            feed_url = "/?format=atom&type=%s" %type
        else:
            feed_url = "/?format=atom"
        self.redirect(feed_url, permanent=True)

class MainPageHandler(BaseRequestHandler):
    def get(self):
        offset = self.get_integer_argument("start", 0)
        order = self.get_integer_argument("order", 0)
        if not offset:
            if order:
                entries = self.get_main_page_entries(order=1)
            else:
                entries = self.get_main_page_entries()
        else:
            if order:
                entries = db.Query(Blogentry).order("published").fetch(limit=blogconfig.NUM_MAIN,
                                offset=offset)
            else:
                entries = db.Query(Blogentry).order("-published").fetch(limit=blogconfig.NUM_MAIN,
                offset=offset)
        if not entries and offset > 0:
            return self.redirect("/")
        feed_entries = self.get_archive_entries(meta='feed')
        extra_context = {
            "entries": entries,
            "feed_entries": feed_entries,
            "next": max(offset - blogconfig.NUM_MAIN, 0),
            "previous": offset + blogconfig.NUM_MAIN if len(entries) == blogconfig.NUM_MAIN else None,
            "offset": offset,
            "order":order,
            "on_homepage": True,
            "comment_title":"Home",
        }
        self.render("main.html", extra_context)

class CommentsPageHandler(BaseRequestHandler):
    def get(self):
        offset = self.get_integer_argument("start", 0)
        if not offset:
            comments = self.get_items(entrytype='comment')
        else:
            comments = db.Query(Blogentry).filter('entrytype =','comment').order("-published").fetch(limit=blogconfig.NUM_COMMENTS,
                offset=offset)
        if not comments and offset > 0:
            return self.redirect("/comments")
        extra_context = {
            "comments": comments,
            "next": max(offset - blogconfig.NUM_COMMENTS, 0),
            "previous": offset + blogconfig.NUM_COMMENTS if len(comments) == blogconfig.NUM_COMMENTS else None,
            "offset": offset,
            "on_comments":True,
            "comment_title":"Comments",
        }
        self.render("comments.html", extra_context)

class StatusesPageHandler(BaseRequestHandler):
    def get(self):
        offset = self.get_integer_argument("start", 0)
        if not offset:
            statuses = self.get_items(entrytype='status')
        else:
            statuses = db.Query(Blogentry).filter('entrytype =','status').order("-published").fetch(limit=blogconfig.NUM_STATUSES,
                offset=offset)
        if not statuses and offset > 0:
            return self.redirect("/statuses")
        extra_context = {
            "statuses": statuses,
            "next": max(offset - blogconfig.NUM_STATUSES, 0),
            "previous": offset + blogconfig.NUM_STATUSES if len(statuses) == blogconfig.NUM_STATUSES else None,
            "offset": offset,
            "on_statuses":True,
            "comment_title":"Statuses",
        }
        self.render("statuses.html", extra_context)

class NewBlogentryHandler(BaseRequestHandler):
    def get_tags_argument(self, name):
        tags = self.request.get(name, "").split(",")
        tags = set([tag for tag in tags if tag])
        return [db.Category(tag) for tag in tags]

    @admin
    def get(self, key=None):
        extra_context = {}
        form = BlogentryForm()
        if key:
            try:
                entry = db.get(key)
                #entry.slug = entry.slug.replace("-"," ")
                extra_context["entry"] = entry
                extra_context["tags"] = ",".join(entry.tags)
                form = BlogentryForm(obj=entry)
            except db.BadKeyError:
                return self.redirect("/new")
        else:
            extra_context["entry"] = None
        extra_context["form"] = form
        extra_context["on_new"] = True

        self.render("edit.html" if key else "new.html", extra_context)

    @admin
    def post(self, key=None):
        extra_context = {}
        tags = self.get_tags_argument("tags")
        koment = self.request.get("koment")
        source = self.request.get("source")
        entrytype = self.request.get("entrytype")
        body_format = self.request.get("body_format")
        body = self.request.get("body")
        #body_html = to_html(body,body_format)
        if key:
            try:
                entry = db.get(key)
                extra_context["entry"] = entry
            except db.BadKeyError:
                return self.raise_error(404)
            entry.title = self.request.get("title")
            slug = str(slugify(self.request.get("slug")))
            if slug != entry.slug:
                if self.get_entry_from_slug(slug=slug):
                    slug += "-" + uuid.uuid4().hex[:4]
            entry.slug = slug
            diff = self.request.get("diff")
            if diff:
                entry.body = body
                body_html = to_html(entry.body,body_format)
                sm= difflib.SequenceMatcher(None, entry.body_html, body_html)
                entry.body_html = (show_diff(sm)).replace("&amp;","&").replace("&gt;",">").replace("&lt;","<").replace('&nbsp;',' ')
            else:
                entry.body = body
                entry.body_html = to_html(entry.body,body_format).replace("&amp;","&").replace("&gt;",">").replace("&lt;","<").replace('&nbsp;',' ')
            if entrytype  != entry.entrytype:
                if entrytype == "post":
                    self.update_tags_and_archives(entry,values=tags,add=True)
                else:
                    self.update_tags_and_archives(entry,values=tags,remove=True)
            if entrytype == entry.entrytype == "post":
                self.update_tags_and_archives(entry,values=tags,edit=True)

            entry.entrytype = entrytype
            entry.updated = datetime.datetime.now() + datetime.timedelta(hours=blogconfig.UTC_OFFSET)

        else:
            slug = self.request.get("slug")
            if slug:
                slug = str(slugify(self.request.get("slug")))
            else:
                slug = str(slugify(self.request.get("title")))
            if not slug:
                slug = self.translate('zh-CN','en',self.request.get("title"))
                slug = str(slugify(slug))
            if self.get_entry_from_slug(slug=slug):
                slug += "-" + uuid.uuid4().hex[:4]
            entry = Blogentry(
                author=users.get_current_user(),
                body=self.request.get("body"),
                body_html = to_html(body,body_format),#body_html,
                title=self.request.get("title"),
                slug=slug,
            )
            entry.tags=tags
            entry.published += datetime.timedelta(hours=blogconfig.UTC_OFFSET)
            entry.updated = entry.published
            entry.entrytype = entrytype
            if entry.entrytype == "post":
                self.update_tags_and_archives(entry,add=True)
            if blogconfig.SYNC_MAIL:
                mail.send_mail(
                    sender = author.email(),
                    reply_to = blogconfig.EMAIL,
                    to = blogconfig.SYNC_MAIL,
                    subject = title,
                    body = body,
                )
        if koment:
            entry.koment=True
        else:
            entry.koment=False
        scheme, netloc, path, query, fragment = urlparse.urlsplit(source)
        if scheme and netloc:
            entry.source = source
        entry.body_format = body_format
        entry.put()
        self.kill_entries_cache(slug=entry.slug if key else None,
            tags=entry.tags, month=entry.published.strftime('%Y/%m'), year=entry.published.strftime('%Y'))
        return self.redirect(self.entry_link(entry))
        form = BlogentryForm(self.request.POST,obj=entry)
        if self.request.POST and form.validate():
            form.populate_obj(entry)
            entry.put()
        extra_context["form"] = form
        self.render("edit.html" if key else "new.html", extra_context)

class PostComment(BaseRequestHandler):
    def post(self):
        author = users.get_current_user()
        body = self.request.get('content')
        to_url = self.request.get('to_url')
        to_title = self.request.get('to_title')
        if not body:
            return self.redirect('%s' %to_url)

        c= Blogentry( to_url =to_url,
                    to_title = to_title,
                    author=author,
                    body=body,
                    entrytype = 'comment')
        c.published += datetime.timedelta(hours=blogconfig.UTC_OFFSET)
        c.updated = c.published
        c.put()
        memcache.delete("comment/archive")
        memcache.delete("comments_to_url/%s/short"%to_url)
        memcache.delete("comments_to_url/%s/all"%to_url)
        self.kill_entries_cache()
        self.redirect(self.request.headers['referer'])

class PostStatus(BaseRequestHandler):
    def post(self):
        author = users.get_current_user()
        body = self.request.get('content')
        if not body:
            return self.redirect('/')
        s= Blogentry(author=author,
                    body=body,
                    entrytype = 'status')
        s.published += datetime.timedelta(hours=blogconfig.UTC_OFFSET)
        s.updated = s.published
        s.put()
        memcache.delete("statuses/archive")
        self.kill_entries_cache()
        self.redirect(self.request.headers['referer'])

class BlogconfigHandler(BaseRequestHandler):
    @admin
    def get(self):
        extra_context = {}
        form = BlogconfigForm(obj=blogconfig)
        extra_context["form"] = form
        self.render("settings.html", extra_context)

    @admin
    def post(self):
        extra_context = {}
        form = BlogconfigForm(self.request.POST,obj=blogconfig)
        if form.validate():
            form.save()
        blogconfig.TITLE = self.request.get("TITLE")
        blogconfig.NAME = self.request.get("NAME")
        blogconfig.EMAIL = self.request.get("EMAIL")
        if self.request.get("SYNC_MAIL"):
            blogconfig.SYNC_MAIL = self.request.get("SYNC_MAIL")
        blogconfig.BASEURL = self.request.get("BASEURL")
        blogconfig.FEED_SMITH = self.request.get("FEED_SMITH")
        blogconfig.NUM_MAIN = int(self.request.get("NUM_MAIN"))
        blogconfig.NUM_RECENT = int(self.request.get("NUM_RECENT"))
        blogconfig.NUM_COMMENTS = int(self.request.get("NUM_COMMENTS"))
        blogconfig.NUM_STATUSES = int(self.request.get("NUM_STATUSES"))
        blogconfig.UTC_OFFSET = int(self.request.get("UTC_OFFSET"))
        blogconfig.RPC_USERNAME = self.request.get("RPC_USERNAME")
        blogconfig.PRC_PASSWORD = self.request.get("PRC_PASSWORD")
        blogconfig.WEBMASTER_VERIFICATION_CONTENT = self.request.get("WEBMASTER_VERIFICATION_CONTENT")
        blogconfig.ANALYTICS = self.request.get("ANALYTICS")
        if self.request.get("SHOW_ENTRYCOUNT"):
            blogconfig.SHOW_ENTRYCOUNT = True
        else:
            blogconfig.SHOW_ENTRYCOUNT = False
        if self.request.get("INDEXED_ALLOWED"):
            blogconfig.INDEXED_ALLOWED = True
        else:
            blogconfig.INDEXED_ALLOWED = False

        blogconfig.put()
        extra_context["form"] = form
        extra_context["saved"] = True
        self.render("settings.html", extra_context)


class MailReceiver(BaseRequestHandler,InboundMailHandler):
    def code2utf(self,subject):
        _subject_list=decode_header(subject)
        if (_subject_list[0][1]):
            _subject = _subject_list[0][0].decode(_subject_list[0][1]).encode("utf-8")
        else :
            _subject = _subject_list[0][0]
        return _subject

    def get_tags_argument(self, name):
        tags = name.split("#")
        tags = set([tag for tag in tags if tag])
        return [db.Category(tag) for tag in tags]

    def receive(self, mail_message):
        title = self.code2utf(mail_message.subject)
        title = title.decode('utf8')
        logging.info(title)
        bodies=mail_message.bodies(content_type='text/html')
        content=''
        for body in bodies:
            # body[0] = "text/plain"
            # body[1] = EncodedPayload --> body[1].decode()
            content = content + body[1].decode()
        #content=content.decode('utf8')
        regex_tag = '#(.*)'
        tags=''
        for match in re.finditer(regex_tag, title):
            tag = match.group(0)
            tags += '%s' %(tag)
            title = title.replace(tag,'')
        if mail_message.to == 'update@hht.appspotmail.com':
            slug = self.translate('zh-CN','en',title)
            slug = str(slugify(slug))
            if self.get_entry_from_slug(slug=slug):
                slug += "-" + uuid.uuid4().hex[:4]
            entry = Blogentry(
                    author=users.User(email = blogconfig.EMAIL),
                    body=content,
                    title=title,
                    slug=slug,
                    entrytype='post',
            )
            entry.tags = self.get_tags_argument(tags)
            entry.published += datetime.timedelta(hours=blogconfig.UTC_OFFSET)
            entry.updated = entry.published
            entry.put()
            self.update_tags_and_archives(entry,add=True)
            self.kill_entries_cache(tags=entry.tags, month=entry.published.strftime('%Y/%m'), year=entry.published.strftime('%Y'))

class ImportWordPressHandler(BaseRequestHandler):
    def get_tags_argument(self, tags):
        tags = set([tag for tag in tags if tag])
        return [db.Category(tag) for tag in tags]

    def parse(self):
        entries=[]

        source=self.request.get("wpfile")
        doc=et.fromstring(source)
        wpns='{http://wordpress.org/export/1.2/}'
        contentns="{http://purl.org/rss/1.0/modules/content/}"
        et._namespace_map[wpns]='wp'
        et._namespace_map[contentns]='content'
        channel=doc.find('channel')

        #parse entries
        items=channel.findall('item')

        for item in items:
            title=item.findtext('title')

            try:
                entry={}
                entry['title']=item.findtext('title')
                entry['pubDate']=item.findtext('pubDate')
                entry['post_type']=item.findtext(wpns+'post_type')
                entry['content']= item.findtext(contentns+'encoded')
                entry['tags']=[]

                cats=item.findall('category')
                for cat in cats:
                    if cat.attrib.has_key('nicename'):
                        cat_type=cat.attrib['domain']
                        if cat_type=='tag':
                            entry['tags'].append(cat.text)

                comment_status=item.findtext(wpns+'comment_status')
                if comment_status=="open":
                    entry['comment_status']=True
                else:
                    entry['comment_status']=False
                logging.info(entry['comment_status'])


                entries.append(entry)
            except:
                logging.info("parse wordpress file error")
        return entries

    @admin
    def get(self):
        extra_context={ "on_import":True,
                       }
        self.render("wpimport.html", extra_context)

    @admin
    def post(self):
        entries = self.parse()
        for entry in entries:
            title = entry['title']
            try:
                slug = self.translate('zh-CN','en',title)
            except:
                slug = str(entry['pubDate'][:-9])
            slug = str(slugify(slug))
            if self.get_entry_from_slug(slug=slug):
                slug += "-" + uuid.uuid4().hex[:4]
            body = entry['content']
            blogentry = Blogentry(
                author=users.get_current_user(),
                body=body,
                body_html = body,
                title=title,
                slug=slug,
                body_format = 'html',
            )
            blogentry.tags=self.get_tags_argument(entry['tags'])
            try:
                blogentry.published=datetime.datetime.strptime( entry['pubDate'][:-6],"%a, %d %b %Y %H:%M:%S")
            except:
                try:
                    blogentry.published=datetime.datetime.strptime( entry['pubDate'][0:19],"%Y-%m-%d %H:%M:%S")
                except:
                    blogentry.published+= datetime.timedelta(hours=blogconfig.UTC_OFFSET)
            blogentry.updated = blogentry.published
            blogentry.entrytype = entry['post_type']
            if blogentry.entrytype == "post":
                #update_time = datetime.datetime.strptime( entry['pubDate'][:-6],"%a, %d %b %Y %H:%M:%S")
                self.update_tags_and_archives(blogentry,add=True,update_time=blogentry.updated)
            blogentry.koment=entry['comment_status']

            blogentry.put()
            self.kill_entries_cache(tags=blogentry.tags, month=blogentry.published.strftime('%Y/%m'), year=blogentry.published.strftime('%Y'))
        self.redirect("/import_wp")

class ExportWordPressHandler(BaseRequestHandler):
    @admin
    def get(self,tags=None):
        entrytypes = ['post','page']
        entries = db.GqlQuery("SELECT * FROM Blogentry WHERE entrytype IN :1 ORDER BY published DESC",entrytypes)
        tags=Tag.all()
        extra_context={ 'entries':entries,
                        'tags':tags,
                        }
        self.response.headers['Content-Type'] = 'binary/octet-stream'#'application/atom+xml'
        self.render('wordpress.xml',extra_context)

class NotFoundHandler(BaseRequestHandler):
    def head(self):
        self.error(404)

    def get(self):
        self.raise_error(404)

class EntryIdRedirectHandler(BaseRequestHandler):
    def get(self,id):
        entry = self.get_entry_from_id(id=id)
        self.redirect(str(self.entry_link(entry,absolute=True)),permanent=True)

class TagPageHandler(BaseRequestHandler):
    def get(self, tag):
        extra_context = {
            "entries": self.get_tagged_entries(tag),
            "tag": urllib.unquote(tag),
            "comment_title":"tag:%s" %(urllib.unquote(tag))
        }
        self.render("tag.html", extra_context)

class MonthPageHandler(BaseRequestHandler):
    def get(self, year, month):
        extra_context = {
            "entries": self.get_monthly_entries(month,year),
            "month": month,
            "year": year,
            "comment_title":"%s-%s" %(year,month),
        }
        self.render("month.html", extra_context)

class YearPageHandler(BaseRequestHandler):
    def get(self, year):
        extra_context = {
            "entries": self.get_yearly_entries(year),
            "year": year,
            "comment_title":year,
        }
        self.render("year.html", extra_context)


class AtomSitemapHandler(BaseRequestHandler):
    def get(self):
        extra_context = {
                        'entries' : self.get_archive_entries(meta='sitemap'),
        }
        self.response.headers['Content-type'] = 'text/xml; charset=UTF-8'
        self.render("sitemap.xml",extra_context)

class OpenSearchHandler(BaseRequestHandler):
    def get(self):
        self.response.headers["Content-Type"] = "application/xml"
        self.render("opensearch.xml")

class SearchHandler(BaseRequestHandler):
    def get(self):
        extra_context = {'on_search':True,
                        "comment_title":"Search",}
        self.render("search.html",extra_context)
class AboutHandler(BaseRequestHandler):
    def get(self):
        user = users.get_current_user()
        extra_context= {'email': user.email() if user else '',
                        'nickname': user.nickname() if user else '',
                        'curtime': time.time(),
                        'on_about': True,
                        "success":False,
                        "comment_title":"About",}

        self.render("about.html",extra_context)
    def post(self):

        if time.time() - string.atof(self.request.get('curtime')) < 2.0:
            logging.info("Aborted contact mailing because form submission "
                          "was less than 2 seconds.")
            return self.error(403)

        user = users.get_current_user()
        sender = user.email() if user else 'hityhoo@gmail.com'
        reply_to = self.request.get('email') or \
                   (user.email() if user else 'unknown@foo.com')
        if not self.request.get('website'):
            mail.send_mail(
                sender = sender,
                reply_to = self.request.get('author') + '<' + reply_to + '>',
                to = blogconfig.EMAIL,
                subject = self.request.get('subject') or 'No Subject Given',
                body = self.request.get('message') or 'No Message Given'
            )
        extra_context={"success":True}
        self.render("about.html",extra_context)

class LoginHandler(BaseRequestHandler):
    def get(self):
        try:
            self.referer = self.request.headers['referer']
        except:
            self.referer = "/"
        return self.redirect(users.create_login_url(self.referer))

class LogoutHandler(BaseRequestHandler):
    def get(self):
        try:
            self.referer = self.request.headers['referer']
        except:
            self.referer = "/"
        return self.redirect(users.create_logout_url(self.referer))

class MediaHandler(BaseRequestHandler):
    def get(self,slug):
        media=Media.get(slug)
        if media:
            self.response.headers['Expires'] = 'Thu, 15 Apr 2010 20:00:00 GMT'
            self.response.headers['Cache-Control'] = 'max-age=3600,public'
            self.response.headers['Content-Type'] = str(media.mtype)
            self.response.out.write(media.bits)

class UpdateHandler(BaseRequestHandler):
    @admin
    def get(self):
        entries=Blogentry.all()
        for entry in entries:
            entry.koment=True
            entry.put()
        self.redirect('/')
class RobotsHandler(BaseRequestHandler):
    def get(self):
        extra_context={}
        self.response.headers['Content-type'] = 'text/plain; charset=UTF-8'
        self.render("robots.txt", extra_context)

application = webapp2.WSGIApplication([
    ("/", MainPageHandler),
    ('/media/(.*)',MediaHandler),
    ("/index/?", ArchivePageHandler),
    ("/archives/?", ArchivesPageHandler),
    ("/([\w-]+)/feed/?", FeedRedirectHandler),
    ("/comments/?", CommentsPageHandler),
    ("/saying/?", StatusesPageHandler),
    ("/delete/?", DeleteBlogentryHandler),
    ("/deleteitem/?", DeleteItemHandler),
    ("/edit/([\w-]+)/?", NewBlogentryHandler),
    ("/post/([\w-]+)/?", EntryIdRedirectHandler),
    ("/comment/([\w-]+)/?", SingelCommentPageHandler),
    ("/saying/([\w-]+)/?", SingelStatusPageHandler),
    ("/page/(?P<slug>.*)/?", SingelPagePageHandler),
    ("/new/?", NewBlogentryHandler),
    ("/postcomment/?", PostComment),
    ("/poststatus/?", PostStatus),
    ("/tag/(.*)/?", TagPageHandler),
    ("/(?P<year>\d+)/(?P<month>\d\d+)/(?P<slug>.*)/?", BlogentryPageHandler),
    ("/(\d{4})/(\d{2})/?", MonthPageHandler),  #for month archive
    ("/(\d{4})/?", YearPageHandler),  #for year archive
    ("/feed/?", FeedRedirectHandler),
    ("/opensearch.xml/?", OpenSearchHandler),
    ("/search/?", SearchHandler),
    ("/settings/?", BlogconfigHandler),
    ("/about/?", AboutHandler),
    ("/login/?", LoginHandler),
    ("/logout/?", LogoutHandler),
    ("/update/?", UpdateHandler),
    ("/import_wp/?",ImportWordPressHandler),
    ('/export/jot.xml',ExportWordPressHandler),
    ("/sitemap.xml", AtomSitemapHandler),
    ("/robots.txt", RobotsHandler),
    ('/_ah/mail/.+', MailReceiver),
    ("/.*", NotFoundHandler),
], debug=True)
