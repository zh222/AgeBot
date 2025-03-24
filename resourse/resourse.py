import re
import subprocess
import numpy as np
from scipy.stats import linregress
R = {
    "object",
    "java heap",
    "native heap",
    "fd number",
    "db number",
    "wake lock number",
    "camera number",
    "location listener number",
    "media number",
    "sensor number",
    "socket number",
    "wifi number",
    "cpu",
    "rss",
}


def run_adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def linear_regression_analysis(series):
    x = np.arange(len(series))
    slope, intercept, r_value, p_value, std_err = linregress(x, series)
    return slope, p_value, r_value


def analyze_resources(resources):
    flag = []
    for resource, value in resources.items():
        slope, p_value, r_value = linear_regression_analysis(value)
        resources[resource] = {
            'value': value,
            'slope': slope,
            'p_value': p_value,
            'r_value': r_value,
            'is_bug': bool(slope > 0 and p_value < 0.05)
        }
        if resources[resource]['is_bug']:
            flag.append(resource)
    resources['is_bug'] = flag


def get_pid(package_name, device_name=None):
    if not device_name:
        command = f'adb shell ps | findstr {package_name}'
    else:
        command = f'adb -s {device_name} shell ps | findstr {package_name}'
    try:
        result = run_adb_command(command).split()
        if len(result) > 1:
            return result[1]
        else:
            return ''
    except:
        return ''


def get_object_counts(package_name, device_name=None):
    object_types = [
        "Views",
        "ViewRootImpl",
        "AppContexts",
        "Activities",
        "Assets",
        "AssetManagers",
        "Local Binders",
        "Proxy Binders",
        "Parcel memory",
        "Parcel count",
        "Death Recipients",
        "OpenSSL Sockets",
        "WebViews",
    ]
    if not device_name:
        proc = subprocess.Popen("adb shell dumpsys meminfo " + package_name,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    else:
        proc = subprocess.Popen(f"adb -s {device_name} shell dumpsys meminfo " + package_name,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    memoryInfo, errInfo = proc.communicate()
    object_counts = {}
    for obj_type in object_types:
        match = re.search(rf'{obj_type}:\s+(\d+)', memoryInfo.decode())
        if match:
            object_counts[obj_type] = int(match.group(1))
        else:
            object_counts[obj_type] = 0
    return object_counts


def get_java_heap(package_name, device_name=None):
    if not device_name:
        command = f'adb shell dumpsys meminfo {package_name} | findstr /c:"Java Heap"'
    else:
        command = f'adb -s {device_name} shell dumpsys meminfo {package_name} | findstr /c:"Java Heap"'
    result = run_adb_command(command)
    if result:
        return int(result.split()[-2])
    return 0


def get_native_heap(package_name, device_name=None):
    if not device_name:
        command = f'adb shell dumpsys meminfo {package_name} | findstr /c:"Native Heap"'
    else:
        command = f'adb -s {device_name} shell dumpsys meminfo {package_name} | findstr /c:"Native Heap"'
    result = run_adb_command(command)
    if result:
        return int(result.split('\n')[-1].split()[-2])
    return 0


def get_rss(package_name, device_name=None):
    if not device_name:
        command = f'adb shell dumpsys meminfo {package_name}'
    else:
        command = f'adb -s {device_name} shell dumpsys meminfo {package_name}'
    result = run_adb_command(command)
    match = re.search(r"TOTAL RSS:\s*(\d+)", result)
    if match:
        return int(match.group(1))
    return 0


def get_cpu(package_name, device_name=None):
    total_cpu = 0.0
    pid = get_pid(package_name, device_name)
    if pid == '':
        return total_cpu
    if not device_name:
        command = f'adb shell top -p {pid} -n 1'
    else:
        command = f'adb -s {device_name} shell top -p {pid} -n -1'
    result = run_adb_command(command).split('\n')
    for r in result:
        if "user" in r:
            items = r.split(" ")
            for item in items:
                if "user" in item:
                    parts = item.split("%")
                    return int(parts[0])
    return total_cpu


def get_fd_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != '':
        if not device_name:
            command = f'adb shell ls -l /proc/{pid}/fd | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell ls -l /proc/{pid}/fd | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_database_number(package_name, device_name=None):
    if not device_name:
        command = f'adb shell lsof | findstr {package_name} | findstr .db | find /v /c ""'
    else:
        command = f'adb -s {device_name} shell lsof | findstr {package_name} | findstr .db | find /v /c ""'
    result = run_adb_command(command)
    return int(result)


def get_wake_lock_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != '':
        if not device_name:
            command = f'adb shell dumpsys power | findstr {pid} | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell dumpsys power | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_socket_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != "":
        if not device_name:
            command = f'adb shell lsof | findstr {pid} | findstr socket | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell lsof | findstr {pid} | findstr socket | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_resource(package_name):
    resources = get_object_counts(package_name) if "object" in R else {}
    if "java heap" in R:
        resources["java heap"] = get_java_heap(package_name)
    if "native heap" in R:
        resources["native heap"] = get_native_heap(package_name)
    if "fd number" in R:
        resources["fd number"] = get_fd_number(package_name)
    if "db number" in R:
        resources["db number"] = get_database_number(package_name)
    if "wake lock number" in R:
        resources["wake lock number"] = get_wake_lock_number(package_name)
    if "socket number" in R:
        resources["socket number"] = get_socket_number(package_name)
    if "cpu" in R:
        resources["cpu"] = get_cpu(package_name)
    if "rss" in R:
        resources["rss"] = get_rss(package_name)
    for k, v in resources.items():
        if v == 0:
            resources[k] = 1
    return resources


def compute_resource_sensitivitis(resource1, resource2, resource_type_weight):
    reward = 0
    for key, value in resource1.items():
        reward += resource_type_weight[key] * (resource2[key] - resource1[key]) / value
    return 1000 * reward


def init_resource(package_name):
    gc(package_name)
    resources = get_resource(package_name)
    for k, v in resources.items():
        resources[k] = [v]
    return resources


def append_resource(package_name, pre_resource):
    gc(package_name)
    resources = get_resource(package_name)
    for k, v in resources.items():
        pre_resource[k].append(v)


def judge_resource(resources):
    analyze_resources(resources)


def gc(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid == '':
        return
    if not device_name:
        command = f'adb shell kill -10 {pid}'
    else:
        command = f'adb -s {device_name} shell kill -10 {pid}'
    run_adb_command(command)
