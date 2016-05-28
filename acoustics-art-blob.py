#!/usr/bin/env python3
# coding: utf-8
"""
acoustics-art-blob.py - Acoustics Album Art Utility

Displays album art and "now playing" information in a configurable window.
"""
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
import cairo

import argparse
import base64
import html
import json
import os
import sys
import http.cookiejar
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse

class Acoustics(object):
    """Class to handle communication with the Acoustics server API."""

    def __init__(self, prefix):
        # We need a cookie jar or the API will not function, as
        # it uses cookies for session tokens.
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        urllib.request.install_opener(opener)
        self.prefix = prefix
        self.is_logged_in = False
        self.query()

    def authenticate(self, user, password):
        counter = 0
        try:
            auth = base64.b64encode("{user}:{password}".format(user=user,password=password).encode('utf-8'))
            r = urllib.request.Request(self.prefix + 'www-data/auth',
                    headers={'Authorization': 'Basic %s' % auth.decode('utf-8')})
            result = urllib.request.urlopen(r)
            self.is_logged_in = True
            return result.read()
        except:
            counter += 1
            if counter == 3:
                return None

    def _curl(self, url):
        try:
            r = urllib.request.Request(url)
            r = urllib.request.urlopen(r)
            return r.read()
        except:
            return b'{}'

    def query(self):
        """Query the server for now-playing information."""
        json_output = self._curl(self.prefix + 'json.py')
        return json.loads(json_output.decode('utf-8'))

    def call(self, mode):
        return self._curl(self.prefix + 'json.py?mode=' + mode)

    def album_art(self, song_id, size):
        """Request album art for a particular song_id."""
        url = self.prefix + 'json.py?mode=art;song_id={song};size={size}'.format(
            song=song_id,
            size=size
        )
        r = urllib.request.urlopen(url)
        return r.read()


