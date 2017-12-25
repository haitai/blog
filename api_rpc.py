# -*- coding: utf-8 -*-
import wsgiref.handlers
import xmlrpclib
import sys
import cgi
import base64
import datetime
from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from functools import wraps
from main import *
rpc_username = blogconfig.RPC_USERNAME
prc_password = blogconfig.PRC_PASSWORD

def checkauth(pos=1):
    def _decorate(method):
        def _wrapper(*args, **kwargs):
            username = args[pos+0]
            password = args[pos+1]
            args = args[0:pos]+args[pos+2:]
            if not (username and password and rpc_username and prc_password and (rpc_username==username) and (prc_password==password)):
                raise ValueError("Authentication Failure")
            return method(*args, **kwargs)
        return _wrapper
    return _decorate

def format_date(d):
    if not d: return None
    return xmlrpclib.DateTime(d.isoformat())

def entry_struct(entry):
    struct = {
        'postid': entry.key().id(),
        'title': unicode(entry.title),
        'description': unicode(entry.body_html),
        'link': entry.entrytype + str(entry.key().id()),
        'userid': 1,
        'mt_keywords':','.join(entry.tags),
        'wp_slug':entry.slug.replace('-',' '),
        'mt_allow_comments': 1 if entry.koment else 0,
        }
    struct['dateCreated'] = format_date(entry.published)
    return struct

class Logger(db.Model):
    request = db.TextProperty()
    response = db.TextProperty()
    date = db.DateTimeProperty(auto_now_add=True)


#-------------------------------------------------------------------------------
# blogger
#-------------------------------------------------------------------------------

@checkauth()
def blogger_getUsersBlogs(discard):
    return [{'url' : blogconfig.BASEURL, 'blogid' : '001', 'blogName' : blogconfig.TITLE}]

#-------------------------------------------------------------------------------
# WordPress
#-------------------------------------------------------------------------------
@checkauth()
def wp_getAuthors(blogid):
    return [{'user_id':1,'user_login':'','display_name':rpc_username}]

#-------------------------------------------------------------------------------
# metaWeblog
#-------------------------------------------------------------------------------

@checkauth()
def metaWeblog_newPost(blogid, struct, publish):
    entry=Blogentry(title = struct['title'],
                    body = struct['description'],
                    body_html = struct['description'],
                    )

    if struct.has_key('mt_keywords'):
        if struct['mt_keywords'] != '':
            tags = set([tag for tag in (struct['mt_keywords']).split(',')])
            entry.tags = [db.Category(tag) for tag in tags]

    if struct.has_key('wp_slug'):
        entry.slug=str(slugify(struct['wp_slug']))
        if entry.slug=='':
            entry.slug=str(slugify(BaseRequestHandler().translate('zh-CN','en',struct['title'])))
    if struct.has_key('dateCreated'):
        entry.updated = entry.published = datetime.datetime.strptime(str(struct['dateCreated']),'%Y%m%dT%H:%M:%SZ') + datetime.timedelta(hours=blogconfig.UTC_OFFSET)
    else:
        entry.published += datetime.timedelta(hours=blogconfig.UTC_OFFSET)
        entry.updated = entry.published
    if struct.has_key('mt_allow_comments'):
        if struct['mt_allow_comments'] == 1:
            entry.koment = True
        else:
            entry.koment = False
    entry.put()
    BaseRequestHandler().update_tags_and_archives(entry,add=True)
    BaseRequestHandler().kill_entries_cache(tags=entry.tags, month=entry.published.strftime('%Y/%m'), year=entry.published.strftime('%Y'))
    postid = entry.key().id()
    return str(postid)

