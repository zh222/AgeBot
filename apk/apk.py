import subprocess
import xml.etree.ElementTree as ET


def run_adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def install_apk(apk_path):
    command = f'adb install {apk_path}'
    result = run_adb_command(command)
    assert 'Success' in result, "Failed to install APK"


def uninstall_app(package_name):
    command = f'adb uninstall {package_name}'
    result = run_adb_command(command)
    assert 'Success' in result, "Failed to uninstall APK"


def apktool(apk_path):
    print('start apktool')
    command = f'apk\\apktool d {apk_path} -o {apk_path.split(".")[0]}'
    result = run_adb_command(command)
    if result != '':
        print("Apktool successfully.")
    else:
        print(f"Apktool failed: {result}")


def xml_to_dict(element):
    node_dict = {}
    for child in element:
        child_dict = xml_to_dict(child)
        if child.tag not in node_dict:
            node_dict[child.tag] = child_dict
        else:
            if not isinstance(node_dict[child.tag], list):
                node_dict[child.tag] = [node_dict[child.tag]]
            node_dict[child.tag].append(child_dict)
    if element.attrib:
        node_dict["@attributes"] = element.attrib
    if element.text and element.text.strip():
        node_dict["@text"] = element.text.strip()

    return node_dict or None


def parse_xml_to_dict(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    return {root.tag: xml_to_dict(root)}


def component_extract(xml_file):
    xml = parse_xml_to_dict(xml_file)
    activities = []
    Main_activity = ''
    if isinstance(xml['manifest']['application']['activity'], list):
        for activity in xml['manifest']['application']['activity']:

            activities.append(activity['@attributes']['{http://schemas.android.com/apk/res/android}name'])
            if 'android.intent.action.MAIN' in str(activity):
                Main_activity = activities[-1]

    else:
        for activity in xml['manifest']['application']['activity'].keys():
            try:
                activities.append(activity['@attributes']['{http://schemas.android.com/apk/res/android}name'])
                if 'android.intent.action.MAIN' in str(activity):
                    Main_activity = activities[-1]
            except:
                pass
    package = xml['manifest']['@attributes']['package']
    return package, Main_activity, activities
