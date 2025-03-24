import random
import re
import subprocess
from collections import defaultdict
import gymnasium as gym
from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.common.touch_action import TouchAction
from gymnasium import spaces
import numpy as np
from appium import webdriver
import time
import xml.etree.ElementTree as ET
from selenium.common import StaleElementReferenceException, WebDriverException, InvalidSessionIdException, \
    InvalidElementStateException
from resourse.resourse import (init_resource, append_resource, get_resource, judge_resource, compute_resource_sensitivitis)


def get_current_activity():
    proc = subprocess.Popen("adb shell dumpsys window | findstr mCurrentFocus",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    memoryInfo, errInfo = proc.communicate()
    res = memoryInfo.decode().split('/')[-1].split('}')[0]
    if "mCurrentFocus" not in res:
        return memoryInfo.decode().split('/')[-1].split('}')[0]
    return None


def jaccard_similarity(state1, state2):
    state1 = np.array(state1)
    state2 = np.array(state2)
    intersection = np.sum(np.logical_and(state1, state2))
    union = np.sum(np.logical_or(state1, state2))
    similarity = intersection / union if union != 0 else 0
    return similarity


class AndroidAppEnv(gym.Env):
    def __init__(self, app_package_name, main_activity, al, activities, version, device_name, port, start_time, resource):
        self.al = al
        self.list_activities = defaultdict(list)  # Activity list
        self.widget_list = defaultdict(int)  # Views list
        self.exe_number = 50
        self.OBSERVATION_SPACE = 2000
        self.epi = 0
        self.bug_report = {}
        self.activities = activities
        self.activities_number = len(self.activities) + 10
        self.start_time = start_time
        self.resource_type = resource
        # Appium 配置
        self.desired_caps = {
            "platformName": "android",
            "platformVersion": version,
            "deviceName": device_name,
            "appPackage": app_package_name,
            "appActivity": main_activity,
            "skipDeviceInitialization": True,
            "noReset": True,
            "newCommandTimeout": 6000,
            "automationName": "UiAutomator2",
            "sessionOverride": True,
            'autoGrantPermissions': True,
        }
        self.driver = webdriver.Remote(f'http://127.0.0.1:{port}/wd/hub', self.desired_caps)

        self.package = app_package_name
        self.current_activity = get_current_activity()
        self.static_views = []
        self.views = {}
        self.update_views()

        self.action_space = spaces.Box(low=np.array([0, 0]),
                                       high=np.array([0.9999, 0.9999]),
                                       dtype=np.float32)

        self.observation_space = spaces.Dict(
            {
                "observation": spaces.Box(low=0, high=1, shape=(self.OBSERVATION_SPACE,), dtype=np.bool_),
                "achieved_goal": spaces.Box(low=0, high=1, shape=(self.OBSERVATION_SPACE,), dtype=np.bool_),
                "desired_goal": spaces.Box(low=0, high=1, shape=(self.OBSERVATION_SPACE,), dtype=np.bool_),
            }
        )

        self.max_steps = 30
        self.current_step = 0
        self.observation = self._get_observation()

        self.state = set()
        self.resource = get_resource(self.package)
        self.weight = {key: 1 for key in self.resource.keys()}
        self.collect_resource = init_resource(self.package)
        self.check_activity()

    def reset(self, seed=None, optional=None):
        super().reset(seed=seed)
        self.epi += 1
        self.current_step = 0
        try:
            self._close()
        except:
            pass
        self._start()
        self.current_activity = get_current_activity()
        self.update_views()

        return self.observation, {}

    def step(self, action_name):

        try:
            return self.step2(action_name)
        except StaleElementReferenceException:
            self._start()
            self.check_activity()
            return self.observation, -100.0, False, False, {}
        except WebDriverException:
            try:
                self._close()
            except InvalidSessionIdException:
                pass
            self._start()
            self.update_views()
            return self.observation, -100.0, True, False, {}
        except Exception as e:
            # print(e)
            self._start()
            self.update_views()
            return self.observation, -100.0, True, False, {}

    def step2(self, action_name):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}, step:{self.current_step}")
        action_name = self.normal_action(action_name)
        self.current_step += 1
        current_view = self.views[action_name[0]]
        try:
            self.action(current_view, action_name)
        except Exception as e:
            self.update_views()
            return self.observation, 0, self._termination(), False, {}
        out_side, reward = self.check_activity()
        if len(self.views) == 0:
            self.driver.back()
            self.update_views()
            return self.observation, -1000, self._termination(), False, {}
        if out_side:
            try:
                self._close()
            except:
                pass
            self._start()
            self.update_views()
            return self.observation, reward, self._termination(), False, {}
        return self.observation, reward, self._termination(), False, {}

    def check_activity(self):
        # Detect if jumped outside the app and calculate rewards
        if self.package != self.driver.current_package and self.driver.current_package != "com.android.permissioncontroller":
            return True, -1000
        self.update_views()
        self.current_activity = get_current_activity()
        temp_resource = get_resource(self.package)
        append_resource(self.package, self.collect_resource)
        reward = -1
        if self.current_activity and (self.current_activity not in self.list_activities or self.is_doubted_state()):
            self.list_activities[self.current_activity].append([self.get_tuple_observation(), time.time() - self.start_time, 0, 0])
            self.Edittext()
            self.scroll_neutral()
            is_bug = self.DOC()
            self.home_return_operation()
            self.notification_operation()
            self.list_activities[self.current_activity][-1][2] = is_bug
            self.list_activities[self.current_activity][-1][3] = temp_resource
            self.update_views()
        later_resource = get_resource(self.package)
        resource_sensitivity = compute_resource_sensitivitis(self.resource, temp_resource, self.weight)
        if self.get_tuple_observation() not in self.state:
            reward = resource_sensitivity
            self.state.add(self.get_tuple_observation())
        self.resource = get_resource(self.package)
        if self.resource_type == 'all':
            reward = compute_resource_sensitivitis(self.resource, later_resource, {key: 1 for key in self.resource.keys()})
        return False, reward


    def is_doubted_state(self):
        if not self.list_activities[self.current_activity]:
            return True
        for state, _, _, _ in self.list_activities[self.current_activity]:
            if jaccard_similarity(state, self.get_tuple_observation()) > 0.5:
                return False
        return True

    def normal_action(self, action_name):
        ac = [(action_name[0]) * (len(self.views)), (action_name[1]) * 2]
        ac = list(map(round, ac))
        return ac

    def action(self, current_view, action_number):
        if not current_view['view']:
            self.driver.back()
        elif current_view['class_name'] == 'android.widget.EditText':
            try:
                current_view['view'].clear()
                current_view['view'].click()
                current_string = ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
                                         for _ in range(random.randint(5, 10)))
                current_view['view'].send_keys(current_string)
            except InvalidElementStateException:
                print('Impossible to insert string')
            except Exception as e:
                print(e)
                pass
        else:
            if current_view['clickable'] == 'true' and current_view['long-clickable'] == 'false':
                current_view['view'].click()

            elif current_view['clickable'] == 'true' and current_view['long-clickable'] == 'true':
                if action_number[1] == 0:
                    current_view['view'].click()
                else:
                    actions = TouchAction(self.driver)
                    actions.long_press(current_view['view']).wait(1000).release().perform()

            elif current_view['clickable'] == 'false' and current_view['long-clickable'] == 'true':
                actions = TouchAction(self.driver)
                actions.long_press(current_view['view']).wait(1000).release().perform()

            elif current_view['scrollable'] == 'true':
                bounds = re.findall(r'\d+', current_view['view'].get_attribute('bounds'))
                bounds = [int(i) for i in bounds]
                if (bounds[2] - bounds[0] > 20) and (bounds[3] - bounds[1] > 40):
                    self.scroll_action(action_number, bounds)

    def scroll_action(self, action_number, bounds):
        y = int((bounds[3] - bounds[1]))
        x = int((bounds[2] - bounds[0]) / 2)
        if action_number[1] == 0:
            try:
                self.driver.swipe(x, int(y * 0.3), x, int(y * 0.5), duration=200)
            except InvalidElementStateException:
                print(f'swipe not performed start_position: ({x}, {y}), end_position: ({x}, {y + 20})')
        elif action_number[1] == 1:
            try:
                self.driver.swipe(x, int(y * 0.5), x, int(y * 0.3), duration=200)
            except InvalidElementStateException:
                print(f'swipe not performed start_position: ({x}, {y + 20}), end_position: ({x}, {y})')
        time.sleep(1)

    def _termination(self):
        return self.current_step >= self.max_steps

    def one_hot_encoding_activities(self):
        activity_observation = [0] * self.activities_number
        if self.current_activity in self.activities:
            index = self.activities.index(self.current_activity)
            activity_observation[index] = 1
        else:
            index = len(self.activities)
            activity_observation[index] = 1
            self.activities.append(self.current_activity)
        return activity_observation

    def one_hot_encoding_widgets(self):
        widget_observation = [0] * (self.OBSERVATION_SPACE - self.activities_number)
        for view in self.static_views:
            if view not in self.widget_list:
                self.widget_list[view] = len(self.widget_list)
            index = self.widget_list[view]
            widget_observation[index] = 1
        return widget_observation

    def _get_observation(self):
        observation_0 = self.one_hot_encoding_activities()
        observation_1 = self.one_hot_encoding_widgets()
        return {
            'observation': np.array(observation_0 + observation_1),
            'achieved_goal': np.array(observation_0 + observation_1),
            'desired_goal': np.array(observation_0 + observation_1),
            }

    def get_tuple_observation(self):
        return tuple(self.observation['observation'])

    def DOC(self):
        resource = init_resource(self.package)
        for i in range(self.exe_number):
            try:
                self.driver.orientation = 'LANDSCAPE' if self.driver.orientation == 'PORTRAIT' else 'PORTRAIT'
            except:
                time.sleep(1)
            time.sleep(3)
            try:
                self.driver.orientation = 'PORTRAIT' if self.driver.orientation == 'LANDSCAPE' else 'LANDSCAPE'
            except:
                time.sleep(1)
            time.sleep(2)
            append_resource(self.package, resource)
        judge_resource(resource)
        if resource['is_bug']:
            self.bug_report[self.current_activity + '_doc_' + ''.join(list(map(str, self.get_tuple_observation())))]\
                = [resource, time.time() - self.start_time]
        for bug in resource['is_bug']:
            self.weight[bug] += 1
        return resource['is_bug']

    def Edittext(self):
        text_boxes = self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")  # 查找所有文本框
        for text_box in text_boxes:
            resource = init_resource(self.package)
            for i in range(self.exe_number):
                text_box.click()  # 选中文本框
                current_string = ''.join(
                    random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
                    for _ in range(random.randint(5, 10)))
                text_box.send_keys(current_string)
                text_box.clear()
                append_resource(self.package, resource)
            judge_resource(resource)
            if resource['is_bug']:
                name = self.current_activity + '_text_' + self.return_attribute(text_box)
                if name not in self.bug_report:
                    self.bug_report[name] = [resource, time.time() - self.start_time]
                    for bug in resource['is_bug']:
                        self.weight[bug] += 1

    def home_return_operation(self):
        resource = init_resource(self.package)
        for i in range(self.exe_number):
            try:
                self.driver.press_keycode(3)
            except:
                pass
            time.sleep(2)
            try:
                self.driver.activate_app(self.package)
            except:
                pass
            time.sleep(2)
            append_resource(self.package, resource)
        judge_resource(resource)
        if resource['is_bug']:
            self.bug_report[self.current_activity + '_home_' + ''.join(list(map(str, self.get_tuple_observation())))] \
                = [resource, time.time() - self.start_time]
        for bug in resource['is_bug']:
            self.weight[bug] += 1

    def notification_operation(self):
        resource = init_resource(self.package)
        for i in range(self.exe_number):
            try:
                self.driver.open_notifications()
            except:
                pass
            time.sleep(2)
            try:
                self.driver.press_keycode(4)
            except:
                pass
            time.sleep(2)
            append_resource(self.package, resource)
        judge_resource(resource)
        if resource['is_bug']:
            self.bug_report[self.current_activity + '_notification_' + ''.join(list(map(str, self.get_tuple_observation())))] \
                = [resource, time.time() - self.start_time]
        for bug in resource['is_bug']:
            self.weight[bug] += 1

    def scroll_neutral(self):
        for current_view in self.views.values():
            if current_view['scrollable'] == 'true':
                bounds = re.findall(r'\d+', current_view['view'].get_attribute('bounds'))
                bounds = [int(i) for i in bounds]
                resource = init_resource(self.package)
                for i in range(self.exe_number):
                    self.scroll_action([0, 0], bounds)
                    time.sleep(2)
                    self.scroll_action([0, 1], bounds)
                    time.sleep(2)
                    append_resource(self.package, resource)
                judge_resource(resource)
                if resource['is_bug']:
                    self.bug_report[self.current_activity + '_scroll_' + ''.join(
                        list(map(str, self.get_tuple_observation())))] \
                        = [resource, time.time() - self.start_time]
                for bug in resource['is_bug']:
                    self.weight[bug] += 1

    def update_views(self):
        i = 0
        while i < 15:
            if self.current_activity == 'com.android.launcher3.uioverrides.QuickstepLauncher':
                try:
                    self._close()
                except:
                    pass
                self._start()
            try:
                self.get_all_views()
                break
            except Exception as e:
                i += 1
                if i >= 5:
                    print('Too Many times tried')
                    try:
                        self._close()
                    except:
                        pass
                    self._start()

    def get_all_views(self):
        page = self.driver.page_source
        tree = ET.fromstring(page)
        elements = tree.findall(".//*[@clickable='true']") + tree.findall(".//*[@scrollable='true']") + \
                   tree.findall(".//*[@long-clickable='true']")
        self.static_views = []
        self.views = {}
        tags = set([element.tag for element in elements])
        i = 0
        for tag in tags:
            elements = self.driver.find_elements(AppiumBy.CLASS_NAME, tag)
            for e in elements:
                clickable = e.get_attribute('clickable')
                scrollable = e.get_attribute('scrollable')
                long_clickable = e.get_attribute('long-clickable')
                if (clickable == 'true') or (scrollable == 'true') or (long_clickable == 'true'):
                    identifier = self.return_attribute(e)
                    self.views.update({i: {'view': e, 'identifier': identifier, 'class_name': tag,
                                           'clickable': clickable, 'scrollable': scrollable,
                                           'long-clickable': long_clickable}})
                    i += 1
                if tag == "android.widget.EditText":
                    self.views.update({i: {'view': e, 'identifier': self.return_attribute(e), 'class_name': tag,
                                           'clickable': clickable, 'scrollable': scrollable,
                                           'long-clickable': long_clickable}})
                self.static_views.append(self.return_attribute(e))
        self.views[i] = {'view': None, 'scrollable': False}
        self.observation = self._get_observation()

    def return_attribute(self, my_view):
        # Gets the unique identity of the element
        attribute_fields = ['resource-id', 'content-desc']
        attribute = None
        for attr in attribute_fields:
            try:
                attribute = my_view.get_attribute(attr)
                if attribute and attribute.strip() != "":
                    break
            except Exception as e:
                pass
        if attribute is None:
            attribute = f"{self.current_activity}.{my_view.get_attribute('class')}."
        return attribute

    def _close(self):
        try:
            self.driver.quit()
        except:
            pass

    def _start(self):
        i = 0
        while True:
            try:
                self.driver = webdriver.Remote('http://127.0.0.1:4723/wd/hub', self.desired_caps)
                time.sleep(5)
                break
            except Exception as e:
                try:
                    self._close()
                    time.sleep(2)
                except:
                    time.sleep(2)
            i += 1
        self.current_activity = get_current_activity()
        self.update_views()
        self.observation = self._get_observation()
        if i % 15 == 0:
            try:
                subprocess.Popen('adb shell reboot -p',
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
                time.sleep(30)
            except:
                pass
