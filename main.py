import os
import random
import time
from datetime import datetime

import bs4
import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from tools.draw_tools import draw_text_with_edge, draw_text_with_shadow
from tools.utils import (
    adaptive_resize,
    download_image,
    download_images_multithreaded,
    get_d_time,
    get_potential,
    get_rating_img_path,
    textsize,
)


class B30Render:
    def __init__(self,  
                 COVER_IMG_DIR='src/cover_img',    
                 BG_IMG_DIR='src/bg_img', 
                 FONT_DIR='src/font', 
                 DIFF_IMG_DIR='src/diff_img',
                 LAYOUT_IMG_DIR='src/layout_img',
                 RATING_IMG_DIR='src/rating_img',
                 BANNER_IMG_DIR='src/banner_img',
                 ):

        self.COVER_IMG_DIR = COVER_IMG_DIR
        self.RATING_IMG_DIR = RATING_IMG_DIR
        self.FONT_DIR = FONT_DIR    
        self.BANNER_IMG_DIR = BANNER_IMG_DIR

        self.final_result = []
        self.img_src_arr = []
        self.img_download_queue = []
        self.img_container = {}
        self.username = 'User001'

        # 成績資訊欄位
        self.columns = { 
            2 : 'difficulty', 
            4 : 'title',
            6 : 'artist',
            7 : 'grade',
            8 : 'score',
            11 : 'date',
            13 : 'P',
            15 : 'F',
            17 : 'L',
            }
        
        self.score_data = pd.DataFrame(columns=self.columns.values())
        self.song_data = ''

        # bg 資訊初始化
        self.box_width, self.box_height = 290, 170
        self.start_x, self.start_y = 30, 30
        self.padding = 30
        self.box_color = (100, 100, 100)

        self.img_width, self.img_height = 2150, self.padding * 7 + self.box_height * 6
        self.image = Image.new('RGB', (self.img_width, self.img_height), color=(128, 128, 128))
        self.draw = ImageDraw.Draw(self.image)

        # 字體初始化
        self.font_path = f'{FONT_DIR}/Exo-SemiBold.ttf'  
        self.font_dict = {
            'title': ImageFont.truetype(self.font_path, 26),
            'score': ImageFont.truetype(self.font_path, 30),
            'text': ImageFont.truetype(self.font_path, 22),
            'date': ImageFont.truetype(self.font_path, 24),
            'ptt_dec': ImageFont.truetype(self.font_path, 40),
            'ptt_fixed': ImageFont.truetype(self.font_path, 30),
            'p_name': ImageFont.truetype(self.font_path, 50),
        }

        # 難度tag初始化
        self.diff_tag_img_dict = {
            'PST': Image.open(f'{DIFF_IMG_DIR}/PST.png'),
            'PRS': Image.open(f'{DIFF_IMG_DIR}/PRS.png'),
            'FTR': Image.open(f'{DIFF_IMG_DIR}/FTR.png'),
            'BYD': Image.open(f'{DIFF_IMG_DIR}/BYD.png'),
            'ETR': Image.open(f'{DIFF_IMG_DIR}/ETR.png'),
        }
        
        self.shadow_color = (0, 0, 0) 
        self.shadow_margin = 17
        self.shadow_blur_radius = 5
        self.shadow_layer = Image.new('RGBA', (self.box_width + self.shadow_margin * 2, 
                                               self.box_height + self.shadow_margin * 2,), 
                                               (0, 0, 0, 1))

        self.shadow_draw = ImageDraw.Draw(self.shadow_layer)

        self.bg_img = Image.open(f'{BG_IMG_DIR}/{random.choice(os.listdir(BG_IMG_DIR))}')
        self.bg_mask = Image.open(f'{LAYOUT_IMG_DIR}/bg_mask.png')

        self.side_img = Image.open(f'{LAYOUT_IMG_DIR}/side2.png')
 
        self.side_img_shadow = Image.open(f'{LAYOUT_IMG_DIR}/side_shadow.png')
        
        
        self.chrome_options = Options()
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
        chrome_args = [
            "--headless",
            "--disable-gpu",
            "--window-size=1920x1080",
            "--log-level=3",
            # 目前 chrome headless bug，會跳出空白視窗，所以設定視窗位置到螢幕外
            "--window-position=-2400,-2400",
            f"--user-agent={self.user_agent}",
        ]
            
        self.add_chrome_args(chrome_args)
        # cookie_str = ''
        # cookies = parse_cookies(cookie_str, domain='.lowiro.com')

        # 生成日期
        
        self.gen_date = datetime.now().strftime("%Y/%m/%d")
    
    def add_chrome_args(self, args):
        for arg in args:
            self.chrome_options.add_argument(arg)

    def get_userkey(self):
        with open('user.txt', 'r') as f:
            data = f.readlines()
            username_input = data[0].strip()
            password_input = data[1].strip()

        return username_input, password_input
    
    def load_song_data(self, score_titles):
        if not os.path.exists('src/arcaea_song_level.csv'):
            print('Creating song data...')
            self.get_song_data()
        
        data = pd.read_csv('src/arcaea_song_level.csv')
        if not self.check_all_song_exist(data, score_titles):
            print('Updating song data...')
            self.get_song_data()
            return pd.read_csv('src/arcaea_song_level.csv')

        return data
    
    def check_all_song_exist(self, song_data, score_titles):
        for title in score_titles:
            if title not in song_data['title'].values:
                return False
        return True
    
    def get_song_data(self):
        # 爬取定數表
        headers = {'User-Agent': self.user_agent}

        def fetch_page(url):
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()  
                return response
            except requests.exceptions.RequestException as e:
                return f"Error: {e}"

        page_content = fetch_page('https://arcwiki.mcd.blue/%E5%AE%9A%E6%95%B0%E8%AF%A6%E8%A1%A8')

        soup = bs4.BeautifulSoup(page_content.text, 'html.parser')
        tbody = soup.find('tbody')
        songs_info = tbody.find_all('tr')

        songs_info_df = pd.DataFrame(columns=['title', 'PST', 'PRS', 'FTR', 'BYD', 'ETR'])

        for idx, song_info in enumerate(songs_info[1:]):
            song_info = song_info.text.split('\n')[1:7]
        
            songs_info_df.loc[idx] = song_info
            
        
        songs_info_df.to_csv('src/arcaea_song_level.csv', index=False)

    def get_ptt_page_online(self):

        final_result = []

        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.chrome_options)

            driver.get("https://arcaea.lowiro.com/zh/profile/potential")
            time.sleep(2)

            # for cookie in cookies:
            #     driver.add_cookie(cookie)

            username_input, password_input = self.get_userkey()
                
            username = driver.find_element(By.CSS_SELECTOR, "input[name='user']")
            password = driver.find_element(By.CSS_SELECTOR, "input[name='password']")

            username.send_keys(username_input)
            password.send_keys(password_input)

            driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()

            # driver.refresh()

            time.sleep(3)

            if '登入失败' in driver.page_source:
                print('login failed, please check your username and password again')
                return 'err'
            

            # 獲取頁面資訊
            results = driver.find_elements(By.CSS_SELECTOR, "div[data-v-337fbd7d].card-list div[data-v-337fbd7d].card")
            for result in results:
                final_result.append(result.text)

            img_results = driver.find_elements(By.CSS_SELECTOR, "div[data-v-337fbd7d].card-list div[data-v-337fbd7d].card div[data-v-3d1a04fb].section-2 img")
            self.username = driver.find_element(By.CSS_SELECTOR, "span[class='username']").text

            avatar_url = driver.find_element(By.CSS_SELECTOR, "div[data-v-f7bc1a70].profile-image").get_attribute('style').split('\"')[1]
            rating_bg_url = driver.find_element(By.CSS_SELECTOR, "div[data-v-f7bc1a70].profile-image div[data-v-f7bc1a70]").get_attribute('style').split('\"')[1]
            download_image(avatar_url, self.img_container, 'avatar')
            download_image(rating_bg_url, self.img_container, 'rating_bg')

            self.img_src_arr = [img.get_attribute('src') for img in img_results]

            # 下載名牌背景

            driver.get("https://arcaea.lowiro.com/zh/profile/")
            time.sleep(2)
            banner_url = driver.find_element(By.CSS_SELECTOR, "img[class='profile-banner__banner']").get_attribute('src')

            download_image(banner_url, self.img_container, 'banner')

        except Exception as e:
            print(f'Error: {e}')
            return 0
        
        finally:
            # 關閉瀏覽器
            driver.quit()
            print('browser closed')

        for idx, result in enumerate(final_result):
            result = result.split('\n')
            row_data = {value: result[key] for key, value in self.columns.items()}
            self.score_data.loc[idx] = row_data
        
        # 儲存成績資料
        self.score_data.to_csv(f"src/score_{self.gen_date.replace('/', '')}.csv", index=False)
        self.song_data = self.load_song_data(self.score_data['title'].values)

        return 0

    def get_ptt_page_offline(self, file_path):
        self.score_data = pd.read_csv(file_path)

        self.song_data = self.load_song_data(self.score_data['title'].values)
    
    def get_avg_ptt(self, type='B30'):
        
        if type == 'B30':
            data = self.score_data[:30]
            n = 30
        elif type == 'R10':
            data = self.score_data[-10:]
            n = 10
        else:
            raise ValueError('type must be B30 or R10')
        
        single_ptt = 0
        for _, row in data.iterrows():
            song_lv = self.song_data[self.song_data['title'] == row['title']][row['difficulty']].values[0]
            single_ptt = single_ptt + get_potential(row['score'], song_lv)

        return round(single_ptt / n, 3)
    
    def get_cover_img(self):
        cnt = 0
        for idx, title in enumerate(self.score_data['title']):
            
            if not os.path.exists(f'{self.COVER_IMG_DIR}/{title}.jpg'):
                # 如果封面圖未下載過，加入下載佇列並讀取
                if not self.img_src_arr:
                    raise ValueError('must use online mode to get img source')
                
                cnt += 1
                self.img_download_queue.append([idx, self.img_src_arr[idx], f"{self.COVER_IMG_DIR}/{title}.jpg"])
            else:
                # 直接讀取封面圖
                cover_img = Image.open(f'{self.COVER_IMG_DIR}/{title}.jpg')        
                self.img_container[idx] = cover_img

        download_images_multithreaded(self.img_download_queue, self.img_container)
        print(f'downloaded {cnt} cover images')

    def draw_banner(
                self,
                coord: tuple, 
                ptt: float, 
                name='User',
                ) -> None:
 
        # ptt = 0
        # 繪製名牌背景
        if 'banner' in self.img_container.keys():
            banner_bg = self.img_container['banner']
        else:
            banner_bg = Image.open(os.path.join(f'{self.BANNER_IMG_DIR}', '1.png'))

        banner_bg = adaptive_resize(banner_bg, (700, '*'))

        banner_bg = banner_bg.crop((0, 0, banner_bg.width - 270, banner_bg.height))
        self.image.paste(banner_bg, (self.img_width - banner_bg.width, coord[1]), banner_bg)
        
        # 繪製玩家頭像
        # avatar_img = Image.open(os.path.join(f'src/avatar_img', 'ava.png'))
        if 'avatar' in self.img_container.keys():
            avatar_img = self.img_container['avatar']
        else:
            avatar_img = Image.open(os.path.join('src/avatar_img', 'ava.png'))
        
        avatar_bg = Image.open(os.path.join('src/avatar_img', 'ava_bg.png'))
        avatar_img = avatar_img.resize((180, 180))
        avatar_bg = avatar_bg.resize((216, 216))
        dx, dy = (avatar_bg.width - avatar_img.width) // 2, (avatar_bg.height - avatar_img.height) // 2
        self.image.paste(avatar_bg, (coord[0] - 80 - dx + 1, coord[1] - 80 - dy + 1), avatar_bg)
        self.image.paste(avatar_img, (coord[0] - 80, coord[1] - 80), avatar_img)


        # 繪製ptt背景框
        if 'rating_bg' in self.img_container.keys():
            ptt_box_img = self.img_container['rating_bg']
        else:
            ptt_box_img = Image.open(os.path.join(f'{self.RATING_IMG_DIR}', get_rating_img_path(ptt)))
        
        ptt_box_img = ptt_box_img.resize((110, 110))
        

        self.image.paste(ptt_box_img, coord, ptt_box_img)


        # 繪製ptt

        ptt_dec_part = str(int(ptt)) + '.'
        ptt_fixed_part = str(int((ptt - int(ptt)) * 100))

        draw_text_with_edge(self.draw, (coord[0] + 12, coord[1] + 65), f'{ptt_dec_part}', self.font_dict['ptt_dec'], (255, 255, 255), (60, 50, 66), side='bottom', ew=2)
        draw_text_with_edge(self.draw, (coord[0] + 12 + textsize(ptt_dec_part, self.font_dict['ptt_dec'])[0] - 1, coord[1] + 65), ptt_fixed_part, self.font_dict['ptt_fixed'], (255, 255, 255), (60, 50, 66), side='bottom', ew=2)

        # 繪製玩家名稱
        draw_text_with_edge(self.draw, (coord[0] + 110, coord[1] + 60), name, self.font_dict['p_name'], (255, 255, 255), (60, 50, 66), side='bottom')
        draw_text_with_shadow(self.draw, (coord[0] + 110, coord[1] + 60), name, self.font_dict['p_name'], (255, 255, 255), side='bottom')


    def draw_background(self, r10_avg_ptt, b30_avg_ptt):
        self.shadow_draw.rectangle([self.shadow_margin, 
                                    self.shadow_margin, 
                                    self.box_width + self.shadow_margin, 
                                    self.box_height + self.shadow_margin], 
                                    fill=self.shadow_color)

        # 应用模糊滤镜
        self.shadow_layer = self.shadow_layer.filter(ImageFilter.GaussianBlur(radius=self.shadow_blur_radius))
    
        # 將背景圖片裁切至畫布大小後貼上
        if self.img_width > self.bg_img.width or self.img_height > self.bg_img.height:
            max_length = max(self.img_width, self.img_height)
            if max_length > self.bg_img.width:
                self.bg_img = adaptive_resize(self.bg_img, (max_length, '*'))
            else:
                self.bg_img = adaptive_resize(self.bg_img, ('*', max_length))
    
        self.bg_img = self.bg_img.crop((self.bg_img.width // 2 - self.img_width // 2, self.bg_img.height // 2 - self.img_height // 2, self.bg_img.width // 2 + self.img_width // 2, self.bg_img.height // 2 + self.img_height // 2))
        self.image.paste(self.bg_img, (0, 0))
        self.image.paste(self.bg_mask, (0, 0), self.bg_mask)

        # 加上側邊背景
        
        self.side_img_shadow = adaptive_resize(self.side_img_shadow, ('*', self.img_height + 140))
        self.side_img = adaptive_resize(self.side_img, ('*', self.img_height + 120))
        
        self.image.paste(self.side_img_shadow, (self.img_width - self.side_img_shadow.width + 2, -5), self.side_img_shadow)
        self.image.paste(self.side_img, (self.img_width - self.side_img.width, -5), self.side_img)
        

        
        draw_text_with_edge(self.draw, (self.img_width - 20, 20), f'{self.gen_date}', self.font_dict['score'], (255, 255, 255), side='right')

        draw_text_with_edge(self.draw, (self.img_width - 20, 280), f'Recent Top 10 AVG: {r10_avg_ptt:.3f}', self.font_dict['score'], (255, 255, 255), side='right')
        draw_text_with_edge(self.draw, (self.img_width - 20, 320), f'Best 30 AVG: {b30_avg_ptt:.3f}', self.font_dict['score'], (255, 255, 255), side='right')
        
        # 加入角色立繪
        # char_img = Image.open('src/char_img/2.png')
        # char_img = adaptive_resize(char_img, (1000, '*'))
        # char_c_coord = (self.img_width - 200, self.img_height - 350)
        # self.image.paste(char_img, (char_c_coord[0] - char_img.width // 2, char_c_coord[1] - char_img.height // 2), char_img)

    def draw_info_box(self, idx, row, coord):
       
        x, y = coord
        
        # 圖片文字資訊
        title = row['title'][:18] + '...' if len(row['title']) > 20 else row['title']
        score = row['score']
        song_lv = self.song_data[self.song_data['title'] == row['title']][row['difficulty']].values[0]

        
        ptt = str(get_potential(score, song_lv)).ljust(6, '0')
        
        grade = row['grade']
    
        date = get_d_time(row['date'])


        P_amount = row['P']
        F_amount = row['F']
        L_amount = row['L']
        

        
        # 裁切封面圖至歌曲框大小
        song_img = self.img_container[idx]

        song_img = song_img.resize((self.box_width + 1, self.box_width + 1))
        song_img = song_img.crop((0, 10, self.box_width + 1, 10 + self.box_height + 1))

        # 高斯模糊
        song_img = song_img.filter(ImageFilter.BoxBlur(3))

        # 調暗圖片
        song_img = song_img.point(lambda p: p * 0.5)

        

        # 陰影打底
    
        self.image.paste(self.shadow_layer, (x - self.shadow_margin, y - self.shadow_margin), self.shadow_layer)

        self.draw.rectangle([x, y, x + self.box_width, y + self.box_height], fill=self.box_color)

        self.image.paste(song_img, (x, y))

        # 加上難度標籤
        diff_tag = self.diff_tag_img_dict[row['difficulty']]
        self.image.paste(diff_tag, (x + self.box_width - diff_tag.width + 1, y), diff_tag)
        
        # 繪製info box文字
    
        draw_text_with_edge(self.draw, (x + 10, y + 10), title, self.font_dict['title'], (255, 255, 255))

        draw_text_with_edge(self.draw, (x + 10, y + 39), score, self.font_dict['score'], (255, 255, 255))
        draw_text_with_edge(self.draw, (x + 180, y + 42), f'[{grade}]', self.font_dict['title'], (255, 255, 255))

        draw_text_with_edge(self.draw, (x + 10, y  + 76), f'Potential: {str(song_lv)} > {ptt}', self.font_dict['text'], (255, 255, 255))

        draw_text_with_edge(self.draw, (x + 10, y + 115), f'#{idx + 1}', self.font_dict['score'], (255, 255, 255))
        draw_text_with_edge(self.draw, (x + 85, y + 110), f'P: {P_amount}', self.font_dict['text'], (255, 255, 255))
        draw_text_with_edge(self.draw, (x + 85, y + 135), f'F: {F_amount} L: {L_amount}', self.font_dict['text'], (255, 255, 255))


        draw_text_with_edge(self.draw, (x + self.box_width - 16, y + 133), date, self.font_dict['date'], (255, 255, 255), side='right')


        

    def generate_b30(self, isOnline=True) -> Image:
        if isOnline:
            ret = self.get_ptt_page_online()
            if ret == 'err':
                return None
            
        else:
            self.get_ptt_page_offline('src/score.csv')
        b30_avg = self.get_avg_ptt('B30')
        r10_avg = self.get_avg_ptt('R10')
        # print(b30_avg, r10_avg)
        self.get_cover_img()
        self.draw_background(r10_avg, b30_avg)
        self.draw_banner((self.img_width - 400, 150), r10_avg * 0.25 + b30_avg * 0.75, self.username)
        for idx, row in self.score_data[:30].iterrows():
            
            x = self.start_x + (idx % 5) * (self.box_width + self.padding)
            y = self.start_y + (idx // 5) * (self.box_height + self.padding)
            self.draw_info_box(idx, row, (x, y))

        print('completed!')
        return self.image
        

if __name__ == '__main__':
    
    arcaea_render = B30Render()
    
    b30_img = arcaea_render.generate_b30(isOnline=True)
    if b30_img:
        b30_img.save('B30.png')
    