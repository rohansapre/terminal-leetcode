import sys
from threading import Thread
from collections import namedtuple
import urwid
import logging
import time
from .leetcode import Leetcode
from views.home import HomeView
from views.detail import DetailView
from views.help import HelpView
from views.loading import *
from views.viewhelper import *
from .config import config
import auth

palette = [
    ('body', 'dark cyan', ''),
    ('focus', 'white', ''),
    ('head', 'white', 'dark gray'),
    ('lock', 'dark gray', ''),
    ('tag', 'white', 'light cyan', 'standout'),
    ('hometag', 'dark red', '')
    ]

DetailData = namedtuple('DetailData', ['title', 'body', 'code', 'id', 'url'])


class Terminal(object):
    def __init__(self):
        self.home_view = None
        self.loop = None
        self.leetcode = Leetcode()
        self.help_view = None
        self.quit_confirm_view = None
        self.submit_confirm_view = None
        self.view_stack = []
        self.detail_view = None
        self.search_view = None
        self.loading_view = None
        self.logger = logging.getLogger(__name__)

    @property
    def current_view(self):
        return None if not len(self.view_stack) else self.view_stack[-1]

    @property
    def is_home(self):
        return len(self.view_stack) == 1

    def goto_view(self, view):
        self.loop.widget = view
        self.view_stack.append(view)

    def go_back(self):
        self.view_stack.pop()
        self.loop.widget = self.current_view

    def keystroke(self, key):
        if self.quit_confirm_view and self.current_view == self.quit_confirm_view:
            if key is 'y':
                raise urwid.ExitMainLoop()
            else:
                self.go_back()

        elif self.submit_confirm_view and self.current_view == self.submit_confirm_view:
            self.go_back()
            if key is 'y':
                self.send_code(self.detail_view.data)

        elif self.current_view == self.search_view:
            if key is 'enter':
                text = self.search_view.contents[1][0].original_widget.get_edit_text()
                self.home_view.handle_search(text)
                self.go_back()
            elif key is 'esc':
                self.go_back()

        elif key in ('q', 'Q'):
            self.goto_view(self.make_quit_confirmation())

        elif key is 's':
            self.goto_view(self.make_submit_confirmation())

        elif not self.is_home and (key is 'left' or key is 'h'):
            self.go_back()

        elif key is 'H':
            if not self.help_view:
                self.make_helpview()
            self.goto_view(self.help_view)

        else:
            return key

    def enter_search(self):
        self.make_search_view()
        self.goto_view(self.search_view)

    def enter_detail(self, data):
        self.show_loading('Loading Quiz', 17, self.current_view)
        self.t = Thread(target=self.run_retrieve_detail, args=(data,))
        self.t.start()

    def reload_list(self):
        '''Press R in home view to retrieve quiz list'''
        items = self.leetcode.hard_retrieve_home()
        if items:
            self.home_view = self.make_listview(items)
            self.view_stack = []
            self.goto_view(self.home_view)

    def make_quit_confirmation(self):
        text = urwid.AttrMap(urwid.Text('Do you really want to quit ? (y/n)'), 'body')
        self.quit_confirm_view = urwid.Overlay(text, self.current_view, 'left',
                                               ('relative', 100), 'bottom', None)
        return self.quit_confirm_view

    def make_submit_confirmation(self):
        text = urwid.AttrMap(urwid.Text('Do you want to submit your code ? (y/n)'), 'body')
        self.submit_confirm_view = urwid.Overlay(text, self.current_view, 'left',
                                               ('relative', 100), 'bottom', None)
        return self.submit_confirm_view

    def make_search_view(self):
        text = urwid.AttrMap(urwid.Edit('Search by id: ', ''), 'body')
        self.search_view = urwid.Overlay(text, self.current_view, 'left',
                                               ('relative', 100), 'bottom', None)
        return self.search_view

    def make_detailview(self, data):
        self.detail_view = DetailView(data, self.leetcode, self.loop)
        return self.detail_view

    def make_listview(self, data):
        header = self.make_header()
        self.home_view = HomeView(data, header, self)
        return self.home_view

    def make_header(self):
        if self.leetcode.is_login:
            columns = [
                ('fixed', 15, urwid.Padding(urwid.AttrWrap(
                    urwid.Text('%s' % config.username),
                    'head', ''))),
                urwid.AttrWrap(urwid.Text('You have solved %d / %d problems. ' %
                    (len(self.leetcode.solved), len(self.leetcode.items))), 'head', ''),
            ]
            return urwid.Columns(columns)
        else:
            text = urwid.AttrWrap(urwid.Text('Not login'), 'head')
        return text

    def make_helpview(self):
        self.help_view = HelpView()
        return self.help_view

    def show_loading(self, text, width, host_view=urwid.SolidFill()):
        self.loading_view = LoadingView(text, width, host_view, self.loop)
        self.loop.widget = self.loading_view
        self.loading_view.start()

    def end_loading(self):
        if self.loading_view:
            self.loading_view.end()
            self.loading_view = None

    def retrieve_home_done(self, data):
        self.home_view = self.make_listview(data)
        self.view_stack = []
        self.goto_view(self.home_view)
        self.end_loading()
        delay_refresh(self.loop)

    def retrieve_detail_done(self, title, body, code):
        quizid = self.home_view.listbox.get_focus()[0].data.id
        url = self.home_view.listbox.get_focus()[0].data.url
        data = DetailData(title, body, code, quizid, url)
        self.goto_view(self.make_detailview(data))
        self.end_loading()
        delay_refresh(self.loop)

    def run_retrieve_home(self):
        if not self.leetcode.is_login:
            self.leetcode.is_login = auth.login()
        if self.loading_view:
            self.loading_view.set_text('Loading')
        data = self.leetcode.hard_retrieve_home()
        if data:
            self.retrieve_home_done(data)
        else:
            self.end_loading()
            toast = Toast('Request fail!', 10, self.current_view, self.loop)
            toast.show()

    def run_retrieve_detail(self, data):
        ret = self.leetcode.retrieve_detail(data)
        if ret:
            title, body, code = ret
            self.retrieve_detail_done(title, body, code)
        else:
            toast = Toast('Request fail!', 10, self.current_view, self.loop)
            toast.show()
            self.logger.error('get detail %s fail', data.id)

    def run_send_code(self, data):
        success, text_or_id = self.leetcode.submit_code(data)
        if success:
            self.loading_view.set_text('Retrieving')
            code = 1
            while code > 0:
                r = self.leetcode.check_submission_result(text_or_id)
                code = r[0]

            self.end_loading()
            if code < 0:
                toast = Toast('error: %s' % r[1], 10 + len(r[1]), self.current_view, self.loop)
            else:
                runtime = r[3]
                if runtime == 'N/A':
                    toast = Toast('faied test: %d/%d' % (r[1], r[2]), 20, self.current_view, self.loop)
                else:
                    toast = Toast('success, time: %s' % r[3], 20, self.current_view, self.loop)
            toast.show()
            delay_refresh(self.loop)
        else:
            self.end_loading()
            toast = Toast('error: %s' % text_or_id, 10 + len(text_or_id), self.current_view, self.loop)
            toast.show()
            self.logger.error('send data fail')

    def send_code(self, data):
        self.show_loading('Sending code', 17, self.current_view)
        self.t = Thread(target=self.run_send_code, args=(data,))
        self.t.start()

    def run(self):
        self.loop = urwid.MainLoop(None, palette, unhandled_input=self.keystroke)
        self.show_loading('Log In', 12)
        self.t = Thread(target=self.run_retrieve_home)
        self.t.start()
        try:
            self.loop.run()
        except KeyboardInterrupt:
            sys.exit()
        finally:
            self.logger.info("clear thread")
            self.clear_thread()

    def clear_thread(self):
        if self.loading_view:
            self.loading_view.end()
        if self.t and self.t.is_alive():
            t.join()

