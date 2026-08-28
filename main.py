# Wokwi用 main.py
# 起動画面(6秒、区切り線がプログレスバーとしてアニメーション) → タコメーター画面
#
# 【Wokwi側の準備】
# 1. ssd1306.py をプロジェクトに追加済みであること
# 2. OLED配線: SDA -> GP0, SCL -> GP1, VCC -> 3V3, GND -> GND
# 3. パルス入力(スタブ): Clock GeneratorパーツのOUTピンを GP16 に接続
#    Clock Generatorの周波数(Hz) = RPM / 60 (R1-Z, 1回転1パルス想定)

from machine import Pin, I2C
import framebuf
import ssd1306
import time

WIDTH = 128
HEIGHT = 64

SPLASH_DURATION_SEC = 6
PROGRESS_STEPS = 30  # 滑らかさ。増やすほど滑らかになるがI2C負荷も増える

# 罫線(プログレスバー)の位置とサイズ
BAR_X = 20
BAR_Y = 30
BAR_MAX_W = WIDTH - 40

# --- OLED ---
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)

# --- パルス入力 ---
PULSE_IN_PIN = 16
PULSES_PER_REV_IN = 1   # R1-Z、片側IGコイルのみ計測の場合
SAMPLE_INTERVAL_MS = 200

pulse_count = 0


def pulse_handler(pin):
    global pulse_count
    pulse_count += 1


pulse_input = Pin(PULSE_IN_PIN, Pin.IN, Pin.PULL_DOWN)
pulse_input.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)


def calc_rpm(count, interval_ms, pulses_per_rev):
    revs = count / pulses_per_rev
    minutes = interval_ms / 1000 / 60
    return revs / minutes


def draw_text_scaled(display, text, x, y, scale=2, shear=0):
    """
    デフォルト8x8フォントをピクセル単位で拡大して描画。
    shear > 0 を指定すると、上の行ほど右にずれた疑似イタリック(斜体)になる。
    """
    w = 8 * len(text)
    h = 8
    buf = bytearray(w)
    fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_VLSB)
    fb.text(text, 0, 0, 1)

    for j in range(h):
        row_shift = (h - 1 - j) * shear
        for i in range(w):
            if fb.pixel(i, j):
                display.fill_rect(
                    x + i * scale + row_shift, y + j * scale, scale, scale, 1
                )


def draw_splash_static():
    """文字部分だけ描画(罫線部分は空けておく)"""
    oled.fill(0)

    text1 = "YAMAHA"
    scale1 = 2
    w1 = 8 * len(text1) * scale1
    x1 = (WIDTH - w1) // 2
    draw_text_scaled(oled, text1, x1, 14, scale1)

    text2 = "R1-Z"
    scale2 = 4
    shear2 = 1
    w2 = 8 * len(text2) * scale2
    x2 = (WIDTH - w2) // 2
    draw_text_scaled(oled, text2, x2, 34, scale2, shear2)


def draw_splash_with_progress():
    oled.invert(1)  # 白黒反転(白地に黒抜き)
    draw_splash_static()
    oled.show()

    step_delay = int(SPLASH_DURATION_SEC * 1000 / PROGRESS_STEPS)

    for i in range(PROGRESS_STEPS + 1):
        w = int(BAR_MAX_W * i / PROGRESS_STEPS)
        oled.fill_rect(BAR_X, BAR_Y, BAR_MAX_W, 1, 0)  # 罫線部分だけ消す
        oled.hline(BAR_X, BAR_Y, w, 1)
        oled.show()
        time.sleep_ms(step_delay)


def draw_tacho(rpm):
    oled.fill(0)

    rpm_text = str(int(rpm))

    # 桁数に応じてスケールを自動調整(画面幅128pxに収まるように)
    scale = min(4, WIDTH // (8 * len(rpm_text)))
    scale = max(1, scale)  # 万一桁数が極端に多くても最低スケール1は確保

    w = 8 * len(rpm_text) * scale
    x = (WIDTH - w) // 2
    draw_text_scaled(oled, rpm_text, x, 12, scale)

    unit_text = "rpm"
    unit_scale = 1
    unit_w = 8 * len(unit_text) * unit_scale
    unit_x = WIDTH - unit_w - 4
    draw_text_scaled(oled, unit_text, unit_x, 50, unit_scale)

    oled.show()


# --- メイン処理 ---
draw_splash_with_progress()
oled.invert(0)  # タコメーター画面は通常表示(黒地に白文字)に戻す

last_time = time.ticks_ms()

while True:
    time.sleep_ms(SAMPLE_INTERVAL_MS)

    now = time.ticks_ms()
    elapsed = time.ticks_diff(now, last_time)
    last_time = now

    pulse_input.irq(trigger=0)
    count = pulse_count
    pulse_count = 0
    pulse_input.irq(trigger=Pin.IRQ_RISING, handler=pulse_handler)

    rpm = calc_rpm(count, elapsed, PULSES_PER_REV_IN)

    draw_tacho(rpm)
