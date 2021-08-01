import os, sys, yaml, glob, time
from cv2 import cv2
from PIL import Image
from PIL import ImageStat
import screen_brightness_control as sbc
from threading import Thread, Lock
sys.path.append(os.path.abspath('.'))
from icons.SysTrayIcon import SysTrayIcon


lock = Lock()

mtime_cur = 0
mtime_old = 0

brightness_cur = sbc.get_brightness()
brightness_old = brightness_cur

cfg = {
    'pause_flag': False,
    'debug_flag': False,
    'sleep_time': 10,
}

exit_flag = False
update_flag = False


#把时间戳转化为时间: 1479264792 to 2016-11-16 10:53:12
def TimeStampToTime(timestamp):
    timeStruct = time.localtime(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S',timeStruct)


#获取文件的修改时间
def getFileModifyTime(filePath):
    t = os.path.getmtime(filePath)
    return TimeStampToTime(t)


def updateConfig(yaml_file='./config.yml'):
    global cfg

    with open(yaml_file, 'r', encoding='utf-8') as f_obj:
        cfg_new = yaml.safe_load(f_obj.read())
        cfg['pause_flag'] = cfg_new.get('pause_flag', cfg['pause_flag'])
        cfg['debug_flag'] = cfg_new.get('debug_flag', cfg['debug_flag'])
        cfg['sleep_time'] = cfg_new.get('sleep_time', cfg['sleep_time'])


def dumpConfig(yaml_file='./config.yml'):
    global cfg

    with open(yaml_file, 'w', encoding='utf-8') as f_obj:
        yaml.safe_dump(cfg, f_obj)


def getBrightness():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    # 读取视频片段
    flag, frame = cap.read()
    if flag == False:
        return sbc.get_brightness()

    # 灰度处理
    gray = cv2.cvtColor(frame, code=cv2.COLOR_BGR2GRAY)
    # 平均亮度
    im=Image.fromarray(gray)
    stat=ImageStat.Stat(im)
    brightness = int(stat.rms[0]*100/255)

    cap.release()
    
    return brightness


def checkConfig(sign=True):
    global mtime_cur, mtime_old, cfg, exit_flag, update_flag

    while True:
        currentpath = os.path.abspath('.')
        yamlpath = glob.glob(os.path.join(currentpath,'*.yml'))

        if yamlpath:
            mtime_old = mtime_cur
            mtime_cur = getFileModifyTime(yamlpath[0])
            if mtime_cur != mtime_old:
                lock.acquire()
                updateConfig(yamlpath[0])
                update_flag = True
                lock.release()

                if cfg['debug_flag']:
                    print(cfg)

        if exit_flag or not sign:
            return


def main():
    global brightness_cur, brightness_old, cfg, exit_flag, update_flag

    while True:
        if not cfg['pause_flag']:
            brightness_cur = getBrightness()

            change = brightness_cur - brightness_old
            if abs(change) < 20:
                tmp = brightness_cur
            else:
                if change > 0:
                    tmp = brightness_old + 20
                    if tmp > 100:
                        tmp = 100
                else:
                    tmp = brightness_old - 20
                    if tmp < 0:
                        tmp = 0
            sbc.set_brightness(tmp)
            brightness_old = tmp

            if cfg['debug_flag']:
                print(f'brightness: {brightness_cur}\nbrightness_old: {brightness_old}\nchange: {tmp}')
                print('#'*20)

            for i in range(cfg['sleep_time']):
                if exit_flag:
                    return
                if update_flag:
                    update_flag = False
                    break
                time.sleep(1)


def trayIcon():
    global cfg, exit_flag

    hover_text = "Automatic Brightness"
    running_icon = os.path.join('./icons','running.ico')
    stopping_icon = os.path.join('./icons','stopping.ico')

    def switchStatus(sysTrayIcon):
        global cfg
        nonlocal stopping_icon, running_icon

        currentpath = os.path.abspath('.')
        yamlpath = glob.glob(os.path.join(currentpath,'*.yml'))

        if sysTrayIcon.icon is running_icon:
            sysTrayIcon.icon = stopping_icon
            flag = True
        else:
            sysTrayIcon.icon = running_icon
            flag = False

        lock.acquire()
        if yamlpath:
            updateConfig(yamlpath[0])
            cfg['pause_flag'] = flag
            dumpConfig(yamlpath[0])
        else:
            cfg['pause_flag'] = flag
            dumpConfig()
        lock.release()

        sysTrayIcon.refresh_icon()

    def set_sleep_time(interval):
        def set_interval(sysTrayIcon):
            global cfg

            currentpath = os.path.abspath('.')
            yamlpath = glob.glob(os.path.join(currentpath,'*.yml'))

            lock.acquire()
            if yamlpath:
                updateConfig(yamlpath[0])
                cfg['sleep_time'] = interval
                dumpConfig(yamlpath[0])
            else:
                cfg['sleep_time'] = interval
                dumpConfig()
            lock.release()

        return set_interval

    menu_options = (('Pause / Continue', None, switchStatus),
                    ('Interval', None, (('1', None, set_sleep_time(1)),
                                        ('5', None, set_sleep_time(5)),
                                        ('10', None, set_sleep_time(10)),
                                        ('20', None, set_sleep_time(20)),
                                        ('30', None, set_sleep_time(30)),
                                        ('60', None, set_sleep_time(60)),
                                        ('120', None, set_sleep_time(120)),
                                        ('300', None, set_sleep_time(300)),
                                        ))
                   )

    def quit(sysTrayIcon):
        global exit_flag
        exit_flag = True

    SysTrayIcon(stopping_icon if cfg['pause_flag'] else running_icon, hover_text, menu_options, left_double_click=switchStatus, on_quit=quit, default_menu_index=1)


if __name__ == '__main__':
    checkConfig(False)

    tasks = [
        Thread(target=checkConfig),
        Thread(target=trayIcon),
    ]

    for task in tasks:
        task.start()

    main()
    