class MainWin(object):

    def destroy(self, widget, data=None):
        GLib.MainLoop().quit()
        sys.exit()

    def set_art_alignment(self, alignment):
        alignments = {
            "bottom": (Gtk.Align.START, Gtk.Align.END),
            "top": (Gtk.Align.START, Gtk.Align.START),
            "center": (Gtk.Align.CENTER, Gtk.Align.CENTER),
            "center-bottom": (Gtk.Align.CENTER, Gtk.Align.END),
            "center-top": (Gtk.Align.CENTER, Gtk.Align.START),
            "top-right": (Gtk.Align.END, Gtk.Align.START),
            "bottom-right": (Gtk.Align.END, Gtk.Align.END),
        }
        if alignment not in alignments:
            raise ValueError("Invalid alignment for album art: " + alignment)
        x, y = alignments[alignment]
        self.image.set_halign(x)
        self.image.set_valign(y)

    def set_label_alignment(self, alignment):
        alignments = {
            "bottom": (Gtk.Align.START,Gtk.Align.END,Gtk.Justification.LEFT),
            "top": (Gtk.Align.START,Gtk.Align.START,Gtk.Justification.LEFT),
            "center": (Gtk.Align.CENTER,Gtk.Align.CENTER,Gtk.Justification.CENTER),
            "center-top": (Gtk.Align.CENTER,Gtk.Align.START,Gtk.Justification.CENTER),
            "center-bottom": (Gtk.Align.CENTER,Gtk.Align.END,Gtk.Justification.CENTER),
            "top-right": (Gtk.Align.END,Gtk.Align.START,Gtk.Justification.RIGHT),
            "bottom-right": (Gtk.Align.END,Gtk.Align.END,Gtk.Justification.RIGHT),
        }
        if alignment not in alignments:
            raise ValueError("Invalid alignment for song info: " + alignment)
        x, y, j = alignments[alignment]
        self.label.set_halign(x)
        self.label.set_valign(y)
        self.label.set_justify(j)

    def expose(self, widget, cr):
        """GTK expose event handler - clear the window to rgba(0,0,0,0) with Cairo."""
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.rectangle(0.0,0.0, *widget.get_size())
        cr.fill()
        cr.set_operator(cairo.OPERATOR_OVER)

    def update(self):
        """Update the album image and now-playing information."""
        global acoustics

        # Query from API
        data = acoustics.query()

        if not data:
            # Either the API is not available, or there was an error.
            return
        if not 'now_playing' in data or not data['now_playing']:
            # There is nothing playing, or the data from the server
            # was invalid. Display "Nothing playing." and clear the
            # album art image.
            self.last_song_id = None
            self.image.clear()
            self.label.set_text("Nothing playing.")
            # We display error messages aligned to the upper left, rather
            # than the bottom left as we do with song information.
            self.set_label_alignment(self.args.info_align)
            return

        # Generate the album art
        if data['now_playing']['song_id'] == self.last_song_id:
            return

        self.last_song_id = data['now_playing']['song_id']

        # Retrieve the album art from the server
        album_art = acoustics.album_art(self.last_song_id, self.args.size)

        # Load the album art into a Gdk Pixbuf
        loader = GdkPixbuf.PixbufLoader()
        loader.write(album_art)
        loader.close()

        # Update the album art image
        self.image.set_from_pixbuf(loader.get_pixbuf())

        # If we have decorations are show up in the taskbar,
        # set the icon and title fort he window.
        if self.args.decorated or self.args.normal_window:
            self.window.set_icon(loader.get_pixbuf())
            self.window.set_title("{song} - {artist}".format(
                song=data['now_playing']['title'],
                artist=data['now_playing']['artist'],
            ))

        # Set the now-playing overlay
        self.label.set_markup('<span size="large">{title}</span>\n{artist}\n{album}'.format(
            title=html.escape(data['now_playing']['title']),
            artist=html.escape(data['now_playing']['artist']),
            album=html.escape(data['now_playing']['album']),
        ))

        # Ensure that the now-playing overlay is aligned to the bottom
        # as we move it around for error messages.
        self.set_label_alignment(self.args.song_align)

    def __init__(self, args):
        self.last_song_id = None
        self.args = args

        self.window = Gtk.Window()

        # Obtain an RGBA visual so we can make a transparent window.
        self.screen = self.window.get_screen()
        colormap = self.screen.get_rgba_visual()

        # Set the window to "app-paintable" so we can use Cairo
        # to clear the background.
        self.window.set_app_paintable(True)
        self.window.set_size_request(self.args.size,self.args.size)
        self.window.set_visual(colormap)
        self.window.set_default_size(self.args.size,self.args.size)

        # Set window hints for window management.
        # Sticky, skip taskbar, skip pager, undecorated.
        if not self.args.decorated:
            self.window.set_decorated(False)

        if not self.args.normal_window:
            self.window.set_keep_above(True)
            self.window.set_skip_taskbar_hint(True)
            self.window.set_skip_pager_hint(True)

        # Hook up event callbacks for the window.
        self.window.connect('draw', self.expose)
        self.window.connect('destroy', self.destroy)
        self.window.connect('notify::has-toplevel-focus', self.focus_window)

        # We use an overlay to display our image and 
        self.container = Gtk.Overlay()

        self.image = Gtk.Image()
        self.set_art_alignment(self.args.art_align)

        self.label = Gtk.Label()
        self.label.set_text("Loading...")
        self.set_label_alignment(self.args.info_align)

        self.buttons = Gtk.Box()

        self._image_stop = Gtk.Image()
        self._image_stop.set_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)),"image/stop.svg"))
        self._image_play = Gtk.Image()
        self._image_play.set_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)),"image/play.svg"))
        self._image_skip = Gtk.Image()
        self._image_skip.set_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)),"image/next.svg"))

        self.button_stop = Gtk.Button()
        self.button_play = Gtk.Button()
        self.button_skip = Gtk.Button()

        self.button_stop.set_image(self._image_stop)
        self.button_play.set_image(self._image_play)
        self.button_skip.set_image(self._image_skip)

        self.buttons.add(self.button_stop)
        self.buttons.add(self.button_play)
        self.buttons.add(self.button_skip)
        self.buttons.set_valign(Gtk.Align.CENTER)
        self.buttons.set_halign(Gtk.Align.CENTER)

        self.button_stop.connect('clicked', self.callback_stop)
        self.button_play.connect('clicked', self.callback_play)
        self.button_skip.connect('clicked', self.callback_skip)

        self.container.add_overlay(self.image)
        self.container.add_overlay(self.label)
        self.container.add_overlay(self.buttons)

        self.button_stop.show()
        self.button_play.show()
        self.button_skip.show()

        self.update()

        self.window.add(self.container)
        self.image.show()
        self.label.show()
        self.container.show()
        self.window.show()

        if not self.args.no_sticky:
            self.window.stick()

        # We use a GTK CSS Provider to give our text a drop shadow effect.
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

        # A 1-second timeout triggers display updates.
        GObject.timeout_add_seconds(1, self.callback)

    def callback_stop(self, _):
        acoustics.call('stop')

    def callback_play(self, _):
        acoustics.call('start')

    def callback_skip(self, _):
        acoustics.call('skip')

    def focus_window(self, widget, data):
        if self.window.get_property("has-toplevel-focus"):
            if acoustics.is_logged_in:
                self.buttons.show()
        else:
            self.buttons.hide()

    def callback(self):
        self.update()
        return True

    def main(self):
        GLib.MainLoop().run()

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Display album art and song information from Acoustics.")

    # Display options
    parser.add_argument('--song-align', default='bottom', help='How to align the song information in the window.')
    parser.add_argument('--info-align', default='top', help='How to align error messages in the window.')
    parser.add_argument('--art-align', default='bottom', help='How to align the album art in the window.')
    parser.add_argument('--size', default=180, type=int, help='Size of the album art and default size of the window.')

    # API configuration
    parser.add_argument('--url', default='http://localhost:6969/', help='Acoustics API endpoint.')
    parser.add_argument('--user', default=None, help='Authentication user name')
    parser.add_argument('--password', default="", help='Authentication password')

    # Window management options
    parser.add_argument('--decorated', action='store_true', help='Show window decorations.')
    parser.add_argument('--no-sticky', action='store_true', help='Don\'t show on all workspaces.')
    parser.add_argument('--normal-window', action='store_true', help='Don\'t skip pager/taskbar.')

    args = parser.parse_args()

    acoustics = Acoustics(args.url)

    if args.user:
        results = acoustics.authenticate(args.user, args.password)

    MainWin(args).main()


