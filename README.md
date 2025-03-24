## Environment
python 3.7
windows 11

## Precondition
Before you use AgeBot, make sure you have turned on an Android emulator/real Android device 
with root privileges and communicate with Appium.

## Command

You can use the AgeBot with the following command:

**python main.py app_name apk_path [device_name] [appium_port]**

app_name indicates the name of the application. 
apk_path indicates the path where the application apk resides.
device_name is the name of the device. 
appium_port is the listening port of the appium you are using.
device_name can be empty, in which case AgeBot will automatically identify the currently available devices. 
appium_port The default value is 4723.

## Result

After two hours, bug_report will be generated in the result/app_name folder. 
It describes activities or views with aging defects, corresponding neutral sequences, 
and resources that continue to rise
