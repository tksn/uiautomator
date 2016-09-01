#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import re
import os.path
import codecs
from mock import MagicMock, call, patch
from uiautomatorminus import AutomatorDevice, Selector


def fake_jsonrpc_method(rpc_client, method, **kwargs):
    rpc_method = MagicMock(**kwargs)
    rpc_client.attach_mock(rpc_method, method)
    return rpc_method


class TestDevice(unittest.TestCase):

    def setUp(self):
        self.device = AutomatorDevice()
        self.device.server = MagicMock()
        self.device.server.jsonrpc = MagicMock()
        self.rpc_client = MagicMock()
        self.device.server.jsonrpc.return_value = self.rpc_client

    def fake_jsonrpc_method(self, method, **kwargs):
        return fake_jsonrpc_method(self.rpc_client, method, **kwargs)

    def test_info(self):
        method = self.fake_jsonrpc_method('deviceInfo', return_value={})
        self.assertEqual(self.device.info, {})
        method.assert_called_once_with()

    def test_click(self):
        method = self.fake_jsonrpc_method('click', return_value=True)
        self.assertEqual(self.device.click(1, 2), True)
        method.assert_called_once_with(1, 2)

    def test_swipe(self):
        method = self.fake_jsonrpc_method('swipe', return_value=True)
        self.assertEqual(self.device.swipe(1, 2, 3, 4, 100), True)
        method.assert_called_once_with(1, 2, 3, 4, 100)

    def test_long_click(self):
        method = self.fake_jsonrpc_method('swipe', return_value=True)
        x, y = 100, 200
        self.assertEqual(self.device.long_click(x, y), True)
        method.assert_called_once_with(x, y, x+1, y+1, 100)

    def test_drag(self):
        method = self.fake_jsonrpc_method('drag', return_value=True)
        self.assertEqual(self.device.drag(1, 2, 3, 4, 100), True)
        method.assert_called_once_with(1, 2, 3, 4, 100)

    def test_dump(self):
        with codecs.open(os.path.join(os.path.dirname(__file__), "res", "layout.xml"), "r", encoding="utf8") as f:
            xml = f.read()
            method = self.fake_jsonrpc_method('dumpWindowHierarchy', return_value=xml)
            self.assertEqual(self.device.dump("/tmp/test.xml"), xml)
            method.assert_called_once_with(True, None)
            self.assertEqual(self.device.dump("/tmp/test.xml", False), xml)

            raw_xml = "".join(re.split(r"\n[ ]*", xml))
            method = self.fake_jsonrpc_method('dumpWindowHierarchy', return_value=raw_xml)
            self.assertTrue("\n  " in self.device.dump("/tmp/test.xml"))

    def test_screenshot(self):
        method = self.fake_jsonrpc_method('takeScreenshot', return_value='1.png')
        self.device.server.adb.cmd = cmd = MagicMock()
        self.device.server.screenshot = MagicMock()
        self.device.server.screenshot.return_value = None
        cmd.return_value.returncode = 0
        self.assertEqual(self.device.screenshot("a.png", 1.0, 99), "a.png")
        method.assert_called_once_with("screenshot.png", 1.0, 99)
        self.assertEqual(cmd.call_args_list, [call("pull", "1.png", "a.png"), call("shell", "rm", "1.png")])

        method = self.fake_jsonrpc_method('takeScreenshot', return_value=None)
        self.assertEqual(self.device.screenshot("a.png", 1.0, 100), None)

    def test_freeze_rotation(self):
        method = self.fake_jsonrpc_method('freezeRotation')
        self.device.freeze_rotation(True)
        self.device.freeze_rotation(False)
        self.assertEqual(method.call_args_list, [call(True), call(False)])

    def test_orientation(self):
        orientation = {
            0: "natural",
            1: "left",
            2: "upsidedown",
            3: "right"
        }
        for i in range(4):
            method = self.fake_jsonrpc_method('deviceInfo', return_value={'displayRotation': i})
            self.assertEqual(self.device.orientation, orientation[i])
        # set
        orientations = [
            (0, "natural", "n", 0),
            (1, "left", "l", 90),
            (2, "upsidedown", "u", 180),
            (3, "right", "r", 270)
        ]
        for values in orientations:
            for value in values:
                method = self.fake_jsonrpc_method('setOrientation')
                self.device.orientation = value
                method.assert_called_once_with(values[1])

        with self.assertRaises(ValueError):
            self.device.orientation = "invalid orientation"

    def test_last_traversed_text(self):
        method = self.fake_jsonrpc_method('getLastTraversedText', return_value='abcdef')
        self.assertEqual(self.device.last_traversed_text, "abcdef")
        method.assert_called_once_with()

    def test_clear_traversed_text(self):
        method = self.fake_jsonrpc_method('clearLastTraversedText')
        self.device.clear_traversed_text()
        method.assert_called_once_with()

    def test_open(self):
        method = self.fake_jsonrpc_method('openNotification')
        self.device.open.notification()
        method.assert_called_once_with()
        method = self.fake_jsonrpc_method('openQuickSettings')
        self.device.open.quick_settings()
        method.assert_called_once_with()

    def test_watchers(self):
        names = ["a", "b", "c"]
        method = self.fake_jsonrpc_method('getWatchers', return_value=names)
        self.assertEqual(self.device.watchers, names)
        method.assert_called_once_with()

        method = self.fake_jsonrpc_method('hasAnyWatcherTriggered', return_value=True)
        self.assertEqual(self.device.watchers.triggered, True)
        method.assert_called_once_with()

        method = self.fake_jsonrpc_method('removeWatcher')
        self.device.watchers.remove("a")
        method.assert_called_once_with('a')
        method = self.fake_jsonrpc_method('removeWatcher')
        self.device.watchers.remove()
        self.assertEqual(method.call_args_list, [call(name) for name in names])

        method = self.fake_jsonrpc_method('resetWatcherTriggers')
        self.device.watchers.reset()
        method.assert_called_once_with()

        method = self.fake_jsonrpc_method('runWatchers')
        self.device.watchers.run()
        method.assert_called_once_with()

    def test_watcher(self):
        method = self.fake_jsonrpc_method('hasWatcherTriggered', return_value=False)
        self.assertFalse(self.device.watcher("name").triggered)
        method.assert_called_once_with("name")

        method = self.fake_jsonrpc_method('removeWatcher')
        self.device.watcher("a").remove()
        method.assert_called_once_with("a")

        method = self.fake_jsonrpc_method('registerClickUiObjectWatcher')
        condition1 = {"text": "my text", "className": "android"}
        condition2 = {"description": "my desc", "clickable": True}
        target = {"className": "android.widget.Button", "text": "OK"}
        self.device.watcher("watcher").when(**condition1).when(**condition2).click(**target)
        method.assert_called_once_with(
            "watcher",
            [Selector(**condition1), Selector(**condition2)],
            Selector(**target)
        )

        method = self.fake_jsonrpc_method('registerPressKeyskWatcher')
        self.device.watcher("watcher2").when(**condition1).when(**condition2).press.back.home.power("menu")
        method.assert_called_once_with(
            "watcher2", [Selector(**condition1), Selector(**condition2)], ("back", "home", "power", "menu"))

    def test_press(self):
        key = ["home", "back", "left", "right", "up", "down", "center",
               "menu", "search", "enter", "delete", "del", "recent",
               "volume_up", "volume_down", "volume_mute", "camera", "power"]
        method = self.fake_jsonrpc_method('pressKey', return_value=True)
        self.assertTrue(self.device.press.home())
        self.assertEqual(method.call_args_list, [call("home")])
        method = self.fake_jsonrpc_method('pressKey', return_value=False)
        self.assertFalse(self.device.press.back())
        self.assertEqual(method.call_args_list, [call("back")])
        method = self.fake_jsonrpc_method('pressKey', return_value=False)
        for k in key:
            self.assertFalse(self.device.press(k))
        self.assertEqual(method.call_args_list, [call(k) for k in key])

        method = self.fake_jsonrpc_method('pressKeyCode', return_value=True)
        self.assertTrue(self.device.press(1))
        self.assertTrue(self.device.press(1, 2))
        self.assertEqual(method.call_args_list, [call(1), call(1, 2)])

    def test_wakeup(self):
        method = self.fake_jsonrpc_method('wakeUp')
        self.device.wakeup()
        method.assert_called_once_with()

        method = self.fake_jsonrpc_method('wakeUp')
        self.device.screen.on()
        method.assert_called_once_with()

        method = self.fake_jsonrpc_method('wakeUp')
        self.device.screen("on")
        method.assert_called_once_with()

    def test_screen_status(self):
        method = self.fake_jsonrpc_method('deviceInfo', return_value={"screenOn": True})
        self.assertTrue(self.device.screen == "on")
        self.assertTrue(self.device.screen != "off")

        method = self.fake_jsonrpc_method('deviceInfo', return_value={"screenOn": False})
        self.assertTrue(self.device.screen == "off")
        self.assertTrue(self.device.screen != "on")

    def test_sleep(self):
        method = self.fake_jsonrpc_method('sleep')
        self.device.sleep()
        method.assert_called_once_with()

        method = self.fake_jsonrpc_method('sleep')
        self.device.screen.off()
        method.assert_called_once_with()

        method = self.fake_jsonrpc_method('sleep')
        self.device.screen("off")
        method.assert_called_once_with()

    def test_wait_idle(self):
        method = self.fake_jsonrpc_method('waitForIdle', return_value=True)
        self.assertTrue(self.device.wait.idle(timeout=10))
        method.assert_called_once_with(10)

        method = self.fake_jsonrpc_method('waitForIdle', return_value=False)
        self.assertFalse(self.device.wait("idle", timeout=10))
        method.assert_called_once_with(10)

    def test_wait_update(self):
        method = self.fake_jsonrpc_method('waitForWindowUpdate', return_value=True)
        self.assertTrue(self.device.wait.update(timeout=10, package_name="android"))
        method.assert_called_once_with("android", 10)

        method = self.fake_jsonrpc_method('waitForWindowUpdate', return_value=False)
        self.assertFalse(self.device.wait("update", timeout=100, package_name="android"))
        method.assert_called_once_with("android", 100)

    def test_get_info_attr(self):
        info = {"test_a": 1, "test_b": "string", "displayWidth": 720, "displayHeight": 1024}
        method = self.fake_jsonrpc_method('deviceInfo', return_value=info)
        for k in info:
            self.assertEqual(getattr(self.device, k), info[k])
        self.assertEqual(self.device.width, info["displayWidth"])
        self.assertEqual(self.device.height, info["displayHeight"])
        with self.assertRaises(AttributeError):
            self.device.not_exists

    def test_device_obj(self):
        with patch("uiautomatorminus.AutomatorDeviceObject") as AutomatorDeviceObject:
            kwargs = {"text": "abc", "description": "description...", "clickable": True}
            self.device(**kwargs)
            AutomatorDeviceObject.assert_called_once_with(self.device, Selector(**kwargs))

        with patch("uiautomatorminus.AutomatorDeviceObject") as AutomatorDeviceObject:
            AutomatorDeviceObject.return_value.exists = True
            self.assertTrue(self.device.exists(clickable=True))
            AutomatorDeviceObject.return_value.exists = False
            self.assertFalse(self.device.exists(text="..."))


class TestDeviceWithSerial(unittest.TestCase):

    def test_serial(self):
        with patch('uiautomatorminus.AutomatorServer') as AutomatorServer:
            AutomatorDevice("abcdefhijklmn")
            AutomatorServer.assert_called_once_with(serial="abcdefhijklmn", local_port=None, adb_server_host=None, adb_server_port=None)
