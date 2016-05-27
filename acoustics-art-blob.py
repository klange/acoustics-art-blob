from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
import cairo

import html
import json
import sys
import http.cookiejar
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse

size=180

class Acoustics(object):

    prefix = 'http://localhost:6969/json.py'

    def __init__(self):
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        urllib.request.install_opener(opener)

    def curl(self, url):
        try:
            r = urllib.request.Request(url)
            r = urllib.request.urlopen(r)
            return r.read()
        except:
            return b'{}'

    def query(self):
        json_output = self.curl(self.prefix)
        return json.loads(json_output.decode('utf-8'))

    def albumart(self, song_id, size):
        return self.prefix + '?mode=art;song_id={song};size={size}'.format(
            song=song_id,
            size=size
        )


class MainWin(object):

    def destroy(self, widget, data=None):
        Gtk.main_quit()

    def expose(self, widget, cr):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.rectangle(0.0,0.0, *widget.get_size())
        cr.fill()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self.counter < 3:
            cr.set_source_rgba(0.5,1.0,0.0,1)
            cr.arc(widget.get_size()[0]/2,widget.get_size()[1]/2,
                   widget.get_size()[0]/2,0,3.141592654*2)
            cr.fill()

    def load_image(self):
        global acoustics
        data = acoustics.query()
        if not data:
            return
        if not 'now_playing' in data or not data['now_playing']:
            self.image.clear()
            self.label.set_text("Nothing playing.")
            self.label.set_xalign(0)
            self.label.set_yalign(0)
            return
        url = acoustics.albumart(data['now_playing']['song_id'],size)
        if url == self.last_image:
            return

        self.last_image = url
        r = urllib.request.urlopen(url)
        loader = GdkPixbuf.PixbufLoader()
        loader.write(r.read())
        loader.close()
        self.image.set_from_pixbuf(loader.get_pixbuf())
        self.label.set_markup('<span size="large">{title}</span>\n{artist}\n{album}'.format(
            title=html.escape(data['now_playing']['title']),
            artist=html.escape(data['now_playing']['artist']),
            album=html.escape(data['now_playing']['album']),
        ))
        self.label.set_xalign(0)
        self.label.set_yalign(1)

    def __init__(self):
        self.last_image = None

        self.window = Gtk.Window()
        self.screen = self.window.get_screen()
        colormap = self.screen.get_rgba_visual()
        self.window.set_app_paintable(True)
        self.window.set_size_request(size,size)
        self.window.set_visual(colormap)
        self.window.set_decorated(False)
        self.window.set_wmclass("conky","conky")
        self.window.set_keep_above(True)
        self.window.set_default_size(size,size)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.connect('draw', self.expose)
        self.window.connect('destroy', self.destroy)

        self.container = Gtk.Overlay()

        self.image = Gtk.Image()

        self.label = Gtk.Label()
        self.label.set_text("Loading...")
        self.label.set_xalign(0)
        self.label.set_yalign(0)

        self.container.add_overlay(self.image)
        self.container.add_overlay(self.label)

        self.load_image()

        self.window.add(self.container)
        self.image.show()
        self.label.show()
        self.container.show()
        self.window.show()
        self.window.stick()

        style = b'''
            .label {
                text-shadow: 1px 1px 2px rgba(0, 0, 0, 1), 0px 0px 2px rgba(0,0,0,1), 0px 0px 2px rgba(0,0,0,1);
                font-weight: bold;
                padding: 2px;
                color: #fff;
            }
        '''
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(style)
        Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                style_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.counter = 0
        GObject.timeout_add_seconds(1, self.callback)

    def callback(self):
        self.counter += 1
        self.load_image()
        return True

    def main(self):
        GLib.MainLoop().run()

if __name__ == "__main__":
    acoustics = Acoustics()
    MainWin().main()