@checkauth()
def wp_newPage(blogid,struct,publish):
    entry=Blogentry(title = struct['title'],
                    body = struct['description'],
                    body_html = struct['description'],
                    )
    if struct.has_key('mt_text_more'):
        entry.body_html=entry.body_html+"<!--more-->"+struct['mt_text_more']
    if struct.has_key('wp_slug'):
        entry.slug=str(slugify(struct['wp_slug']))
        if entry.slug=='':
            entry.slug=str(slugify(BaseRequestHandler().translate('zh-CN','en',struct['title'])))
    entry.entrytype='page'
    if struct.has_key('dateCreated'):
        entry.updated = entry.published = datetime.datetime.strptime(str(struct['dateCreated']),'%Y%m%dT%H:%M:%SZ') + datetime.timedelta(hours=blogconfig.UTC_OFFSET)
    else:
        entry.published += datetime.timedelta(hours=blogconfig.UTC_OFFSET)
        entry.updated = entry.published
    if struct.has_key('mt_allow_comments'):
        if struct['mt_allow_comments'] == 1:
            entry.koment = True
        else:
            entry.koment = False
    entry.put()
    BaseRequestHandler().kill_entries_cache()
    postid =entry.key().id()
    return str(postid)


@checkauth()
def metaWeblog_newMediaObject(postid,struct):
    name=struct['name']
    mtype=struct['type']
    bits=db.Blob(str(struct['bits']))
    media=Media(name=name,mtype=mtype,bits=bits)
    media.put()
    return {'url':'/media/'+str(media.key())}

@checkauth()
def metaWeblog_editPost(postid, struct, publish):
    entry=Blogentry.get_by_id(int(postid))
    if struct.has_key('mt_keywords'):
        if struct['mt_keywords'] != '':
            tags = set([tag for tag in (struct['mt_keywords']).split(',')])
            tags = [db.Category(tag) for tag in tags]
        else:
            tags = []
    BaseRequestHandler().update_tags_and_archives(entry,values=tags,edit=True)
    if struct.has_key('wp_slug'):
        entry.slug=str(slugify(struct['wp_slug']))

    entry.title = struct['title']
    entry.body = struct['description']
    entry.body_html = entry.body
    if struct.has_key('mt_allow_comments'):
        if struct['mt_allow_comments'] == 1:
            entry.koment = True
        else:
            entry.koment = False
    if struct.has_key('dateCreated'):
        entry.updated = datetime.datetime.strptime(str(struct['dateCreated']),'%Y%m%dT%H:%M:%SZ') + datetime.timedelta(hours=blogconfig.UTC_OFFSET)
    entry.put()
    BaseRequestHandler().kill_entries_cache(slug=entry.slug,
            tags=entry.tags, month=entry.published.strftime('%Y/%m'), year=entry.published.strftime('%Y'))
    return True

@checkauth(2)
def wp_editPage(blogid,pageid,struct,publish):
    entry=Blogentry.get_by_id(int(pageid))
    if struct.has_key('wp_slug'):
        entry.slug=struct['wp_slug']
    entry.title = struct['title']
    entry.body = struct['description']
    entry.body_html = entry.body
    if struct.has_key('mt_text_more'):
        entry.body_html=entry.body_html+"<!--more-->"+struct['mt_text_more']
    if struct.has_key('dateCreated'):
        entry.updated = datetime.datetime.strptime(str(struct['dateCreated']),'%Y%m%dT%H:%M:%SZ') + datetime.timedelta(hours=blogconfig.UTC_OFFSET)
    if struct.has_key('mt_allow_comments'):
        if struct['mt_allow_comments'] == 1:
            entry.koment = True
        else:
            entry.koment = False
    entry.put()
    BaseRequestHandler().kill_entries_cache(slug=entry.slug)
    return True

@checkauth()
def metaWeblog_getPost(postid):
    entry = Blogentry.get_by_id(int(postid))
    return entry_struct(entry)

@checkauth(2)
def wp_getPage(blogid,pageid):
    entry = Blogentry.get_by_id(int(pageid))
    return entry_struct(entry)

@checkauth()
def metaWeblog_getRecentPosts(blogid, num_posts):
    entries = Blogentry.gql('WHERE entrytype = :1 ORDER BY published DESC',"post")
    entries = entries.fetch(min(num_posts, 50))
    return [entry_struct(entry) for entry in entries]

