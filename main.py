import csv
import os
import subprocess
import time
import json
import sys
from env.aut_env import AndroidAppEnv
from agent.Q import QLearningAgent
from apk.apk import install_apk, uninstall_app, apktool, component_extract


def run_adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_device_name():
    command = "adb devices"
    res = []
    result = run_adb_command(command).split('\n')
    for line in result:
        if "List" not in line:
            res.append(line.split()[0])
    return res


def get_android_version():
    command = "adb shell getprop ro.build.version.release"
    result = run_adb_command(command)
    return result


def run(al, app, package, main_activity, activities):
    global agent, env
    start_time = time.time()
    env = AndroidAppEnv(package, main_activity, 'resources', activities, android_version, devices_name[0],
                        ports[0], start_time, al.split('_')[-1])
    agent = QLearningAgent(env)
    agent.learn(start_time)
    if not os.path.exists('result'):
        os.mkdir('result')
    if not os.path.exists(f'result/{app}'):
        os.mkdir(f'result/{app}')
    with open(f'result/{app}/bug_report.json', 'w', encoding='utf-8') as json_file:
        json.dump(env.bug_report, json_file, ensure_ascii=False, indent=4)
    try:
        env.close()
    except:
        pass


def main():
    data = {k_apps: {k_als: [] for k_als in als} for k_apps in apps.keys()}
    for app, apk_path in apps.items():
        apktool(apk_path)
        install_apk(apk_path)
        package, Main_activity, activities = component_extract(
            f'{apk_path.split(".")[0]}/AndroidManifest.xml')
        for al in als:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {al} start")
            res = run(al, app, package, Main_activity, activities)
            data[app][al] = res
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {al} stop")
        uninstall_app(package)


if __name__ == '__main__':
    apps = {
        sys.argv[1]: sys.argv[2]
    }
    als = ['q_res_weight']
    android_version = get_android_version()
    if len(sys.argv) == 4 and sys.argv[3] != 'none':
        devices_name = [sys.argv[3]]
    else:
        devices_name = get_device_name()
    if len(sys.argv) == 5:
        ports = [sys.argv[4]]
    else:
        ports = ['4723']
    main()
