#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python wrapper for Android uiautomator tool."""

import base64
import collections
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
import uuid
import xml.dom.minidom
import requests

MAINPACKAGE = 'org.bitbucket.tksn.testsupportapp2'
TESTPACKAGE = 'org.bitbucket.tksn.testsupportapp2.test'
TESTRUNNER = 'android.support.test.runner.AndroidJUnitRunner'
INSTRUMENT_EXTRA_OPTS = [
    '-e', 'class', 'org.bitbucket.tksn.testsupportapp2.TestSupportMain',
    '-e', 'hideWindow', 'true'
]
DEVICE_PORT = int(os.environ.get('UIAUTOMATOR_DEVICE_PORT', '9008'))
LOCAL_PORT = int(os.environ.get('UIAUTOMATOR_LOCAL_PORT', '9008'))

JSONRPC_TIMEOUT = int(os.environ.get('JSONRPC_TIMEOUT', 20))
RESTART_TIMEOUT_AFTER_INSTRUMENT_RESET = 7
RESTART_TIMEOUT_AFTER_REINSTALL = 23
STOP_TIMEOUT = 5


if 'localhost' not in os.environ.get('no_proxy', ''):
    os.environ['no_proxy'] = "localhost,%s" % os.environ.get('no_proxy', '')

__all__ = ["Device", "rect", "point", "Selector", "JsonRPCError"]


def U(x):
    if sys.version_info.major == 2:
        return x.decode('utf-8') if type(x) is str else x
    elif sys.version_info.major == 3:
        return x


def param_to_property(*props, **kwprops):
    if props and kwprops:
        raise SyntaxError("Can not set both props and kwprops at the same time.")

    class Wrapper(object):

        def __init__(self, func):
            self.func = func
            self.kwargs, self.args = {}, []

        def __getattr__(self, attr):
            if kwprops:
                for prop_name, prop_values in kwprops.items():
                    if attr in prop_values and prop_name not in self.kwargs:
                        self.kwargs[prop_name] = attr
                        return self
            elif attr in props:
                self.args.append(attr)
                return self
            raise AttributeError("%s parameter is duplicated or not allowed!" % attr)

        def __call__(self, *args, **kwargs):
            if kwprops:
                kwargs.update(self.kwargs)
                self.kwargs = {}
                return self.func(*args, **kwargs)
            else:
                new_args, self.args = self.args + list(args), []
                return self.func(*new_args, **kwargs)
    return Wrapper


ERROR_CODE_BASE = -32000
ERROR_CODE_FILE_NOT_FOUND = ERROR_CODE_BASE - 2

class JsonRPCError(Exception):

    def __init__(self, code, message):
        self.code = int(code)
        self.message = message

    def __str__(self):
        return "JsonRPC Error code: %d, Message: %s" % (self.code, self.message)


def jsonrpc_call(url, timeout, call_desc, session=None):
    rpc_id = str(uuid.uuid4())
    data = {
        'jsonrpc': '2.0', 'method': call_desc['method'], 'id': rpc_id,
        'params': call_desc.get('args', [])}

    logging.debug('POST:{}'.format(json.dumps(data)))
    req = session or requests
    jsonresult = req.post(url, json=data, timeout=timeout).json()

    logging.debug('  -> {}'.format(json.dumps(jsonresult)))

    error = jsonresult.get('error')
    if error:
        edata = error.get('data', {})
        etype = edata.get('exceptionTypeName', '')
        emsg = error.get('message', '')
        raise JsonRPCError(error.get('code'), '{}: {}'.format(etype, emsg))
    return jsonresult.get('result')



def add_fnf_handling(call, handlers):

    def wrap(method, *args, **kwargs):
        try:
            return call(method, *args, **kwargs)
        except JsonRPCError as e:
            if e.code != ERROR_CODE_FILE_NOT_FOUND:
                raise
        try:
            handlers['on'] = False
            # any handler returns True will break the left handlers
            any(handler(handlers.get('device', None)) for handler in handlers['handlers'])
        finally:
            handlers['on'] = True
        return call(method, *args, **kwargs)
    return wrap


def add_recovery(call, restart_server):
    
    def wrap(method, *args, **kwargs):
        try:
            return call(method, *args, **kwargs)
        except requests.exceptions.RequestException as e:
            logging.debug('RequestException during JSONRPC call: {}'.format(e))
        except JsonRPCError as e:
            logging.debug('JsonRPCError during JSONRPC call: {}'.format(e))
        restart_server()
        return call(method, *args, **kwargs)
    return wrap


class JsonRPCClient(object):

    def __init__(self, call):
        self.__call = call

    def __getattr__(self, method):
        def call(*args, **kwargs):
            return self.__call(method, *args, **kwargs)
        return call