@checkauth()
def wp_getPages(blogid,num):
    entries = Blogentry.all().filter('entrytype =','page').order('-published').fetch(min(num, 20))
    return [entry_struct(entry) for entry in entries]

@checkauth(pos=2)
def blogger_deletePost(appkey, postid, publish):
    entry=Blogentry.get_by_id(int(postid))
    entry.delete()
    BaseRequestHandler().update_tags_and_archives(entry,remove=True)
    BaseRequestHandler().kill_entries_cache(slug=entry.slug, tags=entry.tags, month=entry.published.strftime('%Y/%m'), year=entry.published.strftime('%Y'))
    return True

@checkauth()
def wp_deletePage(blogid,pageid):
    page=Blogentry.get_by_id(int(pageid))
    page.delete()
    BaseRequestHandler().kill_entries_cache(slug=page.slug)
    return True

@checkauth()
def wp_getPageList(blogid):
    return []

def mt_setPostCategories(*arg):
    return True
def mt_getPostCategories(*arg):
    return True

class PlogXMLRPCDispatcher(SimpleXMLRPCDispatcher):
    def __init__(self, funcs):
        SimpleXMLRPCDispatcher.__init__(self, True, 'utf-8')
        self.funcs = funcs

dispatcher = PlogXMLRPCDispatcher({
    'blogger.getUsersBlogs' : blogger_getUsersBlogs,
    'blogger.deletePost' : blogger_deletePost,
    'wp.getAuthors':wp_getAuthors,
    'metaWeblog.newPost' : metaWeblog_newPost,
    'metaWeblog.newMediaObject':metaWeblog_newMediaObject,
    'metaWeblog.editPost' : metaWeblog_editPost,
    'metaWeblog.getPost' : metaWeblog_getPost,
    'metaWeblog.getRecentPosts' : metaWeblog_getRecentPosts,
    'mt.getPostCategories' : mt_getPostCategories,
    'mt.setPostCategories': mt_setPostCategories,
    'wp.newPage':wp_newPage,
    'wp.getPage':wp_getPage,
    'wp.getPages':wp_getPages,
    'wp.editPage':wp_editPage,
    'wp.getPageList':wp_getPageList,
    'wp.deletePage':wp_deletePage,
    })


class CallApi(BaseRequestHandler):
    def get(self):
        Logger(request = self.request.uri, response = '----------------------------------').put()
        self.response.headers['Content-Type'] = 'application/xml; charset=utf-8'
        extra_context = {}
        self.render("rsd.xml", extra_context)
        #self.response.out.write('<h1>please use POST</h1>')

    def post(self):
        #self.response.headers['Content-Type'] = 'application/xml; charset=utf-8'
        request = self.request.body
        response = dispatcher._marshaled_dispatch(request)
        Logger(request = unicode(request, 'utf-8'), response = unicode(response, 'utf-8')).put()
        self.response.out.write(response)

class View(BaseRequestHandler):
    @admin
    def get(self):
        self.response.out.write('<html><body><h1>Logger</h1>')
        for log in Logger.all().order('-date').fetch(5,0):
            self.response.out.write("<p>date: %s</p>" % log.date)
            self.response.out.write("<h1>Request</h1>")
            self.response.out.write('<pre>%s</pre>' % cgi.escape(log.request))
            self.response.out.write("<h1>Reponse</h1>")
            self.response.out.write('<pre>%s</pre>' % cgi.escape(log.response))
            self.response.out.write("<hr />")
        self.response.out.write('</body></html>')

class DeleteLog(BaseRequestHandler):
    @admin
    def get(self):
        for log in Logger.all():
            log.delete()
        return self.redirect('/rpc/view')

def main():
    #webapp.template.register_template_library("filter")
    application = webapp.WSGIApplication(
            [
                ('/rpc', CallApi),
                ('/rsd.xml', CallApi),
                ('/rpc/view', View),
                ('/rpc/dellog', DeleteLog),
                ],
            debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
    main()