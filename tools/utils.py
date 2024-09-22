import threading
import time
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageEnhance

def check_date_fmt(date_str):
    formats = {
        "%Y/%m/%d %p%I:%M": "Ymd",
        "%m/%d/%Y %I:%M %p": "mdY"
    }
    for fmt, fmt_name in formats.items():
        try:
            datetime.strptime(date_str, fmt)
            return fmt_name
        except ValueError:
            continue
    return 0

def get_d_time(date: str) -> str:
    if date.split(" ")[1][:2] == "下午":
        date = date.replace("下午", "PM")
    else:
        date = date.replace("上午", "AM")

    data_fmt = check_date_fmt(date)

    if data_fmt == "Ymd":
        # windows
        date_obj = datetime.strptime(date, "%Y/%m/%d %p%I:%M")
    elif data_fmt == "mdY":
        # linux
        date_obj = datetime.strptime(date, "%m/%d/%Y %I:%M %p")
    else:
        raise ValueError("Invalid date format")

    timestamp = int(date_obj.timestamp())

    d_time = time.time() - timestamp
    if d_time < 60:
        date = f"{int(d_time)}s"
    elif d_time < 3600:
        date = f"{int(d_time // 60)}m"
    elif d_time < 86400:
        date = f"{int(d_time // 3600)}h"
    else:
        date = f"{int(d_time // 86400)}d"

    return date


def adjust_opacity(image, opacity):
    """
    調整圖片的透明度
    :param image: 原始圖片
    :param opacity: 透明度 (0.0 - 1.0)
    :return: 調整透明度後的圖片
    """
    alpha = image.split()[3]  # 提取 alpha 通道
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)  # 調整透明度
    image.putalpha(alpha)  # 將調整後的 alpha 通道應用回圖片
    return image


def get_potential(score: str, song_lv: float) -> float:
    score = int(score.replace(",", ""))
    if score >= 10000000:
        return song_lv + 2
    elif score >= 9800000:
        return round(song_lv + 1 + (score - 9800000) / 200000, 3)
    elif score < 9800000:
        return max(round(song_lv + (score - 9500000) / 300000, 3), 0)


def get_grade(score: int) -> str:
    score = int(score.replace(",", ""))
    if score >= 9900000:
        return "EX+"
    elif score >= 9800000:
        return "EX"
    elif score >= 9500000:
        return "AA"
    elif score >= 9200000:
        return "A"
    elif score >= 8900000:
        return "B"
    elif score >= 8600000:
        return "C"
    else:
        return "D"


def download_image(url, img_container, key, save_path=None):
    try:
        response = requests.get(url)
        response.raise_for_status()  # 如果狀態碼不是 200，這行會拋出 HTTPError

        img = Image.open(BytesIO(response.content))
        if save_path:
            img.save(save_path)
        img_container[key] = img

    except requests.exceptions.RequestException:
        pass


def download_images_multithreaded(img_download_queue, img_container):
    threads = []
    for idx, img_url, save_path in img_download_queue:
        thread = threading.Thread(
            target=download_image, args=(img_url, img_container, idx, save_path)
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


def parse_cookies(cookie_string, domain=".example.com"):
    cookies = []
    for cookie in cookie_string.split("; "):
        name, value = cookie.split("=", 1)
        cookies.append({"name": name, "value": value, "domain": domain})
    return cookies


def textsize(text, font):
    im = Image.new(mode="P", size=(0, 0))
    draw = ImageDraw.Draw(im)
    _, _, width, height = draw.textbbox((0, 0), text=text, font=font)
    return width, height


def get_rating_img_path(ppt: float) -> str:
    if ppt >= 13:
        return "rating_7.png"
    elif ppt >= 12.5:
        return "rating_6.png"
    elif ppt >= 12:
        return "rating_5.png"
    elif ppt >= 11:
        return "rating_4.png"
    elif ppt >= 10:
        return "rating_3.png"
    elif ppt >= 7:
        return "rating_2.png"
    elif ppt >= 3.5:
        return "rating_1.png"
    elif ppt >= 0:
        return "rating_0.png"
    else:
        raise ValueError("Invalid ppt value")


def adaptive_resize(img, size):
    if size[0] == "*":
        ratio = size[1] / img.height
        new_width = img.width * ratio
        new_height = img.height * ratio
    elif size[1] == "*":
        ratio = size[0] / img.width
        new_width = img.width * ratio
        new_height = img.height * ratio
    else:
        new_width, new_height = size
    img = img.resize((int(new_width), int(new_height)))
    return img