class Selector(dict):

    """The class is to build parameters for UiSelector passed to Android device.
    """
    __fields = {
        "text": (0x01, None),  # MASK_TEXT,
        "textContains": (0x02, None),  # MASK_TEXTCONTAINS,
        "textMatches": (0x04, None),  # MASK_TEXTMATCHES,
        "textStartsWith": (0x08, None),  # MASK_TEXTSTARTSWITH,
        "className": (0x10, None),  # MASK_CLASSNAME
        "classNameMatches": (0x20, None),  # MASK_CLASSNAMEMATCHES
        "description": (0x40, None),  # MASK_DESCRIPTION
        "descriptionContains": (0x80, None),  # MASK_DESCRIPTIONCONTAINS
        "descriptionMatches": (0x0100, None),  # MASK_DESCRIPTIONMATCHES
        "descriptionStartsWith": (0x0200, None),  # MASK_DESCRIPTIONSTARTSWITH
        "checkable": (0x0400, False),  # MASK_CHECKABLE
        "checked": (0x0800, False),  # MASK_CHECKED
        "clickable": (0x1000, False),  # MASK_CLICKABLE
        "longClickable": (0x2000, False),  # MASK_LONGCLICKABLE,
        "scrollable": (0x4000, False),  # MASK_SCROLLABLE,
        "enabled": (0x8000, False),  # MASK_ENABLED,
        "focusable": (0x010000, False),  # MASK_FOCUSABLE,
        "focused": (0x020000, False),  # MASK_FOCUSED,
        "selected": (0x040000, False),  # MASK_SELECTED,
        "packageName": (0x080000, None),  # MASK_PACKAGENAME,
        "packageNameMatches": (0x100000, None),  # MASK_PACKAGENAMEMATCHES,
        "resourceId": (0x200000, None),  # MASK_RESOURCEID,
        "resourceIdMatches": (0x400000, None),  # MASK_RESOURCEIDMATCHES,
        "index": (0x800000, 0),  # MASK_INDEX,
        "instance": (0x01000000, 0)  # MASK_INSTANCE,
    }
    __mask, __childOrSibling, __childOrSiblingSelector = "mask", "childOrSibling", "childOrSiblingSelector"

    def __init__(self, **kwargs):
        super(Selector, self).__setitem__(self.__mask, 0)
        super(Selector, self).__setitem__(self.__childOrSibling, [])
        super(Selector, self).__setitem__(self.__childOrSiblingSelector, [])
        for k in kwargs:
            self[k] = kwargs[k]

    def __setitem__(self, k, v):
        if k in self.__fields:
            super(Selector, self).__setitem__(U(k), U(v))
            super(Selector, self).__setitem__(self.__mask, self[self.__mask] | self.__fields[k][0])
        else:
            raise ReferenceError("%s is not allowed." % k)

    def __delitem__(self, k):
        if k in self.__fields:
            super(Selector, self).__delitem__(k)
            super(Selector, self).__setitem__(self.__mask, self[self.__mask] & ~self.__fields[k][0])

    def clone(self):
        kwargs = dict((k, self[k]) for k in self
                      if k not in [self.__mask, self.__childOrSibling, self.__childOrSiblingSelector])
        selector = Selector(**kwargs)
        for v in self[self.__childOrSibling]:
            selector[self.__childOrSibling].append(v)
        for s in self[self.__childOrSiblingSelector]:
            selector[self.__childOrSiblingSelector].append(s.clone())
        return selector

    def child(self, **kwargs):
        self[self.__childOrSibling].append("child")
        self[self.__childOrSiblingSelector].append(Selector(**kwargs))
        return self

    def sibling(self, **kwargs):
        self[self.__childOrSibling].append("sibling")
        self[self.__childOrSiblingSelector].append(Selector(**kwargs))
        return self

    child_selector, from_parent = child, sibling


def rect(top=0, left=0, bottom=100, right=100):
    return {"top": top, "left": left, "bottom": bottom, "right": right}


def intersect(rect1, rect2):
    top = rect1["top"] if rect1["top"] > rect2["top"] else rect2["top"]
    bottom = rect1["bottom"] if rect1["bottom"] < rect2["bottom"] else rect2["bottom"]
    left = rect1["left"] if rect1["left"] > rect2["left"] else rect2["left"]
    right = rect1["right"] if rect1["right"] < rect2["right"] else rect2["right"]
    return left, top, right, bottom


def point(x=0, y=0):
    return {"x": x, "y": y}


