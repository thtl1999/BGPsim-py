
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import json
import math

class VideoFrameMaker:
    def __init__(self, settings, note_frames, thread_id):
        self.C, self.P = settings
        self.note_frames = note_frames
        self.thread_id = thread_id

        self.images = dict()
        image_pack_list = [
            'lane ' + self.C['lane skin id'],
            'note ' + self.C['note skin id'],
            'common'
        ]
        for image_pack in image_pack_list:
            self.add_images(image_pack)

        self.bg = Image.open('assets/bgs.png').convert('RGB').resize((self.C['width'], self.C['height']))
        game_play_line = self.img_resize(self.images['game_play_line.png'], self.C['lane scale'])
        self.paste_center(self.bg, self.C['width'] / 2, self.C['bottom'], game_play_line)
        bg_line_rhythm = self.img_resize(self.images['bg_line_rhythm.png'], self.C['lane scale'])
        self.paste_center(self.bg, self.C['width'] / 2, self.C['bottom'] - bg_line_rhythm.height / 2, bg_line_rhythm)
        jacket = self.img_resize(Image.open(self.C['music jacket']),self.C['jacket scale'])
        self.paste_center(self.bg, self.C['jacket position'][0], self.C['jacket position'][1], jacket)
        font = ImageFont.truetype('NotoSansJP-Bold.otf', self.C['font scale'])
        draw = ImageDraw.Draw(self.bg)
        draw.text(tuple(self.C['name position']), self.C['song name'], align="left", font= font)
        self.empty_image = Image.new("RGBA", (1, 1))

    def work(self):

        # cv2 bug: cannot create video object in __init__
        fourcc = cv2.VideoWriter_fourcc(*self.C['codec'])
        video_size = (self.C['width'], self.C['height'])
        video_name = 'video/' + str(self.thread_id) + 'th ' + self.C['video name']
        video = cv2.VideoWriter(video_name, fourcc, self.C['fps'], video_size)

        for frame in self.note_frames:
            bg = self.bg.copy()
            for note in frame:
                if note['type'] == 'Bar':
                    self.draw_bar(bg, note)
                elif note['type'] == 'Sim':
                    self.draw_sim(bg, note)
                elif note['type'] in ['Single', 'SingleOff', 'Flick', 'Long', 'Skill', 'Tick']:
                    self.draw_note(bg, note)

            cv2_img = self.pil2cv(bg)
            video.write(cv2_img)

        video.release()

    def pil2cv(self, pil_image):
        numpy_image = np.array(pil_image)
        if pil_image.mode == 'RGB':
            return cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
        elif pil_image.mode == 'RGBA':
            return cv2.cvtColor(numpy_image, cv2.COLOR_RGBA2BGRA)

    def add_images(self, file_name):
        json_dict = json.load(open('assets/' + file_name + '.json'))
        image = Image.open('assets/' + file_name + '.png')

        for obj in json_dict['frames']:
            frame = json_dict['frames'][obj]['frame']
            x1 = frame['x']
            y1 = frame['y']
            x2 = x1 + frame['w']
            y2 = y1 + frame['h']

            self.images[obj] = image.crop((x1, y1, x2, y2)).convert('RGBA')

    def paste_center(self, base, x, y, img):
        w, h = img.size
        base.paste(img, (int(x - w / 2), int(y - h / 2)), img)
        return

    def paste_abs(self, base, x, y, img):
        base.paste(img, (x, y), img)
        return

    def draw_bar(self, bg, note):

        if note['frame'][0] > self.C['position length']:
            bottom_distance = self.C['lane space bottom']
            total_distance = (note['lane'][1] - note['lane'][0]) * bottom_distance
            distance_per_frame = total_distance / (note['frame'][0] - note['frame'][1])
            overed_frame = note['frame'][0] - self.C['position length']
            distance = overed_frame * distance_per_frame
        else:
            distance = 0

        # cannot draw transparent color on RGB image
        overlay = Image.new('RGBA', bg.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        self.draw_gradient(draw, note, distance, self.C['edge color'], self.C['center color'], self.C['line color'])
        self.paste_abs(bg, 0, 0, overlay)

        # draw long note sprite when frame[0] is at bottom
        if note['frame'][0] == self.C['position length']:
            long_note = {
                'type': 'Long',
                'lane': 4,
                'frame': self.C['position length']
            }

            long_note_sprite = self.get_note_sprite(long_note)
            tx, ty, bx, by, ts, bs = self.get_note_pos(note)
            self.paste_center(bg, bx + distance, by, long_note_sprite)

    def draw_gradient(self, draw, note, prog_width, c1, c2, c3):
        c3 = tuple(c3)
        tx, ty, bx, by, ts, bs = self.get_note_pos(note)
        bx = bx + prog_width

        lnl_scale = self.C['lnl scale']
        NOTE_WIDTH = self.C['note width']
        NOTE_SIZE = self.C['note size']
        line_width = round(NOTE_SIZE * 3)

        trwh = lnl_scale * NOTE_WIDTH * NOTE_SIZE * ts / 2  # top real width half
        brwh = lnl_scale * NOTE_WIDTH * NOTE_SIZE * bs / 2  # bottom real width half

        for y in range(ty, by):
            r = 1 - (by - y) / (by - ty)
            x1 = int((1 - r) * (tx - trwh) + r * (bx - brwh))
            x2 = int((1 - r) * (tx + trwh) + r * (bx + brwh))

            color = list()
            r = math.sin(r * math.pi)
            for i in range(4):
                color.append(int((1 - r) * c1[i] + r * c2[i]))
            color = tuple(color)

            draw.line([(x1, y), (x2, y)], color)

        draw.line([(tx - trwh, ty), (bx - brwh, by)], c3, width=line_width)
        draw.line([(tx + trwh, ty), (bx + brwh, by)], c3, width=line_width)
        return

    def draw_sim(self, bg, note):
        note_sprite = self.get_sim_sprite(note)
        x1, x2, y, s = self.get_note_pos(note)
        self.paste_center(bg, (x1+x2)/2, y, note_sprite)

    def draw_note(self, bg, note):
        note_sprite = self.get_note_sprite(note)
        x, y, s = self.get_note_pos(note)
        self.paste_center(bg, x, y, note_sprite)
        if note['type'] == 'Flick':
            self.draw_flick_top(bg, note)

    def draw_flick_top(self, bg, note):
        x, y, s = self.get_note_pos(note)
        position = note['frame'] % self.C['flick fps']
        note_width = s * self.C['note width'] * self.C['note size']
        flicky = note_width * 0.1 + position * note_width * 0.3 / self.C['flick fps']
        flick_top = self.img_resize(self.images['note_flick_top.png'], s * self.C['note size'])
        self.paste_center(bg, x, y - flicky, flick_top)

    def draw_bpm(self, bg, bpms):
        pass

    def get_note_sprite(self, note):
        type_dict = {
            'Single': 'note_normal_',
            'Long': 'note_long_',
            'SingleOff': 'note_normal_gray_',
            'Skill': 'note_skill_',
            'Flick': 'note_flick_'
        }

        type = note['type']
        frame = note['frame']
        lane = note['lane']

        if type == 'Tick':
            img = self.images['note_slide_among.png']
        else:
            img = self.images[type_dict[type] + str(lane - 1) + '.png']

        return self.img_resize(img, self.P[frame]['r']*self.C['note size'])

    def img_resize(self, img, f):
        w, h = img.size
        if int(w * f) == 0 or int(h * f) == 0:
            return self.empty_image.copy()
        # .resize() method returns new resized image
        return img.resize((int(w * f), int(h * f)))

    def get_sim_sprite(self, note):
        img = self.images['simultaneous_line.png']
        x1, x2, y, s = self.get_note_pos(note)
        sim_width = abs(x2-x1)
        sim_height = round(img.height * self.C['note size'] * s)

        if sim_width == 0 or sim_height == 0:
            return self.empty_image.copy()
        else:
            # .resize() method returns new resized image
            return img.resize((sim_width, sim_height))

    def get_note_pos(self, note):
        if note['type'] == 'Bar':
            # frame correction
            if note['frame'][0] > self.C['position length']:
                note['frame'][0] = self.C['position length']
            if note['frame'][1] < 0:
                note['frame'][1] = 0

            # skip correction
            if note['frame'][1] < self.C['skip note']:
                note['frame'][1] = self.C['skip note']

            tx = self.P[note['frame'][1]]['x'][note['lane'][1]]
            ty = self.P[note['frame'][1]]['y']
            by = self.P[note['frame'][0]]['y']
            ts = self.P[note['frame'][1]]['r']
            bs = self.P[note['frame'][0]]['r']
            bx = self.P[note['frame'][0]]['x'][note['lane'][0]]
            return tx, ty, bx, by, ts, bs
        elif note['type'] == 'Sim':
            x1 = self.P[note['frame']]['x'][note['lane'][0]]
            x2 = self.P[note['frame']]['x'][note['lane'][1]]
            y = self.P[note['frame']]['y']
            s = self.P[note['frame']]['r']
            return x1, x2, y, s
        else:
            x = self.P[note['frame']]['x'][note['lane']]
            y = self.P[note['frame']]['y']
            s = self.P[note['frame']]['r']
            return x, y, s




