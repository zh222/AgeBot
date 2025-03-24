import csv
import os
import subprocess
import time
import json
from env.aut_env import AndroidAppEnv
from agent.Q import QLearningAgent
from agent.Random import RandomAgent
from apk.apk import install_apk, uninstall_app, apktool, component_extract
from agent.sac import learn


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
    all_res = []
    for i in (0, 2):  # 每种实验配置执行5次,
        start_time = time.time()
        if al.startswith('q_res'):
            env = AndroidAppEnv(package, main_activity, 'resources', activities, android_version, devices_name[0],
                                ports[0], start_time, al.split('_')[-1])
            agent = QLearningAgent(env)
            agent.learn(start_time)
        elif al.startswith('q_res_all'):
            env = AndroidAppEnv(package, main_activity, 'resources', activities, android_version, devices_name[0],
                                ports[0], start_time, al.split('_')[-1])
            agent = QLearningAgent(env)
            agent.learn(start_time)
        elif al.startswith('q_res_weight'):
            env = AndroidAppEnv(package, main_activity, 'resources', activities, android_version, devices_name[0],
                                ports[0], start_time, al.split('_')[-1])
            agent = QLearningAgent(env)
            agent.learn(start_time)
        elif al == 'q_cov':
            env = AndroidAppEnv(package, main_activity, 'cov', activities, android_version, devices_name[0],
                                ports[0], start_time, al.split('_')[-1])
            agent = QLearningAgent(env)
            agent.learn(start_time)
        elif al == 'random':
            env = AndroidAppEnv(package, main_activity, 'cov', activities, android_version, devices_name[0],
                                ports[0], start_time, al.split('_')[-1])
            agent = RandomAgent(env)
            agent.learn(start_time)
        elif al == 'sac':
            env = AndroidAppEnv(package, main_activity, 'resources', activities, android_version, devices_name[0],
                                ports[0], start_time, al.split('_')[-1])
            learn(env, start_time)
        all_res.append([len(env.bug_report), len(env.list_activities), len(env.state)])
        if not os.path.exists('result'):
            os.mkdir('result')
        if not os.path.exists(f'result/{app}'):
            os.mkdir(f'result/{app}')
        if not os.path.exists(f'result/{app}/{i + 1}'):
            os.mkdir(f'result/{app}/{i + 1}')
        # agent.save(f"result/{app}/{al}")
        with open(f'result/{app}/{i + 1}/{al}_bug_report.json', 'w', encoding='utf-8') as json_file:
            json.dump(env.bug_report, json_file, ensure_ascii=False, indent=4)
        with open(f'result/{app}/{i + 1}/{al}_activities.csv', 'w', newline='', encoding='utf-8') as f:
            csv_writer = csv.writer(f)
            for activity in env.list_activities:
                csv_writer.writerow([activity])
        with open(f'result/{app}/{i + 1}/{al}_states.csv', 'w', newline='', encoding='utf-8') as f:
            csv_writer = csv.writer(f)
            for state in env.state:
                csv_writer.writerow([state])
        with open(f'result/{app}/{i + 1}/{al}_coverage.csv', 'w', newline='', encoding='utf-8') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(['bugs', f'activities/{len(activities)}', 'states'])
            csv_writer.writerow([len(env.bug_report), len(env.list_activities), len(env.state)])
        with open(f'result/{app}/{i + 1}/{al}_epi.csv', 'w', newline='', encoding='utf-8') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow([env.epi])
        with open(f'result/{app}/{i + 1}/{al}_state_time.csv', 'w', newline='', encoding='utf-8') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(['activity_state', 'time', 'is_bug', 'resource'])
            for activity, value in env.list_activities.items():
                if activity:
                    for state in value:
                        csv_writer.writerow([activity + '_' + ''.join(map(str, state[0])), state[1], state[2], state[3]])
        with open(f'result/{app}/{i + 1}/{al}_state_resource.json', 'w', encoding='utf-8') as json_file:
            json.dump(env.collect_resource, json_file, ensure_ascii=False, indent=4)
        # with open(f'result/{app}/{i + 1}/{al}_q_table.json', 'w', encoding='utf-8') as json_file:
        #     json.dump(agent.q_table, json_file, ensure_ascii=False, indent=4)
        try:
            env.close()
        except:
            pass
    return all_res


def main():
    data = {k_apps: {k_als: [] for k_als in als} for k_apps in apps.keys()}
    for app, apk_path in apps.items():
        apktool(apk_path)
        install_apk(apk_path)
        package, Main_activity, activities = component_extract(
            f'{apk_path.split(".")[0]}/AndroidManifest.xml')
        if package == 'app.michaelwuensch.bitbanana':
            Main_activity = "app.michaelwuensch.bitbanana.LauncherActivity"
        elif package == 'org.totschnig.myexpenses':
            Main_activity = "org.totschnig.myexpenses.activity.SplashActivity"
        for al in als:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {al} start")
            res = run(al, app, package, Main_activity, activities)
            data[app][al] = res
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {al} stop")
        uninstall_app(package)


if __name__ == '__main__':
    als = [
        # "q_res_weight",
        # "q_cov",
        "random",
        # "sac",
    ]
    apps = {
        # "keepassDroid": "apk/middle/keepassDroid_25133.apk",
        # "k9mail": "apk/high/k9mail_162720.apk",
        # "newpipe": "apk/high/newpipe_57363.apk",
        # "RunnerUp": "apk/middle/RunnerUp_30729.apk",
        # "money_manager_ex": "apk/middle/money_manager_ex_41537.apk",
        # "myexpenses": "apk/high/myexpenses_137437.apk",
        # "redreader": "apk/high/redreader_62750.apk",
        # "taz": "apk/middle/taz_43892.apk",
        # "AntennaPod": "apk/middle/AntennaPod_23793.apk",
        # "butterfly": "apk/low/butterfly_6043.apk",
        # "selfprivacy": "apk/low/selfprivacy_6043.apk",
        # "KitchenOwl": "apk/low/KitchenOwl_9664.apk",
        # "neurolab": "apk/low/neurolab_8284.apk",
        # "souvenirs": "apk/low/souvenirs_9206.apk",
        # "tunner": "apk/low/tuner_3690.apk",
        "bitbanana": "apk/middle/bitbanana_39794.apk",

        # "Gadgetbridge": "apk/high/Gadgetbridge_221736.apk",
        # "Easter_Eggs": "apk/middle/Easter_Eggs_32771.apk",
        # "News_Reader": "apk/low/News_Reader_7358.apk",
        # "Activity_Manager": "apk/low/Activity_Manager_7383.apk",
    }
    android_version = "11"
    devices_name = get_device_name()
    ports = [
        '4723',
    ]
    main()
    # jjj = {key:{} for key in apps.keys()}
    # for app, apk_path in apps.items():
    #     apktool(apk_path)
    #     package, Main_activity, activities = component_extract(
    #         f'{apk_path.split(".")[0]}/AndroidManifest.xml')
    #     jjj[app]["package"] = package
    #     jjj[app]["Main_activity"] = Main_activity
    #     jjj[app]["activities"] = activities
    # with open(f'apps.json', 'w', encoding='utf-8') as json_file:
    #     json.dump(jjj, json_file, ensure_ascii=False, indent=4)