class Adb(object):

    def __init__(self, serial=None, adb_server_host=None, adb_server_port=None):
        self.__adb_cmd = None
        self.default_serial = serial if serial else os.environ.get("ANDROID_SERIAL", None)
        self.adb_server_host = str(adb_server_host if adb_server_host else 'localhost')
        self.adb_server_port = str(adb_server_port if adb_server_port else '5037')
        self.adbHostPortOptions = []
        if self.adb_server_host not in ['localhost', '127.0.0.1']:
            self.adbHostPortOptions += ["-H", self.adb_server_host]
        if self.adb_server_port != '5037':
            self.adbHostPortOptions += ["-P", self.adb_server_port]

    def adb(self):
        if self.__adb_cmd is None:
            if "ANDROID_HOME" in os.environ:
                filename = "adb.exe" if os.name == 'nt' else "adb"
                adb_cmd = os.path.join(os.environ["ANDROID_HOME"], "platform-tools", filename)
                if not os.path.exists(adb_cmd):
                    raise EnvironmentError(
                        "Adb not found in $ANDROID_HOME path: %s." % os.environ["ANDROID_HOME"])
            else:
                import distutils
                if "spawn" not in dir(distutils):
                    import distutils.spawn
                adb_cmd = distutils.spawn.find_executable("adb")
                if adb_cmd:
                    adb_cmd = os.path.realpath(adb_cmd)
                else:
                    raise EnvironmentError("$ANDROID_HOME environment not set.")
            self.__adb_cmd = adb_cmd
        return self.__adb_cmd

    def cmd(self, *args, **kwargs):
        '''adb command, add -s serial by default. return the subprocess.Popen object.'''
        serial = self.device_serial()
        if serial:
            if " " in serial:  # TODO how to include special chars on command line
                serial = "'%s'" % serial
            return self.raw_cmd(*["-s", serial] + list(args))
        else:
            return self.raw_cmd(*args)

    def raw_cmd(self, *args):
        '''adb command. return the subprocess.Popen object.'''
        cmd_line = [self.adb()] + self.adbHostPortOptions + list(args)
        if os.name != "nt":
            cmd_line = [" ".join(cmd_line)]
        logging.debug('POPEN:{}'.format(cmd_line))
        return subprocess.Popen(cmd_line, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def device_serial(self):
        if not self.default_serial:
            devices = self.devices()
            if devices:
                if len(devices) == 1:
                    self.default_serial = list(devices.keys())[0]
                else:
                    raise EnvironmentError("Multiple devices attached but default android serial not set.")
            else:
                raise EnvironmentError("Device not attached.")
        return self.default_serial

    def devices(self):
        '''get a dict of attached devices. key is the device serial, value is device name.'''
        out = self.raw_cmd("devices").communicate()[0].decode("utf-8")
        match = "List of devices attached"
        index = out.find(match)
        if index < 0:
            raise EnvironmentError("adb is not working.")
        return dict([s.split("\t") for s in out[index + len(match):].strip().splitlines() if s.strip()])

    def forward(self, local_port, device_port):
        '''adb port forward. return 0 if success, else non-zero.'''
        return self.cmd("forward", "tcp:%d" % local_port, "tcp:%d" % device_port).wait()

    def forward_list(self):
        '''adb forward --list'''
        version = self.version()
        if int(version[1]) <= 1 and int(version[2]) <= 0 and int(version[3]) < 31:
            raise EnvironmentError("Low adb version.")
        lines = self.raw_cmd("forward", "--list").communicate()[0].decode("utf-8").strip().splitlines()
        return [line.strip().split() for line in lines]

    def version(self):
        '''adb version'''
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", self.raw_cmd("version").communicate()[0].decode("utf-8"))
        return [match.group(i) for i in range(4)]


_init_local_port = LOCAL_PORT - 1


def next_local_port(adbHost=None):
    def is_port_listening(port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = s.connect_ex((str(adbHost) if adbHost else '127.0.0.1', port))
        s.close()
        return result == 0
    global _init_local_port
    _init_local_port = _init_local_port + 1 if _init_local_port < 32764 else LOCAL_PORT
    while is_port_listening(_init_local_port):
        _init_local_port += 1
    return _init_local_port


class NotFoundHandler(object):

    '''
    Handler for UI Object Not Found exception.
    It's a replacement of UiAutomator watcher on device side.
    '''

    def __init__(self):
        self.__handlers = collections.defaultdict(lambda: {'on': True, 'handlers': []})

    def __get__(self, instance, type):
        return self.__handlers[instance.adb.device_serial()]




class AutomatorServer(object):

    """start and quit rpc server on device.
    """
    __apk_dir = 'libs'
    __apk_files = ['app-debug.apk', 'app-debug-androidTest.apk']

    __sdk = 0

    handlers = NotFoundHandler()  # handler UI Not Found exception

    def __init__(self,
            serial=None, local_port=None, device_port=None,
            adb_server_host=None, adb_server_port=None,
            auto_restart=True):
        self.uiautomator_process = None
        self.session = None
        self.adb = Adb(serial=serial, adb_server_host=adb_server_host, adb_server_port=adb_server_port)
        self.device_port = int(device_port) if device_port else DEVICE_PORT
        if local_port:
            self.local_port = local_port
        else:
            try:  # first we will try to use the local port already adb forwarded
                for s, lp, rp in self.adb.forward_list():
                    if s == self.adb.device_serial() and rp == 'tcp:%d' % self.device_port:
                        self.local_port = int(lp[4:])
                        break
                else:
                    self.local_port = next_local_port(adb_server_host)
            except:
                self.local_port = next_local_port(adb_server_host)
        self.auto_restart = auto_restart

    def jsonrpc(self, timeout=None):
        to = timeout or JSONRPC_TIMEOUT
        def call(method, *args, **kwargs):
            call_desc = {
                'method': method, 'args': args or kwargs}
            if self.session is None:
                self.session = requests.Session()
            return jsonrpc_call(self.rpc_uri, to, call_desc, self.session)
        wrapped_call = add_recovery(
            add_fnf_handling(call, self.handlers), self.restart)
        return JsonRPCClient(wrapped_call)

    def sdk_version(self):
        '''sdk version of connected device.'''
        if self.__sdk == 0:
            try:
                self.__sdk = int(self.adb.cmd("shell", "getprop", "ro.build.version.sdk").communicate()[0].decode("utf-8").strip())
            except:
                pass
        return self.__sdk

    def install(self):
        base_dir = os.path.dirname(__file__)
        for apk in self.__apk_files:
            dirpath = os.path.join(base_dir, self.__apk_dir)
            apkpath = os.path.join(dirpath, apk)
            self.adb.cmd("install", "-r", "-t", apkpath).communicate()

    def set_forwarding(self):
        self.adb.forward(self.local_port, self.device_port)

    def start_instrumentation(self):
        cmd = ['shell', 'am', 'instrument']
        instrument_opts = ['-r', '-w', '-e', 'port', str(DEVICE_PORT)]
        instrument_opts.extend(INSTRUMENT_EXTRA_OPTS)
        cmd.extend(instrument_opts)
        cmd.append('/'.join((TESTPACKAGE, TESTRUNNER)))
        self.uiautomator_process = self.adb.cmd(*cmd)
        self.session = None

    def force_stop(self, package):
        cmd = ['shell', 'am', 'force-stop', package]
        self.adb.cmd(*cmd).communicate()

    def stop_instrumentation(self, signal_server=False):
        if self.uiautomator_process and self.uiautomator_process.poll() is None:
            if signal_server:
                try:
                    jsonrpc_call(self.rpc_uri, timeout=5, call_desc={'method': 'stopServer'})
                    self.uiautomator_process.communicate(timeout=STOP_TIMEOUT)
                except:
                    self.uiautomator_process.kill()
            else:
                self.uiautomator_process.kill()
            self.uiautomator_process = None
        self.force_stop(MAINPACKAGE)
        self.force_stop(TESTPACKAGE)

    def wait_device(self, timeout):
        due = time.time() + timeout
        while not self.alive and time.time() < due:
            time.sleep(0.1)
        if not self.alive:
            self.uiautomator_process.kill()
            try:
                out, err = self.uiautomator_process.communicate(timeout=10)
                logging.debug('Instrument stdout/stderr=[{}/{}]'.format(out, err))
                raise IOError("RPC server not started!")
            except subprocess.TimeoutExpired:
                self.uiautomator_process.kill()
                raise IOError("RPC server not started! (communicate)")


    def start(self, timeout=JSONRPC_TIMEOUT):
        self.install()
        self.set_forwarding()
        self.start_instrumentation()
        self.wait_device(timeout)

    def restart(self):
        self.set_forwarding()
        if not self.auto_restart:
            return

        self.stop_instrumentation()
        self.start_instrumentation()

        try:
            self.wait_device(timeout=RESTART_TIMEOUT_AFTER_INSTRUMENT_RESET)
            return
        except IOError:
            pass

        self.stop_instrumentation()
        self.install()
        self.start_instrumentation()
        self.wait_device(timeout=RESTART_TIMEOUT_AFTER_REINSTALL)

    def ping(self):
        try:
            return jsonrpc_call(url=self.rpc_uri, timeout=JSONRPC_TIMEOUT,
                call_desc={'method': 'ping'})
        except:
            return None

    @property
    def alive(self):
        '''Check if the rpc server is alive.'''
        return self.ping() == "pong"

    def stop(self):
        '''Stop the rpc server.'''
        self.stop_instrumentation(signal_server=True)

    @property
    def rpc_uri(self):
        return "http://%s:%d/jsonrpc/" % (self.adb.adb_server_host, self.local_port)

    @property
    def screenshot_uri(self):
        return "http://%s:%d/screenshot.png" % (self.adb.adb_server_host, self.local_port)

    def screenshot(self, scale=1.0, quality=100):
        result = requests.get(
            '{}?scale={}&quality={}'.format(self.screenshot_uri, scale, quality))
        return result.content


class AutomatorDevice(object):

    '''uiautomator wrapper of android device'''

    __orientation = (  # device orientation
        (0, "natural", "n", 0),
        (1, "left", "l", 90),
        (2, "upsidedown", "u", 180),
        (3, "right", "r", 270)
    )
    __alias = {
        "width": "displayWidth",
        "height": "displayHeight"
    }

    def __init__(self,
            serial=None, local_port=None, device_port=None,
            adb_server_host=None, adb_server_port=None,
            auto_restart_server=True,
            jsonrpc_timeout=None, server=None):
        if server is not None:
            self.server = server
        else:
            self.server = AutomatorServer(
                serial=serial,
                local_port=local_port,
                device_port=device_port,
                adb_server_host=adb_server_host,
                adb_server_port=adb_server_port,
                auto_restart=auto_restart_server
            )
        self.jsonrpc_timeout = jsonrpc_timeout

    def jsonrpc(self, timeout=None):
        timeout = timeout or self.jsonrpc_timeout
        return self.server.jsonrpc(timeout=timeout)

    def timeout(self, timeout):
        return AutomatorDevice(server=self.server, jsonrpc_timeout=timeout)

    def __call__(self, **kwargs):
        return AutomatorDeviceObject(self, Selector(**kwargs))

    def __getattr__(self, attr):
        '''alias of fields in info property.'''
        info = self.info
        if attr in info:
            return info[attr]
        elif attr in self.__alias:
            return info[self.__alias[attr]]
        else:
            raise AttributeError("%s attribute not found!" % attr)

    @property
    def info(self):
        '''Get the device info.'''
        return self.jsonrpc().deviceInfo()

    def click(self, x, y):
        '''click at arbitrary coordinates.'''
        return self.jsonrpc().click(x, y)

    def long_click(self, x, y):
        '''long click at arbitrary coordinates.'''
        return self.swipe(x, y, x + 1, y + 1)

    def swipe(self, sx, sy, ex, ey, steps=100):
        return self.jsonrpc().swipe(sx, sy, ex, ey, steps)

    def swipePoints(self, points, steps=100):
        ppoints = []
        for p in points:
            ppoints.append(p[0])
            ppoints.append(p[1])
        return self.jsonrpc().swipePoints(ppoints, steps)

    def drag(self, sx, sy, ex, ey, steps=100):
        '''Swipe from one point to another point.'''
        return self.jsonrpc().drag(sx, sy, ex, ey, steps)

    def dump(self, filename=None, compressed=True, pretty=True):
        '''dump device window and pull to local file.'''
        content = self.jsonrpc().dumpWindowHierarchy(compressed, None)
        if filename:
            with open(filename, "wb") as f:
                f.write(content.encode("utf-8"))
        if pretty and "\n " not in content:
            xml_text = xml.dom.minidom.parseString(content.encode("utf-8"))
            content = U(xml_text.toprettyxml(indent='  '))
        return content

    def screenshot(self, filename, scale=1.0, quality=100):
        '''take screenshot.'''
        result = self.server.screenshot(filename, scale, quality)
        if result:
            return result

        device_file = self.jsonrpc().takeScreenshot("screenshot.png",
                                                         scale, quality)
        if not device_file:
            return None
        p = self.server.adb.cmd("pull", device_file, filename)
        p.wait()
        self.server.adb.cmd("shell", "rm", device_file).wait()
        return filename if p.returncode is 0 else None

    def freeze_rotation(self, freeze=True):
        '''freeze or unfreeze the device rotation in current status.'''
        self.jsonrpc().freezeRotation(freeze)

    @property
    def orientation(self):
        '''
        orienting the devie to left/right or natural.
        left/l:       rotation=90 , displayRotation=1
        right/r:      rotation=270, displayRotation=3
        natural/n:    rotation=0  , displayRotation=0
        upsidedown/u: rotation=180, displayRotation=2
        '''
        return self.__orientation[self.info["displayRotation"]][1]

    @orientation.setter
    def orientation(self, value):
        '''setter of orientation property.'''
        for values in self.__orientation:
            if value in values:
                # can not set upside-down until api level 18.
                self.jsonrpc().setOrientation(values[1])
                break
        else:
            raise ValueError("Invalid orientation.")

    @property
    def last_traversed_text(self):
        '''get last traversed text. used in webview for highlighted text.'''
        return self.jsonrpc().getLastTraversedText()

    def clear_traversed_text(self):
        '''clear the last traversed text.'''
        self.jsonrpc().clearLastTraversedText()

    @property
    def open(self):
        '''
        Open notification or quick settings.
        Usage:
        d.open.notification()
        d.open.quick_settings()
        '''
        @param_to_property(action=["notification", "quick_settings"])
        def _open(action):
            if action == "notification":
                return self.jsonrpc().openNotification()
            else:
                return self.jsonrpc().openQuickSettings()
        return _open

    @property
    def handlers(self):
        obj = self

        class Handlers(object):

            def on(self, fn):
                if fn not in obj.server.handlers['handlers']:
                    obj.server.handlers['handlers'].append(fn)
                obj.server.handlers['device'] = obj
                return fn

            def off(self, fn):
                if fn in obj.server.handlers['handlers']:
                    obj.server.handlers['handlers'].remove(fn)

        return Handlers()

    @property
    def watchers(self):
        obj = self

        class Watchers(list):

            def __init__(self):
                for watcher in obj.jsonrpc().getWatchers():
                    self.append(watcher)

            @property
            def triggered(self):
                return obj.jsonrpc().hasAnyWatcherTriggered()

            def remove(self, name=None):
                if name:
                    obj.jsonrpc().removeWatcher(name)
                else:
                    for name in self:
                        obj.jsonrpc().removeWatcher(name)

            def reset(self):
                obj.jsonrpc().resetWatcherTriggers()
                return self

            def run(self):
                obj.jsonrpc().runWatchers()
                return self
        return Watchers()

    def watcher(self, name):
        obj = self

        class Watcher(object):

            def __init__(self):
                self.__selectors = []

            @property
            def triggered(self):
                return obj.jsonrpc().hasWatcherTriggered(name)

            def remove(self):
                obj.jsonrpc().removeWatcher(name)

            def when(self, **kwargs):
                self.__selectors.append(Selector(**kwargs))
                return self

            def click(self, **kwargs):
                obj.jsonrpc().registerClickUiObjectWatcher(name, self.__selectors, Selector(**kwargs))

            @property
            def press(self):
                @param_to_property(
                    "home", "back", "left", "right", "up", "down", "center",
                    "search", "enter", "delete", "del", "recent", "volume_up",
                    "menu", "volume_down", "volume_mute", "camera", "power")
                def _press(*args):
                    obj.jsonrpc().registerPressKeyskWatcher(name, self.__selectors, args)
                return _press
        return Watcher()

    @property
    def press(self):
        '''
        press key via name or key code. Supported key name includes:
        home, back, left, right, up, down, center, menu, search, enter,
        delete(or del), recent(recent apps), volume_up, volume_down,
        volume_mute, camera, power.
        Usage:
        d.press.back()  # press back key
        d.press.menu()  # press home key
        d.press(89)     # press keycode
        '''
        @param_to_property(
            key=["home", "back", "left", "right", "up", "down", "center",
                 "menu", "search", "enter", "delete", "del", "recent",
                 "volume_up", "volume_down", "volume_mute", "camera", "power"]
        )
        def _press(key, meta=None):
            if isinstance(key, int):
                return self.jsonrpc().pressKeyCode(key, meta) if meta else self.jsonrpc().pressKeyCode(key)
            else:
                return self.jsonrpc().pressKey(str(key))
        return _press

    def wakeup(self):
        '''turn on screen in case of screen off.'''
        self.jsonrpc().wakeUp()

    def sleep(self):
        '''turn off screen in case of screen on.'''
        self.jsonrpc().sleep()

    @property
    def screen(self):
        '''
        Turn on/off screen.
        Usage:
        d.screen.on()
        d.screen.off()

        d.screen == 'on'  # Check if the screen is on, same as 'd.screenOn'
        d.screen == 'off'  # Check if the screen is off, same as 'not d.screenOn'
        '''
        devive_self = self

        class _Screen(object):
            def on(self):
                return devive_self.wakeup()

            def off(self):
                return devive_self.sleep()

            def __call__(self, action):
                if action == "on":
                    return self.on()
                elif action == "off":
                    return self.off()
                else:
                    raise AttributeError("Invalid parameter: %s" % action)

            def __eq__(self, value):
                info = devive_self.info
                if "screenOn" not in info:
                    raise EnvironmentError("Not supported on Android 4.3 and belows.")
                if value in ["on", "On", "ON"]:
                    return info["screenOn"]
                elif value in ["off", "Off", "OFF"]:
                    return not info["screenOn"]
                raise ValueError("Invalid parameter. It can only be compared with on/off.")

            def __ne__(self, value):
                return not self.__eq__(value)

        return _Screen()

    @property
    def wait(self):
        '''
        Waits for the current application to idle or window update event occurs.
        Usage:
        d.wait.idle(timeout=1000)
        d.wait.update(timeout=1000, package_name="com.android.settings")
        '''
        @param_to_property(action=["idle", "update"])
        def _wait(action, timeout=1000, package_name=None):
            http_timeout = timeout / 1000 + JSONRPC_TIMEOUT
            if action == "idle":
                return self.jsonrpc(timeout=http_timeout).waitForIdle(timeout)
            elif action == "update":
                return self.jsonrpc(timeout=http_timeout).waitForWindowUpdate(package_name, timeout)
        return _wait

    def exists(self, **kwargs):
        '''Check if the specified ui object by kwargs exists.'''
        return self(**kwargs).exists

    def remote_exec(self, text, timeout=60000):
        token = self.jsonrpc().runScript(text)
        start_time = time.time()
        timeout_sec = timeout / 1000
        while time.time() - start_time < timeout_sec:
            result = self.jsonrpc().getScriptResult(token)
            if result is not None:
                if result.get('resultCode') == 0:
                    return result['stdOutString']
                else:
                    raise RuntimeError(
                        'Remote script execution failed: code={resultCode}, message={stdErrString}'.format(**result))
            time.sleep(1.0)
        raise RuntimeError('Remote script execution timeout')

    def remote_exec_apk(self, apk_path, class_name, args_dict, timeout=60000):
        with open(apk_path, 'rb') as f:
            apk_data = base64.b64encode(f.read()).decode('ascii')
        token = self.jsonrpc().runApk(apk_data, class_name, args_dict)
        start_time = time.time()
        timeout_sec = timeout / 1000
        while time.time() - start_time < timeout_sec:
            result = self.jsonrpc().getRunApkResult(token)
            if result is not None:
                return result
            time.sleep(1.0)
        raise RuntimeError('Remote script execution timeout')


Device = AutomatorDevice


class AutomatorDeviceUiObject(object):

    '''Represent a UiObject, on which user can perform actions, such as click, set text
    '''

    __alias = {'description': "contentDescription"}

    def __init__(self, device, selector):
        self.device = device
        self.selector = selector

    def jsonrpc(self):
        return self.device.jsonrpc()

    @property
    def exists(self):
        '''check if the object exists in current window.'''
        return self.jsonrpc().exist(self.selector)

    def __getattr__(self, attr):
        '''alias of fields in info property.'''
        info = self.info
        if attr in info:
            return info[attr]
        elif attr in self.__alias:
            return info[self.__alias[attr]]
        else:
            raise AttributeError("%s attribute not found!" % attr)

    @property
    def info(self):
        '''ui object info.'''
        return self.jsonrpc().objInfo(self.selector)

    def set_text(self, text):
        '''set the text field.'''
        if text in [None, ""]:
            return self.jsonrpc().clearTextField(self.selector)  # TODO no return
        else:
            return self.jsonrpc().setText(self.selector, text)

    def clear_text(self):
        '''clear text. alias for set_text(None).'''
        self.set_text(None)

    @property
    def click(self):
        '''
        click on the ui object.
        Usage:
        d(text="Clock").click()  # click on the center of the ui object
        d(text="OK").click.wait(timeout=3000) # click and wait for the new window update
        d(text="John").click.topleft() # click on the topleft of the ui object
        d(text="John").click.bottomright() # click on the bottomright of the ui object
        '''
        @param_to_property(action=["tl", "topleft", "br", "bottomright", "wait"])
        def _click(action=None, timeout=3000):
            if action is None:
                return self.jsonrpc().click(self.selector)
            elif action in ["tl", "topleft", "br", "bottomright"]:
                return self.jsonrpc().click(self.selector, action)
            else:
                return self.jsonrpc().clickAndWaitForNewWindow(self.selector, timeout)
        return _click

    @property
    def long_click(self):
        '''
        Perform a long click action on the object.
        Usage:
        d(text="Image").long_click()  # long click on the center of the ui object
        d(text="Image").long_click.topleft()  # long click on the topleft of the ui object
        d(text="Image").long_click.bottomright()  # long click on the topleft of the ui object
        '''
        @param_to_property(corner=["tl", "topleft", "br", "bottomright"])
        def _long_click(corner=None):
            info = self.info
            if info["longClickable"]:
                if corner:
                    return self.jsonrpc().longClick(self.selector, corner)
                else:
                    return self.jsonrpc().longClick(self.selector)
            else:
                bounds = info.get("visibleBounds") or info.get("bounds")
                if corner in ["tl", "topleft"]:
                    x = (5 * bounds["left"] + bounds["right"]) / 6
                    y = (5 * bounds["top"] + bounds["bottom"]) / 6
                elif corner in ["br", "bottomright"]:
                    x = (bounds["left"] + 5 * bounds["right"]) / 6
                    y = (bounds["top"] + 5 * bounds["bottom"]) / 6
                else:
                    x = (bounds["left"] + bounds["right"]) / 2
                    y = (bounds["top"] + bounds["bottom"]) / 2
                return self.device.long_click(x, y)
        return _long_click

    @property
    def drag(self):
        '''
        Drag the ui object to other point or ui object.
        Usage:
        d(text="Clock").drag.to(x=100, y=100)  # drag to point (x,y)
        d(text="Clock").drag.to(text="Remove") # drag to another object
        '''
        def to(obj, *args, **kwargs):
            if len(args) >= 2 or "x" in kwargs or "y" in kwargs:
                drag_to = lambda x, y, steps=100: self.jsonrpc().dragTo(self.selector, x, y, steps)
            else:
                drag_to = lambda steps=100, **kwargs: self.jsonrpc().dragTo(self.selector, Selector(**kwargs), steps)
            return drag_to(*args, **kwargs)
        return type("Drag", (object,), {"to": to})()

    def gesture(self, start1, start2, *args, **kwargs):
        '''
        perform two point gesture.
        Usage:
        d().gesture(startPoint1, startPoint2).to(endPoint1, endPoint2, steps)
        d().gesture(startPoint1, startPoint2, endPoint1, endPoint2, steps)
        '''
        def to(obj_self, end1, end2, steps=100):
            ctp = lambda pt: point(*pt) if type(pt) == tuple else pt  # convert tuple to point
            s1, s2, e1, e2 = ctp(start1), ctp(start2), ctp(end1), ctp(end2)
            return self.jsonrpc().gesture(self.selector, s1, s2, e1, e2, steps)
        obj = type("Gesture", (object,), {"to": to})()
        return obj if len(args) == 0 else to(None, *args, **kwargs)

    @property
    def pinch(self):
        '''
        Perform two point gesture from edge to center(in) or center to edge(out).
        Usages:
        d().pinch.In(percent=100, steps=10)
        d().pinch.Out(percent=100, steps=100)
        '''
        @param_to_property(in_or_out=["In", "Out"])
        def _pinch(in_or_out="Out", percent=100, steps=50):
            if in_or_out in ["Out", "out"]:
                return self.jsonrpc().pinchOut(self.selector, percent, steps)
            elif in_or_out in ["In", "in"]:
                return self.jsonrpc().pinchIn(self.selector, percent, steps)
        return _pinch

    @property
    def swipe(self):
        '''
        Perform swipe action. if device platform greater than API 18, percent can be used and value between 0 and 1
        Usages:
        d().swipe.right()
        d().swipe.left(steps=10)
        d().swipe.up(steps=10)
        d().swipe.down()
        d().swipe("right", steps=20)
        d().swipe("right", steps=20, percent=0.5)
        '''
        @param_to_property(direction=["up", "down", "right", "left"])
        def _swipe(direction="left", steps=10, percent=1):
            if percent == 1:
                return self.jsonrpc().swipe(self.selector, direction, steps)
            else:
                return self.jsonrpc().swipe(self.selector, direction, percent, steps)
        return _swipe

    @property
    def wait(self):
        '''
        Wait until the ui object gone or exist.
        Usage:
        d(text="Clock").wait.gone()  # wait until it's gone.
        d(text="Settings").wait.exists() # wait until it appears.
        '''
        @param_to_property(action=["exists", "gone"])
        def _wait(action, timeout=3000):
            http_timeout = timeout / 1000 + JSONRPC_TIMEOUT
            if action == "gone":
                return self.device.jsonrpc(
                    timeout=http_timeout).waitUntilGone(self.selector, timeout)
            else:
                return self.device.jsonrpc(
                    timeout=http_timeout).waitForExists(self.selector, timeout)
        return _wait


class AutomatorDeviceNamedUiObject(AutomatorDeviceUiObject):

    def __init__(self, device, name):
        super(AutomatorDeviceNamedUiObject, self).__init__(device, name)

    def child(self, **kwargs):
        return AutomatorDeviceNamedUiObject(
            self.device,
            self.jsonrpc().getChild(self.selector, Selector(**kwargs))
        )

    def sibling(self, **kwargs):
        return AutomatorDeviceNamedUiObject(
            self.device,
            self.jsonrpc().getFromParent(self.selector, Selector(**kwargs))
        )


class AutomatorDeviceObject(AutomatorDeviceUiObject):

    '''Represent a generic UiObject/UiScrollable/UiCollection,
    on which user can perform actions, such as click, set text
    '''

    def __init__(self, device, selector):
        super(AutomatorDeviceObject, self).__init__(device, selector)

    def child(self, **kwargs):
        '''set childSelector.'''
        return AutomatorDeviceObject(
            self.device,
            self.selector.clone().child(**kwargs)
        )

    def sibling(self, **kwargs):
        '''set fromParent selector.'''
        return AutomatorDeviceObject(
            self.device,
            self.selector.clone().sibling(**kwargs)
        )

    child_selector, from_parent = child, sibling

    def child_by_text(self, txt, **kwargs):
        if "allow_scroll_search" in kwargs:
            allow_scroll_search = kwargs.pop("allow_scroll_search")
            name = self.jsonrpc().childByText(
                self.selector,
                Selector(**kwargs),
                txt,
                allow_scroll_search
            )
        else:
            name = self.jsonrpc().childByText(
                self.selector,
                Selector(**kwargs),
                txt
            )
        return AutomatorDeviceNamedUiObject(self.device, name)

    def child_by_description(self, txt, **kwargs):
        if "allow_scroll_search" in kwargs:
            allow_scroll_search = kwargs.pop("allow_scroll_search")
            name = self.jsonrpc().childByDescription(
                self.selector,
                Selector(**kwargs),
                txt,
                allow_scroll_search
            )
        else:
            name = self.jsonrpc().childByDescription(
                self.selector,
                Selector(**kwargs),
                txt
            )
        return AutomatorDeviceNamedUiObject(self.device, name)

    def child_by_instance(self, inst, **kwargs):
        return AutomatorDeviceNamedUiObject(
            self.device,
            self.jsonrpc().childByInstance(self.selector, Selector(**kwargs), inst)
        )

    @property
    def count(self):
        return self.jsonrpc().count(self.selector)

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        count = self.count
        if index >= count:
            raise IndexError()
        elif count == 1:
            return self
        else:
            selector = self.selector.clone()
            selector["instance"] = index
            return AutomatorDeviceObject(self.device, selector)

    def __iter__(self):
        obj, length = self, self.count

        class Iter(object):

            def __init__(self):
                self.index = -1

            def next(self):
                self.index += 1
                if self.index < length:
                    return obj[self.index]
                else:
                    raise StopIteration()
            __next__ = next

        return Iter()

    def right(self, **kwargs):
        def onrightof(rect1, rect2):
            left, top, right, bottom = intersect(rect1, rect2)
            return rect2["left"] - rect1["right"] if top < bottom else -1
        return self.__view_beside(onrightof, **kwargs)

    def left(self, **kwargs):
        def onleftof(rect1, rect2):
            left, top, right, bottom = intersect(rect1, rect2)
            return rect1["left"] - rect2["right"] if top < bottom else -1
        return self.__view_beside(onleftof, **kwargs)

    def up(self, **kwargs):
        def above(rect1, rect2):
            left, top, right, bottom = intersect(rect1, rect2)
            return rect1["top"] - rect2["bottom"] if left < right else -1
        return self.__view_beside(above, **kwargs)

    def down(self, **kwargs):
        def under(rect1, rect2):
            left, top, right, bottom = intersect(rect1, rect2)
            return rect2["top"] - rect1["bottom"] if left < right else -1
        return self.__view_beside(under, **kwargs)

    def __view_beside(self, onsideof, **kwargs):
        bounds = self.info["bounds"]
        min_dist, found = -1, None
        for ui in AutomatorDeviceObject(self.device, Selector(**kwargs)):
            dist = onsideof(bounds, ui.info["bounds"])
            if dist >= 0 and (min_dist < 0 or dist < min_dist):
                min_dist, found = dist, ui
        return found

    @property
    def fling(self):
        '''
        Perform fling action.
        Usage:
        d().fling()  # default vertically, forward
        d().fling.horiz.forward()
        d().fling.vert.backward()
        d().fling.toBeginning(max_swipes=100) # vertically
        d().fling.horiz.toEnd()
        '''
        @param_to_property(
            dimention=["vert", "vertically", "vertical", "horiz", "horizental", "horizentally"],
            action=["forward", "backward", "toBeginning", "toEnd"]
        )
        def _fling(dimention="vert", action="forward", max_swipes=1000):
            vertical = dimention in ["vert", "vertically", "vertical"]
            if action == "forward":
                return self.jsonrpc().flingForward(self.selector, vertical)
            elif action == "backward":
                return self.jsonrpc().flingBackward(self.selector, vertical)
            elif action == "toBeginning":
                return self.jsonrpc().flingToBeginning(self.selector, vertical, max_swipes)
            elif action == "toEnd":
                return self.jsonrpc().flingToEnd(self.selector, vertical, max_swipes)

        return _fling

    @property
    def scroll(self):
        '''
        Perfrom scroll action.
        Usage:
        d().scroll(steps=50) # default vertically and forward
        d().scroll.horiz.forward(steps=100)
        d().scroll.vert.backward(steps=100)
        d().scroll.horiz.toBeginning(steps=100, max_swipes=100)
        d().scroll.vert.toEnd(steps=100)
        d().scroll.horiz.to(text="Clock")
        '''
        def __scroll(vertical, forward, steps=100):
            method = self.jsonrpc().scrollForward if forward else self.jsonrpc().scrollBackward
            return method(self.selector, vertical, steps)

        def __scroll_to_beginning(vertical, steps=100, max_swipes=1000):
            return self.jsonrpc().scrollToBeginning(self.selector, vertical, max_swipes, steps)

        def __scroll_to_end(vertical, steps=100, max_swipes=1000):
            return self.jsonrpc().scrollToEnd(self.selector, vertical, max_swipes, steps)

        def __scroll_to(vertical, **kwargs):
            return self.jsonrpc().scrollTo(self.selector, Selector(**kwargs), vertical)

        @param_to_property(
            dimention=["vert", "vertically", "vertical", "horiz", "horizental", "horizentally"],
            action=["forward", "backward", "toBeginning", "toEnd", "to"])
        def _scroll(dimention="vert", action="forward", **kwargs):
            vertical = dimention in ["vert", "vertically", "vertical"]
            if action in ["forward", "backward"]:
                return __scroll(vertical, action == "forward", **kwargs)
            elif action == "toBeginning":
                return __scroll_to_beginning(vertical, **kwargs)
            elif action == "toEnd":
                return __scroll_to_end(vertical, **kwargs)
            elif action == "to":
                return __scroll_to(vertical, **kwargs)
        return _scroll
